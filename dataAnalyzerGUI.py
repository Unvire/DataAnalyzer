import sys
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from PyQt5 import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from templateDataAnalyzerGUI import Ui_MainWindow
from fileProcessorFactory import FileProcessorsFactory

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = plt.figure(figsize=(width, height), dpi=dpi)
        self.ax = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)
        self.setParent(parent)

class DataAnalyzerGUI(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(DataAnalyzerGUI, self).__init__()
        self.setupUi(self)

        self.measurements = {}
        self.selectedTest = ''

        self.factory = FileProcessorsFactory()
        self.factory.addObserver(self)

        FILE_PROCESSORS = ['Select file type', 'SPEA']
        for fileName in FILE_PROCESSORS:
            self.comboBox.addItem(fileName)

        self.comboBox.currentTextChanged.connect(self.selectProcessor)
        self.pushButton.clicked.connect(self.selectFolder)
        self.listWidget.itemClicked.connect(lambda item: self.listWidgetClickedEvent(item))

        self.canvas = MplCanvas(self.plotFrame)
        self.plot_layout = QtWidgets.QVBoxLayout(self.plotFrame)
        self.plot_layout.addWidget(self.canvas)
        self.plot()
    
    def setMeasurements(self, measurementsDict:dict):
        self.measurements = measurementsDict
    
    def selectProcessor(self, value:str):  
        self.factory.setProcessorType(value)

    def selectFolder(self):
        folderPath = str(QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory"))
        if folderPath:
            self.processLogsInFolder(folderPath)
    
    def processLogsInFolder(self, folderPath:str):
        self.resetSelectSitesComboBox()
        self.factory.processAllLogsInFolder(folderPath)
        measurements = self.factory.getAllMeasurements()
        self.setMeasurements(measurements)
        self.generateMeasurementsList()
        self.updateNumOfSites()

    def listWidgetClickedEvent(self, item):
        self.selectedTest = item.text()
        self.generatePlot()

    def generatePlot(self):
        generatePlot = {'Sequence plot':self._sequencePlot, 
                        'Capability plot': self._capabilityPlot}

        testName = self.selectedTest
        site = '1'
        plotType = 'Capability plot'

        data = self.measurements[testName]        
        dataList = data.getDataFromSite(site)
        limits = data.getLimits()
        
        generatePlot[plotType](dataList, testName, limits)

    def _sequencePlot(self, dataList:list[float], title:str, limits:list[float, float]):
        numberOfSamples = len(dataList)
        self.canvas.ax.cla()
        self.canvas.ax.plot(dataList, '.', linewidth=1, label=f'Data ({numberOfSamples} samples)')
        self.canvas.ax.set_xlim([0, numberOfSamples])
        self.canvas.ax.grid()
        self._addCommonPlotElements(title, limits, False, ['Sample', 'Value'])
    
    def _capabilityPlot(self, dataList:list[float], title:str, limits:list[float, float]):
        numberOfSamples = len(dataList)        
        self.canvas.ax.cla()
        mean = np.mean(dataList)

        self.canvas.ax.hist(dataList, bins=10, density=True, edgecolor='black', alpha=0.7, label=f'Measurements ({numberOfSamples} samples)')
        sns.kdeplot(dataList, color='blue', label='Density ST')
        self.canvas.ax.axvline(mean, linestyle='--', color='green', label='Mean')
        self._addCommonPlotElements(title, limits, True, ['Value', 'Probability density'])
    
    def _addCommonPlotElements(self, title:str, limits:tuple[float], isLimitsVertical:bool, axisLabels:tuple[str]):
        limitHandles = {True: self.canvas.ax.axvline, False:self.canvas.ax.axhline}
        
        lowerLimitValue, upperLimitValue = limits
        xLabel, yLabel = axisLabels
        limitHandles[isLimitsVertical](lowerLimitValue, linestyle='--', color='red', label='LSL')
        limitHandles[isLimitsVertical](upperLimitValue, linestyle='--', color='orange', label='USL')
        self.canvas.ax.set_title(title)
        self.canvas.ax.set_xlabel(xLabel)
        self.canvas.ax.set_ylabel(yLabel)
        self.canvas.ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), fancybox=True, shadow=True, ncol=5)
        self.canvas.draw()
    
    def updateProgressBar(self, progressPercent:int):
        self.progressBar.setProperty("value", progressPercent)
    
    def generateMeasurementsList(self):
        self.listWidget.clear()
        self.listWidget.addItems(self.measurements.keys())
    
    def updateNumOfSites(self):
        testNames = list(self.measurements.keys())
        firstDataContainer = self.measurements[testNames[0]]
        numOfTests = firstDataContainer.getNumOfSites()

        if numOfTests > 1:           
            for i in range(numOfTests):
                self.selectSiteComboBox.addItem(f'{i + 1}')
    
    def resetSelectSitesComboBox(self):
        self.selectSiteComboBox.clear()
        self.selectSiteComboBox.addItem('All sites')

    def plot(self):
        t = np.arange(0.0, 2.0, 0.01)
        s = np.sin(2 * np.pi * t)
        self.canvas.ax.plot(t, s)
        self.canvas.ax.set(title='Sinus Wave', xlabel='Time (s)', ylabel='Amplitude')
        self.canvas.draw()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = DataAnalyzerGUI()
    window.show()
    sys.exit(app.exec_())