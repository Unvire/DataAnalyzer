from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFileDialog, QLabel, QMainWindow, QMessageBox, QProgressBar, QSplitter

from src.measurementEngine import MeasurementEngine
from src.ui.widgets.sidebarPanel import SidebarPanel
from src.ui.widgets.workspacePanel import WorkspacePanel
from src.ui.workers import LogLoaderWorker
from src.plotGenerator import PlotlyChartGenerator


class DataAnalyzerWindow(QMainWindow):
    def __init__(self, version:str):
        super().__init__()
        self.setWindowTitle(f'Data Analyzer {version}')
        self.resize(1380, 820)

        self.engine = MeasurementEngine()
        self._loadedProcessorType = ''
        self._selectedProcessorType = ''
        self._isSearchInSubfolders = True
        self._selectedTestName = ''
        self._loaderWorker: LogLoaderWorker | None = None
        self.plotGenerator = PlotlyChartGenerator()

        self._buildUi()
        self._bindEvents()

    def _buildUi(self):
        processorNames = list(MeasurementEngine.PROCESSORS_DICT.keys())
        self.sidebar = SidebarPanel(processorNames)
        self.workspace = WorkspacePanel()

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.workspace)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([340, 1040])
        self.setCentralWidget(self.splitter)

        self.statusLabel = QLabel('Ready')
        self.progressBar = QProgressBar()
        self.progressBar.setFixedWidth(220)
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.progressBar.setVisible(False)

        self.statusBar().addWidget(self.statusLabel, 1)
        self.statusBar().addPermanentWidget(self.progressBar)

    def _bindEvents(self):
        self.sidebar.processorChanged.connect(self._onProcessorChanged)
        self.sidebar.openFolderRequested.connect(self._onOpenFolder)
        self.sidebar.clearRequested.connect(self._onClear)
        self.sidebar.searchSubfoldersChanged.connect(self._onSearchSubfoldersChanged)
        self.sidebar.testSelected.connect(self._onTestSelected)
        self.sidebar.generateReportRequested.connect(self._onGenerateReport)
        self.workspace.plotOptionsChanged.connect(self._refreshCurrentView)

    def _onProcessorChanged(self, processorName:str):
        self._selectedProcessorType = processorName
        self.engine.setProcessorType(processorName)
        isSameType = self._loadedProcessorType == processorName and bool(self.engine.getMeasurements())
        self.sidebar.setAppendMode(isSameType)

    def _onSearchSubfoldersChanged(self, checked:bool):
        self._isSearchInSubfolders = checked

    def _onOpenFolder(self):
        folderPath = QFileDialog.getExistingDirectory(
            self,
            'Select logs folder',
            '',
            QFileDialog.ShowDirsOnly | QFileDialog.DontUseNativeDialog,
        )
        if not folderPath:
            return

        isAppend = self._loadedProcessorType == self._selectedProcessorType and bool(self.engine.getMeasurements())
        self._startLoadingLogs(folderPath, isAppend)

    def _startLoadingLogs(self, folderPath: str, isAppend: bool):
        self.sidebar.setBusy(True)
        self.progressBar.setValue(0)
        self.progressBar.setVisible(True)
        self.statusLabel.setText(f'Processing logs: {folderPath}...')

        self._loaderWorker = LogLoaderWorker(
            engine=self.engine,
            folderPath=folderPath,
            isAppendTests=isAppend,
            isSearchInSubfolders=self._isSearchInSubfolders,
            useMultiprocessing=True,
            parent=self,
        )
        self._loaderWorker.progressChanged.connect(self.progressBar.setValue)
        self._loaderWorker.finishedLoading.connect(self._onLoadingFinished)
        self._loaderWorker.errorOccurred.connect(self._onLoadingError)
        self._loaderWorker.start()

    def _onLoadingFinished(self, measurements:dict):
        self.progressBar.setValue(100)
        self.progressBar.setVisible(False)
        self.sidebar.setBusy(False)

        if not measurements:
            self.statusLabel.setText('No matching logs found')
            QMessageBox.warning(self, 'No data', 'No data found for selected logs type.')
            return

        self._loadedProcessorType = self._selectedProcessorType
        self.sidebar.setAppendMode(True)
        self.sidebar.setDataControlsEnabled(True)

        testNames = list(measurements.keys())
        self.sidebar.setTestNames(testNames)

        totalPoints = sum(len(df) for df in measurements.values())
        self.statusLabel.setText(f'Loaded {len(testNames)} testów ({totalPoints:,} samples)')
        self._onTestSelected(testNames[0])

    def _onLoadingError(self, errorMessage: str):
        self.progressBar.setVisible(False)
        self.sidebar.setBusy(False)
        self.statusLabel.setText('Error during processing logs')
        QMessageBox.critical(self, 'Error processing logs', f'Error during processing logs:\n{errorMessage}')

    def _onTestSelected(self, testName: str):
        df = self.engine.getTestDataFrame(testName)
        if df is None:
            return

        self._selectedTestName = testName
        sites = df['Site'].dropna().unique().tolist()
        isCxCy = MeasurementEngine.isCxCyDataFrame(df)

        self.workspace.updateSites(sites)
        self.workspace.setPlotControlsEnabled(True, isCxCy=isCxCy)
        self._refreshCurrentView()

    def _refreshCurrentView(self):
        if not self._selectedTestName:
            return

        df = self.engine.getTestDataFrame(self._selectedTestName)
        if df is None:
            return

        options = self.workspace.getPlotOptions()
        selectedSite = options['site']
        filteredDf = df if selectedSite == 'All sites' else df[df['Site'] == selectedSite]

        self.workspace.setRawDataFrame(self._selectedTestName, filteredDf)

        isCxCy = MeasurementEngine.isCxCyDataFrame(filteredDf)
        if isCxCy:
            self.sidebar.statsPanel.updateStats({'samples': f'{len(filteredDf):,}'})
        elif not filteredDf.empty:
            self.sidebar.statsPanel.updateStats({
                'samples': f'{len(filteredDf):,}',
                'lsl': f"{filteredDf['LSL'].iloc[-1]:.4g}",
                'usl': f"{filteredDf['USL'].iloc[-1]:.4g}",
            })
        else:
            self.sidebar.statsPanel.clear()

        fig = self.plotGenerator.createPlot(
            df=filteredDf,
            testName=self._selectedTestName,
            plotType=options['plotType'],
            orderBy=options['orderBy'],
            limitsMode=options['limits'],
            valuesInLimits=options['valuesInLimits'],
            logScale=options['logScale'],
        )
        self.workspace.setFigure(fig)

    def _onClear(self):
        reply = QMessageBox.question(
            self,
            'Clear data',
            'Do you want to clear data?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.engine.clear()
        self._loadedProcessorType = ''
        self._selectedTestName = ''
        self.sidebar.reset()
        self.workspace.clear()
        self.statusLabel.setText('Data cleared')

    def _onGenerateReport(self):
        QMessageBox.information(self,
            'Raport HTML v2.0',
            'Generator raportów Jinja2 + Plotly zostanie podpięty po dodaniu kalkulatora i wykresów.',
        )

    def closeEvent(self, event):
        self.workspace.plotView.cleanup()
        super().closeEvent(event)