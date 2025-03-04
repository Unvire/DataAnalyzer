import pytest
import speaDataProcessor
from dataPoint import DataPoint

@pytest.fixture
def fileLinesProcessingTest():
    mockFileLines = [
        'ANL;1;R261;262;1;RESR261 150K 1%;;PASS;1.499953e+05;1.454955e+05;1.544952e+05;ohm;375 289 ;420',
        'ANL;1;R262;263;1;RESR262 10K 5%;;PASS;9.968847e+03;9.300000e+03;1.070000e+04;ohm;377 379 ;421',
        'ANL;1;R265;264;1;RESR265 1K 1%;;PASS;9.960000e+02;9.300000e+02;1.070000e+03;ohm;385 162 ;422',      
        'ANL;1;R265;264;1;RESR265 1K 1%;;PASS;9.970000e+02;9.300000e+02;1.070000e+03;ohm;385 162 ;422',
        'ANL;2;R265;264;1;RESR265 1K 1%;;PASS;9.980000e+02;9.300000e+02;1.070000e+03;ohm;385 162 ;422',
        'ANL;2;R265;264;1;RESR265 1K 1%;;PASS;9.990000e+02;9.300000e+02;1.070000e+03;ohm;385 162 ;422',
        'FUNC;2;LED4;1002;4;LED_WHITE_15704401_SW57P19D22K72_CXCY(0.329_0.34_0.3196_0.3462_0.3396_0.3616_0.3386_0.3369_0.3196_0.3198);;PASS;0.000000e+00;0.000000e+00;0.000000e+00;;'
    ]
    mockTestTime = '2024/01/01 14:23:14'
    return mockFileLines, mockTestTime

def test__processFileLine(fileLinesProcessingTest):
    fileLines, testTime = fileLinesProcessingTest
    loader = speaDataProcessor.SpeaDataProcessor()
    for line in fileLines:
        loader._processFileLine(line, testTime)
    
    measurements = loader.getMeasurements()
    
    assert list(measurements.keys()) == ['R261 | RESR261 150K 1%', 'R262 | RESR262 10K 5%', 'R265 | RESR265 1K 1%', 'LED4 | LED_WHITE_15704401_SW57P19D22K72_CXCY']

    dataInstance = measurements['R261 | RESR261 150K 1%']
    assert list(dataInstance.data.keys()) == ['1']
    assert dataInstance.getDataFromSite('1') == [
            [DataPoint(float('1.499953e+05'), (float('1.454955e+05'), float('1.544952e+05')), '2024/01/01 14:23:14')]
        ]

    dataInstance = measurements['R262 | RESR262 10K 5%']
    assert list(dataInstance.data.keys()) == ['1']
    assert dataInstance.getDataFromSite('1') == [
            [DataPoint(float('9.968847e+03'), (float('9.300000e+03'), float('1.070000e+04')),'2024/01/01 14:23:14')]
        ]

    dataInstance = measurements['R265 | RESR265 1K 1%']
    assert list(dataInstance.data.keys()) == ['1', '2']
    assert dataInstance.getDataFromSite('1') == [
            [DataPoint(float('9.960000e+02'), (float('9.300000e+02'), float('1.070000e+03')), '2024/01/01 14:23:14'), 
             DataPoint(float('9.970000e+02'), (float('9.300000e+02'), float('1.070000e+03')), '2024/01/01 14:23:14')]
        ]
    assert dataInstance.getDataFromSite('2') == [
            [DataPoint(float('9.980000e+02'), (float('9.300000e+02'), float('1.070000e+03')), '2024/01/01 14:23:14'), 
             DataPoint(float('9.990000e+02'), (float('9.300000e+02'), float('1.070000e+03')), '2024/01/01 14:23:14')]
        ]
    assert 1==0
    
    dataInstance = measurements['LED4 | LED_WHITE_15704401_SW57P19D22K72_CXCY']
    assert list(dataInstance.data.keys()) == ['2']
    assert dataInstance.getDataFromSite('2') == [
            [DataPoint((float('0.329'), float('0.34')), '0.3196_0.3462_0.3396_0.3616_0.3386_0.3369_0.3196_0.3198', '2024/01/01 14:23:14')]
        ]