import os
import re

import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSplitter, QTableView, QVBoxLayout, QWidget, QSizePolicy
)

from src.measurementEngine import MeasurementEngine
from src.pivotAnalyzer import PivotAnalyzer, PivotMatrixResult, naturalSortKey
from src.ui.widgets.plotlyView import PlotlyView
from src.ui.widgets.statsPanel import StatsGuideDialog


class PivotTableModel(QAbstractTableModel):
    COLOR_OK = QColor('#66bb6a')
    COLOR_WARN = QColor('#ffa726')
    COLOR_BAD = QColor('#ef5350')
    COLOR_BLUE = QColor('#4c8dff')
    COLOR_MUTED = QColor('#7c8089')
    SUMMARY_BG = QColor('#2d3038')

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result: PivotMatrixResult | None = None
        self._df = pd.DataFrame()
        self._lowNThreshold = 0

    def setResult(self, result:PivotMatrixResult|None):
        self.beginResetModel()
        self._result = result
        if result is not None and not result.pivotDf.empty:
            self._df = result.pivotDf.reset_index(drop=True)
            maxN = int(np.max(result.countMatrix)) if result.countMatrix.size > 0 else 0
            self._lowNThreshold = 10 if maxN >= 20 else 0
        else:
            self._df = pd.DataFrame()
            self._lowNThreshold = 0
        self.endResetModel()

    def getDataFrame(self) -> pd.DataFrame:
        return self._df

    def clear(self):
        self.setResult(None)

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._df)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._df.columns)

    def headerData(self, section:int, orientation:Qt.Orientation, role:int=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self._df.columns):
            colName = str(self._df.columns[section])
            if role == Qt.ItemDataRole.DisplayRole:
                if self._result and 1 <= section <= len(self._result.shortColLabels):
                    return self._result.shortColLabels[section - 1]
                return colName
            
            if role == Qt.ItemDataRole.ToolTipRole:
                if self._result and 1 <= section <= len(self._result.colLabels):
                    totalColN = int(np.sum(self._result.countMatrix[:, section - 1]))
                    return f'{colName}\nTotal samples across sites: {totalColN:,}'
                return colName
            
        elif orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return str(section + 1)
        
        return None

    def data(self, index:QModelIndex, role:int=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self._result is None or self._df.empty:
            return None

        row = index.row()
        col = index.column()
        nRows = len(self._df)
        nCols = len(self._df.columns)
        isSummaryRow = row == (nRows - 1)
        isSummaryCol = col == (nCols - 1)
        isTestCell = (not isSummaryRow) and (1 <= col <= len(self._result.colLabels))

        rawVal = self._df.iat[row, col]

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 0:
                return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.FontRole and (isSummaryRow or isSummaryCol or col == 0):
            font = QFont()
            font.setBold(True)
            return font

        if role == Qt.ItemDataRole.BackgroundRole and (isSummaryRow or isSummaryCol):
            return self.SUMMARY_BG

        if col == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                text = str(rawVal)
                return text if isSummaryRow else f'Site {text}'
            return None

        cellCnt = int(self._result.countMatrix[row, col - 1]) if isTestCell else 0
        isMasked = isTestCell and (0 < cellCnt < self._result.minSamples)
        isLowN = isTestCell and (not isMasked) and (self._lowNThreshold > 0) and (0 < cellCnt < self._lowNThreshold)

        if role == Qt.ItemDataRole.DisplayRole:
            if isMasked:
                return f'— (n={cellCnt})'
            
            try:
                num = float(rawVal)
            except (TypeError, ValueError):
                return '—'
            
            formatted = PivotAnalyzer.formatMetricValue(num, self._result.metricName, self._result.unitPrefix)
            if isLowN and formatted != '—':
                return f'{formatted} (n={cellCnt})'
            
            return formatted

        if role == Qt.ItemDataRole.ToolTipRole and 1 <= col <= len(self._result.colLabels):
            testName = self._result.colLabels[col - 1]
            if not isSummaryRow:
                fls = int(self._result.failMatrix[row, col - 1])
                extra = ''
                if isMasked:
                    extra = f'\nMasked by Min n ≥ {self._result.minSamples}'
                elif isLowN:
                    extra = '\n⚠ Low sample size — interpret with caution'
                return (
                    f'{testName}\nSite {self._result.rowLabels[row]}\n'
                    f'Samples: {cellCnt:,}  |  Fails: {fls:,}{extra}\n'
                    'Double-click to open test on Plots tab (All sites)'
                )
            totalColN = int(np.sum(self._result.countMatrix[:, col - 1]))
            return f'{testName}\nTotal samples: {totalColN:,}\nDouble-click to open test on Plots tab (All sites)'

        if role == Qt.ItemDataRole.ForegroundRole:
            if isMasked:
                return self.COLOR_MUTED
            
            try:
                num = float(rawVal)
            except (TypeError, ValueError):
                return None
            
            return self._getCellColor(num, self._result.metricName)

        return None

    def getTestNameAtColumn(self, col: int) -> str:
        if self._result is None or col < 1 or col > len(self._result.colLabels):
            return ''
        return self._result.colLabels[col - 1]

    @classmethod
    def _getCellColor(cls, val: float, metric: str) -> QColor | None:
        if not np.isfinite(val):
            return None

        if metric == 'Fails':
            return cls.COLOR_BAD if val > 0 else cls.COLOR_OK
        
        if metric == 'Yield (%)':
            if val >= 99.5:
                return cls.COLOR_OK
            return cls.COLOR_WARN if val >= 98.0 else cls.COLOR_BAD
        
        if metric == 'Ppk':
            if val >= 1.33:
                return cls.COLOR_OK
            return cls.COLOR_WARN if val >= 1.00 else cls.COLOR_BAD
        
        if metric in ('Dev. vs Group (% tol.)', 'Centering Offset (%)'):
            absV = abs(val)
            if absV >= 25.0:
                return cls.COLOR_BAD if val > 0 else cls.COLOR_BLUE
            if absV >= 10.0:
                return cls.COLOR_WARN
            return None
        
        if metric == 'Dev. vs Group (Z-score)':
            absV = abs(val)
            if absV >= 2.0:
                return cls.COLOR_BAD if val > 0 else cls.COLOR_BLUE
            
            if absV >= 1.2:
                return cls.COLOR_WARN
            
            return None
        return None


class PivotTab(QWidget):
    testActivated = Signal(str)
    statusMessageRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._analyzer = PivotAnalyzer()
        self._measurements: dict[str, pd.DataFrame] = {}
        self._allTestNames: list[str] = []
        self._cxcyTestNames: set[str] = set()
        self._checkedTests: set[str] = set()
        self._lastResult: PivotMatrixResult | None = None
        self._guideDialog: StatsGuideDialog | None = None

        self._patternTimer = QTimer(self)
        self._patternTimer.setSingleShot(True)
        self._patternTimer.setInterval(150)
        self._patternTimer.timeout.connect(self._populateTestList)

        self._recomputeTimer = QTimer(self)
        self._recomputeTimer.setSingleShot(True)
        self._recomputeTimer.setInterval(120)
        self._recomputeTimer.timeout.connect(self._recomputeView)

        self._buildUi()
        self._bindEvents()
        self._setControlsEnabled(False)

    def _buildUi(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.mainSplitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- Left pane: Explicit test group picker ----
        pickerGroup = QGroupBox('Test group selection')
        pickerGroup.setMinimumWidth(190)
        pickerLayout = QVBoxLayout(pickerGroup)
        pickerLayout.setContentsMargins(8, 8, 8, 8)
        pickerLayout.setSpacing(6)

        patternRow = QHBoxLayout()
        patternRow.setSpacing(4)
        self.patternEdit = QLineEdit()
        self.patternEdit.setPlaceholderText('Prefix / pattern (e.g. LED, SW, CXCY)...')
        self.patternEdit.setToolTip(
            'Enter any shared prefix, substring, or regex pattern to narrow tests.\n'
            'Then click "Check visible" or pick individual tests below.'
        )
        self.patternEdit.setClearButtonEnabled(True)

        self.regexButton = QPushButton('Regex')
        self.regexButton.setCheckable(True)
        self.regexButton.setCursor(Qt.CursorShape.PointingHandCursor)

        patternRow.addWidget(self.patternEdit, 1)
        patternRow.addWidget(self.regexButton)

        typeSortRow = QHBoxLayout()
        typeSortRow.setSpacing(6)
        self.typeFilterCombo = QComboBox()
        self.typeFilterCombo.addItems(['All types', 'Scalar only', 'CxCy only'])
        self.typeFilterCombo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.typeFilterCombo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.typeFilterCombo.setMinimumContentsLength(8)

        self.naturalSortCheckBox = QCheckBox('Natural sort')
        self.naturalSortCheckBox.setChecked(True)
        self.naturalSortCheckBox.setToolTip('Order LED1, LED2, ..., LED10 instead of alphabetical LED1, LED10, LED2')

        typeSortRow.addWidget(self.typeFilterCombo, 1)
        typeSortRow.addWidget(self.naturalSortCheckBox)

        btnRow = QHBoxLayout()
        btnRow.setSpacing(6)
        self.checkVisibleButton = QPushButton('Check visible')
        self.checkVisibleButton.setProperty('accent', True)
        self.checkVisibleButton.setCursor(Qt.CursorShape.PointingHandCursor)

        self.uncheckAllButton = QPushButton('Uncheck all')
        self.uncheckAllButton.setCursor(Qt.CursorShape.PointingHandCursor)

        btnRow.addWidget(self.checkVisibleButton, 1)
        btnRow.addWidget(self.uncheckAllButton, 1)

        self.selectionInfoLabel = QLabel('Selected: 0 / 0')
        self.selectionInfoLabel.setStyleSheet('color: #9da0a8; font-size: 11px;')
        self.selectionInfoLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        self.testListWidget = QListWidget()
        self.testListWidget.setAlternatingRowColors(True)

        pickerLayout.addLayout(patternRow)
        pickerLayout.addLayout(typeSortRow)
        pickerLayout.addLayout(btnRow)
        pickerLayout.addWidget(self.selectionInfoLabel)
        pickerLayout.addWidget(self.testListWidget, 1)

        # ---- Right pane: Compact 2-row controls + Heatmap/Overlay + Pivot Table ----
        rightPane = QWidget()
        rightPane.setMinimumWidth(300)
        rightLayout = QVBoxLayout(rightPane)
        rightLayout.setContentsMargins(4, 0, 0, 0)
        rightLayout.setSpacing(6)

        controlsRow1 = QHBoxLayout()
        controlsRow1.setSpacing(6)

        self.viewModeLabel = QLabel('View:')
        self.viewModeCombo = QComboBox()
        self.viewModeCombo.addItems([
            'Heatmap: Site × Test',
            'Overlay Comparison',
        ])
        self.viewModeCombo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.viewModeCombo.setMinimumContentsLength(14)
        self.viewModeCombo.setStyleSheet("""
            QComboBox {
                font-weight: 600;
                border: 1px solid #3574f0;
                padding: 4px 8px;
            }
        """)

        self.metricLabel = QLabel('Metric:')
        self.metricCombo = QComboBox()
        self.metricCombo.addItems(PivotAnalyzer.SCALAR_METRICS)
        self.metricCombo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.metricCombo.setMinimumContentsLength(14)

        self.colorByLabel = QLabel('Color:')
        self.colorByCombo = QComboBox()
        self.colorByCombo.addItems(['Test (Position)', 'Site'])
        self.colorByCombo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.colorByCombo.setMinimumContentsLength(10)

        controlsRow1.addWidget(self.viewModeLabel)
        controlsRow1.addWidget(self.viewModeCombo, 1)
        controlsRow1.addWidget(self.metricLabel)
        controlsRow1.addWidget(self.metricCombo, 1)
        controlsRow1.addWidget(self.colorByLabel)
        controlsRow1.addWidget(self.colorByCombo)
        controlsRow1.addStretch(1)

        controlsRow2 = QHBoxLayout()
        controlsRow2.setSpacing(6)

        self.limitsLabel = QLabel('Limits:')
        self.limitsCombo = QComboBox()
        self.limitsCombo.addItems(['All', 'Newest', 'Oldest'])

        self.minSamplesLabel = QLabel('Min n:')
        self.minSamplesCombo = QComboBox()
        self.minSamplesCombo.addItems(['1', '5', '10', '30', '50'])
        self.minSamplesCombo.setCurrentText('1')
        self.minSamplesCombo.setToolTip(
            'Minimum sample count per Site × Test cell required for heatmap & averages.\n'
            'Increase (e.g. 5 or 10) to mask low-count retest/branch steps.'
        )

        for combo in (self.viewModeCombo, self.metricCombo, self.colorByCombo, self.limitsCombo, self.minSamplesCombo):
            combo.setCursor(Qt.CursorShape.PointingHandCursor)

        self.guideButton = QPushButton('? Guide')
        self.guideButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.guideButton.setToolTip('Open Statistics & Pivot Heatmap Diagnostics Guide')

        self.copyPlotButton = QPushButton('Copy plot')
        self.copyPlotButton.setCursor(Qt.CursorShape.PointingHandCursor)

        self.exportCsvButton = QPushButton('Export CSV')
        self.exportCsvButton.setCursor(Qt.CursorShape.PointingHandCursor)

        controlsRow2.addWidget(self.limitsLabel)
        controlsRow2.addWidget(self.limitsCombo)
        controlsRow2.addWidget(self.minSamplesLabel)
        controlsRow2.addWidget(self.minSamplesCombo)
        controlsRow2.addStretch(1)
        controlsRow2.addWidget(self.guideButton)
        controlsRow2.addWidget(self.copyPlotButton)
        controlsRow2.addWidget(self.exportCsvButton)

        self.rightSplitter = QSplitter(Qt.Orientation.Vertical)

        self.plotView = PlotlyView(enablePointCard=False)
        self.plotView.showMessage(
            'Enter a pattern on the left and check tests to compare across sites.'
        )

        tableContainer = QWidget()
        tableLayout = QVBoxLayout(tableContainer)
        tableLayout.setContentsMargins(0, 4, 0, 0)
        tableLayout.setSpacing(4)

        self.tableInfoLabel = QLabel('Double-click any test cell to open it on Plots tab (All sites)')
        self.tableInfoLabel.setStyleSheet('color: #9da0a8; font-size: 11px;')
        self.tableInfoLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        self.tableModel = PivotTableModel()
        self.tableView = QTableView()
        self.tableView.setModel(self.tableModel)
        self.tableView.setAlternatingRowColors(True)
        self.tableView.verticalHeader().setDefaultSectionSize(24)

        tableLayout.addWidget(self.tableInfoLabel)
        tableLayout.addWidget(self.tableView, 1)

        self.rightSplitter.addWidget(self.plotView)
        self.rightSplitter.addWidget(tableContainer)
        self.rightSplitter.setStretchFactor(0, 2)
        self.rightSplitter.setStretchFactor(1, 1)
        self.rightSplitter.setSizes([380, 220])

        rightLayout.addLayout(controlsRow1)
        rightLayout.addLayout(controlsRow2)
        rightLayout.addWidget(self.rightSplitter, 1)

        self.mainSplitter.addWidget(pickerGroup)
        self.mainSplitter.addWidget(rightPane)
        self.mainSplitter.setStretchFactor(0, 0)
        self.mainSplitter.setStretchFactor(1, 1)
        self.mainSplitter.setSizes([230, 620])

        layout.addWidget(self.mainSplitter)

    def _bindEvents(self):
        self.patternEdit.textChanged.connect(lambda _: self._patternTimer.start())
        self.regexButton.toggled.connect(self._populateTestList)
        self.typeFilterCombo.currentTextChanged.connect(self._populateTestList)
        self.naturalSortCheckBox.toggled.connect(self._onNaturalSortToggled)
        self.checkVisibleButton.clicked.connect(self._onCheckVisible)
        self.uncheckAllButton.clicked.connect(self._onUncheckAll)
        self.testListWidget.itemChanged.connect(self._onTestItemChanged)

        self.viewModeCombo.currentTextChanged.connect(self._onViewOptionsChanged)
        self.metricCombo.currentTextChanged.connect(self._recomputeView)
        self.colorByCombo.currentTextChanged.connect(self._recomputeView)
        self.limitsCombo.currentTextChanged.connect(self._recomputeView)

        self.guideButton.clicked.connect(self._openGuideDialog)
        self.copyPlotButton.clicked.connect(self._onCopyPlotClicked)
        self.exportCsvButton.clicked.connect(self._onExportCsvClicked)
        self.tableView.doubleClicked.connect(self._onTableDoubleClicked)

        self.minSamplesCombo.currentTextChanged.connect(self._recomputeView)

    def setMeasurements(self, measurements:dict[str, pd.DataFrame], resetSelection:bool=False):
        self._measurements = measurements
        self._allTestNames = list(measurements.keys())
        self._cxcyTestNames = {
            t for t, df in measurements.items()
            if df is not None and MeasurementEngine.isCxCyDataFrame(df)
        }

        if resetSelection:
            self._checkedTests.clear()
        else:
            self._checkedTests.intersection_update(self._allTestNames)

        self._setControlsEnabled(bool(measurements))
        if not measurements:
            self.clear()
            return

        self._populateTestList()
        self._updateOptionStates()
        if self._checkedTests:
            self._recomputeView()
        else:
            self.tableModel.clear()
            self.plotView.showMessage(
                'Enter a prefix/pattern on the left and check tests to build the Pivot matrix.'
            )

    def _getOrderedTestNames(self, names:list[str]) -> list[str]:
        if self.naturalSortCheckBox.isChecked():
            return sorted(names, key=naturalSortKey)
        return list(names)

    def _populateTestList(self, *_):
        patternText = self.patternEdit.text().strip()
        useRegex = self.regexButton.isChecked()
        typeMode = self.typeFilterCombo.currentText()

        compiled = None
        if patternText and useRegex:
            try:
                compiled = re.compile(patternText, re.IGNORECASE)
                self.patternEdit.setStyleSheet('')
            except re.error:
                self.patternEdit.setStyleSheet('border: 1px solid #d9534f;')
                return
        else:
            self.patternEdit.setStyleSheet('')

        patternLower = patternText.lower()
        filtered: list[str] = []
        for name in self._allTestNames:
            isCx = name in self._cxcyTestNames
            if typeMode == 'Scalar only' and isCx:
                continue
            if typeMode == 'CxCy only' and not isCx:
                continue

            if patternText:
                if useRegex and compiled is not None:
                    if not compiled.search(name):
                        continue
                elif patternLower not in name.lower():
                    continue
            filtered.append(name)

        ordered = self._getOrderedTestNames(filtered)

        self.testListWidget.blockSignals(True)
        self.testListWidget.clear()
        for name in ordered:
            badge = '[CxCy] ' if name in self._cxcyTestNames else ''
            item = QListWidgetItem(f'{badge}{name}')
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setToolTip(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if name in self._checkedTests else Qt.CheckState.Unchecked
            )
            self.testListWidget.addItem(item)
        self.testListWidget.blockSignals(False)

        self._updateSelectionLabel()

    def _onNaturalSortToggled(self, *_):
        self._populateTestList()
        if self._checkedTests:
            self._recomputeView()

    def _onTestItemChanged(self, item:QListWidgetItem):
        testName = item.data(Qt.ItemDataRole.UserRole)
        if not testName:
            return
        if item.checkState() == Qt.CheckState.Checked:
            self._checkedTests.add(testName)
        else:
            self._checkedTests.discard(testName)

        self._updateSelectionLabel()
        self._syncMetricComboForSelection()
        self._updateOptionStates()
        self._recomputeTimer.start()

    def _onCheckVisible(self):
        self.testListWidget.blockSignals(True)
        for i in range(self.testListWidget.count()):
            item = self.testListWidget.item(i)
            item.setCheckState(Qt.CheckState.Checked)
            name = item.data(Qt.ItemDataRole.UserRole)
            if name:
                self._checkedTests.add(name)
        self.testListWidget.blockSignals(False)

        self._updateSelectionLabel()
        self._syncMetricComboForSelection()
        self._updateOptionStates()
        self._recomputeView()

    def _onUncheckAll(self):
        self._checkedTests.clear()
        self.testListWidget.blockSignals(True)
        for i in range(self.testListWidget.count()):
            self.testListWidget.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.testListWidget.blockSignals(False)

        self._updateSelectionLabel()
        self._updateOptionStates()
        self._recomputeView()

    def _getOrderedSelectedTests(self) -> list[str]:
        selectedInBaseOrder = [t for t in self._allTestNames if t in self._checkedTests]
        return self._getOrderedTestNames(selectedInBaseOrder)

    def _selectionIsAllCxCy(self) -> bool:
        return bool(self._checkedTests) and all(t in self._cxcyTestNames for t in self._checkedTests)

    def _syncMetricComboForSelection(self):
        targetList = PivotAnalyzer.CXCY_METRICS if self._selectionIsAllCxCy() else PivotAnalyzer.SCALAR_METRICS
        currentItems = [self.metricCombo.itemText(i) for i in range(self.metricCombo.count())]
        if currentItems == targetList:
            return

        currentMetric = self.metricCombo.currentText()
        self.metricCombo.blockSignals(True)
        self.metricCombo.clear()
        self.metricCombo.addItems(targetList)
        idx = self.metricCombo.findText(currentMetric)
        self.metricCombo.setCurrentIndex(idx if idx >= 0 else 0)
        self.metricCombo.blockSignals(False)

    def _onViewOptionsChanged(self, *_):
        self._updateOptionStates()
        self._recomputeView()

    def _updateOptionStates(self):
        hasData = bool(self._measurements)
        isOverlay = 'Overlay' in self.viewModeCombo.currentText()
        isCxCy = self._selectionIsAllCxCy()

        self.metricLabel.setEnabled(hasData and not isOverlay)
        self.metricCombo.setEnabled(hasData and not isOverlay)

        showColorBy = isOverlay and isCxCy
        self.colorByLabel.setVisible(showColorBy)
        self.colorByCombo.setVisible(showColorBy)
        self.colorByLabel.setEnabled(hasData and showColorBy)
        self.colorByCombo.setEnabled(hasData and showColorBy)

        self.minSamplesLabel.setEnabled(hasData and not isOverlay)
        self.minSamplesCombo.setEnabled(hasData and not isOverlay)

    def _updateSelectionLabel(self):
        visibleCount = self.testListWidget.count()
        self.selectionInfoLabel.setText(
            f'Selected: {len(self._checkedTests):,}  |  Visible: {visibleCount:,} / {len(self._allTestNames):,}'
        )

    def _recomputeView(self, *_):
        self._recomputeTimer.stop()
        if not self._measurements:
            return

        selectedTests = self._getOrderedSelectedTests()
        if not selectedTests:
            self._lastResult = None
            self.tableModel.clear()
            self.exportCsvButton.setEnabled(False)
            self.plotView.showMessage(
                'Enter a prefix/pattern on the left and check tests to build the Pivot matrix.'
            )
            self.tableInfoLabel.setText('No tests selected')
            return

        self._syncMetricComboForSelection()
        viewMode = self.viewModeCombo.currentText()
        metric = self.metricCombo.currentText()
        limitsMode = self.limitsCombo.currentText()

        minSamples = int(self.minSamplesCombo.currentText())

        result = self._analyzer.analyzeMatrix(measurements=self._measurements, selectedTests=selectedTests,
            metric=metric, limitsMode=limitsMode, minSamples=minSamples)
        self._lastResult = result

        if result.warningMessage:
            self.tableModel.clear()
            self.exportCsvButton.setEnabled(False)
            self.plotView.setFigure(self._analyzer.createHeatmapFigure(result))
            self.tableInfoLabel.setText(result.warningMessage.replace('\n', ' '))
            return

        self.tableModel.setResult(result)
        self._configureTableColumns()
        self.exportCsvButton.setEnabled(not result.pivotDf.empty)

        if 'Overlay' in viewMode:
            fig = self._analyzer.createOverlayFigure(measurements=self._measurements, selectedTests=selectedTests,
                limitsMode=limitsMode, colorBy=self.colorByCombo.currentText())
        else:
            fig = self._analyzer.createHeatmapFigure(result)

        self.plotView.setFigure(fig)
        self.tableInfoLabel.setText(
            f'Matrix: {len(result.rowLabels)} site(s) × {len(result.colLabels)} test(s)  '
            '|  Double-click any test cell to inspect on Plots tab (All sites)'
        )
        self.statusMessageRequested.emit(
            f'Pivot ready: {len(result.rowLabels)} × {len(result.colLabels)} ({metric})'
        )

    def _configureTableColumns(self):
        header = self.tableView.horizontalHeader()
        colCount = self.tableModel.columnCount()
        if colCount == 0:
            return
        for col in range(colCount):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

    def _onTableDoubleClicked(self, index: QModelIndex):
        if not index.isValid():
            return
        
        testName = self.tableModel.getTestNameAtColumn(index.column())
        if testName:
            self.testActivated.emit(testName)

    def _openGuideDialog(self):
        if self._guideDialog is None:
            self._guideDialog = StatsGuideDialog(self)

        self._guideDialog.show()
        self._guideDialog.raise_()
        self._guideDialog.activateWindow()

    def _onCopyPlotClicked(self):
        origText = self.copyPlotButton.text()
        self.copyPlotButton.setText('Copying...')
        self.copyPlotButton.setEnabled(False)

        def onDone(success:bool):
            self.copyPlotButton.setText('Copied!' if success else 'Failed')
            QTimer.singleShot(1200, lambda: (
                self.copyPlotButton.setText(origText),
                self.copyPlotButton.setEnabled(bool(self._measurements)),
            ))

        self.plotView.copyPlotToClipboard(onDone)

    def _onExportCsvClicked(self):
        exportDf = self.tableModel.getDataFrame()
        if exportDf.empty:
            return

        metricSlug = re.sub(r'[^a-zA-Z0-9]+', '_', self.metricCombo.currentText()).strip('_').lower()
        defaultName = f'pivot_{metricSlug}.csv'
        filePath, _ = QFileDialog.getSaveFileName(
            self,
            'Export Pivot table to CSV',
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
            f'Exported Pivot matrix ({len(exportDf)} rows) to {os.path.basename(filePath)}'
        )

    def _setControlsEnabled(self, enabled:bool):
        widgetList = [
            self.patternEdit, self.regexButton, self.typeFilterCombo, self.naturalSortCheckBox,
            self.checkVisibleButton, self.uncheckAllButton, self.viewModeLabel, self.viewModeCombo,
            self.limitsLabel, self.limitsCombo, self.copyPlotButton
        ]
        for widget in widgetList:
            widget.setEnabled(enabled)
            
        self.guideButton.setEnabled(True)
        self.exportCsvButton.setEnabled(enabled and self.tableModel.rowCount() > 0)
        self._updateOptionStates()

    def clear(self):
        self._patternTimer.stop()
        self._recomputeTimer.stop()
        self._measurements = {}
        self._allTestNames = []
        self._cxcyTestNames.clear()
        self._checkedTests.clear()
        self._lastResult = None

        self.patternEdit.blockSignals(True)
        self.patternEdit.clear()
        self.patternEdit.setStyleSheet('')
        self.patternEdit.blockSignals(False)

        self.regexButton.blockSignals(True)
        self.regexButton.setChecked(False)
        self.regexButton.blockSignals(False)

        self.typeFilterCombo.blockSignals(True)
        self.typeFilterCombo.setCurrentIndex(0)
        self.typeFilterCombo.blockSignals(False)

        self.testListWidget.blockSignals(True)
        self.testListWidget.clear()
        self.testListWidget.blockSignals(False)

        self.tableModel.clear()
        self.selectionInfoLabel.setText('Selected: 0 / 0')
        self.tableInfoLabel.setText('No data loaded')
        self._setControlsEnabled(False)
        self.plotView.showMessage('Data cleared.')

    def cleanup(self):
        self.plotView.cleanup()