from datetime import datetime
import re

from src.dataProcessorAbstract import AbstractDataProcessor


class FwkDataProcessor(AbstractDataProcessor):
    FILE_EXTENSIONS = ['csv']
    OUTPUT_DATETIME_FORMAT = '%Y/%m/%d %H:%M:%S'

    def processLogFile(self, filePath: str, testTime: str):
        with open(filePath, 'r', encoding='utf-8') as file:
            fileLines = file.readlines()[:-3]

        site = self._getSiteFromHeader(fileLines)
        serialNumber = self._getSerialNumberFromHeader(fileLines)

        for line in fileLines:
            try:
                self._processFileLine(line, site, testTime, serialNumber)
            except ValueError:
                pass

    def _formatDateTime(self, dateStr: str, timeStr: str) -> str:
        parsed = datetime.strptime(f'{dateStr}{timeStr}', '%Y%m%d%H%M%S')
        return parsed.strftime(self.OUTPUT_DATETIME_FORMAT)

    def getLogDateTime(self, fileNameNoExtension: str) -> str:
        fwkNamePattern = r'^\d{8}_\d{6}_BF'
        testStandIpsesNamePattern = r'^.+\d{6}_\d{8}_[Pp|Ff]'
        chineseTeststandNamePattern = r'^\d{8}_\d{6}_'
        chineseTeststandNamePattern2 = r'^UUT\d+_\d{8}_\d{6}_'

        if re.match(fwkNamePattern, fileNameNoExtension):
            date, time, *_ = fileNameNoExtension.split('_')
        elif re.match(testStandIpsesNamePattern, fileNameNoExtension):
            *_, time, date, _ = fileNameNoExtension.split('_')
        elif re.match(chineseTeststandNamePattern, fileNameNoExtension):
            date, time, *_ = fileNameNoExtension.split('_')
        elif re.match(chineseTeststandNamePattern2, fileNameNoExtension):
            _, date, time, *_ = fileNameNoExtension.split('_')
        else:
            raise ValueError(f'Unrecognized FWK filename format: {fileNameNoExtension}')

        return self._formatDateTime(date, time)

    def _getSiteFromHeader(self, fileLines: list[str]) -> str:
        return self._getValueFromFileLine(fileLines, 'test socket index')

    def _getSerialNumberFromHeader(self, fileLines: list[str]) -> str:
        return self._getValueFromFileLine(fileLines, 'uut serial number')

    def _getValueFromFileLine(self, fileLines: list[str], parameterName: str) -> str:
        for line in fileLines:
            if line.lower().startswith(parameterName):
                _, value, *_ = line.split(';')
                return value.strip()
        raise ValueError(f'Missing header parameter: {parameterName}')

    def _processFileLine(self, fileLine: str, site: str, testTime: str, serialNumber: str):
        _, testName, *_, measuredValue, _, lowerLimit, upperLimit, _ = fileLine.split(';')
        
        
        try:
            low = float(lowerLimit)
        except ValueError:
            low = -1e16

        try:
            high = float(upperLimit)
        except ValueError:
            high = 1e16

        if (low == 0 and high == 0) or (low == -1e16 and high == 1e16):
            return
        self._appendScalarRow(testName, site, measuredValue, low, high, testTime, serialNumber)