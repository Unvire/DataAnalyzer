class DataPoint:
    def __init__(self, value:float|tuple[float]|str, date:str):
        self.value = value
        self.date = date
    
    def getValue(self) -> float|tuple[float]:
        return self.value
    
    def getDate(self) -> str:
        return self.date
