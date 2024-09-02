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
        testName = f'{testName1} | {testName2}'
        if testName not in self.measurements:
            testContainer = dataContainer.DataContainer(testName)
            testContainer.setLimits(lowerLimit, upperLimit)
            self.measurements[testName] = testContainer
        self.measurements[testName].addData(site, measuredValue)

if __name__ == '__main__':
    import os
    logFolder = r'C:\python programy\2023_07_27 get measurement from logs\Data'
    logs = os.listdir(logFolder)
    numOfLogs = len(logs)
    
    loader = SpeaDataProcessor()
    for i, logfilePath in enumerate(logs):
        logPath = os.path.join(logFolder, logfilePath)
        loader.processLogFile(logPath)
        print(f'{i + 1} | {numOfLogs}')