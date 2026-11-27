from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QTextBrowser, QVBoxLayout, QWidget,
)

from src.processCalculator import METRIC_HELP


STATS_GUIDE_HTML = """
<style>
    body { color: #dfe1e5; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; line-height: 1.45; }
    h3 { color: #4c8dff; margin: 12px 0 6px 0; border-bottom: 1px solid #35373c; padding-bottom: 3px; }
    ul { margin: 4px 0 8px 0; padding-left: 18px; }
    li { margin-bottom: 4px; }
    b { color: #ffffff; }
    table { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 11px; }
    th, td { border: 1px solid #393b40; padding: 5px 7px; text-align: left; }
    th { background-color: #2b2d30; color: #bcbec4; }
    .ok { color: #66bb6a; font-weight: 600; }
    .warn { color: #ffa726; font-weight: 600; }
    .bad { color: #ef5350; font-weight: 600; }
</style>

<h3>1. Batch Quality</h3>
<ul>
    <li><b>Yield (%)</b> — Percentage of units within limits. Measures pass rate, not safety margin.</li>
    <li><b>Fail L/H</b> — Failure split below LSL (&lt; LSL) vs above USL (&gt; USL). Points directly to drift or offset direction.</li>
    <li><b>DPMO / PPM</b> — Defects Per Million Opportunities. Normalizes defect counts across lots of different sizes.</li>
</ul>

<h3>2. Process Capability (Short-Term vs Long-Term)</h3>
<ul>
    <li><b>&sigma;<sub>within</sub> (Moving Range)</b> — Short-term unit-to-unit noise inside each site (MR&#772; / d<sub>2</sub>).</li>
    <li><b>&sigma;<sub>overall</sub></b> — Total lot variation (noise + time drift + lot changes + site-to-site offsets).</li>
    <li><b>Cp / Pp</b> — Potential capability ignoring centering: whether 6&sigma; physically fits inside [LSL, USL].</li>
    <li><b>Cpk / Ppk</b> — Actual capability accounting for mean shift to the nearest limit.</li>
    <li><b>Ppk (NP)</b> — Non-parametric ISO 22514 percentile capability (P<sub>0.135</sub>, P<sub>50</sub>, P<sub>99.865</sub>). Use when data is skewed (|Skewness| &ge; 1.0).</li>
</ul>

<h3>3. Tolerance Position &amp; Distribution Shape</h3>
<ul>
    <li><b>Tol. Util. (%)</b> — Share of the tolerance window consumed by 6&sigma;<sub>overall</sub> (= 100% / Pp). Lower is better.</li>
    <li><b>Centering (%)</b> — Mean shift from midpoint (% of half-tolerance). 0% = dead-center, &plusmn;100% = sitting on LSL/USL.</li>
    <li><b>Site Delta (%)</b> — Distance between highest and lowest site means as % of the full tolerance window.</li>
    <li><b>Skewness (G<sub>1</sub>)</b> — Asymmetry (0 = symmetric, &gt;0 = right tail toward USL, &lt;0 = left tail toward LSL).</li>
    <li><b>Kurtosis (G<sub>2</sub>)</b> — Excess kurtosis (0 = normal, &gg;0 = heavy tails/isolated outliers, &lt;-1 = flat or bimodal).</li>
</ul>

<h3>4. Quick Diagnostic Cheat Sheet</h3>
<table>
    <tr><th>Pattern</th><th>Most Likely Root Cause</th></tr>
    <tr><td>High Cpk, low Ppk, high <b>Site Delta</b></td><td>Calibration mismatch, cabling, or probe differences between test sites.</td></tr>
    <tr><td>High Cpk, low Ppk, low <b>Site Delta</b></td><td>Thermal/time drift or step change between SMT component reels/lots.</td></tr>
    <tr><td>High Cp &amp; Pp, low Cpk &amp; Ppk, high <b>Centering</b></td><td>Constant offset (4-wire compensation error or shifted nominal value).</td></tr>
    <tr><td>Low Ppk, high <b>Kurtosis</b> (&gg;0), healthy Ppk (NP)</td><td>A few isolated outliers (intermittent probe contact) inflating &sigma;<sub>overall</sub>.</td></tr>
    <tr><td>Negative <b>Kurtosis</b> (&lt;-1)</td><td>Bimodal distribution — inspect per-site curves on Capability plot.</td></tr>
</table>

<h3>5. Status Color Thresholds</h3>
<ul>
    <li><b>Capability (Pp, Cp, Ppk, Cpk, Ppk NP):</b> <span class="ok">&ge; 1.33</span> | <span class="warn">1.00 – 1.32</span> | <span class="bad">&lt; 1.00</span></li>
    <li><b>Yield:</b> <span class="ok">&ge; 99.5%</span> | <span class="warn">98.0 – 99.49%</span> | <span class="bad">&lt; 98.0%</span></li>
    <li><b>Tol. Util.:</b> <span class="ok">&le; 75%</span> | <span class="warn">75.1 – 100%</span> | <span class="bad">&gt; 100%</span> &nbsp;&bull;&nbsp; <b>Site Delta:</b> <span class="ok">&le; 10%</span> | <span class="warn">10.1 – 25%</span> | <span class="bad">&gt; 25%</span></li>
</ul>
"""


class StatsGuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Process Statistics Guide')
        self.resize(680, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(STATS_GUIDE_HTML)
        browser.setStyleSheet(
            'QTextBrowser { background-color: #26282e; border: 1px solid #393b40; border-radius: 6px; padding: 6px; }'
        )

        closeRow = QHBoxLayout()
        closeRow.addStretch(1)
        closeBtn = QPushButton('Close')
        closeBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        closeBtn.clicked.connect(self.accept)
        closeRow.addWidget(closeBtn)

        layout.addWidget(browser, 1)
        layout.addLayout(closeRow)


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
        self._guideDialog: StatsGuideDialog | None = None
        self._buildUi()

    def _buildUi(self):
        outerLayout = QVBoxLayout(self)
        outerLayout.setContentsMargins(0, 0, 0, 0)

        groupBox = QGroupBox('Process statistics')
        groupLayout = QVBoxLayout(groupBox)
        groupLayout.setContentsMargins(6, 6, 6, 6)
        groupLayout.setSpacing(4)

        topRow = QHBoxLayout()
        topRow.setContentsMargins(0, 0, 0, 0)
        hintLabel = QLabel('Hover any metric for details')
        hintLabel.setStyleSheet('color: #7c8089; font-size: 10px;')

        self.helpButton = QPushButton('? Guide')
        self.helpButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.helpButton.setToolTip('Open Process Statistics & Diagnostics Guide')
        self.helpButton.setStyleSheet(
            'QPushButton { padding: 1px 7px; font-size: 10px; border-radius: 4px; color: #bcbec4; }'
        )
        self.helpButton.clicked.connect(self._openGuideDialog)

        topRow.addWidget(hintLabel)
        topRow.addStretch(1)
        topRow.addWidget(self.helpButton)

        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        for key, labelText, row, col in self.METRIC_LAYOUT:
            baseHelp = METRIC_HELP.get(key, '')

            keyLabel = QLabel(labelText)
            keyLabel.setProperty('role', 'statKey')
            keyLabel.setToolTip(baseHelp)

            valLabel = QLabel('—')
            valLabel.setProperty('role', 'statValue')
            valLabel.setProperty('status', 'neutral')
            valLabel.setToolTip(baseHelp)
            valLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            valLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            grid.addWidget(keyLabel, row, col)
            grid.addWidget(valLabel, row, col + 1)

            self._valueLabels[key] = valLabel

        groupLayout.addLayout(topRow)
        groupLayout.addLayout(grid)
        outerLayout.addWidget(groupBox)

    def _openGuideDialog(self):
        if self._guideDialog is None:
            self._guideDialog = StatsGuideDialog(self)
        self._guideDialog.show()
        self._guideDialog.raise_()
        self._guideDialog.activateWindow()

    def updateStats(self, stats:dict[str, str], statuses:dict[str, str]|None=None, tooltips:dict[str, str]|None=None):
        statuses = statuses or {}
        tooltips = tooltips or {}

        for key, label in self._valueLabels.items():
            label.setText(stats.get(key, '—'))
            label.setToolTip(tooltips.get(key, METRIC_HELP.get(key, '')))

            newStatus = statuses.get(key, 'neutral') if key in stats else 'neutral'
            if label.property('status') != newStatus:
                label.setProperty('status', newStatus)
                label.style().unpolish(label)
                label.style().polish(label)

    def clear(self):
        for key, label in self._valueLabels.items():
            label.setText('—')
            label.setToolTip(METRIC_HELP.get(key, ''))
            if label.property('status') != 'neutral':
                label.setProperty('status', 'neutral')
                label.style().unpolish(label)
                label.style().polish(label)