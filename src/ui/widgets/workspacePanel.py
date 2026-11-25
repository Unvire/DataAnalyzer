import os, re

import pandas as pd
import plotly.graph_objects as go
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableView, QTabWidget, QVBoxLayout, QWidget,
)

from src.ui.widgets.dataTableModel import PandasTableModel, RawDataFilterProxyModel
from src.ui.widgets.plotlyView import PlotlyView


class WorkspacePanel(QWidget):
    plotOptionsChanged = Signal()
    openPlotWindowRequested = Signal()
    statusMessageRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._controlsEnabled = False
        self._isCxCy = False
        self._currentRawTestName = ''

        self._rawFilterTimer = QTimer(self)
        self._rawFilterTimer.setSingleShot(True)
        self._rawFilterTimer.setInterval(150)
        self._rawFilterTimer.timeout.connect(self._applyRawDataFilter)

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
        self.tabs.addTab(self._buildPlotsTab(), 'Plots')
        self.tabs.addTab(self._buildYieldParetoTab(), 'Yield && Pareto')
        self.tabs.addTab(self._buildPivotTab(), 'Pivot && Multi-Test')
        self.tabs.addTab(self._buildRawDataTab(), 'Raw data')

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

        self.plotView = PlotlyView()

        layout.addLayout(controlsRow)
        layout.addWidget(self.plotView, 1)
        return tab

    def _buildYieldParetoTab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        placeholder = QLabel('Yield & Pareto module will be connected in the next step.')
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet('color: #9da0a8;')
        layout.addWidget(placeholder)
        return tab

    def _buildPivotTab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        placeholder = QLabel('Pivot table & Multi-Test analysis will be connected in the next step.')
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet('color: #9da0a8;')
        layout.addWidget(placeholder)
        return tab

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
        self.tableProxyModel = RawDataFilterProxyModel(self)
        self.tableProxyModel.setSourceModel(self.tableModel)

        self.tableView = QTableView()
        self.tableView.setModel(self.tableProxyModel)
        self.tableView.setAlternatingRowColors(True)
        self.tableView.setSortingEnabled(True)
        self.tableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tableView.verticalHeader().setDefaultSectionSize(24)

        layout.addLayout(controlsRow)
        layout.addWidget(self.tableInfoLabel)
        layout.addWidget(self.tableView, 1)
        return tab

    def _bindEvents(self):
        self.plotTypeComboBox.currentTextChanged.connect(self._onPlotTypeChanged)
        self.siteComboBox.currentTextChanged.connect(self._emitOptionsChanged)
        self.orderByComboBox.currentTextChanged.connect(self._emitOptionsChanged)
        self.limitsComboBox.currentTextChanged.connect(self._emitOptionsChanged)
        self.valuesInLimitsButton.toggled.connect(self._emitOptionsChanged)
        self.logScaleButton.toggled.connect(self._emitOptionsChanged)
        self.copyPlotButton.clicked.connect(self._onCopyPlotClicked)

        self.rawSearchEdit.textChanged.connect(lambda _: self._rawFilterTimer.start())
        self.rawRegexButton.toggled.connect(self._applyRawDataFilter)
        self.rawColumnComboBox.currentIndexChanged.connect(self._applyRawDataFilter)
        self.exportCsvButton.clicked.connect(self._onExportCsvClicked)

    def _onPlotTypeChanged(self, *_):
        self._updateControlStates()
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

        self.tableProxyModel.setFilterQuery(query, columnIdx, regexEnabled=regexEnabled)

        if self.tableProxyModel.hasRegexError:
            self.rawSearchEdit.setStyleSheet('border: 1px solid #d9534f;')
        else:
            self.rawSearchEdit.setStyleSheet('')

        self._updateRawTableInfo()

    def _updateRawTableInfo(self):
        totalRows = self.tableModel.rowCount()
        visibleRows = self.tableProxyModel.rowCount()

        if not self._currentRawTestName or totalRows == 0:
            self.tableInfoLabel.setText('No data loaded')
            self.exportCsvButton.setEnabled(False)
            return

        if visibleRows == totalRows:
            self.tableInfoLabel.setText(f'Test: {self._currentRawTestName}  |  Rows: {totalRows:,}')
        else:
            self.tableInfoLabel.setText(f'Test: {self._currentRawTestName}  |  Showing: {visibleRows:,} / {totalRows:,} rows')

        self.exportCsvButton.setEnabled(visibleRows > 0)

    def _onExportCsvClicked(self):
        exportDf = self.tableProxyModel.getFilteredDataFrame()
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
            self.exportCsvButton.setEnabled(self.tableProxyModel.rowCount() > 0),
        ))
        self.statusMessageRequested.emit(
            f'Exported {len(exportDf):,} rows to {os.path.basename(filePath)}'
        )

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
            return

        self.siteLabel.setEnabled(True)
        self.siteComboBox.setEnabled(True)
        self.valuesInLimitsButton.setEnabled(True)
        self.copyPlotButton.setEnabled(True)

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
        }

    def clear(self):
        self._currentRawTestName = ''
        self._rawFilterTimer.stop()

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

        self.tableProxyModel.clearFilter()
        self.tableModel.clear()
        self.tableInfoLabel.setText('No data loaded')
        self.exportCsvButton.setEnabled(False)

        self.updateSites([])
        self.setPlotControlsEnabled(False)
        self.plotView.showMessage('Data cleared.')