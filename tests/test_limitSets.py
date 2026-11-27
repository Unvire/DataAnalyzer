import pandas as pd
import pytest

from src.limitSets import extractLimitSets, filterByLimitSet, filterRowsInLimits


def test_extractLimitSets_constantLimitsReturnsEmpty():
    df = pd.DataFrame({
        'Site': ['1', '1', '2'],
        'Value': [5.0, 5.1, 4.9],
        'LSL': [4.8, 4.8, 4.8],
        'USL': [5.2, 5.2, 5.2],
        'TestDate': ['2025/01/01 10:00:00'] * 3,
        'SerialNumber': ['S1', 'S2', 'S3'],
    })
    assert extractLimitSets(df) == []


def test_extractAndFilterLimitSets_separatesLedOnAndOffStates():
    # Alternating OFF [0, 10] and ON [80k, 150k] under the same test name
    df = pd.DataFrame({
        'Site': ['1', '1', '2', '2'],
        'Value': [2.0, 120_000.0, 3.5, 118_000.0],
        'LSL': [0.0, 80_000.0, 0.0, 80_000.0],
        'USL': [10.0, 150_000.0, 10.0, 150_000.0],
        'TestDate': [
            '2025/01/01 10:00:00',
            '2025/01/01 10:00:01',
            '2025/01/01 10:01:00',
            '2025/01/01 10:01:01',
        ],
        'SerialNumber': ['S1', 'S1', 'S2', 'S2'],
    })

    sets = extractLimitSets(df)
    assert len(sets) == 2
    assert sets[0].lsl == pytest.approx(0.0)
    assert sets[0].usl == pytest.approx(10.0)
    assert sets[0].count == 2
    assert sets[1].lsl == pytest.approx(80_000.0)
    assert sets[1].usl == pytest.approx(150_000.0)
    assert sets[1].count == 2

    offDf, offMode = filterByLimitSet(df, sets[0].key, sets)
    assert offMode == 'Newest'
    assert list(offDf['Value']) == pytest.approx([2.0, 3.5])

    onDf, onMode = filterByLimitSet(df, sets[1].key, sets)
    assert onMode == 'Newest'
    assert list(onDf['Value']) == pytest.approx([120_000.0, 118_000.0])


def test_extractAndFilterLimitSets_cxCyMultipleBins():
    b1 = [(0.30, 0.30), (0.32, 0.30), (0.32, 0.32), (0.30, 0.32), (0.30, 0.30)]
    b2 = [(0.40, 0.40), (0.44, 0.40), (0.44, 0.44), (0.40, 0.44), (0.40, 0.40)]
    df = pd.DataFrame({
        'Site': ['1', '1', '2'],
        'CX': [0.31, 0.42, 0.315],
        'CY': [0.31, 0.42, 0.312],
        'Boundary': [b1, b2, b1],
        'TestDate': ['2025/01/01 10:00:00', '2025/01/01 10:01:00', '2025/01/01 10:02:00'],
        'SerialNumber': ['S1', 'S2', 'S3'],
    })

    sets = extractLimitSets(df)
    assert len(sets) == 2
    assert sets[0].count == 2
    assert sets[1].count == 1

    bin2Df, mode = filterByLimitSet(df, sets[1].key, sets)
    assert mode == 'Newest'
    assert len(bin2Df) == 1
    assert bin2Df['SerialNumber'].iloc[0] == 'S2'


def test_filterRowsInLimits_excludesOutliersForStatsRecalculation():
    df = pd.DataFrame({
        'Site': ['1', '1', '1', '1'],
        'Value': [4.5, 5.0, 5.05, 5.5],
        'LSL': [4.8] * 4,
        'USL': [5.2] * 4,
        'TestDate': [
            '2025/01/01 10:00:00',
            '2025/01/01 10:01:00',
            '2025/01/01 10:02:00',
            '2025/01/01 10:03:00',
        ],
        'SerialNumber': ['S1', 'S2', 'S3', 'S4'],
    })
    cleanDf, total, excluded = filterRowsInLimits(df, limitsMode='All')
    assert total == 4
    assert excluded == 2
    assert list(cleanDf['SerialNumber']) == ['S2', 'S3']