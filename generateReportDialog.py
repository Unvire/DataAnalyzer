import sys, os
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel
from PyQt5 import uic

from testListWrapper import TestListWrapper
from dataContainer import DataContainer

class generateReportDialog(QDialog):
    def __init__(self, measurementsDict:dict[str:DataContainer]):
        super().__init__()
        uiFilePath = os.path.join(os.getcwd(), 'ui', 'generateRaportDialog.ui')
        uic.loadUi(uiFilePath, self)

        self.measurements = measurementsDict
        testNames = self._getTestNames()

        self.testListWrapper = TestListWrapper(self.listWidget, self.filterTestsButton, self.resetFilterButton, self.regexPatternEdit)
        self.testListWrapper.setRowOnClickEvent(self.listWidgetClickedEvent)

        self.testListWrapper.setTestNames(testNames)
        self.testListWrapper.generateMeasurementsList()

        self._setStatusOfTestsHandlingWidgets(False)
        self.allTestsCheckBox.toggled.connect(lambda state: self._setStatusOfTestsHandlingWidgets(not state))
    
    def listWidgetClickedEvent(self, *args):
        pass
    
    def _getTestNames(self) -> list[str]:
        return list(self.measurements.keys())

    def _allTestsCheckboxValueChanged(self, state):
        self._setStatusOfTestsHandlingWidgets(state)

    def _setStatusOfTestsHandlingWidgets(self, status:bool):
        self.listWidget.setEnabled(status)
        self.filterTestsButton.setEnabled(status)
        self.resetFilterButton.setEnabled(status)
        self.regexPatternEdit.setEnabled(status)

if __name__ == '__main__':
    mockDict = {'a':'a', 'b':'b', 'c':'c', 'd':'d'}
    app = QApplication(sys.argv)
    window = generateReportDialog(mockDict)
    window.show()
    sys.exit(app.exec_())