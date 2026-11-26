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
    # Sites are added before limit traces
    assert traceNames.index('Site 2 (2)') < traceNames.index('LSL')


def test_capabilityPlot_handlesNormalAndConstantData(scalarDf):
    gen = PlotlyChartGenerator()
    fig = gen.createPlot(scalarDf, 'VDD_5V', plotType='Capability (Histogram)', limitsMode='Newest')

    assert any(t.type == 'histogram' for t in fig.data)
    assert any(t.name and t.name.startswith('Overall Fit') for t in fig.data)

    constDf = scalarDf.copy()
    constDf['Value'] = 5.0
    figConst = gen.createPlot(constDf, 'CONST', plotType='Capability (Histogram)')

    assert any(t.type == 'histogram' for t in figConst.data)
    assert not any(t.name and t.name.startswith('Overall Fit') for t in figConst.data)


def test_boxplotPerSite(scalarDf):
    gen = PlotlyChartGenerator()
    fig = gen.createPlot(scalarDf, 'VDD_5V', plotType='Boxplot', valuesInLimits=True)
    assert len(fig.data) == 2
    assert all(t.type == 'box' for t in fig.data)


def test_cxCyPlot_deduplicatesBoundariesAndSupportsLimitsModes(cxcyDf):
    gen = PlotlyChartGenerator()
    figAll = gen.createPlot(cxcyDf, 'LED_CXCY', valuesInLimits=True, limitsMode='All')
    boundaryTraces = [t for t in figAll.data if t.name.startswith('Bin Boundary')]
    assert len(boundaryTraces) == 1

    # Two different boundaries across time
    b1 = [(0.30, 0.30), (0.34, 0.30), (0.34, 0.34), (0.30, 0.34), (0.30, 0.30)]
    b2 = [(0.31, 0.31), (0.35, 0.31), (0.35, 0.35), (0.31, 0.35), (0.31, 0.31)]
    diffDf = cxcyDf.copy()
    diffDf['Boundary'] = [b1, b2]

    figNewest = gen.createPlot(diffDf, 'LED_CXCY', limitsMode='Newest')
    assert [t.name for t in figNewest.data if 'Bin' in t.name] == ['Active Bin (Newest)']

    figOldest = gen.createPlot(diffDf, 'LED_CXCY', limitsMode='Oldest')
    assert [t.name for t in figOldest.data if 'Bin' in t.name] == ['Initial Bin (Oldest)']


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


def test_siScalingFor33nfCapacitance():
    df = pd.DataFrame({
        'Site': ['1', '1', '1'],
        'Value': [32.5e-9, 33.0e-9, 33.5e-9],
        'LSL': [30.0e-9, 30.0e-9, 30.0e-9],
        'USL': [36.0e-9, 36.0e-9, 36.0e-9],
        'TestDate': ['2025/01/01 10:00:00', '2025/01/01 10:01:00', '2025/01/01 10:02:00'],
        'SerialNumber': ['SN1', 'SN2', 'SN3'],
    })
    gen = PlotlyChartGenerator()

    seqFig = gen.createPlot(df, 'C12 33nF', plotType='Sequence', limitsMode='All')
    assert seqFig.layout.yaxis.title.text == 'Measured Value [n]'
    assert list(seqFig.data[0].y) == pytest.approx([32.5, 33.0, 33.5])

    capFig = gen.createPlot(df, 'C12 33nF', plotType='Capability (Histogram)', limitsMode='Newest')
    assert capFig.layout.xaxis.title.text == 'Measured Value [n]'
    assert list(capFig.data[0].x) == pytest.approx([32.5, 33.0, 33.5])


def test_symlogAppliedForZeroAndNegativeDataOnSequenceAndBoxplot():
    df = pd.DataFrame({
        'Site': ['1', '1', '2', '2'],
        'Value': [-10.0, 0.0, 1.0, 100.0],
        'LSL': [-1e14] * 4,   # sentinel lower limit
        'USL': [200.0] * 4,
        'TestDate': [
            '2025/01/01 10:00:00',
            '2025/01/01 10:01:00',
            '2025/01/01 10:02:00',
            '2025/01/01 10:03:00',
        ],
        'SerialNumber': ['S1', 'S2', 'S3', 'S4'],
    })
    gen = PlotlyChartGenerator()

    seqFig = gen.createPlot(df, 'OFFSET_CURRENT', plotType='Sequence', logScale=True, valuesInLimits=True)
    assert '(Symlog)' in seqFig.layout.yaxis.title.text
    assert seqFig.layout.yaxis.tickmode == 'array'
    assert '0' in seqFig.layout.yaxis.ticktext

    boxFig = gen.createPlot(df, 'OFFSET_CURRENT', plotType='Boxplot', logScale=True, valuesInLimits=True)
    assert '(Symlog)' in boxFig.layout.yaxis.title.text
    assert boxFig.layout.yaxis.tickmode == 'array'


def test_highlightSerialNumberAcrossPlotTypes(scalarDf, cxcyDf):
    gen = PlotlyChartGenerator()

    # Sequence highlight dims population and puts WebGL diamond overlay on top
    seqFig = gen.createPlot(scalarDf, 'VDD_5V', plotType='Sequence', highlightSn='SN1, SN3')
    snTraces = [t for t in seqFig.data if t.name.startswith('SN: ')]
    assert len(snTraces) == 1
    assert snTraces[0].type == 'scattergl'
    assert seqFig.data[-1].name.startswith('SN: ')
    assert len(snTraces[0].y) == 2
    assert seqFig.data[0].marker.opacity == pytest.approx(0.15)

    # Boxplot highlight overlays matched SNs on matching site boxes
    boxFig = gen.createPlot(scalarDf, 'VDD_5V', plotType='Boxplot', highlightSn='SN2')
    boxSnTraces = [t for t in boxFig.data if t.name.startswith('SN: ')]
    assert len(boxSnTraces) == 1
    assert list(boxSnTraces[0].x) == ['Site 1 (2)']
    assert list(boxSnTraces[0].y) == pytest.approx([5.05])

    # Capability highlight places markers at y=0 for matched SNs
    capFig = gen.createPlot(scalarDf, 'VDD_5V', plotType='Capability (Histogram)', highlightSn='SN4')
    capSnTraces = [t for t in capFig.data if t.name.startswith('SN: ')]
    assert len(capSnTraces) == 1
    assert list(capSnTraces[0].x) == pytest.approx([5.10])

    # CxCy highlight overlays matched LED measurement in WebGL on top
    cxFig = gen.createPlot(cxcyDf, 'LED_CXCY', highlightSn='SN2')
    cxSnTraces = [t for t in cxFig.data if t.name.startswith('SN: ')]
    assert len(cxSnTraces) == 1
    assert cxSnTraces[0].type == 'scattergl'
    assert cxFig.data[-1].name.startswith('SN: ')
    assert list(cxSnTraces[0].x) == pytest.approx([0.33])
    assert list(cxSnTraces[0].y) == pytest.approx([0.34])


def test_highlightSerialNumberNoMatchDoesNotDimPlot(scalarDf):
    gen = PlotlyChartGenerator()
    seqFig = gen.createPlot(scalarDf, 'VDD_5V', plotType='Sequence', highlightSn='NON_EXISTENT')
    assert not any(t.name.startswith('SN: ') for t in seqFig.data)
    assert seqFig.data[0].marker.opacity == pytest.approx(0.85)