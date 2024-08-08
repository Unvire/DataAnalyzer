import sys
import matplotlib.pyplot as plt
from PyQt5 import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from templateDataAnalyzerGUI import Ui_MainWindow
import numpy as np

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

        self.canvas = MplCanvas(self.plotFrame)
        self.plot_layout = QtWidgets.QVBoxLayout(self.plotFrame)
        self.plot_layout.addWidget(self.canvas)

        self.plot()

    def plot(self):
        # Tworzenie przykładowego wykresu
        t = np.arange(0.0, 2.0, 0.01)
        s = np.sin(2 * np.pi * t)
        self.canvas.ax.plot(t, s)
        self.canvas.ax.set(title='Sinus Wave', xlabel='Time (s)', ylabel='Amplitude')
        self.canvas.draw()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = DataAnalyzerGUI()
    window.show()
    sys.exit(app.exec_())