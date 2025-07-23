import io, base64, os, time
import multiprocessing

from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

import matplotlib
matplotlib.use('Agg')
os.environ['PYDEVD_DISABLE_FILE_VALIDATION'] = '1'

from mplCanvas import MplCanvas
from processCalculator import ProcessParameterCalculator
from plotGenerator import SequencePlotGenerator, CapabilityPlotGenerator, CxCyPlotGenerator
from dataContainer import DataContainer
from dataPoint import DataPoint

import listParser

class HtmlReportGenerator:
    def __init__(self):
        self.observersList = []

        self.htmlHead = '''
        <html lang="pl">
        <head>
            <meta charset="UTF-8">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 20px;
                }
                .table-container {
                    width: 80%;
                    margin: auto;
                    padding: 10px;
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    background-color: #f9f9f9;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    table-layout: fixed;
                }
                th, td {
                    padding: 12px;
                    text-align: center;
                    border: 1px solid #ddd;
                    box-sizing: border-box;
                }
                th {
                    background-color: #f2f2f2;
                }
                td img {
                    width: auto;
                    height: auto;
                    max-height: 50vh;
                }
            </style>
        </head>
        <body>
        '''
        self.htmlEnd = '''
        </body>
        </html>
        '''

    def generateHtmlReport(self, measurementsDict:dict[str:DataContainer], site:int, orderBy:str, selectedLimits:str, isValuesInLimitsEnabled:bool) -> str:
        def dequeAndUpdateProgressBar(queue):
            processedTables = 0
            while processedTables < numOfTables:
                queue.get()
                processedTables += 1
                progressPercent = int((processedTables) / numOfTables * 100)  
                self.updateObservers(progressPercent)
                time.sleep(0.1)

        maxProcesses = os.cpu_count() - 1 or 4
        chunks = self._splitMeasurementsDictToChunks(measurementsDict, maxProcesses)
        
        with multiprocessing.Manager() as manager:
            queue = manager.Queue()
            poolArgs = [(chunk, site, orderBy, selectedLimits, isValuesInLimitsEnabled, queue) for chunk in chunks]            
            numOfTables = len(measurementsDict)
            
            with multiprocessing.Pool(processes=maxProcesses) as pool:
                results = pool.starmap_async(HtmlReportGenerator._processChunk, poolArgs)  
                dequeAndUpdateProgressBar(queue)
    
                results = results.get()
                
        return self.htmlHead + '\n'.join(results) + self.htmlEnd

    def addObserver(self, instance:object):
        self.observersList.append(instance)
    
    def updateObservers(self, progressPercent:int):   
        progressPercent = progressPercent - 1 if progressPercent > 0 else 0
        for observer in self.observersList:
            try:
                QMetaObject.invokeMethod(
                    observer,
                    'updateProgressBar',
                    Qt.QueuedConnection,
                    Q_ARG(int, progressPercent)
                )
            except Exception as e:
                print(e)
    
    def _splitMeasurementsDictToChunks(self, measurementsDict:dict, numOfChunks:int) -> list[dict]:
        items = list(measurementsDict.items())
        chunk_size = len(items) // numOfChunks
        chunks = [dict(items[i * chunk_size:(i + 1) * chunk_size]) for i in range(numOfChunks)]

        if len(items) % numOfChunks:
            chunks[-1].update(items[numOfChunks * chunk_size:])
        return chunks
    
    @staticmethod
    def _processChunk(chunk:list[dict], site:str, orderBy:str, selectedLimits:str, isValuesInLimitsEnabled:bool, queue:multiprocessing.Queue) -> list[str]:
        buffer = ''
        for _, data in chunk.items():    
            queue.put(1)
            try:
                buffer += HtmlReportGenerator._generateTable(data, site, orderBy, selectedLimits, isValuesInLimitsEnabled)
            except Exception as e:
                print(data.name, e.__repr__())
        return buffer
    
    @staticmethod
    def _generateTable(data:DataContainer, site:str, orderBy:str, selectedLimits:str, isValuesInLimitsEnabled:str) -> str:
        dataPointsList = data.getData(site)
        siteNames = data.getSiteNames() if site == 'All sites' else [site]

        if data.isCxCyMeasurement():
            htmlSubtable = HtmlReportGenerator._generateCxCYTable(dataPointsList, data.name, siteNames, selectedLimits)
        else:
            htmlSubtable = HtmlReportGenerator._generateSequenceCapabilityTable(dataPointsList, data.name, siteNames, orderBy, selectedLimits, isValuesInLimitsEnabled)
        return htmlSubtable
    
    @staticmethod
    def _generateSequenceCapabilityTable(dataPointsList:list[list[DataPoint]], plotName:str, siteNames:list[str], 
                                         plotOrderBy:str, selectedLimits:str, isValuesInLimitsEnabled:bool) -> str:
        valuesList = DataContainer.getValuesFromDataPointsList(dataPointsList)
        limitsList = DataContainer.getLimitsFromDataPointsList(dataPointsList, selectedLimits)

        lowerLimit, upperLimit = limitsList[0][-1] if isinstance(limitsList, list) else limitsList
        isLogScale = upperLimit - lowerLimit > 10000
        isMergeDataList = plotOrderBy == 'Date'

        sequenceCanvas = MplCanvas()
        sequencePlotGenerator = SequencePlotGenerator(sequenceCanvas)
        sequencePlotGenerator.generatePlot(valuesList, plotName, limitsList, isLogScale, siteNames, isMergeDataList, isValuesInLimitsEnabled)
        sequencePlotBytes = HtmlReportGenerator._canvasToBytes(sequenceCanvas)

        capabilityCanvas = MplCanvas()
        capabilityPlotGenerator = CapabilityPlotGenerator(capabilityCanvas)
        capabilityPlotGenerator.generatePlot(valuesList, plotName, [lowerLimit, upperLimit], False, isValuesInLimitsEnabled)
        capabilityPlotBytes = HtmlReportGenerator._canvasToBytes(capabilityCanvas)

        processParameterCalculator = ProcessParameterCalculator()        
        flatValuesList = listParser.nestedValuesListToFlatValueList(valuesList)
        mean, sigmaOverall, pp, ppk, cp, cpk, stability = processParameterCalculator.calculate(flatValuesList, lowerLimit, upperLimit) 
        stability *= 100

        plotsHtmls = f'<td colspan="2"><img src="data:image/png;base64,{sequencePlotBytes}" width="400"></td>\n<td colspan="2"><img src="data:image/png;base64,{capabilityPlotBytes}" width="400"></td>'
        htmlSubtable = HtmlReportGenerator._fillHtmlSubtableWithData(plotName=plotName, siteNames=siteNames, plotTableHtmls=plotsHtmls, 
            lowerLimit=f'{lowerLimit:.5e}', upperLimit=f'{upperLimit:.5e}', 
            mean=f'{mean:.5e}',sigmaOverall=f'{sigmaOverall:.5e}', 
            pp=f'{pp:.5e}', ppk=f'{ppk:.5e}', 
            cp=f'{cp:.5e}', cpk=f'{cpk:.5e}', 
            stability=f'{stability:.5e}')
        return htmlSubtable
    
    @staticmethod
    def _generateCxCYTable(dataPointsList:list[list[DataPoint]], plotName:str, siteNames:list[str], selectedLimits:str):
        valuesList = DataContainer.getValuesFromDataPointsList(dataPointsList)
        siteBoundariesList = DataContainer.getLimitsFromDataPointsList(dataPointsList, selectedLimits)
        siteBoundaries = listParser.uniqueBoundaryStrings(siteBoundariesList)
        boundaryXYs = listParser.processBoundaryStrings(siteBoundaries)

        cxCyCanvas = MplCanvas()
        cxCyPlotGenerator = CxCyPlotGenerator(cxCyCanvas)
        cxCyPlotGenerator.generatePlot(valuesList, plotName, boundaryXYs, siteNames)
        cxCyPlotBytes = HtmlReportGenerator._canvasToBytes(cxCyCanvas)
        cxcyPlotHtml = f'<td colspan="4"><img src="data:image/png;base64,{cxCyPlotBytes}" width="400"></td>'

        htmlSubtable = HtmlReportGenerator._fillHtmlSubtableWithData(plotName=plotName, siteNames=siteNames, plotTableHtmls=cxcyPlotHtml, 
            lowerLimit='N/A', upperLimit='N/A', 
            mean='N/A', sigmaOverall='N/A', 
            pp='N/A', ppk='N/A', 
            cp='N/A', cpk='N/A', 
            stability='N/A')
        return htmlSubtable

    @staticmethod
    def _canvasToBytes(canvas:MplCanvas) -> bytes:
        buffer = io.BytesIO()
        canvas.savefig(buffer, format='png', bbox_inches='tight')    
        canvas.close()        
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    @staticmethod
    def _fillHtmlSubtableWithData(plotName:str, siteNames:list[str], plotTableHtmls:str, lowerLimit:str, upperLimit:str, mean:str, sigmaOverall:str,
                                  pp:str, ppk:str, cp:str, cpk:str, stability:str) -> str:
        siteStr = ', '.join(siteNames)
        htmlSubtable = f'''
        <div class="table-container">
            <table>
                <tr>
                    <th colspan="3">{plotName}</th>
                    <th>Site: {siteStr}</th>
                </tr>
                <tr>
                    {plotTableHtmls}
                </tr>
                <tr>
                    <td>LSL = {lowerLimit}</td>
                    <td>x̄ = {mean}</td>
                    <td>pp = {pp}</td>
                    <td>cp = {cp}</td>
                </tr>
                <tr>
                    <td>USL = {upperLimit}</td>
                    <td>σ = {sigmaOverall}</td>
                    <td>ppk = {ppk}</td>
                    <td>cpk = {cpk}</td>
                </tr>
                <tr>
                    <td colspan="4">Max / Min - 1 = {stability}%</td>
                </tr>
            </table>
        </div>
        </br>
        '''
        return htmlSubtable
        