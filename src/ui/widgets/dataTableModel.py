from dataclasses import dataclass
import math
import re
from typing import Any

import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


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
    def __init__(self, df: pd.DataFrame | None = None, parent=None):
        super().__init__(parent)
        self._df = pd.DataFrame()
        self._columnNames: list[str] = []
        self._columnArrays: list[np.ndarray] = []

        self._filteredIndices: np.ndarray = np.empty(0, dtype=np.int64)
        self._viewIndices: np.ndarray = np.empty(0, dtype=np.int64)

        self._query: str = ''
        self._filterColumn: int = -1
        self._regexEnabled: bool = False
        self._rules: list[_FilterRule] = []
        self._hasRegexError: bool = False

        self._sortColumn: int = -1
        self._sortOrder: Qt.SortOrder = Qt.SortOrder.AscendingOrder

        # Lazy caches built only when a filter/sort actually uses that column
        self._textCache: dict[int, pd.Series] = {}
        self._numericCache: dict[int, np.ndarray] = {}
        self._dateCache: dict[int, pd.Series] = {}
        self._isPureNumericColCache: dict[int, bool] = {}

        if df is not None:
            self.setDataFrame(df)

    @property
    def hasRegexError(self) -> bool:
        return self._hasRegexError

    def setDataFrame(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df.reset_index(drop=True) if df is not None else pd.DataFrame()
        self._columnNames = [str(col) for col in self._df.columns]
        self._columnArrays = [self._df[col].to_numpy() for col in self._df.columns]

        self._textCache = {}
        self._numericCache = {}
        self._dateCache = {}
        self._isPureNumericColCache = {}

        if self._sortColumn >= len(self._columnNames):
            self._sortColumn = -1

        self._recompileRules()
        self._computeFilteredIndices()
        self._applyCurrentSort()
        self.endResetModel()

    def getDataFrame(self) -> pd.DataFrame:
        return self._df

    def getFilteredDataFrame(self) -> pd.DataFrame:
        if self._df.empty or len(self._viewIndices) == 0:
            return self._df.iloc[0:0].copy()
        return self._df.iloc[self._viewIndices].reset_index(drop=True)

    def getColumnNames(self) -> list[str]:
        return list(self._columnNames)

    def totalRowCount(self) -> int:
        return len(self._df)

    def clear(self):
        self._query = ''
        self._filterColumn = -1
        self._rules = []
        self._hasRegexError = False
        self._sortColumn = -1
        self.setDataFrame(pd.DataFrame())

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._viewIndices)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._columnNames)

    @staticmethod
    def _formatCell(value) -> str:
        if isinstance(value, (float, np.floating)):
            return f'{float(value):.6g}'
        return str(value)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._viewIndices) or col < 0 or col >= len(self._columnArrays):
            return None

        sourceRow = int(self._viewIndices[row])
        value = self._columnArrays[col][sourceRow]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._formatCell(value)
        if role == Qt.ItemDataRole.UserRole:
            return value
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._columnNames):
                return self._columnNames[section]
            return None
        return str(section + 1)

    def setFilterQuery(self, query: str, column: int = -1, regexEnabled: bool | None = None):
        nextRegex = self._regexEnabled if regexEnabled is None else regexEnabled
        if query == self._query and column == self._filterColumn and nextRegex == self._regexEnabled:
            return

        self._query = query
        self._filterColumn = column
        self._regexEnabled = nextRegex
        self._recompileRules()

        if self._hasRegexError:
            return

        self.beginResetModel()
        self._computeFilteredIndices()
        self._applyCurrentSort()
        self.endResetModel()

    def clearFilter(self):
        self.setFilterQuery('', -1, self._regexEnabled)

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder):
        if column < 0 or column >= len(self._columnNames):
            if self._sortColumn == -1:
                return
            self._sortColumn = -1
            self.beginResetModel()
            self._viewIndices = self._filteredIndices
            self.endResetModel()
            return

        self._sortColumn = column
        self._sortOrder = order
        self.beginResetModel()
        self._applyCurrentSort()
        self.endResetModel()

    def _applyCurrentSort(self):
        indices = self._filteredIndices
        if self._sortColumn < 0 or self._sortColumn >= len(self._columnNames) or len(indices) <= 1:
            self._viewIndices = indices
            return

        descending = self._sortOrder == Qt.SortOrder.DescendingOrder
        colIdx = self._sortColumn

        if self._isNumericSortableColumn(colIdx):
            numArr = self._getNumericArray(colIdx)[indices]
            nanMask = np.isnan(numArr)
            validPos = np.flatnonzero(~nanMask)
            nanPos = np.flatnonzero(nanMask)

            if len(validPos) > 0:
                validVals = numArr[validPos]
                orderPos = np.argsort(validVals, kind='mergesort')
                if descending:
                    orderPos = orderPos[::-1]
                sortedPos = np.concatenate((validPos[orderPos], nanPos))
            else:
                sortedPos = nanPos
            self._viewIndices = indices[sortedPos]
        else:
            rawCol = self._columnArrays[colIdx][indices]
            strSeries = pd.Series(rawCol).astype(str).str.lower()
            orderPos = strSeries.argsort(kind='mergesort').to_numpy(dtype=np.int64)
            if descending:
                orderPos = orderPos[::-1]
            self._viewIndices = indices[orderPos]

    def _isNumericSortableColumn(self, colIdx: int) -> bool:
        if colIdx in self._isPureNumericColCache:
            return self._isPureNumericColCache[colIdx]

        series = self._df.iloc[:, colIdx]
        if pd.api.types.is_numeric_dtype(series):
            self._isPureNumericColCache[colIdx] = True
            return True

        nonEmpty = series.dropna().astype(str).str.strip()
        nonEmpty = nonEmpty[nonEmpty != '']
        if nonEmpty.empty:
            self._isPureNumericColCache[colIdx] = False
            return False

        converted = pd.to_numeric(nonEmpty, errors='coerce')
        isNumeric = bool(converted.notna().all())
        self._isPureNumericColCache[colIdx] = isNumeric
        return isNumeric

    def _getNumericArray(self, colIdx: int) -> np.ndarray:
        if colIdx not in self._numericCache:
            series = self._df.iloc[:, colIdx]
            self._numericCache[colIdx] = pd.to_numeric(series, errors='coerce').to_numpy(dtype=float)
        return self._numericCache[colIdx]

    def _getDateSeries(self, colIdx: int) -> pd.Series:
        if colIdx not in self._dateCache:
            series = self._df.iloc[:, colIdx]
            self._dateCache[colIdx] = series.astype(str).str.replace('-', '/', regex=False).str.strip()
        return self._dateCache[colIdx]

    def _getTextSeries(self, colIdx: int) -> pd.Series:
        if colIdx not in self._textCache:
            series = self._df.iloc[:, colIdx]
            if pd.api.types.is_float_dtype(series):
                formatted = [f'{float(v):.6g}'.lower() for v in series.to_numpy()]
                self._textCache[colIdx] = pd.Series(formatted, dtype=object)
            else:
                self._textCache[colIdx] = series.astype(str).str.lower()
        return self._textCache[colIdx]

    def _computeFilteredIndices(self):
        n = len(self._df)
        if n == 0:
            self._filteredIndices = np.empty(0, dtype=np.int64)
            return

        if not self._rules:
            self._filteredIndices = np.arange(n, dtype=np.int64)
            return

        mask = np.ones(n, dtype=bool)
        numCols = len(self._columnNames)

        for rule in self._rules:
            if not np.any(mask):
                break

            if rule.kind in ('text', 'regex'):
                isRegex = rule.kind == 'regex'
                pattern = rule.value
                if 0 <= rule.columnIdx < numCols:
                    colSeries = self._getTextSeries(rule.columnIdx)
                    colMask = colSeries.str.contains(
                        pattern, case=True, regex=isRegex, na=False
                    ).to_numpy(dtype=bool)
                    mask &= colMask
                else:
                    anyColMask = np.zeros(n, dtype=bool)
                    for colIdx in range(numCols):
                        colSeries = self._getTextSeries(colIdx)
                        anyColMask |= colSeries.str.contains(
                            pattern, case=True, regex=isRegex, na=False
                        ).to_numpy(dtype=bool)
                    mask &= anyColMask

            elif rule.kind in ('num_cmp', 'num_range'):
                if rule.columnIdx < 0 or rule.columnIdx >= numCols:
                    mask[:] = False
                    break
                arr = self._getNumericArray(rule.columnIdx)
                valid = ~np.isnan(arr)
                if rule.kind == 'num_cmp':
                    mask &= valid & self._compareNumericArray(arr, rule.op, rule.value)
                else:
                    subMask = valid.copy()
                    if rule.value is not None:
                        subMask &= arr >= rule.value
                    if rule.highValue is not None:
                        subMask &= arr <= rule.highValue
                    mask &= subMask

            elif rule.kind in ('date_cmp', 'date_range'):
                if rule.columnIdx < 0 or rule.columnIdx >= numCols:
                    mask[:] = False
                    break
                dates = self._getDateSeries(rule.columnIdx)
                nonEmpty = (dates != '').to_numpy(dtype=bool)
                if rule.kind == 'date_cmp':
                    mask &= nonEmpty & self._compareDateSeries(dates, rule.op, rule.value)
                else:
                    subMask = nonEmpty.copy()
                    if rule.value is not None:
                        subMask &= (dates >= rule.value).to_numpy(dtype=bool)
                    if rule.highValue is not None:
                        subMask &= (dates <= rule.highValue).to_numpy(dtype=bool)
                    mask &= subMask

        self._filteredIndices = np.flatnonzero(mask).astype(np.int64)

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

        colMatch = _COL_PREFIX_PATTERN.match(token)
        if colMatch:
            aliasRaw, sep, rest = colMatch.groups()
            resolvedCol = self._resolveColumnByName(aliasRaw)
            if resolvedCol is not None:
                targetCol = resolvedCol
                expr = rest if sep == ':' else f'{sep}{rest}'

        if '..' in expr:
            lowRaw, highRaw = expr.split('..', 1)
            lowRaw, highRaw = lowRaw.strip(), highRaw.strip()
            if lowRaw or highRaw:
                rangeRule = self._tryBuildRangeRule(lowRaw, highRaw, targetCol)
                if rangeRule is not None:
                    return rangeRule

        cmpMatch = _CMP_PREFIX_PATTERN.match(expr)
        if cmpMatch:
            op, rhs = cmpMatch.groups()
            rhs = rhs.strip()
            cmpRule = self._tryBuildComparisonRule(op, rhs, targetCol)
            if cmpRule is not None:
                return cmpRule

        if self._regexEnabled:
            pattern = re.compile(expr, re.IGNORECASE)
            return _FilterRule(kind='regex', columnIdx=targetCol, value=pattern)

        return _FilterRule(kind='text', columnIdx=targetCol, value=expr.lower())

    def _tryBuildRangeRule(self, lowRaw: str, highRaw: str, targetCol: int) -> _FilterRule | None:
        lowDate = self._parseDateBound(lowRaw, isUpper=False) if lowRaw else None
        highDate = self._parseDateBound(highRaw, isUpper=True) if highRaw else None
        if (not lowRaw or lowDate is not None) and (not highRaw or highDate is not None):
            if lowDate is not None or highDate is not None:
                colIdx = targetCol if targetCol >= 0 else self._getDefaultDateColumn()
                return _FilterRule(kind='date_range', columnIdx=colIdx, value=lowDate, highValue=highDate)

        lowNum = self._parseNumericValue(lowRaw) if lowRaw else None
        highNum = self._parseNumericValue(highRaw) if highRaw else None
        if (not lowRaw or lowNum is not None) and (not highRaw or highNum is not None):
            if lowNum is not None or highNum is not None:
                colIdx = targetCol if targetCol >= 0 else self._getDefaultNumericColumn()
                return _FilterRule(kind='num_range', columnIdx=colIdx, value=lowNum, highValue=highNum)

        return None

    def _tryBuildComparisonRule(self, op: str, rhs: str, targetCol: int) -> _FilterRule | None:
        if _DATE_PATTERN.match(rhs):
            colIdx = targetCol if targetCol >= 0 else self._getDefaultDateColumn()
            if op == '=':
                lowDate = self._parseDateBound(rhs, isUpper=False)
                highDate = self._parseDateBound(rhs, isUpper=True)
                return _FilterRule(kind='date_range', columnIdx=colIdx, value=lowDate, highValue=highDate)
            isUpper = op in ('>', '<=')
            bound = self._parseDateBound(rhs, isUpper=isUpper)
            return _FilterRule(kind='date_cmp', columnIdx=colIdx, op=op, value=bound)

        numVal = self._parseNumericValue(rhs)
        if numVal is not None:
            colIdx = targetCol if targetCol >= 0 else self._getDefaultNumericColumn()
            return _FilterRule(kind='num_cmp', columnIdx=colIdx, op=op, value=numVal)

        return None

    def _resolveColumnByName(self, name: str) -> int | None:
        key = name.strip().lower()
        canonical = COLUMN_ALIASES.get(key, key)
        for idx, colName in enumerate(self._columnNames):
            if colName.lower() == canonical:
                return idx
        return None

    def _getDefaultNumericColumn(self) -> int:
        colsLower = [c.lower() for c in self._columnNames]
        for preferred in ('value', 'cx', 'cy', 'lsl', 'usl'):
            if preferred in colsLower:
                return colsLower.index(preferred)
        return 0 if colsLower else -1

    def _getDefaultDateColumn(self) -> int:
        colsLower = [c.lower() for c in self._columnNames]
        for preferred in ('testdate', 'date'):
            if preferred in colsLower:
                return colsLower.index(preferred)
        return -1

    @staticmethod
    def _tokenizeQuery(query: str) -> list[str]:
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
    def _parseNumericValue(raw: str) -> float | None:
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
    def _parseDateBound(raw: str, isUpper: bool) -> str | None:
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
    def _compareNumericArray(arr: np.ndarray, op: str, rhs: float) -> np.ndarray:
        if op == '>':
            return arr > rhs
        if op == '>=':
            return arr >= rhs
        if op == '<':
            return arr < rhs
        if op == '<=':
            return arr <= rhs
        if op == '=':
            return np.isclose(arr, rhs, rtol=1e-9, atol=1e-12)
        return np.zeros(len(arr), dtype=bool)

    @staticmethod
    def _compareDateSeries(dates: pd.Series, op: str, rhs: str) -> np.ndarray:
        if op == '>':
            return (dates > rhs).to_numpy(dtype=bool)
        if op == '>=':
            return (dates >= rhs).to_numpy(dtype=bool)
        if op == '<':
            return (dates < rhs).to_numpy(dtype=bool)
        if op == '<=':
            return (dates <= rhs).to_numpy(dtype=bool)
        if op == '=':
            return (dates == rhs).to_numpy(dtype=bool)
        return np.zeros(len(dates), dtype=bool)