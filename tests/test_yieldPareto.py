import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import QCoreApplication, Qt

from src.ui.widgets.yieldParetoTab import YieldSummaryTableModel
from src.yieldParetoAnalyzer import YieldParetoAnalyzer


@pytest.fixture(scope='module')
def qtCoreApp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


@pytest.fixture
def sampleBatchMeasurements():
    dates = [
        '2025/01/01 10:00:00',
        '2025/01/01 10:01:00',
        '2025/01/01 10:02:00',
        '2025/01/01 10:03:00',
    ]
    sns = ['SN1', 'SN2', 'SN3', 'SN4']

    # Test A: 2 failures (1 low on SN1, 1 high on SN4)
    dfA = pd.DataFrame({
        'Site': ['1', '1', '2', '2'],
        'Value': [4.70, 5.00, 5.02, 5.30],
        'LSL': [4.8] * 4,
        'USL': [5.2] * 4,
        'TestDate': dates,
        'SerialNumber': sns,
    })

    # Test B: 1 failure (SN4 also fails here -> board SN4 counts once in failedRuns)
    dfB = pd.DataFrame({
        'Site': ['1', '1', '2', '2'],
        'Value': [100.0, 100.5, 100.2, 115.0],
        'LSL': [95.0] * 4,
        'USL': [105.0] * 4,
        'TestDate': dates,
        'SerialNumber': sns,
    })

    # Test C: 100% pass, but offset between sites
    dfC = pd.DataFrame({
        'Site': ['1', '1', '2', '2'],
        'Value': [3.11, 3.12, 3.48, 3.49],
        'LSL': [3.1] * 4,
        'USL': [3.5] * 4,
        'TestDate': dates,
        'SerialNumber': sns,
    })

    # Test D: CxCy with 1 point out of bin (SN2)
    poly = [(0.30, 0.30), (0.35, 0.30), (0.35, 0.35), (0.30, 0.35), (0.30, 0.30)]
    dfD = pd.DataFrame({
        'Site': ['1', '1', '2', '2'],
        'CX': [0.32, 0.38, 0.33, 0.34],
        'CY': [0.32, 0.32, 0.33, 0.34],
        'Boundary': [poly] * 4,
        'TestDate': dates,
        'SerialNumber': sns,
    })

    return {'VDD_5V': dfA, 'R_100': dfB, 'V_3V3': dfC, 'LED_CXCY': dfD}


def test_yieldParetoAnalyzer_batchMetricsAndBoardYield(sampleBatchMeasurements):
    analyzer = YieldParetoAnalyzer()
    res = analyzer.analyze(sampleBatchMeasurements, site='All sites', limitsMode='All')

    assert res.totalTests == 4
    assert res.failingTestsCount == 3
    assert res.totalFails == 4  # 2 in VDD_5V, 1 in R_100, 1 in LED_CXCY
    # Failed boards: SN1 (VDD_5V), SN2 (LED_CXCY), SN4 (VDD_5V & R_100) => 3/4 failed => 25% board yield
    assert res.totalRuns == 4
    assert res.failedRuns == 3
    assert res.boardYieldPct == pytest.approx(25.0)

    # Sorted descending by Fails
    assert res.summaryDf['TestName'].iloc[0] == 'VDD_5V'
    assert res.summaryDf['Fails'].iloc[0] == 2
    assert res.summaryDf['FailLow'].iloc[0] == 1
    assert res.summaryDf['FailHigh'].iloc[0] == 1
    assert res.worstYieldTest == 'VDD_5V'
    assert res.worstYieldPct == pytest.approx(50.0)


def test_yieldParetoAnalyzer_siteFilter(sampleBatchMeasurements):
    analyzer = YieldParetoAnalyzer()
    resSite1 = analyzer.analyze(sampleBatchMeasurements, site='1', limitsMode='Newest')

    # On Site 1 (SN1, SN2): VDD_5V has 1 fail (SN1), LED_CXCY has 1 fail (SN2), R_100 has 0 fails
    assert resSite1.failingTestsCount == 2
    assert resSite1.totalFails == 2
    assert resSite1.totalRuns == 2
    assert resSite1.failedRuns == 2
    assert resSite1.boardYieldPct == pytest.approx(0.0)


def test_paretoFigures_allModesAndTopNBucketing(sampleBatchMeasurements):
    analyzer = YieldParetoAnalyzer()
    res = analyzer.analyze(sampleBatchMeasurements)

    # Defect Pareto with Top 2 aggregates the 3rd failing test into 'Other (1 tests)'
    figPareto = analyzer.createParetoFigure(res.summaryDf, metric='Defect Pareto (Fails)', topN=2)
    cumTrace = [t for t in figPareto.data if t.name == 'Cumulative %'][0]
    assert cumTrace.y[-1] == pytest.approx(100.0)
    assert any('Other (' in label for label in cumTrace.x)

    # Weakest Capability mode
    figPpk = analyzer.createParetoFigure(res.summaryDf, metric='Weakest Capability (Ppk)', topN=10)
    assert len(figPpk.data) == 1
    assert figPpk.data[0].type == 'bar'

    # Highest Site Delta mode (V_3V3 has large delta between Site 1 ~3.225 and Site 2 ~3.385)
    figDelta = analyzer.createParetoFigure(res.summaryDf, metric='Highest Site Delta (%)', topN=10)
    assert len(figDelta.data) == 1
    assert figDelta.data[0].x[0] == 'V_3V3'


def test_paretoFigure_allPassShowsHelpfulMessage():
    analyzer = YieldParetoAnalyzer()
    dfPass = pd.DataFrame({
        'Site': ['1', '1'],
        'Value': [5.0, 5.01],
        'LSL': [4.8, 4.8],
        'USL': [5.2, 5.2],
        'TestDate': ['2025/01/01 10:00:00', '2025/01/01 10:01:00'],
        'SerialNumber': ['S1', 'S2'],
    })
    res = analyzer.analyze({'PASS_TEST': dfPass})
    fig = analyzer.createParetoFigure(res.summaryDf, metric='Defect Pareto (Fails)')
    assert len(fig.data) == 0
    assert '100% Yield' in fig.layout.annotations[0].text


def test_yieldSummaryTableModel_filteringSortingAndLookup(qtCoreApp, sampleBatchMeasurements):
    analyzer = YieldParetoAnalyzer()
    res = analyzer.analyze(sampleBatchMeasurements)

    model = YieldSummaryTableModel(res.summaryDf)
    assert model.rowCount() == 4
    assert model.getTestNameAtRow(0) == 'VDD_5V'

    # Filter using numeric column alias
    model.setFilterQuery('fails>1')
    assert model.rowCount() == 1
    assert model.getTestNameAtRow(0) == 'VDD_5V'

    # Clear and sort ascending by YieldPct
    model.setFilterQuery('')
    yieldCol = model.getColumnNames().index('YieldPct')
    model.sort(yieldCol, Qt.SortOrder.AscendingOrder)
    assert model.getTestNameAtRow(0) == 'VDD_5V'