import pytest
import dataContainer
from dataPoint import DataPoint

def test_init():
    instance = dataContainer.DataContainer('test')
    assert instance.name == 'test'

def test_getDataFromSite():
    instance = dataContainer.DataContainer('test')

    mockDate = '2025-02-28'
    instance.addData('1', 1, (0, 10), mockDate)
    assert instance.getDataFromSite('1') == [[DataPoint(1, (0, 10), mockDate)]]

    instance.addData('1', 2, (0, 10), mockDate)
    instance.addData('1', 3, (0, 10), mockDate)
    instance.addData('1', 4, (0, 10), mockDate)
    instance.addData('1', 5, (0, 10), mockDate)
    assert instance.getDataFromSite('1') == [
            [DataPoint(1, (0, 10), mockDate), DataPoint(2, (0, 10), mockDate), DataPoint(3, (0, 10), mockDate), 
                DataPoint(4, (0, 10), mockDate), DataPoint(5, (0, 10), mockDate)]
        ]

    instance.addData('2', 10, (0, 20), mockDate)
    instance.addData('2', 20, (0, 20), mockDate)
    instance.addData('2', 30, (0, 20), mockDate)
    instance.addData('2', 40, (0, 20), mockDate)
    instance.addData('2', 50, (0, 20), mockDate)
    assert instance.getDataFromSite('2') == [
            [DataPoint(10, (0, 20), mockDate), DataPoint(20, (0, 20), mockDate), DataPoint(30, (0, 20), mockDate), 
                DataPoint(40, (0, 20), mockDate), DataPoint(50, (0, 20), mockDate)]
        ]

    assert list(instance.data.keys()) == ['1', '2']
    assert instance.getDataFromAllSites() == [
            [DataPoint(1, (0, 10), mockDate), DataPoint(2, (0, 10), mockDate), DataPoint(3, (0, 10), mockDate), 
                DataPoint(4, (0, 10), mockDate), DataPoint(5, (0, 10), mockDate)],
            [DataPoint(10, (0, 20), mockDate), DataPoint(20, (0, 20), mockDate), DataPoint(30, (0, 20), mockDate), 
                DataPoint(40, (0, 20), mockDate), DataPoint(50, (0, 20), mockDate)]
        ]
    
    assert instance.getLimits('1') == [(0, 10), (0, 10), (0, 10), (0, 10), (0, 10)]
    assert instance.getLimits('2') == [(0, 20), (0, 20), (0, 20), (0, 20), (0, 20)]

def test_getDataFromSite_CxCyMeasurement():
    instance = dataContainer.DataContainer('test')
    mockDate = '2023-05-01'

    instance.addData('1', (1, 2), '1_1_2_2_1_1_2_2', mockDate)
    assert instance.getDataFromSite('1') == [[DataPoint((1, 2), '1_1_2_2_1_1_2_2', mockDate)]]

    instance.addData('1', (2.1, 0), '1_1_2_2_1_1_2_2', mockDate)
    instance.addData('1', (3.2, 1), '1_1_2_2_1_1_2_2', mockDate)
    instance.addData('1', (4.3, 2), '1_1_2_2_1_1_2_2', mockDate)
    instance.addData('1', (5.4, 3), '1_1_2_2_1_1_2_2', mockDate)
    assert instance.getDataFromSite('1') == [
            [DataPoint((1, 2), '1_1_2_2_1_1_2_2', mockDate), 
             DataPoint((2.1, 0), '1_1_2_2_1_1_2_2', mockDate), 
             DataPoint((3.2, 1), '1_1_2_2_1_1_2_2', mockDate), 
             DataPoint((4.3, 2), '1_1_2_2_1_1_2_2', mockDate), 
             DataPoint((5.4, 3), '1_1_2_2_1_1_2_2', mockDate)]
        ]

    instance.addData('2', (10, 0), '1_1_2_2_1_1_3_3', mockDate)
    instance.addData('2', (20, 0), '1_1_2_2_1_1_3_3', mockDate)
    instance.addData('2', (30, 0), '1_1_2_2_1_1_3_3', mockDate)
    instance.addData('2', (40, 0), '1_1_2_2_1_1_3_3', mockDate)
    instance.addData('2', (50, 0),  '1_1_2_2_1_1_3_3',mockDate)
    assert instance.getDataFromSite('2') == [
            [
                DataPoint((10, 0), '1_1_2_2_1_1_3_3', mockDate), 
                DataPoint((20, 0), '1_1_2_2_1_1_3_3', mockDate), 
                DataPoint((30, 0), '1_1_2_2_1_1_3_3', mockDate),  
                DataPoint((40, 0), '1_1_2_2_1_1_3_3', mockDate), 
                DataPoint((50, 0), '1_1_2_2_1_1_3_3', mockDate)
            ]
        ]

    assert list(instance.data.keys()) == ['1', '2']
    assert instance.getDataFromAllSites() == [
        [
            DataPoint((1, 2), '1_1_2_2_1_1_2_2', mockDate), 
            DataPoint((2.1, 0), '1_1_2_2_1_1_2_2', mockDate), 
            DataPoint((3.2, 1), '1_1_2_2_1_1_2_2', mockDate), 
            DataPoint((4.3, 2), '1_1_2_2_1_1_2_2', mockDate), 
            DataPoint((5.4, 3), '1_1_2_2_1_1_2_2', mockDate)
        ],
        [
            DataPoint((10, 0), '1_1_2_2_1_1_3_3', mockDate), 
            DataPoint((20, 0), '1_1_2_2_1_1_3_3', mockDate), 
            DataPoint((30, 0), '1_1_2_2_1_1_3_3', mockDate),  
            DataPoint((40, 0), '1_1_2_2_1_1_3_3', mockDate), 
            DataPoint((50, 0), '1_1_2_2_1_1_3_3', mockDate)
        ]
    ]

    assert instance.getLimits('1') == ['1_1_2_2_1_1_2_2', '1_1_2_2_1_1_2_2', '1_1_2_2_1_1_2_2', '1_1_2_2_1_1_2_2', '1_1_2_2_1_1_2_2']
    assert instance.getLimits('2') == ['1_1_2_2_1_1_3_3', '1_1_2_2_1_1_3_3', '1_1_2_2_1_1_3_3', '1_1_2_2_1_1_3_3', '1_1_2_2_1_1_3_3']