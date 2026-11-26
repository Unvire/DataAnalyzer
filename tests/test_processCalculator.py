import numpy as np
import pandas as pd
import pytest

from src.processCalculator import ProcessParameterCalculator


def _makeScalarDf(values, sites=None, lsl=4.8, usl=5.2, dates=None):
    n = len(values)
    return pd.DataFrame({
        'Site': sites if sites is not None else ['1'] * n,
        'Value': values,
        'LSL': [lsl] * n if np.isscalar(lsl) else lsl,
        'USL': [usl] * n if np.isscalar(usl) else usl,
        'TestDate': dates if dates is not None else [f'2025/01/01 10:{i // 60:02d}:{i % 60:02d}' for i in range(n)],
        'SerialNumber': [f'SN_{i:04d}' for i in range(n)],
    })


def test_centeredNormalDistribution_metrics():
    rng = np.random.default_rng(42)
    # Centered at 5.0, sigma=0.05, tolerance [4.7, 5.3] => span=0.6, Pp ~ 2.0, TolUtil ~ 50%
    vals = rng.normal(5.0, 0.05, size=2000)
    df = _makeScalarDf(vals, lsl=4.7, usl=5.3)

    calc = ProcessParameterCalculator()
    m = calc.calculate(df, limitsMode='Newest')

    assert m.samples == 2000
    assert m.yieldPct == pytest.approx(100.0)
    assert m.dpmo == pytest.approx(0.0)
    assert m.pp == pytest.approx(2.0, abs=0.1)
    assert m.ppk == pytest.approx(2.0, abs=0.1)
    assert m.cp == pytest.approx(2.0, abs=0.15)
    assert m.cpk == pytest.approx(2.0, abs=0.15)
    assert m.ppkNonParametric == pytest.approx(2.0, abs=0.25)
    assert abs(m.centeringOffsetPct) < 3.0
    assert m.toleranceUtilizationPct == pytest.approx(50.0, abs=3.0)
    assert abs(m.skewness) < 0.15
    assert abs(m.kurtosis) < 0.3


def test_multiSiteOffset_separatesShortTermCpFromLongTermPp():
    rng = np.random.default_rng(7)
    nPerSite = 300
    # Site 1 tight around 4.90, Site 2 tight around 5.10 (span=0.40 => Site Delta = 50%)
    s1 = rng.normal(4.90, 0.01, size=nPerSite)
    s2 = rng.normal(5.10, 0.01, size=nPerSite)
    vals = np.concatenate([s1, s2])
    sites = ['1'] * nPerSite + ['2'] * nPerSite
    df = _makeScalarDf(vals, sites=sites, lsl=4.8, usl=5.2)

    calc = ProcessParameterCalculator()
    m = calc.calculate(df, limitsMode='Newest')

    # Within-site sigma ~ 0.01 => Cp ~ 6.67, while overall sigma ~ 0.10 => Pp ~ 0.66
    assert m.sigmaWithin == pytest.approx(0.01, abs=0.002)
    assert m.sigmaOverall == pytest.approx(0.10, abs=0.005)
    assert m.cp > 5.0
    assert m.pp < 0.8
    assert m.siteDeltaPct == pytest.approx(50.0, abs=2.0)
    assert m.siteDeltaMinSite == '1'
    assert m.siteDeltaMaxSite == '2'


def test_skewedDistribution_nonParametricPpkAndSkewness():
    rng = np.random.default_rng(123)
    # Right-skewed exponential data: LSL=0, USL=10
    vals = rng.exponential(scale=1.0, size=3000)
    df = _makeScalarDf(vals, lsl=0.0, usl=10.0)

    calc = ProcessParameterCalculator()
    m = calc.calculate(df, limitsMode='Newest')

    assert m.skewness > 1.5
    assert m.kurtosis > 3.0
    assert m.ppk is not None
    assert m.ppkNonParametric is not None
    # Non-parametric Ppk reacts properly to the skewed upper/lower tails instead of assuming symmetry
    assert m.ppkNonParametric != pytest.approx(m.ppk, rel=0.1)


def test_failCountsYieldDpmoAndLimitsModes():
    vals = [4.70, 4.90, 5.00, 5.25, 5.30]
    # First 3 rows had tighter USL=5.1, last 2 rows relaxed USL=5.28
    lsls = [4.8, 4.8, 4.8, 4.8, 4.8]
    usls = [5.1, 5.1, 5.1, 5.28, 5.28]
    df = _makeScalarDf(vals, lsl=lsls, usl=usls)

    calc = ProcessParameterCalculator()

    # Mode 'All': 4.70 < 4.8 (fail low), 5.30 > 5.28 (fail high) => 2 fails / 5 = 60% yield
    mAll = calc.calculate(df, limitsMode='All')
    assert mAll.failLow == 1
    assert mAll.failHigh == 1
    assert mAll.yieldPct == pytest.approx(60.0)
    assert mAll.dpmo == pytest.approx(400_000.0)

    # Mode 'Oldest' (USL=5.1): 4.70 fail low, 5.25 & 5.30 fail high => 3 fails / 5 = 40% yield
    mOldest = calc.calculate(df, limitsMode='Oldest')
    assert mOldest.failLow == 1
    assert mOldest.failHigh == 2
    assert mOldest.yieldPct == pytest.approx(40.0)


def test_oneSidedLimitWithSentinelIgnored():
    vals = [10e-6, 12e-6, 15e-6, 25e-6, 11e-6]
    # Leakage current: LSL is sentinel -1e14, USL is 20uA
    df = _makeScalarDf(vals, lsl=-1e14, usl=20e-6)

    calc = ProcessParameterCalculator()
    m = calc.calculate(df, limitsMode='Newest')

    assert m.lsl is None
    assert m.usl == pytest.approx(20e-6)
    assert m.failLow == 0
    assert m.failHigh == 1
    assert m.yieldPct == pytest.approx(80.0)
    assert m.pp is None
    assert m.cp is None
    assert m.ppk is not None
    assert m.cpk is not None
    assert m.centeringOffsetPct is None


def test_cxCyPolygonYield():
    poly = [(0.30, 0.30), (0.35, 0.30), (0.35, 0.35), (0.30, 0.35), (0.30, 0.30)]
    df = pd.DataFrame({
        'Site': ['1', '1', '2', '2'],
        'CX': [0.32, 0.30, 0.36, 0.33],   # 0.30 on edge = pass, 0.36 outside = fail
        'CY': [0.32, 0.32, 0.32, 0.29],   # 0.29 outside = fail
        'Boundary': [poly, poly, poly, poly],
        'TestDate': ['2025/01/01 10:00:00'] * 4,
        'SerialNumber': ['S1', 'S2', 'S3', 'S4'],
    })

    calc = ProcessParameterCalculator()
    m = calc.calculate(df, limitsMode='All')

    assert m.isCxCy is True
    assert m.validSamples == 4
    assert m.failTotal == 2
    assert m.yieldPct == pytest.approx(50.0)
    assert m.dpmo == pytest.approx(500_000.0)


def test_formatForStatsPanelAndEmptyHandling():
    calc = ProcessParameterCalculator()
    emptyM = calc.calculate(pd.DataFrame())
    vals, statuses, tips = calc.formatForStatsPanel(emptyM)
    assert vals == {}

    df = _makeScalarDf([5.0, 5.0, 5.0], lsl=4.8, usl=5.2)
    constM = calc.calculate(df)
    vals, statuses, _ = calc.formatForStatsPanel(constM)
    assert vals['samples'] == '3'
    assert vals['yield'] == '100.00%'
    assert statuses['yield'] == 'ok'
    assert 'ppk' not in vals