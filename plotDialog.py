import sys, os
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5 import uic

from displayPlotWrapper import PlotWrapper

class PlotDialog(QDialog):
    def __init__(self):
        super().__init__()
        uiFilePath = os.path.join(os.getcwd(), 'ui', 'plotDialog.ui')
        uic.loadUi(uiFilePath, self)

        self.plotWidget = PlotWrapper(self.plotFrame, self.selectSiteComboBox, self.plotOrderByComboBox, self.changeYScaleButton,
                                      self.changePlotButton)
        
    def plotData(self, dataList:list[list[float, str]], plotName:str, limits:list[float, float], siteNames:list[str]):
        self.plotWidget.setDataList(dataList)
        self.plotWidget.setPlotName(plotName)
        self.plotWidget.setLimits(limits)
        self.plotWidget.setSiteNames(siteNames)
        self.plotWidget.generatePlot()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PlotDialog()
    window.show()
    sys.exit(app.exec_())