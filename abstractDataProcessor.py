import abc
import dataContainer

class AbstractDataProcessor(metaclass=abc.ABCMeta):
    def __init__(self):
        self.measurements = {}
    
    def clear(self):
        self.measurements = {}
    
    def getMeasurements(self) -> dict[str:dataContainer.DataContainer]:
        return self.measurements

    def createDataContainer(self, testName:str, lowerLimit:str|float, upperLimit:str|float):
        if testName not in self.measurements:
            testContainer = dataContainer.DataContainer(testName)
            testContainer.setLimits(lowerLimit, upperLimit)
            self.measurements[testName] = testContainer

    @abc.abstractmethod
    def processLogFile(self, filePath:str):
        pass