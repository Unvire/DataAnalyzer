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

    def addData(self, site:str, value:float|int|str):
        self.data.setdefault(site, [])
        self.data[site].append(float(value))
    
    def getDataFromSite(self, site:str) -> list[float]:
        return self.data[site]
    
    def getDataFromAllSites(self) -> list[str]:
        result = []
        for _, values in self.data.items():
            result += values
        return result
    
    def getNumOfSites(self) -> int:
        return len(self.data)
