import pytest
import processCalculator

class MockDataClass:
    def __init__(self):
        self.measurements = []
        self.LSL = None
        self.USL = None
        self.mean = None
        self.sigmaWithin = None
        self.sigmaOverall = None
        self.CPL = None
        self.CPU = None
        self.cp = None
        self.cpk = None
        self.PPL = None
        self.PPU = None
        self.pp = None
        self.ppk = None

@pytest.fixture
def sampleData():
    dataClass = MockDataClass()
    dataClass.measurements = [
        44.40984698,
        45.72826182,
        44.27516009,
        44.87098305,
        43.63958596,
        44.89865954,
        44.52371647,
        45.08641810,
        44.56515267,
        43.13298060,
        46.34394012,
        45.49377525,
        45.36517822,
        44.11345968,
        46.69137656,
        43.53316982,
        43.36899205,
        45.97239383,
        44.14397960,
        44.33482048,
        44.39259115,
        45.53710408,
        43.29832541,
        43.16382004,
        43.21086599,
        45.57757573,
        45.51731634,
        42.17417161,
        44.57297918,
        46.02077601,
        45.29140235,
        44.43711425,
        45.22187506,
        44.88297783,
        44.35986601,
        43.69291075,
        46.78118045,
        44.14949097,
        45.67190497,
        44.34944473
    ]
    dataClass.LSL = 43
    dataClass.USL = 45
    dataClass.mean = 44.67
    dataClass.sigmaWithin = 1.05
    dataClass.sigmaOverall = 1.65
    dataClass.CPL = 1.37
    dataClass.CPU = 0.17
    dataClass.cp = 0.77
    dataClass.cpk = 0.17
    dataClass.PPL = 0.11
    dataClass.PPU = 0.85
    dataClass.pp = 0.48
    dataClass.ppk = 0.11    
    return dataClass

def test__calculateMeanSigma(sampleData):
    instance = processCalculator.ProcessParameterCalculator()
    measurements = sampleData.measurements
    mean, sigmaWithin = instance._calculateMeanSigma(measurements)
    assert round(mean, 2) == sampleData.mean
    assert round(sigmaWithin, 2) == sampleData.sigmaWithin
