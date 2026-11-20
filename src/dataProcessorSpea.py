import re

from src.dataProcessorAbstract import AbstractDataProcessor
from src.dataSchemas import parseBoundaryString


class SpeaDataProcessor(AbstractDataProcessor):
    FILE_EXTENSIONS = ['txt']

    def processLogFile(self, filePath: str, testTime: str):
        with open(filePath, 'r', encoding='unicode_escape') as file:
            fileLines = file.readlines()

        if not fileLines:
            return

        serialNumber = self._getSerialNumber(fileLines)
        bodyLines = fileLines[3:-3] if len(fileLines) > 6 else fileLines
        for line in bodyLines:
            try:
                self._processFileLine(line, testTime, serialNumber)
            except ValueError:
                pass

    def _getSerialNumber(self, fileLines: list[str]) -> str:
        if len(fileLines) >= 3:
            parts = fileLines[-3].split(';')
            if len(parts) >= 2 and parts[0].strip().upper() == 'SN':
                return parts[1].strip()
        for line in reversed(fileLines):
            parts = line.split(';')
            if len(parts) >= 2 and parts[0].strip().upper() == 'SN':
                return parts[1].strip()
        return '-'

    def getLogDateTime(self, fileNameNoExtension: str) -> str:
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
            return super().getLogDateTime(f'{year}{month}{day}{hour}{minutes}{seconds}')

        if re.match(speaNamePattern3, fileNameNoExtension):
            time, date = fileNameNoExtension.split('_')[-2:]
            year, month, day = date[:4], date[4:6], date[6:]
            hour, minutes, seconds = time[:2], time[2:4], time[4:]
            return super().getLogDateTime(f'{year}{month}{day}{hour}{minutes}{seconds}')

        raise ValueError(f'Unrecognized SPEA filename format: {fileNameNoExtension}')

    def _processFileLine(self, fileLine: str, testTime: str, serialNumber: str):
        _, site, testName1, _, _, testName2, _, _, measuredValue, lowerLimit, upperLimit, *_ = fileLine.split(';')
        if 'CXCY' in testName2:
            ledBin, valuesString = testName2.split('(')
            testName = f'{testName1} | {ledBin}'

            upcaseValuesString = valuesString.upper()
            cleaned = re.sub(r'[^0-9._]+', '', valuesString.replace('-', '_').replace(',', '.'))

            if 'CX LIMIT:' in upcaseValuesString and 'CY LIMIT:' in upcaseValuesString:
                x, y, x1, x2, x3, x4, y1, y2, y3, y4 = cleaned.split('_')
                boundaryString = '_'.join((x1, y1, x2, y2, x3, y3, x4, y4))
            else:
                x, y, *boundaryXYs = cleaned.split('_')
                boundaryString = '_'.join(boundaryXYs)

            self._appendCxCyRow(testName=testName, site=site, cx=x, cy=y, boundary=parseBoundaryString(boundaryString),
                testDate=testTime, serialNumber=serialNumber)
            
        else:
            low = float(lowerLimit)
            high = float(upperLimit)
            if low == 0.0 and high == 0.0:
                return
            
            testName = f'{testName1} | {testName2}'
            self._appendScalarRow(testName, site, measuredValue, low, high, testTime, serialNumber)