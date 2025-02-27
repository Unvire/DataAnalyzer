import pytest
import dataContainer

def test_init():
    instance = dataContainer.DataContainer('test')
    assert instance.name == 'test'

def test_limits():
    instance = dataContainer.DataContainer('test')
    instance.setLimits(1.23, 4.56)
    assert instance.getLimits() == [1.23, 4.56]

def test_getDataFromSite():
    instance = dataContainer.DataContainer('test')

    instance.addData('1', (1, '2025/01/01'))
    assert instance.getDataFromSite('1') == [[(1, '2025/01/01')]]

    instance.addData('1', (2, '2025/01/01'))
    instance.addData('1', (3, '2025/01/01'))
    instance.addData('1', (4, '2025/01/01'))
    instance.addData('1', (5, '2025/01/01'))
    assert instance.getDataFromSite('1') == [
            [(1, '2025/01/01'), (2, '2025/01/01'), (3, '2025/01/01'), (4, '2025/01/01'), (5, '2025/01/01')]
        ]

    instance.addData('2', (10, '2025/01/01'))
    instance.addData('2', (20, '2025/01/01'))
    instance.addData('2', (30, '2025/01/01'))
    instance.addData('2', (40, '2025/01/01'))
    instance.addData('2', (50, '2025/01/01'))
    assert instance.getDataFromSite('2') == [
            [(10, '2025/01/01'), (20, '2025/01/01'), (30, '2025/01/01'), (40, '2025/01/01'), (50, '2025/01/01')]
        ]

    assert list(instance.data.keys()) == ['1', '2']
    assert sorted(instance.getDataFromAllSites(sortBy='Date')) == [
            [(1, '2025/01/01'), (2, '2025/01/01'), (3, '2025/01/01'), (4, '2025/01/01'), (5, '2025/01/01')],
            [(10, '2025/01/01'), (20, '2025/01/01'), (30, '2025/01/01'), (40, '2025/01/01'), (50, '2025/01/01')]
        ]
    
def test_cxcyBoundaryXYs():
    instance = dataContainer.CxCyDataContainer('test')
    instance.addBoundaryXY((1, 1))    
    instance.addBoundaryXY((2, 2))    
    instance.addBoundaryXY((0, -1))
    assert instance.getBoundaryXYs() == [(1, 1), (2, 2), (0, -1)]

def test_cxcyGetDataFromSite():
    instance = dataContainer.CxCyDataContainer('test')

    instance.addData('1', ((1, 2), '2025/01/01'))
    assert instance.getDataFromSite('1') == [[((1, 2), '2025/01/01')]]

    instance.addData('1', ((2.1, 0), '2025/01/01'))
    instance.addData('1', ((3.2, 1), '2025/01/01'))
    instance.addData('1', ((4.3, 2), '2025/01/01'))
    instance.addData('1', ((5.4, 3), '2025/01/01'))
    assert instance.getDataFromSite('1') == [
            [((1, 2), '2025/01/01'), ((2.1, 0), '2025/01/01'), ((3.2, 1), '2025/01/01'), ((4.3, 2), '2025/01/01'), ((5.4, 3), '2025/01/01')]
        ]

    instance.addData('2', ((10, 0), '2025/01/01'))
    instance.addData('2', ((20, 0), '2025/01/01'))
    instance.addData('2', ((30, 0), '2025/01/01'))
    instance.addData('2', ((40, 0), '2025/01/01'))
    instance.addData('2', ((50, 0), '2025/01/01'))
    assert instance.getDataFromSite('2') == [
            [((10, 0), '2025/01/01'), ((20, 0), '2025/01/01'), ((30, 0), '2025/01/01'),  ((40, 0), '2025/01/01'), ((50, 0), '2025/01/01')]
        ]

    assert list(instance.data.keys()) == ['1', '2']
    assert sorted(instance.getDataFromAllSites(sortBy='Date')) == [
            [((1, 2), '2025/01/01'), ((2.1, 0), '2025/01/01'), ((3.2, 1), '2025/01/01'), ((4.3, 2), '2025/01/01'), ((5.4, 3), '2025/01/01')],
            [((10, 0), '2025/01/01'), ((20, 0), '2025/01/01'), ((30, 0), '2025/01/01'), ((40, 0), '2025/01/01'), ((50, 0), '2025/01/01')]
        ]