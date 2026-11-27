from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton


class ExportActionsBar(QFrame):
    copyPlotClicked = Signal()
    exportCsvClicked = Signal()
    generateReportClicked = Signal()

    def __init__(self, showCsv:bool=False, reportButtonText:str='Generate report...', reportTooltip:str='Generate HTML / PDF report',
            parent=None):
            
        super().__init__(parent)
        self._showCsv = showCsv
        self._copyBaseText = 'Copy plot'

        self.setObjectName('exportActionsBar')
        self.setStyleSheet("""
            QFrame#exportActionsBar {
                background-color: #23252a;
                border: 1px solid #393b40;
                border-radius: 5px;
            }
            QFrame#exportActionsBar QPushButton {
                padding: 3px 9px;
                font-size: 12px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)

        self.copyPlotButton = QPushButton(self._copyBaseText)
        self.copyPlotButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copyPlotButton.setToolTip('Copy current plot to clipboard as PNG')
        self.copyPlotButton.clicked.connect(self.copyPlotClicked.emit)
        layout.addWidget(self.copyPlotButton)

        self.exportCsvButton: QPushButton | None = None
        if showCsv:
            self.exportCsvButton = QPushButton('Export CSV')
            self.exportCsvButton.setCursor(Qt.CursorShape.PointingHandCursor)
            self.exportCsvButton.setToolTip('Export current table to CSV')
            self.exportCsvButton.clicked.connect(self.exportCsvClicked.emit)
            layout.addWidget(self.exportCsvButton)

        self.generateReportButton = QPushButton(reportButtonText)
        self.generateReportButton.setProperty('accent', True)
        self.generateReportButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generateReportButton.setToolTip(reportTooltip)
        self.generateReportButton.clicked.connect(self.generateReportClicked.emit)
        layout.addWidget(self.generateReportButton)

        self.setActionsEnabled(False, hasTableData=False)

    def setActionsEnabled(self, hasData:bool, hasTableData:bool|None=None):
        self.copyPlotButton.setEnabled(hasData)
        self.generateReportButton.setEnabled(hasData)
        if self.exportCsvButton is not None:
            csvEnabled = hasData if hasTableData is None else (hasData and hasTableData)
            self.exportCsvButton.setEnabled(csvEnabled)

    def setCsvEnabled(self, enabled:bool):
        if self.exportCsvButton is not None:
            self.exportCsvButton.setEnabled(enabled)

    def runCopyFeedback(self, copyCallable, isStillEnabledCallable):
        self.copyPlotButton.setText('Copying...')
        self.copyPlotButton.setEnabled(False)

        def onDone(success:bool):
            self.copyPlotButton.setText('Copied!' if success else 'Failed')
            QTimer.singleShot(1200, lambda: (
                self.copyPlotButton.setText(self._copyBaseText),
                self.copyPlotButton.setEnabled(bool(isStillEnabledCallable())),
            ))

        copyCallable(onDone)