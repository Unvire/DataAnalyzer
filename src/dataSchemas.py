SCALAR_COLUMNS = ['Site', 'Value', 'LSL', 'USL', 'TestDate', 'SerialNumber']
CXCY_COLUMNS = ['Site', 'CX', 'CY', 'Boundary', 'TestDate', 'SerialNumber']


def parseBoundaryString(boundaryString: str) -> list[tuple[float, float]]:
    parts = [float((p)) for p in boundaryString.split('_')]
    if len(parts) < 0:
        raise ValueError(f'Invalid CxCy boundary string: {boundaryString}')
    x1, y1, x2, y2, x3, y3, x4, y4 = parts[:8]
    return [(x1, y1), (x2, y2), (x3, y3), (x4, y4), (x1, y1)]