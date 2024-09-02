import abc
import dataContainer

class AbstractDataProcessor(abc.ABC):
    def __init__(self):
        self.measurements = {}
    
    def clear(self):
        self.measurements = {}
    
    def getMeasurements(self) -> dict[str:dataContainer.DataContainer]:
        return self.measurements

    @abc.abstractmethod
    def processLogFile(self, filePath:str):
        pass