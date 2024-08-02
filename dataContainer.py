class DataContainer():
    def __init__(self, name:str):
        self.name = name
        self.data = {}
        self.lowerLimit = None
        self.upperLimit = None
    
    def setLimits(self, lowerLimit:float, upperLimit:float):
        self.lowerLimit = float(lowerLimit)
        self.upperLimit = float(upperLimit)
    
    def getLimits(self) -> list[float, float]:
        return [self.lowerLimit, self.upperLimit]

    def addData(self, site:str, value:float):
        self.data.setdefault(site, [])
        self.data[site].append(float(value))
    
    def getDataFromSite(self, site:str) -> list[float]:
        return self.data[site]
    
    def getDataFromAllSites(self) -> list[str]:
        result = []
        for _, values in self.data.items():
            result += values
        return result

if __name__ == '__main__':
    a = DataContainer('test')
