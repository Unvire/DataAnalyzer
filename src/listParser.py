def mergedDataSeries(data:list[list[float]]) -> tuple[list[list[tuple[int, float]]], int]:
    '''
    Prepares data for  **overlapping series plot**:
    Converts list of measurements (per site) to tuple (listForPlot, lonestSeriesLength):
    data:
    [
        [val11, val12, val13, ..., val1n], 
        [val21, val22, val23, ..., val2n], 
        [val31, val32, val33, ..., val3n], 
        ...
    ] 

    List of values ready to be plotted **(overlapping plots)**:
    [
        [(1, val11), (2, val12), (3, val13), ..., (n, val1n)], 
        [(1, val21), (2, val22), (3, val23), ..., (n, val2n)], 
        [(1, val31), (2, val32), (3, val33), ..., (n, val3n)],
        ...    
    ],
    lonestSeriesLength = max([len(series) for series in result])
    '''
    result = []
    for dataSeries in data:
        seriesPointList = [(i, value) for i, value in enumerate(dataSeries)]
        result.append(seriesPointList)    
    numberOfSamples = max([len(series) for series in result])
    return result, numberOfSamples

def continuousDataSeries(data:list[list[float]]) -> tuple[list[list[tuple[int, float]]], int]:
    '''
    Prepares data for  **series plot next to each other**:
    Converts list of measurements (per site) to tuple (listForPlot, lonestSeriesLength):
    data:
    [
        [val11, val12, val13, ..., val1n], 
        [val21, val22, val23, ..., val2n], 
        [val31, val32, val33, ..., val3n], 
        ...
    ] 

    List of values ready to be plotted **series plot next to each other**:
    [
        [(1     , val11), (2     , val12), (3     , val13), ..., (n     , val1n)], 
        [(n  + 1, val21), (n  + 2, val22), (n  + 3, val23), ..., (n  + n, val2n)], 
        [(2n + 1, val31), (2n + 2, val32), (2n + 3, val33), ..., (2n + n, val3n)],
        ...    
    ],
    lonestSeriesLength = first item of last tuple in last list (each tuples have index included)
    '''
    result = []
    offset = 0
    for dataSeries in data:
        seriesPointList = [(i + offset, value) for i, value in enumerate(dataSeries)]
        offset += len(dataSeries)
        result.append(seriesPointList)
    numberOfSamples, _ = result[-1][-1]
    return result, numberOfSamples + 1

def flattenDataSeries(data:list[list[float]]) -> tuple[list[float], int]:
    result = nestedValuesListToFlatValueList(data)
    return result, len(result)

def nestedValuesListToFlatValueList(data:list[list[float]]) -> list[float]:
    '''
    Prepares data for gauss plot
    Converts list of measurements to flat 1 dimension list of values:
    data:
    [
        [val11, val12, val13, ..., val1n], 
        [val21, val22, val23, ..., val2n], 
        [val31, val32, val33, ..., val3n], 
        ...
    ] 

    List of values ready to be plotted **series plot next to each other**:
    [val11, val12, val13, ..., val1n, val21, val22, val23, ..., val2n, val31, val32, val33, ..., val3n, ...],
    '''
    return [value for siteData in data for value in siteData]

def uniqueBoundaryStrings(siteBoundariesList:list[list[str]]|str) -> list[str]:
    '''
    Processes given boundary strings and ensures that they are all unique.
    If string is passed then it is wrapped in a list
    If list is of strings is passed then it is casted to set to remove duplicates
    '''
    if isinstance(siteBoundariesList, str):
        return [siteBoundariesList]
    
    uniqueBoundaries = set()
    for siteBoundaries in siteBoundariesList:
        for boundaryString in siteBoundaries:
            uniqueBoundaries.add(boundaryString)
    return list(uniqueBoundaries)
        
def processBoundaryStrings(uniqueBoundariesList:list[str]) -> list[list[tuple[float, float]]]:
    '''
    Converts boundary string to a list with points that describe a 2D closed shape, for example:
    x1_y1_x2_y2_x3_y3_x4_y4 is converted to [(x1, y1), (x2, y2), (x3, y3), (x4, y4), (x1, y1),] 
    '''
    result = []
    for boundaryString in uniqueBoundariesList:
        x1, y1, x2, y2, x3, y3, x4, y4 = boundaryString.split('_')
        boundaryXYs = [(float(x1), float(y1)), (float(x2), float(y2)), (float(x3), float(y3)), (float(x4), float(y4)), (float(x1), float(y1))]
        result.append(boundaryXYs) 
    return result