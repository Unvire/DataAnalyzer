import re

from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLineEdit, QListWidget, QPushButton, QVBoxLayout,
    QWidget,
)

from src.ui.widgets.statsPanel import StatsPanel


class SidebarPanel(QWidget):
    processorChanged = Signal(str)
    openFolderRequested = Signal()
    clearRequested = Signal()
    testSelected = Signal(str)
    generateReportRequested = Signal()
    searchSubfoldersChanged = Signal(bool)

    PLACEHOLDER_PROCESSOR = 'Select log type...'

    def __init__(self, processorNames:list[str], parent=None):
        super().__init__(parent)
        self._allTestNames: list[str] = []
        self._filterTimer = QTimer(self)
        self._filterTimer.setSingleShot(True)
        self._filterTimer.setInterval(150)
        self._filterTimer.timeout.connect(self._applyRegexFilter)

        self._buildUi(processorNames)
        self._bindEvents()
        self.setDataControlsEnabled(False)

    def _buildUi(self, processorNames:list[str]):
        self.setMinimumWidth(290)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        sourceGroup = QGroupBox('Data source')
        sourceLayout = QVBoxLayout(sourceGroup)
        sourceLayout.setSpacing(6)

        self.processorComboBox = QComboBox()
        self.processorComboBox.setCursor(Qt.PointingHandCursor)
        self.processorComboBox.addItem(self.PLACEHOLDER_PROCESSOR)
        self.processorComboBox.addItems(processorNames)

        actionRow = QHBoxLayout()
        actionRow.setSpacing(6)
        self.openFolderButton = QPushButton('Open folder')
        self.openFolderButton.setProperty('accent', True)
        self.openFolderButton.setEnabled(False)

        self.clearButton = QPushButton('Clear')
        actionRow.addWidget(self.openFolderButton, 2)
        actionRow.addWidget(self.clearButton, 1)

        self.subfoldersCheckBox = QCheckBox('Search subfolders')
        self.subfoldersCheckBox.setChecked(True)

        sourceLayout.addWidget(self.processorComboBox)
        sourceLayout.addLayout(actionRow)
        sourceLayout.addWidget(self.subfoldersCheckBox)

        testsGroup = QGroupBox('Tests (0)')
        self.testsGroup = testsGroup
        testsLayout = QVBoxLayout(testsGroup)
        testsLayout.setSpacing(6)

        self.regexFilterEdit = QLineEdit()
        self.regexFilterEdit.setPlaceholderText('Filter tests')
        self.regexFilterEdit.setClearButtonEnabled(True)

        self.testListWidget = QListWidget()
        self.testListWidget.setAlternatingRowColors(True)
        self.testListWidget.setSortingEnabled(False)

        testsLayout.addWidget(self.regexFilterEdit)
        testsLayout.addWidget(self.testListWidget, 1)

        self.statsPanel = StatsPanel()

        self.generateReportButton = QPushButton('Generate report')
        self.generateReportButton.setProperty('accent', True)

        layout.addWidget(sourceGroup)
        layout.addWidget(testsGroup, 1)
        layout.addWidget(self.statsPanel)
        layout.addWidget(self.generateReportButton)

    def _bindEvents(self):
        self.processorComboBox.currentTextChanged.connect(self._onProcessorChanged)
        self.openFolderButton.clicked.connect(self.openFolderRequested.emit)
        self.clearButton.clicked.connect(self.clearRequested.emit)
        self.subfoldersCheckBox.toggled.connect(self.searchSubfoldersChanged.emit)
        self.regexFilterEdit.textChanged.connect(lambda _: self._filterTimer.start())
        self.testListWidget.currentTextChanged.connect(self._onCurrentTestChanged)
        self.generateReportButton.clicked.connect(self.generateReportRequested.emit)

    def _onProcessorChanged(self, text:str):
        isValid = text != self.PLACEHOLDER_PROCESSOR
        self.openFolderButton.setEnabled(isValid)
        if isValid:
            self.processorChanged.emit(text)

    def _onCurrentTestChanged(self, testName:str):
        if testName:
            self.testSelected.emit(testName)

    def setTestNames(self, testNames:list[str]):
        self._allTestNames = list(testNames)
        self._populateList(self._allTestNames)
        if self.testListWidget.count() > 0:
            self.testListWidget.setCurrentRow(0)

    def _populateList(self, names:list[str]):
        self.testListWidget.blockSignals(True)
        self.testListWidget.clear()
        self.testListWidget.setSortingEnabled(False)
        self.testListWidget.addItems(names)
        self.testListWidget.blockSignals(False)
        self.testsGroup.setTitle(f'Tests ({len(names)} / {len(self._allTestNames)})')

    def _applyRegexFilter(self):
        pattern = self.regexFilterEdit.text().strip()
        if not pattern:
            self.regexFilterEdit.setStyleSheet('')
            self._populateList(self._allTestNames)
            return

        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            self.regexFilterEdit.setStyleSheet('')
            filtered = [name for name in self._allTestNames if compiled.search(name)]
            self._populateList(filtered)
        except re.error:
            self.regexFilterEdit.setStyleSheet('border: 1px solid #d9534f;')

    def setAppendMode(self, isAppend:bool):
        self.openFolderButton.setText('Load more logs' if isAppend else 'Open folder')

    def setBusy(self, isBusy:bool):
        self.processorComboBox.setEnabled(not isBusy)
        self.openFolderButton.setEnabled(
            not isBusy and self.processorComboBox.currentText() != self.PLACEHOLDER_PROCESSOR
        )
        self.clearButton.setEnabled(not isBusy and bool(self._allTestNames))
        self.generateReportButton.setEnabled(not isBusy and bool(self._allTestNames))

    def setDataControlsEnabled(self, enabled: bool):
        self.clearButton.setEnabled(enabled)
        self.regexFilterEdit.setEnabled(enabled)
        self.generateReportButton.setEnabled(enabled)

    def reset(self):
        self._allTestNames = []
        self.testListWidget.clear()
        self.testsGroup.setTitle('Tests (0)')
        self.regexFilterEdit.clear()
        self.statsPanel.clear()
        self.processorComboBox.setCurrentIndex(0)
        self.setAppendMode(False)
        self.setDataControlsEnabled(False)

    def selectTest(self, testName: str) -> bool:
        if testName not in self._allTestNames:
            return False

        items = self.testListWidget.findItems(testName, Qt.MatchFlag.MatchExactly)
        if not items:
            self._filterTimer.stop()
            self.regexFilterEdit.blockSignals(True)
            self.regexFilterEdit.clear()
            self.regexFilterEdit.setStyleSheet('')
            self.regexFilterEdit.blockSignals(False)
            self._populateList(self._allTestNames)
            items = self.testListWidget.findItems(testName, Qt.MatchFlag.MatchExactly)

        if not items:
            return False

        self.testListWidget.blockSignals(True)
        self.testListWidget.setCurrentItem(items[0])
        self.testListWidget.scrollToItem(items[0])
        self.testListWidget.blockSignals(False)
        return True