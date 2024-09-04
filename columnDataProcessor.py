import dataContainer
from abstractDataProcessor import AbstractDataProcessor

class ColumnDataProcessor(AbstractDataProcessor):
    def __init__(self):
        super().__init__()

    def processLogFile(self, filePath:str):
        with open(filePath, 'r', encoding='unicode_escape') as file:
            fileLines = file.readlines()
        
        fileLines = [line.replace('\n', '') for line in fileLines]
        testName, lowerLimit, upperLimit = self._getSiteLimitsFromHeader(fileLines)
        self.createDataContainer(testName, lowerLimit, upperLimit)
            
        for line in fileLines:
            try:
                self._processFileLine(line, testName)
            except ValueError:
                pass
    
    def _processFileLine(self, fileLine:str, testName:str):
        measuredValue, *_ = fileLine.split(';')
        self.measurements[testName].addData('1', measuredValue)
    
    def _getSiteLimitsFromHeader(self, fileLines:list[str]) -> tuple[str, str, str]:
        testName, lowerLimit, upperLimit, *_ = fileLines.pop(0).split(';')
        return testName, lowerLimit, upperLimit