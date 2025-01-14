import math
import numpy as np

# https://datatab.net/statistics-calculator/process-capability
class ProcessParameterCalculator:
    def calculate(self, measurements:list[float|int], lowerLimit:float, upperLimit:float) -> tuple[float, float, float, float]:
        pass
    
    def _calculateMeanSigma(self, measurements:list[float|int]) -> tuple[float, float]:
        mean = np.mean(measurements)
        sigma = np.std(measurements, ddof=1)
        return mean, sigma