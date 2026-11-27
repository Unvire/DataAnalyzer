import pandas as pd
import pytest

from src.pivotAnalyzer import PivotAnalyzer, naturalSortKey


def _makeScalarTest(sites, values, dates, lsl=90.0, usl=110.0):
    n = len(values)
    return pd.DataFrame({
        'Site': sites,
        'Value': values,
        'LSL': [lsl] * n,
        'USL': [usl] * n,
        'TestDate': dates,
        'SerialNumber': [f'SN_{i:03d}' for i in range(n)],
    })


def test_naturalSortKey_ordersLedIndicesCorrectly():
    names = ['LED10 | LUM', 'LED2 | LUM', 'LED1 | LUM', 'LED11 | LUM']
    assert sorted(names, key=naturalSortKey) == [
        'LED1 | LUM',
        'LED2 | LUM',
        'LED10 | LUM',
        'LED11 | LUM',
    ]


def test_siteByTestMatrix_detectsColumnFeederAndRowSiteAnomalies():
    dates = [f'2025/01/01 10:0{i}:00' for i in range(6)]
    sites = ['1', '1', '2', '2', '3', '3']

    measurements = {
        'LED1 | LUM': _makeScalarTest(sites, [100, 100, 100, 100, 96, 96], dates),
        'LED2 | LUM': _makeScalarTest(sites, [108, 108, 108, 108, 104, 104], dates),
        'LED3 | LUM': _makeScalarTest(sites, [100, 100, 100, 100, 96, 96], dates),
    }

    analyzer = PivotAnalyzer()
    res = analyzer.analyzeMatrix(
        measurements,
        selectedTests=['LED1 | LUM', 'LED2 | LUM', 'LED3 | LUM'],
        metric='Dev. vs Group (% tol.)',
    )

    assert res.rowLabels == ['1', '2', '3']
    assert res.zMatrix.shape == (3, 3)

    assert res.zMatrix[0, 1] == pytest.approx(40.0, abs=0.1)
    assert res.zMatrix[2, 1] == pytest.approx(20.0, abs=0.1)
    assert res.colSummary[1] == pytest.approx(33.333, abs=0.1)
    assert (res.colSummary[1] - res.colSummary[0]) == pytest.approx(40.0, abs=0.1)
    assert res.rowSummary[2] < res.rowSummary[0] - 15.0

    fig = analyzer.createHeatmapFigure(res)
    assert len(fig.data) == 1
    assert fig.data[0].type == 'heatmap'


def test_cxCyMatrixAndOverlay():
    poly = [(0.30, 0.30), (0.34, 0.30), (0.34, 0.34), (0.30, 0.34), (0.30, 0.30)]
    dates = ['2025/01/01 10:00:00', '2025/01/01 10:01:00']

    dfLed1 = pd.DataFrame({
        'Site': ['1', '2'],
        'CX': [0.32, 0.32],
        'CY': [0.32, 0.32],
        'Boundary': [poly, poly],
        'TestDate': dates,
        'SerialNumber': ['S1', 'S2'],
    })
    dfLed2 = pd.DataFrame({
        'Site': ['1', '2'],
        'CX': [0.35, 0.32],
        'CY': [0.32, 0.32],
        'Boundary': [poly, poly],
        'TestDate': dates,
        'SerialNumber': ['S1', 'S2'],
    })

    analyzer = PivotAnalyzer()
    res = analyzer.analyzeMatrix(
        {'LED1 | WHITE': dfLed1, 'LED2 | WHITE': dfLed2},
        selectedTests=['LED1 | WHITE', 'LED2 | WHITE'],
        metric='Dist. from Bin Center',
    )

    assert res.isCxCy is True
    assert res.zMatrix[0, 0] == pytest.approx(0.0, abs=1e-6)
    assert res.zMatrix[0, 1] == pytest.approx(0.03, abs=1e-6)
    assert res.failMatrix[0, 1] == 1

    overlayByTest = analyzer.createOverlayFigure(
        {'LED1 | WHITE': dfLed1, 'LED2 | WHITE': dfLed2},
        selectedTests=['LED1 | WHITE', 'LED2 | WHITE'],
        colorBy='Test (Position)',
    )
    assert any(t.name == 'Bin Boundary' for t in overlayByTest.data)
    assert any(t.type == 'scattergl' for t in overlayByTest.data)

    overlayBySite = analyzer.createOverlayFigure(
        {'LED1 | WHITE': dfLed1, 'LED2 | WHITE': dfLed2},
        selectedTests=['LED1 | WHITE', 'LED2 | WHITE'],
        colorBy='Site',
    )
    assert any(t.name.startswith('Site 1') for t in overlayBySite.data)


def test_mixedScalarAndCxCyReturnsGracefulWarning():
    poly = [(0.30, 0.30), (0.34, 0.30), (0.34, 0.34), (0.30, 0.34), (0.30, 0.30)]
    measurements = {
        'V_5V': _makeScalarTest(['1'], [5.0], ['2025/01/01 10:00:00'], lsl=4.8, usl=5.2),
        'LED1': pd.DataFrame({
            'Site': ['1'],
            'CX': [0.32],
            'CY': [0.32],
            'Boundary': [poly],
            'TestDate': ['2025/01/01 10:00:00'],
            'SerialNumber': ['S1'],
        }),
    }
    analyzer = PivotAnalyzer()
    res = analyzer.analyzeMatrix(measurements, selectedTests=['V_5V', 'LED1'])
    assert 'Mixed Scalar and CxCy' in res.warningMessage
    fig = analyzer.createHeatmapFigure(res)
    assert len(fig.data) == 0

def test_sampleSizeWeightingAndMinSamplesMasking():
    # Col 1 & 3: 100 samples per site around 100.0
    # Col 2: only 3 samples per site with a huge outlier shift (-30% tol) on Site 2
    nBig = 100
    nSmall = 3
    datesBig = [f'2025/01/01 10:{i // 60:02d}:{i % 60:02d}' for i in range(nBig * 2)]
    datesSmall = [f'2025/01/01 10:00:0{i}' for i in range(nSmall * 2)]

    measurements = {
        'LED3_MAIN': _makeScalarTest(['1'] * nBig + ['2'] * nBig, [100.0] * (nBig * 2), datesBig),
        'LED4_RARE': _makeScalarTest(['1'] * nSmall + ['2'] * nSmall, [100.0] * nSmall + [94.0] * nSmall, datesSmall),
        'LED3_AUX': _makeScalarTest(['1'] * nBig + ['2'] * nBig, [100.0] * (nBig * 2), datesBig),
    }

    analyzer = PivotAnalyzer()

    # Even with minSamples=1, sample-weighted Row Avg for Site 2 is barely affected by 3 samples vs 200
    resAll = analyzer.analyzeMatrix(
        measurements,
        selectedTests=['LED3_MAIN', 'LED4_RARE', 'LED3_AUX'],
        metric='Dev. vs Group (% tol.)',
        minSamples=1,
    )
    # 3 samples at -30% out of 203 samples => ~ -0.44% instead of unweighted -10.0%
    assert abs(resAll.rowSummary[1]) < 1.0

    # With minSamples=10, LED4_RARE (n=3 per site) is masked out as NaN without distorting colorscale
    resMasked = analyzer.analyzeMatrix(
        measurements,
        selectedTests=['LED3_MAIN', 'LED4_RARE', 'LED3_AUX'],
        metric='Dev. vs Group (% tol.)',
        minSamples=10,
    )
    assert pd.isna(resMasked.zMatrix[0, 1])
    assert pd.isna(resMasked.zMatrix[1, 1])
    assert resMasked.countMatrix[1, 1] == 3
    assert resMasked.rowSummary[1] == pytest.approx(0.0)