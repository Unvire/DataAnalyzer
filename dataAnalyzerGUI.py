import sys
import matplotlib.pyplot as plt
import numpy as np

from PyQt5 import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from templateDataAnalyzerGUI import Ui_MainWindow
from fileProcessorFactory import FileProcessorsFactory

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

        FILE_PROCESSORS = ['SPEA']
        for fileName in FILE_PROCESSORS:
            self.comboBox.addItem(fileName)
        
        self.pushButton.clicked.connect(self.selectFolder)

        self.canvas = MplCanvas(self.plotFrame)
        self.plot_layout = QtWidgets.QVBoxLayout(self.plotFrame)
        self.plot_layout.addWidget(self.canvas)
        self.plot()
    
    def selectFolder(self):
        folderPath = str(QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory"))
        if folderPath:
            self.processLogsInFolder(folderPath)
    
    def processLogsInFolder(self, folderPath:str):
        print(folderPath)

    def plot(self):
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