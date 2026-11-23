import numpy as np
import pandas as pd
import pytest

from src.plotGenerator import PlotlyChartGenerator


@pytest.fixture
def scalarDf():
    return pd.DataFrame({
        'Site': ['1', '1', '2', '2'],
        'Value': [4.95, 5.05, 5.00, 5.10],
        'LSL': [4.8, 4.8, 4.8, 4.8],
        'USL': [5.2, 5.2, 5.2, 5.2],
        'TestDate': [
            '2025/01/01 10:00:00',
            '2025/01/01 10:01:00',
            '2025/01/01 10:00:30',
            '2025/01/01 10:01:30',
        ],
        'SerialNumber': ['SN1', 'SN2', 'SN3', 'SN4'],
    })


@pytest.fixture
def cxcyDf():
    boundary = [(0.30, 0.30), (0.35, 0.30), (0.35, 0.35), (0.30, 0.35), (0.30, 0.30)]
    return pd.DataFrame({
        'Site': ['1', '2'],
        'CX': [0.32, 0.33],
        'CY': [0.32, 0.34],
        'Boundary': [boundary, boundary],
        'TestDate': ['2025/01/01 10:00:00', '2025/01/01 10:01:00'],
        'SerialNumber': ['SN1', 'SN2'],
    })


def test_sequencePlot_createsSiteTracesAndLimits(scalarDf):
    gen = PlotlyChartGenerator()
    fig = gen.createPlot(scalarDf, 'VDD_5V', plotType='Sequence', orderBy='Date', limitsMode='All')
    traceNames = [t.name for t in fig.data]
    assert 'Site 1 (2)' in traceNames
    assert 'Site 2 (2)' in traceNames
    assert 'LSL' in traceNames
    assert 'USL' in traceNames


def test_capabilityPlot_handlesNormalAndConstantData(scalarDf):
    gen = PlotlyChartGenerator()
    fig = gen.createPlot(scalarDf, 'VDD_5V', plotType='Capability (Histogram)', limitsMode='Newest')
    assert any(t.type == 'histogram' for t in fig.data)
    assert any(t.name == 'Normal Fit' for t in fig.data)

    constDf = scalarDf.copy()
    constDf['Value'] = 5.0
    figConst = gen.createPlot(constDf, 'CONST', plotType='Capability (Histogram)')
    assert any(t.type == 'histogram' for t in figConst.data)
    assert not any(t.name == 'Normal Fit' for t in figConst.data)


def test_boxplotPerSite(scalarDf):
    gen = PlotlyChartGenerator()
    fig = gen.createPlot(scalarDf, 'VDD_5V', plotType='Boxplot', valuesInLimits=True)
    assert len(fig.data) == 2
    assert all(t.type == 'box' for t in fig.data)


def test_cxCyPlot_deduplicatesBoundaries(cxcyDf):
    gen = PlotlyChartGenerator()
    fig = gen.createPlot(cxcyDf, 'LED_CXCY', valuesInLimits=True)
    boundaryTraces = [t for t in fig.data if t.name.startswith('Bin Boundary')]
    assert len(boundaryTraces) == 1


def test_sequencePlot_10000pointsUsesWebgl():
    n = 10_000
    df = pd.DataFrame({
        'Site': ['1'] * n,
        'Value': np.random.normal(3.3, 0.05, n),
        'LSL': [3.0] * n,
        'USL': [3.6] * n,
        'TestDate': ['2025/01/01 10:00:00'] * n,
        'SerialNumber': [f'SN_{i}' for i in range(n)],
    })
    gen = PlotlyChartGenerator()
    fig = gen.createPlot(df, 'V_CORE', plotType='Sequence', limitsMode='Newest')
    assert fig.data[0].type == 'scattergl'
    assert len(fig.data[0].y) == n