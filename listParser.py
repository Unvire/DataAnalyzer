def mergedDataSeries(data:list[list[float]]) -> tuple[list[list[tuple[int, float]]], int]:
    result = []
    for dataSeries in data:
        seriesPointList = [(i, value) for i, value in enumerate(dataSeries)]
        result.append(seriesPointList)    
    numberOfSamples = len(result[0])  
    return result, numberOfSamples

def continuousDataSeries(data:list[list[float]]) -> tuple[list[list[tuple[int, float]]], int]:
    result = []
    offset = 0
    for dataSeries in data:
        seriesPointList = [(i + offset, value) for i, value in enumerate(dataSeries)]
        offset += len(dataSeries)
        result.append(seriesPointList)
    numberOfSamples = sum([len(series) for series in result])
    return result, numberOfSamples

def flattenValueList(data:list[list[float]]) -> tuple[list[float], int]:
    result = [value for siteData in data for value in siteData]
    return result, len(result)