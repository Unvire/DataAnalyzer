import dataContainer

class FwkDataProcessor:
    def __init__(self):
        self.measurements = {}
    
    def clear(self):
        self.measurements = {}

    def getMeasurements(self) -> dict[str:dataContainer.DataContainer]:
        return self.measurements

    def processLogFile(self, filePath:str):
        with open(filePath, 'r', encoding='unicode_escape') as file:
            fileLines = file.readlines()[:-3]
        
        for line in fileLines:
            if line.startswith('Test Socket Index'):
                _, site, *_ = line.split(';')
                break
        
        for line in fileLines:
            try:
                self._processFileLine(line, site)
            except ValueError:
                pass
    
    def _processFileLine(self, fileLine:str, site:str):
        _, testName, *_, measuredValue, _, lowerLimit, upperLimit, _ = fileLine.split(';')
        
        if  not lowerLimit and not upperLimit:
            return
        
        if testName not in self.measurements:
            testContainer = dataContainer.DataContainer(testName)
            testContainer.setLimits(lowerLimit, upperLimit)
            self.measurements[testName] = testContainer
        self.measurements[testName].addData(site, measuredValue)

if __name__ == '__main__':
    import os
    logFolder = r'C:\Users\kbalcerzak\Documents\nexyM FCT1 logs'
    logs = os.listdir(logFolder)
    numOfLogs = len(logs)
    
    loader = FwkDataProcessor()
    for i, logfilePath in enumerate(logs):
        logPath = os.path.join(logFolder, logfilePath)
        loader.processLogFile(logPath)
        print(f'{i + 1} | {numOfLogs}')