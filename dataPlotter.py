import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

class DataPlotter:
    def sequencePlot(self, dataList:list[float], title:str, limits:list[float, float]):
        numberOfSamples = len(dataList)

        plt.plot(dataList, '.', linewidth=1, label=f'Data ({numberOfSamples} samples)')
        plt.xlim([0, numberOfSamples])
        plt.grid()
        self._addCommonPlotElements(title, limits, False, ['Sample', 'Value'])

    def normalDistributionPlot(self, dataList:list[float], title:str, limits:list[float, float]):
        numberOfSamples = len(dataList)
        mean = np.mean(dataList)

        plt.hist(dataList, bins=10, density=True, edgecolor='black', alpha=0.7, label=f'Measurements ({numberOfSamples} samples)')
        sns.kdeplot(dataList, color='blue', label='Density ST')
        plt.axvline(mean, linestyle='--', color='green', label='Mean')
        self._addCommonPlotElements(title, limits, True, ['Value', 'Probability density'])

    def normalProbabilityPlot(self, dataList:list[float], title:str, limits:list[float, float]):
        pass

    def _addCommonPlotElements(self, title:str, limits:tuple[float], isLimitsVertical:bool, axisLabels:tuple[str]):
        limitHandles = {True: plt.axvline, False:plt.axhline}
        
        lowerLimitValue, upperLimitValue = limits
        xLabel, yLabel = axisLabels
        limitHandles[isLimitsVertical](lowerLimitValue, linestyle='--', color='red', label='LSL')
        limitHandles[isLimitsVertical](upperLimitValue, linestyle='--', color='orange', label='USL')
        plt.rcParams['figure.figsize'] = (9, 9)
        plt.title(title)
        plt.xlabel(xLabel)
        plt.ylabel(yLabel)
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), fancybox=True, shadow=True, ncol=5)
        plt.show()

if __name__ == '__main__':
    import os
    from tkinter import filedialog
    import dataContainer, fileProcessorFactory

    logFolderPath = folder_selected = filedialog.askdirectory()
    speaFileProcessor = fileProcessorFactory.FileProcessorsFactory()
    speaFileProcessor.setProcessorType('SPEA')
    speaFileProcessor.processAllLogsInFolder(logFolderPath)
    data = speaFileProcessor.getTestMeasurements('L7-1 | INDL7 20m 20% -20%')

    plotter = DataPlotter()
    plotter.sequencePlot(data.getDataFromSite('1'), data.name, data.getLimits())
    plotter.normalDistributionPlot(data.getDataFromSite('1'), data.name, data.getLimits())