import numpy as np
import pytest

from src.siFormatter import (
    calculateLinthresh,
    formatAxisTitle,
    formatSiValue,
    generateSymlogTicks,
    getSiScale,
    isSentinelLimit,
    shouldAutoLogScale,
    symlogTransform,
)


@pytest.mark.parametrize(
    'values, expectedPrefix, expectedMultiplier',
    [
        ([33e-9, 32.5e-9, 33.4e-9], 'n', 1e9),
        ([100e-12, 105e-12], 'p', 1e12),
        ([4.7e-6, 4.8e-6], 'µ', 1e6),
        ([0.025, 0.026], 'm', 1e3),
        ([3.3, 3.31, 3.29], '', 1.0),
        ([150e3, 149.5e3], 'k', 1e-3),
        ([2.2e6, 2.25e6], 'M', 1e-6),
        ([-33e-9, -32e-9], 'n', 1e9),
    ],
)
def test_getSiScale_ranges(values, expectedPrefix, expectedMultiplier):
    prefix, multiplier = getSiScale(values)
    assert prefix == expectedPrefix
    assert multiplier == pytest.approx(expectedMultiplier)


def test_getSiScale_ignoresExtremeOutliersUsingLimits():
    values = [33e-9, 33.1e-9, 32.9e-9, 1.0, 10.0]
    prefix, multiplier = getSiScale(values, lsl=30e-9, usl=36e-9)
    assert prefix == 'n'
    assert multiplier == pytest.approx(1e9)


def test_sentinelLimit_detection():
    assert isSentinelLimit(None) is True
    assert isSentinelLimit(float('nan')) is True
    assert isSentinelLimit(float('inf')) is True
    assert isSentinelLimit(1e14) is True
    assert isSentinelLimit(-1e14) is True
    assert isSentinelLimit(9.99e37) is True

    assert isSentinelLimit(1e9, dataRef=0.2) is True
    
    assert isSentinelLimit(1e9, dataRef=0.8e9) is False
    assert isSentinelLimit(5.5, dataRef=5.0) is False


def test_shouldAutoLogScale_rules():
    assert shouldAutoLogScale([5.0, 5.1], lsl=5.0, usl=10_000_000_000.0) is True
    
    leakage = [10e-9, 50e-9, 1e-6, 50e-6, 100e-6]
    assert shouldAutoLogScale(leakage, lsl=1e-9, usl=1e-3) is True
    
    assert shouldAutoLogScale([4.99, 5.01], lsl=4.75, usl=5.25) is False
    
    assert shouldAutoLogScale([-1.0, 5.0], lsl=-2.0, usl=1000.0) is False
    assert shouldAutoLogScale([0.0, 5.0], lsl=0.0, usl=1000.0) is False


def test_calculate_linthresh():
    vals = np.array([-50.0, -0.02, 0.0, 0.05, 100.0])
    linthresh = calculateLinthresh(vals)
    assert linthresh == pytest.approx(0.01)


def test_symlogTransform_properties():
    linthresh = 1.0

    assert symlogTransform(0.0, linthresh) == 0.0
    assert symlogTransform(0.5, linthresh) == pytest.approx(0.5)
    assert symlogTransform(-0.5, linthresh) == pytest.approx(-0.5)
    assert symlogTransform(1.0, linthresh) == pytest.approx(1.0)
    assert symlogTransform(-1.0, linthresh) == pytest.approx(-1.0)

    assert symlogTransform(10.0, linthresh) == pytest.approx(2.0)
    assert symlogTransform(100.0, linthresh) == pytest.approx(3.0)

    assert symlogTransform(-10.0, linthresh) == pytest.approx(-2.0)
    assert symlogTransform(-100.0, linthresh) == pytest.approx(-3.0)

    arr = np.array([-100.0, -1.0, 0.0, 1.0, 100.0])
    transformed = symlogTransform(arr, linthresh)
    expected = np.array([-3.0, -1.0, 0.0, 1.0, 3.0])
    np.testing.assert_allclose(transformed, expected)


def test_generateSymlogTicks():
    linthresh = 1.0
    tickVals, tickText = generateSymlogTicks(minVal=-100.0, maxVal=100.0, linthresh=linthresh)

    # Wartości muszą być ułożone ściśle monotonicznie rosnąco
    assert tickVals == sorted(tickVals)
    assert 0.0 in tickVals
    zeroIdx = tickVals.index(0.0)
    assert tickText[zeroIdx] == '0'

    # Weryfikacja obecności dekad -100, -10, -1, 0, 1, 10, 100
    assert tickVals == pytest.approx([-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0])
    assert tickText == ['-100', '-10', '-1', '0', '1', '10', '100']