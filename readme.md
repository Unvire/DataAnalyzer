## About
Data analyzer processes measurement log files in a folder and displays selected measurement in a sequence plot or normal distribution plot.

## How to use
1. Select a log type in a combo box. Currently handled types are:
    - SPEA: line with subtest result is given as _, site, testName1, _, _, testName2, _, _, measuredValue, lowerLimit, upperLimit, *_
    - FWK: line with subtest result is given as _, testName, *_, measuredValue, _, lowerLimit, upperLimit, _
    ";" is a separator character. "\_" represents not needed value, "\*_" represents some number of not needed values.
2. Click button "Open logs folder" and select folder with result log files.
3. After logs are processed, select a test from list. Statistical data will be displayed in the text fields and plot will be generated.
4. Plot can be adjusted with the navbar above the plot and buttons below it.
5. Tests can be filtered out with regex pattern.

## Language
Program is written with python (3.11). Used packages:
- PyQt5
- matplotlib
- numpy
- seaborn

## How to run?
Install all required modules listed in requirements.txt and run dataAnalyzerGUI.py