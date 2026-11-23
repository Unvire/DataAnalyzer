import math

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


def getSiScale(values:np.ndarray|list[float], lsl:float|None=None, usl:float|None=None) -> tuple[str, float]:
    '''
    Returns (si_prefix, multiplier) such that scaled_value = raw_value * multiplier.
    Example: values around 33e-9 -> ('n', 1e9) so 33e-9 * 1e9 == 33.0.
    '''
    arr = np.asarray(values, dtype=float)
    finite = arr[np.isfinite(arr)]

    reference = 0.0
    if finite.size > 0:
        sample = finite
        if (
            lsl is not None and usl is not None
            and np.isfinite(lsl) and np.isfinite(usl)
            and lsl < usl
        ):
            inLimits = finite[(finite >= lsl) & (finite <= usl)]
            if inLimits.size > 0:
                sample = inLimits

        nonZeroAbs = np.abs(sample[sample != 0.0])
        if nonZeroAbs.size > 0:
            reference = float(np.percentile(nonZeroAbs, 75))

    if reference == 0.0:
        limitCandidates = [abs(v) for v in (lsl, usl) if v is not None and np.isfinite(v) and v != 0.0]
        if limitCandidates:
            reference = max(limitCandidates)

    if reference == 0.0 or not math.isfinite(reference):
        return '', 1.0

    exponent = int(math.floor(math.log10(reference) / 3.0) * 3)
    exponent = max(MIN_SI_EXP, min(MAX_SI_EXP, exponent))

    prefix = SI_PREFIXES[exponent]
    multiplier = 10.0 ** (-exponent)
    return prefix, multiplier


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