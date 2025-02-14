import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

import listParser

class PlotGenerator:
    def __init__(self, canvas:plt.Figure):
        self.canvas = canvas
    
    def generatePlot(self, dataList:list[float], title:str, limits:list[float, float], isLogScale:bool, siteNames:list[str], isMergeDataSublists:bool=False):
        assert False

    def _addCommonPlotElements(self, title:str, limits:tuple[float], isLimitsVertical:bool, axisLabels:tuple[str], isLogScale:bool):
        yScale = {True:'symlog', False:'linear'}        
        limitHandles = {True: self.canvas.ax.axvline, False:self.canvas.ax.axhline}

        lowerLimitValue, upperLimitValue = limits
        xLabel, yLabel = axisLabels
        limitHandles[isLimitsVertical](lowerLimitValue, linestyle='--', color='red', label='LSL')
        limitHandles[isLimitsVertical](upperLimitValue, linestyle='--', color='orange', label='USL')
        self.canvas.ax.set_title(title)
        self.canvas.ax.set_xlabel(xLabel)
        self.canvas.ax.set_ylabel(yLabel)
        self.canvas.ax.set_yscale(yScale[isLogScale])
        self.canvas.ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), fancybox=True, shadow=True, ncol=5)
        self.canvas.draw()

class SequencePlotGenerator(PlotGenerator):
    def generatePlot(self, dataList:list[float], title:str, limits:list[float], isLogScale:bool, siteNames:list[str], isMergeDataSublists:bool):
        if isMergeDataSublists:
            dataSeriesList, numberOfSamples = listParser.mergedDataSeries(dataList)
        else:            
            dataSeriesList, numberOfSamples = listParser.continuousDataSeries(dataList)
        
        self.canvas.ax.cla()        
        self.canvas.ax.set_xlim([0, numberOfSamples])

        for siteName, dataSeries in zip(siteNames, dataSeriesList):
            x = [point[0] for point in dataSeries]
            y = [point[1] for point in dataSeries]
            self.canvas.ax.plot(x, y, '.', linewidth=1, label=f'Site{siteName} ({numberOfSamples} samples)', picker=5)
        
        self.canvas.ax.grid()
        self._addCommonPlotElements(title, limits, False, ['Samples sorted by date', 'Value'], isLogScale)

class CapabilityPlotGenerator(PlotGenerator):
    def generatePlot(self, dataList:list[float], title:str, limits:list[float], isLogScale:bool, siteNames:list[str], isMergeDataSublists:bool):
        unnestedDataList = [value for siteData in dataList for value in siteData]
        
        numberOfSamples = len(dataList)        
        self.canvas.ax.cla()
        mean = np.mean(dataList)

        self.canvas.ax.hist(unnestedDataList, bins=10, density=True, edgecolor='black', alpha=0.7, label=f'Measurements ({numberOfSamples} samples)')
        sns.kdeplot(dataList, color='blue', label='Density ST')
        self.canvas.ax.axvline(mean, linestyle='--', color='green', label='Mean')
        self._addCommonPlotElements(title, limits, True, ['Value', 'Probability density'], isLogScale)