import os
import re

import pandas as pd
import plotly.graph_objects as go
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableView, QTabWidget, QVBoxLayout, QWidget,
)

from src.ui.widgets.dataTableModel import PandasTableModel
from src.ui.widgets.plotlyView import PlotlyView
from src.ui.widgets.yieldParetoTab import YieldParetoTab
from src.ui.widgets.pivotTab import PivotTab


class WorkspacePanel(QWidget):
    plotOptionsChanged = Signal()
    openPlotWindowRequested = Signal()
    statusMessageRequested = Signal(str)
    jumpToTestRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._controlsEnabled = False
        self._isCxCy = False
        self._currentRawTestName = ''
        self._pendingRawData: tuple[str, pd.DataFrame] | None = None
        self._rawDataDirty = False

        self._rawFilterTimer = QTimer(self)
        self._rawFilterTimer.setSingleShot(True)
        self._rawFilterTimer.setInterval(150)
        self._rawFilterTimer.timeout.connect(self._applyRawDataFilter)

        self._snFilterTimer = QTimer(self)
        self._snFilterTimer.setSingleShot(True)
        self._snFilterTimer.setInterval(200)
        self._snFilterTimer.timeout.connect(self._emitOptionsChanged)

        self._buildUi()
        self._bindEvents()
        self.setPlotControlsEnabled(False)

    def _buildUi(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.tabs = QTabWidget()
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self._plotsTabIndex = self.tabs.addTab(self._buildPlotsTab(), 'Plots')
        self._yieldTabIndex = self.tabs.addTab(self._buildYieldParetoTab(), 'Yield && Pareto')
        self._pivotTabIndex = self.tabs.addTab(self._buildPivotTab(), 'Pivot && Multi-Test')
        self._rawTabIndex = self.tabs.addTab(self._buildRawDataTab(), 'Raw data')

        layout.addWidget(self.tabs)

    def _buildPlotsTab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        controlsRow = QHBoxLayout()
        controlsRow.setSpacing(8)

        self.plotTypeLabel = QLabel('Plot:')
        self.plotTypeComboBox = QComboBox()
        self.plotTypeComboBox.addItems(['Sequence', 'Capability (Histogram)', 'Boxplot'])
        self.plotTypeComboBox.setStyleSheet("""
            QComboBox {
                font-weight: 600;
                border: 1px solid #3574f0;
                padding: 4px 10px;
                min-width: 155px;
            }
        """)

        self.siteLabel = QLabel('Site:')
        self.siteComboBox = QComboBox()
        self.siteComboBox.addItem('All sites')
        self.siteComboBox.setMinimumWidth(100)

        self.orderByLabel = QLabel('Sorting:')
        self.orderByComboBox = QComboBox()
        self.orderByComboBox.addItems(['Date', 'Sites'])

        self.limitsLabel = QLabel('Limits:')
        self.limitsComboBox = QComboBox()
        self.limitsComboBox.addItems(['All', 'Newest', 'Oldest'])

        for combo in (
            self.plotTypeComboBox,
            self.siteComboBox,
            self.orderByComboBox,
            self.limitsComboBox,
        ):
            combo.setCursor(Qt.CursorShape.PointingHandCursor)

        self.valuesInLimitsButton = QPushButton('Only in limits')
        self.valuesInLimitsButton.setCheckable(True)
        self.valuesInLimitsButton.setCursor(Qt.CursorShape.PointingHandCursor)

        self.logScaleButton = QPushButton('Log scale')
        self.logScaleButton.setCheckable(True)
        self.logScaleButton.setCursor(Qt.CursorShape.PointingHandCursor)

        self.copyPlotButton = QPushButton('Copy plot')
        self.copyPlotButton.setCursor(Qt.CursorShape.PointingHandCursor)

        controlsRow.addWidget(self.plotTypeLabel)
        controlsRow.addWidget(self.plotTypeComboBox)
        controlsRow.addWidget(self.siteLabel)
        controlsRow.addWidget(self.siteComboBox)
        controlsRow.addWidget(self.orderByLabel)
        controlsRow.addWidget(self.orderByComboBox)
        controlsRow.addWidget(self.limitsLabel)
        controlsRow.addWidget(self.limitsComboBox)
        controlsRow.addWidget(self.valuesInLimitsButton)
        controlsRow.addWidget(self.logScaleButton)
        controlsRow.addStretch(1)
        controlsRow.addWidget(self.copyPlotButton)

        snRow = QHBoxLayout()
        snRow.setSpacing(8)

        self.snFilterLabel = QLabel('Serial Number:')
        self.snFilterEdit = QLineEdit()
        self.snFilterEdit.setPlaceholderText('Track SN / golden unit (partial or comma-separated)...')
        self.snFilterEdit.setToolTip(
            'Highlight all measurements for the given Serial Number(s).\n'
            'Supports partial match and multiple SNs separated by commas.'
        )
        self.snFilterEdit.setClearButtonEnabled(True)

        self.onlySnButton = QPushButton('Only SN')
        self.onlySnButton.setCheckable(True)
        self.onlySnButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.onlySnButton.setToolTip('Show ONLY measurements matching the entered SN (isolates golden unit)')

        self.snMatchLabel = QLabel('')
        self.snMatchLabel.setStyleSheet('color: #9da0a8;')

        snRow.addWidget(self.snFilterLabel)
        snRow.addWidget(self.snFilterEdit, 1)
        snRow.addWidget(self.onlySnButton)
        snRow.addWidget(self.snMatchLabel)

        self.plotView = PlotlyView()

        layout.addLayout(controlsRow)
        layout.addLayout(snRow)
        layout.addWidget(self.plotView, 1)
        return tab

    def _buildYieldParetoTab(self) -> QWidget:
        self.yieldParetoTab = YieldParetoTab()
        return self.yieldParetoTab

    def _buildPivotTab(self) -> QWidget:
        self.pivotTab = PivotTab()
        return self.pivotTab

    def _buildRawDataTab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        controlsRow = QHBoxLayout()
        controlsRow.setSpacing(8)

        self.rawSearchEdit = QLineEdit()
        self.rawSearchEdit.setPlaceholderText(
            'Filter: text/regex, >5.1, 4.9..5.1, 2025/01/01..2025/01/03, site>=2'
        )
        self.rawSearchEdit.setToolTip(
            'Supported filters (combine multiple terms with spaces):\n'
            '• Text / Regex (toggle "Regex"):  ^17025.*70$\n'
            '• Numeric (SI supported):  >5.05, <=33n, 4.9..5.1, val>1.2k, site>=2\n'
            '• Date / Time:  >2025/01/01, 2025/01/01..2025/01/03, >="2025/01/01 10:00"'
        )
        self.rawSearchEdit.setClearButtonEnabled(True)
        self.rawSearchEdit.setEnabled(False)

        self.rawRegexButton = QPushButton('Regex')
        self.rawRegexButton.setCheckable(True)
        self.rawRegexButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rawRegexButton.setToolTip('Interpret text tokens as regular expressions (case-insensitive)')
        self.rawRegexButton.setEnabled(False)

        self.rawColumnLabel = QLabel('Column:')
        self.rawColumnComboBox = QComboBox()
        self.rawColumnComboBox.addItem('All columns')
        self.rawColumnComboBox.setMinimumWidth(130)
        self.rawColumnComboBox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rawColumnComboBox.setEnabled(False)

        self.exportCsvButton = QPushButton('Export CSV')
        self.exportCsvButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exportCsvButton.setToolTip('Export currently filtered rows to CSV')
        self.exportCsvButton.setEnabled(False)

        controlsRow.addWidget(self.rawSearchEdit, 1)
        controlsRow.addWidget(self.rawRegexButton)
        controlsRow.addWidget(self.rawColumnLabel)
        controlsRow.addWidget(self.rawColumnComboBox)
        controlsRow.addWidget(self.exportCsvButton)

        self.tableInfoLabel = QLabel('No data loaded')
        self.tableInfoLabel.setStyleSheet('color: #9da0a8;')

        self.tableModel = PandasTableModel()
        self.tableView = QTableView()
        self.tableView.setModel(self.tableModel)
        self.tableView.setAlternatingRowColors(True)
        self.tableView.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.tableView.setSortingEnabled(True)
        self.tableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tableView.verticalHeader().setDefaultSectionSize(24)

        layout.addLayout(controlsRow)
        layout.addWidget(self.tableInfoLabel)
        layout.addWidget(self.tableView, 1)
        return tab

    def _bindEvents(self):
        self.tabs.currentChanged.connect(self._onTabChanged)

        self.plotTypeComboBox.currentTextChanged.connect(self._onPlotTypeChanged)
        self.siteComboBox.currentTextChanged.connect(self._emitOptionsChanged)
        self.orderByComboBox.currentTextChanged.connect(self._emitOptionsChanged)
        self.limitsComboBox.currentTextChanged.connect(self._emitOptionsChanged)
        self.valuesInLimitsButton.toggled.connect(self._emitOptionsChanged)
        self.logScaleButton.toggled.connect(self._emitOptionsChanged)
        self.copyPlotButton.clicked.connect(self._onCopyPlotClicked)

        self.snFilterEdit.textChanged.connect(lambda _: self._snFilterTimer.start())
        self.snFilterEdit.returnPressed.connect(self._onSnReturnPressed)
        self.onlySnButton.toggled.connect(self._emitOptionsChanged)

        self.rawSearchEdit.textChanged.connect(lambda _: self._rawFilterTimer.start())
        self.rawRegexButton.toggled.connect(self._applyRawDataFilter)
        self.rawColumnComboBox.currentIndexChanged.connect(self._applyRawDataFilter)
        self.exportCsvButton.clicked.connect(self._onExportCsvClicked)

        self.yieldParetoTab.testActivated.connect(self.jumpToTestRequested.emit)
        self.yieldParetoTab.statusMessageRequested.connect(self.statusMessageRequested.emit)

        self.pivotTab.testActivated.connect(self.jumpToTestRequested.emit)
        self.pivotTab.statusMessageRequested.connect(self.statusMessageRequested.emit)

    def _onTabChanged(self, index: int):
        if index == self._rawTabIndex and self._rawDataDirty:
            self._flushPendingRawData()
        elif index == self._yieldTabIndex:
            self.yieldParetoTab.refreshIfNeeded()

    def _onPlotTypeChanged(self, *_):
        self._updateControlStates()
        self._emitOptionsChanged()

    def _onSnReturnPressed(self):
        self._snFilterTimer.stop()
        self._emitOptionsChanged()

    def _emitOptionsChanged(self, *_):
        self.plotOptionsChanged.emit()

    def _onCopyPlotClicked(self):
        origText = self.copyPlotButton.text()
        self.copyPlotButton.setText('Copying...')
        self.copyPlotButton.setEnabled(False)

        def onDone(success: bool):
            self.copyPlotButton.setText('Copied!' if success else 'Failed')
            QTimer.singleShot(1200, lambda: (
                self.copyPlotButton.setText(origText),
                self.copyPlotButton.setEnabled(True)
            ))

        self.plotView.copyPlotToClipboard(onDone)

    def _applyRawDataFilter(self, *_):
        query = self.rawSearchEdit.text()
        columnIdx = self.rawColumnComboBox.currentIndex() - 1
        regexEnabled = self.rawRegexButton.isChecked()

        self.tableModel.setFilterQuery(query, columnIdx, regexEnabled=regexEnabled)

        if self.tableModel.hasRegexError:
            self.rawSearchEdit.setStyleSheet('border: 1px solid #d9534f;')
        else:
            self.rawSearchEdit.setStyleSheet('')

        self._updateRawTableInfo()

    def _updateRawTableInfo(self):
        totalRows = self.tableModel.totalRowCount()
        visibleRows = self.tableModel.rowCount()

        if not self._currentRawTestName or totalRows == 0:
            self.tableInfoLabel.setText('No data loaded')
            self.exportCsvButton.setEnabled(False)
            return

        if visibleRows == totalRows:
            self.tableInfoLabel.setText(f'Test: {self._currentRawTestName}  |  Rows: {totalRows:,}')
        else:
            self.tableInfoLabel.setText(
                f'Test: {self._currentRawTestName}  |  Showing: {visibleRows:,} / {totalRows:,} rows'
            )

        self.exportCsvButton.setEnabled(visibleRows > 0)

    def _onExportCsvClicked(self):
        if self._rawDataDirty:
            self._flushPendingRawData()

        exportDf = self.tableModel.getFilteredDataFrame()
        if exportDf.empty:
            return

        safeName = re.sub(r'[\\/:*?"<>|\s]+', '_', self._currentRawTestName).strip('_') or 'raw_data'
        defaultFileName = f'{safeName}.csv'

        filePath, _ = QFileDialog.getSaveFileName(
            self,
            'Export filtered rows to CSV',
            defaultFileName,
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

        origText = self.exportCsvButton.text()
        self.exportCsvButton.setText('Exported!')
        self.exportCsvButton.setEnabled(False)
        QTimer.singleShot(1200, lambda: (
            self.exportCsvButton.setText(origText),
            self.exportCsvButton.setEnabled(self.tableModel.rowCount() > 0),
        ))
        self.statusMessageRequested.emit(
            f'Exported {len(exportDf):,} rows to {os.path.basename(filePath)}'
        )

    def _flushPendingRawData(self):
        self._rawDataDirty = False
        if self._pendingRawData is None:
            return

        testName, df = self._pendingRawData
        self._currentRawTestName = testName
        self.tableModel.setDataFrame(df)

        previousColumn = self.rawColumnComboBox.currentText()
        self.rawColumnComboBox.blockSignals(True)
        self.rawColumnComboBox.clear()
        self.rawColumnComboBox.addItem('All columns')
        self.rawColumnComboBox.addItems(self.tableModel.getColumnNames())
        idx = self.rawColumnComboBox.findText(previousColumn)
        self.rawColumnComboBox.setCurrentIndex(idx if idx >= 0 else 0)
        self.rawColumnComboBox.blockSignals(False)

        hasRows = not df.empty
        self.rawSearchEdit.setEnabled(hasRows)
        self.rawRegexButton.setEnabled(hasRows)
        self.rawColumnComboBox.setEnabled(hasRows)

        self._applyRawDataFilter()

    def _updateControlStates(self):
        if not self._controlsEnabled:
            self.plotTypeLabel.setEnabled(False)
            self.plotTypeComboBox.setEnabled(False)
            self.siteLabel.setEnabled(False)
            self.siteComboBox.setEnabled(False)
            self.orderByLabel.setEnabled(False)
            self.orderByComboBox.setEnabled(False)
            self.limitsLabel.setEnabled(False)
            self.limitsComboBox.setEnabled(False)
            self.valuesInLimitsButton.setEnabled(False)
            self.logScaleButton.setEnabled(False)
            self.copyPlotButton.setEnabled(False)
            self.snFilterLabel.setEnabled(False)
            self.snFilterEdit.setEnabled(False)
            self.onlySnButton.setEnabled(False)
            return

        self.siteLabel.setEnabled(True)
        self.siteComboBox.setEnabled(True)
        self.valuesInLimitsButton.setEnabled(True)
        self.copyPlotButton.setEnabled(True)
        self.snFilterLabel.setEnabled(True)
        self.snFilterEdit.setEnabled(True)
        self.onlySnButton.setEnabled(True)

        if self._isCxCy:
            self.plotTypeLabel.setEnabled(False)
            self.plotTypeComboBox.setEnabled(False)
            self.orderByLabel.setEnabled(False)
            self.orderByComboBox.setEnabled(False)
            self.limitsLabel.setEnabled(True)
            self.limitsComboBox.setEnabled(True)
            self.logScaleButton.setEnabled(False)
            return

        self.plotTypeLabel.setEnabled(True)
        self.plotTypeComboBox.setEnabled(True)

        currType = self.plotTypeComboBox.currentText().strip().lower()

        if currType == 'sequence':
            self.orderByLabel.setEnabled(True)
            self.orderByComboBox.setEnabled(True)
            self.limitsLabel.setEnabled(True)
            self.limitsComboBox.setEnabled(True)
            self.logScaleButton.setEnabled(True)
        elif currType in ('capability (histogram)', 'capability', 'histogram'):
            self.orderByLabel.setEnabled(False)
            self.orderByComboBox.setEnabled(False)
            self.limitsLabel.setEnabled(False)
            self.limitsComboBox.setEnabled(False)
            self.logScaleButton.setEnabled(False)
        elif currType == 'boxplot':
            self.orderByLabel.setEnabled(False)
            self.orderByComboBox.setEnabled(False)
            self.limitsLabel.setEnabled(False)
            self.limitsComboBox.setEnabled(False)
            self.logScaleButton.setEnabled(True)

    def setSnMatchInfo(self, matchedCount: int, matchedSites: int, hasQuery: bool):
        if not hasQuery:
            self.snMatchLabel.setText('')
            self.snMatchLabel.setStyleSheet('color: #9da0a8;')
            return

        if matchedCount == 0:
            self.snMatchLabel.setText('No matching SN')
            self.snMatchLabel.setStyleSheet('color: #ef5350; font-weight: 600;')
        else:
            siteWord = 'site' if matchedSites == 1 else 'sites'
            self.snMatchLabel.setText(f'Matched: {matchedCount:,} pts ({matchedSites} {siteWord})')
            self.snMatchLabel.setStyleSheet('color: #ffd600; font-weight: 600;')

    def setFigure(self, fig: go.Figure):
        self.plotView.setFigure(fig)

    def showPlotMessage(self, message: str):
        self.plotView.showMessage(message)

    def updateSites(self, sites: list[str]):
        current = self.siteComboBox.currentText()
        self.siteComboBox.blockSignals(True)
        self.siteComboBox.clear()
        self.siteComboBox.addItem('All sites')
        if len(sites) > 1:
            self.siteComboBox.addItems(sorted(sites))
        idx = self.siteComboBox.findText(current)
        self.siteComboBox.setCurrentIndex(idx if idx >= 0 else 0)
        self.siteComboBox.blockSignals(False)

    def setRawDataFrame(self, testName: str, df: pd.DataFrame):
        self._pendingRawData = (testName, df)
        self._rawDataDirty = True
        if self.tabs.currentIndex() == self._rawTabIndex:
            self._flushPendingRawData()

    def setPlotControlsEnabled(self, enabled: bool, isCxCy: bool = False):
        self._controlsEnabled = enabled
        self._isCxCy = isCxCy
        self._updateControlStates()

    def getPlotOptions(self) -> dict:
        return {
            'site': self.siteComboBox.currentText(),
            'plotType': self.plotTypeComboBox.currentText(),
            'orderBy': self.orderByComboBox.currentText(),
            'limits': self.limitsComboBox.currentText(),
            'limitsMode': self.limitsComboBox.currentText(),
            'valuesInLimits': self.valuesInLimitsButton.isChecked(),
            'logScale': self.logScaleButton.isChecked(),
            'snQuery': self.snFilterEdit.text().strip(),
            'onlySn': self.onlySnButton.isChecked(),
        }

    def clear(self):
        self._currentRawTestName = ''
        self._pendingRawData = None
        self._rawDataDirty = False
        self._rawFilterTimer.stop()
        self._snFilterTimer.stop()

        self.snFilterEdit.blockSignals(True)
        self.snFilterEdit.clear()
        self.snFilterEdit.blockSignals(False)

        self.onlySnButton.blockSignals(True)
        self.onlySnButton.setChecked(False)
        self.onlySnButton.blockSignals(False)
        self.setSnMatchInfo(0, 0, hasQuery=False)

        self.rawSearchEdit.blockSignals(True)
        self.rawSearchEdit.clear()
        self.rawSearchEdit.setStyleSheet('')
        self.rawSearchEdit.setEnabled(False)
        self.rawSearchEdit.blockSignals(False)

        self.rawRegexButton.blockSignals(True)
        self.rawRegexButton.setChecked(False)
        self.rawRegexButton.setEnabled(False)
        self.rawRegexButton.blockSignals(False)

        self.rawColumnComboBox.blockSignals(True)
        self.rawColumnComboBox.clear()
        self.rawColumnComboBox.addItem('All columns')
        self.rawColumnComboBox.setEnabled(False)
        self.rawColumnComboBox.blockSignals(False)

        self.tableView.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.tableModel.clear()
        self.tableInfoLabel.setText('No data loaded')
        self.exportCsvButton.setEnabled(False)

        self.yieldParetoTab.clear()
        self.pivotTab.clear()

        self.updateSites([])
        self.setPlotControlsEnabled(False)
        self.plotView.showMessage('Data cleared.')

    def setBatchMeasurements(self, measurements: dict[str, pd.DataFrame], resetExcluded: bool = False):
        isYieldActive = self.tabs.currentIndex() == self._yieldTabIndex
        self.yieldParetoTab.setMeasurements(measurements, isTabActive=isYieldActive, resetExcluded=resetExcluded)
        self.pivotTab.setMeasurements(measurements, resetSelection=resetExcluded)

    def switchToPlotsTab(self):
        self.tabs.setCurrentIndex(self._plotsTabIndex)

    def cleanup(self):
        self.plotView.cleanup()
        self.yieldParetoTab.cleanup()
        self.pivotTab.cleanup()

    def resetSiteToAll(self):
        self.siteComboBox.blockSignals(True)
        self.siteComboBox.setCurrentIndex(0)
        self.siteComboBox.blockSignals(False)