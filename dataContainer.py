class AbstractDataContainer:
    def __init__(self, name:str):
        self.name = name
        self.data = {}
    
    def getName(self) -> str:
        return self.name
    
    def addData(self, site:str, valueTuple:tuple[float|int|str, str]):
        value, date = valueTuple
        if site not in self.data:
            self.data[site] = []
            self.data = {key:self.data[key] for key in sorted(self.data)}
        processedTuple = float(value), date
        self.data[site].append(processedTuple)

    def getDataFromSite(self, site:str) -> list[list[tuple[float, str]]]:
        return [sorted(self.data[site], key=lambda item: item[1])]
    
    def getDataFromAllSites(self, sortBy:str) -> list[list[tuple[float, str]]]:
        result = []
        if sortBy == 'Date':
            for _, values in self.data.items():
                values = sorted(values, key=lambda item: item[1])
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
    def generateDataList(dataContainer:'DataContainer', orderBy:str, selectedSite:str) -> list[tuple[float, str]]:
        if selectedSite == 'All sites':
            dataList = dataContainer.getDataFromAllSites(orderBy)
        else:
            dataList = dataContainer.getDataFromSite(selectedSite)
        return dataList


class DataContainer(AbstractDataContainer):
    def __init__(self, name:str):
        super().__init__(name)
        self.lowerLimit = None
        self.upperLimit = None
    
    def setLimits(self, lowerLimit:float|int|str, upperLimit:float|int|str):
        self.lowerLimit = float(lowerLimit)
        self.upperLimit = float(upperLimit)
    
    def getLimits(self) -> list[float, float]:
        return [self.lowerLimit, self.upperLimit]