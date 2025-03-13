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

def uniqueBoundaryStrings(siteBoundariesList:list[list[str]]|str) -> list[str]:
    if isinstance(siteBoundariesList, str):
        return [siteBoundariesList]
    
    uniqueBoundaries = set()
    for siteBoundaries in siteBoundariesList:
        for boundaryString in siteBoundaries:
            uniqueBoundaries.add(boundaryString)
    return list(uniqueBoundaries)
        
def processBoundaryStrings(uniqueBoundariesList:list[str]) -> list[list[tuple[float, float]]]:
    result = []
    for boundaryString in uniqueBoundariesList:
        x1, y1, x2, y2, x3, y3, x4, y4 = boundaryString.split('_')
        boundaryXYs = [(float(x1), float(y1)), (float(x2), float(y2)), (float(x3), float(y3)), (float(x4), float(y4)), (float(x1), float(y1))]
        result.append(boundaryXYs) 
    return result