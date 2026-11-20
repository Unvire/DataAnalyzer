import pytest
from src.dataSchemas import CXCY_COLUMNS, SCALAR_COLUMNS, parseBoundaryString


def test_schemaColumnDefinitions():
    assert SCALAR_COLUMNS == ['Site', 'Value', 'LSL', 'USL', 'TestDate', 'SerialNumber']
    assert CXCY_COLUMNS == ['Site', 'CX', 'CY', 'Boundary', 'TestDate', 'SerialNumber']


def test_parseBoundaryString_valid():
    rawString = '0.3196_0.3462_0.3396_0.3616_0.3386_0.3369_0.3196_0.3198'
    result = parseBoundaryString(rawString)
    expected = [
        (0.3196, 0.3462),
        (0.3396, 0.3616),
        (0.3386, 0.3369),
        (0.3196, 0.3198),
        (0.3196, 0.3462),
    ]
    assert result == expected


def test_parseBoundaryString_invalid():
    with pytest.raises(ValueError):
        parseBoundaryString('0.1_0.2_0.3')