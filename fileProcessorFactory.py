import dataContainer
import speaDataProcessor

class DataProcessorsFactory:
    def __init__(self, loaderType:str):
        self.dataProcessorsDict = {
            'SPEA': speaDataProcessor.SpeaDataProcessor
        }

        self.loaderInstance = self.dataProcessorsDict[loaderType]
    
    def processLogFile(self, logPath:str):
        self.loaderInstance.processLogFile(logPath)
    
    def getMeasurements(self) -> dict[str:dataContainer.DataContainer]:
        return self.loaderInstance.getMeasurements()