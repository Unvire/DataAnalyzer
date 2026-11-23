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
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        .plotly-graph-div {{
            width: 100% !important;
            height: 100vh !important;
        }}

        #point-card {{
            display: none;
            position: absolute;
            z-index: 9999;
            background-color: #26282e;
            border: 1px solid #43454a;
            border-radius: 6px;
            box-shadow: 0 4px 18px rgba(0, 0, 0, 0.45);
            color: #dfe1e5;
            width: 290px;
            padding: 10px 12px;
            font-size: 12px;
            user-select: text !important;
            -webkit-user-select: text !important;
            cursor: default;
        }}

        #point-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #35373c;
            padding-bottom: 6px;
            margin-bottom: 8px;
            font-weight: 600;
            color: #3574f0;
        }}

        #point-card-close {{
            background: none;
            border: none;
            color: #9da0a8;
            font-size: 16px;
            cursor: pointer;
            padding: 0 4px;
            line-height: 1;
        }}

        #point-card-close:hover {{
            color: #ffffff;
        }}

        .info-row {{
            display: flex;
            justify-content: space-between;
            margin: 4px 0;
            line-height: 1.4;
        }}

        .info-key {{
            color: #9da0a8;
            font-weight: 500;
        }}

        .info-val {{
            color: #dfe1e5;
            font-family: 'Consolas', monospace;
            text-align: right;
            user-select: text !important;
            -webkit-user-select: text !important;
        }}

        .sn-highlight {{
            color: #ffffff;
            background: #1e1f22;
            padding: 2px 5px;
            border-radius: 3px;
            border: 1px solid #35373c;
            font-weight: bold;
        }}

        #point-card-actions {{
            display: flex;
            gap: 6px;
            margin-top: 10px;
            padding-top: 8px;
            border-top: 1px solid #35373c;
        }}

        .card-btn {{
            flex: 1;
            background-color: #2b2d30;
            border: 1px solid #43454a;
            border-radius: 4px;
            color: #dfe1e5;
            padding: 5px 8px;
            font-size: 11px;
            cursor: pointer;
            text-align: center;
        }}

        .card-btn:hover {{
            background-color: #393b40;
            border-color: #5a5d64;
        }}

        .card-btn-accent {{
            background-color: #3574f0;
            border-color: #3574f0;
            color: #ffffff;
        }}

        .card-btn-accent:hover {{
            background-color: #4682f5;
        }}
    </style>
</head>
<body>
    {plotDiv}

    <div id="point-card">
        <div id="point-card-header">
            <span>Point Details</span>
            <button id="point-card-close" title="Close">&times;</button>
        </div>
        <div id="point-card-body"></div>
        <div id="point-card-actions">
            <button id="btn-copy-sn" class="card-btn card-btn-accent">Copy SN</button>
            <button id="btn-copy-all" class="card-btn">Copy Summary</button>
        </div>
    </div>

    <script>
        (function() {{
            var card = document.getElementById('point-card');
            var cardBody = document.getElementById('point-card-body');
            var closeBtn = document.getElementById('point-card-close');
            var copySnBtn = document.getElementById('btn-copy-sn');
            var copyAllBtn = document.getElementById('btn-copy-all');

            var currentPointData = {{}};

            function copyTextToClipboard(text) {{
                if (navigator.clipboard && window.isSecureContext) {{
                    navigator.clipboard.writeText(text).catch(function() {{
                        fallbackCopy(text);
                    }});
                }} else {{
                    fallbackCopy(text);
                }}
            }}

            function fallbackCopy(text) {{
                var textArea = document.createElement("textarea");
                textArea.value = text;
                textArea.style.position = "fixed";
                textArea.style.left = "-999999px";
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                try {{
                    document.execCommand('copy');
                }} catch (err) {{}}
                document.body.removeChild(textArea);
            }}

            closeBtn.addEventListener('click', function() {{
                card.style.display = 'none';
            }});

            copySnBtn.addEventListener('click', function() {{
                if (currentPointData.sn) {{
                    copyTextToClipboard(currentPointData.sn);
                    var origText = copySnBtn.innerText;
                    copySnBtn.innerText = 'Copied!';
                    setTimeout(function() {{ copySnBtn.innerText = origText; }}, 1200);
                }}
            }});

            copyAllBtn.addEventListener('click', function() {{
                var summary = [
                    'SN: ' + (currentPointData.sn || '—'),
                    'Site: ' + (currentPointData.site || '—'),
                    'Value: ' + (currentPointData.val || '—'),
                    'Date: ' + (currentPointData.date || '—'),
                    'LSL: ' + (currentPointData.lsl || '—'),
                    'USL: ' + (currentPointData.usl || '—')
                ].join('\\n');
                copyTextToClipboard(summary);
                var origText = copyAllBtn.innerText;
                copyAllBtn.innerText = 'Copied!';
                setTimeout(function() {{ copyAllBtn.innerText = origText; }}, 1200);
            }});

            var plotDiv = document.getElementsByClassName('plotly-graph-div')[0];
            if (plotDiv) {{
                plotDiv.on('plotly_click', function(data) {{
                    if (!data || !data.points || data.points.length === 0) return;
                    var pt = data.points[0];

                    if (pt.data && (pt.data.name === 'LSL' || pt.data.name === 'USL')) return;

                    var sn = '—';
                    var date = '—';
                    var lsl = '—';
                    var usl = '—';

                    if (pt.customdata && pt.customdata.length > 0) {{
                        sn = pt.customdata[0] || '—';
                        date = pt.customdata[1] || '—';
                        if (pt.customdata.length >= 4) {{
                            lsl = pt.customdata[2];
                            usl = pt.customdata[3];
                        }}
                    }}

                    var valFormatted = (typeof pt.y === 'number') ? pt.y.toPrecision(6) : pt.y;
                    var siteName = (pt.data && pt.data.name) ? pt.data.name.split(' (')[0] : '—';

                    currentPointData = {{
                        sn: sn,
                        site: siteName,
                        val: valFormatted,
                        date: date,
                        lsl: lsl,
                        usl: usl
                    }};

                    cardBody.innerHTML = 
                        '<div class="info-row"><span class="info-key">Serial Number:</span><span class="info-val sn-highlight">' + sn + '</span></div>' +
                        '<div class="info-row"><span class="info-key">Site:</span><span class="info-val">' + siteName + '</span></div>' +
                        '<div class="info-row"><span class="info-key">Value:</span><span class="info-val">' + valFormatted + '</span></div>' +
                        '<div class="info-row"><span class="info-key">Date:</span><span class="info-val">' + date + '</span></div>' +
                        (lsl !== '—' ? '<div class="info-row"><span class="info-key">Limits:</span><span class="info-val">[' + lsl + ', ' + usl + ']</span></div>' : '');

                    var evt = data.event;
                    var clickX = evt ? evt.clientX : (window.innerWidth / 2 - 145);
                    var clickY = evt ? evt.clientY : (window.innerHeight / 2 - 100);

                    var posX = clickX + 16;
                    var posY = clickY + 16;

                    if (posX + 300 > window.innerWidth) posX = clickX - 305;
                    if (posY + 230 > window.innerHeight) posY = clickY - 220;

                    card.style.left = Math.max(10, posX) + 'px';
                    card.style.top = Math.max(10, posY) + 'px';
                    card.style.display = 'block';
                }});
            }}
        }})();
    </script>
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