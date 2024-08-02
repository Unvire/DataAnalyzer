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

    instance.addData('1', 1)
    assert instance.getDataFromSite('1') == [1]

    instance.addData('1', 2)
    instance.addData('1', 3)
    instance.addData('1', 4)
    instance.addData('1', 5)
    assert instance.getDataFromSite('1') == [1, 2, 3, 4, 5]

    instance.addData('2', 20)
    instance.addData('2', 30)
    instance.addData('2', 40)
    instance.addData('2', 50)
    assert instance.getDataFromSite('2') == [20, 30, 40, 50]

    assert list(instance.data.keys()) == ['1', '2']
    assert sorted(instance.getDataFromAllSites()) == [1, 2, 3, 4, 5, 20, 30, 40, 50]