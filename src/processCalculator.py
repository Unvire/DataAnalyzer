from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np
import pandas as pd

from src.siFormatter import formatSiValue, isSentinelLimit


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

    def calculate(self, df:pd.DataFrame|None, limitsMode:str='All') -> ProcessMetrics:
        if df is None or df.empty:
            return ProcessMetrics()

        if 'CX' in df.columns and 'CY' in df.columns:
            return self._calculateCxCy(df, limitsMode=limitsMode)

        return self._calculateScalar(df, limitsMode=limitsMode)

    def _calculateScalar(self, df:pd.DataFrame, limitsMode:str = 'All') -> ProcessMetrics:
        metrics = ProcessMetrics(isCxCy=False, samples=len(df))
        if 'Value' not in df.columns:
            return metrics

        rawVals = df['Value'].to_numpy(dtype=float)
        finiteMask = np.isfinite(rawVals)
        validDf = df[finiteMask]
        values = rawVals[finiteMask]
        n = len(values)
        metrics.validSamples = n

        if n == 0:
            return metrics

        nonZero = np.abs(values[values != 0.0])
        dataRef = float(np.median(nonZero)) if nonZero.size > 0 else None

        lslRef, uslRef = self._resolveScalarLimits(validDf, limitsMode)
        hasLsl = lslRef is not None and not isSentinelLimit(lslRef, dataRef)
        hasUsl = uslRef is not None and not isSentinelLimit(uslRef, dataRef)

        metrics.lsl = lslRef if hasLsl else None
        metrics.usl = uslRef if hasUsl else None

        meanVal = float(np.mean(values))
        medianVal = float(np.median(values))
        metrics.mean = meanVal
        metrics.median = medianVal

        # Fail counts, Yield and DPMO/PPM
        failLowCount, failHighCount, evaluatedLimits = self._evaluateScalarFails(
            validDf, values, limitsMode, metrics.lsl, metrics.usl, dataRef
        )
        metrics.failLow = failLowCount
        metrics.failHigh = failHighCount
        metrics.failTotal = failLowCount + failHighCount

        if evaluatedLimits:
            metrics.yieldPct = ((n - metrics.failTotal) / n) * 100.0
            metrics.failLowPpm = (failLowCount / n) * 1_000_000.0
            metrics.failHighPpm = (failHighCount / n) * 1_000_000.0
            metrics.dpmo = (metrics.failTotal / n) * 1_000_000.0

        # Long-term sigma (overall) & Short-term sigma (within via Moving Range)
        sigmaOverall = float(np.std(values, ddof=1)) if n > 1 else None
        sigmaWithin = self._calculateWithinSigma(validDf)
        metrics.sigmaOverall = sigmaOverall
        metrics.sigmaWithin = sigmaWithin

        # Capability indices (Pp, Ppk, Cp, Cpk)
        metrics.pp, metrics.ppk = self._computeCapabilityIndices(
            meanVal, sigmaOverall, metrics.lsl, metrics.usl
        )
        metrics.cp, metrics.cpk = self._computeCapabilityIndices(
            meanVal, sigmaWithin, metrics.lsl, metrics.usl
        )

        # Non-parametric Ppk (ISO 22514 percentile method)
        metrics.ppkNonParametric = self._computeNonParametricPpk(
            values, medianVal, metrics.lsl, metrics.usl
        )

        # Two-sided tolerance indicators: Centering Offset, Tolerance Utilization, Site-to-Site Delta
        if metrics.lsl is not None and metrics.usl is not None and metrics.usl > metrics.lsl:
            tolSpan = metrics.usl - metrics.lsl
            midpoint = 0.5 * (metrics.lsl + metrics.usl)
            halfTol = 0.5 * tolSpan
            metrics.centeringOffsetPct = ((meanVal - midpoint) / halfTol) * 100.0

            if sigmaOverall is not None:
                metrics.toleranceUtilizationPct = ((6.0 * sigmaOverall) / tolSpan) * 100.0

            self._populateSiteDelta(metrics, validDf, tolSpan)
        else:
            self._populateSiteDelta(metrics, validDf, tolSpan=None)

        # Distribution shape (unbiased Fisher-Pearson skewness and excess kurtosis)
        metrics.skewness = self._computeSkewness(values, meanVal, sigmaOverall)
        metrics.kurtosis = self._computeExcessKurtosis(values, meanVal, sigmaOverall)

        return metrics

    def _calculateCxCy(self, df:pd.DataFrame, limitsMode:str='All') -> ProcessMetrics:
        metrics = ProcessMetrics(isCxCy=True, samples=len(df))
        cx = df['CX'].to_numpy(dtype=float)
        cy = df['CY'].to_numpy(dtype=float)
        finiteMask = np.isfinite(cx) & np.isfinite(cy)
        validDf = df[finiteMask]
        n = len(validDf)
        metrics.validSamples = n

        if n == 0:
            return metrics

        cxValid = cx[finiteMask]
        cyValid = cy[finiteMask]
        metrics.cxMean = float(np.mean(cxValid))
        metrics.cyMean = float(np.mean(cyValid))

        if 'Boundary' not in validDf.columns:
            return metrics

        sortedDf = validDf.sort_values(by='TestDate', kind='mergesort') if 'TestDate' in validDf.columns else validDf
        boundaries = sortedDf['Boundary'].dropna()
        if boundaries.empty:
            return metrics

        if limitsMode == 'Newest':
            refPoly = boundaries.iloc[-1]
            insideMask = self._pointsInPolygon(cxValid, cyValid, refPoly)
            failCount = int(np.sum(~insideMask))
        elif limitsMode == 'Oldest':
            refPoly = boundaries.iloc[0]
            insideMask = self._pointsInPolygon(cxValid, cyValid, refPoly)
            failCount = int(np.sum(~insideMask))
        else:
            # Per-row polygon check grouped by distinct polygons for speed
            passMask = np.ones(n, dtype=bool)
            polyGroups: dict[tuple[tuple[float, float], ...], list[int]] = {}
            for rowIdx, poly in enumerate(validDf['Boundary'].tolist()):
                if poly is None or len(poly) < 3:
                    continue
                key = tuple((float(pt[0]), float(pt[1])) for pt in poly)
                polyGroups.setdefault(key, []).append(rowIdx)

            for polyKey, idxList in polyGroups.items():
                idxArr = np.asarray(idxList, dtype=np.int64)
                passMask[idxArr] = self._pointsInPolygon(cxValid[idxArr], cyValid[idxArr], polyKey)

            failCount = int(np.sum(~passMask))

        metrics.failTotal = failCount
        metrics.yieldPct = ((n - failCount) / n) * 100.0
        metrics.dpmo = (failCount / n) * 1_000_000.0
        return metrics

    @staticmethod
    def _resolveScalarLimits(df:pd.DataFrame, limitsMode:str) -> tuple[float|None, float|None]:
        if 'LSL' not in df.columns or 'USL' not in df.columns or df.empty:
            return None, None
        sortedDf = df.sort_values(by='TestDate', kind='mergesort') if 'TestDate' in df.columns else df
        row = sortedDf.iloc[0] if limitsMode == 'Oldest' else sortedDf.iloc[-1]
        lsl = float(row['LSL']) if pd.notna(row['LSL']) else None
        usl = float(row['USL']) if pd.notna(row['USL']) else None
        return lsl, usl

    @classmethod
    def _buildValidLimitMask(cls, limitArr: np.ndarray, dataRef: float | None) -> np.ndarray:
        finiteMask = np.isfinite(limitArr)
        if not np.any(finiteMask):
            return np.zeros(len(limitArr), dtype=bool)

        uniqueVals = np.unique(limitArr[finiteMask])
        sentinelVals = [v for v in uniqueVals if isSentinelLimit(float(v), dataRef)]
        if not sentinelVals:
            return finiteMask
        if len(sentinelVals) == len(uniqueVals):
            return np.zeros(len(limitArr), dtype=bool)

        return finiteMask & (~np.isin(limitArr, sentinelVals))

    def _evaluateScalarFails(self, validDf:pd.DataFrame, values:np.ndarray, limitsMode:str, lslRef: float|None,
            uslRef:float|None,dataRef:float|None) -> tuple[int, int, bool]:
        
        if limitsMode == 'All' and 'LSL' in validDf.columns and 'USL' in validDf.columns:
            lslArr = validDf['LSL'].to_numpy(dtype=float)
            uslArr = validDf['USL'].to_numpy(dtype=float)
            validLslMask = self._buildValidLimitMask(lslArr, dataRef)
            validUslMask = self._buildValidLimitMask(uslArr, dataRef)

            if not (np.any(validLslMask) or np.any(validUslMask)):
                return 0, 0, False

            failLowMask = validLslMask & (values < lslArr)
            failHighMask = validUslMask & (values > uslArr)
            return int(np.sum(failLowMask)), int(np.sum(failHighMask)), True

        if lslRef is None and uslRef is None:
            return 0, 0, False

        failLow = int(np.sum(values < lslRef)) if lslRef is not None else 0
        failHigh = int(np.sum(values > uslRef)) if uslRef is not None else 0
        return failLow, failHigh, True

    def _calculateWithinSigma(self, validDf:pd.DataFrame) -> float|None:
        if len(validDf) < 2:
            return None

        orderedDf = validDf.sort_values(by='TestDate', kind='mergesort') if 'TestDate' in validDf.columns else validDf
        movingRanges: list[np.ndarray] = []

        if 'Site' in orderedDf.columns:
            for _, siteDf in orderedDf.groupby(orderedDf['Site'].astype(str), sort=False):
                vals = siteDf['Value'].to_numpy(dtype=float)
                if len(vals) >= 2:
                    movingRanges.append(np.abs(np.diff(vals)))

        if not movingRanges:
            vals = orderedDf['Value'].to_numpy(dtype=float)
            if len(vals) >= 2:
                movingRanges.append(np.abs(np.diff(vals)))

        if not movingRanges:
            return None

        allMr = np.concatenate(movingRanges)
        if allMr.size == 0:
            return None

        mrBar = float(np.mean(allMr))
        return mrBar / self.D2_MR2

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

        # If two-sided spec was expected, require both tails to have non-zero spread
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
        if metrics.validSamples != metrics.samples:
            tooltips['samples'] = f'Valid numeric samples: {metrics.validSamples:,} / {metrics.samples:,}'

        if metrics.yieldPct is not None:
            values['yield'] = f'{metrics.yieldPct:.2f}%'
            statuses['yield'] = cls._gradeYield(metrics.yieldPct)
            tooltips['yield'] = f'Pass: {metrics.validSamples - metrics.failTotal:,} / {metrics.validSamples:,}'

        if metrics.isCxCy:
            values['failLH'] = f'{metrics.failTotal:,} out'
            tooltips['failLH'] = 'Points outside active CxCy bin polygon'
            if metrics.dpmo is not None:
                values['dpmo'] = cls._formatPpm(metrics.dpmo)
                statuses['dpmo'] = cls._gradeDpmo(metrics.dpmo)
            if metrics.cxMean is not None and metrics.cyMean is not None:
                values['mean'] = f'{metrics.cxMean:.4f}, {metrics.cyMean:.4f}'
                tooltips['mean'] = f'Mean CX = {metrics.cxMean:.5f}, Mean CY = {metrics.cyMean:.5f}'
            return values, statuses, tooltips

        # Scalar test metrics
        if metrics.yieldPct is not None:
            values['failLH'] = f'{metrics.failLow:,} / {metrics.failHigh:,}'
            statuses['failLH'] = 'ok' if metrics.failTotal == 0 else 'bad'
            lowPpmStr = cls._formatPpm(metrics.failLowPpm or 0.0)
            highPpmStr = cls._formatPpm(metrics.failHighPpm or 0.0)
            tooltips['failLH'] = (
                f'Fail Low: {metrics.failLow:,} ({lowPpmStr} PPM)\n'
                f'Fail High: {metrics.failHigh:,} ({highPpmStr} PPM)'
            )

        if metrics.dpmo is not None:
            values['dpmo'] = cls._formatPpm(metrics.dpmo)
            statuses['dpmo'] = cls._gradeDpmo(metrics.dpmo)
            tooltips['dpmo'] = f'Defects Per Million Opportunities: {metrics.dpmo:,.1f} PPM'

        if metrics.lsl is not None:
            values['lsl'] = formatSiValue(metrics.lsl, precision=4)
            tooltips['lsl'] = f'LSL = {metrics.lsl:.6g}'

        if metrics.usl is not None:
            values['usl'] = formatSiValue(metrics.usl, precision=4)
            tooltips['usl'] = f'USL = {metrics.usl:.6g}'

        if metrics.mean is not None:
            values['mean'] = formatSiValue(metrics.mean, precision=4)
            medStr = formatSiValue(metrics.median, precision=4) if metrics.median is not None else '—'
            tooltips['mean'] = f'Mean = {metrics.mean:.6g}\nMedian (X50) = {medStr}'

        if metrics.sigmaOverall is not None:
            values['sigma'] = formatSiValue(metrics.sigmaOverall, precision=3)
            withinStr = (
                formatSiValue(metrics.sigmaWithin, precision=3)
                if metrics.sigmaWithin is not None
                else '—'
            )
            tooltips['sigma'] = (
                f'σ_overall (long-term) = {formatSiValue(metrics.sigmaOverall, precision=4)}\n'
                f'σ_within (MR / d2) = {withinStr}'
            )

        for key, val, tip in (
            ('pp', metrics.pp, 'Long-term Process Performance: (USL - LSL) / (6 * σ_overall)'),
            ('cp', metrics.cp, 'Short-term Process Capability: (USL - LSL) / (6 * σ_within)'),
            ('ppk', metrics.ppk, 'Long-term Performance Index (overall σ)'),
            ('cpk', metrics.cpk, 'Short-term Capability Index (Moving Range σ_within)'),
            ('ppkNp', metrics.ppkNonParametric, 'Non-parametric Ppk (ISO 22514 percentile method: P0.135, P50, P99.865)'),
        ):
            if val is not None:
                values[key] = f'{val:.2f}'
                statuses[key] = cls._gradeCapability(val)
                tooltips[key] = tip

        if metrics.toleranceUtilizationPct is not None:
            values['tolUtil'] = f'{metrics.toleranceUtilizationPct:.1f}%'
            statuses['tolUtil'] = cls._gradeTolUtilization(metrics.toleranceUtilizationPct)
            tooltips['tolUtil'] = '6 * σ_overall / (USL - LSL) × 100%  (lower is better)'

        if metrics.centeringOffsetPct is not None:
            values['centering'] = f'{metrics.centeringOffsetPct:+.1f}%'
            statuses['centering'] = cls._gradeCentering(metrics.centeringOffsetPct)
            tooltips['centering'] = (
                'Mean offset from tolerance midpoint (% of half-tolerance).\n'
                '0% = centered, +100% = at USL, -100% = at LSL.'
            )

        if metrics.siteDeltaPct is not None:
            values['siteDelta'] = f'{metrics.siteDeltaPct:.1f}%'
            statuses['siteDelta'] = cls._gradeSiteDelta(metrics.siteDeltaPct)
            absStr = formatSiValue(metrics.siteDeltaAbs, precision=3) if metrics.siteDeltaAbs is not None else '—'
            tooltips['siteDelta'] = (
                f'Max site mean shift: {absStr} ({metrics.siteDeltaPct:.2f}% of tolerance)\n'
                f'Lowest mean: Site {metrics.siteDeltaMinSite}  |  Highest mean: Site {metrics.siteDeltaMaxSite}'
            )
        elif metrics.siteDeltaAbs is not None:
            values['siteDelta'] = formatSiValue(metrics.siteDeltaAbs, precision=3)
            tooltips['siteDelta'] = (
                f'Site mean shift (one-sided spec): {values["siteDelta"]}\n'
                f'Lowest: Site {metrics.siteDeltaMinSite}  |  Highest: Site {metrics.siteDeltaMaxSite}'
            )

        if metrics.skewness is not None:
            values['skewness'] = f'{metrics.skewness:+.2f}'
            if abs(metrics.skewness) >= 1.0:
                statuses['skewness'] = 'warn'
            tooltips['skewness'] = 'Skewness (0 = symmetric; |skew| > 1 suggests using Ppk NP)'

        if metrics.kurtosis is not None:
            values['kurtosis'] = f'{metrics.kurtosis:+.2f}'
            tooltips['kurtosis'] = 'Excess Kurtosis (0 = normal, >0 = heavy tails/outliers, <0 = flat)'

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