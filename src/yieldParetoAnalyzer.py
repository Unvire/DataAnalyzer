from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.measurementEngine import MeasurementEngine
from src.processCalculator import ProcessParameterCalculator
from src.siFormatter import isSentinelLimit


SUMMARY_COLUMNS = [
    'TestName',
    'Samples',
    'Fails',
    'FailLow',
    'FailHigh',
    'YieldPct',
    'DPMO',
    'Ppk',
    'Cpk',
    'PpkNP',
    'SiteDeltaPct',
    'LSL',
    'USL',
    'Mean',
    'Sigma',
]


@dataclass
class BatchSummaryResult:
    summaryDf: pd.DataFrame
    totalTests: int = 0
    failingTestsCount: int = 0
    totalFails: int = 0
    totalMeasurements: int = 0
    measurementYieldPct: float | None = None
    totalRuns: int = 0
    failedRuns: int = 0
    boardYieldPct: float | None = None
    worstYieldTest: str = ''
    worstYieldPct: float | None = None
    worstPpkTest: str = ''
    worstPpkValue: float | None = None


class YieldParetoAnalyzer:
    BG_COLOR = '#1e1f22'
    PLOT_BG_COLOR = '#26282e'
    GRID_COLOR = '#35373c'
    TEXT_COLOR = '#dfe1e5'
    MUTED_TEXT_COLOR = '#9da0a8'

    FAIL_LOW_COLOR = '#4c8dff'
    FAIL_HIGH_COLOR = '#ef5350'
    FAIL_CXCY_COLOR = '#ab47bc'
    CUMULATIVE_COLOR = '#ffd600'
    OK_COLOR = '#66bb6a'
    WARN_COLOR = '#ffa726'
    BAD_COLOR = '#ef5350'

    def __init__(self, calculator:ProcessParameterCalculator|None=None):
        self._calculator = calculator or ProcessParameterCalculator()

    def analyze(self, measurements:dict[str, pd.DataFrame], site:str='All sites', limitsMode:str='All',
            progressCallback=None) -> BatchSummaryResult:
        
        if not measurements:
            return BatchSummaryResult(summaryDf=pd.DataFrame(columns=SUMMARY_COLUMNS))

        rows: list[dict] = []
        allRuns: set[str] = set()
        failedRuns: set[str] = set()

        totalTestsInput = len(measurements)
        totalFails = 0
        totalMeasurements = 0

        for idx, (testName, fullDf) in enumerate(measurements.items(), start=1):
            if fullDf is None or fullDf.empty:
                if progressCallback:
                    progressCallback(int(idx / totalTestsInput * 100))
                continue

            df = fullDf if site == 'All sites' else fullDf[fullDf['Site'].astype(str) == site]
            if df.empty:
                if progressCallback:
                    progressCallback(int(idx / totalTestsInput * 100))
                continue

            metrics = self._calculator.calculate(df, limitsMode=limitsMode)
            totalFails += metrics.failTotal
            totalMeasurements += metrics.validSamples

            self._accumulateBoardRuns(df, limitsMode, allRuns, failedRuns)

            rows.append({
                'TestName': testName,
                'Samples': metrics.validSamples,
                'Fails': metrics.failTotal,
                'FailLow': metrics.failLow,
                'FailHigh': metrics.failHigh,
                'YieldPct': metrics.yieldPct if metrics.yieldPct is not None else np.nan,
                'DPMO': metrics.dpmo if metrics.dpmo is not None else np.nan,
                'Ppk': metrics.ppk if metrics.ppk is not None else np.nan,
                'Cpk': metrics.cpk if metrics.cpk is not None else np.nan,
                'PpkNP': metrics.ppkNonParametric if metrics.ppkNonParametric is not None else np.nan,
                'SiteDeltaPct': metrics.siteDeltaPct if metrics.siteDeltaPct is not None else np.nan,
                'LSL': metrics.lsl if metrics.lsl is not None else np.nan,
                'USL': metrics.usl if metrics.usl is not None else np.nan,
                'Mean': metrics.mean if metrics.mean is not None else np.nan,
                'Sigma': metrics.sigmaOverall if metrics.sigmaOverall is not None else np.nan,
            })

            if progressCallback:
                progressCallback(int(idx / totalTestsInput * 100))

        if not rows:
            return BatchSummaryResult(summaryDf=pd.DataFrame(columns=SUMMARY_COLUMNS))

        summaryDf = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
        summaryDf = summaryDf.sort_values(
            by=['Fails', 'DPMO', 'Ppk'],
            ascending=[False, False, True],
            na_position='last',
            kind='mergesort',
        ).reset_index(drop=True)

        failingTestsCount = int((summaryDf['Fails'] > 0).sum())
        measurementYieldPct = (
            ((totalMeasurements - totalFails) / totalMeasurements) * 100.0
            if totalMeasurements > 0
            else None
        )

        totalRuns = len(allRuns)
        failedRunsCount = len(failedRuns)
        boardYieldPct = (
            ((totalRuns - failedRunsCount) / totalRuns) * 100.0
            if totalRuns > 0
            else None
        )

        worstYieldTest = ''
        worstYieldPct = None
        validYields = summaryDf.dropna(subset=['YieldPct'])
        if not validYields.empty:
            worstYRow = validYields.loc[validYields['YieldPct'].idxmin()]
            worstYieldTest = str(worstYRow['TestName'])
            worstYieldPct = float(worstYRow['YieldPct'])

        worstPpkTest = ''
        worstPpkValue = None
        validPpks = summaryDf.dropna(subset=['Ppk'])
        if not validPpks.empty:
            worstPRow = validPpks.loc[validPpks['Ppk'].idxmin()]
            worstPpkTest = str(worstPRow['TestName'])
            worstPpkValue = float(worstPRow['Ppk'])

        return BatchSummaryResult(
            summaryDf=summaryDf,
            totalTests=len(summaryDf),
            failingTestsCount=failingTestsCount,
            totalFails=totalFails,
            totalMeasurements=totalMeasurements,
            measurementYieldPct=measurementYieldPct,
            totalRuns=totalRuns,
            failedRuns=failedRunsCount,
            boardYieldPct=boardYieldPct,
            worstYieldTest=worstYieldTest,
            worstYieldPct=worstYieldPct,
            worstPpkTest=worstPpkTest,
            worstPpkValue=worstPpkValue,
        )


    def _accumulateBoardRuns(self, df:pd.DataFrame, limitsMode:str, allRuns:set[str], failedRuns:set[str]):
        if 'SerialNumber' not in df.columns or 'TestDate' not in df.columns:
            return

        runKeys = df['SerialNumber'].astype(str).str.cat(df['TestDate'].astype(str), sep='\x1f')
        allRuns.update(runKeys.unique())

        failMask = self._computeRowFailMask(df, limitsMode)
        if np.any(failMask):
            failedRuns.update(runKeys[failMask].unique())

    def _computeRowFailMask(self, df:pd.DataFrame, limitsMode:str) -> np.ndarray:
        n = len(df)
        if n == 0:
            return np.zeros(0, dtype=bool)

        if MeasurementEngine.isCxCyDataFrame(df):
            cx = df['CX'].to_numpy(dtype=float)
            cy = df['CY'].to_numpy(dtype=float)
            finiteMask = np.isfinite(cx) & np.isfinite(cy)
            if not np.any(finiteMask) or 'Boundary' not in df.columns:
                return np.zeros(n, dtype=bool)

            sortedDf = df.sort_values(by='TestDate', kind='mergesort') if 'TestDate' in df.columns else df
            boundaries = sortedDf['Boundary'].dropna()
            if boundaries.empty:
                return np.zeros(n, dtype=bool)

            failMask = np.zeros(n, dtype=bool)
            if limitsMode in ('Newest', 'Oldest'):
                refPoly = boundaries.iloc[0] if limitsMode == 'Oldest' else boundaries.iloc[-1]
                inside = ProcessParameterCalculator._pointsInPolygon(cx[finiteMask], cy[finiteMask], refPoly)
                failMask[finiteMask] = ~inside
                return failMask

            polyGroups: dict[tuple[tuple[float, float], ...], list[int]] = {}
            validIndices = np.flatnonzero(finiteMask)
            boundaryCol = df['Boundary'].tolist()
            for rowIdx in validIndices:
                poly = boundaryCol[rowIdx]
                if poly is None or len(poly) < 3:
                    continue
                key = tuple((float(pt[0]), float(pt[1])) for pt in poly)
                polyGroups.setdefault(key, []).append(int(rowIdx))

            for polyKey, idxList in polyGroups.items():
                idxArr = np.asarray(idxList, dtype=np.int64)
                inside = ProcessParameterCalculator._pointsInPolygon(cx[idxArr], cy[idxArr], polyKey)
                failMask[idxArr] = ~inside
            return failMask

        if 'Value' not in df.columns or 'LSL' not in df.columns or 'USL' not in df.columns:
            return np.zeros(n, dtype=bool)

        vals = df['Value'].to_numpy(dtype=float)
        finiteMask = np.isfinite(vals)
        if not np.any(finiteMask):
            return np.zeros(n, dtype=bool)

        finiteVals = vals[finiteMask]
        nonZero = np.abs(finiteVals[finiteVals != 0.0])
        dataRef = float(np.median(nonZero)) if nonZero.size > 0 else None

        if limitsMode == 'All':
            lslArr = df['LSL'].to_numpy(dtype=float)
            uslArr = df['USL'].to_numpy(dtype=float)
            validLsl = ProcessParameterCalculator._buildValidLimitMask(lslArr, dataRef)
            validUsl = ProcessParameterCalculator._buildValidLimitMask(uslArr, dataRef)
            return finiteMask & ((validLsl & (vals < lslArr)) | (validUsl & (vals > uslArr)))

        lslRef, uslRef = ProcessParameterCalculator._resolveScalarLimits(df, limitsMode)
        hasLsl = lslRef is not None and not isSentinelLimit(lslRef, dataRef)
        hasUsl = uslRef is not None and not isSentinelLimit(uslRef, dataRef)

        failMask = np.zeros(n, dtype=bool)
        if hasLsl:
            failMask |= finiteMask & (vals < lslRef)
        if hasUsl:
            failMask |= finiteMask & (vals > uslRef)
        return failMask


    # ------------------------------------------------------------------
    # Chart Builders
    # ------------------------------------------------------------------
    def createParetoFigure(self, summaryDf:pd.DataFrame,  metric:str='Defect Pareto (Fails)', topN:int|None=20) -> go.Figure:
        if summaryDf is None or summaryDf.empty:
            return self._createEmptyFigure('No tests available for Yield & Pareto analysis.')

        normalized = metric.strip().lower()
        if 'ppk' in normalized:
            return self._createLowestPpkFigure(summaryDf, topN=topN)
        if 'delta' in normalized:
            return self._createHighestSiteDeltaFigure(summaryDf, topN=topN)
        return self._createDefectParetoFigure(summaryDf, topN=topN)

    def _createDefectParetoFigure(self, summaryDf: pd.DataFrame, topN: int | None = 20) -> go.Figure:
        failingDf = summaryDf[summaryDf['Fails'] > 0].sort_values(
            by=['Fails', 'DPMO'],
            ascending=[False, False],
            kind='mergesort',
        )

        if failingDf.empty:
            return self._createEmptyFigure(
                '100% Yield — 0 failures across all tests.\n'
                'Switch chart mode to "Weakest Capability (Ppk)" to inspect safety margins.'
            )

        totalFailsAll = int(failingDf['Fails'].sum())

        if topN is not None and len(failingDf) > topN:
            headDf = failingDf.iloc[:topN].copy()
            tailDf = failingDf.iloc[topN:]
            otherRow = pd.DataFrame([{
                'TestName': f'Other ({len(tailDf)} tests)',
                'Samples': int(tailDf['Samples'].sum()),
                'Fails': int(tailDf['Fails'].sum()),
                'FailLow': int(tailDf['FailLow'].sum()),
                'FailHigh': int(tailDf['FailHigh'].sum()),
                'YieldPct': np.nan,
                'DPMO': np.nan,
                'Ppk': np.nan,
            }])
            plotDf = pd.concat([headDf, otherRow], ignore_index=True)
        else:
            plotDf = failingDf.reset_index(drop=True)

        fullNames = plotDf['TestName'].astype(str).tolist()
        shortLabels = self._makeUniqueShortLabels(fullNames)
        failLow = plotDf['FailLow'].to_numpy(dtype=int)
        failHigh = plotDf['FailHigh'].to_numpy(dtype=int)
        failsTotal = plotDf['Fails'].to_numpy(dtype=int)
        failOther = np.maximum(0, failsTotal - failLow - failHigh)

        cumPct = (np.cumsum(failsTotal) / max(totalFailsAll, 1)) * 100.0

        yieldStrs = [f'{v:.2f}%' if np.isfinite(v) else '—' for v in plotDf['YieldPct'].to_numpy(dtype=float)]
        ppkStrs = [f'{v:.2f}' if np.isfinite(v) else '—' for v in plotDf['Ppk'].to_numpy(dtype=float)]
        customData = np.column_stack((fullNames, failsTotal, failLow, failHigh, yieldStrs, ppkStrs, cumPct))

        hoverTemplate = (
            '<b>%{customdata[0]}</b><br>'
            'Total Fails: %{customdata[1]} (Cum: %{customdata[6]:.1f}%)<br>'
            'Fail Low / High: %{customdata[2]} / %{customdata[3]}<br>'
            'Yield: %{customdata[4]}  |  Ppk: %{customdata[5]}'
            '<extra></extra>'
        )

        fig = go.Figure()

        if np.any(failHigh > 0):
            fig.add_trace(
                go.Bar(x=shortLabels, y=failHigh, name='Fail High (> USL)', marker_color=self.FAIL_HIGH_COLOR, 
                    customdata=customData, hovertemplate=hoverTemplate)
            )
        if np.any(failLow > 0):
            fig.add_trace(
                go.Bar(x=shortLabels, y=failLow, name='Fail Low (< LSL)', marker_color=self.FAIL_LOW_COLOR,
                    customdata=customData, hovertemplate=hoverTemplate)
            )
        if np.any(failOther > 0):
            fig.add_trace(
                go.Bar(x=shortLabels, y=failOther, name='CxCy Out of Bin', marker_color=self.FAIL_CXCY_COLOR,
                    customdata=customData, hovertemplate=hoverTemplate)
            )

        fig.add_trace(
            go.Scatter(
                x=shortLabels,
                y=cumPct,
                name='Cumulative %',
                yaxis='y2',
                mode='lines+markers',
                line=dict(color=self.CUMULATIVE_COLOR, width=2.4),
                marker=dict(size=6, color=self.CUMULATIVE_COLOR),
                customdata=customData,
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    'Cumulative Share: %{y:.1f}%<br>'
                    'Test Fails: %{customdata[1]}'
                    '<extra></extra>'
                ),
            )
        )

        # 80/20 Pareto reference line on secondary Y axis
        fig.add_shape(type='line', xref='paper', x0=0.0, x1=1.0, yref='y2', y0=80.0, y1=80.0,
            line=dict(color=self.WARN_COLOR, width=1.4, dash='dash'))
        
        fig.add_annotation(xref='paper', x=0.99, yref='y2', y=82.5, text='80% Pareto', showarrow=False,
            xanchor='right', font=dict(size=11, color=self.WARN_COLOR))

        self._applyParetoLayout(fig, title=f'Defect Pareto — Top Failing Tests ({totalFailsAll:,} total fails)',
            yTitle='Failure Count', hasSecondaryAxis=True)
        
        fig.update_layout(barmode='stack')
        return fig

    def _createLowestPpkFigure(self, summaryDf:pd.DataFrame, topN:int|None=20) -> go.Figure:
        validDf = summaryDf.dropna(subset=['Ppk']).sort_values(by='Ppk', ascending=True, kind='mergesort')
        if validDf.empty:
            return self._createEmptyFigure('No tests with valid Ppk values available.')

        plotDf = validDf.iloc[:topN].reset_index(drop=True) if topN is not None else validDf.reset_index(drop=True)
        fullNames = plotDf['TestName'].astype(str).tolist()
        shortLabels = self._makeUniqueShortLabels(fullNames)
        ppkVals = plotDf['Ppk'].to_numpy(dtype=float)

        barColors = [
            self.BAD_COLOR if v < 1.0 else (self.WARN_COLOR if v < 1.33 else self.OK_COLOR)
            for v in ppkVals
        ]
        cpkStrs = [f'{v:.2f}' if np.isfinite(v) else '—' for v in plotDf['Cpk'].to_numpy(dtype=float)]
        yieldStrs = [f'{v:.2f}%' if np.isfinite(v) else '—' for v in plotDf['YieldPct'].to_numpy(dtype=float)]
        customData = np.column_stack((fullNames, ppkVals, cpkStrs, yieldStrs, plotDf['Fails'].to_numpy(dtype=int)))

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=shortLabels,
                y=ppkVals,
                name='Ppk',
                marker_color=barColors,
                customdata=customData,
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    'Ppk: %{y:.2f}  |  Cpk: %{customdata[2]}<br>'
                    'Yield: %{customdata[3]}  |  Fails: %{customdata[4]}'
                    '<extra></extra>'
                ),
            )
        )

        fig.add_hline(y=1.00, line_dash='dash', line_color=self.BAD_COLOR, line_width=1.5, annotation_text='Ppk = 1.00',
            annotation_position='top right', annotation_font_color=self.BAD_COLOR)
        
        fig.add_hline(y=1.33, line_dash='dash', line_color=self.OK_COLOR, line_width=1.5, annotation_text='Ppk = 1.33', 
            annotation_position='top right', annotation_font_color=self.OK_COLOR)

        self._applyParetoLayout(fig, title='Weakest Process Capability — Lowest Ppk Tests',
            yTitle='Ppk', hasSecondaryAxis=False)
        
        return fig

    def _createHighestSiteDeltaFigure(self, summaryDf:pd.DataFrame, topN:int|None=20) -> go.Figure:
        validDf = summaryDf.dropna(subset=['SiteDeltaPct']).sort_values(
            by='SiteDeltaPct',
            ascending=False,
            kind='mergesort',
        )
        if validDf.empty:
            return self._createEmptyFigure(
                'Site-to-Site Delta requires at least 2 test sites and two-sided limits.'
            )

        plotDf = validDf.iloc[:topN].reset_index(drop=True) if topN is not None else validDf.reset_index(drop=True)
        fullNames = plotDf['TestName'].astype(str).tolist()
        shortLabels = self._makeUniqueShortLabels(fullNames)
        deltas = plotDf['SiteDeltaPct'].to_numpy(dtype=float)

        barColors = [
            self.BAD_COLOR if v > 25.0 else (self.WARN_COLOR if v > 10.0 else self.OK_COLOR)
            for v in deltas
        ]
        ppkStrs = [f'{v:.2f}' if np.isfinite(v) else '—' for v in plotDf['Ppk'].to_numpy(dtype=float)]
        cpkStrs = [f'{v:.2f}' if np.isfinite(v) else '—' for v in plotDf['Cpk'].to_numpy(dtype=float)]
        customData = np.column_stack((fullNames, ppkStrs, cpkStrs, plotDf['Fails'].to_numpy(dtype=int)))

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=shortLabels,
                y=deltas,
                name='Site Delta (%)',
                marker_color=barColors,
                customdata=customData,
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    'Site Delta: %{y:.1f}% of tolerance<br>'
                    'Ppk: %{customdata[1]}  |  Cpk: %{customdata[2]}<br>'
                    'Fails: %{customdata[3]}'
                    '<extra></extra>'
                ),
            )
        )

        fig.add_hline(y=10.0, line_dash='dash', line_color=self.WARN_COLOR, line_width=1.4, annotation_text='10% Warning',
            annotation_position='top right', annotation_font_color=self.WARN_COLOR)
        
        fig.add_hline(y=25.0, line_dash='dash', line_color=self.BAD_COLOR, line_width=1.4, annotation_text='25% Critical',
            annotation_position='top right', annotation_font_color=self.BAD_COLOR)

        self._applyParetoLayout(fig, title='Largest Site-to-Site Offset (% of Tolerance Window)',
            yTitle='Site Delta [%]', hasSecondaryAxis=False)
        
        return fig

    def _applyParetoLayout(self, fig:go.Figure, title:str, yTitle:str, hasSecondaryAxis:bool):
        layoutKwargs = dict(
            separators='. ',
            title=dict(text=title, x=0.02, y=0.96, font=dict(size=14, color=self.TEXT_COLOR)),
            paper_bgcolor=self.BG_COLOR,
            plot_bgcolor=self.PLOT_BG_COLOR,
            font=dict(family='Segoe UI, Arial, sans-serif', size=11, color=self.TEXT_COLOR),
            margin=dict(l=60, r=60 if hasSecondaryAxis else 25, t=68, b=115),
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
                tickangle=-35,
                gridcolor=self.GRID_COLOR,
                automargin=True,
            ),
            yaxis=dict(
                title=dict(text=yTitle, standoff=8),
                gridcolor=self.GRID_COLOR,
                zerolinecolor=self.GRID_COLOR,
                separatethousands=True,
                automargin=True,
            ),
        )

        if hasSecondaryAxis:
            layoutKwargs['yaxis2'] = dict(
                title=dict(text='Cumulative [%]', font=dict(color=self.CUMULATIVE_COLOR)),
                tickfont=dict(color=self.CUMULATIVE_COLOR),
                overlaying='y',
                side='right',
                range=[0, 105],
                ticksuffix='%',
                showgrid=False,
            )

        fig.update_layout(**layoutKwargs)

    def _createEmptyFigure(self, message:str) -> go.Figure:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor=self.BG_COLOR,
            plot_bgcolor=self.BG_COLOR,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[
                dict(
                    text=message.replace('\n', '<br>'),
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

    @staticmethod
    def _makeUniqueShortLabels(names:list[str], maxLen:int=28) -> list[str]:
        counts: dict[str, int] = {}
        labels: list[str] = []
        for name in names:
            short = name if len(name) <= maxLen else f'{name[:maxLen - 1]}…'
            counts[short] = counts.get(short, 0) + 1
            if counts[short] > 1:
                labels.append(f'{short} ({counts[short]})')
            else:
                labels.append(short)
        return labels