import io, base64, os
import multiprocessing, threading

import matplotlib
matplotlib.use('Agg')
os.environ['PYDEVD_DISABLE_FILE_VALIDATION'] = '1'

from mplCanvas import MplCanvas
from processCalculator import ProcessParameterCalculator
from plotGenerator import SequencePlotGenerator, CapabilityPlotGenerator
from dataContainer import DataContainer


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

    def generateHtmlReport(self, measurementsDict:dict[str:DataContainer], site:int) -> str:
        def monitorProgress():
            nonlocal processedTables
            while processedTables < numOfTables:
                queue.get()
                processedTables += 1
                progressPercent = int((processedTables + 1) / numOfTables * 100)
                progressPercent = 100 if progressPercent > 100 else progressPercent
                print('\t', progressPercent)
                self.updateObservers(progressPercent)
                
        maxProcesses = os.cpu_count() or 4
        chunks = self._splitMeasurementsDictToChunks(measurementsDict, maxProcesses)
        
        with multiprocessing.Manager() as manager:

            queue = manager.Queue()
            poolArgs = [(chunk, site, queue) for chunk in chunks]

            with multiprocessing.Pool(processes=maxProcesses) as pool:
                results = pool.starmap_async(HtmlReportGenerator._processChunk, poolArgs)
                
                numOfTables = len(measurementsDict)
                processedTables = 0
        
                progressThread = threading.Thread(target=monitorProgress, daemon=True)
                progressThread.start()

                results = results.get()
                progressThread.join()
        return self.htmlHead + '\n'.join(results) + self.htmlEnd

    def addObserver(self, instance:object):
        self.observersList.append(instance)
    
    def updateObservers(self, progressPercent:int):
        for observer in self.observersList:
            observer.updateProgressBar(progressPercent)
    
    def _splitMeasurementsDictToChunks(self, measurementsDict:dict, numOfChunks:int) -> list[dict]:
        items = list(measurementsDict.items())
        chunk_size = len(items) // numOfChunks
        chunks = [dict(items[i * chunk_size:(i + 1) * chunk_size]) for i in range(numOfChunks)]

        if len(items) % numOfChunks:
            chunks[-1].update(items[numOfChunks * chunk_size:])
        return chunks
    
    @staticmethod
    def _processChunk(chunk:list[dict], site:str, queue:multiprocessing.Queue) -> list[str]:
        buffer = ''
        for _, data in chunk.items():    
            queue.put(1)
            try:
                buffer += HtmlReportGenerator._generateTable(data, site)
            except Exception:
                pass
        return buffer
    
    @staticmethod
    def _generateTable(data:DataContainer, site:int) -> str:
        title = data.name
        dataList = data.getDataFromAllSites() if site == '0' else data.getDataFromSite(site)

        lowerLimit, upperLimit = data.getLimits()        
        processParameterCalculator = ProcessParameterCalculator()
        mean, sigmaOverall, pp, ppk, cp, cpk = processParameterCalculator.calculate(dataList, lowerLimit, upperLimit)
        
        isLogScale = upperLimit - lowerLimit > 10000
        sequencePlotBase64 = HtmlReportGenerator._generatePlot('Sequence', dataList, lowerLimit, upperLimit, isLogScale)
        capabilityPlotBase64 = HtmlReportGenerator._generatePlot('Capability', dataList, lowerLimit, upperLimit, isLogScale)
        
        siteStr = site if site != '0' else 'All sites'
        htmlSubtable = f'''
        <div class="table-container">
            <table>
                <tr>
                    <th colspan="3">{title}</th>
                    <th>Site: {siteStr}</th>
                </tr>
                <tr>
                    <td colspan="2"><img src="data:image/png;base64,{sequencePlotBase64}" width="400"></td>
                    <td colspan="2"><img src="data:image/png;base64,{capabilityPlotBase64}" width="400"></td>
                </tr>
                <tr>
                    <td>LSL = {lowerLimit:.5e}</td>
                    <td>x̄ = {mean:.5e}</td>
                    <td>pp = {pp:.5e}</td>
                    <td>cp = {cp:.5e}</td>
                </tr>
                <tr>
                    <td>USL = {upperLimit:.5e}</td>
                    <td>σ = {sigmaOverall:.5e}</td>
                    <td>ppk = {ppk:.5e}</td>
                    <td>cpk = {cpk:.5e}</td>
                </tr>
            </table>
        </div>
        </br>
        '''
        return htmlSubtable
    
    @staticmethod
    def _generatePlot(plotType:str, dataList:list[float], lowerLimit:float, upperLimit:float, isLogScale:bool) -> bytes:
        plotTypeDict = {
            'Sequence': SequencePlotGenerator,
            'Capability': CapabilityPlotGenerator
        }

        canvas = MplCanvas(isUsePyPlot=False)
        plotGenerator = plotTypeDict[plotType](canvas)
        plotGenerator.generatePlot(dataList, '', (lowerLimit, upperLimit), isLogScale)
        
        buffer = io.BytesIO()
        canvas.savefig(buffer, format='png', bbox_inches='tight')    
        canvas.close()        
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
