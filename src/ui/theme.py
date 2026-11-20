from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication


DARK_QSS = """
QWidget {
    background-color: #1e1f22;
    color: #dfe1e5;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #1e1f22;
}

QSplitter::handle {
    background-color: #2b2d30;
    width: 3px;
}

QSplitter::handle:hover {
    background-color: #3574f0;
}

QGroupBox {
    border: 1px solid #393b40;
    border-radius: 6px;
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
    color: #bcbec4;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    background-color: #1e1f22;
}

QPushButton {
    background-color: #2b2d30;
    border: 1px solid #43454a;
    border-radius: 5px;
    padding: 6px 12px;
    color: #dfe1e5;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #393b40;
    border-color: #5a5d64;
}

QPushButton:pressed {
    background-color: #25272a;
}

QPushButton:disabled {
    background-color: #242528;
    color: #6f737a;
    border-color: #323438;
}

QPushButton[accent="true"] {
    background-color: #3574f0;
    border-color: #3574f0;
    color: #ffffff;
}

QPushButton[accent="true"]:hover {
    background-color: #4682f5;
    border-color: #4682f5;
}

QPushButton[accent="true"]:disabled {
    background-color: #2b3a55;
    border-color: #2b3a55;
    color: #7c8aa5;
}

QPushButton:checked {
    background-color: #2e436e;
    border-color: #3574f0;
    color: #ffffff;
}

QComboBox, QLineEdit {
    background-color: #2b2d30;
    border: 1px solid #43454a;
    border-radius: 5px;
    padding: 5px 8px;
    color: #dfe1e5;
    selection-background-color: #3574f0;
}

QComboBox:focus, QLineEdit:focus {
    border-color: #3574f0;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox QAbstractItemView {
    background-color: #2b2d30;
    border: 1px solid #43454a;
    selection-background-color: #2e436e;
    color: #dfe1e5;
    outline: 0;
}

QListWidget, QTableView {
    background-color: #26282e;
    border: 1px solid #393b40;
    border-radius: 6px;
    alternate-background-color: #2b2d30;
    gridline-color: #323438;
    outline: 0;
}

QListWidget::item {
    padding: 5px 8px;
    border-radius: 4px;
}

QListWidget::item:hover {
    background-color: #32353d;
}

QListWidget::item:selected {
    background-color: #2e436e;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #2b2d30;
    color: #bcbec4;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #393b40;
    border-bottom: 1px solid #393b40;
    font-weight: 600;
}

QTabWidget::pane {
    border: 1px solid #393b40;
    border-radius: 6px;
    background-color: #1e1f22;
    top: -1px;
}

QTabBar::tab {
    background-color: #26282e;
    color: #9da0a8;
    border: 1px solid #393b40;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 7px 16px;
    margin-right: 3px;
}

QTabBar::tab:hover {
    color: #dfe1e5;
    background-color: #2f323a;
}

QTabBar::tab:selected {
    background-color: #1e1f22;
    color: #ffffff;
    border-bottom: 2px solid #3574f0;
    font-weight: 600;
}

QProgressBar {
    background-color: #2b2d30;
    border: 1px solid #393b40;
    border-radius: 4px;
    text-align: center;
    color: #dfe1e5;
    min-height: 16px;
}

QProgressBar::chunk {
    background-color: #3574f0;
    border-radius: 3px;
}

QStatusBar {
    background-color: #26282e;
    border-top: 1px solid #393b40;
    color: #bcbec4;
}

QCheckBox {
    spacing: 6px;
}

QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border-radius: 3px;
    border: 1px solid #5a5d64;
    background-color: #2b2d30;
}

QCheckBox::indicator:checked {
    background-color: #3574f0;
    border-color: #3574f0;
}

QScrollBar:vertical {
    background: #1e1f22;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #43454a;
    border-radius: 5px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #5a5d64;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #1e1f22;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #43454a;
    border-radius: 5px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background: #5a5d64;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QLabel[role="statKey"] {
    color: #9da0a8;
    font-size: 12px;
}

QLabel[role="statValue"] {
    background-color: #26282e;
    border: 1px solid #35373c;
    border-radius: 4px;
    padding: 3px 6px;
    color: #dfe1e5;
    font-family: "Consolas", "Cascadia Mono", monospace;
    font-size: 12px;
}
"""


def applyDarkTheme(app:QApplication):
    app.setStyle('Fusion')

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor('#1e1f22'))
    palette.setColor(QPalette.WindowText, QColor('#dfe1e5'))
    palette.setColor(QPalette.Base, QColor('#26282e'))
    palette.setColor(QPalette.AlternateBase, QColor('#2b2d30'))
    palette.setColor(QPalette.ToolTipBase, QColor('#2b2d30'))
    palette.setColor(QPalette.ToolTipText, QColor('#dfe1e5'))
    palette.setColor(QPalette.Text, QColor('#dfe1e5'))
    palette.setColor(QPalette.Button, QColor('#2b2d30'))
    palette.setColor(QPalette.ButtonText, QColor('#dfe1e5'))
    palette.setColor(QPalette.Highlight, QColor('#3574f0'))
    palette.setColor(QPalette.HighlightedText, QColor('#ffffff'))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor('#6f737a'))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor('#6f737a'))

    app.setPalette(palette)
    app.setStyleSheet(DARK_QSS)