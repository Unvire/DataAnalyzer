import math
import numpy as np

# https://datatab.net/statistics-calculator/process-capability
class ProcessParameterCalculator:
    def calculate(self, measurements:list[float|int], lowerLimit:float, upperLimit:float) -> tuple[float, float, float, float]:
        mean, sigmaOverall = self._calculateMeanSigmaOverall(measurements)
        pp, ppk = self._calculatePpPpk(mean, sigmaOverall, lowerLimit, upperLimit)
        cp, cpk = self._calculateCpCpk(len(measurements), mean, sigmaOverall, lowerLimit, upperLimit)
        return mean, sigmaOverall, pp, ppk, cp, cpk
    
    def _calculateMeanSigmaOverall(self, measurements:list[float|int]) -> tuple[float, float]:
        mean = np.mean(measurements)
        sigma = np.std(measurements, ddof=1)
        return mean, sigma
    
    def _calculatePpPpk(self, mean:float, sigmaOverall:float, LSL:float, USL:float) -> tuple[float, float]:
        pp = (USL - LSL) / (6 * sigmaOverall)
        PPL = (mean - LSL) / (3 * sigmaOverall)
        PPU = (USL - mean) / (3 * sigmaOverall)
        ppk = min(PPL, PPU)
        return pp, ppk

    def _calculateCpCpk(self, numOfSamples:int,  mean:float, sigmaOverall:float, LSL:float, USL:float) -> tuple[float, float]:
        c4_df =  math.sqrt(2 / (numOfSamples - 1)) * math.gamma(numOfSamples / 2) / math.gamma((numOfSamples - 1) / 2)
        sigmaWithin = sigmaOverall / c4_df
        cp = (USL - LSL) / (6 * sigmaWithin)
        CPL = (mean - LSL) / (3 * sigmaWithin)
        CPU = (USL - mean) / (3 * sigmaWithin)
        cpk = min(CPL, CPU)
        return cp, cpk