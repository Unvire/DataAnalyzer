from dataPoint import DataPoint

class DataContainer:
    def __init__(self, name:str):
        self.limits = {}
        self.name = name
        self.data = {}
    
    def getName(self) -> str:
        return self.name
    
    def addData(self, site:str, value:float|int|str, limits:tuple[float, float]|str, testDate:str):
        def valueToFloats(value):
            if isinstance(value, tuple) or isinstance(value, list):
                value = [float(val) for val in list(value)]
            else:
                value = float(value)
            return value
        
        value = valueToFloats(value)
        dataPointInstance = DataPoint(value, limits, testDate)
        if site not in self.data:
            self._addSiteAndSortInPlace(site)
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

    def getLimits(self, site:str) -> list[list[tuple[float, float]|str]]:
        dataPointsList = self.data[site]
        return [dataPoint.getLimits() for dataPoint in dataPointsList]
    
    def _addSiteAndSortInPlace(self, siteName:str):
        self.data[siteName] = []
        self.data = {key:self.data[key] for key in sorted(self.data)}
    
    
    @staticmethod
    def generateDataList(dataContainer:'DataContainer', orderBy:str, selectedSite:str) -> list[DataPoint]:
        if selectedSite == 'All sites':
            dataList = dataContainer.getDataFromAllSites(orderBy)
        else:
            dataList = dataContainer.getDataFromSite(selectedSite)
        return dataList