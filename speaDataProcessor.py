import dataContainer
from abstractDataProcessor import AbstractDataProcessor

class SpeaDataProcessor(AbstractDataProcessor):
    def __init__(self):
        super().__init__()

    def processLogFile(self, filePath:str):
        with open(filePath, 'r', encoding='unicode_escape') as file:
            fileLines = file.readlines()[3:-3]
        
        for line in fileLines:
            try:
                self._processFileLine(line)
            except ValueError:
                pass
    
    def _processFileLine(self, fileLine:str):
        _, site, testName1, _, _, testName2, _, _, measuredValue, lowerLimit, upperLimit, *_ = fileLine.split(';')
        if float(lowerLimit) == 0.0 and float(upperLimit) == 0.0:
            return
        
        testName = f'{testName1} | {testName2}'
        self.createDataContainer(testName, lowerLimit, upperLimit)
        self.measurements[testName].addData(site, measuredValue)