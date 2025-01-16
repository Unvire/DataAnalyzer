import io, base64, math

from mplCanvas import MplCanvas
from processCalculator import ProcessParameterCalculator
from plotGenerator import SequencePlotGenerator, CapabilityPlotGenerator
from dataContainer import DataContainer

class HtmlReportGenerator:
    def __init__(self):
        self.processParameterCalculator = ProcessParameterCalculator()

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
                    max-height: 400px
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
        buffer = self.htmlHead
        i, iEnd = 0, len(measurementsDict)
        for _, data in measurementsDict.items():
            try:
                buffer += self._generateTable(data, site)
            except Exception as e:
                print(data.name)
                print(e)
            print((i + 1) / iEnd * 100)
            i+=1
        buffer += self.htmlEnd
        return buffer
        
    def _generateTable(self, data:DataContainer, site:int) -> str:
        title = data.name
        dataList = data.getDataFromAllSites() if site == '0' else data.getDataFromSite(site)

        lowerLimit, upperLimit = data.getLimits()
        mean, sigmaOverall, pp, ppk, cp, cpk = self.processParameterCalculator.calculate(dataList, lowerLimit, upperLimit)
        
        isLogScale = upperLimit - lowerLimit > 10000
        sequencePlotBase64 = self._generatePlot('Sequence', dataList, lowerLimit, upperLimit, isLogScale)
        capabilityPlotBase64 = self._generatePlot('Capability', dataList, lowerLimit, upperLimit, isLogScale)
        
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
    
    def _generatePlot(self, plotType:str, dataList:list[float], lowerLimit:float, upperLimit:float, isLogScale:bool) -> bytes:
        plotTypeDict = {
            'Sequence': SequencePlotGenerator,
            'Capability': CapabilityPlotGenerator
        }

        canvas = MplCanvas()
        plotGenerator = plotTypeDict[plotType](canvas)
        plotGenerator.generatePlot(dataList, '', (lowerLimit, upperLimit), isLogScale)
        
        buffer = io.BytesIO()
        canvas.savefig(buffer, format='png', bbox_inches='tight')    
        canvas.close()        
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

