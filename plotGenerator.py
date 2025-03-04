import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

import listParser

class PlotGenerator:
    def __init__(self, canvas:plt.Figure):
        self.canvas = canvas
    
    def generatePlot(self, dataList:list[float], title:str, limits:list[float, float], isLogScale:bool, siteNames:list[str], isMergeDataSublists:bool=False):
        assert False

    def _addLegendAndScale(self, title:str, axisLabels:tuple[str], isLogScale:bool):
        yScale = {True:'symlog', False:'linear'}

        xLabel, yLabel = axisLabels
        self.canvas.ax.set_yscale(yScale[isLogScale])
        self._addPlotText(title, xLabel, yLabel)
    
    def _addPlotText(self, title:str, xLabel:str, yLabel:str):
        self.canvas.ax.set_title(title)
        self.canvas.ax.set_xlabel(xLabel)
        self.canvas.ax.set_ylabel(yLabel)
        self._setLegendWithUniqueLabels()
        self.canvas.draw()
    
    def _setLegendWithUniqueLabels(self):
        handles, labels = self.canvas.ax.get_legend_handles_labels()
        uniqueLabels = []
        uniqueHandles = []
        for handle, label in zip(handles, labels):
            if label not in uniqueLabels:
                uniqueLabels.append(label)
                uniqueHandles.append(handle)
        self.canvas.ax.legend(handles=uniqueHandles, labels=uniqueLabels, loc='upper center', bbox_to_anchor=(0.5, -0.05), fancybox=True, shadow=True, ncol=5)

class SequencePlotGenerator(PlotGenerator):
    def generatePlot(self, valuesList:list[list[float]], title:str, limitsList:list[list[float]], isLogScale:bool, siteNames:list[str], isMergeDataSublists:bool):
        listParserHandlesDict = {
            True: listParser.mergedDataSeries,
            False: listParser.continuousDataSeries
        }

        dataSeriesList, longestSeriesLength = listParserHandlesDict[isMergeDataSublists](valuesList)
        limitSeriesList, _ = listParserHandlesDict[isMergeDataSublists](limitsList)
        self.canvas.ax.cla()        
        self.canvas.ax.set_xlim([0, longestSeriesLength])

        for siteName, dataSeries, limitSeries in zip(siteNames, dataSeriesList, limitSeriesList):
            xLim = [point[0] for point in limitSeries]
            yLowerLim =  [point[1][0] for point in limitSeries]
            self.canvas.ax.plot(xLim, yLowerLim, '-.', linewidth=1, label=f'LSL', picker=1, color='red')

            yUpperLim =  [point[1][1] for point in limitSeries]
            self.canvas.ax.plot(xLim, yUpperLim, '-.', linewidth=1, label=f'USL', picker=1, color='orange')
            
            xVal, yVal = [point[0] for point in dataSeries], [point[1] for point in dataSeries]
            seriesLength = len(dataSeries)
            self.canvas.ax.plot(xVal, yVal, '.', linewidth=1, label=f'Site{siteName} ({seriesLength} samples)', picker=5)
        
        self.canvas.ax.grid()
        self._addLegendAndScale(title, ['Samples sorted by date', 'Value'], isLogScale)

class CapabilityPlotGenerator(PlotGenerator):
    def generatePlot(self, dataList:list[list[float]], title:str, limits:list[float], isLogScale:bool, *args):
        dataList, numberOfSamples = listParser.flattenDataSeries(dataList)

        self.canvas.ax.cla()
        mean = np.mean(dataList)
        numOfBins = _calculateNumberOfHistogramBins(dataList)

        self.canvas.ax.hist(dataList, bins=numOfBins, density=True, edgecolor='black', alpha=0.7, label=f'Measurements ({numberOfSamples} samples)')
        sns.kdeplot(dataList, color='blue', label='Density ST')
        self.canvas.ax.axvline(mean, linestyle='--', color='green', label='Mean')
        self._addLegendAndScale(title, limits, True, ['Value', 'Probability density'], isLogScale)

class CxCyPlotGenerator(PlotGenerator):
    def generatePlot(self, dataList:list[list[float]], title:str, boundaryXs:list[float], boundaryYs:list[float], siteNames:list[str]):
        self.canvas.ax.cla()
        for siteName, dataSeries in zip(siteNames, dataList):
            x = [point[0] for point in dataSeries]
            y = [point[1] for point in dataSeries]
            seriesLength = len(dataSeries)
            self.canvas.ax.plot(x, y, '.', linewidth=1, label=f'Site{siteName} ({seriesLength} samples)', picker=5)
        self.canvas.ax.plot(boundaryXs, boundaryYs, linewidth=2, color='red', label=f'Bin boundary', picker=5)
        
        self.canvas.ax.grid()
        self._addPlotText(title, 'CX', 'CY')


def _calculateNumberOfHistogramBins(data:list[float]) -> int:
    numberOfSamples = len(data)
    if numberOfSamples == 0:
        return 10
    
    binsStruges = int(1 + np.log2(numberOfSamples))
    binsRice = int(2 * numberOfSamples ** (1/3))
    if numberOfSamples > 1:
        q75, q25 = np.percentile(data, [75, 25])
        iqr = q75 - q25
        binWidth = 2 * iqr / (numberOfSamples ** (1/3))
        binsFd = int((max(data) - min(data)) / binWidth) if binWidth > 0 else binsRice
    else:
        binsFd = binsRice    
    return max(5, min(binsStruges, binsRice, binsFd))