import matplotlib.pyplot as plt

class DataPlotter:
    def __init__(self, dataList:list[float]):
        pass

    def sequencePlot(self, dataList:list[float]):
        pass

    def normalDistributionPlot(self, dataList:list[float]):
        pass

    def normalProbabilityPlot(self, dataList:list[float]):
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
    plotter.sequencePlot(data.getDataFromSite('1'))