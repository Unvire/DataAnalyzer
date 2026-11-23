from PySide6.QtCore import QThread, Signal

from src.measurementEngine import MeasurementEngine


class LogLoaderWorker(QThread):
    progressChanged = Signal(int)
    finishedLoading = Signal(dict)
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
            measurements = self.engine.processFolder(
                folderPath=self.folderPath,
                isAppendTests=self.isAppendTests,
                isSearchInSubfolders=self.isSearchInSubfolders,
                progressCallback=self.progressChanged.emit,
                useMultiprocessing=self.useMultiprocessing,
            )
            self.finishedLoading.emit(measurements)
        except Exception as exc:
            self.errorOccurred.emit(str(exc))