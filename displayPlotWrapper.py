from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QFrame, QComboBox, QPushButton

from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backend_bases import PickEvent

from mplCanvas import MplCanvas
from plotGenerator import SequencePlotGenerator, CapabilityPlotGenerator

class PlotWrapper:
    def __init__(self, plotFrame:QFrame, selectSiteComboBox:QComboBox, plotOrderByComboBox:QComboBox, changeYScaleButton:QPushButton, 
                 changePlotButton:QPushButton):
        
        self.plotFrame = plotFrame
        self.selectSiteComboBox = selectSiteComboBox
        self.plotOrderByComboBox = plotOrderByComboBox
        self.changeYScaleButton = changeYScaleButton
        self.changePlotButton = changePlotButton

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
        self.changePlotButton.clicked.connect(self.selectPlotType)
    

        