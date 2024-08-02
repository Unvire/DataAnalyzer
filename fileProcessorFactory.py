import os
import dataContainer
import speaDataProcessor

class FileProcessorsFactory:
    def __init__(self, loaderType:str):
        self.dataProcessorsDict = {
            'SPEA': speaDataProcessor.SpeaDataProcessor
        }

        self.loaderInstance = self.dataProcessorsDict[loaderType]()
    
    def processAllLogsInFolder(self, folderPath:str):
        for file in os.listdir(folderPath):
            logPath = os.path.join(folderPath, file)
            self.processLogFile(logPath)
    
    def processLogFile(self, logPath:str):
        self.loaderInstance.processLogFile(logPath)
    
    def getAllMeasurements(self) -> dict[str:dataContainer.DataContainer]:
        return self.loaderInstance.getMeasurements()
    
    def getTestMeasurements(self, testName:str) -> dataContainer.DataContainer:
        allMeasurements = self.getAllMeasurements()
        return allMeasurements.get(testName, None)