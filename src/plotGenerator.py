import colorsys
from dataclasses import dataclass
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.siFormatter import (
    calculateLinthresh, formatAxisTitle, generateSymlogTicks,
    getSiScale, isSentinelLimit, symlogTransform,
)


@dataclass
class _ScalarScaleContext:
    prefix: str
    scaleFactor: float
    unitSuffix: str
    scaledValuesAll: np.ndarray
    hasValidLsl: bool
    hasValidUsl: bool
    lslScaled: float | None
    uslScaled: float | None
    lslPlot: float | None
    uslPlot: float | None
    useSymlog: bool
    linthresh: float

    def toPlotY(self, scaledValues:np.ndarray) -> np.ndarray:
        return symlogTransform(scaledValues, self.linthresh) if self.useSymlog else scaledValues

    def yAxisTitle(self, baseTitle:str='Measured Value') -> str:
        title = formatAxisTitle(baseTitle, self.prefix)
        return f'{title} (Symlog)' if self.useSymlog else title


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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @staticmethod
    def getSerialMatchMask(df:pd.DataFrame|None, serialQuery:str) -> np.ndarray:
        if df is None or df.empty or not serialQuery or 'SerialNumber' not in df.columns:
            return np.zeros(len(df) if df is not None else 0, dtype=bool)

        tokens = [token.strip() for token in re.split(r'[,;]+', serialQuery) if token.strip()]
        if not tokens:
            return np.zeros(len(df), dtype=bool)

        pattern = '|'.join(re.escape(token) for token in tokens)
        series = df['SerialNumber'].astype(str)
        return series.str.contains(pattern, case=False, regex=True, na=False).to_numpy(dtype=bool)

    def createPlot(self, df:pd.DataFrame, testName:str, plotType:str='Sequence', orderBy:str='Date', limitsMode:str='All', valuesInLimits:bool=False, 
            logScale:bool=False, highlightSn:str='') -> go.Figure:
        
        if df is None or df.empty:
            return self._createEmptyFigure('No data available for selected filters.')

        if 'CX' in df.columns and 'CY' in df.columns:
            return self.createCxCyPlot(df, testName, limitsMode=limitsMode, valuesInLimits=valuesInLimits, highlightSn=highlightSn)

        normalizedType = plotType.strip().lower()
        if normalizedType == 'sequence':
            return self.createSequencePlot(df, testName, orderBy=orderBy, limitsMode=limitsMode, valuesInLimits=valuesInLimits,
                logScale=logScale, highlightSn=highlightSn)

        if normalizedType in ('capability (histogram)', 'capability', 'histogram'):
            return self.createCapabilityPlot(df, testName, limitsMode=limitsMode, valuesInLimits=valuesInLimits, logScale=logScale,
                highlightSn=highlightSn)

        if normalizedType == 'boxplot':
            return self.createBoxplot(df, testName, limitsMode=limitsMode, valuesInLimits=valuesInLimits, logScale=logScale,
                highlightSn=highlightSn)

        raise ValueError(f'Unsupported plot type: {plotType}')


    # ------------------------------------------------------------------
    # Sequence Plot
    # ------------------------------------------------------------------
    def createSequencePlot(self, df:pd.DataFrame, testName:str, orderBy:str='Date', limitsMode:str='All', valuesInLimits:bool=False,
            logScale:bool=False, highlightSn:str='') -> go.Figure:
        
        fig = go.Figure()
        ctx = self._prepareScalarContext(df, limitsMode=limitsMode, logScale=logScale, allowSymlog=True)

        hasSnMatches = bool(highlightSn) and bool(np.any(self.getSerialMatchMask(df, highlightSn)))
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

        for idx, (site, siteDfRaw) in enumerate(df.groupby(df['Site'].astype(str), sort=True)):
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

            siteVals = siteDf['Value'].to_numpy(dtype=float) * ctx.scaleFactor
            siteLsl = siteDf['LSL'].to_numpy(dtype=float) * ctx.scaleFactor
            siteUsl = siteDf['USL'].to_numpy(dtype=float) * ctx.scaleFactor

            yPlot = ctx.toPlotY(siteVals)
            finiteY = yPlot[np.isfinite(yPlot)]
            if finiteY.size > 0:
                minPlotY = min(minPlotY, float(np.min(finiteY)))
                maxPlotY = max(maxPlotY, float(np.max(finiteY)))

            customData = self._buildScalarCustomData(siteDf, siteVals=siteVals, siteLsl=siteLsl, siteUsl=siteUsl, hasValidLsl=ctx.hasValidLsl,
                hasValidUsl=ctx.hasValidUsl)

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
                        f'Value: %{{customdata[4]:.6g}}{ctx.unitSuffix}<br>'
                        'SN: %{customdata[0]}<br>'
                        'Date: %{customdata[1]}<br>'
                        f'Limits: [%{{customdata[2]}}{ctx.unitSuffix}, %{{customdata[3]}}{ctx.unitSuffix}]'
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
            self._addDynamicSequenceLimitTraces(fig, siteLimitsData, ctx)
        else:
            self._addHorizontalLimitLines(fig, ctx)

        if matchedX:
            self._addSerialHighlightOverlay(
                fig=fig,
                x=np.concatenate(matchedX),
                y=np.concatenate(matchedY),
                highlightSn=highlightSn,
                customData=np.vstack(matchedCustomData),
                hoverTemplate=(
                    '<b>SN: %{customdata[0]}</b><br>'
                    'Site: %{customdata[5]}<br>'
                    'Sample: %{x}<br>'
                    f'Value: %{{customdata[4]:.6g}}{ctx.unitSuffix}<br>'
                    'Date: %{customdata[1]}<br>'
                    f'Limits: [%{{customdata[2]}}{ctx.unitSuffix}, %{{customdata[3]}}{ctx.unitSuffix}]'
                    '<extra></extra>'
                ),
                useWebgl=True,
            )

        xTitle='Samples sorted by date' if orderBy == 'Date' else 'Samples grouped by site'
        self._applyCommonLayout(fig, title=testName, xTitle=xTitle, yTitle=ctx.yAxisTitle(),
            logScale=(logScale and not ctx.useSymlog))
        fig.update_xaxes(range=[-max(1, maxX * 0.01), maxX + max(1, maxX * 0.01)])

        if ctx.useSymlog and np.isfinite(minPlotY):
            self._applySymlogYAxis(fig, ctx)

        if valuesInLimits:
            self._applyScalarLimitsRange(fig, ctx, axis='y', fallbackMin=minPlotY, fallbackMax=maxPlotY,
                logScale=(logScale and not ctx.useSymlog))

        return fig


    # ------------------------------------------------------------------
    # Capability (Histogram + Normal Fits)
    # ------------------------------------------------------------------
    def createCapabilityPlot(self, df:pd.DataFrame, testName:str, limitsMode:str='Newest', valuesInLimits:bool=False,
            logScale:bool=False, highlightSn:str='') -> go.Figure:

        rawVals = df['Value'].to_numpy(dtype=float)
        finiteMask = np.isfinite(rawVals)
        validDf = df[finiteMask]
        if validDf.empty:
            return self._createEmptyFigure('No numeric values available.')

        ctx = self._prepareScalarContext(validDf, limitsMode=limitsMode, logScale=False, allowSymlog=False)
        scaledAll = ctx.scaledValuesAll

        inLimitsMask = self._buildInLimitsMask(scaledAll, ctx) if valuesInLimits else np.ones(len(scaledAll), dtype=bool)
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
            hovertemplate=f'Range: %{{x}}{ctx.unitSuffix}<br>Density: %{{y:.4g}}<extra></extra>',
        )
        if binSize is not None:
            histKwargs['xbins'] = dict(size=binSize)
        else:
            histKwargs['nbinsx'] = 10
        fig.add_trace(go.Histogram(**histKwargs))

        xMin, xMax = float(np.min(plotValues)), float(np.max(plotValues))
        if not valuesInLimits:
            if ctx.hasValidLsl and ctx.lslScaled is not None:
                xMin = min(xMin, ctx.lslScaled)
            if ctx.hasValidUsl and ctx.uslScaled is not None:
                xMax = max(xMax, ctx.uslScaled)
        xGrid = np.linspace(xMin, xMax, 300)

        meanOverall = float(np.mean(plotValues))
        stdOverall = float(np.std(plotValues, ddof=1)) if len(plotValues) > 1 else 0.0

        if stdOverall > 0.0:
            fig.add_trace(
                go.Scatter(
                    x=xGrid,
                    y=self._gaussianPdf(xGrid, meanOverall, stdOverall),
                    mode='lines',
                    name=f'Overall Fit (μ={meanOverall:.4g}, σ={stdOverall:.3g})',
                    line=dict(color='#ffffff', width=2.5, dash='dash'),
                    hovertemplate=f'Overall: %{{x:.6g}}{ctx.unitSuffix}<br>PDF: %{{y:.4g}}<extra></extra>',
                )
            )

        self._addCapabilityPerSiteCurves(fig, validDf, xGrid, ctx, valuesInLimits)

        if highlightSn:
            self._addCapabilitySnOverlay(fig, plotDf, plotValues, highlightSn, stdOverall, binSize, ctx)

        self._addCapabilityReferenceLines(fig, meanOverall, ctx)

        self._applyCommonLayout(fig, title=f'{testName} — Capability', xTitle=formatAxisTitle('Measured Value', ctx.prefix),
            yTitle='Probability Density', logScale=logScale)

        if valuesInLimits:
            self._applyScalarLimitsRange(fig, ctx, axis='x', fallbackMin=float(np.nanmin(plotValues)),
                fallbackMax=float(np.nanmax(plotValues)), logScale=False)

        return fig


    # ------------------------------------------------------------------
    # Boxplot (Per-Site Comparison)
    # ------------------------------------------------------------------
    def createBoxplot(self, df:pd.DataFrame, testName:str, limitsMode:str='Newest', valuesInLimits:bool=False,
            logScale:bool=False, highlightSn:str='') -> go.Figure:

        fig = go.Figure()
        ctx = self._prepareScalarContext(df, limitsMode=limitsMode, logScale=logScale, allowSymlog=True)

        hasSnMatches = bool(highlightSn) and bool(np.any(self.getSerialMatchMask(df, highlightSn)))
        minPlotY = float('inf')
        maxPlotY = float('-inf')

        matchedBoxX: list[str] = []
        matchedBoxY: list[float] = []
        matchedBoxCustom: list[np.ndarray] = []

        lslLabel = f'{ctx.lslScaled:.4g}' if (ctx.hasValidLsl and ctx.lslScaled is not None) else 'None'
        uslLabel = f'{ctx.uslScaled:.4g}' if (ctx.hasValidUsl and ctx.uslScaled is not None) else 'None'

        for idx, (site, siteDf) in enumerate(df.groupby(df['Site'].astype(str), sort=True)):
            color = self._getSiteColor(idx)
            siteLabel = f'Site {site} ({len(siteDf):,})'
            siteVals = siteDf['Value'].to_numpy(dtype=float) * ctx.scaleFactor
            yPlot = ctx.toPlotY(siteVals)

            finiteY = yPlot[np.isfinite(yPlot)]
            if finiteY.size > 0:
                minPlotY = min(minPlotY, float(np.min(finiteY)))
                maxPlotY = max(maxPlotY, float(np.max(finiteY)))

            opacity = 0.45 if hasSnMatches else 1.0
            fig.add_trace(
                go.Box(y=yPlot, name=siteLabel, marker_color=color, opacity=opacity, boxmean='sd', boxpoints='outliers')
            )

            if hasSnMatches:
                siteSnMask = self.getSerialMatchMask(siteDf, highlightSn)
                if np.any(siteSnMask):
                    matchedSiteDf = siteDf[siteSnMask]
                    mCount = len(matchedSiteDf)
                    matchedBoxX.extend([siteLabel] * mCount)
                    matchedBoxY.extend(yPlot[siteSnMask].tolist())
                    matchedBoxCustom.append(np.column_stack((
                        matchedSiteDf['SerialNumber'].astype(str).to_numpy(),
                        matchedSiteDf['TestDate'].astype(str).to_numpy(),
                        np.full(mCount, lslLabel, dtype=object),
                        np.full(mCount, uslLabel, dtype=object),
                        siteVals[siteSnMask],
                        np.full(mCount, site, dtype=object),
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
                    f'Value: %{{customdata[4]:.6g}}{ctx.unitSuffix}<br>'
                    'Date: %{customdata[1]}<br>'
                    f'Limits: [%{{customdata[2]}}{ctx.unitSuffix}, %{{customdata[3]}}{ctx.unitSuffix}]'
                    '<extra></extra>'
                ),
                useWebgl=False,
            )

        self._addHorizontalLimitLines(fig, ctx)

        self._applyCommonLayout(fig, title=f'{testName} — Site Comparison', xTitle='Test Site',
            yTitle=ctx.yAxisTitle(), logScale=(logScale and not ctx.useSymlog))

        if ctx.useSymlog and np.isfinite(minPlotY):
            self._applySymlogYAxis(fig, ctx)

        if valuesInLimits:
            self._applyScalarLimitsRange(fig, ctx, axis='y', fallbackMin=minPlotY, fallbackMax=maxPlotY,
                logScale=(logScale and not ctx.useSymlog))

        return fig


    # ------------------------------------------------------------------
    # CxCy LED Bin Plot
    # ------------------------------------------------------------------
    def createCxCyPlot(self, df:pd.DataFrame, testName:str, valuesInLimits:bool=False, limitsMode:str='All',
            highlightSn:str ='') -> go.Figure:
        
        fig = go.Figure()

        snMaskAll = self.getSerialMatchMask(df, highlightSn) if highlightSn else np.zeros(len(df), dtype=bool)
        hasSnMatches = bool(np.any(snMaskAll))
        pointOpacity = 0.15 if hasSnMatches else 0.85
        pointSize = 5 if hasSnMatches else 6

        for idx, (site, siteDf) in enumerate(df.groupby(df['Site'].astype(str), sort=True)):
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

        boundaries = self._extractCxCyBoundaries(df, limitsMode)
        bounds = self._addCxCyBoundaryTraces(fig, boundaries)

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

        if valuesInLimits and bounds is not None:
            minX, maxX, minY, maxY = bounds
            self._applyAxisLimitsPadding(fig, axis='x', low=minX, high=maxX, logScale=False)
            self._applyAxisLimitsPadding(fig, axis='y', low=minY, high=maxY, logScale=False)

        return fig


    # ------------------------------------------------------------------
    # Scaling, Symlog & Limit Helpers
    # ------------------------------------------------------------------
    def _prepareScalarContext(self, df:pd.DataFrame, limitsMode:str, logScale:bool, allowSymlog:bool) -> _ScalarScaleContext:
        rawValues = df['Value'].to_numpy(dtype=float)
        finiteVals = rawValues[np.isfinite(rawValues)]
        nonZero = np.abs(finiteVals[finiteVals != 0.0])
        dataRef = float(np.median(nonZero)) if nonZero.size > 0 else None

        lslRaw, uslRaw = self._resolveScalarLimits(df, limitsMode)
        hasValidLsl = not isSentinelLimit(lslRaw, dataRef)
        hasValidUsl = not isSentinelLimit(uslRaw, dataRef)

        prefix, scaleFactor = getSiScale(rawValues, lslRaw, uslRaw)
        unitSuffix = f' {prefix}' if prefix else ''
        scaledValuesAll = rawValues * scaleFactor

        lslScaled = (lslRaw * scaleFactor) if (hasValidLsl and lslRaw is not None) else None
        uslScaled = (uslRaw * scaleFactor) if (hasValidUsl and uslRaw is not None) else None

        useSymlog = False
        linthresh = 1.0
        if logScale and allowSymlog:
            checkParts: list[np.ndarray] = []
            finiteScaled = scaledValuesAll[np.isfinite(scaledValuesAll)]
            if finiteScaled.size > 0:
                checkParts.append(finiteScaled)
            if lslScaled is not None:
                checkParts.append(np.array([lslScaled], dtype=float))
            if uslScaled is not None:
                checkParts.append(np.array([uslScaled], dtype=float))

            if checkParts:
                combined = np.concatenate(checkParts) if len(checkParts) > 1 else checkParts[0]
                if np.any(combined <= 0.0):
                    useSymlog = True
                    linthresh = calculateLinthresh(combined)

        lslPlot = float(symlogTransform(lslScaled, linthresh)) if (useSymlog and lslScaled is not None) else lslScaled
        uslPlot = float(symlogTransform(uslScaled, linthresh)) if (useSymlog and uslScaled is not None) else uslScaled

        return _ScalarScaleContext(prefix=prefix, scaleFactor=scaleFactor, unitSuffix=unitSuffix, scaledValuesAll=scaledValuesAll,
            hasValidLsl=hasValidLsl, hasValidUsl=hasValidUsl, lslScaled=lslScaled, uslScaled=uslScaled, lslPlot=lslPlot,
            uslPlot=uslPlot, useSymlog=useSymlog, linthresh=linthresh)
    

    @staticmethod
    def _resolveScalarLimits(df: pd.DataFrame, limitsMode: str) -> tuple[float | None, float | None]:
        if df.empty or 'LSL' not in df.columns or 'USL' not in df.columns:
            return None, None
        sortedDf = df.sort_values(by='TestDate', kind='mergesort')
        row = sortedDf.iloc[0] if limitsMode == 'Oldest' else sortedDf.iloc[-1]
        lsl = float(row['LSL']) if pd.notna(row['LSL']) else None
        usl = float(row['USL']) if pd.notna(row['USL']) else None
        return lsl, usl
    

    @staticmethod
    def _buildInLimitsMask(scaledValues: np.ndarray, ctx: _ScalarScaleContext) -> np.ndarray:
        mask = np.ones(len(scaledValues), dtype=bool)
        if ctx.hasValidLsl and ctx.lslScaled is not None:
            mask &= scaledValues >= ctx.lslScaled
        if ctx.hasValidUsl and ctx.uslScaled is not None:
            mask &= scaledValues <= ctx.uslScaled
        return mask


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


    @classmethod
    def _buildScalarCustomData(cls, siteDf:pd.DataFrame, siteVals:np.ndarray, siteLsl:np.ndarray, siteUsl:np.ndarray,
            hasValidLsl:bool, hasValidUsl:bool) -> np.ndarray:

        return np.column_stack((
            siteDf['SerialNumber'].astype(str).to_numpy(),
            siteDf['TestDate'].astype(str).to_numpy(),
            cls._formatLimitArray(siteLsl, hasValidLsl),
            cls._formatLimitArray(siteUsl, hasValidUsl),
            siteVals,
        ))

    def _addDynamicSequenceLimitTraces(self, fig: go.Figure, siteLimitsData: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
            ctx: _ScalarScaleContext):
        
        for idx, (xVals, siteLsl, siteUsl) in enumerate(siteLimitsData):
            if ctx.hasValidLsl:
                fig.add_trace(
                    go.Scattergl(
                        x=xVals,
                        y=ctx.toPlotY(siteLsl),
                        mode='lines',
                        name='LSL',
                        legendgroup='LSL',
                        showlegend=(idx == 0),
                        line=dict(color=self.LSL_COLOR, width=1.6, dash='dashdot'),
                        customdata=siteLsl,
                        hovertemplate=f'LSL: %{{customdata:.6g}}{ctx.unitSuffix}<extra></extra>',
                    )
                )

            if ctx.hasValidUsl:
                fig.add_trace(
                    go.Scattergl(
                        x=xVals,
                        y=ctx.toPlotY(siteUsl),
                        mode='lines',
                        name='USL',
                        legendgroup='USL',
                        showlegend=(idx == 0),
                        line=dict(color=self.USL_COLOR, width=1.6, dash='dashdot'),
                        customdata=siteUsl,
                        hovertemplate=f'USL: %{{customdata:.6g}}{ctx.unitSuffix}<extra></extra>',
                    )
                )


    def _addHorizontalLimitLines(self, fig:go.Figure, ctx:_ScalarScaleContext):
        if ctx.hasValidLsl and ctx.lslPlot is not None and ctx.lslScaled is not None:
            fig.add_hline(
                y=ctx.lslPlot,
                line_dash='dash',
                line_color=self.LSL_COLOR,
                line_width=1.8,
                annotation_text=f'LSL ({ctx.lslScaled:.4g})',
                annotation_position='bottom right',
                annotation_font_color=self.LSL_COLOR,
            )

        if ctx.hasValidUsl and ctx.uslPlot is not None and ctx.uslScaled is not None:
            fig.add_hline(
                y=ctx.uslPlot,
                line_dash='dash',
                line_color=self.USL_COLOR,
                line_width=1.8,
                annotation_text=f'USL ({ctx.uslScaled:.4g})',
                annotation_position='top right',
                annotation_font_color=self.USL_COLOR,
            )

    def _applySymlogYAxis(self, fig:go.Figure, ctx:_ScalarScaleContext):
        finiteScaled = ctx.scaledValuesAll[np.isfinite(ctx.scaledValuesAll)]
        if finiteScaled.size == 0:
            return

        minValReal = float(np.min(finiteScaled))
        maxValReal = float(np.max(finiteScaled))
        if ctx.hasValidLsl and ctx.lslScaled is not None:
            minValReal = min(minValReal, ctx.lslScaled)
        if ctx.hasValidUsl and ctx.uslScaled is not None:
            maxValReal = max(maxValReal, ctx.uslScaled)

        tickVals, tickText = generateSymlogTicks(minValReal, maxValReal, ctx.linthresh)
        fig.update_layout(
            yaxis=dict(type='linear', tickmode='array', tickvals=tickVals, ticktext=tickText, zeroline=True,
                zerolinecolor='#5a5d64', zerolinewidth=1.5)
        )

    def _applyScalarLimitsRange(self, fig:go.Figure, ctx:_ScalarScaleContext, axis:str, fallbackMin:float,
            fallbackMax:float, logScale:bool):
        
        if not (ctx.hasValidLsl or ctx.hasValidUsl):
            return

        lowBound = ctx.lslPlot if (ctx.hasValidLsl and ctx.lslPlot is not None) else fallbackMin
        highBound = ctx.uslPlot if (ctx.hasValidUsl and ctx.uslPlot is not None) else fallbackMax
        self._applyAxisLimitsPadding(fig, axis=axis, low=lowBound, high=highBound, logScale=logScale)


    # ------------------------------------------------------------------
    # Capability & CxCy Sub-Builders
    # ------------------------------------------------------------------
    @staticmethod
    def _gaussianPdf(xGrid:np.ndarray, mean:float, std:float) -> np.ndarray:
        return (1.0 / (std * np.sqrt(2.0 * np.pi))) * np.exp(-0.5 * ((xGrid - mean) / std) ** 2)

    def _addCapabilityPerSiteCurves(self, fig:go.Figure, validDf:pd.DataFrame, xGrid:np.ndarray, ctx:_ScalarScaleContext,
            valuesInLimits:bool):

        siteGroups = list(validDf.groupby(validDf['Site'].astype(str), sort=True))
        if len(siteGroups) <= 1:
            return

        autoHidePerSite = len(siteGroups) > 8
        for idx, (site, siteDf) in enumerate(siteGroups):
            siteScaled = siteDf['Value'].to_numpy(dtype=float) * ctx.scaleFactor
            if valuesInLimits:
                siteScaled = siteScaled[self._buildInLimitsMask(siteScaled, ctx)]

            if len(siteScaled) < 3:
                continue

            mSite = float(np.mean(siteScaled))
            sSite = float(np.std(siteScaled, ddof=1))
            if sSite <= 0.0:
                continue

            fig.add_trace(
                go.Scatter(
                    x=xGrid,
                    y=self._gaussianPdf(xGrid, mSite, sSite),
                    mode='lines',
                    name=f'Site {site} (μ={mSite:.4g}, σ={sSite:.3g})',
                    visible=True if not autoHidePerSite else 'legendonly',
                    line=dict(color=self._getSiteColor(idx), width=1.8),
                    hovertemplate=f'Site {site}: %{{x:.6g}}{ctx.unitSuffix}<br>PDF: %{{y:.4g}}<extra></extra>',
                )
            )

    def _addCapabilitySnOverlay(self, fig:go.Figure, plotDf:pd.DataFrame, plotValues:np.ndarray, highlightSn:str,
            stdOverall:float, binSize:float|None, ctx:_ScalarScaleContext):
        
        snMask = self.getSerialMatchMask(plotDf, highlightSn)
        if not np.any(snMask):
            return

        matchedDf = plotDf[snMask]
        matchedVals = plotValues[snMask]

        peakY = float(1.0 / (stdOverall * np.sqrt(2.0 * np.pi))) if stdOverall > 0.0 else 0.0
        try:
            if np.ptp(plotValues) > 0.0:
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
                f'Value: %{{x:.6g}}{ctx.unitSuffix}<br>'
                'Date: %{customdata[1]}'
                '<extra></extra>'
            ),
            useWebgl=False,
        )

    def _addCapabilityReferenceLines(self, fig:go.Figure, meanOverall:float, ctx:_ScalarScaleContext):
        fig.add_vline(x=meanOverall, line_dash='dot', line_color=self.MEAN_COLOR, line_width=2, annotation_text='Mean',
            annotation_position='top', annotation_font_color=self.MEAN_COLOR)
        
        if ctx.hasValidLsl and ctx.lslScaled is not None:
            fig.add_vline(x=ctx.lslScaled, line_dash='dash', line_color=self.LSL_COLOR, line_width=2, annotation_text='LSL',
                annotation_position='top left', annotation_font_color=self.LSL_COLOR)
            
        if ctx.hasValidUsl and ctx.uslScaled is not None:
            fig.add_vline( x=ctx.uslScaled, line_dash='dash', line_color=self.USL_COLOR, line_width=2, annotation_text='USL',
                annotation_position='top right', annotation_font_color=self.USL_COLOR)

    @staticmethod
    def _extractCxCyBoundaries(df:pd.DataFrame, limitsMode:str) -> list[tuple[tuple[tuple[float, float], ...], str]]:
        sortedByDateDf = df.sort_values(by='TestDate', kind='mergesort')
        validBoundaries = sortedByDateDf['Boundary'].dropna()
        if validBoundaries.empty:
            return []

        if limitsMode == 'Newest':
            lastValid = validBoundaries.iloc[-1]
            return [(tuple(tuple(pt) for pt in lastValid), 'Active Bin (Newest)')]

        if limitsMode == 'Oldest':
            firstValid = validBoundaries.iloc[0]
            return [(tuple(tuple(pt) for pt in firstValid), 'Initial Bin (Oldest)')]

        result: list[tuple[tuple[tuple[float, float], ...], str]] = []
        seen: set[tuple[tuple[float, float], ...]] = set()
        for boundary in validBoundaries:
            key = tuple(tuple(pt) for pt in boundary)
            if key not in seen:
                seen.add(key)
                label = f'Bin Boundary {len(seen)}' if len(seen) > 1 else 'Bin Boundary'
                result.append((key, label))
        return result

    def _addCxCyBoundaryTraces(self, fig:go.Figure, boundaries:list[tuple[tuple[tuple[float, float], ...], str]]) -> tuple[float, float, float, float]|None:
        if not boundaries:
            return None

        minX, maxX = float('inf'), float('-inf')
        minY, maxY = float('inf'), float('-inf')
        dashStyles = ['solid', 'dash', 'dot', 'dashdot']

        for idx, (boundary, label) in enumerate(boundaries):
            bx = [pt[0] for pt in boundary]
            by = [pt[1] for pt in boundary]
            minX, maxX = min(minX, min(bx)), max(maxX, max(bx))
            minY, maxY = min(minY, min(by)), max(maxY, max(by))

            dash = dashStyles[idx % len(dashStyles)]
            color = self.USL_COLOR if idx == 0 else ('#e040fb' if idx == 1 else self.LSL_COLOR)

            fig.add_trace(
                go.Scatter(x=bx, y=by, mode='lines', name=label, line=dict(color=color, width=2.2, dash=dash),
                    hoverinfo='skip')
            )

        return minX, maxX, minY, maxY

    def _addSerialHighlightOverlay(self, fig:go.Figure, x, y, highlightSn:str, customData:np.ndarray, hoverTemplate:str,
            useWebgl: bool):

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


    # ------------------------------------------------------------------
    # Layout, Axis Padding & Palette
    # ------------------------------------------------------------------
    def _applyCommonLayout(self, fig:go.Figure, title:str, xTitle:str, yTitle:str, logScale:bool):
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
    def _calculateHistogramBinSize(data:np.ndarray) -> float|None:
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

    def _createEmptyFigure(self, message:str) -> go.Figure:
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

        # Calculate distinct colors using golden-angle HSL progression
        step = idx - len(self.SITE_PALETTE) + 1
        hue = ((step * 137.508) % 360.0) / 360.0
        lightness = 0.56 + (step % 3) * 0.08
        saturation = 0.75 if step % 2 == 0 else 0.88
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        return f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'