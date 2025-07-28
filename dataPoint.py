class DataPoint:
    def __init__(self, value:float|tuple[float]|str, limits:tuple[float, float]|str, date:str, serialNumber:str):
        self.value = value
        self.date = date
        self.limits = limits
        self.serialNumber = serialNumber
    
    def __eq__(self, dataPointInstance:'DataPoint'):
        isLimitsEqual = self._isFloatOrSequenceEqual(self.limits, dataPointInstance.limits)
        isValueEqual = self._isFloatOrSequenceEqual(self.value, dataPointInstance.value)
        return isValueEqual and isLimitsEqual and self.date == dataPointInstance.date

    def _isFloatOrSequenceEqual(self, firstVariable, secondVariable) -> bool:
        if isinstance(firstVariable, tuple) or isinstance(firstVariable, list):
            isValueEqual = all([val1 == val2 for val1, val2 in zip(list(firstVariable), list(secondVariable))])
        else:
            isValueEqual = firstVariable == secondVariable
        return isValueEqual
    
    def __repr__(self) -> str:
        return f'DataPoint: {self.value=}, {self.date=}, {self.limits=}'
    
    def getValue(self) -> float|tuple[float]:
        return self.value
    
    def getDate(self) -> str:
        return self.date
    
    def getLimits(self) -> tuple[float, float]|str:
        return self.limits
    
    def getSerialNumber(self) -> str:
        return self.serialNumber
