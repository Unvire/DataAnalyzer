import sys
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from PyQt5 import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

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
        self.selectedSite = '0'
        self.selectedPlotType = 'Sequence plot'        
        self.isLogScale = False

        self.factory = FileProcessorsFactory()
        self.factory.addObserver(self)

        FILE_PROCESSORS = ['Select file type', 'SPEA']
        for fileName in FILE_PROCESSORS:
            self.comboBox.addItem(fileName)

        self.comboBox.currentTextChanged.connect(lambda value: self.selectProcessor(value))
        self.pushButton.clicked.connect(self.selectFolder)
        self.changePlotButton.clicked.connect(self.selectPlotType)
        self.listWidget.itemClicked.connect(lambda item: self.listWidgetClickedEvent(item))
        self.selectSiteComboBox.activated.connect(lambda value: self.selectSiteComboBoxClickedEvent(value))
        self.changeYScaleButton.clicked.connect(self.changeYScale)

        self.canvas = MplCanvas(self.plotFrame)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        self.plotLayout = QtWidgets.QVBoxLayout(self.plotFrame)
        self.plotLayout.addWidget(self.toolbar)
        self.plotLayout.addWidget(self.canvas)
    
    def setMeasurements(self, measurementsDict:dict):
        self.measurements = measurementsDict
    
    def selectProcessor(self, value:str):  
        self.factory.setProcessorType(value)
    
    def selectPlotType(self):
        plotTypeMap = {'Sequence plot':'Capability plot', 'Capability plot':'Sequence plot'}
        self.selectedPlotType = plotTypeMap[self.selectedPlotType]
        self.generatePlot()

    def selectFolder(self):
        folderPath = str(QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory"))
        if folderPath:
            self.processLogsInFolder(folderPath)
    
    def changeYScale(self):
        self.isLogScale = not self.isLogScale
        self.generatePlot()
    
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
    
    def selectSiteComboBoxClickedEvent(self, value:str|int):
        self.selectedSite = str(value)
        self.generatePlot()

    def generatePlot(self):
        generatePlot = {'Sequence plot':self._sequencePlot, 
                        'Capability plot': self._capabilityPlot}
        
        testName = self.selectedTest     
        data = self.measurements[testName]

        site = self.selectedSite
        if site == '0':
            dataList = data.getDataFromAllSites()
        else:
            dataList = data.getDataFromSite(site)
        
        plotType = self.selectedPlotType
        limits = data.getLimits()
        generatePlot[plotType](dataList, testName, limits, self.isLogScale)

        mean = np.mean(dataList)
        sigma = np.std(dataList)
        self.updateStatisticalData(len(dataList), limits, mean, sigma)

    def _sequencePlot(self, dataList:list[float], title:str, limits:list[float, float], isLogScale:bool):
        numberOfSamples = len(dataList)
        self.canvas.ax.cla()
        self.canvas.ax.plot(dataList, '.', linewidth=1, label=f'Data ({numberOfSamples} samples)')
        self.canvas.ax.set_xlim([0, numberOfSamples])
        self.canvas.ax.grid()
        self._addCommonPlotElements(title, limits, False, ['Sample', 'Value'], isLogScale)
    
    def _capabilityPlot(self, dataList:list[float], title:str, limits:list[float, float], isLogScale:bool):
        numberOfSamples = len(dataList)        
        self.canvas.ax.cla()
        mean = np.mean(dataList)

        self.canvas.ax.hist(dataList, bins=10, density=True, edgecolor='black', alpha=0.7, label=f'Measurements ({numberOfSamples} samples)')
        sns.kdeplot(dataList, color='blue', label='Density ST')
        self.canvas.ax.axvline(mean, linestyle='--', color='green', label='Mean')
        self._addCommonPlotElements(title, limits, True, ['Value', 'Probability density'], isLogScale)
    
    def updateStatisticalData(self, numOfSamples:int, limits:tuple[float, float], mean:float, sigma:float):
        LSL, USL = limits
        self.samplesEdit.setText(str(numOfSamples))
        self.lowerLimitEdit.setText(str(LSL))
        self.upperLimitEdit.setText(str(USL))
        self.averageEdit.setText(str(mean))
        self.sigmaEdit.setText(str(sigma))
    
    def _addCommonPlotElements(self, title:str, limits:tuple[float], isLimitsVertical:bool, axisLabels:tuple[str], isLogScale):
        yScale = {True:'log', False:'linear'}        
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


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = DataAnalyzerGUI()
    window.show()
    sys.exit(app.exec_())