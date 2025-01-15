import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

class PlotGenerator:
    def __init__(self, canvas:plt.Figure):
        self.canvas = canvas
    
    def generatePlot(self, dataList:list[float], title:str, limits:list[float, float], isLogScale:bool):
        pass

    def _addCommonPlotElements(self, title:str, limits:tuple[float], isLimitsVertical:bool, axisLabels:tuple[str], isLogScale):
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
    def generatePlot(self, dataList:list[float], title:str, limits:list[float], isLogScale:bool):
        numberOfSamples = len(dataList)
        self.canvas.ax.cla()
        self.canvas.ax.plot(dataList, '.', linewidth=1, label=f'Data ({numberOfSamples} samples)')
        self.canvas.ax.set_xlim([0, numberOfSamples])
        self.canvas.ax.grid()
        self._addCommonPlotElements(title, limits, False, ['Sample', 'Value'], isLogScale)

class CapabilityPlotGenerator(PlotGenerator):
    def generatePlot(self, dataList:list[float], title:str, limits:list[float], isLogScale:bool):
        numberOfSamples = len(dataList)        
        self.canvas.ax.cla()
        mean = np.mean(dataList)

        self.canvas.ax.hist(dataList, bins=10, density=True, edgecolor='black', alpha=0.7, label=f'Measurements ({numberOfSamples} samples)')
        sns.kdeplot(dataList, color='blue', label='Density ST')
        self.canvas.ax.axvline(mean, linestyle='--', color='green', label='Mean')
        self._addCommonPlotElements(title, limits, True, ['Value', 'Probability density'], isLogScale)