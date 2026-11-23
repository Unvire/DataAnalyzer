import colorsys

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.siFormatter import formatAxisTitle, getSiScale


class PlotlyChartGenerator:
    DELTA_LIMITS_PERCENTAGE = 0.05
    BG_COLOR = '#1e1f22'
    PLOT_BG_COLOR = '#26282e'
    GRID_COLOR = '#35373c'
    TEXT_COLOR = '#dfe1e5'
    MUTED_TEXT_COLOR = '#9da0a8'
    LSL_COLOR = '#ef5350'
    USL_COLOR = '#ffa726'
    MEAN_COLOR = '#66bb6a'

    SITE_PALETTE = [
        '#4c8dff',
        '#26c6da',
        '#ab47bc',
        '#ffca28',
        '#ec407a',
        '#66bb6a',
        '#ff7043',
        '#8d6e63',
    ]

    def createPlot(self, df:pd.DataFrame, testName:str, plotType:str='Sequence', orderBy: str = 'Date', limitsMode: str = 'All',
            valuesInLimits: bool = False, logScale: bool = False) -> go.Figure:

        if df is None or df.empty:
            return self._createEmptyFigure('No data available for selected filters.')

        if 'CX' in df.columns and 'CY' in df.columns:
            return self.createCxCyPlot(df, testName, valuesInLimits=valuesInLimits)

        if plotType == 'Capability (Histogram)':
            return self.createCapabilityPlot(df, testName, limitsMode=limitsMode, valuesInLimits=valuesInLimits, logScale=logScale)

        if plotType == 'Boxplot':
            return self.createBoxplot(df, testName, limitsMode=limitsMode, valuesInLimits=valuesInLimits, logScale=logScale)

        return self.createSequencePlot(df, testName, orderBy=orderBy, limitsMode=limitsMode, valuesInLimits=valuesInLimits, logScale=logScale)


    def createSequencePlot(self, df:pd.DataFrame, testName:str, orderBy:str='Date', limitsMode:str='All', valuesInLimits:bool=False, 
            logScale:bool=False) -> go.Figure:

        fig = go.Figure()
        sortedSites = sorted(df['Site'].astype(str).unique().tolist())

        lslRef, uslRef = self._resolveScalarLimits(df, limitsMode)
        prefix, scaleFactor = getSiScale(df['Value'].to_numpy(dtype=float), lslRef, uslRef)
        unitSuffix = f' {prefix}' if prefix else ''

        offset = 0
        maxX = 0
        allLsl: list[float] = []
        allUsl: list[float] = []

        for idx, site in enumerate(sortedSites):
            siteDf = df[df['Site'].astype(str) == site].sort_values(by='TestDate', kind='mergesort')
            n = len(siteDf)
            if n == 0:
                continue

            if orderBy == 'Sites':
                xVals = np.arange(offset, offset + n)
                offset += n
            else:
                xVals = np.arange(0, n)

            maxX = max(maxX, int(xVals[-1]) + 1)
            color = self._getSiteColor(idx)

            scaledValues = siteDf['Value'].to_numpy(dtype=float) * scaleFactor
            scaledLsl = siteDf['LSL'].to_numpy(dtype=float) * scaleFactor
            scaledUsl = siteDf['USL'].to_numpy(dtype=float) * scaleFactor

            allLsl.extend(scaledLsl.tolist())
            allUsl.extend(scaledUsl.tolist())

            customData = np.column_stack((
                siteDf['SerialNumber'].astype(str).to_numpy(),
                siteDf['TestDate'].astype(str).to_numpy(),
                scaledLsl,
                scaledUsl,
            ))

            fig.add_trace(
                go.Scattergl(
                    x=xVals,
                    y=scaledValues,
                    mode='markers',
                    name=f'Site {site} ({n:,})',
                    marker=dict(size=5, color=color, opacity=0.85),
                    customdata=customData,
                    hovertemplate=(
                        f'<b>Site {site}</b><br>'
                        'Sample: %{x}<br>'
                        f'Value: %{{y:.6g}}{unitSuffix}<br>'
                        'SN: %{customdata[0]}<br>'
                        'Date: %{customdata[1]}<br>'
                        f'Limits: [%{{customdata[2]:.4g}}{unitSuffix}, %{{customdata[3]:.4g}}{unitSuffix}]'
                        '<extra></extra>'
                    ),
                )
            )

            if limitsMode == 'All':
                fig.add_trace(
                    go.Scattergl(
                        x=xVals,
                        y=scaledLsl,
                        mode='lines',
                        name='LSL',
                        legendgroup='LSL',
                        showlegend=(idx == 0),
                        line=dict(color=self.LSL_COLOR, width=1.6, dash='dashdot'),
                        hovertemplate=f'LSL: %{{y:.6g}}{unitSuffix}<extra></extra>',
                    )
                )
                fig.add_trace(
                    go.Scattergl(
                        x=xVals,
                        y=scaledUsl,
                        mode='lines',
                        name='USL',
                        legendgroup='USL',
                        showlegend=(idx == 0),
                        line=dict(color=self.USL_COLOR, width=1.6, dash='dashdot'),
                        hovertemplate=f'USL: %{{y:.6g}}{unitSuffix}<extra></extra>',
                    )
                )

        if limitsMode == 'All' and allLsl:
            yMinLim = float(np.nanmin(allLsl))
            yMaxLim = float(np.nanmax(allUsl))
        else:
            lslScaled = lslRef * scaleFactor
            uslScaled = uslRef * scaleFactor
            self._addHorizontalLimitLines(fig, lslScaled, uslScaled)
            yMinLim, yMaxLim = lslScaled, uslScaled

        self._applyCommonLayout(
            fig,
            title=testName,
            xTitle='Samples sorted by date' if orderBy == 'Date' else 'Samples grouped by site',
            yTitle=formatAxisTitle('Measured Value', prefix),
            logScale=logScale,
        )

        fig.update_xaxes(range=[-max(1, maxX * 0.01), maxX + max(1, maxX * 0.01)])
        if valuesInLimits:
            self._applyAxisLimitsPadding(fig, axis='y', low=yMinLim, high=yMaxLim, logScale=logScale)

        return fig


    def createCapabilityPlot(self, df:pd.DataFrame, testName:str, limitsMode:str='Newest', valuesInLimits:bool=False,
            logScale:bool=False) -> go.Figure:

        values = df['Value'].dropna().to_numpy(dtype=float)
        if len(values) == 0:
            return self._createEmptyFigure('No numeric values available.')

        lslRaw, uslRaw = self._resolveScalarLimits(df, limitsMode)
        prefix, scaleFactor = getSiScale(values, lslRaw, uslRaw)
        unitSuffix = f' {prefix}' if prefix else ''

        scaledAll = values * scaleFactor
        lslVal = lslRaw * scaleFactor
        uslVal = uslRaw * scaleFactor

        if valuesInLimits:
            plotValues = scaledAll[(scaledAll >= lslVal) & (scaledAll <= uslVal)]
            if len(plotValues) == 0:
                plotValues = scaledAll
        else:
            plotValues = scaledAll

        fig = go.Figure()
        binSize = self._calculateHistogramBinSize(plotValues)

        histKwargs = dict(
            x=plotValues,
            histnorm='probability density',
            name=f'All Sites ({len(plotValues):,})',
            marker=dict(color='#3a4252', opacity=0.6, line=dict(color='#1e1f22', width=1)),
            hovertemplate=f'Range: %{{x}}{unitSuffix}<br>Density: %{{y:.4g}}<extra></extra>',
        )
        if binSize is not None:
            histKwargs['xbins'] = dict(size=binSize)
        else:
            histKwargs['nbinsx'] = 10

        fig.add_trace(go.Histogram(**histKwargs))

        xMin = min(float(np.min(plotValues)), lslVal) if not valuesInLimits else lslVal
        xMax = max(float(np.max(plotValues)), uslVal) if not valuesInLimits else uslVal
        xGrid = np.linspace(xMin, xMax, 300)

        # overall fit
        meanOverall = float(np.mean(plotValues))
        stdOverall = float(np.std(plotValues, ddof=1)) if len(plotValues) > 1 else 0.0

        if stdOverall > 0:
            overallPdf = (1.0 / (stdOverall * np.sqrt(2.0 * np.pi))) * np.exp(
                -0.5 * ((xGrid - meanOverall) / stdOverall) ** 2
            )
            fig.add_trace(
                go.Scatter(
                    x=xGrid,
                    y=overallPdf,
                    mode='lines',
                    name=f'Overall Fit (μ={meanOverall:.4g}, σ={stdOverall:.3g})',
                    line=dict(color='#ffffff', width=2.5, dash='dash'),
                    hovertemplate=f'Overall: %{{x:.6g}}{unitSuffix}<br>PDF: %{{y:.4g}}<extra></extra>',
                )
            )

        sortedSites = sorted(df['Site'].astype(str).unique().tolist())
        if len(sortedSites) > 1:
            autoHidePerSite = len(sortedSites) > 8

            for idx, site in enumerate(sortedSites):
                siteRaw = df[df['Site'].astype(str) == site]['Value'].dropna().to_numpy(dtype=float)
                siteScaled = siteRaw * scaleFactor
                if valuesInLimits:
                    siteScaled = siteScaled[(siteScaled >= lslVal) & (siteScaled <= uslVal)]

                if len(siteScaled) < 3:
                    continue

                mSite = float(np.mean(siteScaled))
                sSite = float(np.std(siteScaled, ddof=1))
                if sSite <= 0:
                    continue

                sitePdf = (1.0 / (sSite * np.sqrt(2.0 * np.pi))) * np.exp(-0.5 * ((xGrid - mSite) / sSite) ** 2)
                siteColor = self._getSiteColor(idx)

                fig.add_trace(
                    go.Scatter(
                        x=xGrid,
                        y=sitePdf,
                        mode='lines',
                        name=f'Site {site} (μ={mSite:.4g}, σ={sSite:.3g})',
                        visible=True if not autoHidePerSite else 'legendonly',
                        line=dict(color=siteColor, width=1.8),
                        hovertemplate=f'Site {site}: %{{x:.6g}}{unitSuffix}<br>PDF: %{{y:.4g}}<extra></extra>',
                    )
                )

        fig.add_vline(
            x=meanOverall,
            line_dash='dot',
            line_color=self.MEAN_COLOR,
            line_width=2,
            annotation_text='Mean',
            annotation_position='top',
            annotation_font_color=self.MEAN_COLOR,
        )
        fig.add_vline(
            x=lslVal,
            line_dash='dash',
            line_color=self.LSL_COLOR,
            line_width=2,
            annotation_text='LSL',
            annotation_position='top left',
            annotation_font_color=self.LSL_COLOR,
        )
        fig.add_vline(
            x=uslVal,
            line_dash='dash',
            line_color=self.USL_COLOR,
            line_width=2,
            annotation_text='USL',
            annotation_position='top right',
            annotation_font_color=self.USL_COLOR,
        )

        self._applyCommonLayout(
            fig,
            title=f'{testName} — Capability',
            xTitle=formatAxisTitle('Measured Value', prefix),
            yTitle='Probability Density',
            logScale=logScale,
        )

        if valuesInLimits:
            self._applyAxisLimitsPadding(fig, axis='x', low=lslVal, high=uslVal, logScale=False)

        return fig


    def createBoxplot(self, df:pd.DataFrame, testName:str, limitsMode:str='Newest', valuesInLimits:bool=False,
            logScale:bool=False) -> go.Figure:
        
        fig = go.Figure()
        sortedSites = sorted(df['Site'].astype(str).unique().tolist())

        lslRaw, uslRaw = self._resolveScalarLimits(df, limitsMode)
        prefix, scaleFactor = getSiScale(df['Value'].to_numpy(dtype=float), lslRaw, uslRaw)

        for idx, site in enumerate(sortedSites):
            siteDf = df[df['Site'].astype(str) == site]
            color = self._getSiteColor(idx)
            fig.add_trace(
                go.Box(
                    y=siteDf['Value'].to_numpy(dtype=float) * scaleFactor,
                    name=f'Site {site} ({len(siteDf):,})',
                    marker_color=color,
                    boxmean='sd',
                    boxpoints='outliers',
                )
            )

        lslVal = lslRaw * scaleFactor
        uslVal = uslRaw * scaleFactor
        self._addHorizontalLimitLines(fig, lslVal, uslVal)

        self._applyCommonLayout(
            fig,
            title=f'{testName} — Site Comparison',
            xTitle='Test Site',
            yTitle=formatAxisTitle('Measured Value', prefix),
            logScale=logScale,
        )

        if valuesInLimits:
            self._applyAxisLimitsPadding(fig, axis='y', low=lslVal, high=uslVal, logScale=logScale)

        return fig


    def createCxCyPlot(self, df: pd.DataFrame, testName: str, valuesInLimits: bool = False) -> go.Figure:
        fig = go.Figure()
        sortedSites = sorted(df['Site'].astype(str).unique().tolist())

        for idx, site in enumerate(sortedSites):
            siteDf = df[df['Site'].astype(str) == site]
            color = self._getSiteColor(idx)
            customData = np.column_stack((
                siteDf['SerialNumber'].astype(str).to_numpy(),
                siteDf['TestDate'].astype(str).to_numpy(),
            ))

            fig.add_trace(
                go.Scattergl(
                    x=siteDf['CX'].to_numpy(),
                    y=siteDf['CY'].to_numpy(),
                    mode='markers',
                    name=f'Site {site} ({len(siteDf):,})',
                    marker=dict(size=6, color=color, opacity=0.85),
                    customdata=customData,
                    hovertemplate=(
                        f'<b>Site {site}</b><br>'
                        'CX: %{x:.5f}<br>'
                        'CY: %{y:.5f}<br>'
                        'SN: %{customdata[0]}<br>'
                        'Date: %{customdata[1]}'
                        '<extra></extra>'
                    ),
                )
            )

        uniqueBoundaries: list[tuple[tuple[float, float], ...]] = []
        seen: set[tuple[tuple[float, float], ...]] = set()
        for boundary in df['Boundary'].dropna():
            key = tuple(tuple(pt) for pt in boundary)
            if key not in seen:
                seen.add(key)
                uniqueBoundaries.append(key)

        minX, maxX = float('inf'), float('-inf')
        minY, maxY = float('inf'), float('-inf')

        for idx, boundary in enumerate(uniqueBoundaries, start=1):
            bx = [pt[0] for pt in boundary]
            by = [pt[1] for pt in boundary]
            minX, maxX = min(minX, min(bx)), max(maxX, max(bx))
            minY, maxY = min(minY, min(by)), max(maxY, max(by))

            fig.add_trace(
                go.Scatter(
                    x=bx,
                    y=by,
                    mode='lines',
                    name=f'Bin Boundary {idx}',
                    line=dict(color=self.USL_COLOR if idx % 2 else self.LSL_COLOR, width=2),
                    hoverinfo='skip',
                )
            )

        self._applyCommonLayout(fig, title=testName, xTitle='CX', yTitle='CY', logScale=False)

        if valuesInLimits and uniqueBoundaries:
            self._applyAxisLimitsPadding(fig, axis='x', low=minX, high=maxX, logScale=False)
            self._applyAxisLimitsPadding(fig, axis='y', low=minY, high=maxY, logScale=False)

        return fig


    def _applyCommonLayout(self, fig:go.Figure, title:str, xTitle:str, yTitle:str, logScale:bool):
        fig.update_layout(
            title=dict(text=title, x=0.02, y=0.97, font=dict(size=15, color=self.TEXT_COLOR)),
            paper_bgcolor=self.BG_COLOR,
            plot_bgcolor=self.PLOT_BG_COLOR,
            font=dict(family='Segoe UI, Arial, sans-serif', size=12, color=self.TEXT_COLOR),
            margin=dict(l=65, r=25, t=80, b=55),
            hovermode='closest',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1.0,
                bgcolor='rgba(38, 40, 46, 0.75)',
                bordercolor=self.GRID_COLOR,
                borderwidth=1,
            ),
            xaxis=dict(
                title=dict(text=xTitle, standoff=10),
                gridcolor=self.GRID_COLOR,
                zerolinecolor=self.GRID_COLOR,
                exponentformat='e',
                automargin=True,
            ),
            yaxis=dict(
                title=dict(text=yTitle, standoff=10),
                gridcolor=self.GRID_COLOR,
                zerolinecolor=self.GRID_COLOR,
                type='log' if logScale else 'linear',
                exponentformat='e',
                automargin=True,
            ),
        )


    def _addHorizontalLimitLines(self, fig:go.Figure, lslVal:float, uslVal:float):
        fig.add_hline(
            y=lslVal,
            line_dash='dash',
            line_color=self.LSL_COLOR,
            line_width=1.8,
            annotation_text='LSL',
            annotation_position='bottom right',
            annotation_font_color=self.LSL_COLOR,
        )
        fig.add_hline(
            y=uslVal,
            line_dash='dash',
            line_color=self.USL_COLOR,
            line_width=1.8,
            annotation_text='USL',
            annotation_position='top right',
            annotation_font_color=self.USL_COLOR,
        )

    def _applyAxisLimitsPadding(self, fig:go.Figure, axis:str, low:float, high:float, logScale:bool):
        if not (np.isfinite(low) and np.isfinite(high)):
            return
        
        span = abs(high - low)
        delta = span * self.DELTA_LIMITS_PERCENTAGE if span > 0 else max(abs(low) * 0.05, 1e-6)
        minBound = low - delta
        maxBound = high + delta

        if logScale:
            if maxBound <= 0:
                return
            minBound = max(minBound, maxBound * 1e-6) if minBound <= 0 else minBound
            axisRange = [np.log10(minBound), np.log10(maxBound)]
        else:
            axisRange = [minBound, maxBound]

        if axis == 'x':
            fig.update_xaxes(range=axisRange)
        else:
            fig.update_yaxes(range=axisRange)

    @staticmethod
    def _resolveScalarLimits(df: pd.DataFrame, limitsMode: str) -> tuple[float, float]:
        sortedDf = df.sort_values(by='TestDate', kind='mergesort')
        row = sortedDf.iloc[0] if limitsMode == 'Oldest' else sortedDf.iloc[-1]
        return float(row['LSL']), float(row['USL'])

    @staticmethod
    def _calculateHistogramBinSize(data: np.ndarray) -> float | None:
        n = len(data)
        if n < 2:
            return None

        dataRange = float(np.max(data) - np.min(data))
        if dataRange <= 0:
            return None

        q75, q25 = np.percentile(data, [75, 25])
        iqr = float(q75 - q25)

        if iqr > 0:
            fdWidth = 2.0 * iqr / (n ** (1.0 / 3.0))
            binsFd = int(np.ceil(dataRange / fdWidth)) if fdWidth > 0 else 10
        else:
            binsFd = int(np.ceil(2.0 * (n ** (1.0 / 3.0))))

        binsRice = int(np.ceil(2.0 * (n ** (1.0 / 3.0))))
        binsSturges = int(np.ceil(1.0 + np.log2(n)))

        numBins = max(8, min(80, min(binsFd, max(binsRice, binsSturges))))
        return dataRange / numBins

    def _createEmptyFigure(self, message: str) -> go.Figure:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor=self.BG_COLOR,
            plot_bgcolor=self.BG_COLOR,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[
                dict(
                    text=message,
                    xref='paper',
                    yref='paper',
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=14, color=self.MUTED_TEXT_COLOR),
                )
            ],
        )
        return fig

    def _getSiteColor(self, idx: int) -> str:
        if idx < len(self.SITE_PALETTE):
            return self.SITE_PALETTE[idx]

        # calcluate colors from golden angle HSL model
        step = idx - len(self.SITE_PALETTE) + 1
        hue = ((step * 137.508) % 360.0) / 360.0
        lightness = 0.56 + (step % 3) * 0.08 
        saturation = 0.72 if step % 2 == 0 else 0.85
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        return f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'