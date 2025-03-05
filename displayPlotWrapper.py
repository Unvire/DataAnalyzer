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
                 changePlotButton:QPushButton):
        
        self.plotFrame = plotFrame
        self.selectSiteComboBox = selectSiteComboBox
        self.plotOrderByComboBox = plotOrderByComboBox
        self.changeYScaleButton = _changeYScaleButton
        self.changePlotButton = changePlotButton
        
        self.dataContainer = None 

        self.selectedSite = 'All sites'
        self.selectedPlotType = 'Sequence plot'
        self.plotOrderBy = 'Date'
        self.isLogScale = False        
        self.isPickedPoint = False 

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

    def _getClickedPointData(self, seriesIndex:int, pointIndex:int) -> tuple[str, str]:
        dataList = DataContainer.generateDataList(self.dataContainer, 'Date', 'All sites')
        value, date = dataList[seriesIndex][pointIndex]        
        if 1==0:#isinstance(self.dataContainer, CxCyDataContainer):
            cx, cy = value
            cx = format(cx, '.3E')
            cy = format(cy, '.3E')
            formattedValue = f'({cx}, {cy})'
        else:
            formattedValue = format(value, '.3E')
        return formattedValue, date  
    
    def _changePlotType(self):
        plotTypeInverterMap = {'Sequence plot':'Capability plot', 'Capability plot':'Sequence plot'}
        self.selectedPlotType = plotTypeInverterMap[self.selectedPlotType]
        self.generatePlot()
    
    def _changeYScale(self):        
        self.isLogScale = not self.isLogScale
        self.generatePlot()
    
    def _selectSiteComboBoxClickedEvent(self, value:str|int):
        self.selectedSite = self.selectSiteComboBox.itemText(value)
        sortByState = self.selectedSite == 'All sites'
        self.plotOrderByComboBox.setEnabled(sortByState)

        try:
            self.generatePlot()
            if 1==0:#not isinstance(self.dataContainer, CxCyDataContainer):
                self.updateProcessParameters()
        except Exception:
            message = 'Error with selected measurement'
            self.errorMessageHandle('Error', message)

    def _plotOrderByComboBoxClickedEvent(self, value:str):
        self.plotOrderBy = self.plotOrderByComboBox.currentText()        
        self.generatePlot()

    def generatePlot(self):
        siteNames = self.dataContainer.getSiteNames()
        limits = self.dataContainer.getLimits(siteNames[0])
        if isinstance(limits[0], str):
            self._generateCXCYPlot()                        
            self.setStatusPlotHandlingWidgets(False)
            self.selectSiteComboBox.setEnabled(True)
        else:
            self._generateCapabilityOrSequencePlot()            
            self.setStatusPlotHandlingWidgets(True)       
    
    def _generateCapabilityOrSequencePlot(self):
        generatePlot = {'Sequence plot':self.sequencePlotGenerator.generatePlot, 
                        'Capability plot': self.capabilityPlotGenerator.generatePlot}
        
        plotName, siteNames, valuesList, limitsList = self._commonPlotData()

        plotType = self.selectedPlotType             
        isMergeDataList = self.plotOrderBy == 'Date'
        generatePlot[plotType](valuesList, plotName, limitsList, self.isLogScale, siteNames, isMergeDataList)
    
    def _generateCXCYPlot(self):
        def uniqueBoundaryStrings(siteBoundariesList:list[list[str]]) -> list[str]:
            uniqueBoundaries = set()
            for siteBoundaries in siteBoundariesList:
                for boundaryString in siteBoundaries:
                    uniqueBoundaries.add(boundaryString)
            return list(uniqueBoundaries)
        
        def processBoundaryStrings(uniqueBoundariesList:list[str]) -> list[list[tuple[float, float]]]:
            result = []
            for boundaryString in uniqueBoundariesList:
                x1, y1, x2, y2, x3, y3, x4, y4 = boundaryString.split('_')
                boundaryXYs = [(float(x1), float(y1)), (float(x2), float(y2)), (float(x3), float(y3)), (float(x4), float(y4)), (float(x1), float(y1))]
                result.append(boundaryXYs) 
            return result

        plotName, siteNames, valuesList, siteBoundariesList = self._commonPlotData()
        siteBoundaries = uniqueBoundaryStrings(siteBoundariesList)
        boundaryXYs = processBoundaryStrings(siteBoundaries)
        self.cxCyPlotGenerator.generatePlot(valuesList, plotName, boundaryXYs, siteNames)

    def _commonPlotData(self) -> tuple[str, list[str], list[list[float | tuple[float, float]]], list[list[str | tuple[float, float]]]]:
        plotName = self.dataContainer.name
        dataPointsList, siteNames = self._getDataPointsList(self.selectedSite)        
        valuesList = DataContainer.getValuesFromDataPointsList(dataPointsList)
        limitsList = DataContainer.getLimitsFromDataPointsList(dataPointsList)
        return plotName, siteNames, valuesList, limitsList

    def _getDataPointsList(self, selectedSite:str) -> tuple[list[list[DataPoint]], list[str]]:
        if selectedSite == 'All sites':
            dataPointsList = self.dataContainer.getDataFromAllSites()
            siteNames = self.dataContainer.getSiteNames()
        else:
            siteNames = [selectedSite]
            dataPointsList = self.dataContainer.getDataFromSite(selectedSite)
        return dataPointsList, siteNames

    def setStatusPlotHandlingWidgets(self, status:bool):        
        self.selectSiteComboBox.setEnabled(status)
        self.plotOrderByComboBox.setEnabled(status)
        self.changeYScaleButton.setEnabled(status)
        self.changePlotButton.setEnabled(status)
    
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
        
        if self.annotation:
            self.annotation.remove()
            self.annotation = None
            self.canvas.draw_idle() 

    def _canvasOnPick(self, event: PickEvent):
        def getSeriesID(artist):
            for i, line in enumerate(self.canvas.ax.lines):
                if line == artist:
                    return i

        if self.annotation:
            self.annotation.remove()
        
        self.isPickedPoint = True

        seriesID = getSeriesID(event.artist)
        index = event.ind[0]
        x = event.artist.get_xdata()[index]
        y = event.artist.get_ydata()[index]        
        
        formattedValue, date = self._getClickedPointData(seriesID, index)
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

    

        