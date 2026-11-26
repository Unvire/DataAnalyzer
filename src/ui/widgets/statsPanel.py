from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget


class StatsPanel(QWidget):
    METRIC_LAYOUT = [
        ('samples', 'Samples', 0, 0),
        ('yield', 'Yield', 0, 2),
        ('failLH', 'Fail L/H', 1, 0),
        ('dpmo', 'DPMO', 1, 2),
        ('lsl', 'LSL', 2, 0),
        ('usl', 'USL', 2, 2),
        ('mean', 'Mean', 3, 0),
        ('sigma', 'Sigma', 3, 2),
        ('pp', 'Pp', 4, 0),
        ('cp', 'Cp', 4, 2),
        ('ppk', 'Ppk', 5, 0),
        ('cpk', 'Cpk', 5, 2),
        ('ppkNp', 'Ppk (NP)', 6, 0),
        ('tolUtil', 'Tol. Util.', 6, 2),
        ('centering', 'Centering', 7, 0),
        ('siteDelta', 'Site Delta', 7, 2),
        ('skewness', 'Skewness', 8, 0),
        ('kurtosis', 'Kurtosis', 8, 2),
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
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        for key, labelText, row, col in self.METRIC_LAYOUT:
            keyLabel = QLabel(labelText)
            keyLabel.setProperty('role', 'statKey')

            valLabel = QLabel('—')
            valLabel.setProperty('role', 'statValue')
            valLabel.setProperty('status', 'neutral')
            valLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            valLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            grid.addWidget(keyLabel, row, col)
            grid.addWidget(valLabel, row, col + 1)

            self._valueLabels[key] = valLabel

        outerLayout.addWidget(groupBox)

    def updateStats(self, stats:dict[str,str], statuses:dict[str, str]|None=None, tooltips:dict[str, str]|None=None):
        statuses = statuses or {}
        tooltips = tooltips or {}

        for key, label in self._valueLabels.items():
            label.setText(stats.get(key, '—'))
            label.setToolTip(tooltips.get(key, ''))

            newStatus = statuses.get(key, 'neutral') if key in stats else 'neutral'
            if label.property('status') != newStatus:
                label.setProperty('status', newStatus)
                label.style().unpolish(label)
                label.style().polish(label)

    def clear(self):
        for label in self._valueLabels.values():
            label.setText('—')
            label.setToolTip('')
            if label.property('status') != 'neutral':
                label.setProperty('status', 'neutral')
                label.style().unpolish(label)
                label.style().polish(label)