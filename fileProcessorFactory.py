import os
import dataContainer
import speaDataProcessor, fwkDataProcessor, columnDataProcessor

from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

class FileProcessorsFactory:
    def __init__(self):
        self.dataProcessorsDict = {
            'SPEA': speaDataProcessor.SpeaDataProcessor,
            'FWK': fwkDataProcessor.FwkDataProcessor,
            'Column file': columnDataProcessor.ColumnDataProcessor
        }
        self.observersList = []
        self.progressPercent = -1
    
    def setProcessorType(self, loaderType:str):
        if loaderType in self.dataProcessorsDict:
            self.loaderInstance = self.dataProcessorsDict[loaderType]()
    
    def addObserver(self, instance:object):
        self.observersList.append(instance)

    def processAllLogsInFolder(self, folderPath:str):
        self.loaderInstance.clear()
        logFiles = self.getLogsSortedByDate(folderPath)
        numOfFiles = len(logFiles)
        for i, file in enumerate(logFiles):
            logPath = os.path.join(folderPath, file)
            self.processLogFile(logPath)

            progressPercent = int((i + 1) / numOfFiles * 100)
            self.updateObservers(progressPercent)
    
    def updateObservers(self, progressPercent:int):
        for observer in self.observersList:
            try:
                QMetaObject.invokeMethod(
                    observer,
                    "updateProgressBar",
                    Qt.QueuedConnection,
                    Q_ARG(int, progressPercent)
                )
            except Exception as e:
                print(e)
    
    def processLogFile(self, logPath:str):
        self.loaderInstance.processLogFile(logPath)
    
    def getAllMeasurements(self) -> dict[str:dataContainer.DataContainer]:
        return self.loaderInstance.getMeasurements()
    
    def getTestMeasurements(self, testName:str) -> dataContainer.DataContainer:
        allMeasurements = self.getAllMeasurements()
        return allMeasurements.get(testName, None)
    
    def getLogsSortedByDate(self, folderPath:str) -> list[str]:
        logNames = os.listdir(folderPath)
        sortingKey = lambda x: os.path.getmtime(os.path.join(folderPath, x))
        return sorted(logNames, key=sortingKey)