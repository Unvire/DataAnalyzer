from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np
import pandas as pd

from src.siFormatter import formatSiValue, isSentinelLimit


METRIC_HELP: dict[str, str] = {
    'samples': (
        'Samples (N): Total number of valid numeric measurements included in calculations.'
    ),
    'yield': (
        'Yield (%): Percentage of measurements within specification limits.\n'
        'Measures current pass rate, but not safety margin.\n'
        'Thresholds: ≥99.5% (OK), 98.0–99.49% (Warn), <98.0% (Bad).'
    ),
    'failLH': (
        'Fail Low / High: Count of measurements below LSL (< LSL) and above USL (> USL).\n'
        'One-sided fails indicate offset/drift (e.g., worn probes); balanced fails suggest excessive spread.'
    ),
    'dpmo': (
        'DPMO / PPM: Defects Per Million Opportunities.\n'
        'Normalizes defect rate across different lot sizes (e.g., 1 fail in 500 = 2,000 PPM).\n'
        'Thresholds: 0 (OK), ≤5,000 (Warn), >5,000 (Bad).'
    ),
    'lsl': 'LSL: Lower Specification Limit (sentinel dummy limits like -1e14 are automatically ignored).',
    'usl': 'USL: Upper Specification Limit (sentinel dummy limits like +1e14 are automatically ignored).',
    'mean': 'Mean (μ): Arithmetic average of all valid measurements. Compare with Median (X50) to spot skew.',
    'sigma': (
        'Sigma (σ): Process standard deviation.\n'
        'σ_overall = total lot spread (noise + drift + site offsets).\n'
        'σ_within = short-term within-site noise estimated via Moving Range (MR̄ / d2).'
    ),
    'pp': (
        'Pp (Long-Term Potential): (USL - LSL) / (6 · σ_overall).\n'
        'Shows whether total lot spread physically fits inside the tolerance window if centered.\n'
        'Thresholds: ≥1.33 (OK), 1.00–1.32 (Warn), <1.00 (Bad).'
    ),
    'cp': (
        'Cp (Short-Term Potential): (USL - LSL) / (6 · σ_within).\n'
        'Best-case capability inside a single site without time drift or site-to-site offsets.\n'
        'Thresholds: ≥1.33 (OK), 1.00–1.32 (Warn), <1.00 (Bad).'
    ),
    'ppk': (
        'Ppk (Long-Term Actual Capability): Real margin to the nearest limit using σ_overall.\n'
        'If Cpk is high but Ppk is low, suspect time drift, lot shifts, or site calibration offsets.\n'
        'Thresholds: ≥1.33 (OK), 1.00–1.32 (Warn), <1.00 (Bad).'
    ),
    'cpk': (
        'Cpk (Short-Term Actual Capability): Margin to the nearest limit using within-site σ_within.\n'
        'If Cp is high but Cpk is low, the process is tight but off-center.\n'
        'Thresholds: ≥1.33 (OK), 1.00–1.32 (Warn), <1.00 (Bad).'
    ),
    'ppkNp': (
        'Ppk (NP) — Non-Parametric ISO 22514: Percentile capability using P0.135, P50, P99.865.\n'
        'More reliable than standard Ppk for skewed/non-normal data (e.g., leakage current, contact resistance).'
    ),
    'tolUtil': (
        'Tolerance Utilization (%): 6 · σ_overall / (USL - LSL) × 100% (equals 100% / Pp).\n'
        'Percentage of the specification window consumed by process spread (lower is better).\n'
        'Thresholds: ≤75% (OK), 75.1–100% (Warn), >100% (Bad).'
    ),
    'centering': (
        'Centering Offset (%): Shift of process mean from tolerance midpoint (% of half-tolerance).\n'
        '0% = centered, +100% = on USL, -100% = on LSL.\n'
        'Thresholds: |offset| ≤25% (OK), 25.1–50% (Warn), >50% (Bad).'
    ),
    'siteDelta': (
        'Site-to-Site Delta (%): Gap between highest and lowest site means as % of tolerance width.\n'
        'High values indicate calibration mismatch, fixture wiring, or probe differences between sites.\n'
        'Thresholds: ≤10% (OK), 10.1–25% (Warn), >25% (Bad).'
    ),
    'skewness': (
        'Skewness (G1): Distribution asymmetry (0 = symmetric).\n'
        '>0 = right tail (toward USL), <0 = left tail (toward LSL).\n'
        'When |G1| ≥ 1.0, rely on Ppk (NP) rather than classical Ppk.'
    ),
    'kurtosis': (
        'Excess Kurtosis (G2): Tail weight relative to normal distribution (0 = normal).\n'
        '≫0 = sharp peak with isolated extreme outliers (e.g., intermittent probe contact).\n'
        '< -1 = flat or bimodal distribution (e.g., shifted sites or mixed component lots).'
    ),
}


@dataclass
class ProcessMetrics:
    isCxCy: bool = False
    samples: int = 0
    validSamples: int = 0
    yieldPct: float | None = None
    failLow: int = 0
    failHigh: int = 0
    failTotal: int = 0
    failLowPpm: float | None = None
    failHighPpm: float | None = None
    dpmo: float | None = None

    lsl: float | None = None
    usl: float | None = None
    mean: float | None = None
    median: float | None = None
    sigmaOverall: float | None = None
    sigmaWithin: float | None = None

    pp: float | None = None
    ppk: float | None = None
    cp: float | None = None
    cpk: float | None = None
    ppkNonParametric: float | None = None

    centeringOffsetPct: float | None = None
    toleranceUtilizationPct: float | None = None
    skewness: float | None = None
    kurtosis: float | None = None

    siteDeltaPct: float | None = None
    siteDeltaAbs: float | None = None
    siteDeltaMinSite: str = ''
    siteDeltaMaxSite: str = ''

    cxMean: float | None = None
    cyMean: float | None = None


class ProcessParameterCalculator:
    # Exact unbiasing constant d2 for Moving Range of subgroup size n = 2: sqrt(4 / pi)
    D2_MR2 = math.sqrt(4 / math.pi)

    def calculate(self, df:pd.DataFrame|None, limitsMode:str='All', includeShapeStats:bool=True) -> ProcessMetrics:
        metrics, _ = self.calculateWithFailMask(df, limitsMode=limitsMode, includeShapeStats=includeShapeStats)
        return metrics

    def calculateWithFailMask(self, df:pd.DataFrame|None, limitsMode:str='All', includeShapeStats: bool=True) -> tuple[ProcessMetrics, np.ndarray]:
        if df is None or df.empty:
            return ProcessMetrics(), np.zeros(0, dtype=bool)

        if 'CX' in df.columns and 'CY' in df.columns:
            return self._calculateCxCy(df, limitsMode=limitsMode)

        return self._calculateScalar(df, limitsMode=limitsMode, includeShapeStats=includeShapeStats)

    def _calculateScalar(self, df:pd.DataFrame, limitsMode:str='All', includeShapeStats:bool=True) -> tuple[ProcessMetrics, np.ndarray]:
        totalRows = len(df)
        fullFailMask = np.zeros(totalRows, dtype=bool)
        metrics = ProcessMetrics(isCxCy=False, samples=totalRows)

        if 'Value' not in df.columns:
            return metrics, fullFailMask

        rawVals = df['Value'].to_numpy(dtype=float)
        finiteMask = np.isfinite(rawVals)
        allFinite = bool(np.all(finiteMask))

        values = rawVals if allFinite else rawVals[finiteMask]
        n = len(values)
        metrics.validSamples = n
        if n == 0:
            return metrics, fullFailMask

        nonZero = np.abs(values[values != 0.0])
        dataRef = float(np.median(nonZero)) if nonZero.size > 0 else None

        lslCol = df['LSL'].to_numpy(dtype=float) if 'LSL' in df.columns else None
        uslCol = df['USL'].to_numpy(dtype=float) if 'USL' in df.columns else None
        datesCol = df['TestDate'].to_numpy() if 'TestDate' in df.columns else None
        sitesCol = df['Site'].to_numpy() if 'Site' in df.columns else None

        lslArr = (lslCol if allFinite else lslCol[finiteMask]) if lslCol is not None else None
        uslArr = (uslCol if allFinite else uslCol[finiteMask]) if uslCol is not None else None
        datesArr = (datesCol if allFinite else datesCol[finiteMask]) if datesCol is not None else None
        sitesArr = (sitesCol if allFinite else sitesCol[finiteMask]) if sitesCol is not None else None

        lslRef, uslRef = self._resolveScalarLimitsFast(lslArr, uslArr, datesArr, limitsMode)
        hasLsl = lslRef is not None and not isSentinelLimit(lslRef, dataRef)
        hasUsl = uslRef is not None and not isSentinelLimit(uslRef, dataRef)

        metrics.lsl = lslRef if hasLsl else None
        metrics.usl = uslRef if hasUsl else None

        meanVal = float(np.mean(values))
        medianVal = float(np.median(values))
        metrics.mean = meanVal
        metrics.median = medianVal

        # Fail counts, row-level fail mask, Yield and DPMO/PPM
        failLowMask, failHighMask, evaluatedLimits = self._evaluateScalarFailMasks(values=values, lslArr=lslArr,
            uslArr=uslArr, limitsMode=limitsMode, lslRef=metrics.lsl, uslRef=metrics.usl, dataRef=dataRef)
        
        failLowCount = int(np.sum(failLowMask))
        failHighCount = int(np.sum(failHighMask))
        metrics.failLow = failLowCount
        metrics.failHigh = failHighCount
        metrics.failTotal = failLowCount + failHighCount

        if evaluatedLimits:
            validFailMask = failLowMask | failHighMask
            if allFinite:
                fullFailMask = validFailMask
            else:
                fullFailMask[finiteMask] = validFailMask

            metrics.yieldPct = ((n - metrics.failTotal) / n) * 100.0
            metrics.failLowPpm = (failLowCount / n) * 1_000_000.0
            metrics.failHighPpm = (failHighCount / n) * 1_000_000.0
            metrics.dpmo = (metrics.failTotal / n) * 1_000_000.0

        # Long-term sigma (overall) & Short-term sigma (within via Moving Range) + Site-to-Site Delta in one pass
        sigmaOverall = float(np.std(values, ddof=1)) if n > 1 else None
        metrics.sigmaOverall = sigmaOverall

        tolSpan = (
            (metrics.usl - metrics.lsl)
            if (metrics.lsl is not None and metrics.usl is not None and metrics.usl > metrics.lsl)
            else None
        )
        sigmaWithin = self._computeWithinSigmaAndSiteDelta(metrics, values, sitesArr, datesArr, tolSpan)
        metrics.sigmaWithin = sigmaWithin

        # Capability indices (Pp, Ppk, Cp, Cpk)
        metrics.pp, metrics.ppk = self._computeCapabilityIndices(meanVal, sigmaOverall, metrics.lsl, metrics.usl)
        
        metrics.cp, metrics.cpk = self._computeCapabilityIndices(meanVal, sigmaWithin, metrics.lsl, metrics.usl)

        # Non-parametric Ppk (ISO 22514 percentile method)
        metrics.ppkNonParametric = self._computeNonParametricPpk(values, medianVal, metrics.lsl, metrics.usl)

        # Two-sided tolerance indicators
        if tolSpan is not None:
            midpoint = 0.5 * (metrics.lsl + metrics.usl)
            halfTol = 0.5 * tolSpan
            metrics.centeringOffsetPct = ((meanVal - midpoint) / halfTol) * 100.0
            if sigmaOverall is not None:
                metrics.toleranceUtilizationPct = ((6.0 * sigmaOverall) / tolSpan) * 100.0

        # Distribution shape (skipped during fast batch Pareto scan when not needed)
        if includeShapeStats:
            metrics.skewness = self._computeSkewness(values, meanVal, sigmaOverall)
            metrics.kurtosis = self._computeExcessKurtosis(values, meanVal, sigmaOverall)

        return metrics, fullFailMask

    def _calculateCxCy(self, df:pd.DataFrame, limitsMode:str='All') -> tuple[ProcessMetrics, np.ndarray]:
        totalRows = len(df)
        fullFailMask = np.zeros(totalRows, dtype=bool)
        metrics = ProcessMetrics(isCxCy=True, samples=totalRows)

        cx = df['CX'].to_numpy(dtype=float)
        cy = df['CY'].to_numpy(dtype=float)
        finiteMask = np.isfinite(cx) & np.isfinite(cy)
        allFinite = bool(np.all(finiteMask))

        cxValid = cx if allFinite else cx[finiteMask]
        cyValid = cy if allFinite else cy[finiteMask]
        n = len(cxValid)
        metrics.validSamples = n

        if n == 0:
            return metrics, fullFailMask

        metrics.cxMean = float(np.mean(cxValid))
        metrics.cyMean = float(np.mean(cyValid))

        if 'Boundary' not in df.columns:
            return metrics, fullFailMask

        validDf = df if allFinite else df[finiteMask]
        boundariesList = validDf['Boundary'].tolist()
        validBoundaryIndices = [i for i, b in enumerate(boundariesList) if b is not None and len(b) >= 3]
        if not validBoundaryIndices:
            return metrics, fullFailMask

        if limitsMode in ('Newest', 'Oldest'):
            datesArr = validDf['TestDate'].to_numpy() if 'TestDate' in validDf.columns else None
            refIdx = self._pickBoundaryIndex(validBoundaryIndices, datesArr, limitsMode)
            refPoly = boundariesList[refIdx]
            insideMask = self._pointsInPolygon(cxValid, cyValid, refPoly)
            validFailMask = ~insideMask
            
        else:
            passMask = np.ones(n, dtype=bool)
            polyGroups: dict[tuple[tuple[float, float], ...], list[int]] = {}
            for rowIdx in validBoundaryIndices:
                poly = boundariesList[rowIdx]
                key = tuple((float(pt[0]), float(pt[1])) for pt in poly)
                polyGroups.setdefault(key, []).append(rowIdx)

            for polyKey, idxList in polyGroups.items():
                idxArr = np.asarray(idxList, dtype=np.int64)
                passMask[idxArr] = self._pointsInPolygon(cxValid[idxArr], cyValid[idxArr], polyKey)

            validFailMask = ~passMask

        if allFinite:
            fullFailMask = validFailMask
        else:
            fullFailMask[finiteMask] = validFailMask

        failCount = int(np.sum(validFailMask))
        metrics.failTotal = failCount
        metrics.yieldPct = ((n - failCount) / n) * 100.0
        metrics.dpmo = (failCount / n) * 1_000_000.0
        return metrics, fullFailMask

    @staticmethod
    def _pickBoundaryIndex(validIndices:list[int], datesArr:np.ndarray|None, limitsMode:str) -> int:
        if datesArr is None or len(validIndices) == 1:
            return validIndices[0] if limitsMode == 'Oldest' else validIndices[-1]

        datesList = [str(datesArr[i]) for i in validIndices]
        if limitsMode == 'Oldest':
            bestPos = min(range(len(validIndices)), key=datesList.__getitem__)
            return validIndices[bestPos]

        maxDate = max(datesList)
        for pos in range(len(validIndices) - 1, -1, -1):
            if datesList[pos] == maxDate:
                return validIndices[pos]
        return validIndices[-1]

    @staticmethod
    def _isArrayConstant(arr:np.ndarray) -> bool:
        if len(arr) <= 1:
            return True
        first = arr[0]
        if math.isnan(float(first)):
            return bool(np.all(np.isnan(arr)))
        return bool(np.all(arr == first))

    @classmethod
    def _resolveScalarLimitsFast(cls, lslArr:np.ndarray|None, uslArr:np.ndarray|None, datesArr:np.ndarray|None,
        limitsMode:str) -> tuple[float|None, float|None]:
        
        if lslArr is None or uslArr is None or len(lslArr) == 0:
            return None, None

        # Fast path: limits never changed across the lot (avoids touching TestDate at all)
        if cls._isArrayConstant(lslArr) and cls._isArrayConstant(uslArr):
            lslVal = float(lslArr[0])
            uslVal = float(uslArr[0])
            return (
                lslVal if math.isfinite(lslVal) else None,
                uslVal if math.isfinite(uslVal) else None,
            )

        if datesArr is None or len(datesArr) != len(lslArr):
            rowIdx = 0 if limitsMode == 'Oldest' else (len(lslArr) - 1)
        else:
            datesList = datesArr.tolist()
            if limitsMode == 'Oldest':
                rowIdx = min(range(len(datesList)), key=datesList.__getitem__)
            else:
                maxDate = max(datesList)
                rowIdx = len(datesList) - 1
                for i in range(len(datesList) - 1, -1, -1):
                    if datesList[i] == maxDate:
                        rowIdx = i
                        break

        lslVal = float(lslArr[rowIdx])
        uslVal = float(uslArr[rowIdx])
        return (
            lslVal if math.isfinite(lslVal) else None,
            uslVal if math.isfinite(uslVal) else None,
        )

    @classmethod
    def _resolveScalarLimits(cls, df:pd.DataFrame, limitsMode:str) -> tuple[float|None, float|None]:
        if df.empty or 'LSL' not in df.columns or 'USL' not in df.columns:
            return None, None
        lslArr = df['LSL'].to_numpy(dtype=float)
        uslArr = df['USL'].to_numpy(dtype=float)
        datesArr = df['TestDate'].to_numpy() if 'TestDate' in df.columns else None
        return cls._resolveScalarLimitsFast(lslArr, uslArr, datesArr, limitsMode)

    @classmethod
    def _buildValidLimitMask(cls, limitArr:np.ndarray, dataRef:float|None) -> np.ndarray:
        n = len(limitArr)
        if n == 0:
            return np.zeros(0, dtype=bool)

        # Fast path for constant limits
        if cls._isArrayConstant(limitArr):
            first = float(limitArr[0])
            if not math.isfinite(first) or isSentinelLimit(first, dataRef):
                return np.zeros(n, dtype=bool)
            return np.ones(n, dtype=bool)

        finiteMask = np.isfinite(limitArr)
        if not np.any(finiteMask):
            return np.zeros(n, dtype=bool)

        uniqueVals = np.unique(limitArr[finiteMask])
        sentinelVals = [v for v in uniqueVals if isSentinelLimit(float(v), dataRef)]
        if not sentinelVals:
            return finiteMask
        if len(sentinelVals) == len(uniqueVals):
            return np.zeros(n, dtype=bool)

        return finiteMask & (~np.isin(limitArr, sentinelVals))

    def _evaluateScalarFailMasks(self, values:np.ndarray, lslArr:np.ndarray|None, uslArr:np.ndarray|None, limitsMode:str,
            lslRef: float|None, uslRef: float|None, dataRef:float|None) -> tuple[np.ndarray, np.ndarray, bool]:
        
        n = len(values)
        zeros = np.zeros(n, dtype=bool)

        if limitsMode == 'All' and lslArr is not None and uslArr is not None:
            validLslMask = self._buildValidLimitMask(lslArr, dataRef)
            validUslMask = self._buildValidLimitMask(uslArr, dataRef)

            hasAnyLsl = bool(np.any(validLslMask))
            hasAnyUsl = bool(np.any(validUslMask))
            if not (hasAnyLsl or hasAnyUsl):
                return zeros, zeros, False

            failLowMask = (validLslMask & (values < lslArr)) if hasAnyLsl else zeros
            failHighMask = (validUslMask & (values > uslArr)) if hasAnyUsl else zeros
            return failLowMask, failHighMask, True

        if lslRef is None and uslRef is None:
            return zeros, zeros, False

        failLowMask = (values < lslRef) if lslRef is not None else zeros
        failHighMask = (values > uslRef) if uslRef is not None else zeros
        return failLowMask, failHighMask, True

    @staticmethod
    def _isNonDecreasing(arr: np.ndarray) -> bool:
        n = len(arr)
        if n <= 1:
            return True
        return bool(np.all(arr[:-1] <= arr[1:]))

    def _computeWithinSigmaAndSiteDelta(self, metrics:ProcessMetrics, values:np.ndarray, sitesArr:np.ndarray|None, 
            datesArr: np.ndarray|None, tolSpan:float|None) -> float|None:
        
        n = len(values)
        if n < 2:
            return None

        if sitesArr is None:
            orderedVals = values
            if datesArr is not None and not self._isNonDecreasing(datesArr):
                order = np.argsort(datesArr, kind='mergesort')
                orderedVals = values[order]
            mrBar = float(np.mean(np.abs(np.diff(orderedVals))))
            return mrBar / self.D2_MR2

        # Group by site using fast C-level factorization without allocating sub-DataFrames
        codes, uniques = pd.factorize(sitesArr, sort=False)
        numSites = len(uniques)

        if numSites <= 1:
            orderedVals = values
            if datesArr is not None and not self._isNonDecreasing(datesArr):
                order = np.argsort(datesArr, kind='mergesort')
                orderedVals = values[order]
            mrBar = float(np.mean(np.abs(np.diff(orderedVals))))
            return mrBar / self.D2_MR2

        siteOrder = np.argsort(codes, kind='mergesort')
        sortedCodes = codes[siteOrder]
        splitPoints = np.flatnonzero(np.diff(sortedCodes)) + 1
        bounds = np.concatenate(([0], splitPoints, [n]))

        mrSum = 0.0
        mrCount = 0
        minMean = float('inf')
        maxMean = float('-inf')
        minSiteName = ''
        maxSiteName = ''
        validSiteCount = 0

        for segIdx in range(len(bounds) - 1):
            start = int(bounds[segIdx])
            end = int(bounds[segIdx + 1])
            segLen = end - start
            if segLen == 0:
                continue

            idxSlice = siteOrder[start:end]
            siteCode = int(sortedCodes[start])
            siteLabel = str(uniques[siteCode])
            sVals = values[idxSlice]

            sMean = float(np.mean(sVals))
            validSiteCount += 1
            if sMean < minMean:
                minMean = sMean
                minSiteName = siteLabel
            if sMean > maxMean:
                maxMean = sMean
                maxSiteName = siteLabel

            if segLen >= 2:
                if datesArr is not None:
                    sDates = datesArr[idxSlice]
                    if not self._isNonDecreasing(sDates):
                        dateOrder = np.argsort(sDates, kind='mergesort')
                        sVals = sVals[dateOrder]
                diffs = np.abs(np.diff(sVals))
                mrSum += float(np.sum(diffs))
                mrCount += segLen - 1

        if validSiteCount >= 2:
            deltaAbs = maxMean - minMean
            metrics.siteDeltaAbs = deltaAbs
            metrics.siteDeltaMinSite = minSiteName
            metrics.siteDeltaMaxSite = maxSiteName
            if tolSpan is not None and tolSpan > 0.0:
                metrics.siteDeltaPct = (deltaAbs / tolSpan) * 100.0

        if mrCount == 0:
            # Fallback if every site had only 1 sample
            orderedVals = values
            if datesArr is not None and not self._isNonDecreasing(datesArr):
                order = np.argsort(datesArr, kind='mergesort')
                orderedVals = values[order]
            mrBar = float(np.mean(np.abs(np.diff(orderedVals))))
            return mrBar / self.D2_MR2

        return (mrSum / mrCount) / self.D2_MR2

    @staticmethod
    def _computeCapabilityIndices(meanVal:float, sigma:float|None, lsl: float|None, usl:float |None) -> tuple[float | None, float | None]:
        if sigma is None or not np.isfinite(sigma) or sigma <= 0.0:
            return None, None

        denom = 3.0 * sigma
        cpLow = (meanVal - lsl) / denom if lsl is not None else None
        cpHigh = (usl - meanVal) / denom if usl is not None else None

        if lsl is not None and usl is not None and usl > lsl:
            cpVal = (usl - lsl) / (6.0 * sigma)
            cpkVal = min(cpLow, cpHigh)
            return cpVal, cpkVal

        if cpLow is not None:
            return None, cpLow
        if cpHigh is not None:
            return None, cpHigh
        return None, None

    @staticmethod
    def _computeNonParametricPpk(values:np.ndarray, medianVal:float, lsl:float|None, usl:float|None) -> float|None:
        if len(values) < 2 or (lsl is None and usl is None):
            return None

        pLow, pHigh = np.percentile(values, [0.135, 99.865])
        candidates: list[float] = []

        if lsl is not None:
            lowerSpread = medianVal - float(pLow)
            if lowerSpread > 0.0:
                candidates.append((medianVal - lsl) / lowerSpread)

        if usl is not None:
            upperSpread = float(pHigh) - medianVal
            if upperSpread > 0.0:
                candidates.append((usl - medianVal) / upperSpread)

        if not candidates:
            return None

        if lsl is not None and usl is not None and len(candidates) < 2:
            return None

        return float(min(candidates))

    @staticmethod
    def _populateSiteDelta(metrics:ProcessMetrics, validDf:pd.DataFrame, tolSpan:float|None):
        if 'Site' not in validDf.columns:
            return

        siteMeans = validDf.groupby(validDf['Site'].astype(str))['Value'].mean().dropna()
        if len(siteMeans) < 2:
            return

        minSite = str(siteMeans.idxmin())
        maxSite = str(siteMeans.idxmax())
        deltaAbs = float(siteMeans.loc[maxSite] - siteMeans.loc[minSite])

        metrics.siteDeltaAbs = deltaAbs
        metrics.siteDeltaMinSite = minSite
        metrics.siteDeltaMaxSite = maxSite

        if tolSpan is not None and tolSpan > 0.0:
            metrics.siteDeltaPct = (deltaAbs / tolSpan) * 100.0

    @staticmethod
    def _computeSkewness(values:np.ndarray, meanVal:float, sigmaOverall:float|None) -> float|None:
        n = len(values)
        if n < 3 or sigmaOverall is None or sigmaOverall <= 0.0:
            return None
        z = (values - meanVal) / sigmaOverall
        m3 = float(np.sum(z ** 3))
        return (n / ((n - 1) * (n - 2))) * m3

    @staticmethod
    def _computeExcessKurtosis(values:np.ndarray, meanVal:float, sigmaOverall:float|None) -> float|None:
        n = len(values)
        if n < 4 or sigmaOverall is None or sigmaOverall <= 0.0:
            return None
        
        z = (values - meanVal) / sigmaOverall
        m4 = float(np.sum(z ** 4))
        term1 = (n * (n + 1)) / ((n - 1) * (n - 2) * (n - 3)) * m4
        term2 = (3.0 * ((n - 1) ** 2)) / ((n - 2) * (n - 3))
        return term1 - term2

    @staticmethod
    def _pointsInPolygon(px:np.ndarray, py:np.ndarray, polygon:Sequence[tuple[float, float]], edgeEps:float=1e-12) -> np.ndarray:
        nPts = len(px)
        if nPts == 0 or len(polygon) < 3:
            return np.zeros(nPts, dtype=bool)

        pts = list(polygon)
        if pts[0] != pts[-1]:
            pts.append(pts[0])

        inside = np.zeros(nPts, dtype=bool)
        onEdge = np.zeros(nPts, dtype=bool)

        for i in range(len(pts) - 1):
            x1, y1 = float(pts[i][0]), float(pts[i][1])
            x2, y2 = float(pts[i + 1][0]), float(pts[i + 1][1])

            # Check if point lies directly on segment [p1, p2]
            dx = x2 - x1
            dy = y2 - y1
            segLenSq = dx * dx + dy * dy
            if segLenSq > 0.0:
                cross = np.abs((px - x1) * dy - (py - y1) * dx)
                dot = (px - x1) * dx + (py - y1) * dy
                onSeg = (cross <= edgeEps * math.sqrt(segLenSq)) & (dot >= -edgeEps) & (dot <= segLenSq + edgeEps)
                onEdge |= onSeg

            # Ray casting to +infinity along X
            straddlesY = (y1 > py) != (y2 > py)
            if np.any(straddlesY):
                xIntersect = x1 + (py[straddlesY] - y1) * (x2 - x1) / (y2 - y1)
                inside[straddlesY] ^= px[straddlesY] < xIntersect

        return inside | onEdge

    @staticmethod
    def _mergeTooltip(detail:str, metricKey:str) -> str:
        desc = METRIC_HELP.get(metricKey, '')
        if detail and desc:
            return f'{detail}\n\n{desc}'
        return detail or desc


    @classmethod
    def formatForStatsPanel(cls, metrics: ProcessMetrics) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
        """
        Returns (values, statuses, tooltips) dictionaries ready for StatsPanel.updateStats().
        Status values: 'ok', 'warn', 'bad', or 'neutral'.
        """
        values: dict[str, str] = {}
        statuses: dict[str, str] = {}
        tooltips: dict[str, str] = {}

        if metrics.samples == 0:
            return values, statuses, tooltips

        values['samples'] = f'{metrics.validSamples:,}'
        sampleDetail = (
            f'Valid numeric samples: {metrics.validSamples:,} / {metrics.samples:,}'
            if metrics.validSamples != metrics.samples
            else f'Samples: {metrics.validSamples:,}'
        )
        tooltips['samples'] = cls._mergeTooltip(sampleDetail, 'samples')

        if metrics.yieldPct is not None:
            values['yield'] = f'{metrics.yieldPct:.2f}%'
            statuses['yield'] = cls._gradeYield(metrics.yieldPct)
            tooltips['yield'] = cls._mergeTooltip(
                f'Pass: {metrics.validSamples - metrics.failTotal:,} / {metrics.validSamples:,}',
                'yield',
            )

        if metrics.isCxCy:
            values['failLH'] = f'{metrics.failTotal:,} out'
            statuses['failLH'] = 'ok' if metrics.failTotal == 0 else 'bad'
            tooltips['failLH'] = 'Points outside active CxCy bin polygon.'

            if metrics.dpmo is not None:
                values['dpmo'] = cls._formatPpm(metrics.dpmo)
                statuses['dpmo'] = cls._gradeDpmo(metrics.dpmo)
                tooltips['dpmo'] = cls._mergeTooltip(f'Current: {metrics.dpmo:,.1f} PPM', 'dpmo')
                
            if metrics.cxMean is not None and metrics.cyMean is not None:
                values['mean'] = f'{metrics.cxMean:.4f}, {metrics.cyMean:.4f}'
                tooltips['mean'] = f'Mean CX = {metrics.cxMean:.5f}, Mean CY = {metrics.cyMean:.5f}'
                
            return values, statuses, tooltips

        if metrics.yieldPct is not None:
            values['failLH'] = f'{metrics.failLow:,} / {metrics.failHigh:,}'
            statuses['failLH'] = 'ok' if metrics.failTotal == 0 else 'bad'
            lowPpmStr = cls._formatPpm(metrics.failLowPpm or 0.0)
            highPpmStr = cls._formatPpm(metrics.failHighPpm or 0.0)
            tooltips['failLH'] = cls._mergeTooltip(
                f'Fail Low: {metrics.failLow:,} ({lowPpmStr} PPM)\n'
                f'Fail High: {metrics.failHigh:,} ({highPpmStr} PPM)',
                'failLH',
            )

        if metrics.dpmo is not None:
            values['dpmo'] = cls._formatPpm(metrics.dpmo)
            statuses['dpmo'] = cls._gradeDpmo(metrics.dpmo)
            tooltips['dpmo'] = cls._mergeTooltip(f'Current: {metrics.dpmo:,.1f} PPM', 'dpmo')

        if metrics.lsl is not None:
            values['lsl'] = formatSiValue(metrics.lsl, precision=4)
            tooltips['lsl'] = cls._mergeTooltip(f'Exact LSL = {metrics.lsl:.6g}', 'lsl')

        if metrics.usl is not None:
            values['usl'] = formatSiValue(metrics.usl, precision=4)
            tooltips['usl'] = cls._mergeTooltip(f'Exact USL = {metrics.usl:.6g}', 'usl')

        if metrics.mean is not None:
            values['mean'] = formatSiValue(metrics.mean, precision=4)
            medStr = formatSiValue(metrics.median, precision=4) if metrics.median is not None else '—'
            tooltips['mean'] = cls._mergeTooltip(
                f'Mean = {metrics.mean:.6g}\nMedian (X50) = {medStr}',
                'mean',
            )

        if metrics.sigmaOverall is not None:
            values['sigma'] = formatSiValue(metrics.sigmaOverall, precision=3)
            withinStr = (
                formatSiValue(metrics.sigmaWithin, precision=3)
                if metrics.sigmaWithin is not None
                else '—'
            )
            tooltips['sigma'] = cls._mergeTooltip(
                f'σ_overall (long-term) = {formatSiValue(metrics.sigmaOverall, precision=4)}\n'
                f'σ_within (MR̄ / d2) = {withinStr}',
                'sigma',
            )

        for key, val in (
            ('pp', metrics.pp),
            ('cp', metrics.cp),
            ('ppk', metrics.ppk),
            ('cpk', metrics.cpk),
            ('ppkNp', metrics.ppkNonParametric),
        ):
            if val is not None:
                values[key] = f'{val:.2f}'
                statuses[key] = cls._gradeCapability(val)
                tooltips[key] = cls._mergeTooltip(f'Current: {val:.3f}', key)

        if metrics.toleranceUtilizationPct is not None:
            values['tolUtil'] = f'{metrics.toleranceUtilizationPct:.1f}%'
            statuses['tolUtil'] = cls._gradeTolUtilization(metrics.toleranceUtilizationPct)
            tooltips['tolUtil'] = cls._mergeTooltip(
                f'Current: {metrics.toleranceUtilizationPct:.2f}% of tolerance window',
                'tolUtil',
            )

        if metrics.centeringOffsetPct is not None:
            values['centering'] = f'{metrics.centeringOffsetPct:+.1f}%'
            statuses['centering'] = cls._gradeCentering(metrics.centeringOffsetPct)
            tooltips['centering'] = cls._mergeTooltip(
                f'Current: {metrics.centeringOffsetPct:+.2f}% of half-tolerance',
                'centering',
            )

        if metrics.siteDeltaPct is not None:
            values['siteDelta'] = f'{metrics.siteDeltaPct:.1f}%'
            statuses['siteDelta'] = cls._gradeSiteDelta(metrics.siteDeltaPct)
            absStr = formatSiValue(metrics.siteDeltaAbs, precision=3) if metrics.siteDeltaAbs is not None else '—'
            tooltips['siteDelta'] = cls._mergeTooltip(
                f'Max site mean shift: {absStr} ({metrics.siteDeltaPct:.2f}% of tolerance)\n'
                f'Lowest mean: Site {metrics.siteDeltaMinSite}  |  Highest mean: Site {metrics.siteDeltaMaxSite}',
                'siteDelta',
            )
        elif metrics.siteDeltaAbs is not None:
            values['siteDelta'] = formatSiValue(metrics.siteDeltaAbs, precision=3)
            tooltips['siteDelta'] = cls._mergeTooltip(
                f'Site mean shift (one-sided spec): {values["siteDelta"]}\n'
                f'Lowest: Site {metrics.siteDeltaMinSite}  |  Highest: Site {metrics.siteDeltaMaxSite}',
                'siteDelta',
            )

        if metrics.skewness is not None:
            values['skewness'] = f'{metrics.skewness:+.2f}'
            if abs(metrics.skewness) >= 1.0:
                statuses['skewness'] = 'warn'
            tooltips['skewness'] = cls._mergeTooltip(f'Current G1 = {metrics.skewness:+.3f}', 'skewness')

        if metrics.kurtosis is not None:
            values['kurtosis'] = f'{metrics.kurtosis:+.2f}'
            tooltips['kurtosis'] = cls._mergeTooltip(f'Current G2 = {metrics.kurtosis:+.3f}', 'kurtosis')

        return values, statuses, tooltips

    @staticmethod
    def _formatPpm(ppm: float) -> str:
        if ppm == 0.0:
            return '0'
        if ppm < 10.0:
            return f'{ppm:.1f}'
        return f'{ppm:,.0f}'

    @staticmethod
    def _gradeYield(yieldPct: float) -> str:
        if yieldPct >= 99.5:
            return 'ok'
        if yieldPct >= 98.0:
            return 'warn'
        return 'bad'

    @staticmethod
    def _gradeDpmo(dpmo: float) -> str:
        if dpmo == 0.0:
            return 'ok'
        if dpmo <= 5000.0:
            return 'warn'
        return 'bad'

    @staticmethod
    def _gradeCapability(val: float) -> str:
        if val >= 1.33:
            return 'ok'
        if val >= 1.00:
            return 'warn'
        return 'bad'

    @staticmethod
    def _gradeTolUtilization(pct: float) -> str:
        if pct <= 75.0:
            return 'ok'
        if pct <= 100.0:
            return 'warn'
        return 'bad'

    @staticmethod
    def _gradeCentering(offsetPct: float) -> str:
        absOff = abs(offsetPct)
        if absOff <= 25.0:
            return 'ok'
        if absOff <= 50.0:
            return 'warn'
        return 'bad'

    @staticmethod
    def _gradeSiteDelta(deltaPct: float) -> str:
        if deltaPct <= 10.0:
            return 'ok'
        if deltaPct <= 25.0:
            return 'warn'
        return 'bad'