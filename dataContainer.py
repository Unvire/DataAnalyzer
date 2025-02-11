class DataContainer():
    def __init__(self, name:str):
        self.name = name
        self.data = {}
        self.lowerLimit = None
        self.upperLimit = None
    
    def getName(self) -> str:
        return self.name
    
    def setLimits(self, lowerLimit:float|int|str, upperLimit:float|int|str):
        self.lowerLimit = float(lowerLimit)
        self.upperLimit = float(upperLimit)
    
    def getLimits(self) -> list[float, float]:
        return [self.lowerLimit, self.upperLimit]

    def addData(self, site:str, valueTuple:tuple[float|int|str, str]):
        value, date = valueTuple
        self.data.setdefault(site, [])
        processedTuple = float(value), date
        self.data[site].append(processedTuple)
    
    def getDataFromSite(self, site:str) -> list[tuple[float, str]]:
        return sorted(self.data[site], key=lambda item: item[1])
    
    def getDataFromAllSites(self, sortBy:str) -> list[tuple[float, str]]:
        result = []
        if sortBy == 'Date':
            for _, values in self.data.items():
                result += values
            result = sorted(result, key=lambda item: item[1])
        else:
            for site in self.data:
                result += self.getDataFromSite(site)
        return result

    def getNumOfSites(self) -> int:
        return len(self.data)
    
    def getSiteNames(self) -> list[str]:
        return list(self.data.keys())