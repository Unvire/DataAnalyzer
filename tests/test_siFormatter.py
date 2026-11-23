import pytest

from src.siFormatter import formatAxisTitle, formatSiValue, getSiScale


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
def test_get_si_scale_ranges(values, expectedPrefix, expectedMultiplier):
    prefix, multiplier = getSiScale(values)
    assert prefix == expectedPrefix
    assert multiplier == pytest.approx(expectedMultiplier)


def test_get_si_scale_ignores_extreme_outliers_using_limits():
    values = [33e-9, 33.1e-9, 32.9e-9, 1.0, 10.0]
    prefix, multiplier = getSiScale(values, lsl=30e-9, usl=36e-9)
    assert prefix == 'n'
    assert multiplier == pytest.approx(1e9)


def test_get_si_scale_zeros_fallback_to_limits():
    prefix, multiplier = getSiScale([0.0, 0.0], lsl=-50e-6, usl=50e-6)
    assert prefix == 'µ'
    assert multiplier == pytest.approx(1e6)


def test_format_helpers():
    assert formatAxisTitle('Measured Value', 'n') == 'Measured Value [n]'
    assert formatAxisTitle('Measured Value', '') == 'Measured Value'
    assert formatAxisTitle('Capacitance', 'n', 'F') == 'Capacitance [nF]'
    assert formatSiValue(3.3e-8, unit='F') == '33 nF'