import abc
from datetime import datetime

import src.dataContainer as dataContainer

class AbstractDataProcessor(metaclass=abc.ABCMeta):
    def __init__(self):
        self.measurements = {}
    
    def clear(self):
        self.measurements = {}
    
    def getMeasurements(self) -> dict[str:dataContainer.DataContainer]:
        return self.measurements

    def createDataContainer(self, testName:str):
        if testName not in self.measurements:
            testContainer = dataContainer.DataContainer(testName)
            self.measurements[testName] = testContainer

    @abc.abstractmethod
    def processLogFile(self, filePath:str, testDate:str, serialNumber:str):
        pass

    @abc.abstractmethod
    def getLogDateTime(self, datetimeString:str):
        dateTimeObject = datetime.strptime(datetimeString, '%Y%m%d%H%M%S')
        return dateTimeObject.strftime('%Y/%m/%d %H:%M:%S')