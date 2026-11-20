import abc
from datetime import datetime
from typing import Any


class AbstractDataProcessor(metaclass=abc.ABCMeta):
    FILE_EXTENSIONS: list[str] = []

    def __init__(self):
        self._rawRowsByTest: dict[str, list[dict[str, Any]]] = {}
        self._cxcyTests: set[str] = set()

    def clear(self):
        self._rawRowsByTest = {}
        self._cxcyTests = set()

    def getRawRowsByTest(self) -> dict[str, list[dict[str, Any]]]:
        return self._rawRowsByTest

    def getCxCyTests(self) -> set[str]:
        return self._cxcyTests

    def _appendScalarRow(self, testName:str, site:str, value:float|int|str, lowerLimit:float|int|str, upperLimit:float|int|str,
        testDate:str, serialNumber:str):

        row = {
            'Site': str(site),
            'Value': float(value),
            'LSL': float(lowerLimit),
            'USL': float(upperLimit),
            'TestDate': testDate,
            'SerialNumber': str(serialNumber),
        }
        self._rawRowsByTest.setdefault(testName, []).append(row)

    def _appendCxCyRow(self, testName:str, site:str, cx:float|int|str, cy:float|int|str, boundary:list[tuple[float, float]], 
            testDate:str, serialNumber:str):
        
        row = {
            'Site': str(site),
            'CX': float(cx),
            'CY': float(cy),
            'Boundary': boundary,
            'TestDate': testDate,
            'SerialNumber': str(serialNumber),
        }
        self._cxcyTests.add(testName)
        self._rawRowsByTest.setdefault(testName, []).append(row)

    @abc.abstractmethod
    def processLogFile(self, filePath: str, testDate: str):
        pass

    @abc.abstractmethod
    def getLogDateTime(self, datetimeString: str) -> str:
        pass