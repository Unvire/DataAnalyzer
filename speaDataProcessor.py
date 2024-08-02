import dataContainer

class SpeaDataProcessor:
    def __init__(self):
        self.measurements = {}
    
    def getMeasurements(self) -> dict[str:dataContainer.DataContainer]:
        return self.measurements

    def processLogFile(self, filePath:str):
        with open(filePath, 'r', encoding='unicode_escape') as file:
            fileLines = file.readlines()[3:-3]
        
        for line in fileLines:
            try:
                self._processFileLine(line)
            except ValueError:
                pass
    
    def _processFileLine(self, fileLine:str):
        _, site, _, _, _, testName, _, _, measuredValue, lowerLimit, upperLimit, *_ = fileLine.split(';')
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