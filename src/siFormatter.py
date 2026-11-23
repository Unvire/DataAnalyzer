import math
from typing import Sequence

import numpy as np


SI_PREFIXES: dict[int, str] = {
    -15: 'f',
    -12: 'p',
    -9: 'n',
    -6: 'µ',
    -3: 'm',
    0: '',
    3: 'k',
    6: 'M',
    9: 'G',
    12: 'T',
}

MIN_SI_EXP = min(SI_PREFIXES.keys())
MAX_SI_EXP = max(SI_PREFIXES.keys())
SENTINEL_LIMIT_ABS = 1e9


def isSentinelLimit(limit:float|None, dataRef:float|None=None) -> bool:
    if limit is None or not np.isfinite(limit):
        return True
    
    absLim = abs(limit)
    if absLim >= 1e12:
        return True
    
    if absLim >= SENTINEL_LIMIT_ABS:
        if dataRef is None or dataRef == 0.0 or (absLim / max(abs(dataRef), 1e-12)) >= 1e4:
            return True
        
    if dataRef is not None and abs(dataRef) > 0.0:
        if absLim / abs(dataRef) >= 1e8:
            return True
        
    return False


def getSiScale(values:np.ndarray|Sequence[float], lsl:float|None=None, usl:float|None=None) -> tuple[str, float]:
    """
    Returns (si_prefix, multiplier) such that scaled_value = raw_value * multiplier.
    Filters out dummy sentinel limits (e.g. 1e14) before determining magnitude.
    """
    arr = np.asarray(values, dtype=float)
    finite = arr[np.isfinite(arr)]

    nonZeroFinite = np.abs(finite[finite != 0.0])
    dataRef = float(np.percentile(nonZeroFinite, 75)) if nonZeroFinite.size > 0 else None

    validLsl = lsl if (lsl is not None and not isSentinelLimit(lsl, dataRef)) else None
    validUsl = usl if (usl is not None and not isSentinelLimit(usl, dataRef)) else None

    reference = 0.0
    if finite.size > 0:
        sample = finite

        if validLsl is not None and validUsl is not None and validLsl < validUsl:
            inLimits = finite[(finite >= validLsl) & (finite <= validUsl)]
            if inLimits.size > 0:
                sample = inLimits

        elif validLsl is not None:
            inLimits = finite[finite >= validLsl]
            if inLimits.size > 0:
                sample = inLimits

        elif validUsl is not None:
            inLimits = finite[finite <= validUsl]
            if inLimits.size > 0:
                sample = inLimits

        nonZeroAbs = np.abs(sample[sample != 0.0])
        if nonZeroAbs.size > 0:
            reference = float(np.percentile(nonZeroAbs, 75))

    if reference == 0.0:
        limitCandidates = [abs(v) for v in (validLsl, validUsl) if v is not None and np.isfinite(v) and v != 0.0]
        if limitCandidates:
            reference = max(limitCandidates)

    if reference == 0.0 or not math.isfinite(reference):
        return '', 1.0

    exponent = int(math.floor(math.log10(reference) / 3.0) * 3)
    exponent = max(MIN_SI_EXP, min(MAX_SI_EXP, exponent))

    prefix = SI_PREFIXES[exponent]
    multiplier = 10.0 ** (-exponent)
    return prefix, multiplier


def shouldAutoLogScale(values:np.ndarray|Sequence[float], lsl:float|None=None, usl:float|None=None, ratioThreshold:float=1000.0) -> bool:
    """
    Returns True only if values/limits are strictly positive, not dummy sentinels,
    and cover at least 3 orders of magnitude (ratio >= 1000).
    """
    arr = np.asarray(values, dtype=float)
    finite = arr[np.isfinite(arr)]
    
    if finite.size == 0 or np.any(finite <= 0):
        return False

    dataMin = float(np.min(finite))
    dataMax = float(np.max(finite))

    if dataMin > 0 and (dataMax / dataMin) >= ratioThreshold:
        return True

    if lsl is not None and usl is not None:
        if lsl > 0 and usl > 0 and (usl / lsl) >= ratioThreshold:
            return True

    return False


def formatAxisTitle(baseTitle: str, prefix: str, unit: str = '') -> str:
    combinedUnit = f'{prefix}{unit}'
    return f'{baseTitle} [{combinedUnit}]' if combinedUnit else baseTitle


def formatSiValue(value: float, precision: int = 4, unit: str = '') -> str:
    if not np.isfinite(value):
        return str(value)
    
    if value == 0.0:
        return f'0 {unit}'.strip()
    
    prefix, multiplier = getSiScale([value])
    scaled = value * multiplier
    suffix = f'{prefix}{unit}'
    return f'{scaled:.{precision}g} {suffix}'.strip()

def calculateLinthresh(values: np.ndarray, default: float = 1.0) -> float:
    arr = np.asarray(values, dtype=float)
    finite = arr[np.isfinite(arr)]
    nonZero = np.abs(finite[finite != 0.0])
    if nonZero.size == 0:
        return default
    
    minVal = float(np.min(nonZero))
    exp = int(math.floor(math.log10(minVal)))
    return max(10.0 ** exp, 1e-12)


def symlogTransform(y:np.ndarray|float, linthresh:float=1.0) -> np.ndarray|float:
    """
    Symmetrical log transform:
    For |y| <= linthresh: y / linthresh
    For |y| > linthresh: sign(y) * (1 + log10(|y| / linthresh))
    """
    isScalar = np.isscalar(y)
    arr = np.asarray(y, dtype=float)

    absY = np.abs(arr)
    linearMask = absY <= linthresh

    out = np.empty_like(arr, dtype=float)
    out[linearMask] = arr[linearMask] / max(linthresh, 1e-12)

    logMask = ~linearMask
    safeDiv = np.maximum(absY[logMask] / max(linthresh, 1e-12), 1e-12)
    out[logMask] = np.sign(arr[logMask]) * (1.0 + np.log10(safeDiv))

    return float(out) if isScalar else out


def generateSymlogTicks(minVal:float, maxVal:float, linthresh:float=1.0) -> tuple[list[float], list[str]]:
    tickPairs: list[tuple[float, str]] = [(0.0, '0')]

    if maxVal > 0:
        maxDecade = int(math.ceil(math.log10(max(maxVal / linthresh, 1.0))))
        for d in range(0, maxDecade + 1):
            val = linthresh * (10.0 ** d)
            transformedCoord = 1.0 + d
            tickPairs.append((transformedCoord, f'{val:.4g}'))

    if minVal < 0:
        minDecade = int(math.ceil(math.log10(max(abs(minVal) / linthresh, 1.0))))
        for d in range(0, minDecade + 1):
            val = -linthresh * (10.0 ** d)
            transformedCoord = -(1.0 + d)
            tickPairs.append((transformedCoord, f'{val:.4g}'))

    tickPairs.sort(key=lambda item: item[0])

    tickVals = [p[0] for p in tickPairs]
    tickText = [p[1] for p in tickPairs]
    return tickVals, tickText