import dataContainer
from abstractDataProcessor import AbstractDataProcessor

class ColumnDataProcessor(AbstractDataProcessor):
    def __init__(self):
        super().__init__()

    def processLogFile(self, filePath:str):
        with open(filePath, 'r', encoding='unicode_escape') as file:
            fileLines = file.readlines().replace('\n', '')
        
        testName, lowerLimit, upperLimit = fileLines.pop(0).split(';')
        if testName not in self.measurements:
            testContainer = dataContainer.DataContainer(testName)
            testContainer.setLimits(lowerLimit, upperLimit)
            self.measurements[testName] = testContainer
            
        for line in fileLines:
            try:
                self._processFileLine(line, testName)
            except ValueError:
                pass
    
    def _processFileLine(self, measuredValue:str, testName:str):
        self.measurements[testName].addData('1', measuredValue)