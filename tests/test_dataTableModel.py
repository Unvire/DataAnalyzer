import pandas as pd
import pytest
from PySide6.QtCore import QCoreApplication, Qt

from src.ui.widgets.dataTableModel import PandasTableModel


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

    model.setFilterQuery('alpha')
    assert model.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_ALPHA_001', 'SN_ALPHA_003']

    model.setFilterQuery('alpha 2025/01/02')
    assert model.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_ALPHA_003']


def test_regexFilteringAndInvalidRegexHandling(qtCoreApp, sampleRawDf):
    model = PandasTableModel(sampleRawDf)

    model.setFilterQuery(r'^SN_(ALPHA|GAMMA)_00[14]$', regexEnabled=True)
    assert not model.hasRegexError
    assert model.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_ALPHA_001', 'SN_GAMMA_004']

    model.setFilterQuery(r'[unclosed', regexEnabled=True)
    assert model.hasRegexError


def test_numericComparisonRangeAndSiSuffix(qtCoreApp, sampleRawDf):
    model = PandasTableModel(sampleRawDf)

    model.setFilterQuery('>5.1')
    assert model.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_BETA_002']

    model.setFilterQuery('4.9..5.1')
    assert model.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_ALPHA_001', 'SN_ALPHA_003']

    model.setFilterQuery('site>=2')
    assert model.getFilteredDataFrame()['Site'].tolist() == ['2', '10']

    capDf = pd.DataFrame({
        'Site': ['1', '1', '1'],
        'Value': [30e-9, 33e-9, 40e-9],
        'LSL': [25e-9, 25e-9, 25e-9],
        'USL': [45e-9, 45e-9, 45e-9],
        'TestDate': ['2025/01/01 10:00:00'] * 3,
        'SerialNumber': ['C1', 'C2', 'C3'],
    })
    model.setDataFrame(capDf)
    model.setFilterQuery('31n..35n')
    assert model.getFilteredDataFrame()['SerialNumber'].tolist() == ['C2']


def test_dateComparisonAndRange(qtCoreApp, sampleRawDf):
    model = PandasTableModel(sampleRawDf)

    model.setFilterQuery('>2025-01-01')
    assert model.getFilteredDataFrame()['SerialNumber'].tolist() == [
        'SN_BETA_002', 'SN_ALPHA_003', 'SN_GAMMA_004'
    ]

    model.setFilterQuery('2025/01/02..2025/01/02')
    assert model.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_BETA_002', 'SN_ALPHA_003']

    model.setFilterQuery('>="2025/01/02 11:45" <="2025/01/03 09:00"')
    assert model.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_ALPHA_003', 'SN_GAMMA_004']


def test_combinedRegexNumericAndDateQuery(qtCoreApp, sampleRawDf):
    model = PandasTableModel(sampleRawDf)

    model.setFilterQuery(r'^SN_ALPHA_\d{3}$ >5.0 2025/01/02..2025/01/03', regexEnabled=True)
    assert model.getFilteredDataFrame()['SerialNumber'].tolist() == ['SN_ALPHA_003']


def test_numericSortingAndFilteredCsvExport(qtCoreApp, sampleRawDf, tmp_path):
    model = PandasTableModel(sampleRawDf)

    model.sort(0, Qt.SortOrder.AscendingOrder)
    assert model.getFilteredDataFrame()['Site'].tolist() == ['1', '1', '2', '10']

    model.sort(1, Qt.SortOrder.DescendingOrder)
    assert model.getFilteredDataFrame()['Value'].tolist() == pytest.approx([12.5, 5.05, 4.95, 3.123456789])

    model.setFilterQuery('<5.0')
    filteredDf = model.getFilteredDataFrame()
    csvPath = tmp_path / 'filtered.csv'
    filteredDf.to_csv(csvPath, index=False, encoding='utf-8-sig')

    reloaded = pd.read_csv(csvPath)
    assert len(reloaded) == 2
    assert reloaded['SerialNumber'].tolist() == ['SN_ALPHA_001', 'SN_GAMMA_004']
    assert reloaded['Value'].iloc[1] == pytest.approx(3.123456789)