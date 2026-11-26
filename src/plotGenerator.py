import colorsys
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.siFormatter import (
    calculateLinthresh, formatAxisTitle, generateSymlogTicks, getSiScale,
    isSentinelLimit, symlogTransform,
)


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
    HIGHLIGHT_SN_COLOR = '#ffe600'

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

    @staticmethod
    def getSerialMatchMask(df: pd.DataFrame | None, serialQuery: str) -> np.ndarray:
        if df is None or df.empty or not serialQuery or 'SerialNumber' not in df.columns:
            return np.zeros(len(df) if df is not None else 0, dtype=bool)

        tokens = [token.strip() for token in re.split(r'[,;]+', serialQuery) if token.strip()]
        if not tokens:
            return np.zeros(len(df), dtype=bool)

        pattern = '|'.join(re.escape(token) for token in tokens)
        series = df['SerialNumber'].astype(str)
        return series.str.contains(pattern, case=False, regex=True, na=False).to_numpy(dtype=bool)

    @staticmethod
    def _formatLimitArray(arr: np.ndarray, isValid: bool) -> np.ndarray:
        n = len(arr)
        if not isValid or n == 0:
            return np.full(n, 'None', dtype=object)

        first = arr[0]
        if np.isfinite(first) and np.all(arr == first):
            return np.full(n, f'{float(first):.4g}', dtype=object)

        uniqueVals = np.unique(arr[np.isfinite(arr)])
        mapping = {float(v): f'{float(v):.4g}' for v in uniqueVals}
        return np.array(
            [mapping.get(float(v), 'None') if np.isfinite(v) else 'None' for v in arr],
            dtype=object,
        )

    def _addSerialHighlightOverlay(
        self,
        fig: go.Figure,
        x,
        y,
        highlightSn: str,
        customData: np.ndarray,
        hoverTemplate: str,
        useWebgl: bool,
    ):
        traceCls = go.Scattergl if useWebgl else go.Scatter
        count = len(x)
        extraKwargs = {} if useWebgl else {'cliponaxis': False}

        # Outer target ring (halo) above background population
        fig.add_trace(
            traceCls(
                x=x,
                y=y,
                mode='markers',
                name='',
                showlegend=False,
                hoverinfo='skip',
                marker=dict(
                    size=20,
                    symbol='circle-open',
                    color=self.HIGHLIGHT_SN_COLOR,
                    line=dict(color=self.HIGHLIGHT_SN_COLOR, width=2.5),
                ),
                **extraKwargs,
            )
        )

        # High-contrast diamond with dark outline on the topmost Z-layer
        fig.add_trace(
            traceCls(
                x=x,
                y=y,
                mode='markers',
                name=f'SN: {highlightSn} ({count:,})',
                marker=dict(
                    size=12,
                    symbol='diamond',
                    color=self.HIGHLIGHT_SN_COLOR,
                    line=dict(color='#111214', width=2.0),
                ),
                customdata=customData,
                hovertemplate=hoverTemplate,
                **extraKwargs,
            )
        )

    def createPlot(
        self,
        df: pd.DataFrame,
        testName: str,
        plotType: str = 'Sequence',
        orderBy: str = 'Date',
        limitsMode: str = 'All',
        valuesInLimits: bool = False,
        logScale: bool = False,
        highlightSn: str = '',
    ) -> go.Figure:

        if df is None or df.empty:
            return self._createEmptyFigure('No data available for selected filters.')

        if 'CX' in df.columns and 'CY' in df.columns:
            return self.createCxCyPlot(
                df,
                testName,
                limitsMode=limitsMode,
                valuesInLimits=valuesInLimits,
                highlightSn=highlightSn,
            )

        normalizedType = plotType.strip().lower()
        if normalizedType == 'sequence':
            return self.createSequencePlot(
                df,
                testName,
                orderBy=orderBy,
                limitsMode=limitsMode,
                valuesInLimits=valuesInLimits,
                logScale=logScale,
                highlightSn=highlightSn,
            )

        if normalizedType in ('capability (histogram)', 'capability', 'histogram'):
            return self.createCapabilityPlot(
                df,
                testName,
                limitsMode=limitsMode,
                valuesInLimits=valuesInLimits,
                logScale=logScale,
                highlightSn=highlightSn,
            )

        if normalizedType == 'boxplot':
            return self.createBoxplot(
                df,
                testName,
                limitsMode=limitsMode,
                valuesInLimits=valuesInLimits,
                logScale=logScale,
                highlightSn=highlightSn,
            )

        raise ValueError(f'Unsupported plot type: {plotType}')

    def createSequencePlot(
        self,
        df: pd.DataFrame,
        testName: str,
        orderBy: str = 'Date',
        limitsMode: str = 'All',
        valuesInLimits: bool = False,
        logScale: bool = False,
        highlightSn: str = '',
    ) -> go.Figure:

        fig = go.Figure()

        rawValues = df['Value'].to_numpy(dtype=float)
        finiteVals = rawValues[np.isfinite(rawValues)]
        dataRef = (
            float(np.median(np.abs(finiteVals[finiteVals != 0])))
            if finiteVals.size > 0 and np.any(finiteVals != 0)
            else None
        )

        lslRef, uslRef = self._resolveScalarLimits(df, limitsMode)
        hasValidLsl = not isSentinelLimit(lslRef, dataRef)
        hasValidUsl = not isSentinelLimit(uslRef, dataRef)

        prefix, scaleFactor = getSiScale(rawValues, lslRef, uslRef)
        unitSuffix = f' {prefix}' if prefix else ''

        scaledValuesAll = rawValues * scaleFactor

        useSymlog = False
        linthresh = 1.0
        if logScale:
            checkVals = [scaledValuesAll[np.isfinite(scaledValuesAll)]]
            if hasValidLsl:
                checkVals.append([lslRef * scaleFactor])
            if hasValidUsl:
                checkVals.append([uslRef * scaleFactor])
            combined = np.concatenate(checkVals) if len(checkVals) > 1 else checkVals[0]
            if np.any(combined <= 0):
                useSymlog = True
                linthresh = calculateLinthresh(combined)

        snMaskAll = self.getSerialMatchMask(df, highlightSn) if highlightSn else np.zeros(len(df), dtype=bool)
        hasSnMatches = bool(np.any(snMaskAll))
        pointOpacity = 0.15 if hasSnMatches else 0.85
        pointSize = 4 if hasSnMatches else 5

        offset = 0
        maxX = 0
        minPlotY = float('inf')
        maxPlotY = float('-inf')
        siteLimitsData: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

        matchedX: list[np.ndarray] = []
        matchedY: list[np.ndarray] = []
        matchedCustomData: list[np.ndarray] = []

        siteGroups = df.groupby(df['Site'].astype(str), sort=True)

        for idx, (site, siteDfRaw) in enumerate(siteGroups):
            siteDf = siteDfRaw.sort_values(by='TestDate', kind='mergesort')
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

            siteVals = siteDf['Value'].to_numpy(dtype=float) * scaleFactor
            siteLsl = siteDf['LSL'].to_numpy(dtype=float) * scaleFactor
            siteUsl = siteDf['USL'].to_numpy(dtype=float) * scaleFactor

            yPlot = symlogTransform(siteVals, linthresh) if useSymlog else siteVals
            finiteY = yPlot[np.isfinite(yPlot)]
            if finiteY.size > 0:
                minPlotY = min(minPlotY, float(np.min(finiteY)))
                maxPlotY = max(maxPlotY, float(np.max(finiteY)))

            customLsl = self._formatLimitArray(siteLsl, hasValidLsl)
            customUsl = self._formatLimitArray(siteUsl, hasValidUsl)

            customData = np.column_stack((
                siteDf['SerialNumber'].astype(str).to_numpy(),
                siteDf['TestDate'].astype(str).to_numpy(),
                customLsl,
                customUsl,
                siteVals,
            ))

            fig.add_trace(
                go.Scattergl(
                    x=xVals,
                    y=yPlot,
                    mode='markers',
                    name=f'Site {site} ({n:,})',
                    marker=dict(size=pointSize, color=color, opacity=pointOpacity),
                    customdata=customData,
                    hovertemplate=(
                        f'<b>Site {site}</b><br>'
                        'Sample: %{x}<br>'
                        f'Value: %{{customdata[4]:.6g}}{unitSuffix}<br>'
                        'SN: %{customdata[0]}<br>'
                        'Date: %{customdata[1]}<br>'
                        f'Limits: [%{{customdata[2]}}{unitSuffix}, %{{customdata[3]}}{unitSuffix}]'
                        '<extra></extra>'
                    ),
                )
            )

            if hasSnMatches:
                siteSnMask = self.getSerialMatchMask(siteDf, highlightSn)
                if np.any(siteSnMask):
                    matchedCount = int(np.sum(siteSnMask))
                    matchedX.append(xVals[siteSnMask])
                    matchedY.append(yPlot[siteSnMask])
                    siteCol = np.full((matchedCount, 1), site, dtype=object)
                    matchedCustomData.append(np.hstack((customData[siteSnMask], siteCol)))

            siteLimitsData.append((xVals, siteLsl, siteUsl))

        if limitsMode == 'All':
            for idx, (xVals, siteLsl, siteUsl) in enumerate(siteLimitsData):
                lslPlot = symlogTransform(siteLsl, linthresh) if useSymlog else siteLsl
                uslPlot = symlogTransform(siteUsl, linthresh) if useSymlog else siteUsl

                if hasValidLsl:
                    fig.add_trace(
                        go.Scattergl(
                            x=xVals,
                            y=lslPlot,
                            mode='lines',
                            name='LSL',
                            legendgroup='LSL',
                            showlegend=(idx == 0),
                            line=dict(color=self.LSL_COLOR, width=1.6, dash='dashdot'),
                            customdata=siteLsl,
                            hovertemplate=f'LSL: %{{customdata:.6g}}{unitSuffix}<extra></extra>',
                        )
                    )
                if hasValidUsl:
                    fig.add_trace(
                        go.Scattergl(
                            x=xVals,
                            y=uslPlot,
                            mode='lines',
                            name='USL',
                            legendgroup='USL',
                            showlegend=(idx == 0),
                            line=dict(color=self.USL_COLOR, width=1.6, dash='dashdot'),
                            customdata=siteUsl,
                            hovertemplate=f'USL: %{{customdata:.6g}}{unitSuffix}<extra></extra>',
                        )
                    )

        if matchedX:
            allMatchedX = np.concatenate(matchedX)
            allMatchedY = np.concatenate(matchedY)
            self._addSerialHighlightOverlay(
                fig=fig,
                x=allMatchedX,
                y=allMatchedY,
                highlightSn=highlightSn,
                customData=np.vstack(matchedCustomData),
                hoverTemplate=(
                    '<b>SN: %{customdata[0]}</b><br>'
                    'Site: %{customdata[5]}<br>'
                    'Sample: %{x}<br>'
                    f'Value: %{{customdata[4]:.6g}}{unitSuffix}<br>'
                    'Date: %{customdata[1]}<br>'
                    f'Limits: [%{{customdata[2]}}{unitSuffix}, %{{customdata[3]}}{unitSuffix}]'
                    '<extra></extra>'
                ),
                useWebgl=True,
            )

        lslScaled = lslRef * scaleFactor
        uslScaled = uslRef * scaleFactor
        lslLine = symlogTransform(lslScaled, linthresh) if useSymlog else lslScaled
        uslLine = symlogTransform(uslScaled, linthresh) if useSymlog else uslScaled

        if limitsMode != 'All':
            if hasValidLsl:
                fig.add_hline(
                    y=lslLine,
                    line_dash='dash',
                    line_color=self.LSL_COLOR,
                    line_width=1.8,
                    annotation_text=f'LSL ({lslScaled:.4g})',
                    annotation_position='bottom right',
                    annotation_font_color=self.LSL_COLOR,
                )
            if hasValidUsl:
                fig.add_hline(
                    y=uslLine,
                    line_dash='dash',
                    line_color=self.USL_COLOR,
                    line_width=1.8,
                    annotation_text=f'USL ({uslScaled:.4g})',
                    annotation_position='top right',
                    annotation_font_color=self.USL_COLOR,
                )

        self._applyCommonLayout(
            fig,
            title=testName,
            xTitle='Samples sorted by date' if orderBy == 'Date' else 'Samples grouped by site',
            yTitle=formatAxisTitle('Measured Value', prefix) + (' (Symlog)' if useSymlog else ''),
            logScale=(logScale and not useSymlog),
        )

        fig.update_xaxes(range=[-max(1, maxX * 0.01), maxX + max(1, maxX * 0.01)])

        if useSymlog and np.isfinite(minPlotY):
            minValReal = float(np.nanmin(scaledValuesAll))
            maxValReal = float(np.nanmax(scaledValuesAll))
            if hasValidLsl:
                minValReal = min(minValReal, lslScaled)
            if hasValidUsl:
                maxValReal = max(maxValReal, uslScaled)

            tickVals, tickText = generateSymlogTicks(minValReal, maxValReal, linthresh)
            fig.update_layout(
                yaxis=dict(
                    type='linear',
                    tickmode='array',
                    tickvals=tickVals,
                    ticktext=tickText,
                    zeroline=True,
                    zerolinecolor='#5a5d64',
                    zerolinewidth=1.5,
                )
            )

        if valuesInLimits and (hasValidLsl or hasValidUsl):
            lowBound = lslLine if hasValidLsl else minPlotY
            highBound = uslLine if hasValidUsl else maxPlotY
            self._applyAxisLimitsPadding(
                fig,
                axis='y',
                low=lowBound,
                high=highBound,
                logScale=(logScale and not useSymlog),
            )

        return fig

    def createCapabilityPlot(
        self,
        df: pd.DataFrame,
        testName: str,
        limitsMode: str = 'Newest',
        valuesInLimits: bool = False,
        logScale: bool = False,
        highlightSn: str = '',
    ) -> go.Figure:

        rawVals = df['Value'].to_numpy(dtype=float)
        finiteMask = np.isfinite(rawVals)
        validDf = df[finiteMask]
        values = rawVals[finiteMask]
        if len(values) == 0:
            return self._createEmptyFigure('No numeric values available.')

        lslRaw, uslRaw = self._resolveScalarLimits(df, limitsMode)
        dataRef = float(np.median(np.abs(values[values != 0]))) if np.any(values != 0) else None

        hasValidLsl = not isSentinelLimit(lslRaw, dataRef)
        hasValidUsl = not isSentinelLimit(uslRaw, dataRef)

        prefix, scaleFactor = getSiScale(values, lslRaw, uslRaw)
        unitSuffix = f' {prefix}' if prefix else ''

        scaledAll = values * scaleFactor
        lslVal = lslRaw * scaleFactor if hasValidLsl else None
        uslVal = uslRaw * scaleFactor if hasValidUsl else None

        inLimitsMask = np.ones(len(scaledAll), dtype=bool)
        if valuesInLimits:
            if hasValidLsl and hasValidUsl:
                inLimitsMask = (scaledAll >= lslVal) & (scaledAll <= uslVal)
            elif hasValidLsl:
                inLimitsMask = scaledAll >= lslVal
            elif hasValidUsl:
                inLimitsMask = scaledAll <= uslVal

            if not np.any(inLimitsMask):
                inLimitsMask = np.ones(len(scaledAll), dtype=bool)

        plotDf = validDf[inLimitsMask]
        plotValues = scaledAll[inLimitsMask]

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

        xMin = float(np.min(plotValues))
        xMax = float(np.max(plotValues))
        if not valuesInLimits:
            if hasValidLsl:
                xMin = min(xMin, lslVal)
            if hasValidUsl:
                xMax = max(xMax, uslVal)

        xGrid = np.linspace(xMin, xMax, 300)

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
                    if hasValidLsl:
                        siteScaled = siteScaled[siteScaled >= lslVal]
                    if hasValidUsl:
                        siteScaled = siteScaled[siteScaled <= uslVal]

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

        if highlightSn:
            snMask = self.getSerialMatchMask(plotDf, highlightSn)
            if np.any(snMask):
                matchedDf = plotDf[snMask]
                matchedVals = plotValues[snMask]

                peakY = float(1.0 / (stdOverall * np.sqrt(2.0 * np.pi))) if stdOverall > 0 else 0.0
                try:
                    if np.ptp(plotValues) > 0:
                        nbins = max(1, int(np.ceil(np.ptp(plotValues) / binSize))) if binSize else 10
                        histDens, _ = np.histogram(plotValues, bins=nbins, density=True)
                        if histDens.size > 0 and np.all(np.isfinite(histDens)):
                            peakY = max(peakY, float(np.max(histDens)))
                except ValueError:
                    pass

                if peakY > 0.0:
                    stemX: list[float | None] = []
                    stemY: list[float | None] = []
                    for val in matchedVals:
                        stemX.extend([float(val), float(val), None])
                        stemY.extend([0.0, peakY * 1.05, None])
                    fig.add_trace(
                        go.Scatter(
                            x=stemX,
                            y=stemY,
                            mode='lines',
                            name='',
                            showlegend=False,
                            hoverinfo='skip',
                            line=dict(color=self.HIGHLIGHT_SN_COLOR, width=1.8, dash='dot'),
                            opacity=0.85,
                        )
                    )

                customData = np.column_stack((
                    matchedDf['SerialNumber'].astype(str).to_numpy(),
                    matchedDf['TestDate'].astype(str).to_numpy(),
                    matchedDf['Site'].astype(str).to_numpy(),
                ))
                self._addSerialHighlightOverlay(
                    fig=fig,
                    x=matchedVals,
                    y=np.zeros(len(matchedVals)),
                    highlightSn=highlightSn,
                    customData=customData,
                    hoverTemplate=(
                        '<b>SN: %{customdata[0]}</b><br>'
                        'Site: %{customdata[2]}<br>'
                        f'Value: %{{x:.6g}}{unitSuffix}<br>'
                        'Date: %{customdata[1]}'
                        '<extra></extra>'
                    ),
                    useWebgl=False,
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
        if hasValidLsl:
            fig.add_vline(
                x=lslVal,
                line_dash='dash',
                line_color=self.LSL_COLOR,
                line_width=2,
                annotation_text='LSL',
                annotation_position='top left',
                annotation_font_color=self.LSL_COLOR,
            )
        if hasValidUsl:
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

        if valuesInLimits and (hasValidLsl or hasValidUsl):
            lowBound = lslVal if hasValidLsl else float(np.nanmin(plotValues))
            highBound = uslVal if hasValidUsl else float(np.nanmax(plotValues))
            self._applyAxisLimitsPadding(fig, axis='x', low=lowBound, high=highBound, logScale=False)

        return fig

    def createBoxplot(
        self,
        df: pd.DataFrame,
        testName: str,
        limitsMode: str = 'Newest',
        valuesInLimits: bool = False,
        logScale: bool = False,
        highlightSn: str = '',
    ) -> go.Figure:

        fig = go.Figure()

        rawValues = df['Value'].to_numpy(dtype=float)
        finiteVals = rawValues[np.isfinite(rawValues)]
        dataRef = (
            float(np.median(np.abs(finiteVals[finiteVals != 0])))
            if finiteVals.size > 0 and np.any(finiteVals != 0)
            else None
        )

        lslRaw, uslRaw = self._resolveScalarLimits(df, limitsMode)
        hasValidLsl = not isSentinelLimit(lslRaw, dataRef)
        hasValidUsl = not isSentinelLimit(uslRaw, dataRef)

        prefix, scaleFactor = getSiScale(rawValues, lslRaw, uslRaw)
        unitSuffix = f' {prefix}' if prefix else ''

        scaledValuesAll = rawValues * scaleFactor
        useSymlog = False
        linthresh = 1.0
        if logScale:
            checkVals = [scaledValuesAll[np.isfinite(scaledValuesAll)]]
            if hasValidLsl:
                checkVals.append([lslRaw * scaleFactor])
            if hasValidUsl:
                checkVals.append([uslRaw * scaleFactor])
            combined = np.concatenate(checkVals) if len(checkVals) > 1 else checkVals[0]
            if np.any(combined <= 0):
                useSymlog = True
                linthresh = calculateLinthresh(combined)

        lslScaled = lslRaw * scaleFactor
        uslScaled = uslRaw * scaleFactor
        lslLine = symlogTransform(lslScaled, linthresh) if useSymlog else lslScaled
        uslLine = symlogTransform(uslScaled, linthresh) if useSymlog else uslScaled

        hasSnMatches = bool(highlightSn) and bool(np.any(self.getSerialMatchMask(df, highlightSn)))
        matchedBoxX: list[str] = []
        matchedBoxY: list[float] = []
        matchedBoxCustom: list[np.ndarray] = []

        siteGroups = df.groupby(df['Site'].astype(str), sort=True)
        for idx, (site, siteDf) in enumerate(siteGroups):
            color = self._getSiteColor(idx)
            siteLabel = f'Site {site} ({len(siteDf):,})'
            siteVals = siteDf['Value'].to_numpy(dtype=float) * scaleFactor
            yPlot = symlogTransform(siteVals, linthresh) if useSymlog else siteVals

            fig.add_trace(
                go.Box(
                    y=yPlot,
                    name=siteLabel,
                    marker_color=color,
                    opacity=0.45 if hasSnMatches else 1.0,
                    boxmean='sd',
                    boxpoints='outliers',
                )
            )

            if hasSnMatches:
                siteSnMask = self.getSerialMatchMask(siteDf, highlightSn)
                if np.any(siteSnMask):
                    matchedSiteDf = siteDf[siteSnMask]
                    mVals = siteVals[siteSnMask]
                    mYPlot = yPlot[siteSnMask]
                    mCount = len(matchedSiteDf)
                    matchedBoxX.extend([siteLabel] * mCount)
                    matchedBoxY.extend(mYPlot.tolist())
                    matchedBoxCustom.append(np.column_stack((
                        matchedSiteDf['SerialNumber'].astype(str).to_numpy(),
                        matchedSiteDf['TestDate'].astype(str).to_numpy(),
                        [f'{lslScaled:.4g}' if hasValidLsl else 'None'] * mCount,
                        [f'{uslScaled:.4g}' if hasValidUsl else 'None'] * mCount,
                        mVals,
                        [site] * mCount,
                    )))

        if matchedBoxX:
            self._addSerialHighlightOverlay(
                fig=fig,
                x=matchedBoxX,
                y=matchedBoxY,
                highlightSn=highlightSn,
                customData=np.vstack(matchedBoxCustom),
                hoverTemplate=(
                    '<b>SN: %{customdata[0]}</b><br>'
                    'Site: %{customdata[5]}<br>'
                    f'Value: %{{customdata[4]:.6g}}{unitSuffix}<br>'
                    'Date: %{customdata[1]}<br>'
                    f'Limits: [%{{customdata[2]}}{unitSuffix}, %{{customdata[3]}}{unitSuffix}]'
                    '<extra></extra>'
                ),
                useWebgl=False,
            )

        if hasValidLsl:
            fig.add_hline(
                y=lslLine,
                line_dash='dash',
                line_color=self.LSL_COLOR,
                line_width=1.8,
                annotation_text=f'LSL ({lslScaled:.4g})',
                annotation_position='bottom right',
                annotation_font_color=self.LSL_COLOR,
            )
        if hasValidUsl:
            fig.add_hline(
                y=uslLine,
                line_dash='dash',
                line_color=self.USL_COLOR,
                line_width=1.8,
                annotation_text=f'USL ({uslScaled:.4g})',
                annotation_position='top right',
                annotation_font_color=self.USL_COLOR,
            )

        self._applyCommonLayout(
            fig,
            title=f'{testName} — Site Comparison',
            xTitle='Test Site',
            yTitle=formatAxisTitle('Measured Value', prefix) + (' (Symlog)' if useSymlog else ''),
            logScale=(logScale and not useSymlog),
        )

        if useSymlog:
            minValReal = float(np.nanmin(scaledValuesAll))
            maxValReal = float(np.nanmax(scaledValuesAll))
            if hasValidLsl:
                minValReal = min(minValReal, lslScaled)
            if hasValidUsl:
                maxValReal = max(maxValReal, uslScaled)

            tickVals, tickText = generateSymlogTicks(minValReal, maxValReal, linthresh)
            fig.update_layout(
                yaxis=dict(
                    type='linear',
                    tickmode='array',
                    tickvals=tickVals,
                    ticktext=tickText,
                    zeroline=True,
                    zerolinecolor='#5a5d64',
                    zerolinewidth=1.5,
                )
            )

        if valuesInLimits and (hasValidLsl or hasValidUsl):
            lowBound = lslLine if hasValidLsl else float(np.nanmin(scaledValuesAll))
            highBound = uslLine if hasValidUsl else float(np.nanmax(scaledValuesAll))
            self._applyAxisLimitsPadding(
                fig,
                axis='y',
                low=lowBound,
                high=highBound,
                logScale=(logScale and not useSymlog),
            )

        return fig

    def createCxCyPlot(
        self,
        df: pd.DataFrame,
        testName: str,
        valuesInLimits: bool = False,
        limitsMode: str = 'All',
        highlightSn: str = '',
    ) -> go.Figure:

        fig = go.Figure()

        snMaskAll = self.getSerialMatchMask(df, highlightSn) if highlightSn else np.zeros(len(df), dtype=bool)
        hasSnMatches = bool(np.any(snMaskAll))
        pointOpacity = 0.15 if hasSnMatches else 0.85
        pointSize = 5 if hasSnMatches else 6

        siteGroups = df.groupby(df['Site'].astype(str), sort=True)
        for idx, (site, siteDf) in enumerate(siteGroups):
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
                    marker=dict(size=pointSize, color=color, opacity=pointOpacity),
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

        sortedByDateDf = df.sort_values(by='TestDate', kind='mergesort')
        boundariesToDraw: list[tuple[tuple[tuple[float, float], ...], str]] = []

        if limitsMode == 'Newest':
            lastValid = sortedByDateDf['Boundary'].dropna().iloc[-1] if not sortedByDateDf['Boundary'].dropna().empty else None
            if lastValid:
                boundariesToDraw.append((tuple(tuple(pt) for pt in lastValid), 'Active Bin (Newest)'))
        elif limitsMode == 'Oldest':
            firstValid = sortedByDateDf['Boundary'].dropna().iloc[0] if not sortedByDateDf['Boundary'].dropna().empty else None
            if firstValid:
                boundariesToDraw.append((tuple(tuple(pt) for pt in firstValid), 'Initial Bin (Oldest)'))
        else:
            seen: set[tuple[tuple[float, float], ...]] = set()
            for boundary in sortedByDateDf['Boundary'].dropna():
                key = tuple(tuple(pt) for pt in boundary)
                if key not in seen:
                    seen.add(key)
                    label = f'Bin Boundary {len(seen)}' if len(seen) > 1 else 'Bin Boundary'
                    boundariesToDraw.append((key, label))

        minX, maxX = float('inf'), float('-inf')
        minY, maxY = float('inf'), float('-inf')

        dashStyles = ['solid', 'dash', 'dot', 'dashdot']

        for idx, (boundary, label) in enumerate(boundariesToDraw):
            bx = [pt[0] for pt in boundary]
            by = [pt[1] for pt in boundary]
            minX, maxX = min(minX, min(bx)), max(maxX, max(bx))
            minY, maxY = min(minY, min(by)), max(maxY, max(by))

            dash = dashStyles[idx % len(dashStyles)]
            color = self.USL_COLOR if idx == 0 else ('#e040fb' if idx == 1 else self.LSL_COLOR)

            fig.add_trace(
                go.Scatter(
                    x=bx,
                    y=by,
                    mode='lines',
                    name=label,
                    line=dict(color=color, width=2.2, dash=dash),
                    hoverinfo='skip',
                )
            )

        if hasSnMatches:
            matchedDf = df[snMaskAll]
            matchedCustom = np.column_stack((
                matchedDf['SerialNumber'].astype(str).to_numpy(),
                matchedDf['TestDate'].astype(str).to_numpy(),
                matchedDf['Site'].astype(str).to_numpy(),
            ))
            self._addSerialHighlightOverlay(
                fig=fig,
                x=matchedDf['CX'].to_numpy(),
                y=matchedDf['CY'].to_numpy(),
                highlightSn=highlightSn,
                customData=matchedCustom,
                hoverTemplate=(
                    '<b>SN: %{customdata[0]}</b><br>'
                    'Site: %{customdata[2]}<br>'
                    'CX: %{x:.5f}<br>'
                    'CY: %{y:.5f}<br>'
                    'Date: %{customdata[1]}'
                    '<extra></extra>'
                ),
                useWebgl=True,
            )

        self._applyCommonLayout(fig, title=testName, xTitle='CX', yTitle='CY', logScale=False)

        if valuesInLimits and boundariesToDraw:
            self._applyAxisLimitsPadding(fig, axis='x', low=minX, high=maxX, logScale=False)
            self._applyAxisLimitsPadding(fig, axis='y', low=minY, high=maxY, logScale=False)

        return fig

    def _applyCommonLayout(self, fig: go.Figure, title: str, xTitle: str, yTitle: str, logScale: bool):
        fig.update_layout(
            separators='. ',
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
                exponentformat='none',
                separatethousands=True,
                automargin=True,
            ),
            yaxis=dict(
                title=dict(text=yTitle, standoff=10),
                gridcolor=self.GRID_COLOR,
                zerolinecolor=self.GRID_COLOR,
                type='log' if logScale else 'linear',
                exponentformat='power' if logScale else 'none',
                separatethousands=True,
                automargin=True,
            ),
        )

    def _applyAxisLimitsPadding(self, fig: go.Figure, axis: str, low: float, high: float, logScale: bool):
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

        # calculate colors from golden angle HSL model
        step = idx - len(self.SITE_PALETTE) + 1
        hue = ((step * 137.508) % 360.0) / 360.0
        lightness = 0.56 + (step % 3) * 0.08
        saturation = 0.75 if step % 2 == 0 else 0.88
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        return f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'