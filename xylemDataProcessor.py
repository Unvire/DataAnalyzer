from abstractDataProcessor import AbstractDataProcessor

class XylemDataProcessor(AbstractDataProcessor):
    def __init__(self):
        super().__init__()

    def processLogFile(self, filePath:str, testTime:str):
        with open(filePath, 'r', encoding='unicode_escape') as file:
            fileLines = file.readlines()[:-3]
        
        siteIndex, site = self._getSiteFromHeader(fileLines)
        
        for line in fileLines[siteIndex + 1:]:
            try:
                self._processFileLine(line, site, testTime)
            except ValueError:
                pass
    
    def _getSiteFromHeader(self, fileLines:list[str]) -> tuple[int, str]:
        for i, line in enumerate(fileLines):
            if line.startswith('Test Socket Index'):
                *_, site = line.split(',')
                return i, site
    
    def _processFileLine(self, fileLine:str, site:str, testTime:str):        
        #Sequence	StepName	Status	Date	Time	Duration	Value	Units	Limit	LimitLow	LimitHigh	ReportText	ErrorCode	ErrorMsg	StepType
        _, testName, _, _, _, _, _, measuredValue, _, _, lowerLimit, upperLimit, *_ = fileLine.split(',')
        
        if  not lowerLimit and not upperLimit:
            return
        
        # throws ValueError when not number
        float(lowerLimit)
        float(upperLimit)
        
        self.createDataContainer(testName, lowerLimit, upperLimit)
        self.measurements[testName].addData(site, (measuredValue, testTime))