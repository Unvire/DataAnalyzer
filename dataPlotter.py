import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm
import seaborn as sns

class DataPlotter:
    def sequencePlot(self, dataList:list[float], title:str, limits:list[float, float]):
        lowerLimitValue, upperLimitValue = limits
        numberOfSamples = len(dataList)
        lowerLimitList = [lowerLimitValue] * numberOfSamples
        upperLimitList = [upperLimitValue] * numberOfSamples

        plt.plot(dataList, '.', linewidth=1)
        plt.plot(lowerLimitList)
        plt.plot(upperLimitList)
        plt.title(title)
        plt.xlim([0, numberOfSamples])
        plt.xlabel('Sample')
        plt.ylabel('Value')
        plt.legend(['Data', 'Lower limit', 'Upper limit'])
        plt.grid()
        plt.show()

    def normalDistributionPlot(self, dataList:list[float], title:str, limits:list[float, float]):
        lowerLimitValue, upperLimitValue = limits
        mean = np.mean(dataList)

        x = np.linspace(np.min(dataList), np.max(dataList), 2 * len(dataList))
        y = norm.pdf(x, loc=5, scale=1)

        plt.figure(figsize=(15,10))
        plt.figure().set_figheight(9)
        plt.hist(dataList, bins=10, density=True, edgecolor='black', alpha=0.7, label='Measurements')
        sns.kdeplot(dataList, color="blue", label="Density ST")
        plt.plot(x, y, linestyle="--", color="black", label="Theorethical Density ST")
        plt.axvline(lowerLimitValue, linestyle="--", color="red", label="LSL")
        plt.axvline(upperLimitValue, linestyle="--", color="orange", label="USL")
        plt.axvline(mean, linestyle="--", color="green", label="Mean")
        plt.title(title)
        plt.xlabel('Value')
        plt.ylabel('Probability Density')
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), fancybox=True, shadow=True, ncol=5)
        plt.show()

    def normalProbabilityPlot(self, dataList:list[float], title:str, limits:list[float, float]):
        pass

if __name__ == '__main__':
    import os
    from tkinter import filedialog
    import dataContainer, fileProcessorFactory

    logFolderPath = folder_selected = filedialog.askdirectory()
    speaFileProcessor = fileProcessorFactory.FileProcessorsFactory('SPEA')
    speaFileProcessor.processAllLogsInFolder(logFolderPath)
    data = speaFileProcessor.getTestMeasurements('L7-1 -> INDL7 20m 20% -20%')

    plotter = DataPlotter()
    #plotter.sequencePlot(data.getDataFromSite('1'), data.name, data.getLimits())
    plotter.normalDistributionPlot(data.getDataFromSite('1'), data.name, data.getLimits())