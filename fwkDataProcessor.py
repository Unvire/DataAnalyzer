from abstractDataProcessor import AbstractDataProcessor

class FwkDataProcessor(AbstractDataProcessor):
    def __init__(self):
        super().__init__()

    def processLogFile(self, filePath:str, testTime:str):
        with open(filePath, 'r', encoding='unicode_escape') as file:
            fileLines = file.readlines()[:-3]
        
        site = self._getSiteFromHeader(fileLines)
        
        for line in fileLines:
            try:
                self._processFileLine(line, site, testTime)
            except ValueError:
                pass
    
    def _getSiteFromHeader(self, fileLines:list[str]) -> str:
        for line in fileLines:
            if line.startswith('Test Socket Index'):
                _, site, *_ = line.split(';')
                return site.strip()
    
    def _processFileLine(self, fileLine:str, site:str, testTime:str):
        _, testName, *_, measuredValue, _, lowerLimit, upperLimit, _ = fileLine.split(';')
        
        float(lowerLimit); float(upperLimit)
        if float(lowerLimit) == 0 and float(upperLimit) == 0:
            return
        
        self.createDataContainer(testName)
        self.measurements[testName].addData(site, measuredValue, (float(lowerLimit), float(upperLimit)), testTime)