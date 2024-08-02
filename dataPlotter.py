import matplotlib.pyplot as plt

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
        pass

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
    plotter.sequencePlot(data.getDataFromSite('1'), data.name, data.getLimits())