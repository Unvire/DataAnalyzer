from src.dataProcessorAbstract import AbstractDataProcessor


class GrugliascoDataProcessor(AbstractDataProcessor):
    FILE_EXTENSIONS = ['txt']

    def getLogDateTime(self, fileNameNoExtension: str) -> str:
        _, _, date, time, *_ = fileNameNoExtension.split('][')
        datetimeString = date.replace('-', '') + time.replace('-', '')
        return super().getLogDateTime(datetimeString)

    def processLogFile(self, filePath: str, testTime: str):
        with open(filePath, 'r', encoding='unicode_escape') as file:
            fileLines = file.readlines()[:-3]

        try:
            site = self._getSiteFromHeader(fileLines)
            serialNumber = self._getSerialNumberFromHeader(fileLines)
        except (TypeError, ValueError):
            return

        for line in fileLines:
            try:
                self._processFileLine(line, site, testTime, serialNumber)
            except ValueError:
                pass

    def _getSiteFromHeader(self, fileLines: list[str]) -> str:
        return self._getValueFromFileLine(fileLines, 'test socket index')

    def _getSerialNumberFromHeader(self, fileLines: list[str]) -> str:
        return self._getValueFromFileLine(fileLines, 'uut serial number')

    def _getValueFromFileLine(self, fileLines: list[str], parameterName: str) -> str:
        for line in fileLines:
            if line.lower().startswith(parameterName):
                _, value, *_ = line.split(',')
                return value.strip()
        raise ValueError(f'Missing header parameter: {parameterName}')

    def _processFileLine(self, fileLine: str, site: str, testTime: str, serialNumber: str):
        _, testName, _, _, _, _, _, measuredValue, _, _, lowerLimit, upperLimit, *_ = fileLine.split(',')
        low = float(lowerLimit)
        high = float(upperLimit)
        if not low and not high:
            return
        self._appendScalarRow(testName, site, measuredValue, low, high, testTime, serialNumber)