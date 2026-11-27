import pytest
from src.dataProcessorFwk import FwkDataProcessor


@pytest.fixture
def fwkHeaderAndLines():
    lines = [
        'Operator;admin;;;;;;;;;',
        'UUT Serial Number;014250302025804;;;;;;;;;',
        'Test Socket Index;1;;;;;;;;;',
        ';;;;;;;;;;',
        'Sequence;Step Name;Status;Date;Time;Timefromstart;Value;Units;LimitLow;Limithigh;Normal',
        '1;SW1 high[2.6V];Passed;06-08-2024;01:23:06;0.31;2.660224;[V];2.340;2.860;-',
        '2;SW2 high[2.6V];Passed;06-08-2024;01:23:06;0.32;2.652450;[V];2.340;2.860;-',
        '2;Done task;Passed;06-08-2024;01:23:06;0.32;2.652450;[V];-;-;-',
        '2;Upper limit only;Passed;06-08-2024;01:23:06;0.32;2.652450;[V];-;3;-',
        '2;Lower limit only;Passed;06-08-2024;01:23:06;0.32;2.652450;[V];2;0;-',
    ]
    return lines


def test_fwk_getLogDateTime():
    processor = FwkDataProcessor()
    fwkName = '20250211_062707_BF2S1_LOW3_Passed'
    ipsesName = 'NEXY-M-600_263240_125355_20250110_FAILED'

    assert processor.getLogDateTime(fwkName) == '2025/02/11 06:27:07'
    assert processor.getLogDateTime(ipsesName) == '2025/01/10 12:53:55'


def test_fwk_headerExtraction(fwkHeaderAndLines):
    processor = FwkDataProcessor()
    assert processor._getSiteFromHeader(fwkHeaderAndLines) == '1'
    assert processor._getSerialNumberFromHeader(fwkHeaderAndLines) == '014250302025804'


def test_fwk_processFileLines(fwkHeaderAndLines):
    processor = FwkDataProcessor()
    site = processor._getSiteFromHeader(fwkHeaderAndLines)
    serialNumber = processor._getSerialNumberFromHeader(fwkHeaderAndLines)
    testTime = '2024/08/06 01:23:06'

    for line in fwkHeaderAndLines[5:]:
        processor._processFileLine(line, site, testTime, serialNumber)

    rawRows = processor.getRawRowsByTest()
    assert 'SW1 high[2.6V]' in rawRows
    assert 'SW2 high[2.6V]' in rawRows
    assert 'Done task' not in rawRows
    assert 'Upper limit only' in rawRows
    assert 'Lower limit only' in rawRows
    

    sw1 = rawRows['SW1 high[2.6V]'][0]
    assert sw1['Site'] == '1'
    assert sw1['Value'] == 2.660224
    assert sw1['LSL'] == 2.34
    assert sw1['USL'] == 2.86
    assert sw1['SerialNumber'] == '014250302025804'