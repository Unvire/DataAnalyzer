import sys, os
import threading

from PyQt5 import QtWidgets, uic
from PyQt5 import QtCore
from PyQt5.QtWidgets import QMessageBox

from dialogGenerateReport import GenerateReportDialog
from dialogPlot import PlotDialog

from wrapperTestList import TestListWrapper
from wrapperDisplayPlot import PlotWrapper
from fileProcessorFactory import FileProcessorsFactory
from processCalculator import ProcessParameterCalculator
from htmlReportGenerator import HtmlReportGenerator
from dataContainer import DataContainer
import listParser

class DataAnalyzerGUI(QtWidgets.QMainWindow):
    FILE_PROCESSORS = ['Select file type', 'SPEA', 'FWK / Ipses', 'TestStand Grugliasco', 'Column file']

    def __init__(self):
        super().__init__()
        uiFilePath = os.path.join(os.getcwd(), 'ui', 'main.ui')
        uic.loadUi(uiFilePath, self)

        self.testListWrapper = TestListWrapper(self.listWidget, self.filterTestsButton, self.resetFilterButton, self.regexPatternEdit)
        self.testListWrapper.setRowOnClickEvent(self.listWidgetClickedEvent)

        self.measurements = {}
        self.selectedTest = ''
        self.logsProcessingSuccess = True
        self.currentFileType = ''
        self.plotWindowsDict = {}

        self.threadTimer = QtCore.QTimer()
        self.threadFinished = False

        self.processParameterCalculator = ProcessParameterCalculator()
        self.factory = FileProcessorsFactory()
        self.factory.addObserver(self)

        for fileName in DataAnalyzerGUI.FILE_PROCESSORS:
            self.logsTypeComboBox.addItem(fileName)
        
        self.plotWidget = PlotWrapper(self.plotFrame, self.selectSiteComboBox, self.plotOrderByComboBox, self.changeYScaleButton,
                                      self.changePlotButton, self.selectLimitsComboBox)
        self.plotWidget.setErrorMessegeHandle(self.showErrorMessage)
        self.plotWidget.setUpdateProcessParametersHandle(self.updateProcessParameters)
        
        self.openLogsFolderButton.setEnabled(False)  
        self.plotWidget.setStatusPlotHandlingWidgets(False)
        self._setStatusOfTestsHandlingWidgets(False)  

        self.logsTypeComboBox.currentTextChanged.connect(lambda value: self.selectProcessor(value))
        self.openLogsFolderButton.clicked.connect(self.selectFolder)
        self.clearButton.clicked.connect(self.clear)
        self.generateReportButton.clicked.connect(self.openGenerateReportDialogWindow)
        self.plotNewWindowButton.clicked.connect(self.plotInNewWindow)

    def setMeasurements(self, measurementsDict:dict):
        self.measurements = measurementsDict
    
    def selectProcessor(self, value:str):
        if value == DataAnalyzerGUI.FILE_PROCESSORS[0]:
            self.openLogsFolderButton.setEnabled(False)
            return
        
        isFileTypeChanged = self.currentFileType != value
        self._updateOpenLogsFolderButtonText(isFileTypeChanged)

        self.factory.setProcessorType(value)
        self.openLogsFolderButton.setEnabled(True)  

    def selectFolder(self):
        dialog = QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, False)
        dialog.setOption(QtWidgets.QFileDialog.ReadOnly, False)
        dialog.setWindowTitle('Select Directory or paste path in the "Directory" field')

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            folderPath = dialog.selectedFiles()[0]

            isAppendTests = self.currentFileType == self.logsTypeComboBox.currentText()
            self.processLogsInFolder(folderPath, isAppendTests)
            self.currentFileType = self.logsTypeComboBox.currentText()            
            self._updateOpenLogsFolderButtonText(False)
    
    def clear(self):
        userResponse = QMessageBox.question(self, 'Warning', 'Do you want to clear loaded data?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if userResponse == QMessageBox.No:
            return
        
        self.testListWrapper.clear()
        self.plotWidget.clear()
        self._updateStatisticalEdits()

        self.currentFileType = ''            
        self.logsTypeComboBox.setCurrentIndex(0)
        self.updateProgressBar(0)
        self._updateOpenLogsFolderButtonText(True)
        
        self._setStatusOfTestsHandlingWidgets(False)
        self.plotWidget.setStatusPlotHandlingWidgets(False)   
        self._setStatusOfThreadsCallingWidgets(False)        
    
    def _updateOpenLogsFolderButtonText(self, isFileTypeChanged:bool):
        if isFileTypeChanged:
            self.openLogsFolderButton.setText('Open logs folder')
        else:
            self.openLogsFolderButton.setText('Append new logs')
    
    def openGenerateReportDialogWindow(self):    
        def runReportGeneration():
            nonlocal htmlCode
            htmlCode = self.htmlReportGenerator.generateHtmlReport(testsForReport, selectedSite, orderBy, selectedLimits)
            self.threadFinished = True
            
        testNames = self._getMeasurementsList()
        data = self._getSelectedMeasurementDataContainer()

        if len(data.getSiteNames()) == 1:
            siteNames = ['All sites']
        else:
            siteNames = ['All sites'] + data.getSiteNames()

        dialogWindow = GenerateReportDialog(testNames, siteNames)
        if dialogWindow.exec_() == QtWidgets.QDialog.Accepted:
            filePath, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save report', '', 'Hyper Text Markup Language file (*.html)')
            if not filePath.lower().endswith('.html'):
                filePath += '.html'

            selectedTestNames, selectedSite, orderBy, selectedLimits = dialogWindow.getData()
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
    
    def plotInNewWindow(self):
        if self.selectedTest in self.plotWindowsDict:
            return
        
        dataContainer = self._getSelectedMeasurementDataContainer()
        dialogWindow = PlotDialog(dataContainer)
        dialogWindow.setCloseEventHandle(self.closePlotWindow)
        dialogWindow.show()
        self.plotWindowsDict[self.selectedTest] = dialogWindow
    
    def closePlotWindow(self, windowTitle:str):
        self.plotWindowsDict.pop(windowTitle, None) 
    
    def processLogsInFolder(self, folderPath:str, isAppendTests:bool):
        def runProcessLogs():
            try:
                self.factory.processAllLogsInFolder(folderPath, isAppendTests)
            except Exception:         
                self.logsProcessingSuccess = False
            self.threadFinished = True            
        
        self.plotWidget.resetSelectSitesComboBox()
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
        else:
            self.showErrorMessage('Error', 'Error during processing files. Check if folder with logs is correct')            
            self.openLogsFolderButton.setEnabled(True)
    
    def _finishProcessingLogs(self):
        measurements = self.factory.getAllMeasurements()
        self.setMeasurements(measurements)            

        try:       
            testsList = self._getMeasurementsList()
            self.testListWrapper.setTestNames(testsList)
            self.testListWrapper.generateMeasurementsList()

            firstMeasurement = self.measurements[testsList[0]]
            self.plotWidget.setDataContainer(firstMeasurement)
            self.plotWidget.updateNumOfSites()
            self.plotWidget.generatePlot()
            self.selectedTest = firstMeasurement.name

        except IndexError:
            self.showErrorMessage('Error', 'Error after processing files. Check if correct log type is selected')
            self.openLogsFolderButton.setEnabled(True)
            return
        
        self._setStatusOfThreadsCallingWidgets(True) 
        self._setStatusOfTestsHandlingWidgets(True)
    
    def listWidgetClickedEvent(self, item):
        try:
            self.selectedTest = item.text()
            dataContainer = self._getSelectedMeasurementDataContainer()
            self.plotWidget.setDataContainer(dataContainer)
            self.plotWidget.generatePlot()
            if not dataContainer.isCxCyMeasurement():
                self.updateProcessParameters()
        except AttributeError:
            pass
        except Exception:
            message = 'Error with selected measurement'
            self.showErrorMessage('Error', message)
    
    def updateProcessParameters(self):
        dataContainer = self._getSelectedMeasurementDataContainer()
        site = self.plotWidget.getSelectedSite()

        dataPointsList = dataContainer.getData(site)
        nestedValuesList = DataContainer.getValuesFromDataPointsList(dataPointsList)        
        valuesList = listParser.nestedValuesListToFlatValueList(nestedValuesList)

        lowerLimit, upperLimit = DataContainer.getLimitsFromDataPointsList(dataPointsList, 'Newest')

        mean, sigma, pp, ppk, cp, cpk, stability = self.processParameterCalculator.calculate(valuesList, lowerLimit, upperLimit)
        self._updateStatisticalEdits(numOfSamples=len(valuesList), lowerLimit=lowerLimit, upperLimit=upperLimit, mean=mean, 
                                     sigma=sigma, pp=pp, ppk=ppk, cp=cp, cpk=cpk, stability=stability)

    def _getSelectedMeasurementDataContainer(self) -> DataContainer:
        testName = self.selectedTest     
        return self.measurements[testName]
    
    def _updateStatisticalEdits(self, numOfSamples:int|str='', lowerLimit:float|str='', upperLimit:float|str='', mean:float|str='', 
                                sigma:float|str='', pp:float|str='', ppk:float|str='', cp:float|str='', cpk:float|str='', stability:float|str=''):
        self.samplesEdit.setText(str(numOfSamples))
        self.lowerLimitEdit.setText(str(lowerLimit))
        self.upperLimitEdit.setText(str(upperLimit))
        self.averageEdit.setText(str(mean))
        self.sigmaEdit.setText(str(sigma))
        self.ppEdit.setText(str(pp))
        self.ppkEdit.setText(str(ppk))
        self.cpEdit.setText(str(cp))
        self.cpkEdit.setText(str(cpk))
        self.stabilityEdit.setText(f'{stability * 100}%')
    
    @QtCore.pyqtSlot(int)
    def updateProgressBar(self, progressPercent:int):
        self.progressBar.setProperty('value', progressPercent)
    
    def showErrorMessage(self, title:str, text:str):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Critical)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.exec_()

    def _setStatusOfTestsHandlingWidgets(self, status:bool):
        self.clearButton.setEnabled(status)
        self.filterTestsButton.setEnabled(status)
        self.resetFilterButton.setEnabled(status)
        self.generateReportButton.setEnabled(status)        
        self.plotNewWindowButton.setEnabled(status)
    
    def _setStatusOfThreadsCallingWidgets(self, status:bool):
        self.openLogsFolderButton.setEnabled(status)
        self.generateReportButton.setEnabled(status)        
    
    def _getMeasurementsList(self) -> list[str]:
        return list(self.measurements.keys())

    def closeEvent(self, event):
        for _, subWindowHandle in self.plotWindowsDict.items():
            subWindowHandle.close()
        super().close()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = DataAnalyzerGUI()
    window.show()
    sys.exit(app.exec_())