import numpy as np
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

    # Baseline ~100 across LED1 & LED3; LED2 shifted +8 (+40% of tol=20) on ALL sites (SMT feeder)
    # Site 3 shifted -4 (-20% of tol=20) across LED1 & LED3 (uncalibrated site)
    measurements = {
        'LED1 | LUM': _makeScalarTest(sites, [100, 100, 100, 100, 96, 96], dates),
        'LED2 | LUM': _makeScalarTest(sites, [108, 108, 108, 108, 104, 104], dates),
        'LED3 | LUM': _makeScalarTest(sites, [100, 100, 100, 100, 96, 96], dates),
    }

    analyzer = PivotAnalyzer()
    res = analyzer.analyzeMatrix(
        measurements,
        selectedTests=['LED1 | LUM', 'LED2 | LUM', 'LED3 | LUM'],
        rowMode='Site',
        metric='Dev. vs Group (% tol.)',
    )

    assert res.rowLabels == ['1', '2', '3']
    assert res.zMatrix.shape == (3, 3)

    # LED2 stands out +40% on nominal sites and +33.33% overall (pulled down by Site 3's -20% shift)
    assert res.zMatrix[0, 1] == pytest.approx(40.0, abs=0.1)
    assert res.zMatrix[2, 1] == pytest.approx(20.0, abs=0.1)
    assert res.colSummary[1] == pytest.approx(33.333, abs=0.1)
    assert (res.colSummary[1] - res.colSummary[0]) == pytest.approx(40.0, abs=0.1)

    # Site 3 row average stands out negative relative to Sites 1 and 2
    assert res.rowSummary[2] < res.rowSummary[0] - 15.0

    fig = analyzer.createHeatmapFigure(res)
    assert len(fig.data) == 1
    assert fig.data[0].type == 'heatmap'


def test_batchByTestMatrix_detectsMidLotShift():
    # 4 chronological runs: first 2 at 100, last 2 shifted to 106 (reel change)
    dates = [
        '2025/01/01 08:00:00',
        '2025/01/01 09:00:00',
        '2025/01/02 08:00:00',
        '2025/01/02 09:00:00',
    ]
    sites = ['1', '1', '1', '1']
    measurements = {
        'LED1': _makeScalarTest(sites, [100.0, 100.0, 106.0, 106.0], dates),
        'LED2': _makeScalarTest(sites, [100.0, 100.0, 106.0, 106.0], dates),
    }

    analyzer = PivotAnalyzer()
    res = analyzer.analyzeMatrix(
        measurements,
        selectedTests=['LED1', 'LED2'],
        rowMode='Batch',
        batchSetting='Daily',
        metric='Centering Offset (%)',
    )

    assert res.rowLabels == ['2025/01/01', '2025/01/02']
    assert res.zMatrix[0, 0] == pytest.approx(0.0)
    assert res.zMatrix[1, 0] == pytest.approx(60.0)


def test_cxCyMatrixAndOverlay():
    poly = [(0.30, 0.30), (0.34, 0.30), (0.34, 0.34), (0.30, 0.34), (0.30, 0.30)]  # centroid = (0.32, 0.32)
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
        'CX': [0.35, 0.32],  # Site 1 LED2 is 0.03 away from center and outside bin
        'CY': [0.32, 0.32],
        'Boundary': [poly, poly],
        'TestDate': dates,
        'SerialNumber': ['S1', 'S2'],
    })

    analyzer = PivotAnalyzer()
    res = analyzer.analyzeMatrix(
        {'LED1 | WHITE': dfLed1, 'LED2 | WHITE': dfLed2},
        selectedTests=['LED1 | WHITE', 'LED2 | WHITE'],
        rowMode='Site',
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