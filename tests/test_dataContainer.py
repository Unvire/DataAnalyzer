import pytest
import dataContainer
from dataPoint import DataPoint

def test_init():
    instance = dataContainer.DataContainer('test')
    assert instance.name == 'test'

def test_limits():
    instance = dataContainer.DataContainer('test')
    instance.addLimits(1.23, 4.56, '2025-02-18')
    instance.addLimits(1.23, 4.56, '2024-10-05')
    instance.addLimits(10.23, 14.56, '2025-02-28')
    expected = [
            [DataPoint(1.23, '2025-02-18'), DataPoint(4.56, '2025-02-18')], 
            [DataPoint(1.23, '2024-10-05'), DataPoint(4.56, '2024-10-05')], 
            [DataPoint(10.23, '2025-02-28'), DataPoint(14.56, '2025-02-28')]
        ]
    assert instance.getLimits() == expected

def test_getDataFromSite():
    instance = dataContainer.DataContainer('test')

    mockDate = '2025-02-28'
    instance.addData('1', 1, mockDate)
    assert instance.getDataFromSite('1') == [[DataPoint(1, mockDate)]]

    instance.addData('1', 2, mockDate)
    instance.addData('1', 3, mockDate)
    instance.addData('1', 4, mockDate)
    instance.addData('1', 5, mockDate)
    assert instance.getDataFromSite('1') == [
            [DataPoint(1, mockDate), DataPoint(2, mockDate), DataPoint(3, mockDate), DataPoint(4, mockDate), DataPoint(5, mockDate)]
        ]

    instance.addData('2', 10, mockDate)
    instance.addData('2', 20, mockDate)
    instance.addData('2', 30, mockDate)
    instance.addData('2', 40, mockDate)
    instance.addData('2', 50, mockDate)
    assert instance.getDataFromSite('2') == [
            [DataPoint(10, mockDate), DataPoint(20, mockDate), DataPoint(30, mockDate), DataPoint(40, mockDate), DataPoint(50, mockDate)]
        ]

    assert list(instance.data.keys()) == ['1', '2']
    assert instance.getDataFromAllSites(sortBy='Date') == [
            [DataPoint(1, mockDate), DataPoint(2, mockDate), DataPoint(3, mockDate), DataPoint(4, mockDate), DataPoint(5, mockDate)],
            [DataPoint(10, mockDate), DataPoint(20, mockDate), DataPoint(30, mockDate), DataPoint(40, mockDate), DataPoint(50, mockDate)]
        ]
    
def test_cxcyLimits():
    mockDate = '2025-02-28'
    instance = dataContainer.CxCyDataContainer('test')
    instance.addLimits('1_1_2_2_1_1_2_2', mockDate)    
    instance.addLimits('10_10_20_20_10_10_20_20', mockDate)    
    instance.addLimits('15_15_25_25_15_15_25_25', mockDate)
    assert instance.getLimits() == [
            DataPoint('1_1_2_2_1_1_2_2', mockDate), DataPoint('10_10_20_20_10_10_20_20', mockDate), DataPoint('15_15_25_25_15_15_25_25', mockDate)
        ]

def test_cxcyGetDataFromSite():
    instance = dataContainer.CxCyDataContainer('test')
    mockDate = '2023-05-01'

    instance.addData('1', (1, 2), mockDate)
    assert instance.getDataFromSite('1') == [[DataPoint((1, 2), mockDate)]]

    instance.addData('1', (2.1, 0), mockDate)
    instance.addData('1', (3.2, 1), mockDate)
    instance.addData('1', (4.3, 2), mockDate)
    instance.addData('1', (5.4, 3), mockDate)
    assert instance.getDataFromSite('1') == [
            [DataPoint((1, 2), mockDate), DataPoint((2.1, 0), mockDate), DataPoint((3.2, 1), mockDate), DataPoint((4.3, 2), mockDate), DataPoint((5.4, 3), mockDate)]
        ]

    instance.addData('2', (10, 0), mockDate)
    instance.addData('2', (20, 0), mockDate)
    instance.addData('2', (30, 0), mockDate)
    instance.addData('2', (40, 0), mockDate)
    instance.addData('2', (50, 0), mockDate)
    assert instance.getDataFromSite('2') == [
            [DataPoint((10, 0), mockDate), DataPoint((20, 0), mockDate), DataPoint((30, 0), mockDate),  DataPoint((40, 0), mockDate), DataPoint((50, 0), mockDate)]
        ]

    assert list(instance.data.keys()) == ['1', '2']
    assert instance.getDataFromAllSites(sortBy='Date') == [
            [DataPoint((1, 2), mockDate), DataPoint((2.1, 0), mockDate), DataPoint((3.2, 1), mockDate), DataPoint((4.3, 2), mockDate), DataPoint((5.4, 3), mockDate)],
            [DataPoint((10, 0), mockDate), DataPoint((20, 0), mockDate), DataPoint((30, 0), mockDate), DataPoint((40, 0), mockDate), DataPoint((50, 0), mockDate)]
        ]