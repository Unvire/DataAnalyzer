import sys, os
import threading

from PyQt5 import QtWidgets, uic
from PyQt5 import QtCore
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backend_bases import PickEvent

from generateReportDialog import GenerateReportDialog

from mplCanvas import MplCanvas
from testListWrapper import TestListWrapper
from fileProcessorFactory import FileProcessorsFactory
from processCalculator import ProcessParameterCalculator
from plotGenerator import SequencePlotGenerator, CapabilityPlotGenerator
from htmlReportGenerator import HtmlReportGenerator
from dataContainer import DataContainer

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
        self.logsProcessingSuccess = True
        self.isPickedPoint = False
        self.dataList = []
        self.plotOrderBy = 'Date'

        self.threadTimer = QtCore.QTimer()
        self.threadFinished = False

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
        self.plotOrderByComboBox.activated.connect(self.plotOrderByComboBoxClickedEvent)
        self.changeYScaleButton.clicked.connect(self.changeYScale)
        self.generateReportButton.clicked.connect(self.openGenerateReportDialogWindow)

        self.canvas = MplCanvas(self.plotFrame)
        self.toolbar = NavigationToolbar(self.canvas, self)        
        self.annotation = None
        self.canvas.mpl_connect('pick_event', self.canvasOnPick)
        self.canvas.mpl_connect('button_press_event', self.canvasOnClick)
        
        self.plotLayout = QtWidgets.QVBoxLayout(self.plotFrame)
        self.plotLayout.addWidget(self.toolbar)
        self.plotLayout.addWidget(self.canvas)

        self.sequencePlotGenerator = SequencePlotGenerator(self.canvas)
        self.capabilityPlotGenerator = CapabilityPlotGenerator(self.canvas)

    
    def setMeasurements(self, measurementsDict:dict):
        self.measurements = measurementsDict
    
    def setPlottedDataList(self, dataList:list[tuple[float, str]]):
        self.dataList = dataList
    
    def getValuesFromDataList(self) -> list[float]:
        return [value for value, _ in self.dataList]

    def getDateFromDataList(self, index:str) -> str:
        _, date = self.dataList[index]
        return date
    
    def selectProcessor(self, value:str):
        if value != DataAnalyzerGUI.FILE_PROCESSORS[0]:
            self.factory.setProcessorType(value)
            self.openLogsFolderButton.setEnabled(True)
        else:
            self.openLogsFolderButton.setEnabled(False)
    
    def selectPlotType(self):
        if not self.selectedTest:
            return
        
        plotTypeMap = {'Sequence plot':'Capability plot', 'Capability plot':'Sequence plot'}
        self.selectedPlotType = plotTypeMap[self.selectedPlotType]
        self.generatePlot()

    def selectFolder(self):
        folderPath = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Directory'))
        if folderPath:
            self.processLogsInFolder(folderPath)
    
    def changeYScale(self):        
        if not self.selectedTest:
            return
        
        self.isLogScale = not self.isLogScale
        self.generatePlot()
    
    def openGenerateReportDialogWindow(self):    
        def runReportGeneration():
            nonlocal htmlCode
            htmlCode = self.htmlReportGenerator.generateHtmlReport(testsForReport, selectedSite)
            self.threadFinished = True
            
        testNames = self._getMeasurementsList()
        dialogWindow = GenerateReportDialog(testNames, self.selectSiteComboBox.count() - 1)
        if dialogWindow.exec_() == QtWidgets.QDialog.Accepted:
            filePath, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save report', '', 'Hyper Text Markup Language file (*.html)')
            if not filePath.lower().endswith('.html'):
                filePath += '.html'

            selectedTestNames, selectedSite = dialogWindow.getData()
            testsForReport = self.measurements if len(selectedTestNames) == len(testNames) else {testName:self.measurements[testName] for testName in selectedTestNames}

            self.htmlReportGenerator = HtmlReportGenerator()
            self.htmlReportGenerator.addObserver(self)

            htmlCode= ''            
            self._setStatusOfThreadsCallingWidgets(False)
            reportThread = threading.Thread(target=runReportGeneration, daemon=True)
            reportThread.start()

            self.threadFinished = False
            self.threadTimer = QtCore.QTimer()
            self.threadTimer.timeout.connect(lambda: self._reportThreadStatus(filePath, htmlCode))
            self.threadTimer.start(100)
    
    def _reportThreadStatus(self, filePath:str, htmlCode:str):
        if self.threadFinished:
            self.threadTimer.stop()
            self._saveReport(filePath, htmlCode)
            self._setStatusOfThreadsCallingWidgets(True)
    
    def _saveReport(self, filePath:str, htmlCode:str):
        with open(filePath, 'w', encoding='utf-8') as file:
            file.writelines(htmlCode)
            
        self.updateProgressBar(100)
        
        message1 = f'Report was saved: {filePath}.\n\n To save it to PDF file open the report in browser.\n'
        message2 = 'Press ctrl+P to open print menu. Set in advanced mode:\n'
        message3 = '  -margins: none,\n  -scale: 40% (or different scale so the images will fit in tables),\n'
        message4 = 'Save it as PDF file.'
        message = message1 + message2 + message3 + message4        
        QtWidgets.QMessageBox.information(self,  'Info',  message, QtWidgets.QMessageBox.Ok)
    
    def processLogsInFolder(self, folderPath:str):
        def runProcessLogs():
            try:
                self.factory.processAllLogsInFolder(folderPath)
            except Exception:            
                self.showErrorMessage('Error', 'Error during processing files. Check if folder with logs is correct')
                self.logsProcessingSuccess = False
            self.threadFinished = True            
        
        self.resetSelectSitesComboBox()
        self._setStatusOfThreadsCallingWidgets(False)
        self.logsProcessingSuccess = True
        reportThread = threading.Thread(target=runProcessLogs, daemon=True)
        reportThread.start()

        self.threadFinished = False
        self.threadTimer = QtCore.QTimer()
        self.threadTimer.timeout.connect(self._processLogsThreadStatus)
        self.threadTimer.start(100)
    
    def _processLogsThreadStatus(self):
        if not self.threadFinished:
            return
        
        self.threadTimer.stop()
        if self.logsProcessingSuccess:
            self._finishProcessingLogs()
    
    def _finishProcessingLogs(self):
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
        
        self._setStatusOfThreadsCallingWidgets(True)
        self._setStatusOfTestsHandlingWidgets(True)
    
    def listWidgetClickedEvent(self, item):
        try:
            self.selectedTest = item.text()
            self.generatePlot()            
            self.updateProcessParameters()
        except AttributeError:
            pass
    
    def selectSiteComboBoxClickedEvent(self, value:str|int):
        if not self.selectedTest:
            return

        self.selectedSite = str(value)

        sortByState = self.selectedSite == '0'
        self.plotOrderByComboBox.setEnabled(sortByState)

        self.generatePlot()
        self.updateProcessParameters()
    
    def plotOrderByComboBoxClickedEvent(self, value:str):
        if not self.selectedTest:
            return
        
        self.plotOrderBy = self.plotOrderByComboBox.currentText()        
        self.generatePlot()

    def generatePlot(self):
        generatePlot = {'Sequence plot':self.sequencePlotGenerator.generatePlot, 
                        'Capability plot': self.capabilityPlotGenerator.generatePlot}
        
        testName = self.selectedTest        
        plotType = self.selectedPlotType
        
        data = self._getSelectedMeasurementDataContainer()
        limits = data.getLimits()

        dataListValues = self.getValuesFromDataList()
        generatePlot[plotType](dataListValues, testName, limits, self.isLogScale)
    
    def updateProcessParameters(self):
        data = self._getSelectedMeasurementDataContainer()
        lowerLimit, upperLimit = data.getLimits()
        dataListValues = self.getValuesFromDataList()

        mean, sigma, pp, ppk, cp, cpk = self.processParameterCalculator.calculate(dataListValues, lowerLimit, upperLimit)
        self._updateStatisticalEdits(numOfSamples=len(dataListValues), lowerLimit=lowerLimit, upperLimit=upperLimit, mean=mean, 
                                     sigma=sigma, pp=pp, ppk=ppk, cp=cp, cpk=cpk)

    def _getSelectedMeasurementDataContainer(self) -> DataContainer:
        testName = self.selectedTest     
        data = self.measurements[testName]

        site = self.selectedSite
        dataList = data.getDataFromAllSites(self.plotOrderBy) if site == '0' else data.getDataFromSite(site)
        self.setPlottedDataList(dataList)
        return data  
    
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
    
    @QtCore.pyqtSlot(int)
    def updateProgressBar(self, progressPercent:int):
        self.progressBar.setProperty('value', progressPercent)
    
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
        self.plotOrderByComboBox.setEnabled(status)
        self.changeYScaleButton.setEnabled(status)
        self.changePlotButton.setEnabled(status)
        self.filterTestsButton.setEnabled(status)
        self.resetFilterButton.setEnabled(status)
        self.generateReportButton.setEnabled(status)
    
    def _setStatusOfThreadsCallingWidgets(self, status:bool):
        self.openLogsFolderButton.setEnabled(status)
        self.generateReportButton.setEnabled(status)        
    
    def _getMeasurementsList(self) -> list[str]:
        return list(self.measurements.keys())
    
    def canvasOnClick(self, event):
        if event.inaxes is None:
            return

        if self.isPickedPoint:
            self.isPickedPoint = False
            return
        
        if self.annotation:
            self.annotation.remove()
            self.annotation = None
            self.canvas.draw_idle() 

    def canvasOnPick(self, event: PickEvent):
        if self.annotation:
            self.annotation.remove()
        
        self.isPickedPoint = True

        index = event.ind[0]
        x = event.artist.get_xdata()[index]
        y = event.artist.get_ydata()[index]        
        date = self.getDateFromDataList(index)
        formattedValue = format(y, '.3E')
        self.annotation = self.canvas.ax.annotate(
            f'{formattedValue}\n{date}',
            (x, y),
            xytext=(0, 10),
            textcoords='offset points',
            ha='center',
            bbox=dict(
                boxstyle='round,pad=0.5',
                fc='lightblue',
                ec='black',
                lw=1
            ),
            arrowprops=dict(arrowstyle='->')
        )
        self.canvas.draw_idle()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = DataAnalyzerGUI()
    window.show()
    sys.exit(app.exec_())