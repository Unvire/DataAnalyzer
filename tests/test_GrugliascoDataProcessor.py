import pytest
from src.dataProcessorGrugliasco import GrugliascoDataProcessor


@pytest.fixture
def grugliascoLines():
    header = [
        'Station ID,U62P-FCT-049',
        'UUT Serial Number,2024_XYLEM_042325',
        'Test Socket Index,0',
        '',
    ]
    data = [
        'Sequence,Step Name,Status,Date,Time,Duration,Value,Units,Limit,LimitLow,LimitHigh,ReportText,ErrorCode,ErrorMsg,StepType',
        'Main,init,Done,2024/09/13,"18:28:07,240",0.002,,,,,,,0,,Action',
        '4.3.5: Chek,Vdd_ISO,Passed,2024/09/13,"18:28:11,155",0.51,5.032810,[VDC],GELE,4.800000,5.100000,,0,,Test',
    ]
    return header + data


def test_grugliasco_getLogDateTime():
    processor = GrugliascoDataProcessor()
    fileName = '[U62P-FCT-049][XYLEM.seq][2024-09-13][18-37-10][TSOI][2024_XYLEM_042331][0]'
    assert processor.getLogDateTime(fileName) == '2024/09/13 18:37:10'


def test_grugliasco_processLines(grugliascoLines):
    processor = GrugliascoDataProcessor()
    site = processor._getSiteFromHeader(grugliascoLines)
    serialNumber = processor._getSerialNumberFromHeader(grugliascoLines)
    testTime = '2024/09/13 18:37:10'

    assert site == '0'
    assert serialNumber == '2024_XYLEM_042325'

    for line in grugliascoLines:
        try:
            processor._processFileLine(line, site, testTime, serialNumber)
        except ValueError:
            pass

    rawRows = processor.getRawRowsByTest()
    assert 'Vdd_ISO' in rawRows
    row = rawRows['Vdd_ISO'][0]
    assert row['Site'] == '0'
    assert row['Value'] == 5.03281
    assert row['LSL'] == 4.8
    assert row['USL'] == 5.1