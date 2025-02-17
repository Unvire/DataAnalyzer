from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QFrame, QComboBox, QPushButton

from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backend_bases import PickEvent

from mplCanvas import MplCanvas
from plotGenerator import SequencePlotGenerator, CapabilityPlotGenerator
from dataContainer import DataContainer
import listParser


class PlotWrapper:
    def __init__(self, plotFrame:QFrame, selectSiteComboBox:QComboBox, plotOrderByComboBox:QComboBox, changeYScaleButton:QPushButton, 
                 changePlotButton:QPushButton):
        
        self.plotFrame = plotFrame
        self.selectSiteComboBox = selectSiteComboBox
        self.plotOrderByComboBox = plotOrderByComboBox
        self.changeYScaleButton = changeYScaleButton
        self.changePlotButton = changePlotButton
        
        self.selectedSite = 'All sites'
        self.selectedPlotType = 'Sequence plot'
        self.plotOrderBy = 'Date'        
        self.dataList = []
        self.isLogScale = False        
        self.isPickedPoint = False

        self.sequencePlotGenerator = SequencePlotGenerator(self.canvas)
        self.capabilityPlotGenerator = CapabilityPlotGenerator(self.canvas)

    def _initCanvas(self):
        self.canvas = MplCanvas(self.plotFrame)
        self.toolbar = NavigationToolbar(self.canvas, self)        
        self.annotation = None

        self.plotLayout = QtWidgets.QVBoxLayout(self.plotFrame)
        self.plotLayout.addWidget(self.toolbar)
        self.plotLayout.addWidget(self.canvas)
    
    def _bindEvents(self):
        self.canvas.mpl_connect('pick_event', self.canvasOnPick)
        self.canvas.mpl_connect('button_press_event', self.canvasOnClick)
        self.selectSiteComboBox.activated.connect(lambda value: self.selectSiteComboBoxClickedEvent(value))        
        self.plotOrderByComboBox.activated.connect(self.plotOrderByComboBoxClickedEvent)        
        self.changeYScaleButton.clicked.connect(self.changeYScale)        
        self.changePlotButton.clicked.connect(self.changePlotType)  
    
    def clear(self):
        self.canvas.clear()        
        self.logsTypeComboBox.setCurrentIndex(0)
    
    def setPlottedDataList(self, dataList:list[tuple[float, str]]):
        self.dataList = dataList  

    def getDateFromDataList(self, seriesIndex:int, pointIndex:int) -> str:
        _, date = self.dataList[seriesIndex][pointIndex]
        return date  
    
    def changePlotType(self):
        plotTypeInverterMap = {'Sequence plot':'Capability plot', 'Capability plot':'Sequence plot'}
        self.selectedPlotType = plotTypeInverterMap[self.selectedPlotType]
        self.generatePlot()
    
    def changeYScale(self):        
        self.isLogScale = not self.isLogScale
        self.generatePlot()
    
    def selectSiteComboBoxClickedEvent(self, value:str|int):
        self.selectedSite = self.selectSiteComboBox.itemText(value)
        sortByState = self.selectedSite == 'All sites'
        self.plotOrderByComboBox.setEnabled(sortByState)

        try:
            self.generatePlot()
            self.updateProcessParameters()
        except Exception:
            message = 'Error with selected measurement'
            self.showErrorMessage('Error', message)

    def plotOrderByComboBoxClickedEvent(self, value:str):
        self.plotOrderBy = self.plotOrderByComboBox.currentText()        
        self.generatePlot()

    def generatePlot(self, testData:DataContainer):
        generatePlot = {'Sequence plot':self.sequencePlotGenerator.generatePlot, 
                        'Capability plot': self.capabilityPlotGenerator.generatePlot}
        
        testName = testData.name       
        plotType = self.selectedPlotType
        
        limits = testData.getLimits()        
        isMergeDataList = self.plotOrderBy == 'Date'

        siteNames = testData.getSiteNames() if self.selectedSite == 'All sites' else [self.selectedSite]
        
        dataList = listParser.valueDateSeriesToValueSeries(self.dataList)
        generatePlot[plotType](dataList, testName, limits, self.isLogScale, siteNames, isMergeDataList)
    
    def setStatusPlotHandlingWidgets(self, status:bool):        
        self.selectSiteComboBox.setEnabled(status)
        self.plotOrderByComboBox.setEnabled(status)
        self.changeYScaleButton.setEnabled(status)
        self.changePlotButton.setEnabled(status)
    
    def updateNumOfSites(self):
        testNames = self._getMeasurementsList()
        firstDataContainer = self.measurements[testNames[0]]
        numOfTests = firstDataContainer.getNumOfSites()

        if numOfTests > 1:           
            siteNames = firstDataContainer.getSiteNames()
            for siteName in siteNames:
                self.selectSiteComboBox.addItem(siteName)
    
    def resetSelectSitesComboBox(self):
        self.selectSiteComboBox.clear()
        self.selectSiteComboBox.addItem('All sites')
    
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
        
        date = self.getDateFromDataList(seriesID, index)
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

    

        