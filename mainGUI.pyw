import sys, os
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from PyQt5 import QtWidgets, uic
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from testListWrapper import TestListWrapper
from fileProcessorFactory import FileProcessorsFactory
from processCalculator import ProcessParameterCalculator
from plotGenerator import SequencePlotGenerator, CapabilityPlotGenerator
from dataContainer import DataContainer

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = plt.figure(figsize=(width, height), dpi=dpi)
        self.ax = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)
        self.setParent(parent)

class DataAnalyzerGUI(QtWidgets.QMainWindow):
    FILE_PROCESSORS = ['Select file type', 'SPEA', 'FWK', 'Column file']

    def __init__(self):
        super().__init__()
        uiFilePath = os.path.join(os.getcwd(), 'ui', 'main.ui')
        uic.loadUi(uiFilePath, self)

        self.testListWrapper = TestListWrapper(self.listWidget, self.filterTestsButton, self.resetFilterButton, self.regexPatternEdit)
        self.testListWrapper.setRowOnClickEvent(self.listWidgetClickedEvent)

        self.measurements = {}
        self.selectedTest = ''
        self.selectedSite = '0'
        self.selectedPlotType = 'Sequence plot'        
        self.isLogScale = False

        self.processParameterCalculator = ProcessParameterCalculator()
        self.factory = FileProcessorsFactory()
        self.factory.addObserver(self)

        for fileName in DataAnalyzerGUI.FILE_PROCESSORS:
            self.logsTypeComboBox.addItem(fileName)
        
        self.openLogsFolderButton.setEnabled(False)
        self._setStatusOfTestsHandlingWidgets(False)

        self.logsTypeComboBox.currentTextChanged.connect(lambda value: self.selectProcessor(value))
        self.openLogsFolderButton.clicked.connect(self.selectFolder)
        self.changePlotButton.clicked.connect(self.selectPlotType)
        self.selectSiteComboBox.activated.connect(lambda value: self.selectSiteComboBoxClickedEvent(value))
        self.changeYScaleButton.clicked.connect(self.changeYScale)

        self.canvas = MplCanvas(self.plotFrame)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        self.plotLayout = QtWidgets.QVBoxLayout(self.plotFrame)
        self.plotLayout.addWidget(self.toolbar)
        self.plotLayout.addWidget(self.canvas)

        self.sequencePlotGenerator = SequencePlotGenerator(self.canvas)
        self.capabilityPlotGenerator = CapabilityPlotGenerator(self.canvas)
    
    def setMeasurements(self, measurementsDict:dict):
        self.measurements = measurementsDict
    
    def selectProcessor(self, value:str):
        if value != DataAnalyzerGUI.FILE_PROCESSORS[0]:
            self.factory.setProcessorType(value)
            self.openLogsFolderButton.setEnabled(True)
        else:
            self.openLogsFolderButton.setEnabled(False)
    
    def selectPlotType(self):
        plotTypeMap = {'Sequence plot':'Capability plot', 'Capability plot':'Sequence plot'}
        self.selectedPlotType = plotTypeMap[self.selectedPlotType]
        self.generatePlot()

    def selectFolder(self):
        folderPath = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Directory'))
        if folderPath:
            self.processLogsInFolder(folderPath)
    
    def changeYScale(self):
        self.isLogScale = not self.isLogScale
        self.generatePlot()
    
    def processLogsInFolder(self, folderPath:str):
        self.resetSelectSitesComboBox()
        try:
            self.factory.processAllLogsInFolder(folderPath)
        except Exception:            
            self.showErrorMessage('Error', 'Error during processing files. Check if folder with logs is correct')
            return

        measurements = self.factory.getAllMeasurements()
        self.setMeasurements(measurements)

        try:            
            testsList = self._getMeasurementsList()
            self.testListWrapper.setTestNames(testsList)
            self.testListWrapper.generateMeasurementsList()
            self.updateNumOfSites()

        except IndexError:
            self.showErrorMessage('Error', 'Error after processing files. Check if correct log type is selected')
            return

        self._setStatusOfTestsHandlingWidgets(True)
    
    def listWidgetClickedEvent(self, item):#
        try:
            self.selectedTest = item.text()
            self.generatePlot()            
            self.updateProcessParameters()
        except AttributeError:
            pass
    
    def selectSiteComboBoxClickedEvent(self, value:str|int):
        self.selectedSite = str(value)
        self.generatePlot()
        self.updateProcessParameters()

    def generatePlot(self):
        generatePlot = {'Sequence plot':self.sequencePlotGenerator.generatePlot, 
                        'Capability plot': self.capabilityPlotGenerator.generatePlot}
        
        testName = self.selectedTest        
        plotType = self.selectedPlotType
        
        data, dataList = self._getSelectedMeasurementData()
        limits = data.getLimits()
        generatePlot[plotType](dataList, testName, limits, self.isLogScale)
    
    def updateProcessParameters(self):
        data, dataList = self._getSelectedMeasurementData()
        lowerLimit, upperLimit = data.getLimits()
        mean, sigma, pp, ppk, cp, cpk = self.processParameterCalculator.calculate(dataList, lowerLimit, upperLimit)
        self._updateStatisticalEdits(numOfSamples=len(dataList), lowerLimit=lowerLimit, upperLimit=upperLimit, mean=mean, 
                                     sigma=sigma, pp=pp, ppk=ppk, cp=cp, cpk=cpk)

    def _getSelectedMeasurementData(self) -> tuple[DataContainer, list[float]]:
        testName = self.selectedTest     
        data = self.measurements[testName]

        site = self.selectedSite
        if site == '0':
            dataList = data.getDataFromAllSites()
        else:
            dataList = data.getDataFromSite(site)
        return data, dataList        
    
    def _updateStatisticalEdits(self, numOfSamples:int, lowerLimit:float, upperLimit:float, mean:float, sigma:float, pp:float, ppk:float, cp:float, cpk:float):
        self.samplesEdit.setText(str(numOfSamples))
        self.lowerLimitEdit.setText(str(lowerLimit))
        self.upperLimitEdit.setText(str(upperLimit))
        self.averageEdit.setText(str(mean))
        self.sigmaEdit.setText(str(sigma))
        self.ppEdit.setText(str(pp))
        self.ppkEdit.setText(str(ppk))
        self.cpEdit.setText(str(cp))
        self.cpkEdit.setText(str(cpk))
    
    def updateProgressBar(self, progressPercent:int):
        self.progressBar.setProperty("value", progressPercent)
    
    def updateNumOfSites(self):
        testNames = self._getMeasurementsList()
        firstDataContainer = self.measurements[testNames[0]]
        numOfTests = firstDataContainer.getNumOfSites()

        if numOfTests > 1:           
            for i in range(numOfTests):
                self.selectSiteComboBox.addItem(f'{i + 1}')
    
    def resetSelectSitesComboBox(self):
        self.selectSiteComboBox.clear()
        self.selectSiteComboBox.addItem('All sites')
    
    def showErrorMessage(self, title:str, text:str):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Critical)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.exec_()

    def _setStatusOfTestsHandlingWidgets(self, status:bool):
        self.selectSiteComboBox.setEnabled(status)
        self.changeYScaleButton.setEnabled(status)
        self.changePlotButton.setEnabled(status)
        self.filterTestsButton.setEnabled(status)
        self.resetFilterButton.setEnabled(status)
        self.generateReportButton.setEnabled(status)
    
    def _getMeasurementsList(self) -> list[str]:
        return list(self.measurements.keys())

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = DataAnalyzerGUI()
    window.show()
    sys.exit(app.exec_())