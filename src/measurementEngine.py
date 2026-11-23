import os
from multiprocessing import Pool, cpu_count
from typing import Any

import pandas as pd

from src.dataProcessorAbstract import AbstractDataProcessor
from src.dataProcessorFwk import FwkDataProcessor
from src.dataProcessorGrugliasco import GrugliascoDataProcessor
from src.dataProcessorSpea import SpeaDataProcessor
from src.dataSchemas import CXCY_COLUMNS, SCALAR_COLUMNS


def _processSingleFileWorker(task:tuple[type[AbstractDataProcessor], str, str]) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    processorClass, fullFilePath, formattedTime = task

    processor: AbstractDataProcessor = processorClass()
    processor.processLogFile(fullFilePath, formattedTime)
    rawRows = processor.getRawRowsByTest()
    return rawRows, processor.getCxCyTests(), list(rawRows.keys())


class MeasurementEngine:
    PROCESSORS_DICT: dict[str, type[AbstractDataProcessor]] = {
        'SPEA': SpeaDataProcessor,
        'FWK / Ipses / BEC': FwkDataProcessor,
        'TestStand Grugliasco': GrugliascoDataProcessor
    }

    def __init__(self, numWorkers: int | None = None):
        self.processorClass: type[AbstractDataProcessor] | None = None
        self.numWorkers = numWorkers or max(1, (cpu_count() or 2) - 1)
        self.measurements: dict[str, pd.DataFrame] = {}
        self._rawRowsByTest: dict[str, list[dict[str, Any]]] = {}
        self._cxcyTests: set[str] = set()
        self._masterSequence: list[str] = []

    def setProcessorType(self, loaderType: str):
        if loaderType not in self.PROCESSORS_DICT:
            raise ValueError(f'Unknown processor type: {loaderType}')
        self.processorClass = self.PROCESSORS_DICT[loaderType]

    def clear(self):
        self.measurements = {}
        self._rawRowsByTest = {}
        self._cxcyTests = set()
        self._masterSequence = []

    def getMeasurements(self) -> dict[str, pd.DataFrame]:
        return self.measurements

    def getTestDataFrame(self, testName: str) -> pd.DataFrame | None:
        return self.measurements.get(testName)

    @staticmethod
    def isCxCyDataFrame(df: pd.DataFrame) -> bool:
        return 'CX' in df.columns and 'CY' in df.columns

    def processFolder(self, folderPath:str, isAppendTests:bool = False, isSearchInSubfolders:bool=True, progressCallback=None,
        useMultiprocessing:bool=True):
        
        if self.processorClass is None:
            raise RuntimeError('Processor type has not been set')

        if not isAppendTests:
            self.clear()

        tempProcessor = self.processorClass()
        candidateFiles = self._collectFiles(folderPath, isSearchInSubfolders)
        tasks: list[tuple[type[AbstractDataProcessor], str, str]] = []

        for filePath in candidateFiles:
            fileNameWithExt = os.path.basename(filePath)
            if '.' not in fileNameWithExt:
                continue
            fileNameNoExt, fileExt = fileNameWithExt.rsplit('.', 1)
            if fileExt.lower() not in [ext.lower() for ext in tempProcessor.FILE_EXTENSIONS]:
                continue
            formattedTime = tempProcessor.getLogDateTime(fileNameNoExt)
            tasks.append((self.processorClass, filePath, formattedTime))

        totalTasks = len(tasks)
        if totalTasks == 0:
            self.buildDataFrames()
            if progressCallback:
                progressCallback(100)
            return self.measurements

        if useMultiprocessing and totalTasks > 1:
            with Pool(processes=min(self.numWorkers, totalTasks)) as pool:
                for idx, (rowsByTest, cxcySet, fileOrder) in enumerate(pool.imap(_processSingleFileWorker, tasks, chunksize=16), start=1):
                    self._mergeFileResult(rowsByTest, cxcySet, fileOrder)
                    if progressCallback:
                        progressCallback(int(idx / totalTasks * 100))
        else:
            for idx, task in enumerate(tasks, start=1):
                rowsByTest, cxcySet, fileOrder = _processSingleFileWorker(task)
                self._mergeFileResult(rowsByTest, cxcySet, fileOrder)
                if progressCallback:
                    progressCallback(int(idx / totalTasks * 100))

        self.buildDataFrames()

    def _mergeFileResult(self, rowsByTest:dict[str, list[dict[str, Any]]], cxcySet:set[str], fileOrder:list[str]):
        self._cxcyTests.update(cxcySet)

        if len(fileOrder) > len(self._masterSequence):
            missingFromNew = [t for t in self._masterSequence if t not in fileOrder]
            self._masterSequence = fileOrder + missingFromNew
        else:
            for t in fileOrder:
                if t not in self._masterSequence:
                    self._masterSequence.append(t)

        for testName, rows in rowsByTest.items():
            self._rawRowsByTest.setdefault(testName, []).extend(rows)

    def buildDataFrames(self) -> dict[str, pd.DataFrame]:
        built: dict[str, pd.DataFrame] = {}
        orderedKeys = self._masterSequence if self._masterSequence else list(self._rawRowsByTest.keys())

        for testName in orderedKeys:
            if testName not in self._rawRowsByTest:
                continue
            rows = self._rawRowsByTest[testName]
            if testName in self._cxcyTests:
                df = pd.DataFrame(rows, columns=CXCY_COLUMNS)
                if not df.empty:
                    df['Site'] = df['Site'].astype(str)
                    df['CX'] = pd.to_numeric(df['CX'], errors='coerce')
                    df['CY'] = pd.to_numeric(df['CY'], errors='coerce')
                    df['SerialNumber'] = df['SerialNumber'].astype(str)
            else:
                df = pd.DataFrame(rows, columns=SCALAR_COLUMNS)
                if not df.empty:
                    df['Site'] = df['Site'].astype(str)
                    df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
                    df['LSL'] = pd.to_numeric(df['LSL'], errors='coerce')
                    df['USL'] = pd.to_numeric(df['USL'], errors='coerce')
                    df['SerialNumber'] = df['SerialNumber'].astype(str)
            built[testName] = df

        self.measurements = built
        return self.measurements

    @staticmethod
    def _collectFiles(folderPath: str, isSearchInSubfolders: bool) -> list[str]:
        if not isSearchInSubfolders:
            return [
                os.path.join(folderPath, entry)
                for entry in os.listdir(folderPath)
                if os.path.isfile(os.path.join(folderPath, entry))
            ]

        collected: list[str] = []
        for root, _, files in os.walk(folderPath):
            for fileName in files:
                collected.append(os.path.join(root, fileName))
        return collected