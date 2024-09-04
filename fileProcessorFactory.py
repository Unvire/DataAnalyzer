import os
import dataContainer
import speaDataProcessor, fwkDataProcessor, columnDataProcessor

class FileProcessorsFactory:
    def __init__(self):
        self.dataProcessorsDict = {
            'SPEA': speaDataProcessor.SpeaDataProcessor,
            'FWK': fwkDataProcessor.FwkDataProcessor,
            'One column file': columnDataProcessor.ColumnDataProcessor
        }
        self.observersList = []
    
    def setProcessorType(self, loaderType:str):
        if loaderType in self.dataProcessorsDict:
            self.loaderInstance = self.dataProcessorsDict[loaderType]()
    
    def addObserver(self, instance:object):
        self.observersList.append(instance)

    def processAllLogsInFolder(self, folderPath:str):
        self.loaderInstance.clear()
        numOfFiles = len(os.listdir(folderPath))
        for i, file in enumerate(os.listdir(folderPath)):
            logPath = os.path.join(folderPath, file)
            self.processLogFile(logPath)

            progressPercent = int((i + 1) / numOfFiles * 100)
            self.updateObservers(progressPercent)
    
    def updateObservers(self, progressPercent:int):
        for observer in self.observersList:
            observer.updateProgressBar(progressPercent)
    
    def processLogFile(self, logPath:str):
        self.loaderInstance.processLogFile(logPath)
    
    def getAllMeasurements(self) -> dict[str:dataContainer.DataContainer]:
        return self.loaderInstance.getMeasurements()
    
    def getTestMeasurements(self, testName:str) -> dataContainer.DataContainer:
        allMeasurements = self.getAllMeasurements()
        return allMeasurements.get(testName, None)