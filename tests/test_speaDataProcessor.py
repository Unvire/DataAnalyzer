import pytest
from src.dataProcessorSpea import SpeaDataProcessor


@pytest.fixture
def speaFileLines():
    lines = [
        'FORMAT;mmdd',
        'START;aaa;bbb;74;30101401;ADMINISTRATOR;02/25/2025;07:52:30',
        'LOT;',
        'ANL;2;****************(1);1;1;****************(1);;PASS;0.000000e+00;0.000000e+00;0.000000e+00;;;1',
        'ANL;1;R261;262;1;RESR261 150K 1%;;PASS;1.499953e+05;1.454955e+05;1.544952e+05;ohm;375 289 ;420',
        'ANL;1;R262;263;1;RESR262 10K 5%;;PASS;9.968847e+03;9.300000e+03;1.070000e+04;ohm;377 379 ;421',
        'ANL;1;R265;264;1;RESR265 1K 1%;;PASS;9.960000e+02;9.300000e+02;1.070000e+03;ohm;385 162 ;422',
        'ANL;2;R265;264;1;RESR265 1K 1%;;PASS;9.980000e+02;9.300000e+02;1.070000e+03;ohm;385 162 ;422',
        'FUNC;2;LED4;1002;4;LED_WHITE_CXCY(0.329_0.34_0.3196_0.3462_0.3396_0.3616_0.3386_0.3369_0.3196_0.3198);;PASS;0;0;0;;',
        'SN;170250254017870',
        'BOARDRESULT;PASS',
        'END;PASS;06/25/2025;16:25:17',
    ]
    return lines


def test_spea_getLogDateTime():
    processor = SpeaDataProcessor()
    assert processor.getLogDateTime('PROJECT_170250_20250125173559') == '2025/01/25 17:35:59'
    assert processor.getLogDateTime('NEXY_10725_28072025_082428') == '2025/07/28 08:24:28'
    assert processor.getLogDateTime('LVM_17025_001_162517_20250625') == '2025/06/25 16:25:17'


def test_spea_serialNumberExtraction(speaFileLines):
    processor = SpeaDataProcessor()
    assert processor._getSerialNumber(speaFileLines) == '170250254017870'


def test_spea_processFileLines(speaFileLines):
    processor = SpeaDataProcessor()
    testTime = '2025/01/25 17:35:59'
    serialNumber = processor._getSerialNumber(speaFileLines)

    for line in speaFileLines[:-3]:
        processor._processFileLine(line, testTime, serialNumber)

    rawRows = processor.getRawRowsByTest()
    cxcyTests = processor.getCxCyTests()

    assert 'R261 | RESR261 150K 1%' in rawRows
    assert 'R265 | RESR265 1K 1%' in rawRows
    assert 'LED4 | LED_WHITE_CXCY' in rawRows
    assert 'LED4 | LED_WHITE_CXCY' in cxcyTests

    r265Rows = rawRows['R265 | RESR265 1K 1%']
    assert len(r265Rows) == 2
    assert r265Rows[0]['Site'] == '1'
    assert r265Rows[0]['Value'] == 996.0
    assert r265Rows[1]['Site'] == '2'
    assert r265Rows[1]['Value'] == 998.0

    ledRow = rawRows['LED4 | LED_WHITE_CXCY'][0]
    assert ledRow['Site'] == '2'
    assert ledRow['CX'] == 0.329
    assert ledRow['CY'] == 0.34
    assert len(ledRow['Boundary']) == 5