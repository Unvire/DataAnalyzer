import sys, os
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5 import uic

from testListWrapper import TestListWrapper

class GenerateReportDialog(QDialog):
    def __init__(self, testNames:list[str], numOfSites:int):
        super().__init__()
        uiFilePath = os.path.join(os.getcwd(), 'ui', 'generateRaportDialog.ui')
        uic.loadUi(uiFilePath, self)

        self.testNames = testNames

        if numOfSites > 1:           
            for i in range(numOfSites):
                self.selectSiteComboBox.addItem(f'{i + 1}')

        self.testListWrapper = TestListWrapper(self.listWidget, self.filterTestsButton, self.resetFilterButton, self.regexPatternEdit)
        self.testListWrapper.setRowOnClickEvent(self.listWidgetClickedEvent)

        self.testListWrapper.setTestNames(testNames)
        self.testListWrapper.generateMeasurementsList()

        self._setStatusOfTestsHandlingWidgets(False)
        self.allTestsCheckBox.toggled.connect(lambda state: self._setStatusOfTestsHandlingWidgets(not state))

        self.generateButton.clicked.connect(self.accept)
    
    def getData(self) -> tuple[list[str], str, str]:        
        selectedTests = self.testNames if self.allTestsCheckBox.isChecked() else self.testListWrapper.getSelectedItems()
        orderBy = self.plotOrderByComboBox.currentText()
        return selectedTests, str(self.selectSiteComboBox.currentIndex()), orderBy
    
    def listWidgetClickedEvent(self, *args):
        pass

    def _allTestsCheckboxValueChanged(self, state):
        self._setStatusOfTestsHandlingWidgets(state)

    def _setStatusOfTestsHandlingWidgets(self, status:bool):
        self.listWidget.setEnabled(status)
        self.filterTestsButton.setEnabled(status)
        self.resetFilterButton.setEnabled(status)
        self.regexPatternEdit.setEnabled(status)

if __name__ == '__main__':
    mockDict = ['a', 'b', 'c', 'd', 'e', 'f']
    app = QApplication(sys.argv)
    window = GenerateReportDialog(mockDict, 2)
    window.show()
    sys.exit(app.exec_())