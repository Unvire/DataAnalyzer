import math
import os
import re

import numpy as np
import pandas as pd
from PySide6.QtCore import QModelIndex, QTimer, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSplitter, QTableView, QVBoxLayout,
    QWidget,
)

from src.siFormatter import formatSiValue
from src.ui.widgets.dataTableModel import PandasTableModel
from src.ui.widgets.plotlyView import PlotlyView
from src.ui.workers import YieldAnalysisWorker
from src.yieldParetoAnalyzer import BatchSummaryResult, SUMMARY_COLUMNS, YieldParetoAnalyzer


class YieldSummaryTableModel(PandasTableModel):
    HEADER_LABELS: dict[str, str] = {
        'TestName': 'Test Name',
        'Samples': 'Samples',
        'Fails': 'Fails',
        'FailLow': 'Fail L',
        'FailHigh': 'Fail H',
        'YieldPct': 'Yield',
        'DPMO': 'DPMO',
        'Ppk': 'Ppk',
        'Cpk': 'Cpk',
        'PpkNP': 'Ppk (NP)',
        'SiteDeltaPct': 'Site Δ',
        'LSL': 'LSL',
        'USL': 'USL',
        'Mean': 'Mean',
        'Sigma': 'Sigma',
    }

    SUMMARY_ALIASES: dict[str, str] = {
        'test': 'testname',
        'name': 'testname',
        'testname': 'testname',
        'samples': 'samples',
        'n': 'samples',
        'fails': 'fails',
        'fail': 'fails',
        'faillow': 'faillow',
        'failhigh': 'failhigh',
        'yield': 'yieldpct',
        'yieldpct': 'yieldpct',
        'dpmo': 'dpmo',
        'ppm': 'dpmo',
        'ppk': 'ppk',
        'cpk': 'cpk',
        'ppknp': 'ppknp',
        'delta': 'sitedeltapct',
        'sitedelta': 'sitedeltapct',
        'lsl': 'lsl',
        'usl': 'usl',
        'mean': 'mean',
        'sigma': 'sigma',
    }

    COLOR_OK = QColor('#66bb6a')
    COLOR_WARN = QColor('#ffa726')
    COLOR_BAD = QColor('#ef5350')

    def headerData(self, section:int, orientation:Qt.Orientation, role:int=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._columnNames):
                colName = self._columnNames[section]
                return self.HEADER_LABELS.get(colName, colName)
        return super().headerData(section, orientation, role)

    def data(self, index:QModelIndex, role:int=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._viewIndices) or col < 0 or col >= len(self._columnArrays):
            return None

        sourceRow = int(self._viewIndices[row])
        colName = self._columnNames[col]
        value = self._columnArrays[col][sourceRow]

        if role == Qt.ItemDataRole.UserRole:
            return value

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if colName == 'TestName':
                return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.DisplayRole:
            return self._formatSummaryCell(colName, value)

        if role == Qt.ItemDataRole.ForegroundRole:
            return self._getStatusColor(colName, value)

        return None

    def getTestNameAtRow(self, viewRow:int) -> str:
        if viewRow < 0 or viewRow >= len(self._viewIndices) or 'TestName' not in self._columnNames:
            return ''
        colIdx = self._columnNames.index('TestName')
        sourceRow = int(self._viewIndices[viewRow])
        return str(self._columnArrays[colIdx][sourceRow])

    def _resolveColumnByName(self, name:str) -> int|None:
        key = name.strip().lower()
        canonical = self.SUMMARY_ALIASES.get(key)
        if canonical:
            for idx, colName in enumerate(self._columnNames):
                if colName.lower() == canonical:
                    return idx
        return super()._resolveColumnByName(name)

    def _getDefaultNumericColumn(self) -> int:
        colsLower = [c.lower() for c in self._columnNames]
        for preferred in ('fails', 'yieldpct', 'ppk', 'cpk'):
            if preferred in colsLower:
                return colsLower.index(preferred)
        return super()._getDefaultNumericColumn()

    @staticmethod
    def _isMissing(value) -> bool:
        if value is None:
            return True
        if isinstance(value, (float, np.floating)):
            return math.isnan(float(value))
        return False

    @classmethod
    def _formatSummaryCell(cls, colName:str, value) -> str:
        if cls._isMissing(value):
            return '—'

        if colName == 'TestName':
            return str(value)
        if colName in ('Samples', 'Fails', 'FailLow', 'FailHigh'):
            return f'{int(value):,}'
        if colName == 'YieldPct':
            return f'{float(value):.2f}%'
        if colName == 'DPMO':
            v = float(value)
            if v == 0.0:
                return '0'
            return f'{v:.1f}' if v < 10.0 else f'{v:,.0f}'
        if colName in ('Ppk', 'Cpk', 'PpkNP'):
            return f'{float(value):.2f}'
        if colName == 'SiteDeltaPct':
            return f'{float(value):.1f}%'
        if colName in ('LSL', 'USL', 'Mean', 'Sigma'):
            return formatSiValue(float(value), precision=4)
        return str(value)

    @classmethod
    def _getStatusColor(cls, colName:str, value) -> QColor|None:
        if cls._isMissing(value):
            return None

        if colName == 'Fails':
            return cls.COLOR_BAD if int(value) > 0 else cls.COLOR_OK
        
        if colName == 'YieldPct':
            v = float(value)
            if v >= 99.5:
                return cls.COLOR_OK
            return cls.COLOR_WARN if v >= 98.0 else cls.COLOR_BAD
        
        if colName in ('Ppk', 'Cpk', 'PpkNP'):
            v = float(value)
            if v >= 1.33:
                return cls.COLOR_OK
            return cls.COLOR_WARN if v >= 1.00 else cls.COLOR_BAD
        
        if colName == 'SiteDeltaPct':
            v = float(value)
            if v <= 10.0:
                return cls.COLOR_OK
            return cls.COLOR_WARN if v <= 25.0 else cls.COLOR_BAD
        
        return None


class YieldParetoTab(QWidget):
    testActivated = Signal(str)
    statusMessageRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._analyzer = YieldParetoAnalyzer()
        self._measurements: dict[str, pd.DataFrame] = {}
        self._lastResult: BatchSummaryResult | None = None
        self._isDirty = False
        self._requestCounter = 0
        self._worker: YieldAnalysisWorker | None = None

        self._filterTimer = QTimer(self)
        self._filterTimer.setSingleShot(True)
        self._filterTimer.setInterval(150)
        self._filterTimer.timeout.connect(self._applyTableFilter)

        self._buildUi()
        self._bindEvents()
        self._setControlsEnabled(False)

    def _buildUi(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Top controls bar
        controlsRow = QHBoxLayout()
        controlsRow.setSpacing(8)

        self.chartModeLabel = QLabel('Chart:')
        self.chartModeComboBox = QComboBox()
        self.chartModeComboBox.addItems([
            'Defect Pareto (Fails)',
            'Weakest Capability (Ppk)',
            'Highest Site Delta (%)',
        ])
        self.chartModeComboBox.setStyleSheet("""
            QComboBox {
                font-weight: 600;
                border: 1px solid #3574f0;
                padding: 4px 10px;
                min-width: 185px;
            }
        """)

        self.siteLabel = QLabel('Site:')
        self.siteComboBox = QComboBox()
        self.siteComboBox.addItem('All sites')
        self.siteComboBox.setMinimumWidth(95)

        self.limitsLabel = QLabel('Limits:')
        self.limitsComboBox = QComboBox()
        self.limitsComboBox.addItems(['All', 'Newest', 'Oldest'])

        self.topNLabel = QLabel('Top:')
        self.topNComboBox = QComboBox()
        self.topNComboBox.addItems(['15', '20', '30', '50', 'All'])
        self.topNComboBox.setCurrentText('20')

        for combo in (
            self.chartModeComboBox,
            self.siteComboBox,
            self.limitsComboBox,
            self.topNComboBox,
        ):
            combo.setCursor(Qt.CursorShape.PointingHandCursor)

        self.copyPlotButton = QPushButton('Copy plot')
        self.copyPlotButton.setCursor(Qt.CursorShape.PointingHandCursor)

        self.exportCsvButton = QPushButton('Export CSV')
        self.exportCsvButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exportCsvButton.setToolTip('Export filtered batch summary table to CSV')

        controlsRow.addWidget(self.chartModeLabel)
        controlsRow.addWidget(self.chartModeComboBox)
        controlsRow.addWidget(self.siteLabel)
        controlsRow.addWidget(self.siteComboBox)
        controlsRow.addWidget(self.limitsLabel)
        controlsRow.addWidget(self.limitsComboBox)
        controlsRow.addWidget(self.topNLabel)
        controlsRow.addWidget(self.topNComboBox)
        controlsRow.addStretch(1)
        controlsRow.addWidget(self.copyPlotButton)
        controlsRow.addWidget(self.exportCsvButton)

        # KPI summary cards
        kpiRow = QHBoxLayout()
        kpiRow.setSpacing(8)
        self._kpiLabels: dict[str, QLabel] = {}
        for key, title in (
            ('boardYield', 'Board Yield (Runs)'),
            ('failingTests', 'Failing Tests'),
            ('totalFails', 'Total Fails'),
            ('worstYield', 'Lowest Yield Test'),
            ('worstPpk', 'Lowest Ppk Test'),
        ):
            card, valLabel = self._createKpiCard(title)
            self._kpiLabels[key] = valLabel
            kpiRow.addWidget(card, 1)

        # Main vertical splitter: Pareto chart on top, sortable batch table on bottom
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        self.plotView = PlotlyView(enablePointCard=False)
        self.plotView.showMessage('Load logs and open this tab to generate Yield & Pareto analysis.')

        tableContainer = QWidget()
        tableLayout = QVBoxLayout(tableContainer)
        tableLayout.setContentsMargins(0, 4, 0, 0)
        tableLayout.setSpacing(6)

        filterRow = QHBoxLayout()
        filterRow.setSpacing(8)

        self.searchEdit = QLineEdit()
        self.searchEdit.setPlaceholderText(
            'Filter batch tests: name/regex, fails>0, yield<99, ppk<1.33, delta>15'
        )
        self.searchEdit.setToolTip(
            'Double-click any row to jump directly to its plot.\n'
            'Supports multi-term filters: fails>0, yield<99.5, ppk<1.33, cpk<1.33, delta>10'
        )
        self.searchEdit.setClearButtonEnabled(True)

        self.regexButton = QPushButton('Regex')
        self.regexButton.setCheckable(True)
        self.regexButton.setCursor(Qt.CursorShape.PointingHandCursor)

        self.onlyFailingButton = QPushButton('Only failing')
        self.onlyFailingButton.setCheckable(True)
        self.onlyFailingButton.setCursor(Qt.CursorShape.PointingHandCursor)

        self.tableInfoLabel = QLabel('No data loaded')
        self.tableInfoLabel.setStyleSheet('color: #9da0a8;')

        filterRow.addWidget(self.searchEdit, 1)
        filterRow.addWidget(self.regexButton)
        filterRow.addWidget(self.onlyFailingButton)
        filterRow.addWidget(self.tableInfoLabel)

        self.tableModel = YieldSummaryTableModel()
        self.tableView = QTableView()
        self.tableView.setModel(self.tableModel)
        self.tableView.setAlternatingRowColors(True)
        self.tableView.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tableView.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.tableView.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.tableView.setSortingEnabled(True)
        self.tableView.verticalHeader().setDefaultSectionSize(24)

        tableLayout.addLayout(filterRow)
        tableLayout.addWidget(self.tableView, 1)

        self.splitter.addWidget(self.plotView)
        self.splitter.addWidget(tableContainer)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([380, 320])

        layout.addLayout(controlsRow)
        layout.addLayout(kpiRow)
        layout.addWidget(self.splitter, 1)

    @staticmethod
    def _createKpiCard(title:str) -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #26282e;
                border: 1px solid #393b40;
                border-radius: 6px;
            }
        """)
        cardLayout = QVBoxLayout(frame)
        cardLayout.setContentsMargins(10, 6, 10, 6)
        cardLayout.setSpacing(2)

        titleLabel = QLabel(title)
        titleLabel.setStyleSheet('color: #9da0a8; font-size: 11px; border: none;')

        valLabel = QLabel('—')
        valLabel.setStyleSheet(
            'color: #dfe1e5; font-size: 14px; font-weight: 600; '
            'font-family: "Consolas", "Cascadia Mono", monospace; border: none;'
        )

        cardLayout.addWidget(titleLabel)
        cardLayout.addWidget(valLabel)
        return frame, valLabel

    def _bindEvents(self):
        self.chartModeComboBox.currentTextChanged.connect(self._redrawParetoChart)
        self.topNComboBox.currentTextChanged.connect(self._redrawParetoChart)
        self.siteComboBox.currentTextChanged.connect(self._onAnalysisParamsChanged)
        self.limitsComboBox.currentTextChanged.connect(self._onAnalysisParamsChanged)
        self.copyPlotButton.clicked.connect(self._onCopyPlotClicked)
        self.exportCsvButton.clicked.connect(self._onExportCsvClicked)

        self.searchEdit.textChanged.connect(lambda _: self._filterTimer.start())
        self.regexButton.toggled.connect(self._applyTableFilter)
        self.onlyFailingButton.toggled.connect(self._applyOnlyFailingFilter)
        self.tableView.doubleClicked.connect(self._onTableRowDoubleClicked)

    def setMeasurements(self, measurements: dict[str, pd.DataFrame], isTabActive: bool):
        self._measurements = measurements
        self._lastResult = None
        self._isDirty = True

        allSites = self._collectAllSites(measurements)
        self._updateSiteOptions(allSites)
        self._setControlsEnabled(bool(measurements))

        if not measurements:
            self.clear()
            return

        if isTabActive:
            self.refreshIfNeeded()

    def refreshIfNeeded(self):
        if not self._isDirty or not self._measurements:
            return
        self._isDirty = False
        self._startAnalysis()

    def _onAnalysisParamsChanged(self, *_):
        if not self._measurements:
            return
        self._isDirty = False
        self._startAnalysis()

    def _startAnalysis(self):
        self._requestCounter += 1
        reqId = self._requestCounter

        site = self.siteComboBox.currentText()
        limitsMode = self.limitsComboBox.currentText()

        self.plotView.showMessage('Calculating Yield & Pareto across all tests...')
        self.tableInfoLabel.setText('Calculating...')

        worker = YieldAnalysisWorker(
            analyzer=self._analyzer,
            measurements=self._measurements,
            site=site,
            limitsMode=limitsMode,
            requestId=reqId,
            parent=self,
        )
        worker.finishedAnalysis.connect(self._onAnalysisFinished)
        worker.errorOccurred.connect(self._onAnalysisError)
        self._worker = worker
        worker.start()

    def _onAnalysisFinished(self, requestId: int):
        if requestId != self._requestCounter or self._worker is None:
            return
        result = self._worker.result
        if result is None:
            return

        self._lastResult = result
        self._updateKpiCards(result)
        self._applyOnlyFailingFilter()
        self._redrawParetoChart()

        self.statusMessageRequested.emit(
            f'Yield & Pareto ready: {result.failingTestsCount:,} / {result.totalTests:,} tests with failures '
            f'({result.totalFails:,} total fails)'
        )

    def _onAnalysisError(self, errorMessage:str):
        self.plotView.showMessage(f'Analysis error: {errorMessage}')
        self.tableInfoLabel.setText('Analysis error')

    def _redrawParetoChart(self, *_):
        if self._lastResult is None:
            return

        topNText = self.topNComboBox.currentText()
        topN = None if topNText == 'All' else int(topNText)
        metric = self.chartModeComboBox.currentText()

        fig = self._analyzer.createParetoFigure(
            self._lastResult.summaryDf,
            metric=metric,
            topN=topN,
        )
        self.plotView.setFigure(fig)

    def _updateKpiCards(self, result:BatchSummaryResult):
        if result.boardYieldPct is not None:
            color = self._yieldColor(result.boardYieldPct)
            self._setKpiValue(
                'boardYield',
                f'{result.boardYieldPct:.2f}%',
                color=color,
                tooltip=f'Passed runs: {result.totalRuns - result.failedRuns:,} / {result.totalRuns:,}',
            )
        else:
            self._setKpiValue('boardYield', '—')

        failColor = '#ef5350' if result.failingTestsCount > 0 else '#66bb6a'
        self._setKpiValue(
            'failingTests',
            f'{result.failingTestsCount:,} / {result.totalTests:,}',
            color=failColor,
            tooltip=f'{result.failingTestsCount:,} tests had at least 1 out-of-limits measurement',
        )

        measYieldStr = f' ({result.measurementYieldPct:.2f}%)' if result.measurementYieldPct is not None else ''
        self._setKpiValue(
            'totalFails',
            f'{result.totalFails:,}',
            color='#ef5350' if result.totalFails > 0 else '#66bb6a',
            tooltip=f'Total measurement failures: {result.totalFails:,} / {result.totalMeasurements:,}{measYieldStr}',
        )

        if result.worstYieldPct is not None:
            shortName = self._truncateText(result.worstYieldTest, 20)
            self._setKpiValue(
                'worstYield',
                f'{result.worstYieldPct:.2f}%',
                color=self._yieldColor(result.worstYieldPct),
                tooltip=f'Test: {result.worstYieldTest}\nYield: {result.worstYieldPct:.2f}%',
            )
            self._kpiLabels['worstYield'].setText(f'{result.worstYieldPct:.2f}% ({shortName})')
        else:
            self._setKpiValue('worstYield', '—')

        if result.worstPpkValue is not None:
            shortName = self._truncateText(result.worstPpkTest, 18)
            ppkColor = '#66bb6a' if result.worstPpkValue >= 1.33 else ('#ffa726' if result.worstPpkValue >= 1.0 else '#ef5350')
            self._setKpiValue(
                'worstPpk',
                f'{result.worstPpkValue:.2f} ({shortName})',
                color=ppkColor,
                tooltip=f'Test: {result.worstPpkTest}\nPpk: {result.worstPpkValue:.3f}',
            )
        else:
            self._setKpiValue('worstPpk', '—')

    def _setKpiValue(self, key:str, text:str, color:str='#dfe1e5', tooltip:str=''):
        label = self._kpiLabels[key]
        label.setText(text)
        label.setToolTip(tooltip)
        label.setStyleSheet(
            f'color: {color}; font-size: 13px; font-weight: 600; '
            'font-family: "Consolas", "Cascadia Mono", monospace; border: none;'
        )

    def _applyOnlyFailingFilter(self, *_):
        if self._lastResult is None:
            self.tableModel.clear()
            self._updateTableInfo()
            return

        df = self._lastResult.summaryDf
        if self.onlyFailingButton.isChecked():
            df = df[df['Fails'] > 0].reset_index(drop=True)

        self.tableModel.setDataFrame(df)
        self._configureTableColumns()
        self._applyTableFilter()

    def _configureTableColumns(self):
        header = self.tableView.horizontalHeader()
        colCount = self.tableModel.columnCount()
        if colCount == 0:
            return

        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.tableView.setColumnWidth(0, 240)
        for col in range(1, colCount):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

    def _applyTableFilter(self, *_):
        query = self.searchEdit.text()
        regexEnabled = self.regexButton.isChecked()
        self.tableModel.setFilterQuery(query, column=-1, regexEnabled=regexEnabled)

        if self.tableModel.hasRegexError:
            self.searchEdit.setStyleSheet('border: 1px solid #d9534f;')
        else:
            self.searchEdit.setStyleSheet('')

        self._updateTableInfo()

    def _updateTableInfo(self):
        total = self.tableModel.totalRowCount()
        visible = self.tableModel.rowCount()
        if total == 0:
            self.tableInfoLabel.setText('0 tests')
            self.exportCsvButton.setEnabled(False)
            return

        if visible == total:
            self.tableInfoLabel.setText(f'{total:,} tests  (double-click to open plot)')
        else:
            self.tableInfoLabel.setText(f'Showing {visible:,} / {total:,} tests')
        self.exportCsvButton.setEnabled(visible > 0)

    def _onTableRowDoubleClicked(self, index: QModelIndex):
        if not index.isValid():
            return
        testName = self.tableModel.getTestNameAtRow(index.row())
        if testName:
            self.testActivated.emit(testName)

    def _onCopyPlotClicked(self):
        origText = self.copyPlotButton.text()
        self.copyPlotButton.setText('Copying...')
        self.copyPlotButton.setEnabled(False)

        def onDone(success: bool):
            self.copyPlotButton.setText('Copied!' if success else 'Failed')
            QTimer.singleShot(1200, lambda: (
                self.copyPlotButton.setText(origText),
                self.copyPlotButton.setEnabled(bool(self._measurements)),
            ))

        self.plotView.copyPlotToClipboard(onDone)

    def _onExportCsvClicked(self):
        exportDf = self.tableModel.getFilteredDataFrame()
        if exportDf.empty:
            return

        siteTag = re.sub(r'\s+', '_', self.siteComboBox.currentText()).lower()
        defaultName = f'yield_pareto_{siteTag}.csv'
        filePath, _ = QFileDialog.getSaveFileName(
            self,
            'Export Yield & Pareto summary to CSV',
            defaultName,
            'CSV Files (*.csv);;All Files (*)',
        )
        if not filePath:
            return

        if not filePath.lower().endswith('.csv'):
            filePath += '.csv'

        try:
            exportDf.to_csv(filePath, index=False, encoding='utf-8-sig')
        except OSError as exc:
            QMessageBox.critical(self, 'Export Error', f'Could not save CSV file:\n{exc}')
            return

        self.statusMessageRequested.emit(
            f'Exported {len(exportDf):,} tests summary to {os.path.basename(filePath)}'
        )

    def _updateSiteOptions(self, sites: list[str]):
        current = self.siteComboBox.currentText()
        self.siteComboBox.blockSignals(True)
        self.siteComboBox.clear()
        self.siteComboBox.addItem('All sites')
        if len(sites) > 1:
            self.siteComboBox.addItems(sites)
        idx = self.siteComboBox.findText(current)
        self.siteComboBox.setCurrentIndex(idx if idx >= 0 else 0)
        self.siteComboBox.blockSignals(False)

    @staticmethod
    def _collectAllSites(measurements:dict[str, pd.DataFrame]) -> list[str]:
        sites: set[str] = set()
        for df in measurements.values():
            if df is not None and not df.empty and 'Site' in df.columns:
                sites.update(df['Site'].dropna().astype(str).unique().tolist())
        return sorted(sites)

    def _setControlsEnabled(self, enabled: bool):
        widgetList = [self.chartModeLabel, self.chartModeComboBox, self.siteLabel, self.siteComboBox, self.limitsLabel, self.limitsComboBox, 
            self.topNLabel, self.topNComboBox, self.copyPlotButton, self.searchEdit, self.regexButton, self.onlyFailingButton]
        
        for widget in widgetList:
            widget.setEnabled(enabled)
        self.exportCsvButton.setEnabled(enabled and self.tableModel.rowCount() > 0)

    @staticmethod
    def _yieldColor(pct:float) -> str:
        if pct >= 99.5:
            return '#66bb6a'
        if pct >= 98.0:
            return '#ffa726'
        return '#ef5350'

    @staticmethod
    def _truncateText(text:str, maxLen:int) -> str:
        return text if len(text) <= maxLen else f'{text[:maxLen - 1]}…'

    def clear(self):
        self._requestCounter += 1
        self._measurements = {}
        self._lastResult = None
        self._isDirty = False
        self._filterTimer.stop()

        self.searchEdit.blockSignals(True)
        self.searchEdit.clear()
        self.searchEdit.setStyleSheet('')
        self.searchEdit.blockSignals(False)

        self.regexButton.blockSignals(True)
        self.regexButton.setChecked(False)
        self.regexButton.blockSignals(False)

        self.onlyFailingButton.blockSignals(True)
        self.onlyFailingButton.setChecked(False)
        self.onlyFailingButton.blockSignals(False)

        for key in self._kpiLabels:
            self._setKpiValue(key, '—')

        self._updateSiteOptions([])
        self.tableView.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.tableModel.clear()
        self.tableInfoLabel.setText('No data loaded')
        self._setControlsEnabled(False)
        self.plotView.showMessage('Data cleared.')

    def cleanup(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(1500)
        self.plotView.cleanup()