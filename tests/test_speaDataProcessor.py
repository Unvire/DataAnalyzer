import pytest
import speaDataProcessor

@pytest.fixture
def fileLinesProcessingTest():
    mockFileLines = [
        'ANL;1;R261;262;1;RESR261 150K 1%;;PASS;1.499953e+05;1.454955e+05;1.544952e+05;ohm;375 289 ;420',
        'ANL;1;R262;263;1;RESR262 10K 5%;;PASS;9.968847e+03;9.300000e+03;1.070000e+04;ohm;377 379 ;421',
        'ANL;1;R265;264;1;RESR265 1K 1%;;PASS;9.960000e+02;9.300000e+02;1.070000e+03;ohm;385 162 ;422',      
        'ANL;1;R265;264;1;RESR265 1K 1%;;PASS;9.970000e+02;9.300000e+02;1.070000e+03;ohm;385 162 ;422',
        'ANL;2;R265;264;1;RESR265 1K 1%;;PASS;9.980000e+02;9.300000e+02;1.070000e+03;ohm;385 162 ;422',
        'ANL;2;R265;264;1;RESR265 1K 1%;;PASS;9.990000e+02;9.300000e+02;1.070000e+03;ohm;385 162 ;422',
    ]
    return mockFileLines

def test__processFileLine(fileLinesProcessingTest):
    loader = speaDataProcessor.SpeaDataProcessor()
    for line in fileLinesProcessingTest:
        loader._processFileLine(line)
    
    measurements = loader.getMeasurements()
    
    assert list(measurements.keys()) == ['RESR261 150K 1%', 'RESR262 10K 5%', 'RESR265 1K 1%']

    dataInstance = measurements['RESR261 150K 1%']
    assert list(dataInstance.data.keys()) == ['1']
    assert dataInstance.getDataFromSite('1') == [float('1.499953e+05')]

    dataInstance = measurements['RESR262 10K 5%']
    assert list(dataInstance.data.keys()) == ['1']
    assert dataInstance.getDataFromSite('1') == [float('9.968847e+03')]

    dataInstance = measurements['RESR265 1K 1%']
    assert list(dataInstance.data.keys()) == ['1', '2']
    assert dataInstance.getDataFromSite('1') == [float('9.960000e+02'), float('9.970000e+02')]
    assert dataInstance.getDataFromSite('2') == [float('9.980000e+02'), float('9.990000e+02')]