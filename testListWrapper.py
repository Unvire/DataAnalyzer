import re

from PyQt5.QtWidgets import QListWidget, QLineEdit, QPushButton

class TestListWrapper:
    def __init__(self, listWidget:QListWidget, filterTestsButton:QPushButton, resetFilterButton:QPushButton, regexPatternEdit:QLineEdit):
        self.listWidget = listWidget
        self.filterTestsButton = filterTestsButton
        self.resetFilterButton = resetFilterButton
        self.regexPatternEdit = regexPatternEdit
        self.testNames = None
        self.rowOnClickEvent = None
        
        self.filterTestsButton.clicked.connect(self.filterMeasurementsWithRegex)
        self.resetFilterButton.clicked.connect(self.resetFilterMeasurements)        
        self.listWidget.itemClicked.connect(lambda item: self.listWidgetClickedEvent(item))
        self.listWidget.currentRowChanged.connect(lambda rowID: self.listWidgetArrowKeyEvent(rowID))
    
    def setTestNames(self, testNames:list[str]):
        self.testNames = testNames
    
    def setRowOnClickEvent(self, functionHandle):
        self.rowOnClickEvent = functionHandle

    def getTestNames(self) -> list[str]:
        return self.testNames
    
    def filterMeasurementsWithRegex(self):
        pattern = self.regexPatternEdit.text()
        result = []
        try:
            for testName in self.testNames:
                if re.search(pattern, testName):
                    result.append(testName)
            self.generateMeasurementsList(result)
        except re.error:
            pass
    
    def resetFilterMeasurements(self):
        self.generateMeasurementsList(self.testNames)

    def generateMeasurementsList(self, testsList:list[str]|None=None):
        testsList = self.testNames if not testsList else testsList
        self.listWidget.clear()
        self.listWidget.addItems(testsList)
    
    def listWidgetArrowKeyEvent(self, rowID:int):
        item = self.listWidget.item(rowID)
        self.listWidgetClickedEvent(item)
    
    def listWidgetClickedEvent(self, item):
        self.rowOnClickEvent(item)
    
    def getSelectedItems(self) -> list[str]:
        return [item.text() for item in self.listWidget.selectedItems()]