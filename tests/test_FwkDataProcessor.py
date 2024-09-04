import pytest
import fwkDataProcessor

@pytest.fixture
def file1LinesProcessingTest():
    mockFileLines = [
        'Operator;administrator;;;;;;;;;',
        'Test Socket Index;1;;;;;;;;;',
        'Version_HW;1.1;;;;;;;;;',
        ';;;;;;;;;;',
        'Sequence;Step Name;Status;Date;Time;Timefromstart;Value;Units;LimitLow;Limithigh;Normal',
        '1;SW1 high[2.6V];Passed;06-08-2024;01:23:06;0.3196242;2.660224;[V];2.340;2.860;-',
        '2;SW2 high[2.6V];Passed;06-08-2024;01:23:06;0.3208613;2.652450;[V];2.340;2.860;-',        
        '3;SW1 high[2.6V];Passed;06-08-2024;01:23:06;0.3196242;2.660224;[V];2.340;2.860;-', 
    ]
    return mockFileLines

@pytest.fixture
def file2LinesProcessingTest():
    mockFileLines = [
        'Test Socket Index;2;;;;;;;;;',
        ';;;;;;;;;;',
        '1;SW1 high[2.6V];Passed;06-08-2024;01:23:06;0.3196242;2.560224;[V];2.340;2.860;-',
        '2;SW2 high[2.6V];Passed;06-08-2024;01:23:06;0.3208613;2.552450;[V];2.340;2.860;-',        
        '3;SW1 high[2.6V];Passed;06-08-2024;01:23:06;0.3196242;2.560224;[V];2.340;2.860;-', 
    ]
    return mockFileLines

def test__getSiteFromHeader(file1LinesProcessingTest, file2LinesProcessingTest):
    loader = fwkDataProcessor.FwkDataProcessor()
    assert loader._getSiteFromHeader(file1LinesProcessingTest) == '1'
    assert loader._getSiteFromHeader(file2LinesProcessingTest) == '2'


def test__processFileLine(file1LinesProcessingTest, file2LinesProcessingTest):
    loader = fwkDataProcessor.FwkDataProcessor()
    for mockfile in [file1LinesProcessingTest, file2LinesProcessingTest]:
        site = loader._getSiteFromHeader(mockfile)
        for line in mockfile:
            try:
                loader._processFileLine(line, site)
            except ValueError:
                pass
    
    measurements = loader.getMeasurements()
    assert list(measurements.keys()) == ['SW1 high[2.6V]', 'SW2 high[2.6V]']

    dataInstance = measurements['SW1 high[2.6V]']
    assert list(dataInstance.data.keys()) == ['1', '2']
    assert dataInstance.getDataFromSite('1') == [float('2.660224'), float('2.660224')]    
    assert dataInstance.getDataFromSite('2') == [float('2.560224'), float('2.560224')]

    dataInstance = measurements['SW2 high[2.6V]']
    assert list(dataInstance.data.keys()) == ['1', '2']
    assert dataInstance.getDataFromSite('1') == [float('2.652450')]    
    assert dataInstance.getDataFromSite('2') == [float('2.552450')]