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
    assert instance.getDataFromSite('1') == [(1, '2025/01/01')]

    instance.addData('1', (2, '2025/01/01'))
    instance.addData('1', (3, '2025/01/01'))
    instance.addData('1', (4, '2025/01/01'))
    instance.addData('1', (5, '2025/01/01'))
    assert instance.getDataFromSite('1') == [(1, '2025/01/01'), (2, '2025/01/01'), (3, '2025/01/01'), (4, '2025/01/01'), (5, '2025/01/01')]

    instance.addData('2', (20, '2025/01/01'))
    instance.addData('2', (30, '2025/01/01'))
    instance.addData('2', (40, '2025/01/01'))
    instance.addData('2', (50, '2025/01/01'))
    assert instance.getDataFromSite('2') == [(20, '2025/01/01'), (30, '2025/01/01'), (40, '2025/01/01'), (50, '2025/01/01')]

    assert list(instance.data.keys()) == ['1', '2']
    assert sorted(instance.getDataFromAllSites()) == [(1, '2025/01/01'), (2, '2025/01/01'), (3, '2025/01/01'), (4, '2025/01/01'), (5, '2025/01/01'),
                                                      (20, '2025/01/01'), (30, '2025/01/01'), (40, '2025/01/01'), (50, '2025/01/01')]