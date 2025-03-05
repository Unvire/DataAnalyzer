def mergedDataSeries(data:list[list[float]]) -> tuple[list[list[tuple[int, float]]], int]:
    result = []
    for dataSeries in data:
        seriesPointList = [(i, value) for i, value in enumerate(dataSeries)]
        result.append(seriesPointList)    
    numberOfSamples = max([len(series) for series in result])
    return result, numberOfSamples

def continuousDataSeries(data:list[list[float]]) -> tuple[list[list[tuple[int, float]]], int]:
    result = []
    offset = 0
    for dataSeries in data:
        seriesPointList = [(i + offset, value) for i, value in enumerate(dataSeries)]
        offset += len(dataSeries)
        result.append(seriesPointList)
    numberOfSamples, _ = result[-1][-1]
    return result, numberOfSamples + 1

def flattenDataSeries(data:list[list[float]]) -> tuple[list[float], int]:
    result = [value for siteData in data for value in siteData]
    return result, len(result)

def valueDateSeriesToValueSeries(data:list[list[float, str]]) -> list[list[float]]:
    return [[value for value, _ in siteData] for siteData in data]

def nestedValuesListToFlatValueList(data:list[list[float]]) -> list[float]:
    return [value for siteData in data for value in siteData]