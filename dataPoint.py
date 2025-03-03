class DataPoint:
    def __init__(self, value:float|tuple[float]|str, date:str):
        self.value = value
        self.date = date
    
    def __eq__(self, dataPointInstance:'DataPoint'):
        if isinstance(self.value, tuple) or isinstance(self.value, list):
            isValueEqual = all([val1 == val2 for val1, val2 in zip(list(self.value), list(dataPointInstance.value))])
        else:
            isValueEqual = self.value == dataPointInstance.value
        return isValueEqual and self.date == dataPointInstance.date
    
    def __repr__(self) -> str:
        return f'DataPoint: {self.value=}, {self.date=}'
    
    def getValue(self) -> float|tuple[float]:
        return self.value
    
    def getDate(self) -> str:
        return self.date
