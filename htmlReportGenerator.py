from dataContainer import DataContainer
from processCalculator import ProcessParameterCalculator

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
                    width: 100%;
                    height: auto;
                    max-width: 120px;
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
        for _, data in measurementsDict.items():
            buffer += self._generateTable(data, site)
        buffer += self.htmlEnd
        return buffer
        
    def _generateTable(self, data:DataContainer, site:int) -> str:
        title = data.name
        if site == '0':
            dataList = data.getDataFromAllSites()
        else:
            dataList = data.getDataFromSite(site)

        lowerLimit, upperLimit = data.getLimits()
        mean, sigmaOverall, pp, ppk, cp, cpk = self.processParameterCalculator.calculate(dataList, lowerLimit, upperLimit)
        
        siteStr = site if site else 'All sites'
        #<td colspan="2"><img src="obraz1.jpg" alt="Obraz 1"></td>
        #<td colspan="2"><img src="obraz2.jpg" alt="Obraz 2"></td>
        htmlSubtable = f'''
        <div class="table-container">
            <table>
                <tr>
                    <th colspan="2">{title}</th>
                    <th colspan="2">Site: {siteStr}</th>
                </tr>
                <tr>
                    <th colspan="2">a</th>
                    <th colspan="2">b</th>
                </tr>
                <tr>
                    <td>LSL: {lowerLimit}</td>
                    <td>x̄: {mean}</td>
                    <td>pp: {pp}</td>
                    <td>cp: {cp}</td>
                </tr>
                <tr>
                    <td>USL: {upperLimit}</td>
                    <td>σ: {sigmaOverall}</td>
                    <td>ppk: {ppk}</td>
                    <td>cpk: {cpk}</td>
                </tr>
            </table>
        </div>
        '''
        return htmlSubtable

