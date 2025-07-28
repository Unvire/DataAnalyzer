import pytest
import dataProcessorFwk
from dataPoint import DataPoint

@pytest.fixture
def file1LinesProcessingTest():
    mockFileLines = [
        'Operator;administrator;;;;;;;;;',
        'UUT Serial Number;014250302025804;;;;;;;;;',
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
        'UUT Serial Number;114250302025804;;;;;;;;;',
        ';;;;;;;;;;',
        '1;SW1 high[2.6V];Passed;06-08-2024;01:23:06;0.3196242;2.560224;[V];2.340;2.860;-',
        '2;SW2 high[2.6V];Passed;06-08-2024;01:23:06;0.3208613;2.552450;[V];2.340;2.860;-',        
        '3;SW1 high[2.6V];Passed;06-08-2024;01:23:06;0.3196242;2.560224;[V];2.340;2.860;-', 
    ]
    return mockFileLines

@pytest.fixture
def mockFileNameFwk():
    return '20250211_062707_BF2S1_03725022404F21421698_LOW3 30417472_Passed'

@pytest.fixture
def mockFileNameIpses():
    return 'NEXY-M-600-main_263240002025600_125355_20250110_FAILED'

def test_getLogDateTime(mockFileNameFwk, mockFileNameIpses):
    loader = dataProcessorFwk.FwkDataProcessor()
    
    expected = '2025/02/11 06:27:07'
    assert loader.getLogDateTime(mockFileNameFwk) == expected

    expected = '2025/01/10 12:53:55'
    assert loader.getLogDateTime(mockFileNameIpses) == expected

def test__getSiteFromHeader(file1LinesProcessingTest, file2LinesProcessingTest):
    loader = dataProcessorFwk.FwkDataProcessor()
    assert loader._getSiteFromHeader(file1LinesProcessingTest) == '1'
    assert loader._getSiteFromHeader(file2LinesProcessingTest) == '2'

def test__getSerialNumberFromHeader(file1LinesProcessingTest, file2LinesProcessingTest):
    loader = dataProcessorFwk.FwkDataProcessor()
    assert loader._getSerialNumberFromHeader(file1LinesProcessingTest) == '014250302025804'
    assert loader._getSerialNumberFromHeader(file2LinesProcessingTest) == '114250302025804'

def test__processFileLine(file1LinesProcessingTest, file2LinesProcessingTest, mockFileNameFwk):
    loader = dataProcessorFwk.FwkDataProcessor()
    testTime = loader.getLogDateTime(mockFileNameFwk)

    for mockfile in [file1LinesProcessingTest, file2LinesProcessingTest]:
        site = loader._getSiteFromHeader(mockfile)
        serialNumber = loader._getSerialNumberFromHeader(mockfile)
        for line in mockfile:
            try:
                loader._processFileLine(line, site, testTime, serialNumber)
            except ValueError:
                pass
    
    measurements = loader.getMeasurements()
    assert list(measurements.keys()) == ['SW1 high[2.6V]', 'SW2 high[2.6V]']

    dataInstance = measurements['SW1 high[2.6V]']
    assert list(dataInstance.data.keys()) == ['1', '2']
    assert dataInstance.getData('1') == [[DataPoint(float('2.660224'), (2.340, 2.860), '2025/02/11 06:27:07', '014250302025804'), 
                                                  DataPoint(float('2.660224'), (2.340, 2.860), '2025/02/11 06:27:07', '014250302025804')]]    
    assert dataInstance.getData('2') == [[DataPoint(float('2.560224'), (2.340, 2.860), '2025/02/11 06:27:07', '114250302025804'), 
                                                  DataPoint(float('2.560224'), (2.340, 2.860), '2025/02/11 06:27:07', '114250302025804')]]

    dataInstance = measurements['SW2 high[2.6V]']
    assert list(dataInstance.data.keys()) == ['1', '2']
    assert dataInstance.getData('1') == [[DataPoint(float('2.652450'), (2.340, 2.860), '2025/02/11 06:27:07', '014250302025804')]]    
    assert dataInstance.getData('2') == [[DataPoint(float('2.552450'), (2.340, 2.860), '2025/02/11 06:27:07', '114250302025804')]]