import multiprocessing
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from src.ui.mainWindow import DataAnalyzerWindow
from src.ui.theme import applyDarkTheme

VERSION = '2.0.0'

def main():
    multiprocessing.freeze_support()
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    applyDarkTheme(app)

    window = DataAnalyzerWindow(VERSION)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()