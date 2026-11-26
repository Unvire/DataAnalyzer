import base64
import json
import os
import tempfile
from typing import Callable

import plotly.graph_objects as go
from plotly.offline import get_plotlyjs
from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget


class _PlotlyWebEnginePage(QWebEnginePage):
    _CLIPBOARD_PREFIX = '__PY_CLIPBOARD__:'

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        if isinstance(message, str) and message.startswith(self._CLIPBOARD_PREFIX):
            payload = message[len(self._CLIPBOARD_PREFIX):]
            try:
                text = json.loads(payload)
            except json.JSONDecodeError:
                text = payload
            QGuiApplication.clipboard().setText(str(text))
            return
        super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)


class PlotlyView(QWidget):
    _CACHE_DIR = os.path.join(tempfile.gettempdir(), 'data_analyzer_v2_plotly')
    _PLOTLY_JS_FILENAME = 'plotly.min.js'

    def __init__(self, parent=None):
        super().__init__(parent)
        self._htmlPath = os.path.join(self._CACHE_DIR, f'chart_{id(self)}.html')
        self._shellReady = False
        self._pendingFigureJson: str | None = None
        self._pendingMessage: str | None = 'Load logs in order to display plot.'
        self._ensurePlotlyJsCached()
        self._writeShellHtml()
        self._buildUi()

    def _buildUi(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.webView = QWebEngineView(self)
        self._webPage = _PlotlyWebEnginePage(self.webView)
        self.webView.setPage(self._webPage)
        self._webPage.setBackgroundColor(QColor('#1e1f22'))

        settings = self.webView.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste, True)

        self.webView.loadFinished.connect(self._onShellLoaded)
        layout.addWidget(self.webView)

        self.webView.load(QUrl.fromLocalFile(self._htmlPath))

    @classmethod
    def _ensurePlotlyJsCached(cls):
        os.makedirs(cls._CACHE_DIR, exist_ok=True)
        jsPath = os.path.join(cls._CACHE_DIR, cls._PLOTLY_JS_FILENAME)
        if not os.path.exists(jsPath):
            with open(jsPath, 'w', encoding='utf-8') as f:
                f.write(get_plotlyjs())

    def _writeShellHtml(self):
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
        #plotly-container {{
            width: 100%;
            height: 100vh;
            display: none;
        }}
        #message-overlay {{
            width: 100%;
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #9da0a8;
            font-size: 15px;
            text-align: center;
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
            width: 295px;
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
    <div id="message-overlay">Load logs in order to display plot.</div>
    <div id="plotly-container"></div>

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
            var plotDiv = document.getElementById('plotly-container');
            var msgOverlay = document.getElementById('message-overlay');
            var card = document.getElementById('point-card');
            var cardBody = document.getElementById('point-card-body');
            var closeBtn = document.getElementById('point-card-close');
            var copySnBtn = document.getElementById('btn-copy-sn');
            var copyAllBtn = document.getElementById('btn-copy-all');

            var plotConfig = {{
                responsive: true,
                displaylogo: false,
                modeBarButtonsToRemove: ['lasso2d', 'select2d']
            }};

            var currentPointData = {{}};
            var currentLayoutXTitle = '';

            // Prevent mouse drags inside popup from panning/zooming the plot underneath
            card.addEventListener('mousedown', function(e) {{ e.stopPropagation(); }});
            card.addEventListener('click', function(e) {{ e.stopPropagation(); }});

            function copyTextToClipboard(text) {{
                var strVal = String(text);
                console.log('__PY_CLIPBOARD__:' + JSON.stringify(strVal));
            }}

            function escapeHtml(str) {{
                return String(str)
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');
            }}

            function formatNum(val) {{
                var num = Number(val);
                if (val !== null && val !== '' && !isNaN(num)) {{
                    return Number(num.toPrecision(6)).toString();
                }}
                return String(val);
            }}

            closeBtn.addEventListener('click', function() {{
                card.style.display = 'none';
            }});

            copySnBtn.addEventListener('click', function() {{
                if (currentPointData.sn && currentPointData.sn !== '—') {{
                    copyTextToClipboard(currentPointData.sn);
                    copySnBtn.innerText = 'Copied!';
                    setTimeout(function() {{ copySnBtn.innerText = 'Copy SN'; }}, 1200);
                }}
            }});

            copyAllBtn.addEventListener('click', function() {{
                var lines = [
                    'SN: ' + (currentPointData.sn || '—'),
                    'Site: ' + (currentPointData.site || '—'),
                    'Value: ' + (currentPointData.val || '—'),
                    'Date: ' + (currentPointData.date || '—')
                ];
                if (currentPointData.lsl && currentPointData.lsl !== '—') {{
                    lines.push('LSL: ' + currentPointData.lsl);
                    lines.push('USL: ' + currentPointData.usl);
                }}
                copyTextToClipboard(lines.join('\\n'));
                copyAllBtn.innerText = 'Copied!';
                setTimeout(function() {{ copyAllBtn.innerText = 'Copy Summary'; }}, 1200);
            }});

            function handlePointClick(data) {{
                if (!data || !data.points || data.points.length === 0) return;
                var pt = data.points[0];

                if (pt.data && (pt.data.name === 'LSL' || pt.data.name === 'USL')) return;

                var sn = '—';
                var date = '—';
                var lsl = '—';
                var usl = '—';
                var siteName = (pt.data && pt.data.name) ? pt.data.name.split(' (')[0] : '—';
                var valFormatted = '';

                var cd = pt.customdata;
                if (cd && cd.length > 0) {{
                    sn = (cd[0] !== undefined && cd[0] !== null && cd[0] !== '') ? String(cd[0]) : '—';
                    date = (cd[1] !== undefined && cd[1] !== null && cd[1] !== '') ? String(cd[1]) : '—';
                    if (cd.length >= 5) {{
                        lsl = String(cd[2]);
                        usl = String(cd[3]);
                        valFormatted = formatNum(cd[4]);
                        if (cd.length >= 6 && cd[5] !== undefined && cd[5] !== null) {{
                            siteName = 'Site ' + cd[5];
                        }}
                    }} else if (cd.length === 3) {{
                        siteName = 'Site ' + cd[2];
                    }}
                }}

                if (!valFormatted) {{
                    if (currentLayoutXTitle === 'CX') {{
                        valFormatted = 'CX=' + formatNum(pt.x) + ', CY=' + formatNum(pt.y);
                    }} else if (pt.y === 0 && typeof pt.x === 'number' && currentLayoutXTitle.indexOf('Measured Value') === 0) {{
                        valFormatted = formatNum(pt.x);
                    }} else {{
                        valFormatted = formatNum(pt.y);
                    }}
                }}

                currentPointData = {{
                    sn: sn,
                    site: siteName,
                    val: valFormatted,
                    date: date,
                    lsl: lsl,
                    usl: usl
                }};

                cardBody.innerHTML =
                    '<div class="info-row"><span class="info-key">Serial Number:</span><span class="info-val sn-highlight">' + escapeHtml(sn) + '</span></div>' +
                    '<div class="info-row"><span class="info-key">Site:</span><span class="info-val">' + escapeHtml(siteName) + '</span></div>' +
                    '<div class="info-row"><span class="info-key">Value:</span><span class="info-val">' + escapeHtml(valFormatted) + '</span></div>' +
                    '<div class="info-row"><span class="info-key">Date:</span><span class="info-val">' + escapeHtml(date) + '</span></div>' +
                    (lsl !== '—' ? '<div class="info-row"><span class="info-key">Limits:</span><span class="info-val">[' + escapeHtml(lsl) + ', ' + escapeHtml(usl) + ']</span></div>' : '');

                var evt = data.event;
                var clickX = evt ? evt.clientX : (window.innerWidth / 2 - 145);
                var clickY = evt ? evt.clientY : (window.innerHeight / 2 - 100);

                var posX = clickX + 16;
                var posY = clickY + 16;

                if (posX + 305 > window.innerWidth) posX = clickX - 310;
                if (posY + 230 > window.innerHeight) posY = clickY - 220;

                card.style.left = Math.max(10, posX) + 'px';
                card.style.top = Math.max(10, posY) + 'px';
                card.style.display = 'block';
            }}

            function bindPlotClick() {{
                if (!plotDiv || typeof plotDiv.on !== 'function') return;
                if (typeof plotDiv.removeAllListeners === 'function') {{
                    plotDiv.removeAllListeners('plotly_click');
                }}
                plotDiv.on('plotly_click', handlePointClick);
            }}

            window.renderPlot = function(figObj) {{
                card.style.display = 'none';
                msgOverlay.style.display = 'none';
                plotDiv.style.display = 'block';

                var layout = figObj.layout || {{}};
                currentLayoutXTitle = (layout.xaxis && layout.xaxis.title && layout.xaxis.title.text)
                    ? String(layout.xaxis.title.text)
                    : '';

                Plotly.react(plotDiv, figObj.data || [], layout, plotConfig)
                    .then(function() {{
                        bindPlotClick();
                        Plotly.Plots.resize(plotDiv);
                    }});
            }};

            window.showMessage = function(msg) {{
                card.style.display = 'none';
                if (typeof Plotly !== 'undefined') {{
                    try {{ Plotly.purge(plotDiv); }} catch (e) {{}}
                }}
                plotDiv.style.display = 'none';
                msgOverlay.textContent = msg;
                msgOverlay.style.display = 'flex';
            }};

            window.addEventListener('resize', function() {{
                if (plotDiv.style.display !== 'none' && typeof Plotly !== 'undefined') {{
                    Plotly.Plots.resize(plotDiv);
                }}
            }});
        }})();
    </script>
</body>
</html>"""

        with open(self._htmlPath, 'w', encoding='utf-8') as f:
            f.write(htmlContent)

    def _onShellLoaded(self, ok: bool):
        if not ok:
            return
        self._shellReady = True
        if self._pendingFigureJson is not None:
            figJson = self._pendingFigureJson
            self._pendingFigureJson = None
            self._pendingMessage = None
            self._runRenderPlot(figJson)
        elif self._pendingMessage is not None:
            msg = self._pendingMessage
            self._pendingMessage = None
            self._runShowMessage(msg)

    def _runRenderPlot(self, figJson: str):
        safeJson = figJson.replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
        self.webView.page().runJavaScript(f'window.renderPlot({safeJson});')

    def _runShowMessage(self, message: str):
        self.webView.page().runJavaScript(f'window.showMessage({json.dumps(message)});')

    def setFigure(self, fig: go.Figure):
        figJson = fig.to_json()
        if not self._shellReady:
            self._pendingFigureJson = figJson
            self._pendingMessage = None
            return
        self._runRenderPlot(figJson)

    def copyPlotToClipboard(self, onDone: Callable[[bool], None] | None = None):
        jsScript = """
        (function() {
            var gd = document.getElementById('plotly-container');
            if (!gd || gd.style.display === 'none' || typeof Plotly === 'undefined') return null;
            return Plotly.toImage(gd, {format: 'png', width: 1920, height: 1080});
        })();
        """

        def handleResult(dataUri):
            success = False
            if dataUri and isinstance(dataUri, str) and dataUri.startswith('data:image/png;base64,'):
                try:
                    rawBase64 = dataUri.split(',', 1)[1]
                    imgBytes = base64.b64decode(rawBase64)
                    qimg = QImage.fromData(imgBytes)
                    if not qimg.isNull():
                        QGuiApplication.clipboard().setImage(qimg)
                        success = True
                except Exception:
                    success = False

            if not success:
                pixmap = self.webView.grab()
                if not pixmap.isNull():
                    QGuiApplication.clipboard().setPixmap(pixmap)
                    success = True

            if onDone:
                onDone(success)

        self.webView.page().runJavaScript(jsScript, handleResult)

    def showMessage(self, message: str):
        if not self._shellReady:
            self._pendingMessage = message
            self._pendingFigureJson = None
            return
        self._runShowMessage(message)

    def cleanup(self):
        if os.path.exists(self._htmlPath):
            try:
                os.remove(self._htmlPath)
            except OSError:
                pass