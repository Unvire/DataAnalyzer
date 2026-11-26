from PySide6.QtCore import QThread, Signal

from src.measurementEngine import MeasurementEngine
from src.yieldParetoAnalyzer import BatchSummaryResult, YieldParetoAnalyzer


class LogLoaderWorker(QThread):
    progressChanged = Signal(int)
    finishedLoading = Signal()
    errorOccurred = Signal(str)

    def __init__(self, engine:MeasurementEngine, folderPath:str, isAppendTests:bool, isSearchInSubfolders:bool,
            useMultiprocessing:bool=True, parent=None):
        
        super().__init__(parent)
        self.engine = engine
        self.folderPath = folderPath
        self.isAppendTests = isAppendTests
        self.isSearchInSubfolders = isSearchInSubfolders
        self.useMultiprocessing = useMultiprocessing

    def run(self):
        try:
            self.engine.processFolder(
                folderPath=self.folderPath,
                isAppendTests=self.isAppendTests,
                isSearchInSubfolders=self.isSearchInSubfolders,
                progressCallback=self.progressChanged.emit,
                useMultiprocessing=self.useMultiprocessing,
            )
            self.finishedLoading.emit()
        except Exception as exc:
            self.errorOccurred.emit(str(exc))

class YieldAnalysisWorker(QThread):
    finishedAnalysis = Signal(int)
    errorOccurred = Signal(str)

    def __init__(self, analyzer:YieldParetoAnalyzer, measurements:dict, site:str, limitsMode:str,
            requestId:int, parent=None):

        super().__init__(parent)
        self.analyzer = analyzer
        self.measurements = measurements
        self.site = site
        self.limitsMode = limitsMode
        self.requestId = requestId
        self.result: BatchSummaryResult | None = None

    def run(self):
        try:
            self.result = self.analyzer.analyze(
                measurements=self.measurements,
                site=self.site,
                limitsMode=self.limitsMode,
            )
            self.finishedAnalysis.emit(self.requestId)
        except Exception as exc:
            self.errorOccurred.emit(str(exc))