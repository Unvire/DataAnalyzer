import colorsys
from dataclasses import dataclass, field
import math
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.measurementEngine import MeasurementEngine
from src.processCalculator import ProcessParameterCalculator
from src.siFormatter import formatAxisTitle, formatSiValue, getSiScale, isSentinelLimit


def naturalSortKey(text: str) -> list[int | str]:
    parts = re.split(r'(\d+)', str(text))
    return [int(p) if p.isdigit() else p.lower() for p in parts]


@dataclass
class PivotMatrixResult:
    isCxCy: bool = False
    metricName: str = ''
    minSamples: int = 1
    rowLabels: list[str] = field(default_factory=list)
    colLabels: list[str] = field(default_factory=list)
    shortColLabels: list[str] = field(default_factory=list)
    zMatrix: np.ndarray = field(default_factory=lambda: np.empty((0, 0), dtype=float))
    countMatrix: np.ndarray = field(default_factory=lambda: np.empty((0, 0), dtype=int))
    failMatrix: np.ndarray = field(default_factory=lambda: np.empty((0, 0), dtype=int))
    auxMeanMatrix: np.ndarray = field(default_factory=lambda: np.empty((0, 0), dtype=float))
    rowSummary: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=float))
    colSummary: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=float))
    overallSummary: float = float('nan')
    pivotDf: pd.DataFrame = field(default_factory=pd.DataFrame)
    unitPrefix: str = ''
    scaleFactor: float = 1.0
    warningMessage: str = ''


class PivotAnalyzer:
    BG_COLOR = '#1e1f22'
    PLOT_BG_COLOR = '#26282e'
    GRID_COLOR = '#35373c'
    TEXT_COLOR = '#dfe1e5'
    MUTED_TEXT_COLOR = '#9da0a8'
    LSL_COLOR = '#ef5350'
    USL_COLOR = '#ffa726'

    SITE_PALETTE = [
        '#4c8dff',
        '#26c6da',
        '#ab47bc',
        '#ffca28',
        '#ec407a',
        '#66bb6a',
        '#ff7043',
        '#8d6e63',
    ]

    SCALAR_METRICS = [
        'Dev. vs Group (% tol.)',
        'Dev. vs Group (Z-score)',
        'Centering Offset (%)',
        'Mean',
        'Sigma',
        'Ppk',
        'Yield (%)',
        'Fails',
    ]

    CXCY_METRICS = [
        'Dist. from Bin Center',
        'CX Dev. vs Group',
        'CY Dev. vs Group',
        'CX Mean',
        'CY Mean',
        'Yield (%)',
        'Fails',
    ]

    def __init__(self, calculator:ProcessParameterCalculator|None=None):
        self._calculator = calculator or ProcessParameterCalculator()


    # ------------------------------------------------------------------
    # Matrix Calculation (Site × Test)
    # ------------------------------------------------------------------
    def analyzeMatrix(self, measurements:dict[str, pd.DataFrame], selectedTests:list[str], metric:str='', limitsMode:str='All',
            minSamples: int = 1) -> PivotMatrixResult:
        
        minSamples = max(1, int(minSamples))
        validTests = [
            t for t in selectedTests
            if t in measurements and measurements[t] is not None and not measurements[t].empty
        ]
        if not validTests:
            return PivotMatrixResult(
                minSamples=minSamples,
                warningMessage='Select at least one test from the left panel to build the matrix.',
            )

        cxcyFlags = [MeasurementEngine.isCxCyDataFrame(measurements[t]) for t in validTests]
        if any(cxcyFlags) and not all(cxcyFlags):
            return PivotMatrixResult(
                minSamples=minSamples,
                warningMessage=(
                    'Mixed Scalar and CxCy tests selected.\n'
                    'Filter by Type (Scalar or CxCy) or uncheck one of the groups.'
                ),
            )

        isCxCy = all(cxcyFlags)
        defaultMetric = self.CXCY_METRICS[0] if isCxCy else self.SCALAR_METRICS[0]
        if metric not in (self.CXCY_METRICS if isCxCy else self.SCALAR_METRICS):
            metric = defaultMetric

        if isCxCy:
            return self._analyzeCxCyMatrix(measurements=measurements, testNames=validTests, metric=metric, limitsMode=limitsMode, 
                minSamples=minSamples)

        return self._analyzeScalarMatrix(measurements=measurements, testNames=validTests, metric=metric, limitsMode=limitsMode,
            minSamples=minSamples)

    @staticmethod
    def _collectSiteRows(measurements:dict[str, pd.DataFrame], testNames:list[str]) -> tuple[list[str], dict[str, np.ndarray]]:
        allSites: set[str] = set()
        perTest: dict[str, np.ndarray] = {}
        for t in testNames:
            arr = measurements[t]['Site'].astype(str).to_numpy()
            perTest[t] = arr
            allSites.update(np.unique(arr).tolist())
        return sorted(allSites, key=naturalSortKey), perTest

    def _analyzeScalarMatrix(self, measurements:dict[str, pd.DataFrame], testNames:list[str], metric:str, limitsMode:str,
            minSamples:int) -> PivotMatrixResult:
        
        rowLabels, perTestRows = self._collectSiteRows(measurements, testNames)
        nRows = len(rowLabels)
        nCols = len(testNames)
        if nRows == 0 or nCols == 0:
            return PivotMatrixResult(metricName=metric, minSamples=minSamples, warningMessage='No matching sites found.')

        rowIdxMap = {label: i for i, label in enumerate(rowLabels)}

        meanMatrix = np.full((nRows, nCols), np.nan, dtype=float)
        sigmaMatrix = np.full((nRows, nCols), np.nan, dtype=float)
        ppkMatrix = np.full((nRows, nCols), np.nan, dtype=float)
        yieldMatrix = np.full((nRows, nCols), np.nan, dtype=float)
        centeringMatrix = np.full((nRows, nCols), np.nan, dtype=float)
        normPosMatrix = np.full((nRows, nCols), np.nan, dtype=float)
        countMatrix = np.zeros((nRows, nCols), dtype=int)
        failMatrix = np.zeros((nRows, nCols), dtype=int)

        colMean = np.full(nCols, np.nan, dtype=float)
        colSigma = np.full(nCols, np.nan, dtype=float)
        colPpk = np.full(nCols, np.nan, dtype=float)
        colYield = np.full(nCols, np.nan, dtype=float)
        colCentering = np.full(nCols, np.nan, dtype=float)
        colNormPos = np.full(nCols, np.nan, dtype=float)
        colFails = np.full(nCols, np.nan, dtype=float)

        acceptedSampleValues: list[np.ndarray] = []
        fallbackSampleValues: list[np.ndarray] = []
        refLsls: list[float] = []
        refUsls: list[float] = []

        for c, testName in enumerate(testNames):
            df = measurements[testName]
            fullMetrics, fullFailMask = self._calculator.calculateWithFailMask(df, limitsMode=limitsMode, includeShapeStats=False)

            lsl = fullMetrics.lsl
            usl = fullMetrics.usl
            hasTwoSided = lsl is not None and usl is not None and usl > lsl
            tolSpan = (usl - lsl) if hasTwoSided else None
            midpoint = (0.5 * (lsl + usl)) if hasTwoSided else None

            rawVals = df['Value'].to_numpy(dtype=float)
            finiteMask = np.isfinite(rawVals)
            if np.any(finiteMask):
                fallbackSampleValues.append(rawVals[finiteMask])

            rowArr = perTestRows[testName]
            acceptedSites: list[str] = []

            for rLabel, rIdx in rowIdxMap.items():
                cellMask = (rowArr == rLabel) & finiteMask
                nCell = int(np.sum(cellMask))
                if nCell == 0:
                    continue

                cellFails = int(np.sum(fullFailMask[cellMask]))
                countMatrix[rIdx, c] = nCell
                failMatrix[rIdx, c] = cellFails

                if nCell < minSamples:
                    continue

                acceptedSites.append(rLabel)
                cellVals = rawVals[cellMask]
                acceptedSampleValues.append(cellVals)

                cMean = float(np.mean(cellVals))
                cSigma = float(np.std(cellVals, ddof=1)) if nCell > 1 else np.nan

                meanMatrix[rIdx, c] = cMean
                sigmaMatrix[rIdx, c] = cSigma

                if fullMetrics.yieldPct is not None:
                    yieldMatrix[rIdx, c] = ((nCell - cellFails) / nCell) * 100.0

                if np.isfinite(cSigma) and cSigma > 0.0:
                    _, cPpk = self._calculator._computeCapabilityIndices(cMean, cSigma, lsl, usl)
                    if cPpk is not None:
                        ppkMatrix[rIdx, c] = cPpk

                if hasTwoSided and tolSpan is not None and midpoint is not None:
                    centeringMatrix[rIdx, c] = ((cMean - midpoint) / (0.5 * tolSpan)) * 100.0
                    normPosMatrix[rIdx, c] = ((cMean - midpoint) / tolSpan) * 100.0

            if not acceptedSites:
                continue

            if len(acceptedSites) == len(rowIdxMap) or minSamples <= 1:
                colMetrics = fullMetrics
            else:
                acceptedRowMask = np.isin(rowArr, acceptedSites)
                colMetrics = self._calculator.calculate(df[acceptedRowMask], limitsMode=limitsMode, includeShapeStats=False)

            colMean[c] = colMetrics.mean if colMetrics.mean is not None else np.nan
            colSigma[c] = colMetrics.sigmaOverall if colMetrics.sigmaOverall is not None else np.nan
            colPpk[c] = colMetrics.ppk if colMetrics.ppk is not None else np.nan
            colYield[c] = colMetrics.yieldPct if colMetrics.yieldPct is not None else np.nan
            colCentering[c] = colMetrics.centeringOffsetPct if colMetrics.centeringOffsetPct is not None else np.nan
            colFails[c] = float(colMetrics.failTotal)

            if hasTwoSided and tolSpan is not None and midpoint is not None and colMetrics.mean is not None:
                colNormPos[c] = ((colMetrics.mean - midpoint) / tolSpan) * 100.0
                refLsls.append(lsl)
                refUsls.append(usl)

        samplePool = acceptedSampleValues if acceptedSampleValues else fallbackSampleValues
        prefix, scaleFactor = '', 1.0
        if samplePool:
            combined = np.concatenate(samplePool)
            lslHint = float(np.median(refLsls)) if refLsls else None
            uslHint = float(np.median(refUsls)) if refUsls else None
            prefix, scaleFactor = getSiScale(combined, lslHint, uslHint)

        acceptedWeights = np.where(countMatrix >= minSamples, countMatrix, 0).astype(float)
        colWeights = np.sum(acceptedWeights, axis=0)

        if metric == 'Dev. vs Group (% tol.)':
            if np.any(np.isfinite(normPosMatrix) & (acceptedWeights > 0)):
                groupMedPos = self._weightedMedian(normPosMatrix, acceptedWeights)
                zMatrix = normPosMatrix - groupMedPos
                colSummary = colNormPos - groupMedPos

            else:
                zMatrix, colSummary = self._computeWeightedZScore(meanMatrix, colMean, acceptedWeights)

            rowSummary = self._weightedNanMean(zMatrix, acceptedWeights, axis=1)
            overallSummary = self._weightedNanMeanScalar(zMatrix, acceptedWeights)

        elif metric == 'Dev. vs Group (Z-score)':
            zMatrix, colSummary = self._computeWeightedZScore(meanMatrix, colMean, acceptedWeights)
            rowSummary = self._weightedNanMean(zMatrix, acceptedWeights, axis=1)
            overallSummary = self._weightedNanMeanScalar(zMatrix, acceptedWeights)

        elif metric == 'Centering Offset (%)':
            zMatrix = centeringMatrix
            colSummary = colCentering
            rowSummary = self._weightedNanMean(zMatrix, acceptedWeights, axis=1)
            overallSummary = self._weightedNanMeanScalar(colCentering, colWeights)

        elif metric == 'Mean':
            zMatrix = meanMatrix * scaleFactor
            colSummary = colMean * scaleFactor
            rowSummary = self._weightedNanMean(zMatrix, acceptedWeights, axis=1)
            overallSummary = self._weightedNanMeanScalar(colSummary, colWeights)

        elif metric == 'Sigma':
            zMatrix = sigmaMatrix * scaleFactor
            colSummary = colSigma * scaleFactor
            rowSummary = self._weightedNanMean(zMatrix, acceptedWeights, axis=1)
            overallSummary = self._weightedNanMeanScalar(colSummary, colWeights)

        elif metric == 'Ppk':
            zMatrix = ppkMatrix
            colSummary = colPpk
            rowSummary = self._nanMinAxis(zMatrix, axis=1)
            overallSummary = float(np.nanmin(colPpk)) if np.any(np.isfinite(colPpk)) else float('nan')

        elif metric == 'Yield (%)':
            zMatrix = yieldMatrix
            colSummary = colYield
            validYieldMask = np.isfinite(yieldMatrix) & (acceptedWeights > 0)
            rowCounts = np.sum(np.where(validYieldMask, countMatrix, 0), axis=1)
            rowFails = np.sum(np.where(validYieldMask, failMatrix, 0), axis=1)
            rowSummary = np.where(rowCounts > 0, ((rowCounts - rowFails) / np.maximum(rowCounts, 1)) * 100.0, np.nan)
            totalCount = int(np.sum(rowCounts))
            totalFail = int(np.sum(rowFails))
            overallSummary = ((totalCount - totalFail) / totalCount) * 100.0 if totalCount > 0 else float('nan')

        else:  # 'Fails'
            zMatrix = np.where(acceptedWeights > 0, failMatrix.astype(float), np.nan)
            colSummary = colFails
            rowHasAccepted = np.sum(acceptedWeights > 0, axis=1) > 0
            rowFailSums = np.sum(np.where(acceptedWeights > 0, failMatrix, 0), axis=1).astype(float)
            rowSummary = np.where(rowHasAccepted, rowFailSums, np.nan)
            overallSummary = float(np.nansum(colFails)) if np.any(np.isfinite(colFails)) else float('nan')

        shortCols = self._makeUniqueShortLabels(testNames)
        pivotDf = self._buildPivotDataFrame(metric=metric, rowLabels=rowLabels, colLabels=testNames, zMatrix=zMatrix,
            rowSummary=rowSummary, colSummary=colSummary, overallSummary=overallSummary)

        return PivotMatrixResult(
            isCxCy=False,
            metricName=metric,
            minSamples=minSamples,
            rowLabels=rowLabels,
            colLabels=testNames,
            shortColLabels=shortCols,
            zMatrix=zMatrix,
            countMatrix=countMatrix,
            failMatrix=failMatrix,
            auxMeanMatrix=meanMatrix,
            rowSummary=rowSummary,
            colSummary=colSummary,
            overallSummary=overallSummary,
            pivotDf=pivotDf,
            unitPrefix=prefix,
            scaleFactor=scaleFactor,
        )

    def _analyzeCxCyMatrix(self, measurements:dict[str, pd.DataFrame], testNames:list[str], metric:str, limitsMode:str,
            minSamples:int) -> PivotMatrixResult:
        
        rowLabels, perTestRows = self._collectSiteRows(measurements, testNames)
        nRows = len(rowLabels)
        nCols = len(testNames)
        if nRows == 0 or nCols == 0:
            return PivotMatrixResult(isCxCy=True, metricName=metric, minSamples=minSamples, warningMessage='No matching sites found.')

        rowIdxMap = {label: i for i, label in enumerate(rowLabels)}

        cxMeanMatrix = np.full((nRows, nCols), np.nan, dtype=float)
        cyMeanMatrix = np.full((nRows, nCols), np.nan, dtype=float)
        distMatrix = np.full((nRows, nCols), np.nan, dtype=float)
        yieldMatrix = np.full((nRows, nCols), np.nan, dtype=float)
        countMatrix = np.zeros((nRows, nCols), dtype=int)
        failMatrix = np.zeros((nRows, nCols), dtype=int)

        colCxMean = np.full(nCols, np.nan, dtype=float)
        colCyMean = np.full(nCols, np.nan, dtype=float)
        colDist = np.full(nCols, np.nan, dtype=float)
        colYield = np.full(nCols, np.nan, dtype=float)
        colFails = np.full(nCols, np.nan, dtype=float)

        for c, testName in enumerate(testNames):
            df = measurements[testName]
            fullMetrics, fullFailMask = self._calculator.calculateWithFailMask(df, limitsMode=limitsMode, includeShapeStats=False)

            centroid = self._getActivePolygonCentroid(df, limitsMode)
            cxArr = df['CX'].to_numpy(dtype=float)
            cyArr = df['CY'].to_numpy(dtype=float)
            finiteMask = np.isfinite(cxArr) & np.isfinite(cyArr)

            rowArr = perTestRows[testName]
            acceptedSites: list[str] = []

            for rLabel, rIdx in rowIdxMap.items():
                cellMask = (rowArr == rLabel) & finiteMask
                nCell = int(np.sum(cellMask))
                if nCell == 0:
                    continue

                cellFails = int(np.sum(fullFailMask[cellMask]))
                countMatrix[rIdx, c] = nCell
                failMatrix[rIdx, c] = cellFails

                if nCell < minSamples:
                    continue

                acceptedSites.append(rLabel)
                cCx = float(np.mean(cxArr[cellMask]))
                cCy = float(np.mean(cyArr[cellMask]))

                cxMeanMatrix[rIdx, c] = cCx
                cyMeanMatrix[rIdx, c] = cCy

                if fullMetrics.yieldPct is not None:
                    yieldMatrix[rIdx, c] = ((nCell - cellFails) / nCell) * 100.0

                if centroid is not None:
                    distMatrix[rIdx, c] = math.hypot(cCx - centroid[0], cCy - centroid[1])

            if not acceptedSites:
                continue

            if len(acceptedSites) == len(rowIdxMap) or minSamples <= 1:
                colMetrics = fullMetrics
            else:
                acceptedRowMask = np.isin(rowArr, acceptedSites)
                colMetrics = self._calculator.calculate(df[acceptedRowMask], limitsMode=limitsMode, includeShapeStats=False)

            colCxMean[c] = colMetrics.cxMean if colMetrics.cxMean is not None else np.nan
            colCyMean[c] = colMetrics.cyMean if colMetrics.cyMean is not None else np.nan
            colYield[c] = colMetrics.yieldPct if colMetrics.yieldPct is not None else np.nan
            colFails[c] = float(colMetrics.failTotal)

            if centroid is not None and np.isfinite(colCxMean[c]) and np.isfinite(colCyMean[c]):
                colDist[c] = math.hypot(colCxMean[c] - centroid[0], colCyMean[c] - centroid[1])

        acceptedWeights = np.where(countMatrix >= minSamples, countMatrix, 0).astype(float)
        colWeights = np.sum(acceptedWeights, axis=0)

        if metric == 'Dist. from Bin Center':
            zMatrix = distMatrix
            colSummary = colDist
            rowSummary = self._weightedNanMean(zMatrix, acceptedWeights, axis=1)
            overallSummary = self._weightedNanMeanScalar(colDist, colWeights)

        elif metric == 'CX Dev. vs Group':
            medCx = self._weightedMedian(cxMeanMatrix, acceptedWeights)
            zMatrix = cxMeanMatrix - medCx
            colSummary = colCxMean - medCx
            rowSummary = self._weightedNanMean(zMatrix, acceptedWeights, axis=1)
            overallSummary = self._weightedNanMeanScalar(zMatrix, acceptedWeights)

        elif metric == 'CY Dev. vs Group':
            medCy = self._weightedMedian(cyMeanMatrix, acceptedWeights)
            zMatrix = cyMeanMatrix - medCy
            colSummary = colCyMean - medCy
            rowSummary = self._weightedNanMean(zMatrix, acceptedWeights, axis=1)
            overallSummary = self._weightedNanMeanScalar(zMatrix, acceptedWeights)

        elif metric == 'CX Mean':
            zMatrix = cxMeanMatrix
            colSummary = colCxMean
            rowSummary = self._weightedNanMean(zMatrix, acceptedWeights, axis=1)
            overallSummary = self._weightedNanMeanScalar(colCxMean, colWeights)

        elif metric == 'CY Mean':
            zMatrix = cyMeanMatrix
            colSummary = colCyMean
            rowSummary = self._weightedNanMean(zMatrix, acceptedWeights, axis=1)
            overallSummary = self._weightedNanMeanScalar(colCyMean, colWeights)

        elif metric == 'Yield (%)':
            zMatrix = yieldMatrix
            colSummary = colYield
            validYieldMask = np.isfinite(yieldMatrix) & (acceptedWeights > 0)
            rowCounts = np.sum(np.where(validYieldMask, countMatrix, 0), axis=1)
            rowFails = np.sum(np.where(validYieldMask, failMatrix, 0), axis=1)
            rowSummary = np.where(rowCounts > 0, ((rowCounts - rowFails) / np.maximum(rowCounts, 1)) * 100.0, np.nan)
            totalCount = int(np.sum(rowCounts))
            totalFail = int(np.sum(rowFails))
            overallSummary = ((totalCount - totalFail) / totalCount) * 100.0 if totalCount > 0 else float('nan')

        else:  # 'Fails'
            zMatrix = np.where(acceptedWeights > 0, failMatrix.astype(float), np.nan)
            colSummary = colFails
            rowHasAccepted = np.sum(acceptedWeights > 0, axis=1) > 0
            rowFailSums = np.sum(np.where(acceptedWeights > 0, failMatrix, 0), axis=1).astype(float)
            rowSummary = np.where(rowHasAccepted, rowFailSums, np.nan)
            overallSummary = float(np.nansum(colFails)) if np.any(np.isfinite(colFails)) else float('nan')

        shortCols = self._makeUniqueShortLabels(testNames)
        pivotDf = self._buildPivotDataFrame(metric=metric, rowLabels=rowLabels, colLabels=testNames, zMatrix=zMatrix, rowSummary=rowSummary,
            colSummary=colSummary, overallSummary=overallSummary)

        return PivotMatrixResult(
            isCxCy=True,
            metricName=metric,
            minSamples=minSamples,
            rowLabels=rowLabels,
            colLabels=testNames,
            shortColLabels=shortCols,
            zMatrix=zMatrix,
            countMatrix=countMatrix,
            failMatrix=failMatrix,
            auxMeanMatrix=distMatrix,
            rowSummary=rowSummary,
            colSummary=colSummary,
            overallSummary=overallSummary,
            pivotDf=pivotDf,
        )


    # ------------------------------------------------------------------
    # Figures: Heatmap & Overlay Comparison
    # ------------------------------------------------------------------
    def createHeatmapFigure(self, result:PivotMatrixResult) -> go.Figure:
        if result.warningMessage:
            return self._createEmptyFigure(result.warningMessage)

        nRows, nCols = result.zMatrix.shape
        if nRows == 0 or nCols == 0:
            return self._createEmptyFigure('No matrix data available.')

        metric = result.metricName
        unitSuffix = f' [{result.unitPrefix}]' if (metric in ('Mean', 'Sigma') and result.unitPrefix) else ''
        yLabels = [f'Site {r}' for r in result.rowLabels]

        maxCellN = int(np.max(result.countMatrix)) if result.countMatrix.size > 0 else 0
        lowNThreshold = 10 if maxCellN >= 20 else 0

        showCellText = (nRows * nCols) <= 220
        showSecondLineN = (nRows * nCols) <= 120
        textMatrix: list[list[str]] = []
        hoverMatrix: list[list[str]] = []

        for r in range(nRows):
            tRow: list[str] = []
            hRow: list[str] = []
            for c in range(nCols):
                val = result.zMatrix[r, c]
                cnt = int(result.countMatrix[r, c])
                fls = int(result.failMatrix[r, c])

                if cnt == 0:
                    tRow.append('')
                    hRow.append(f'<b>{result.colLabels[c]}</b><br>{yLabels[r]}<br>No data')
                    continue

                if cnt < result.minSamples:
                    tRow.append(
                        f'<span style="color:#8b8f99;font-size:10px">n={cnt:,} (&lt;{result.minSamples})</span>'
                        if showCellText else ''
                    )
                    hRow.append(
                        f'<b>{result.colLabels[c]}</b><br>{yLabels[r]}<br>'
                        f'Masked by Min n &ge; {result.minSamples} (actual n={cnt:,})<br>'
                        f'Fails: {fls:,}'
                    )
                    continue

                if not np.isfinite(val):
                    tRow.append(
                        f'<span style="color:#8b8f99;font-size:10px">— (n={cnt:,})</span>'
                        if showCellText else ''
                    )
                    hRow.append(
                        f'<b>{result.colLabels[c]}</b><br>{yLabels[r]}<br>'
                        f'{metric}: — (insufficient samples)<br>'
                        f'Samples: {cnt:,}  |  Fails: {fls:,}'
                    )
                    continue

                formatted = self.formatMetricValue(val, metric, result.unitPrefix)
                isLowN = lowNThreshold > 0 and cnt < lowNThreshold
                warnPrefix = '⚠ ' if isLowN else ''

                if showCellText:
                    if showSecondLineN:
                        tRow.append(
                            f'{formatted}<br>'
                            f'<span style="font-size:9px;color:rgba(255,255,255,0.75)">{warnPrefix}n={cnt:,}</span>'
                        )
                    else:
                        tRow.append(f'{warnPrefix}{formatted}')
                else:
                    tRow.append('')

                extraMean = ''
                if not result.isCxCy and metric not in ('Mean', 'Sigma') and np.isfinite(result.auxMeanMatrix[r, c]):
                    extraMean = f'<br>Mean: {formatSiValue(float(result.auxMeanMatrix[r, c]), precision=4)}'

                lowNNote = '  <b>(⚠ low sample size)</b>' if isLowN else ''
                hRow.append(
                    f'<b>{result.colLabels[c]}</b><br>'
                    f'{yLabels[r]}<br>'
                    f'{metric}{unitSuffix}: <b>{formatted}</b>'
                    f'{extraMean}<br>'
                    f'Samples: {cnt:,}{lowNNote}  |  Fails: {fls:,}'
                )
            textMatrix.append(tRow)
            hoverMatrix.append(hRow)

        colorscale, zmin, zmax, zmid = self._resolveHeatmapColorScale(result.zMatrix, metric)

        heatmapKwargs = dict(
            z=result.zMatrix,
            x=result.shortColLabels,
            y=yLabels,
            text=textMatrix if showCellText else None,
            texttemplate='%{text}' if showCellText else None,
            textfont=dict(size=10, color='#ffffff'),
            hovertext=hoverMatrix,
            hoverinfo='text',
            colorscale=colorscale,
            xgap=2,
            ygap=2,
            colorbar=dict(
                title=dict(text=f'{metric}{unitSuffix}', font=dict(size=11, color=self.TEXT_COLOR)),
                tickfont=dict(color=self.TEXT_COLOR),
            ),
        )
        if zmin is not None:
            heatmapKwargs['zmin'] = zmin
        if zmax is not None:
            heatmapKwargs['zmax'] = zmax
        if zmid is not None:
            heatmapKwargs['zmid'] = zmid

        minNote = f'  [Min n ≥ {result.minSamples}]' if result.minSamples > 1 else ''
        fig = go.Figure(data=go.Heatmap(**heatmapKwargs))
        fig.update_layout(
            separators='. ',
            title=dict(
                text=f'Pivot Heatmap (Site × Test) — {metric}{unitSuffix}{minNote}',
                x=0.02,
                y=0.96,
                font=dict(size=14, color=self.TEXT_COLOR),
            ),
            paper_bgcolor=self.BG_COLOR,
            plot_bgcolor=self.PLOT_BG_COLOR,
            font=dict(family='Segoe UI, Arial, sans-serif', size=11, color=self.TEXT_COLOR),
            margin=dict(l=80, r=30, t=58, b=105),
            xaxis=dict(tickangle=-35, side='bottom', automargin=True),
            yaxis=dict(autorange='reversed', automargin=True),
        )
        return fig

    def createOverlayFigure(self, measurements:dict[str, pd.DataFrame], selectedTests:list[str], limitsMode:str='All',
            colorBy:str='Test (Position)') -> go.Figure:
        
        validTests = [
            t for t in selectedTests
            if t in measurements and measurements[t] is not None and not measurements[t].empty
        ]
        if not validTests:
            return self._createEmptyFigure('Select at least one test to display Overlay Comparison.')

        cxcyFlags = [MeasurementEngine.isCxCyDataFrame(measurements[t]) for t in validTests]
        if any(cxcyFlags) and not all(cxcyFlags):
            return self._createEmptyFigure(
                'Mixed Scalar and CxCy tests selected.\n'
                'Filter by Type (Scalar or CxCy) or uncheck one of the groups.'
            )

        if all(cxcyFlags):
            return self._createCxCyOverlayFigure(measurements, validTests, limitsMode=limitsMode, colorBy=colorBy)

        return self._createScalarOverlayFigure(measurements, validTests, limitsMode=limitsMode)

    def _createScalarOverlayFigure(self, measurements:dict[str, pd.DataFrame], testNames:list[str], limitsMode:str) -> go.Figure:
        allVals: list[np.ndarray] = []
        lsls: list[float] = []
        usls: list[float] = []

        for t in testNames:
            df = measurements[t]
            vals = df['Value'].to_numpy(dtype=float)
            finite = vals[np.isfinite(vals)]
            if finite.size > 0:
                allVals.append(finite)
            nonZero = np.abs(finite[finite != 0.0])
            dataRef = float(np.median(nonZero)) if nonZero.size > 0 else None
            lsl, usl = ProcessParameterCalculator._resolveScalarLimits(df, limitsMode)
            if lsl is not None and not isSentinelLimit(lsl, dataRef):
                lsls.append(lsl)
            if usl is not None and not isSentinelLimit(usl, dataRef):
                usls.append(usl)

        if not allVals:
            return self._createEmptyFigure('No numeric values available for selected tests.')

        combined = np.concatenate(allVals)
        lslHint = float(np.median(lsls)) if lsls else None
        uslHint = float(np.median(usls)) if usls else None
        prefix, scaleFactor = getSiScale(combined, lslHint, uslHint)
        shortLabels = self._makeUniqueShortLabels(testNames)

        fig = go.Figure()
        for idx, (tName, shortLbl) in enumerate(zip(testNames, shortLabels)):
            df = measurements[tName]
            vals = df['Value'].to_numpy(dtype=float)
            finiteScaled = vals[np.isfinite(vals)] * scaleFactor
            fig.add_trace(
                go.Box(
                    y=finiteScaled,
                    name=f'{shortLbl} (n={len(finiteScaled):,})',
                    marker_color=self._getColor(idx),
                    boxmean='sd',
                    boxpoints='outliers',
                )
            )

        if len(lsls) == len(testNames) and np.allclose(lsls, lsls[0], rtol=1e-6, atol=1e-12):
            lslScaled = lsls[0] * scaleFactor
            fig.add_hline(y=lslScaled, line_dash='dash', line_color=self.LSL_COLOR, line_width=1.8,
                annotation_text=f'Shared LSL ({lslScaled:.4g})', annotation_position='bottom right',
                annotation_font_color=self.LSL_COLOR)
            
        if len(usls) == len(testNames) and np.allclose(usls, usls[0], rtol=1e-6, atol=1e-12):
            uslScaled = usls[0] * scaleFactor
            fig.add_hline(y=uslScaled, line_dash='dash', line_color=self.USL_COLOR, line_width=1.8,
                annotation_text=f'Shared USL ({uslScaled:.4g})', annotation_position='top right',
                annotation_font_color=self.USL_COLOR)

        fig.update_layout(
            separators='. ',
            title=dict(
                text=f'Multi-Test Distribution Comparison ({len(testNames)} tests)',
                x=0.02,
                y=0.96,
                font=dict(size=14, color=self.TEXT_COLOR),
            ),
            paper_bgcolor=self.BG_COLOR,
            plot_bgcolor=self.PLOT_BG_COLOR,
            font=dict(family='Segoe UI, Arial, sans-serif', size=11, color=self.TEXT_COLOR),
            margin=dict(l=65, r=25, t=60, b=115),
            showlegend=False,
            xaxis=dict(tickangle=-35, gridcolor=self.GRID_COLOR, automargin=True),
            yaxis=dict(
                title=dict(text=formatAxisTitle('Measured Value', prefix), standoff=10),
                gridcolor=self.GRID_COLOR,
                zerolinecolor=self.GRID_COLOR,
                exponentformat='none',
                separatethousands=True,
                automargin=True,
            ),
        )
        return fig

    def _createCxCyOverlayFigure(self, measurements:dict[str, pd.DataFrame], testNames:list[str], limitsMode:str, colorBy:str) -> go.Figure:
        fig = go.Figure()
        shortLabels = self._makeUniqueShortLabels(testNames)

        if colorBy.lower().startswith('site'):
            siteBuckets: dict[str, list[pd.DataFrame]] = {}
            for tName in testNames:
                df = measurements[tName].copy()
                df['_TestName'] = tName
                for site, sub in df.groupby(df['Site'].astype(str), sort=False):
                    siteBuckets.setdefault(site, []).append(sub)

            for idx, site in enumerate(sorted(siteBuckets.keys(), key=naturalSortKey)):
                merged = pd.concat(siteBuckets[site], ignore_index=True)
                customData = np.column_stack((
                    merged['_TestName'].astype(str).to_numpy(),
                    merged['SerialNumber'].astype(str).to_numpy(),
                    merged['TestDate'].astype(str).to_numpy(),
                ))
                fig.add_trace(
                    go.Scattergl(
                        x=merged['CX'].to_numpy(dtype=float),
                        y=merged['CY'].to_numpy(dtype=float),
                        mode='markers',
                        name=f'Site {site} ({len(merged):,})',
                        marker=dict(size=5, color=self._getColor(idx), opacity=0.75),
                        customdata=customData,
                        hovertemplate=(
                            f'<b>Site {site}</b><br>'
                            'Test: %{customdata[0]}<br>'
                            'CX: %{x:.5f}  |  CY: %{y:.5f}<br>'
                            'SN: %{customdata[1]}<br>'
                            'Date: %{customdata[2]}'
                            '<extra></extra>'
                        ),
                    )
                )
        else:
            for idx, (tName, shortLbl) in enumerate(zip(testNames, shortLabels)):
                df = measurements[tName]
                customData = np.column_stack((
                    df['Site'].astype(str).to_numpy(),
                    df['SerialNumber'].astype(str).to_numpy(),
                    df['TestDate'].astype(str).to_numpy(),
                ))
                fig.add_trace(
                    go.Scattergl(
                        x=df['CX'].to_numpy(dtype=float),
                        y=df['CY'].to_numpy(dtype=float),
                        mode='markers',
                        name=f'{shortLbl} ({len(df):,})',
                        marker=dict(size=5, color=self._getColor(idx), opacity=0.75),
                        customdata=customData,
                        hovertemplate=(
                            f'<b>{tName}</b><br>'
                            'Site: %{customdata[0]}<br>'
                            'CX: %{x:.5f}  |  CY: %{y:.5f}<br>'
                            'SN: %{customdata[1]}<br>'
                            'Date: %{customdata[2]}'
                            '<extra></extra>'
                        ),
                    )
                )

        seenBounds: set[tuple[tuple[float, float], ...]] = set()
        uniqueBounds: list[tuple[tuple[float, float], ...]] = []
        for tName in testNames:
            df = measurements[tName]
            if 'Boundary' not in df.columns:
                continue

            validB = df['Boundary'].dropna()
            if validB.empty:
                continue

            if limitsMode == 'Newest':
                candidates = [validB.iloc[-1]]
            elif limitsMode == 'Oldest':
                candidates = [validB.iloc[0]]
            else:
                candidates = validB.tolist()

            for poly in candidates:
                if poly is None or len(poly) < 3:
                    continue

                key = tuple((round(float(p[0]), 6), round(float(p[1]), 6)) for p in poly)
                if key not in seenBounds:
                    seenBounds.add(key)
                    uniqueBounds.append(key)

        dashStyles = ['solid', 'dash', 'dot', 'dashdot']
        for idx, poly in enumerate(uniqueBounds):
            bx = [p[0] for p in poly]
            by = [p[1] for p in poly]
            color = self.USL_COLOR if idx == 0 else ('#e040fb' if idx == 1 else self.LSL_COLOR)
            fig.add_trace(
                go.Scatter(
                    x=bx,
                    y=by,
                    mode='lines',
                    name=f'Bin Boundary {idx + 1}' if len(uniqueBounds) > 1 else 'Bin Boundary',
                    line=dict(color=color, width=2.2, dash=dashStyles[idx % len(dashStyles)]),
                    hoverinfo='skip',
                )
            )

        fig.update_layout(
            separators='. ',
            title=dict(
                text=f'Multi-LED CxCy Bin Overlay ({len(testNames)} tests)',
                x=0.02,
                y=0.96,
                font=dict(size=14, color=self.TEXT_COLOR),
            ),
            paper_bgcolor=self.BG_COLOR,
            plot_bgcolor=self.PLOT_BG_COLOR,
            font=dict(family='Segoe UI, Arial, sans-serif', size=11, color=self.TEXT_COLOR),
            margin=dict(l=65, r=25, t=72, b=55),
            hovermode='closest',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1.0,
                bgcolor='rgba(38, 40, 46, 0.75)',
                bordercolor=self.GRID_COLOR,
                borderwidth=1,
            ),
            xaxis=dict(title='CX', gridcolor=self.GRID_COLOR, zerolinecolor=self.GRID_COLOR, automargin=True),
            yaxis=dict(title='CY', gridcolor=self.GRID_COLOR, zerolinecolor=self.GRID_COLOR, automargin=True),
        )
        return fig


    # ------------------------------------------------------------------
    # Weighted Statistics & Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _weightedMedian(values:np.ndarray, weights:np.ndarray) -> float:
        valid = np.isfinite(values) & (weights > 0)
        v = values[valid]
        w = weights[valid].astype(float)
        if v.size == 0:
            return float('nan')
        
        if v.size == 1:
            return float(v[0])

        order = np.argsort(v)
        vSorted = v[order]
        wSorted = w[order]
        cumW = np.cumsum(wSorted)
        cutoff = 0.5 * cumW[-1]
        idx = int(np.searchsorted(cumW, cutoff))
        if idx < len(vSorted) - 1 and math.isclose(cumW[idx], cutoff, rel_tol=1e-12, abs_tol=1e-12):
            return 0.5 * float(vSorted[idx] + vSorted[idx + 1])
        return float(vSorted[min(idx, len(vSorted) - 1)])

    @staticmethod
    def _weightedNanMean(values:np.ndarray, weights:np.ndarray, axis:int) -> np.ndarray:
        valid = np.isfinite(values) & (weights > 0)
        safeVals = np.where(valid, values, 0.0)
        safeWeights = np.where(valid, weights, 0.0)
        wSum = np.sum(safeWeights, axis=axis)
        vSum = np.sum(safeVals * safeWeights, axis=axis)
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where(wSum > 0, vSum / wSum, np.nan)

    @staticmethod
    def _weightedNanMeanScalar(values:np.ndarray, weights:np.ndarray) -> float:
        valid = np.isfinite(values) & (weights > 0)
        if not np.any(valid):
            return float('nan')
        wSum = float(np.sum(weights[valid]))
        if wSum <= 0.0:
            return float('nan')
        return float(np.sum(values[valid] * weights[valid]) / wSum)

    @classmethod
    def _computeWeightedZScore(cls, meanMatrix:np.ndarray, colMean:np.ndarray, weights:np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        valid = np.isfinite(meanMatrix) & (weights > 0)
        if int(np.sum(valid)) < 2:
            return np.zeros_like(meanMatrix), np.zeros_like(colMean)

        med = cls._weightedMedian(meanMatrix, weights)
        absDev = np.abs(meanMatrix - med)
        mad = cls._weightedMedian(absDev, weights)
        robustSigma = 1.4826 * mad

        if not np.isfinite(robustSigma) or robustSigma <= 0.0:
            v = meanMatrix[valid]
            w = weights[valid].astype(float)
            wMean = float(np.sum(v * w) / np.sum(w))
            wVar = float(np.sum(w * ((v - wMean) ** 2)) / np.sum(w))
            robustSigma = math.sqrt(wVar) if wVar > 0.0 else 0.0

        if robustSigma <= 0.0:
            return np.zeros_like(meanMatrix), np.zeros_like(colMean)

        return (meanMatrix - med) / robustSigma, (colMean - med) / robustSigma

    @staticmethod
    def _nanMinAxis(arr:np.ndarray, axis:int) -> np.ndarray:
        with np.errstate(all='ignore'):
            return np.nanmin(arr, axis=axis)

    @staticmethod
    def _getActivePolygonCentroid(df:pd.DataFrame, limitsMode:str) -> tuple[float, float]|None:
        if 'Boundary' not in df.columns:
            return None
        
        validB = df['Boundary'].dropna()
        if validB.empty:
            return None

        poly = validB.iloc[0] if limitsMode == 'Oldest' else validB.iloc[-1]
        if poly is None or len(poly) < 3:
            return None

        pts = [(float(p[0]), float(p[1])) for p in poly]
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts = pts[:-1]
        if len(pts) < 3:
            return None

        area2 = 0.0
        cxAcc = 0.0
        cyAcc = 0.0
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            cross = x0 * y1 - x1 * y0
            area2 += cross
            cxAcc += (x0 + x1) * cross
            cyAcc += (y0 + y1) * cross

        if abs(area2) > 1e-12:
            return cxAcc / (3.0 * area2), cyAcc / (3.0 * area2)

        return (
            sum(p[0] for p in pts) / n,
            sum(p[1] for p in pts) / n,
        )

    @staticmethod
    def _buildPivotDataFrame(metric:str, rowLabels:list[str], colLabels:list[str], zMatrix:np.ndarray,
            rowSummary:np.ndarray, colSummary:np.ndarray, overallSummary:float) -> pd.DataFrame:
        
        summaryColName = 'Total' if metric == 'Fails' else ('Min' if metric == 'Ppk' else 'Row Avg')

        rows: list[dict] = []
        for rIdx, rLabel in enumerate(rowLabels):
            rowDict: dict = {'Site': rLabel}
            for cIdx, cLabel in enumerate(colLabels):
                rowDict[cLabel] = float(zMatrix[rIdx, cIdx])
            rowDict[summaryColName] = float(rowSummary[rIdx])
            rows.append(rowDict)

        totalRow: dict = {'Site': 'All / Group'}
        for cIdx, cLabel in enumerate(colLabels):
            totalRow[cLabel] = float(colSummary[cIdx])
        totalRow[summaryColName] = float(overallSummary)
        rows.append(totalRow)

        return pd.DataFrame(rows, columns=['Site', *colLabels, summaryColName])

    @staticmethod
    def formatMetricValue(val: float, metric: str, unitPrefix: str = '') -> str:
        if not np.isfinite(val):
            return '—'
        
        if metric == 'Fails':
            return f'{int(round(val)):,}'
        if metric == 'Yield (%)':

            return f'{val:.2f}%'
        if metric == 'Ppk':
            return f'{val:.2f}'
        
        if metric in ('Dev. vs Group (% tol.)', 'Centering Offset (%)'):
            return f'{val:+.1f}%'
        
        if metric == 'Dev. vs Group (Z-score)':
            return f'{val:+.2f}σ'
        
        if metric in ('Mean', 'Sigma'):
            suffix = f' {unitPrefix}' if unitPrefix else ''
            return f'{val:.4g}{suffix}'
        
        if metric in ('CX Dev. vs Group', 'CY Dev. vs Group'):
            return f'{val:+.4f}'
        
        if metric in ('CX Mean', 'CY Mean', 'Dist. from Bin Center'):
            return f'{val:.4f}'
        
        return f'{val:.4g}'

    @staticmethod
    def _resolveHeatmapColorScale(zMatrix:np.ndarray, metric:str):
        finite = zMatrix[np.isfinite(zMatrix)]
        if finite.size == 0:
            return 'Viridis', None, None, None

        divergingScale = [
            [0.0, '#1e88e5'],
            [0.25, '#4c8dff'],
            [0.5, '#2b2d30'],
            [0.75, '#ffa726'],
            [1.0, '#ef5350'],
        ]
        higherBetterScale = [
            [0.0, '#ef5350'],
            [0.5, '#ffa726'],
            [1.0, '#66bb6a'],
        ]
        lowerBetterScale = [
            [0.0, '#2b2d30'],
            [0.45, '#ffa726'],
            [1.0, '#ef5350'],
        ]

        if metric in ('Dev. vs Group (% tol.)', 'Centering Offset (%)'):
            maxAbs = max(10.0, float(np.max(np.abs(finite))))
            return divergingScale, -maxAbs, maxAbs, 0.0

        if metric == 'Dev. vs Group (Z-score)':
            maxAbs = max(2.0, float(np.max(np.abs(finite))))
            return divergingScale, -maxAbs, maxAbs, 0.0

        if metric in ('CX Dev. vs Group', 'CY Dev. vs Group'):
            maxAbs = max(0.002, float(np.max(np.abs(finite))))
            return divergingScale, -maxAbs, maxAbs, 0.0

        if metric == 'Yield (%)':
            low = min(95.0, float(np.min(finite)))
            return higherBetterScale, low, 100.0, None

        if metric == 'Ppk':
            high = max(2.0, float(np.max(finite)))
            return higherBetterScale, 0.0, min(high, 3.0), None

        if metric in ('Fails', 'Sigma', 'Dist. from Bin Center'):
            high = max(1e-6, float(np.max(finite)))
            return lowerBetterScale, 0.0, high, None

        return [[0.0, '#1f3b5c'], [0.5, '#26c6da'], [1.0, '#ffd600']], None, None, None

    def _createEmptyFigure(self, message:str) -> go.Figure:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor=self.BG_COLOR,
            plot_bgcolor=self.BG_COLOR,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[
                dict(
                    text=message.replace('\n', '<br>'),
                    xref='paper',
                    yref='paper',
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=14, color=self.MUTED_TEXT_COLOR),
                )
            ],
        )
        return fig

    @staticmethod
    def _makeUniqueShortLabels(names:list[str], maxLen:int=28) -> list[str]:
        """Keep both prefix and distinguishing suffix when shortening long test names."""
        counts: dict[str, int] = {}
        labels: list[str] = []
        headLen = max(8, (maxLen - 1) // 2 + 2)
        tailLen = max(6, maxLen - headLen - 1)

        for name in names:
            if len(name) <= maxLen:
                short = name
            else:
                short = f'{name[:headLen]}…{name[-tailLen:]}'
            counts[short] = counts.get(short, 0) + 1
            labels.append(f'{short} ({counts[short]})' if counts[short] > 1 else short)
        return labels

    def _getColor(self, idx: int) -> str:
        if idx < len(self.SITE_PALETTE):
            return self.SITE_PALETTE[idx]
        step = idx - len(self.SITE_PALETTE) + 1
        hue = ((step * 137.508) % 360.0) / 360.0
        lightness = 0.56 + (step % 3) * 0.08
        saturation = 0.75 if step % 2 == 0 else 0.88
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        return f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'