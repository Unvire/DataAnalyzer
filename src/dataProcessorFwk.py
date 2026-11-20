import re

from src.dataProcessorAbstract import AbstractDataProcessor


class FwkDataProcessor(AbstractDataProcessor):
    FILE_EXTENSIONS = ['csv']

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

        return super().getLogDateTime(date + time)

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
        low = float(lowerLimit)
        high = float(upperLimit)
        if low == 0 and high == 0:
            return
        self._appendScalarRow(testName, site, measuredValue, low, high, testTime, serialNumber)