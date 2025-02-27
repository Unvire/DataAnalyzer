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
        testName = f'{testName1} | {testName2}'
        if 'CXCY' in testName2:
            #LED_WHITE_15704401_SW57P19D22_CXCY(0.3316_0.3405_0.3196_0.3462_0.3396_0.3616_0.3386_0.3369_0.3221_0.3298)
            _, valuesString = testName2.split('(')
            x, y, x0, y0, x1, y1, x2, y2, x3, y3 = valuesString[:-1].split('_')
            boundaryXYs = [(x0, y0), (x1, y1), (x2, y2), (x3, y3)]
            self._processCXCYFileLine(testName, boundaryXYs, site, (x, y), testTime)
        else:
            self._processMeasurementFileLine(testName, lowerLimit, upperLimit, site, measuredValue, testTime)        
    
    def _processMeasurementFileLine(self, testName:str, lowerLimit:str, upperLimit:str, site:str, measuredValue:str, testTime:str):
        if float(lowerLimit) == 0.0 and float(upperLimit) == 0.0:
            return

        self.createDataContainer(testName, lowerLimit, upperLimit)
        self.measurements[testName].addData(site, (measuredValue, testTime))
    
    def _processCXCYFileLine(self, testName:str, boundaryXYs:list[tuple[str, str]], site:str, xy:tuple[str, str], testTime:str):
        self.createCXCYDataContainer(testName, boundaryXYs)
        self.measurements[testName].addData(site, (xy, testTime))