import numpy as np

# https://datatab.net/statistics-calculator/process-capability
class ProcessParameterCalculator:
    def calculate(self, measurements:list[float|int], lowerLimit:float, upperLimit:float) -> tuple[float, float, float, float, float, float]:
        mean, sigmaOverall, sigmaWithin = self._calculateMeanAndSigmas(measurements)
        pp, ppk = self._calculatePpPpk(mean, sigmaOverall, lowerLimit, upperLimit)
        cp, cpk = self._calculateCpCpk(mean, sigmaWithin, lowerLimit, upperLimit)
        stability = self._calculateStability(min(measurements), max(measurements))
        return mean, sigmaOverall, pp, ppk, cp, cpk, stability
    
    def _calculateMeanAndSigmas(self, measurements:list[float|int]) -> tuple[float, float, float]:
        mean = np.mean(measurements)
        sigmaOverall= np.std(measurements, ddof=1)
        sigmaWithin = np.std(measurements, ddof=0)
        return mean, sigmaOverall, sigmaWithin
    
    def _calculatePpPpk(self, mean:float, sigmaOverall:float, LSL:float, USL:float) -> tuple[float, float]:
        pp = (USL - LSL) / (6 * sigmaOverall)
        PPL = (mean - LSL) / (3 * sigmaOverall)
        PPU = (USL - mean) / (3 * sigmaOverall)
        ppk = min(PPL, PPU)
        return pp, ppk

    def _calculateCpCpk(self, mean:float, sigmaWithin:float, LSL:float, USL:float) -> tuple[float, float]:
        cp = (USL - LSL) / (6 * sigmaWithin)
        CPL = (mean - LSL) / (3 * sigmaWithin)
        CPU = (USL - mean) / (3 * sigmaWithin)
        cpk = min(CPL, CPU)
        return cp, cpk
    
    def _calculateStability(self, minVal:float, maxVal:float) -> float:
        if minVal == 0:
            return 0
        return maxVal / minVal - 1