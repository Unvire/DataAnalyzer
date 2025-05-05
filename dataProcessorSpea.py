from dataProcessorAbstract import AbstractDataProcessor

class SpeaDataProcessor(AbstractDataProcessor):     
    FILE_EXTENSIONS = ['txt']

    def __init__(self):
        super().__init__()

    def processLogFile(self, filePath:str, testTime:str):
        with open(filePath, 'r', encoding='unicode_escape') as file:
            fileLines = file.readlines()[3:-3]
        
        for line in fileLines:
            try:
                self._processFileLine(line, testTime)
            except ValueError:
                pass
    
    def _processFileLine(self, fileLine:str, testTime:str):
        _, site, testName1, _, _, testName2, _, _, measuredValue, lowerLimit, upperLimit, *_ = fileLine.split(';')
        if 'CXCY' in testName2:
            ledBin, valuesString = testName2.split('(')
            testName = f'{testName1} | {ledBin}'
            x, y, *boundaryXYs = valuesString[:-1].split('_')
            limits = '_'.join(boundaryXYs)
            value = x, y
        else:            
            if float(lowerLimit) == 0.0 and float(upperLimit) == 0.0:
                return
            
            testName = f'{testName1} | {testName2}'
            value = measuredValue
            limits = float(lowerLimit), float(upperLimit)
        self.createDataContainer(testName)
        self.measurements[testName].addData(site, value, limits, testTime)