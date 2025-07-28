from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QFrame, QComboBox, QPushButton

from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backend_bases import PickEvent

from mplCanvas import MplCanvas
from plotGenerator import SequencePlotGenerator, CapabilityPlotGenerator, CxCyPlotGenerator
from dataContainer import DataContainer
from dataPoint import DataPoint
import listParser

class PlotWrapper:
    def __init__(self, plotFrame:QFrame, selectSiteComboBox:QComboBox, plotOrderByComboBox:QComboBox, _changeYScaleButton:QPushButton, 
                 changePlotButton:QPushButton, selectLimitsComboBox:QComboBox, valuesInLimitsButton:QPushButton):
        
        self.plotFrame = plotFrame
        self.selectSiteComboBox = selectSiteComboBox
        self.plotOrderByComboBox = plotOrderByComboBox
        self.changeYScaleButton = _changeYScaleButton
        self.changePlotButton = changePlotButton
        self.selectLimitsComboBox = selectLimitsComboBox
        self.valuesInLimitsButton = valuesInLimitsButton
        
        self.dataContainer = None 

        self.selectedSite = 'All sites'
        self.selectedPlotType = 'Sequence plot'
        self.plotOrderBy = 'Date'
        self.selectedLimits = 'All'
        self.isLogScale = False        
        self.isPickedPoint = False
        self.isValuesInLimitsEnabled = False

        self.errorMessageHandle = lambda: None
        self.updateProcessParameters = lambda: None

        self._initCanvas()
        self._bindEvents()
        self.sequencePlotGenerator = SequencePlotGenerator(self.canvas)
        self.capabilityPlotGenerator = CapabilityPlotGenerator(self.canvas)
        self.cxCyPlotGenerator = CxCyPlotGenerator(self.canvas)

    def _initCanvas(self):
        self.canvas = MplCanvas(self.plotFrame)
        self.toolbar = NavigationToolbar(self.canvas)        
        self.annotation = None

        self.plotLayout = QtWidgets.QVBoxLayout(self.plotFrame)
        self.plotLayout.addWidget(self.toolbar)
        self.plotLayout.addWidget(self.canvas)
    
    def _bindEvents(self):
        self.canvas.mpl_connect('pick_event', self._canvasOnPick)
        self.canvas.mpl_connect('button_press_event', self._canvasOnClick)
        self.selectSiteComboBox.activated.connect(lambda value: self._selectSiteComboBoxClickedEvent(value))        
        self.plotOrderByComboBox.activated.connect(self._plotOrderByComboBoxClickedEvent)        
        self.changeYScaleButton.clicked.connect(self._changeYScale)        
        self.changePlotButton.clicked.connect(self._changePlotType)
        self.selectLimitsComboBox.activated.connect(lambda value: self._selectLimitsComboBoxClickedEvent(value))
        self.valuesInLimitsButton.clicked.connect(self._valuesInLimitsButtonClicked)
    
    def setDataContainer(self, dataContainer:DataContainer):
        self.dataContainer = dataContainer
    
    def setErrorMessegeHandle(self, functionHandle):
        self.errorMessageHandle = functionHandle
    
    def setUpdateProcessParametersHandle(self, functionHandle):
        self.updateProcessParameters = functionHandle

    def getSelectedSite(self) -> str:
        return self.selectedSite
    
    def getPlotOrderBy(self) -> str:
        return self.plotOrderBy
    
    def clear(self):
        self.canvas.clear()

    def _getClickedPointData(self, seriesIndex:int, pointIndex:int) -> tuple[str, str, str]:
        dataPointsList, _ = self._getDataPointsList(self.selectedSite)
        value = DataContainer.getValuesFromDataPointsList(dataPointsList)[seriesIndex][pointIndex]
        date = DataContainer.getDateStringsFromDataPointsList(dataPointsList)[seriesIndex][pointIndex]
        serialNumber = DataContainer.getSerialNumbersFromDataPointsList(dataPointsList)[seriesIndex][pointIndex]
        if self.dataContainer.isCxCyMeasurement():
            cx, cy = value
            cx = format(cx, '.3E')
            cy = format(cy, '.3E')
            formattedValue = f'({cx}, {cy})'
        else:
            formattedValue = format(value, '.3E')
        return formattedValue, date, serialNumber
    
    def _changePlotType(self):
        plotTypeInverterMap = {'Sequence plot':'Capability plot', 'Capability plot':'Sequence plot'}
        self.selectedPlotType = plotTypeInverterMap[self.selectedPlotType]
        self._updateSelectLimitsComboBox(self.selectedPlotType)
        self.generatePlot()
    
    def _updateSelectLimitsComboBox(self, selectedPlotType:str):
        isCapabilityPlot = selectedPlotType == 'Capability plot'
        limitsOptions = ['All'] * int(not isCapabilityPlot) + ['Oldest', 'Newest']
        
        self.selectLimitsComboBox.clear()
        for option in limitsOptions:
            self.selectLimitsComboBox.addItem(option)
        
        if isCapabilityPlot and self.selectedLimits == 'All':
            self.selectedLimits = 'Oldest'
        elif not isCapabilityPlot:
            self.selectedLimits = 'All'

    def _changeYScale(self):        
        self.isLogScale = not self.isLogScale
        self.generatePlot()
    
    def _selectLimitsComboBoxClickedEvent(self, value:str|int):
        self.selectedLimits = self.selectLimitsComboBox.itemText(value)
        self.generatePlot()
    
    def _valuesInLimitsButtonClicked(self):
        self.isValuesInLimitsEnabled = not self.isValuesInLimitsEnabled
        self.generatePlot()
    
    def _selectSiteComboBoxClickedEvent(self, value:str|int):
        self.selectedSite = self.selectSiteComboBox.itemText(value)
        sortByState = self.selectedSite == 'All sites'
        self.plotOrderByComboBox.setEnabled(sortByState)

        try:
            self.generatePlot()
            if not self.dataContainer.isCxCyMeasurement():
                self.updateProcessParameters()
        except Exception:
            message = 'Error with selected measurement'
            self.errorMessageHandle('Error', message)

    def _plotOrderByComboBoxClickedEvent(self, value:str):
        self.plotOrderBy = self.plotOrderByComboBox.currentText()        
        self.generatePlot()

    def generatePlot(self):        
        if self.dataContainer.isCxCyMeasurement():
            self._generateCXCYPlot()                        
            self.setStatusPlotHandlingWidgets(False)
            self.selectSiteComboBox.setEnabled(True)
            self.selectLimitsComboBox.setEnabled(True)
        else:
            self._generateCapabilityOrSequencePlot()            
            self.setStatusPlotHandlingWidgets(True)       
    
    def _generateCapabilityOrSequencePlot(self):
        generatePlot = {'Sequence plot':self.sequencePlotGenerator.generatePlot, 
                        'Capability plot': self.capabilityPlotGenerator.generatePlot}
        
        plotName, siteNames, valuesList, limitsList = self._commonPlotData()
            
        isMergeDataList = self.plotOrderBy == 'Date'
        generatePlot[self.selectedPlotType ](valuesList, plotName, limitsList, self.isLogScale, siteNames, isMergeDataList, self.isValuesInLimitsEnabled)
    
    def _generateCXCYPlot(self):
        plotName, siteNames, valuesList, siteBoundariesList = self._commonPlotData()        
        siteBoundaries = listParser.uniqueBoundaryStrings(siteBoundariesList)
        boundaryXYs = listParser.processBoundaryStrings(siteBoundaries)
        self.cxCyPlotGenerator.generatePlot(valuesList, plotName, boundaryXYs, siteNames)

    def _commonPlotData(self) -> tuple[str, list[str], list[list[float | tuple[float, float]]], list[list[str | tuple[float, float]]]] | list[float|str]:
        plotName = self.dataContainer.name
        dataPointsList, siteNames = self._getDataPointsList(self.selectedSite)        
        valuesList = DataContainer.getValuesFromDataPointsList(dataPointsList)
        limitsList = DataContainer.getLimitsFromDataPointsList(dataPointsList, self.selectedLimits)   
        return plotName, siteNames, valuesList, limitsList

    def _getDataPointsList(self, selectedSite:str) -> tuple[list[list[DataPoint]], list[str]]:
        dataPointsList = self.dataContainer.getData(selectedSite)
        siteNames = self.dataContainer.getSiteNames() if selectedSite == 'All sites' else [selectedSite]
        return dataPointsList, siteNames

    def setStatusPlotHandlingWidgets(self, status:bool):        
        self.selectSiteComboBox.setEnabled(status)
        self.plotOrderByComboBox.setEnabled(status)
        self.changeYScaleButton.setEnabled(status)
        self.changePlotButton.setEnabled(status)
        self.valuesInLimitsButton.setEnabled(status)
    
    def updateNumOfSites(self):
        if self.dataContainer.getNumOfSites() > 1: 
            for siteName in self.dataContainer.getSiteNames():
                self.selectSiteComboBox.addItem(siteName)
    
    def resetSelectSitesComboBox(self):
        self.selectSiteComboBox.clear()
        self.selectSiteComboBox.addItem('All sites')
    
    def _canvasOnClick(self, event):
        if event.inaxes is None:
            return

        if self.isPickedPoint:
            self.isPickedPoint = False
            return
        
        self._removeAnnotation()        
        self.canvas.draw_idle()

    def _canvasOnPick(self, event: PickEvent):
        def getSeriesID(artist):
            for i, line in enumerate(self.canvas.ax.lines):
                if line == artist:
                    return i
        
        self._removeAnnotation()        
        self.canvas.draw_idle()
        
        self.isPickedPoint = True

        seriesID = getSeriesID(event.artist)
        index = event.ind[0]
        x = event.artist.get_xdata()[index]
        y = event.artist.get_ydata()[index]        
        
        try:
            formattedValue, date, serialNumber = self._getClickedPointData(seriesID, index)
            self.annotation = self.canvas.ax.annotate(
                f'{formattedValue}\n{date}\n{serialNumber}',
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
            
        except IndexError:
            pass

        self.canvas.draw_idle()
    
    def _removeAnnotation(self):
        if self.annotation:
            self.annotation.remove()
            self.annotation = None

    

        