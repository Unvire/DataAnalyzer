from workers.dataProcessorAbstract import AbstractDataProcessor

class GrugliascoDataProcessor(AbstractDataProcessor):
    FILE_EXTENSIONS = ['txt']
    
    def __init__(self):
        super().__init__()
    
    def getLogDateTime(self, fileNameNoExtension: str) -> str:
        _, _, date, time, *_ = fileNameNoExtension.split('][')
        datetimeString = date.replace('-', '') + time.replace('-', '')
        return super().getLogDateTime(datetimeString)

    def processLogFile(self, filePath:str, testTime:str):
        with open(filePath, 'r', encoding='unicode_escape') as file:
            fileLines = file.readlines()[:-3]
        
        try:
            site = self._getSiteFromHeader(fileLines)
            serialNumber = self._getSerialNumberFromHeader(fileLines)
        except TypeError:
            return
        
        for line in fileLines:
            try:
                self._processFileLine(line, site, testTime, serialNumber)
            except ValueError:
                pass
    
    def _getSiteFromHeader(self, fileLines:list[str]) -> str:        
        return self._getValueFromFileLine(fileLines, 'test socket index')
    
    def _getSerialNumberFromHeader(self, fileLines:list[str]) -> str:
        return self._getValueFromFileLine(fileLines, 'uut serial number')
    
    def _getValueFromFileLine(self, fileLines:list[str], parameterName:str) -> str:
        for line in fileLines:
            lineLowerCase = line.lower()
            if lineLowerCase.startswith(parameterName):
                _, value, *_ = line.split(',')
                return value.strip()
    
    def _processFileLine(self, fileLine:str, site:str, testTime:str, serialNumber:str):        
        #Sequence	StepName	Status	Date	Time	Duration	Value	Units	Limit	LimitLow	LimitHigh	ReportText	ErrorCode	ErrorMsg	StepType
        _, testName, _, _, _, _, _, measuredValue, _, _, lowerLimit, upperLimit, *_ = fileLine.split(',')
        
        if  not float(lowerLimit) and not float(upperLimit):
            return
        
        self.createDataContainer(testName)
        self.measurements[testName].addData(site, measuredValue, (float(lowerLimit), float(upperLimit)), testTime, serialNumber)