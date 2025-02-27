import sys, os
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5 import uic

from displayPlotWrapper import PlotWrapper
from dataContainer import DataContainer

class PlotDialog(QDialog):
    def __init__(self, dataContainer:DataContainer):
        super().__init__()
        uiFilePath = os.path.join(os.getcwd(), 'ui', 'plotDialog.ui')
        uic.loadUi(uiFilePath, self)
        self.setWindowTitle(dataContainer.name)

        self.closeCallbackHandle = lambda: None

        self.plotWidget = PlotWrapper(self.plotFrame, self.selectSiteComboBox, self.plotOrderByComboBox, self.changeYScaleButton,
                                      self.changePlotButton)
        self.plotWidget.setDataContainer(dataContainer)
        self.plotWidget.updateNumOfSites()
        self.plotWidget.generatePlot()
    
    def setCloseEventHandle(self, function):
        self.closeCallbackHandle = function

    def closeEvent(self, event):
        self.closeCallbackHandle(self.windowTitle())
        return super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PlotDialog()
    window.show()
    sys.exit(app.exec_())