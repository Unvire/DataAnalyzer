## About
Data analyzer processes measurement log files in a folder and displays selected measurement in a sequence plot or normal distribution plot.

## How to use
1. Select a log type in a combo box. Currently handled types are:
    - SPEA: each line has testname and cavity. Line with subtest result is given as \_, site, testName1, \_, \_, testName2, \_, \_, measuredValue, lowerLimit, upperLimit, \*\_. Example:
    ``ANL;1;C198;404;1;CAPC198 100pF 10% -10%;;PASS;1.097657e-10;7.500000e-11;1.250000e-10;F;37 307 ;583``
    ";" is a separator character. "\_" represents not needed value, "\*_" represents some number of not needed values.

    - FWK: a file has a header and measurements. Header must include line "Test Socket Index;[ID];..." which determines cavity of the test. Example:
    ``Test Socket Index;1;;;;;;;;;``    
    Line with subtest result is given as \_, testName, \*\_, measuredValue, \_, lowerLimit, upperLimit, \_. Example:
    ``13;VDD_5V;Passed;06-08-1998;01:23:17;0.039621;4.936198;[V];4.750;5.250;-``
    ";" is a separator character. "\_" represents not needed value, "\*_" represents some number of not needed values.
    
    - Column file: First line of a file is a header and below that are measurements. Example:
    ``L1-1[H];1.499917e-02;4.800180e-02;``
    ``1.682167e-02``
    ``1.671479e-02``
    ``1.664199e-02``
    First line is a header: testName;lowerLimit;upperLimit.
    Each line below header must contain 1 measurement value.
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
Install all required modules listed in requirements.txt and run mainGUI.pyw
