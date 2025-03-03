from dataPoint import DataPoint

class AbstractDataContainer:
    def __init__(self, name:str):
        self.limits = {}
        self.name = name
        self.data = {}
    
    def getName(self) -> str:
        return self.name
    
    def addData(self, site:str, value:float|int|str, testDate:str):
        if isinstance(value, tuple) or isinstance(value, list):
            value = [float(val) for val in list(value)]
        else:
            value = float(value)
            
        dataPointInstance = DataPoint(value, testDate)
        if site not in self.data:
            self.data[site] = []
            self.data = {key:self.data[key] for key in sorted(self.data)}
        self.data[site].append(dataPointInstance)

    def getDataFromSite(self, site:str) -> list[list[DataPoint]]:
        return [sorted(self.data[site], key=lambda dataPointInstance: dataPointInstance.getValue())]
    
    def getDataFromAllSites(self, sortBy:str) -> list[list[DataPoint]]:
        result = []
        if sortBy == 'Date':
            for _, values in self.data.items():
                values = sorted(values, key=lambda dataPointInstance: dataPointInstance.getDate())
                result.append(values)
        else:
            for site in self.data:
                result += self.getDataFromSite(site)
        return result

    def getNumOfSites(self) -> int:
        return len(self.data)
    
    def getSiteNames(self) -> list[str]:
        return list(self.data.keys())
    
    @staticmethod
    def generateDataList(dataContainer:'DataContainer', orderBy:str, selectedSite:str) -> list[DataPoint]:
        if selectedSite == 'All sites':
            dataList = dataContainer.getDataFromAllSites(orderBy)
        else:
            dataList = dataContainer.getDataFromSite(selectedSite)
        return dataList


class DataContainer(AbstractDataContainer):
    def addLimits(self, lowerLimit:float|int|str, upperLimit:float|int|str, testDate:str):
        if self.limits:
            lastLowerLimitInstance, lastUpperLimitInstance = self.limits[-1]

        lowerLimit = DataPoint(float(lowerLimit), testDate)
        upperLimit = DataPoint(float(upperLimit), testDate)

        self.limits.append([lowerLimit, upperLimit])
    
    def getLimits(self) -> list[list[DataPoint, DataPoint]]:
        return self.limits


class CxCyDataContainer(AbstractDataContainer):
    def addLimits(self, boundaryXYsString:str, testDate:str):
        limitString = DataPoint(boundaryXYsString, testDate)
        self.limits.append(limitString)
    
    def getLimits(self) -> list[DataPoint]:
        return self.limits