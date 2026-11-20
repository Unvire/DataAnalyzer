import pandas as pd
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableView, QTabWidget,
    QVBoxLayout, QWidget,
)

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from src.ui.widgets.dataTableModel import PandasTableModel


class WorkspacePanel(QWidget):
    plotOptionsChanged = pyqtSignal()
    openPlotWindowRequested = pyqtSignal()

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
        self.tabs.addTab(self._buildPlotsTab(), 'Plots')
        self.tabs.addTab(self._buildYieldParetoTab(), 'Yield & Pareto')
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

        self.valuesInLimitsButton = QPushButton('Only in limits')
        self.valuesInLimitsButton.setCheckable(True)

        self.logScaleButton = QPushButton('Log scale')
        self.logScaleButton.setCheckable(True)

        self.newWindowButton = QPushButton('New window')

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

        if HAS_WEBENGINE:
            self.plotView = QWebEngineView()
            self.plotView.page().setBackgroundColor(QColor('#1e1f22'))
            self.setPlotHtml(self._emptyPlotHtml('Load logs in order to display plot.'))
        else:
            self.plotView = QLabel('Install PyQtWebEngine in order to display interactive Plotly plots.')
            self.plotView.setAlignment(Qt.AlignCenter)

        layout.addLayout(controlsRow)
        layout.addWidget(self.plotView, 1)
        return tab

    def _buildYieldParetoTab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        placeholder = QLabel('Moduł Yield & Pareto zostanie podpięty w kolejnym kroku (kalkulator + Plotly).')
        placeholder.setAlignment(Qt.AlignCenter)
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
        self.tableView.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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

    def setPlotHtml(self, html:str):
        if HAS_WEBENGINE:
            self.plotView.setHtml(html)

    def updateSites(self, sites:list[str]):
        current = self.siteComboBox.currentText()
        self.siteComboBox.blockSignals(True)
        self.siteComboBox.clear()
        self.siteComboBox.addItem('All sites')
        if len(sites) > 1:
            self.siteComboBox.addItems(sorted(sites))
        idx = self.siteComboBox.findText(current)
        self.siteComboBox.setCurrentIndex(idx if idx >= 0 else 0)
        self.siteComboBox.blockSignals(False)

    def setRawDataFrame(self, testName:str, df:pd.DataFrame):
        self.tableModel.setDataFrame(df)
        self.tableInfoLabel.setText(f'Test: {testName}  |  Samples: {len(df):,}')

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
        self.tableInfoLabel.setText('No loaded data')
        self.updateSites([])
        self.setPlotControlsEnabled(False)
        self.setPlotHtml(self._emptyPlotHtml('Data was cleared.'))

    @staticmethod
    def _emptyPlotHtml(message: str) -> str:
        return f"""
        <html>
            <body style="background:#1e1f22; color:#9da0a8; font-family:'Segoe UI', sans-serif;
                         display:flex; align-items:center; justify-content:center; height:92vh; margin:0;">
                <div style="text-align:center; font-size:15px;">{message}</div>
            </body>
        </html>
        """