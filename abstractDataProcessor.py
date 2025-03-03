import abc
import dataContainer

class AbstractDataProcessor(metaclass=abc.ABCMeta):
    def __init__(self):
        self.measurements = {}
    
    def clear(self):
        self.measurements = {}
    
    def getMeasurements(self) -> dict[str:dataContainer.DataContainer]:
        return self.measurements

    def createDataContainer(self, testName:str, lowerLimit:str|float, upperLimit:str|float, testTime:str):
        if testName not in self.measurements:
            testContainer = dataContainer.DataContainer(testName)
            self.measurements[testName] = testContainer
        self.measurements[testName].addLimits(lowerLimit, upperLimit, testTime)
    
    def createCXCYDataContainer(self, testName:str, boundaryXYsString:str, testTime:str):
        if testName not in self.measurements:
            testContainer = dataContainer.CxCyDataContainer(testName)
            self.measurements[testName] = testContainer
        self.measurements[testName].addLimits(boundaryXYsString, testTime)

    @abc.abstractmethod
    def processLogFile(self, filePath:str, testDate:str):
        pass