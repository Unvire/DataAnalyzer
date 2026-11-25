from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QLabel, QMainWindow, QMessageBox, QProgressBar, QSplitter

from src.measurementEngine import MeasurementEngine
from src.plotGenerator import PlotlyChartGenerator
from src.ui.widgets.sidebarPanel import SidebarPanel
from src.ui.widgets.workspacePanel import WorkspacePanel
from src.ui.workers import LogLoaderWorker
from src.siFormatter import shouldAutoLogScale


class DataAnalyzerWindow(QMainWindow):
    def __init__(self, version:str):
        super().__init__()
        self.setWindowTitle(f'Data Analyzer {version}')
        self.resize(1380, 820)

        self.engine = MeasurementEngine()
        self.plotGenerator = PlotlyChartGenerator()
        self._loadedProcessorType = ''
        self._selectedProcessorType = ''
        self._isSearchInSubfolders = True
        self._selectedTestName = ''
        self._loaderWorker: LogLoaderWorker | None = None

        self._buildUi()
        self._bindEvents()

    def _buildUi(self):
        processorNames = list(MeasurementEngine.PROCESSORS_DICT.keys())
        self.sidebar = SidebarPanel(processorNames)
        self.workspace = WorkspacePanel()

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
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
        self.workspace.statusMessageRequested.connect(self.statusLabel.setText)

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
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog,
        )
        if not folderPath:
            return

        isAppend = self._loadedProcessorType == self._selectedProcessorType and bool(self.engine.getMeasurements())
        self._startLoadingLogs(folderPath, isAppend)

    def _startLoadingLogs(self, folderPath:str, isAppend:bool):
        self.sidebar.setBusy(True)
        self.progressBar.setValue(0)
        self.progressBar.setVisible(True)
        self.statusLabel.setText(f'Processing folder: {folderPath}...')

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

    def _onLoadingFinished(self):
        self.progressBar.setValue(100)
        self.progressBar.setVisible(False)
        self.sidebar.setBusy(False)

        measurements = self.engine.getMeasurements()
        if not measurements:
            self.statusLabel.setText('No matching logs found')
            QMessageBox.warning(self, 'No Data', 'No measurements were found for the selected log format.')
            return

        self._loadedProcessorType = self._selectedProcessorType
        self.sidebar.setAppendMode(True)
        self.sidebar.setDataControlsEnabled(True)

        testNames = list(measurements)
        self.sidebar.setTestNames(testNames)
        self._onTestSelected(testNames[0])

    def _onLoadingError(self, errorMessage:str):
        self.progressBar.setVisible(False)
        self.sidebar.setBusy(False)
        self.statusLabel.setText('Error while loading logs')
        QMessageBox.critical(self, 'Processing Error', f'An error occurred while reading files:\n{errorMessage}')

    def _onTestSelected(self, testName: str):
        df = self.engine.getTestDataFrame(testName)
        if df is None:
            return

        self._selectedTestName = testName
        sites = df['Site'].dropna().unique().tolist()
        isCxCy = MeasurementEngine.isCxCyDataFrame(df)

        self.workspace.updateSites(sites)
        self.workspace.setPlotControlsEnabled(True, isCxCy=isCxCy)

        if not isCxCy and not df.empty and 'Value' in df.columns:
            lsl = float(df['LSL'].iloc[-1]) if 'LSL' in df.columns else None
            usl = float(df['USL'].iloc[-1]) if 'USL' in df.columns else None
            vals = df['Value'].dropna().to_numpy(dtype=float)
            
            autoLog = shouldAutoLogScale(vals, lsl, usl, ratioThreshold=1000.0)
            
            self.workspace.logScaleButton.blockSignals(True)
            self.workspace.logScaleButton.setChecked(autoLog)
            self.workspace.logScaleButton.blockSignals(False)

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

        totalTests = len(self.engine.getMeasurements())
        self.statusLabel.setText(
            f'Tests: {totalTests:,}  |  Selected: {self._selectedTestName}  |  '
            f'Samples: {len(filteredDf):,} (Site: {selectedSite})'
        )

    def _onClear(self):
        reply = QMessageBox.question(
            self,
            'Clear Data',
            'Are you sure you want to clear all loaded data?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.engine.clear()
        self._loadedProcessorType = ''
        self._selectedTestName = ''
        self.sidebar.reset()
        self.workspace.clear()
        self.statusLabel.setText('Data cleared')

    def _onGenerateReport(self):
        QMessageBox.information(
            self,
            'HTML Report v2.0',
            'Jinja2 + Plotly report generator will be connected in the next step.',
        )

    def closeEvent(self, event):
        if self._loaderWorker is not None and self._loaderWorker.isRunning():
            self._loaderWorker.wait(2000)
        self.workspace.plotView.cleanup()
        super().closeEvent(event)