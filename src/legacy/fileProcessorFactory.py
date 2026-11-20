import os

import src.dataContainer as dataContainer
import src.dataProcessorSpea, src.dataProcessorFwk, src.dataProcessorColumn, src.dataProcessorGrugliasco

from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

class FileProcessorsFactory:
    def __init__(self):
        self.dataProcessorsDict = {
            'SPEA': src.dataProcessorSpea.SpeaDataProcessor,
            'FWK / Ipses / BEC': src.dataProcessorFwk.FwkDataProcessor,
            'TestStand Grugliasco': src.dataProcessorGrugliasco.GrugliascoDataProcessor,
            'Column file': src.dataProcessorColumn.ColumnDataProcessor
        }
        self.observersList = []
        self.progressPercent = -1
    
    def setProcessorType(self, loaderType:str):
        if loaderType in self.dataProcessorsDict:
            self.loaderInstance = self.dataProcessorsDict[loaderType]()
    
    def addObserver(self, instance:object):
        self.observersList.append(instance)

    def processAllLogsInFolder(self, folderPath:str, isAppendTests:bool, isSearchInSubfolders:bool):
        if not isAppendTests:
            self.loaderInstance.clear()

        logFiles = self._getFilesFromSubfolders(folderPath) if isSearchInSubfolders else os.listdir(folderPath)

        numOfFiles = len(logFiles)
        for i, file in enumerate(logFiles):
            if not '.' in file:
                continue
            
            fileNameWithPossiblePath, fileExtension = file.rsplit('.', 1)
            if fileExtension not in self.loaderInstance.FILE_EXTENSIONS:
                continue
            
            fileName = fileNameWithPossiblePath if os.sep not in fileNameWithPossiblePath else fileNameWithPossiblePath.rsplit(os.sep, 1)[1]
            
            formatedTime = self.loaderInstance.getLogDateTime(fileName)
            logPath = os.path.join(folderPath, file)
            self.processLogFile(logPath, formatedTime)

            progressPercent = int((i + 1) / numOfFiles * 100)
            self.updateObservers(progressPercent)
    
    def updateObservers(self, progressPercent:int):
        for observer in self.observersList:
            try:
                QMetaObject.invokeMethod(
                    observer,
                    'updateProgressBar',
                    Qt.QueuedConnection,
                    Q_ARG(int, progressPercent)
                )
            except Exception as e:
                print(e)
    
    def processLogFile(self, logPath:str, testTime:str):
        self.loaderInstance.processLogFile(logPath, testTime)
    
    def getAllMeasurements(self) -> dict[str:dataContainer.DataContainer]:
        return self.loaderInstance.getMeasurements()
    
    def getTestMeasurements(self, testName:str) -> dataContainer.DataContainer:
        allMeasurements = self.getAllMeasurements()
        return allMeasurements.get(testName, None)

    def _getFilesFromSubfolders(self, folderPath:str) -> list[str]:
        result = []
    
        for subFolderPath, _, files  in os.walk(folderPath):
            for fileName in files:
                fullFilePath = os.path.join(subFolderPath, fileName)
                result.append(fullFilePath)
        
        return result


if __name__ == '__main__':
    def getFolderWithLogs() -> str:        
        from tkinter import filedialog
        folderPath = filedialog.askdirectory()
        return folderPath
    
    folderPath = getFolderWithLogs()
    factory = FileProcessorsFactory()
    factory.setProcessorType('TestStand XYLEM')
    factory.processAllLogsInFolder(folderPath, isAppendTests=False)