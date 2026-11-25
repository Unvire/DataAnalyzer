import pandas as pd
import pytest
from PySide6.QtCore import QCoreApplication, Qt

from src.ui.widgets.dataTableModel import PandasTableModel, RawDataFilterProxyModel


@pytest.fixture(scope='module')
def qtCoreApp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


@pytest.fixture
def sampleRawDf():
    return pd.DataFrame({
        'Site': ['1', '2', '10', '1'],
        'Value': [4.95, 12.5, 5.05, 3.123456789],
        'LSL': [4.8, 4.8, 4.8, 4.8],
        'USL': [5.2, 5.2, 5.2, 5.2],
        'TestDate': [
            '2025/01/01 10:00:00',
            '2025/01/02 11:30:00',
            '2025/01/02 12:00:00',
            '2025/01/03 08:15:00',
        ],
        'SerialNumber': ['SN_ALPHA_001', 'SN_BETA_002', 'SN_ALPHA_003', 'SN_GAMMA_004'],
    })


def test_filterAcrossAllColumnsAndMultiToken(qtCoreApp, sampleRawDf):
    model = PandasTableModel(sampleRawDf)
    proxy = RawDataFilterProxyModel()
    proxy.setSourceModel(model)

    proxy.setFilterQuery('alpha')
    assert proxy.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_ALPHA_001', 'SN_ALPHA_003']

    proxy.setFilterQuery('alpha 2025/01/02')
    assert proxy.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_ALPHA_003']


def test_regexFilteringAndInvalidRegexHandling(qtCoreApp, sampleRawDf):
    model = PandasTableModel(sampleRawDf)
    proxy = RawDataFilterProxyModel()
    proxy.setSourceModel(model)

    proxy.setFilterQuery(r'^SN_(ALPHA|GAMMA)_00[14]$', regexEnabled=True)
    assert not proxy.hasRegexError
    assert proxy.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_ALPHA_001', 'SN_GAMMA_004']

    # Invalid regex sets error flag without crashing
    proxy.setFilterQuery(r'[unclosed', regexEnabled=True)
    assert proxy.hasRegexError


def test_numericComparisonRangeAndSiSuffix(qtCoreApp, sampleRawDf):
    model = PandasTableModel(sampleRawDf)
    proxy = RawDataFilterProxyModel()
    proxy.setSourceModel(model)

    # Default numeric comparison checks Value (does NOT falsely match USL=5.2)
    proxy.setFilterQuery('>5.1')
    assert proxy.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_BETA_002']

    proxy.setFilterQuery('4.9..5.1')
    assert proxy.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_ALPHA_001', 'SN_ALPHA_003']

    # Column prefix override
    proxy.setFilterQuery('site>=2')
    assert proxy.getFilteredDataFrame()['Site'].tolist() == ['2', '10']

    # SI units
    capDf = pd.DataFrame({
        'Site': ['1', '1', '1'],
        'Value': [30e-9, 33e-9, 40e-9],
        'LSL': [25e-9, 25e-9, 25e-9],
        'USL': [45e-9, 45e-9, 45e-9],
        'TestDate': ['2025/01/01 10:00:00'] * 3,
        'SerialNumber': ['C1', 'C2', 'C3'],
    })
    model.setDataFrame(capDf)
    proxy.setFilterQuery('31n..35n')
    assert proxy.getFilteredDataFrame()['SerialNumber'].tolist() == ['C2']


def test_dateComparisonAndRange(qtCoreApp, sampleRawDf):
    model = PandasTableModel(sampleRawDf)
    proxy = RawDataFilterProxyModel()
    proxy.setSourceModel(model)

    proxy.setFilterQuery('>2025-01-01')
    assert proxy.getFilteredDataFrame()['SerialNumber'].tolist() == [
        'SN_BETA_002', 'SN_ALPHA_003', 'SN_GAMMA_004'
    ]

    proxy.setFilterQuery('2025/01/02..2025/01/02')
    assert proxy.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_BETA_002', 'SN_ALPHA_003']

    proxy.setFilterQuery('>="2025/01/02 11:45" <="2025/01/03 09:00"')
    assert proxy.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_ALPHA_003', 'SN_GAMMA_004']


def test_combinedRegexNumericAndDateQuery(qtCoreApp, sampleRawDf):
    model = PandasTableModel(sampleRawDf)
    proxy = RawDataFilterProxyModel()
    proxy.setSourceModel(model)

    proxy.setFilterQuery(r'^SN_ALPHA_\d{3}$ >5.0 2025/01/02..2025/01/03', regexEnabled=True)
    assert proxy.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_ALPHA_003']


def test_numericSortingAndFilteredCsvExport(qtCoreApp, sampleRawDf, tmp_path):
    model = PandasTableModel(sampleRawDf)
    proxy = RawDataFilterProxyModel()
    proxy.setSourceModel(model)

    proxy.sort(0, Qt.SortOrder.AscendingOrder)
    assert proxy.getFilteredDataFrame()['Site'].tolist() == ['1', '1', '2', '10']

    proxy.setFilterQuery('<5.0')
    filteredDf = proxy.getFilteredDataFrame()
    csvPath = tmp_path / 'filtered.csv'
    filteredDf.to_csv(csvPath, index=False, encoding='utf-8-sig')

    reloaded = pd.read_csv(csvPath)
    assert len(reloaded) == 2
    assert reloaded['SerialNumber'].tolist() == ['SN_ALPHA_001', 'SN_GAMMA_004']
    assert reloaded['Value'].iloc[1] == pytest.approx(3.123456789)