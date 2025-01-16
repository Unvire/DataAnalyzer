
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100, isUsePyPlot=True):
        if not isUsePyPlot:
            self.fig = Figure(figsize=(width, height), dpi=dpi)
        else:
            self.fig = plt.figure(figsize=(width, height), dpi=dpi)
            
        self.ax = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)
        self.setParent(parent)
    
    def savefig(self, *args, **kwargs):
        self.fig.savefig(*args, **kwargs)
    
    def close(self):
        plt.close(self.fig)