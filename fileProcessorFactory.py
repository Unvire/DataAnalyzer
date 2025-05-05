import os
from datetime import datetime

import dataContainer
import dataProcessorSpea, dataProcessorFwk, dataProcessorColumn, dataProcessorXylem

from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

class FileProcessorsFactory:
    def __init__(self):
        self.dataProcessorsDict = {
            'SPEA': dataProcessorSpea.SpeaDataProcessor,
            'FWK': dataProcessorFwk.FwkDataProcessor,
            'TestStand XYLEM': dataProcessorXylem.XylemDataProcessor,
            'Column file': dataProcessorColumn.ColumnDataProcessor
        }
        self.observersList = []
        self.progressPercent = -1
    
    def setProcessorType(self, loaderType:str):
        if loaderType in self.dataProcessorsDict:
            self.loaderInstance = self.dataProcessorsDict[loaderType]()
    
    def addObserver(self, instance:object):
        self.observersList.append(instance)

    def processAllLogsInFolder(self, folderPath:str, isAppendTests:bool):
        if not isAppendTests:
            self.loaderInstance.clear()

        logFiles = os.listdir(folderPath)
        numOfFiles = len(logFiles)
        for i, file in enumerate(logFiles):
            fileExtension = file.split('.')[-1]
            if fileExtension not in self.loaderInstance.FILE_EXTENSIONS:
                continue
            logPath = os.path.join(folderPath, file)

            modificationDate = os.path.getmtime(logPath)
            modificationDateAsTimeStamp = datetime.fromtimestamp(modificationDate)
            formatedTime = modificationDateAsTimeStamp.strftime('%Y/%m/%d %H:%M:%S')

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


if __name__ == '__main__':
    def getFolderWithLogs() -> str:        
        from tkinter import filedialog
        folderPath = filedialog.askdirectory()
        return folderPath
    
    folderPath = getFolderWithLogs()
    factory = FileProcessorsFactory()
    factory.setProcessorType('TestStand XYLEM')
    factory.processAllLogsInFolder(folderPath, isAppendTests=False)