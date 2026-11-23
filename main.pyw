import multiprocessing
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.ui.mainWindow import DataAnalyzerWindow
from src.ui.theme import applyDarkTheme

VERSION = '2.0.0'

def main():
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)
    applyDarkTheme(app)

    window = DataAnalyzerWindow(VERSION)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()