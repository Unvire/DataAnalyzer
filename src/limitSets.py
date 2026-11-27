from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from src.measurementEngine import MeasurementEngine
from src.processCalculator import ProcessParameterCalculator
from src.siFormatter import formatSiValue


LIMIT_SET_PREFIX = '__LIMIT_SET__:'


@dataclass(frozen=True)
class LimitSetOption:
    key: str
    label: str
    count: int
    isCxCy: bool
    lsl: float | None = None
    usl: float | None = None
    boundaryKey: tuple[tuple[float, float], ...] | None = None


def _isConstantFloatArray(arr:np.ndarray) -> bool:
    if arr.size <= 1:
        return True
    
    first = float(arr[0])
    if math.isnan(first):
        return bool(np.all(np.isnan(arr)))
    
    return bool(np.all(arr == first))


def _normalizeScalarLimitArrays(df:pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns (normLsl, normUsl, validLsl, validUsl) where sentinel/NaN limits
    are replaced with -inf / +inf for exact vectorized grouping & filtering.
    """
    vals = df['Value'].to_numpy(dtype=float)
    finiteVals = vals[np.isfinite(vals)]
    nonZero = np.abs(finiteVals[finiteVals != 0.0])
    dataRef = float(np.median(nonZero)) if nonZero.size > 0 else None

    lslArr = df['LSL'].to_numpy(dtype=float)
    uslArr = df['USL'].to_numpy(dtype=float)

    validLsl = ProcessParameterCalculator._buildValidLimitMask(lslArr, dataRef)
    validUsl = ProcessParameterCalculator._buildValidLimitMask(uslArr, dataRef)

    normLsl = np.where(validLsl, lslArr, -np.inf)
    normUsl = np.where(validUsl, uslArr, np.inf)
    return normLsl, normUsl, validLsl, validUsl


def _normalizeBoundaryKey(poly) -> tuple[tuple[float, float], ...]|None:
    if poly is None or len(poly) < 3:
        return None
    return tuple((round(float(p[0]), 6), round(float(p[1]), 6)) for p in poly)


def _formatScalarRange(lsl:float|None, usl:float|None) -> str:
    if lsl is not None and usl is not None:
        return f'[{formatSiValue(lsl, precision=4)}, {formatSiValue(usl, precision=4)}]'
    
    if lsl is not None:
        return f'[≥ {formatSiValue(lsl, precision=4)}]'
    
    if usl is not None:
        return f'[≤ {formatSiValue(usl, precision=4)}]'
    
    return '[No limits]'


def extractLimitSets(df:pd.DataFrame|None) -> list[LimitSetOption]:
    """
    Detects distinct limit pairs (scalar) or bin polygons (CxCy) within a test.
    Returns an empty list when the test has only a single consistent limit set.
    """
    if df is None or df.empty:
        return []

    if MeasurementEngine.isCxCyDataFrame(df):
        if 'Boundary' not in df.columns:
            return []

        boundaries = df['Boundary'].tolist()
        counts: dict[tuple[tuple[float, float], ...], int] = {}
        order: list[tuple[tuple[float, float], ...]] = []

        prevObj = None
        prevKey = None
        for poly in boundaries:
            if poly is prevObj:
                key = prevKey

            else:
                key = _normalizeBoundaryKey(poly)
                prevObj = poly
                prevKey = key

            if key is None:
                continue

            if key not in counts:
                counts[key] = 0
                order.append(key)
            counts[key] += 1

        if len(order) <= 1:
            return []

        options: list[LimitSetOption] = []
        for idx, polyKey in enumerate(order):
            pts = polyKey[:-1] if (len(polyKey) > 1 and polyKey[0] == polyKey[-1]) else polyKey
            cxAvg = sum(p[0] for p in pts) / len(pts)
            cyAvg = sum(p[1] for p in pts) / len(pts)
            cnt = counts[polyKey]
            options.append(
                LimitSetOption(
                    key=f'{LIMIT_SET_PREFIX}{idx}',
                    label=f'Bin #{idx + 1}: ({cxAvg:.3f}, {cyAvg:.3f}) (n={cnt:,})',
                    count=cnt,
                    isCxCy=True,
                    boundaryKey=polyKey,
                )
            )
        return options

    if 'Value' not in df.columns or 'LSL' not in df.columns or 'USL' not in df.columns:
        return []

    lslRaw = df['LSL'].to_numpy(dtype=float)
    uslRaw = df['USL'].to_numpy(dtype=float)
    # Fast O(N) exit when limits never vary across the test
    if _isConstantFloatArray(lslRaw) and _isConstantFloatArray(uslRaw):
        return []

    normLsl, normUsl, _, _ = _normalizeScalarLimitArrays(df)
    pairs = np.column_stack((normLsl, normUsl))
    uniquePairs, counts = np.unique(pairs, axis=0, return_counts=True)

    if len(uniquePairs) <= 1:
        return []

    # Sort ascending by (LSL, USL) so OFF state naturally precedes ON state
    sortOrder = np.lexsort((uniquePairs[:, 1], uniquePairs[:, 0]))
    options = []
    for idx, pos in enumerate(sortOrder):
        rawL = float(uniquePairs[pos, 0])
        rawU = float(uniquePairs[pos, 1])
        lslVal = rawL if math.isfinite(rawL) else None
        uslVal = rawU if math.isfinite(rawU) else None
        cnt = int(counts[pos])
        rangeText = _formatScalarRange(lslVal, uslVal)
        options.append(
            LimitSetOption(
                key=f'{LIMIT_SET_PREFIX}{idx}',
                label=f'Limit #{idx + 1}: {rangeText} (n={cnt:,})',
                count=cnt,
                isCxCy=False,
                lsl=lslVal,
                usl=uslVal,
            )
        )
    return options


def filterByLimitSet(df: pd.DataFrame|None, limitMode:str, limitSets:list[LimitSetOption]) -> tuple[pd.DataFrame, str]:
    """
    If limitMode selects a specific LimitSetOption, filters df strictly to rows
    matching that limit pair/polygon and returns (filteredDf, 'Newest').
    Otherwise returns (df, limitMode) unchanged.
    """
    if df is None or df.empty or not limitMode.startswith(LIMIT_SET_PREFIX):
        return (df if df is not None else pd.DataFrame()), limitMode

    selected = next((opt for opt in limitSets if opt.key == limitMode), None)
    if selected is None:
        return df, 'All'

    if selected.isCxCy:
        if 'Boundary' not in df.columns or selected.boundaryKey is None:
            return df, 'All'
        targetKey = selected.boundaryKey
        boundaries = df['Boundary'].tolist()
        mask = np.zeros(len(boundaries), dtype=bool)
        prevObj = None
        prevMatch = False
        for i, poly in enumerate(boundaries):
            if poly is prevObj:
                mask[i] = prevMatch
            else:
                prevMatch = _normalizeBoundaryKey(poly) == targetKey
                prevObj = poly
                mask[i] = prevMatch
        return df[mask], 'Newest'

    normLsl, normUsl, _, _ = _normalizeScalarLimitArrays(df)
    targetLsl = selected.lsl if selected.lsl is not None else -np.inf
    targetUsl = selected.usl if selected.usl is not None else np.inf

    if math.isfinite(targetLsl):
        lslMask = np.isfinite(normLsl) & np.isclose(normLsl, targetLsl, rtol=1e-9, atol=1e-15)
    else:
        lslMask = np.isneginf(normLsl)

    if math.isfinite(targetUsl):
        uslMask = np.isfinite(normUsl) & np.isclose(normUsl, targetUsl, rtol=1e-9, atol=1e-15)
    else:
        uslMask = np.isposinf(normUsl)

    return df[lslMask & uslMask], 'Newest'


def filterRowsInLimits(df:pd.DataFrame|None, limitsMode:str='All', calculator: ProcessParameterCalculator|None=None) -> tuple[pd.DataFrame, int, int]:
    """
    Filters DataFrame to measurements strictly within specification limits.
    Returns (inLimitsDf, totalRows, excludedOutliersCount).
    """
    if df is None or df.empty:
        return pd.DataFrame(), 0, 0

    calc = calculator or ProcessParameterCalculator()
    _, failMask = calc.calculateWithFailMask(df, limitsMode=limitsMode, includeShapeStats=False)
    totalRows = len(df)
    excludedCount = int(np.sum(failMask))
    if excludedCount == 0:
        return df, totalRows, 0
    
    return df[~failMask], totalRows, excludedCount