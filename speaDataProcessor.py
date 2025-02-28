from abstractDataProcessor import AbstractDataProcessor

class SpeaDataProcessor(AbstractDataProcessor):
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
            x, y, x0, y0, x1, y1, x2, y2, x3, y3 = valuesString[:-1].split('_')
            boundaryXYs = [(x0, y0), (x1, y1), (x2, y2), (x3, y3)]
            self._processCXCYFileLine(testName, boundaryXYs, site, (x, y), testTime)
        else:
            testName = f'{testName1} | {testName2}'
            self._processMeasurementFileLine(testName, lowerLimit, upperLimit, site, measuredValue, testTime)        
    
    def _processMeasurementFileLine(self, testName:str, lowerLimit:str, upperLimit:str, site:str, measuredValue:str, testTime:str):
        if float(lowerLimit) == 0.0 and float(upperLimit) == 0.0:
            return

        self.createDataContainer(testName, lowerLimit, upperLimit)
        self.measurements[testName].addData(site, (measuredValue, testTime))
    
    def _processCXCYFileLine(self, testName:str, boundaryXYs:list[tuple[str, str]], site:str, xy:tuple[str, str], testTime:str):
        self.createCXCYDataContainer(testName, boundaryXYs)
        self.measurements[testName].addData(site, (xy, testTime))