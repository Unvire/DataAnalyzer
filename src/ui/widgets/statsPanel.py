from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget


class StatsPanel(QWidget):
    METRIC_LAYOUT = [
        ('samples', 'Samples', 0, 0),
        ('yield', 'Yield', 0, 2),
        ('lsl', 'LSL', 1, 0),
        ('usl', 'USL', 1, 2),
        ('mean', 'Mean', 2, 0),
        ('sigma', 'Sigma', 2, 2),
        ('pp', 'Pp', 3, 0),
        ('cp', 'Cp', 3, 2),
        ('ppk', 'Ppk', 4, 0),
        ('cpk', 'Cpk', 4, 2),
        ('stability', 'Max/Min - 1', 5, 0),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._valueLabels: dict[str, QLabel] = {}
        self._buildUi()

    def _buildUi(self):
        outerLayout = QVBoxLayout(self)
        outerLayout.setContentsMargins(0, 0, 0, 0)

        groupBox = QGroupBox('Process statistics')
        grid = QGridLayout(groupBox)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        for key, labelText, row, col in self.METRIC_LAYOUT:
            keyLabel = QLabel(labelText)
            keyLabel.setProperty('role', 'statKey')

            valLabel = QLabel('—')
            valLabel.setProperty('role', 'statValue')
            valLabel.setTextInteractionFlags(Qt.TextSelectableByMouse)
            valLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            grid.addWidget(keyLabel, row, col)
            if key == 'stability':
                grid.addWidget(valLabel, row, col + 1, 1, 3)
            else:
                grid.addWidget(valLabel, row, col + 1)

            self._valueLabels[key] = valLabel

        outerLayout.addWidget(groupBox)

    def updateStats(self, stats: dict[str, str]):
        for key, label in self._valueLabels.items():
            label.setText(stats.get(key, '—'))

    def clear(self):
        for label in self._valueLabels.values():
            label.setText('—')