from dataclasses import dataclass
import math
import re
from typing import Any

import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt


SI_SUFFIX_FACTORS: dict[str, float] = {
    'f': 1e-15,
    'p': 1e-12,
    'n': 1e-9,
    'u': 1e-6,
    'µ': 1e-6,
    'μ': 1e-6,
    'm': 1e-3,
    'k': 1e3,
    'K': 1e3,
    'M': 1e6,
    'G': 1e9,
    'T': 1e12,
}

COLUMN_ALIASES: dict[str, str] = {
    'site': 'site',
    'val': 'value',
    'value': 'value',
    'lsl': 'lsl',
    'usl': 'usl',
    'cx': 'cx',
    'cy': 'cy',
    'date': 'testdate',
    'testdate': 'testdate',
    'sn': 'serialnumber',
    'serial': 'serialnumber',
    'serialnumber': 'serialnumber',
}

_NUM_PATTERN = re.compile(r'^([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)(f|p|n|u|µ|μ|m|k|K|M|G|T)?$')
_DATE_PATTERN = re.compile(r'^(\d{4})[/-](\d{2})[/-](\d{2})(?:[\sT_](\d{2}):(\d{2})(?::(\d{2}))?)?$')
_COL_PREFIX_PATTERN = re.compile(r'^([a-zA-Z_]+)\s*(>=|<=|>|<|=|:)(.+)$')
_CMP_PREFIX_PATTERN = re.compile(r'^(>=|<=|>|<|=)(.+)$')


@dataclass
class _FilterRule:
    kind: str  # 'text', 'regex', 'num_cmp', 'num_range', 'date_cmp', 'date_range'
    columnIdx: int  # -1 means all columns (for text/regex)
    op: str = ''
    value: Any = None
    highValue: Any = None


class PandasTableModel(QAbstractTableModel):
    def __init__(self, df:pd.DataFrame|None=None, parent=None):
        super().__init__(parent)
        self._df = df.reset_index(drop=True) if df is not None else pd.DataFrame()
        self._searchCache: list[list[str]] | None = None
        self._numericCache: dict[int, np.ndarray] = {}
        self._dateCache: dict[int, list[str]] = {}

    def setDataFrame(self, df:pd.DataFrame):
        self.beginResetModel()
        self._df = df.reset_index(drop=True)
        self._searchCache = None
        self._numericCache = {}
        self._dateCache = {}
        self.endResetModel()

    def getDataFrame(self) -> pd.DataFrame:
        return self._df

    def getColumnNames(self) -> list[str]:
        return [str(col) for col in self._df.columns]

    def clear(self):
        self.setDataFrame(pd.DataFrame())

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._df)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._df.columns)

    @staticmethod
    def _formatCell(value) -> str:
        if isinstance(value, (float, np.floating)):
            return f'{float(value):.6g}'
        return str(value)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        value = self._df.iat[index.row(), index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._formatCell(value)
        if role == Qt.ItemDataRole.UserRole:
            return value
        return None

    def headerData(self, section:int, orientation:Qt.Orientation, role:int=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)

    def _ensureSearchCache(self):
        if self._searchCache is not None:
            return

        if self._df.empty:
            self._searchCache = []
            return

        formattedColumns: list[list[str]] = []
        for col in self._df.columns:
            series = self._df[col]
            if pd.api.types.is_float_dtype(series):
                formattedColumns.append([f'{float(v):.6g}'.lower() for v in series.to_numpy()])
            else:
                formattedColumns.append([str(v).lower() for v in series.tolist()])

        self._searchCache = [list(rowTuple) for rowTuple in zip(*formattedColumns)]

    def getRowSearchTexts(self, row:int) -> list[str]:
        self._ensureSearchCache()
        if self._searchCache is None or row < 0 or row >= len(self._searchCache):
            return []
        return self._searchCache[row]

    def getNumericColumnArray(self, columnIdx:int) -> np.ndarray | None:
        if columnIdx < 0 or columnIdx >= len(self._df.columns):
            return None
        if columnIdx not in self._numericCache:
            colSeries = self._df.iloc[:, columnIdx]
            numeric = pd.to_numeric(colSeries, errors='coerce').to_numpy(dtype=float)
            self._numericCache[columnIdx] = numeric
        return self._numericCache[columnIdx]

    def getDateColumnStrings(self, columnIdx:int) -> list[str] | None:
        if columnIdx < 0 or columnIdx >= len(self._df.columns):
            return None
        if columnIdx not in self._dateCache:
            colSeries = self._df.iloc[:, columnIdx]
            self._dateCache[columnIdx] = [str(v).replace('-', '/').strip() for v in colSeries.tolist()]
        return self._dateCache[columnIdx]



class RawDataFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._query: str = ''
        self._filterColumn: int = -1
        self._regexEnabled: bool = False
        self._rules: list[_FilterRule] = []
        self._hasRegexError: bool = False
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setDynamicSortFilter(True)

    @property
    def hasRegexError(self) -> bool:
        return self._hasRegexError

    def setSourceModel(self, sourceModel):
        oldModel = self.sourceModel()
        if oldModel is not None:
            try:
                oldModel.modelReset.disconnect(self._onSourceModelReset)
            except (RuntimeError, TypeError):
                pass

        super().setSourceModel(sourceModel)

        if sourceModel is not None:
            sourceModel.modelReset.connect(self._onSourceModelReset)
        self._recompileRules()

    def _onSourceModelReset(self):
        self._recompileRules()

    def setFilterQuery(self, query: str, column: int = -1, regexEnabled: bool | None = None):
        nextRegex = self._regexEnabled if regexEnabled is None else regexEnabled
        if query == self._query and column == self._filterColumn and nextRegex == self._regexEnabled:
            return

        self._query = query
        self._filterColumn = column
        self._regexEnabled = nextRegex
        self._recompileRules()
        if not self._hasRegexError:
            self.invalidateFilter()

    def clearFilter(self):
        self._query = ''
        self._filterColumn = -1
        self._rules = []
        self._hasRegexError = False
        self.invalidateFilter()

    def _recompileRules(self):
        tokens = self._tokenizeQuery(self._query)
        if not tokens:
            self._rules = []
            self._hasRegexError = False
            return

        compiled: list[_FilterRule] = []
        try:
            for token in tokens:
                compiled.append(self._parseToken(token))
        except re.error:
            self._hasRegexError = True
            return

        self._rules = compiled
        self._hasRegexError = False

    def _parseToken(self, token: str) -> _FilterRule:
        targetCol = self._filterColumn
        expr = token

        # Optional column prefix, e.g. val>5.1, date:2025/01/01..2025/01/02, sn:^17025
        colMatch = _COL_PREFIX_PATTERN.match(token)
        if colMatch:
            aliasRaw, sep, rest = colMatch.groups()
            resolvedCol = self._resolveColumnByName(aliasRaw)
            if resolvedCol is not None:
                targetCol = resolvedCol
                expr = rest if sep == ':' else f'{sep}{rest}'

        # 1. Range expression: low..high (supports open ends like 4.9.. or ..5.1)
        if '..' in expr:
            lowRaw, highRaw = expr.split('..', 1)
            lowRaw, highRaw = lowRaw.strip(), highRaw.strip()
            if lowRaw or highRaw:
                rangeRule = self._tryBuildRangeRule(lowRaw, highRaw, targetCol)
                if rangeRule is not None:
                    return rangeRule

        # 2. Comparison expression: >=, <=, >, <, =
        cmpMatch = _CMP_PREFIX_PATTERN.match(expr)
        if cmpMatch:
            op, rhs = cmpMatch.groups()
            rhs = rhs.strip()
            cmpRule = self._tryBuildComparisonRule(op, rhs, targetCol)
            if cmpRule is not None:
                return cmpRule

        # 3. Text or Regex expression
        if self._regexEnabled:
            pattern = re.compile(expr, re.IGNORECASE)
            return _FilterRule(kind='regex', columnIdx=targetCol, value=pattern)

        return _FilterRule(kind='text', columnIdx=targetCol, value=expr.lower())


    def _tryBuildRangeRule(self,lowRaw:str, highRaw:str, targetCol:int) -> _FilterRule | None:
        # Try Date range
        lowDate = self._parseDateBound(lowRaw, isUpper=False) if lowRaw else None
        highDate = self._parseDateBound(highRaw, isUpper=True) if highRaw else None
        if (not lowRaw or lowDate is not None) and (not highRaw or highDate is not None):
            if lowDate is not None or highDate is not None:
                colIdx = targetCol if targetCol >= 0 else self._getDefaultDateColumn()
                return _FilterRule(kind='date_range', columnIdx=colIdx, value=lowDate, highValue=highDate)

        # Try Numeric range
        lowNum = self._parseNumericValue(lowRaw) if lowRaw else None
        highNum = self._parseNumericValue(highRaw) if highRaw else None
        if (not lowRaw or lowNum is not None) and (not highRaw or highNum is not None):
            if lowNum is not None or highNum is not None:
                colIdx = targetCol if targetCol >= 0 else self._getDefaultNumericColumn()
                return _FilterRule(kind='num_range', columnIdx=colIdx, value=lowNum, highValue=highNum)

        return None

    def _tryBuildComparisonRule(self, op:str, rhs:str, targetCol:int) -> _FilterRule | None:
        # Try Date comparison
        if _DATE_PATTERN.match(rhs):
            colIdx = targetCol if targetCol >= 0 else self._getDefaultDateColumn()
            if op == '=':
                lowDate = self._parseDateBound(rhs, isUpper=False)
                highDate = self._parseDateBound(rhs, isUpper=True)
                return _FilterRule(kind='date_range', columnIdx=colIdx, value=lowDate, highValue=highDate)
            isUpper = op in ('>', '<=')
            bound = self._parseDateBound(rhs, isUpper=isUpper)
            return _FilterRule(kind='date_cmp', columnIdx=colIdx, op=op, value=bound)

        # Try Numeric comparison
        numVal = self._parseNumericValue(rhs)
        if numVal is not None:
            colIdx = targetCol if targetCol >= 0 else self._getDefaultNumericColumn()
            return _FilterRule(kind='num_cmp', columnIdx=colIdx, op=op, value=numVal)

        return None

    def _resolveColumnByName(self, name:str) -> int|None:
        model = self.sourceModel()
        if not isinstance(model, PandasTableModel):
            return None

        key = name.strip().lower()
        canonical = COLUMN_ALIASES.get(key, key)
        for idx, colName in enumerate(model.getColumnNames()):
            if colName.lower() == canonical:
                return idx
        return None

    def _getDefaultNumericColumn(self) -> int:
        model = self.sourceModel()
        if not isinstance(model, PandasTableModel):
            return -1

        colsLower = [c.lower() for c in model.getColumnNames()]
        for preferred in ('value', 'cx', 'cy', 'lsl', 'usl'):
            if preferred in colsLower:
                return colsLower.index(preferred)
        return 0 if colsLower else -1

    def _getDefaultDateColumn(self) -> int:
        model = self.sourceModel()
        if not isinstance(model, PandasTableModel):
            return -1

        colsLower = [c.lower() for c in model.getColumnNames()]
        for preferred in ('testdate', 'date'):
            if preferred in colsLower:
                return colsLower.index(preferred)
        return -1

    @staticmethod
    def _tokenizeQuery(query:str) -> list[str]:
        tokens: list[str] = []
        current: list[str] = []
        inQuotes = False
        for ch in query:
            if ch == '"':
                inQuotes = not inQuotes
            elif ch.isspace() and not inQuotes:
                if current:
                    tokens.append(''.join(current))
                    current = []
            else:
                current.append(ch)
        if current:
            tokens.append(''.join(current))
        return tokens

    @staticmethod
    def _parseNumericValue(raw:str) -> float|None:
        match = _NUM_PATTERN.match(raw.strip())
        if not match:
            return None
        numStr, suffix = match.groups()
        try:
            base = float(numStr)
        except ValueError:
            return None
        factor = SI_SUFFIX_FACTORS.get(suffix, 1.0) if suffix else 1.0
        return base * factor

    @staticmethod
    def _parseDateBound(raw:str, isUpper:bool) -> str|None:
        match = _DATE_PATTERN.match(raw.strip())
        if not match:
            return None
        year, month, day, hour, minute, second = match.groups()
        if hour is None:
            timePart = '23:59:59' if isUpper else '00:00:00'
        elif second is None:
            timePart = f'{hour}:{minute}:{"59" if isUpper else "00"}'
        else:
            timePart = f'{hour}:{minute}:{second}'
        return f'{year}/{month}/{day} {timePart}'

    @staticmethod
    def _compare(lhs:Any, op:str, rhs:Any) -> bool:
        if op == '>':
            return lhs > rhs
        
        if op == '>=':
            return lhs >= rhs
        
        if op == '<':
            return lhs < rhs
        
        if op == '<=':
            return lhs <= rhs
        
        if op == '=':
            if isinstance(lhs, float) and isinstance(rhs, float):
                return math.isclose(lhs, rhs, rel_tol=1e-9, abs_tol=1e-12)
            return lhs == rhs
        return False

    def filterAcceptsRow(self, sourceRow:int, sourceParent:QModelIndex) -> bool:
        if not self._rules:
            return True

        model = self.sourceModel()
        if not isinstance(model, PandasTableModel):
            return super().filterAcceptsRow(sourceRow, sourceParent)

        rowTexts: list[str] | None = None

        for rule in self._rules:
            if rule.kind in ('text', 'regex'):
                if rowTexts is None:
                    rowTexts = model.getRowSearchTexts(sourceRow)
                if not rowTexts:
                    return False

                if 0 <= rule.columnIdx < len(rowTexts):
                    target = rowTexts[rule.columnIdx]
                    matched = bool(rule.value.search(target)) if rule.kind == 'regex' else (rule.value in target)
                else:
                    if rule.kind == 'regex':
                        matched = any(rule.value.search(cell) for cell in rowTexts)
                    else:
                        matched = any(rule.value in cell for cell in rowTexts)
                if not matched:
                    return False

            elif rule.kind in ('num_cmp', 'num_range'):
                arr = model.getNumericColumnArray(rule.columnIdx)
                if arr is None or sourceRow >= len(arr):
                    return False
                val = float(arr[sourceRow])
                if math.isnan(val):
                    return False

                if rule.kind == 'num_cmp':
                    if not self._compare(val, rule.op, rule.value):
                        return False
                else:
                    if rule.value is not None and val < rule.value:
                        return False
                    if rule.highValue is not None and val > rule.highValue:
                        return False

            elif rule.kind in ('date_cmp', 'date_range'):
                dates = model.getDateColumnStrings(rule.columnIdx)
                if dates is None or sourceRow >= len(dates):
                    return False
                dateVal = dates[sourceRow]
                if not dateVal:
                    return False

                if rule.kind == 'date_cmp':
                    if not self._compare(dateVal, rule.op, rule.value):
                        return False
                else:
                    if rule.value is not None and dateVal < rule.value:
                        return False
                    if rule.highValue is not None and dateVal > rule.highValue:
                        return False

        return True

    def lessThan(self, sourceLeft:QModelIndex, sourceRight:QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return super().lessThan(sourceLeft, sourceRight)

        leftVal = model.data(sourceLeft, Qt.ItemDataRole.UserRole)
        rightVal = model.data(sourceRight, Qt.ItemDataRole.UserRole)

        leftNum = self._tryFloat(leftVal)
        rightNum = self._tryFloat(rightVal)

        if leftNum is not None and rightNum is not None:
            leftNan = math.isnan(leftNum)
            rightNan = math.isnan(rightNum)
            if leftNan and rightNan:
                return False
            if leftNan:
                return False
            if rightNan:
                return True
            return leftNum < rightNum

        return str(leftVal).lower() < str(rightVal).lower()

    @staticmethod
    def _tryFloat(value) -> float|None:
        if isinstance(value, (int, float, np.integer, np.floating)):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return float(stripped)
            except ValueError:
                return None
        return None

    def getFilteredDataFrame(self) -> pd.DataFrame:
        model = self.sourceModel()
        if not isinstance(model, PandasTableModel):
            return pd.DataFrame()

        sourceDf = model.getDataFrame()
        if sourceDf.empty or self.rowCount() == 0:
            return sourceDf.iloc[0:0].copy()

        sourceRows = [
            self.mapToSource(self.index(row, 0)).row()
            for row in range(self.rowCount())
        ]
        return sourceDf.iloc[sourceRows].reset_index(drop=True)