import re

from src.dataProcessorAbstract import AbstractDataProcessor

class SpeaDataProcessor(AbstractDataProcessor):     
    FILE_EXTENSIONS = ['txt']

    def __init__(self):
        super().__init__()

    def processLogFile(self, filePath:str, testTime:str):
        with open(filePath, 'r', encoding='unicode_escape') as file:
            fileLines = file.readlines()
        
        serialNumber = self._getSerialNumber(fileLines)
        fileLines = fileLines[3:-3]
        
        for line in fileLines:
            try:
                self._processFileLine(line, testTime, serialNumber)
            except ValueError:
                pass
    
    def _getSerialNumber(self, fileLines:list[str]) -> str:
        _, serialNumber, *_ = fileLines[-3].split(';')
        return serialNumber
    
    def getLogDateTime(self, fileNameNoExtension:str) -> str:
        speaNamePattern1 = r'.+_\d{14}$'
        speaNamePattern2 = r'.+_\d{8}_\d{6}$'
        speaNamePattern3 = r'.+_\d{6}_\d{8}$'
        
        if re.match(speaNamePattern1, fileNameNoExtension):
            datetimeString = fileNameNoExtension.split('_')[-1]
            return super().getLogDateTime(datetimeString)
        
        if re.match(speaNamePattern2, fileNameNoExtension):
            date, time = fileNameNoExtension.split('_')[-2:]
            day, month, year = date[:2], date[2:4], date[4:]
            hour, minutes, seconds = time[:2], time[2:4], time[4:]
            datetimeString = f'{year}{month}{day}{hour}{minutes}{seconds}'
            return super().getLogDateTime(datetimeString)    

        if re.match(speaNamePattern3, fileNameNoExtension):
            time, date = fileNameNoExtension.split('_')[-2:]
            year, month, day = date[:4], date[4:6], date[6:]
            hour, minutes, seconds = time[:2], time[2:4], time[4:]
            datetimeString = f'{year}{month}{day}{hour}{minutes}{seconds}'
            return super().getLogDateTime(datetimeString)       
        
        raise ValueError
    
    def _processFileLine(self, fileLine:str, testTime:str, serialNumber:str):
        _, site, testName1, _, _, testName2, _, _, measuredValue, lowerLimit, upperLimit, *_ = fileLine.split(';')
        if 'CXCY' in testName2:
            ledBin, valuesString = testName2.split('(')
            testName = f'{testName1} | {ledBin}'
            
            upcaseValuesString = valuesString.upper()
            valuesString = valuesString.replace('-', '_').replace(',', '.')
            valuesString = re.sub(r'[^0-9._]+', '', valuesString)
            
            if 'CX LIMIT:' in upcaseValuesString and 'CY LIMIT:' in upcaseValuesString:
                # edge case: x_y_CX Limit:x1_x2_x3_x4_CY Limit:y1_y2_y3_y4
                x, y, x1, x2, x3, x4, y1, y2, y3, y4 = valuesString.split('_')
                boundaryXYs = x1, y1, x2, y2, x3, y3, x4, y4
            else:
                # typical case: x_y_x1_y1_x2_y2_x3_y3_x4_y4
                x, y, *boundaryXYs = valuesString.split('_')

            limits = '_'.join(boundaryXYs)
            value = x, y
        else:            
            if float(lowerLimit) == 0.0 and float(upperLimit) == 0.0:
                return
            
            testName = f'{testName1} | {testName2}'
            value = measuredValue
            limits = float(lowerLimit), float(upperLimit)
        self.createDataContainer(testName)
        self.measurements[testName].addData(site, value, limits, testTime, serialNumber)