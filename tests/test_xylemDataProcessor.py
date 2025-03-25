import pytest
import dataProcessorXylem
from dataPoint import DataPoint

@pytest.fixture
def file1LinesProcessingTest():
    mockFileLines = [
        'Station ID,U62P-FCT-049',
        'Operator,bitron',
        'Part Number,20890487',
        'UUT Serial Number,2024_XYLEM_042325',
        'Batch Serial Number,TSOI',
        'Test Socket Index,0',
        ''
    ]
    return mockFileLines

@pytest.fixture
def file2LinesProcessingTest():
    mockFileLines = [
        'Sequence,Step Name,Status,Date,Time,Duration,Value,Units,Limit,LimitLow,LimitHigh,ReportText,ErrorCode,ErrorMsg,StepType',
        'MainSequence,initMainComunication,Done,2024/09/13,"18:28:07,240",0.002568,,,,,,,0,,Action',
        'MainSequence,setting_Kikusui 230Vac,Done,2024/09/13,"18:28:07,247",0.057764,,,,,,,0,,Action',
        '4.3.5: Chek Voltage,P04.004: Vdd_ISO,Passed,2024/09/13,"18:28:11,155",0.510367,5.032810,[VDC],GELE,4.800000,5.100000,,1073676293,VISA Read in',
        '4.3.9: Check External NTC,P08.002: NTC1 Value,Passed,2024/09/13,"18:28:16,720",0.000057,891.000000,_,GELE,853.000000,930.000000,,0,,NumericLimitTest',
        '4.3.5: Chek Voltage,P04.004: Vdd_ISO,Passed,2024/09/13,"18:28:11,155",0.510367,5.062810,[VDC],GELE,4.800000,5.100000,,1073676293,VISA Read in',
        '4.3.9: Check External NTC,P08.002: NTC1 Value,Passed,2024/09/13,"18:28:16,720",0.000057,921.000000,_,GELE,853.000000,930.000000,,0,,NumericLimitTest',
    ]
    return mockFileLines

@pytest.fixture
def mockDate():
    return '2024/01/01 14:52:30'

def test__getSiteFromHeader(file1LinesProcessingTest):
    loader = dataProcessorXylem.XylemDataProcessor()
    assert loader._getSiteFromHeader(file1LinesProcessingTest) == (5, '0')


def test__processFileLine(file1LinesProcessingTest, file2LinesProcessingTest, mockDate):
    loader = dataProcessorXylem.XylemDataProcessor()
    mockFile = file1LinesProcessingTest + file2LinesProcessingTest
    siteIndex, site = loader._getSiteFromHeader(mockFile)

    for line in mockFile[siteIndex + 1:]:
        try:
            loader._processFileLine(line, site, mockDate)
        except ValueError:
            pass
    
    measurements = loader.getMeasurements()
    assert list(measurements.keys()) == ['P04.004: Vdd_ISO', 'P08.002: NTC1 Value']

    dataContainer = measurements['P04.004: Vdd_ISO']
    assert list(dataContainer.data.keys()) == ['0']
    assert dataContainer.getData('0') == [[DataPoint(float('5.032810'), (4.8, 5.1), mockDate), DataPoint(float('5.062810'), (4.8, 5.1), mockDate)]]

    dataContainer = measurements['P08.002: NTC1 Value']
    assert list(dataContainer.data.keys()) == ['0']
    assert dataContainer.getData('0') == [[DataPoint(float('891.000000'), (853, 930), mockDate), DataPoint(float('921.000000'), (853, 930), mockDate)]]