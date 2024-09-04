import pytest
import columnDataProcessor

@pytest.fixture
def file1LinesProcessingTest():
    mockFileLines = [
        'test1;0;10',
        '1',
        '2', 
    ]
    return mockFileLines

@pytest.fixture
def file2LinesProcessingTest():
    mockFileLines = [
        'test1;0;10;',
        '3',
        '4', 
    ]
    return mockFileLines

@pytest.fixture
def file3LinesProcessingTest():
    mockFileLines = [
        'test2;10;20',
        '15',
        '16', 
    ]
    return mockFileLines

def test__getSiteLimitsFromHeader(file1LinesProcessingTest, file2LinesProcessingTest, file3LinesProcessingTest):    
    loader = columnDataProcessor.ColumnDataProcessor()
    assert loader._getSiteLimitsFromHeader(file1LinesProcessingTest) == ('test1', '0', '10')
    assert loader._getSiteLimitsFromHeader(file2LinesProcessingTest) == ('test1', '0', '10')
    assert loader._getSiteLimitsFromHeader(file3LinesProcessingTest) == ('test2', '10', '20')
    

def test__processFileLine(file1LinesProcessingTest, file2LinesProcessingTest, file3LinesProcessingTest):
    loader = columnDataProcessor.ColumnDataProcessor()
    for mockFile in [file1LinesProcessingTest, file2LinesProcessingTest, file3LinesProcessingTest]:
        testName, lowerLimit, upperLimit = loader._getSiteLimitsFromHeader(mockFile)
        loader.createDataContainer(testName, lowerLimit, upperLimit)
        for line in mockFile:
            loader._processFileLine(line, testName)
    
    measurements = loader.getMeasurements()
    assert list(measurements.keys()) == ['test1', 'test2']

    dataInstance = measurements['test1']
    assert list(dataInstance.data.keys()) == ['1']
    assert dataInstance.getDataFromSite('1') == [float('1'), float('2'), float('3'), float('4')]

    dataInstance = measurements['test2']
    assert list(dataInstance.data.keys()) == ['1']
    assert dataInstance.getDataFromSite('1') == [float('15'), float('16')]