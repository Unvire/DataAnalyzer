import pytest
import listParser

@pytest.fixture
def mockDataSeries():
    mockList = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [8, 9, 10 ,11, 12]        
    ]
    return mockList

@pytest.fixture
def mockValueDateSeries():
    mockList = [
        [(1, 'date'), (2, 'date'), (3, 'date'), (4, 'date')],
        [(5, 'date'), (6, 'date'), (7, 'date'), (8, 'date')],
        [(9, 'date'), (10, 'date'), (11, 'date'), (12, 'date')]        
    ]
    return mockList

@pytest.fixture
def mockValueSeries():
    mockList = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10, 11, 12]        
    ]
    return mockList

@pytest.fixture
def mockUniqueCxCBoundaryStrings():
    val1 = '1_1_2_2_3_3_4_4'
    val2 = '10_10_20_20_30_30_40_40'
    return [val1, val2]



def test_mergedDataSeries(mockDataSeries):
    result = listParser.mergedDataSeries(mockDataSeries)
    expectedList = [
        [(0, 1), (1, 2), (2, 3), (3, 4)],
        [(0, 5), (1, 6), (2, 7), (3, 8)],
        [(0, 8), (1, 9), (2, 10) ,(3, 11), (4, 12)]  
    ]
    expectedLength = 5
    assert result == (expectedList, expectedLength)

def test_continuousDataSeries(mockDataSeries):
    result = listParser.continuousDataSeries(mockDataSeries)
    expectedList = [
        [(0, 1), (1, 2), (2, 3), (3, 4)],
        [(4, 5), (5, 6), (6, 7), (7, 8)],
        [(8, 8), (9, 9), (10, 10) ,(11, 11), (12, 12)]  
    ]
    expectedLength = 13
    assert result == (expectedList, expectedLength)

def test_flattenDataSeries(mockDataSeries):    
    result = listParser.flattenDataSeries(mockDataSeries)
    expectedList = [1, 2, 3, 4, 5, 6, 7, 8, 8, 9, 10 ,11, 12]
    expectedLength = 13
    assert result == (expectedList, expectedLength)

def test_valueDateSeriesToValueSeries(mockValueDateSeries):
    result = listParser.valueDateSeriesToValueSeries(mockValueDateSeries)
    expected = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10 ,11, 12]        
    ]
    assert result == expected

def test_nestedValuesListToFlatValueList(mockValueSeries):
    result = listParser.nestedValuesListToFlatValueList(mockValueSeries)
    expected = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10 ,11, 12]
    assert result == expected

def test_uniqueBoundaryStrings(mockUniqueCxCBoundaryStrings):
    val1, val2 = mockUniqueCxCBoundaryStrings
    inputData = [[val1, val2, val2], [val2], [val2, val2], [val1, val1, val2]]

    result = listParser.uniqueBoundaryStrings(inputData)
    expected = [val1, val2]
    assert sorted(result) == sorted(expected)

def test_processBoundaryStrings(mockUniqueCxCBoundaryStrings):    
    val1, val2 = mockUniqueCxCBoundaryStrings
    inputData = [val1, val2]
    result = listParser.processBoundaryStrings(inputData)
    expected = [
            [(1, 1), (2, 2), (3, 3), (4, 4), (1, 1)], 
            [(10, 10), (20, 20), (30, 30), (40, 40), (10, 10)]
        ]
    assert result == expected