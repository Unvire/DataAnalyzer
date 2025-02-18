from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QFrame, QComboBox, QPushButton

from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backend_bases import PickEvent

from mplCanvas import MplCanvas
from plotGenerator import SequencePlotGenerator, CapabilityPlotGenerator
from dataContainer import DataContainer
import listParser


class PlotWrapper:
    def __init__(self, plotFrame:QFrame, selectSiteComboBox:QComboBox, plotOrderByComboBox:QComboBox, _changeYScaleButton:QPushButton, 
                 changePlotButton:QPushButton):
        
        self.plotFrame = plotFrame
        self.selectSiteComboBox = selectSiteComboBox
        self.plotOrderByComboBox = plotOrderByComboBox
        self.changeYScaleButton = _changeYScaleButton
        self.changePlotButton = changePlotButton
       
        self.plotName = ''
        self.limits = []
        self.siteNames = []

        self.selectedSite = 'All sites'
        self.selectedPlotType = 'Sequence plot'
        self.plotOrderBy = 'Date'        
        self.dataList = []
        self.isLogScale = False        
        self.isPickedPoint = False        

        self.errorMessageHandle = lambda: None
        self.updateProcessParameters = lambda: None

        self._initCanvas()
        self._bindEvents()
        self.sequencePlotGenerator = SequencePlotGenerator(self.canvas)
        self.capabilityPlotGenerator = CapabilityPlotGenerator(self.canvas)

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
    
    def setPlotName(self, plotName:str):
        self.plotName = plotName
    
    def setLimits(self, limits:list[float, float]):
        self.limits = limits

    def setSiteNames(self, siteNames:list[str]):
        self.siteNames = siteNames
    
    def setDataList(self, dataList:list[tuple[float, str]]):
        self.dataList = dataList
    
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

    def _getDateFromDataList(self, seriesIndex:int, pointIndex:int) -> str:
        _, date = self.dataList[seriesIndex][pointIndex]
        return date  
    
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
            self.updateProcessParameters()
        except Exception:
            message = 'Error with selected measurement'
            self.errorMessageHandle('Error', message)

    def _plotOrderByComboBoxClickedEvent(self, value:str):
        self.plotOrderBy = self.plotOrderByComboBox.currentText()        
        self.generatePlot()

    def generatePlot(self):
        generatePlot = {'Sequence plot':self.sequencePlotGenerator.generatePlot, 
                        'Capability plot': self.capabilityPlotGenerator.generatePlot}
        
        plotType = self.selectedPlotType             
        isMergeDataList = self.plotOrderBy == 'Date'
        siteNames = self.siteNames if self.selectedSite == 'All sites' else [self.selectedSite]
        
        dataList = listParser.valueDateSeriesToValueSeries(self.dataList)
        generatePlot[plotType](dataList, self.plotName, self.limits, self.isLogScale, siteNames, isMergeDataList)
    
    def setStatusPlotHandlingWidgets(self, status:bool):        
        self.selectSiteComboBox.setEnabled(status)
        self.plotOrderByComboBox.setEnabled(status)
        self.changeYScaleButton.setEnabled(status)
        self.changePlotButton.setEnabled(status)
    
    def updateNumOfSites(self):
        numOfTests = len(self.siteNames)

        if numOfTests > 1: 
            for siteName in self.siteNames:
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
        
        date = self._getDateFromDataList(seriesID, index)
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

    

        