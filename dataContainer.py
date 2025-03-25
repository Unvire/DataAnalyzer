import abc
from dataPoint import DataPoint

class AbstractDataContainer(metaclass=abc.ABCMeta):
    def __init__(self, name:str):
        self.name = name
        self.data = {}
    
    def getName(self) -> str:
        return self.name
    
    @abc.abstractmethod
    def addData(self, *args):
        pass
    
    @abc.abstractmethod
    def getData(self, *args):
        pass

class DataContainer(AbstractDataContainer):    
    def addData(self, site:str, value:float|int|str, limits:tuple[float, float]|str, testDate:str):        
        value = DataContainer.valueToFloats(value)
        dataPointInstance = DataPoint(value, limits, testDate)
        if site not in self.data:
            self._addSiteAndSortInPlace(site)
        self.data[site].append(dataPointInstance)

    def getData(self, site:str) -> list[list[DataPoint]]:
        return self._getDataFromAllSites() if site == 'All sites' else self._getDataFromSite(site)            

    def getNumOfSites(self) -> int:
        return len(self.data)
    
    def getSiteNames(self) -> list[str]:
        return list(self.data.keys())

    def getLimits(self, site:str) -> list[list[tuple[float, float]|str]]:
        dataPointsList = self.data[site]
        return [dataPoint.getLimits() for dataPoint in dataPointsList]
    
    def isCxCyMeasurement(self) -> bool:
        firstSite = self.getSiteNames()[0]
        dataPoint = self.data[firstSite][0]
        limits = dataPoint.getLimits()
        return isinstance(limits, str)

    def _getDataFromSite(self, site:str) -> list[list[DataPoint]]:
        return [sorted(self.data[site], key=lambda dataPointInstance: dataPointInstance.getDate())]    
    
    def _getDataFromAllSites(self) -> list[list[DataPoint]]:
        result = []
        for siteName, values in self.data.items():
            values = self._getDataFromSite(siteName)
            result += values
        return result
    
    def _addSiteAndSortInPlace(self, siteName:str):
        self.data[siteName] = []
        self.data = {key:self.data[key] for key in sorted(self.data)}   

    @staticmethod    
    def valueToFloats(value):
        if isinstance(value, tuple) or isinstance(value, list):
            value = [float(val) for val in list(value)]
        else:
            value = float(value)
        return value 
    
    @staticmethod
    def getValuesFromDataPointsList(dataPointsList:list[list[DataPoint]]) -> list[list[float | tuple[float, float]]]:
        result = []
        for siteDataPointsList in dataPointsList:
            result.append([dataPointInstance.getValue() for dataPointInstance in siteDataPointsList])
        return result
    
    @staticmethod
    def getLimitsFromDataPointsList(dataPointsList:list[list[DataPoint]], selectedLimits:str) -> list[list[str | tuple[float, float]]] | list[str|float, str|float]:
        result = []
        for siteDataPointsList in dataPointsList:
            result.append([dataPointInstance.getLimits() for dataPointInstance in siteDataPointsList])
            
        if selectedLimits == 'Oldest':
            return result[0][0]
        elif selectedLimits == 'Newest':
            return result[0][-1]
        return result
    
    @staticmethod
    def getDateStringsFromDataPointsList(dataPointsList:list[list[DataPoint]]) -> list[list[str]]:
        result = []
        for siteDataPointsList in dataPointsList:
            result.append([dataPointInstance.getDate() for dataPointInstance in siteDataPointsList])
        return result

class LedDataContainer(AbstractDataContainer):
    pass

if __name__ == '__main__':
    a = LedDataContainer()