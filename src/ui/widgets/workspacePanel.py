import pandas as pd
import plotly.graph_objects as go
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableView,
    QTabWidget, QVBoxLayout, QWidget,
)

from src.ui.widgets.dataTableModel import PandasTableModel
from src.ui.widgets.plotlyView import PlotlyView


class WorkspacePanel(QWidget):
    plotOptionsChanged = Signal()
    openPlotWindowRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
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

        self.siteComboBox = QComboBox()
        self.siteComboBox.addItem('All sites')

        self.plotTypeComboBox = QComboBox()
        self.plotTypeComboBox.addItems(['Sequence', 'Capability (Histogram)', 'Boxplot'])

        self.orderByComboBox = QComboBox()
        self.orderByComboBox.addItems(['Date', 'Sites'])

        self.limitsComboBox = QComboBox()
        self.limitsComboBox.addItems(['All', 'Oldest', 'Newest'])

        for combo in (
            self.siteComboBox,
            self.plotTypeComboBox,
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

        self.newWindowButton = QPushButton('New window')
        self.newWindowButton.setCursor(Qt.CursorShape.PointingHandCursor)

        controlsRow.addWidget(QLabel('Site:'))
        controlsRow.addWidget(self.siteComboBox)
        controlsRow.addWidget(QLabel('Plot:'))
        controlsRow.addWidget(self.plotTypeComboBox)
        controlsRow.addWidget(QLabel('Sorting:'))
        controlsRow.addWidget(self.orderByComboBox)
        controlsRow.addWidget(QLabel('Limits:'))
        controlsRow.addWidget(self.limitsComboBox)
        controlsRow.addWidget(self.valuesInLimitsButton)
        controlsRow.addWidget(self.logScaleButton)
        controlsRow.addStretch(1)
        controlsRow.addWidget(self.newWindowButton)

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

        self.tableInfoLabel = QLabel('No data loaded')
        self.tableInfoLabel.setStyleSheet('color: #9da0a8;')

        self.tableModel = PandasTableModel()
        self.tableView = QTableView()
        self.tableView.setModel(self.tableModel)
        self.tableView.setAlternatingRowColors(True)
        self.tableView.setSortingEnabled(False)
        self.tableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tableView.verticalHeader().setDefaultSectionSize(24)

        layout.addWidget(self.tableInfoLabel)
        layout.addWidget(self.tableView, 1)
        return tab

    def _bindEvents(self):
        self.siteComboBox.currentTextChanged.connect(self._emitOptionsChanged)
        self.plotTypeComboBox.currentTextChanged.connect(self._emitOptionsChanged)
        self.orderByComboBox.currentTextChanged.connect(self._emitOptionsChanged)
        self.limitsComboBox.currentTextChanged.connect(self._emitOptionsChanged)
        self.valuesInLimitsButton.toggled.connect(self._emitOptionsChanged)
        self.logScaleButton.toggled.connect(self._emitOptionsChanged)
        self.newWindowButton.clicked.connect(self.openPlotWindowRequested.emit)

    def _emitOptionsChanged(self, *_):
        self.plotOptionsChanged.emit()

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
        self.tableModel.setDataFrame(df)
        self.tableInfoLabel.setText(f'Test: {testName}  |  Rows: {len(df):,}')

    def setPlotControlsEnabled(self, enabled: bool, isCxCy: bool = False):
        self.siteComboBox.setEnabled(enabled)
        self.valuesInLimitsButton.setEnabled(enabled)
        self.newWindowButton.setEnabled(enabled)

        scalarOnly = enabled and not isCxCy
        self.plotTypeComboBox.setEnabled(scalarOnly)
        self.orderByComboBox.setEnabled(scalarOnly)
        self.limitsComboBox.setEnabled(scalarOnly)
        self.logScaleButton.setEnabled(scalarOnly)

    def getPlotOptions(self) -> dict:
        return {
            'site': self.siteComboBox.currentText(),
            'plotType': self.plotTypeComboBox.currentText(),
            'orderBy': self.orderByComboBox.currentText(),
            'limits': self.limitsComboBox.currentText(),
            'valuesInLimits': self.valuesInLimitsButton.isChecked(),
            'logScale': self.logScaleButton.isChecked(),
        }

    def clear(self):
        self.tableModel.clear()
        self.tableInfoLabel.setText('No data loaded')
        self.updateSites([])
        self.setPlotControlsEnabled(False)
        self.plotView.showMessage('Data cleared.')