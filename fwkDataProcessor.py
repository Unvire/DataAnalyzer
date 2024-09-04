import dataContainer
from abstractDataProcessor import AbstractDataProcessor

class FwkDataProcessor(AbstractDataProcessor):
    def __init__(self):
        super().__init__()

    def processLogFile(self, filePath:str):
        with open(filePath, 'r', encoding='unicode_escape') as file:
            fileLines = file.readlines()[:-3]
        
        site = self._getSiteFromHeader(fileLines)
        
        for line in fileLines:
            try:
                self._processFileLine(line, site)
            except ValueError:
                pass
    
    def _getSiteFromHeader(self, fileLines:list[str]) -> str:
        for line in fileLines:
            if line.startswith('Test Socket Index'):
                _, site, *_ = line.split(';')
                return site
    
    def _processFileLine(self, fileLine:str, site:str):
        _, testName, *_, measuredValue, _, lowerLimit, upperLimit, _ = fileLine.split(';')
        
        if  not lowerLimit and not upperLimit:
            return
        
        self.createDataContainer(testName, lowerLimit, upperLimit)
        self.measurements[testName].addData(site, measuredValue)