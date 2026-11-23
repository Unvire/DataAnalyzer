import os
import tempfile

import plotly.graph_objects as go
from plotly.offline import get_plotlyjs
from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget


class PlotlyView(QWidget):
    _CACHE_DIR = os.path.join(tempfile.gettempdir(), 'data_analyzer_v2_plotly')
    _PLOTLY_JS_FILENAME = 'plotly.min.js'

    def __init__(self, parent=None):
        super().__init__(parent)
        self._htmlPath = os.path.join(self._CACHE_DIR, f'chart_{id(self)}.html')
        self._renderCounter = 0
        self._ensurePlotlyJsCached()
        self._buildUi()

    def _buildUi(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.webView = QWebEngineView(self)
        self.webView.page().setBackgroundColor(QColor('#1e1f22'))
        layout.addWidget(self.webView)
        self.showMessage('Load logs in order to display plot.')

    @classmethod
    def _ensurePlotlyJsCached(cls):
        os.makedirs(cls._CACHE_DIR, exist_ok=True)
        jsPath = os.path.join(cls._CACHE_DIR, cls._PLOTLY_JS_FILENAME)
        if not os.path.exists(jsPath):
            with open(jsPath, 'w', encoding='utf-8') as f:
                f.write(get_plotlyjs())

    def setFigure(self, fig: go.Figure):
        config = {
            'responsive': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        }
        plotDiv = fig.to_html(full_html=False, include_plotlyjs=False, config=config)
        htmlContent = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <script src="{self._PLOTLY_JS_FILENAME}"></script>
    <style>
        html, body {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            background-color: #1e1f22;
            overflow: hidden;
        }}
        .plotly-graph-div {{
            width: 100% !important;
            height: 100vh !important;
        }}
    </style>
</head>
<body>
    {plotDiv}
</body>
</html>"""

        with open(self._htmlPath, 'w', encoding='utf-8') as f:
            f.write(htmlContent)

        self._renderCounter += 1
        url = QUrl.fromLocalFile(self._htmlPath)
        url.setQuery(f'v={self._renderCounter}')
        self.webView.load(url)

    def showMessage(self, message: str):
        htmlContent = f"""<!DOCTYPE html>
<html>
<body style="background:#1e1f22; color:#9da0a8; font-family:'Segoe UI', sans-serif;
             display:flex; align-items:center; justify-content:center; height:92vh; margin:0;">
    <div style="text-align:center; font-size:15px;">{message}</div>
</body>
</html>"""
        self.webView.setHtml(htmlContent)

    def cleanup(self):
        if os.path.exists(self._htmlPath):
            try:
                os.remove(self._htmlPath)
            except OSError:
                pass