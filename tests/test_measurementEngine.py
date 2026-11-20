import time
import pandas as pd
import pytest
from src.measurementEngine import MeasurementEngine


def test_measurementEngine_unsupportedProcessor():
    engine = MeasurementEngine()
    with pytest.raises(ValueError):
        engine.setProcessorType('NonExistingProcessor')


def test_measurementEngine_speaPipeline(tmp_path):
    logContent = [
        'START;aaa;bbb;74;30101401;ADMINISTRATOR;02/25/2025;07:52:30',
        'LOT;',
        'ANL;2;****************(1);1;1;****************(1);;PASS;0.000000e+00;0.000000e+00;0.000000e+00;;;1',
        'ANL;1;R1;1;1;RES 1K;;PASS;1000.0;900.0;1100.0;ohm;1 1;1',
        'FUNC;2;LED1;2;4;LED_CXCY(0.32_0.34_0.30_0.35_0.35_0.35_0.35_0.30_0.30_0.30);;PASS;0;0;0;;',
        'SN;SN001',
        'BOARDRESULT;PASS',
        'END;PASS;01/25/2025;17:35:59',
    ]
    (tmp_path / 'TEST_LOG_20250125173559.txt').write_text('\n'.join(logContent), encoding='utf-8')

    engine = MeasurementEngine(numWorkers=1)
    engine.setProcessorType('SPEA')
    result = engine.processFolder(str(tmp_path), useMultiprocessing=False)

    assert 'R1 | RES 1K' in result
    assert 'LED1 | LED_CXCY' in result

    r1Df = result['R1 | RES 1K']
    assert isinstance(r1Df, pd.DataFrame)
    assert not MeasurementEngine.isCxCyDataFrame(r1Df)
    assert r1Df['Value'].iloc[0] == 1000.0
    assert r1Df['LSL'].iloc[0] == 900.0
    assert r1Df['USL'].iloc[0] == 1100.0
    assert r1Df['SerialNumber'].iloc[0] == 'SN001'

    ledDf = result['LED1 | LED_CXCY']
    assert MeasurementEngine.isCxCyDataFrame(ledDf)
    assert ledDf['CX'].iloc[0] == 0.32
    assert ledDf['CY'].iloc[0] == 0.34
    assert len(ledDf['Boundary'].iloc[0]) == 5


def test_measurementEngine_appendMode(tmp_path):
    folderA = tmp_path / 'batch_A'
    folderB = tmp_path / 'batch_B'
    folderA.mkdir()
    folderB.mkdir()

    def make_fwk_log(sn, val):
        return [
            'Operator;admin;;;;;;;;;',
            f'UUT Serial Number;{sn};;;;;;;;;',
            'Test Socket Index;1;;;;;;;;;',
            ';;;;;;;;;;',
            'Sequence;Step Name;Status;Date;Time;Timefromstart;Value;Units;LimitLow;Limithigh;Normal',
            f'1;Voltage;Passed;06-08-2024;01:23:06;0.31;{val};[V];4.5;5.5;-',
            'FOOTER_1',
            'FOOTER_2',
            'FOOTER_3',
        ]

    (folderA / '20250211_062707_BF_A.csv').write_text('\n'.join(make_fwk_log('SN_A', 5.01)), encoding='utf-8')
    (folderB / '20250211_062708_BF_B.csv').write_text('\n'.join(make_fwk_log('SN_B', 5.02)), encoding='utf-8')

    engine = MeasurementEngine(numWorkers=1)
    engine.setProcessorType('FWK / Ipses / BEC')

    engine.processFolder(str(folderA), isAppendTests=False, useMultiprocessing=False)
    assert len(engine.getTestDataFrame('Voltage')) == 1

    engine.processFolder(str(folderB), isAppendTests=True, useMultiprocessing=False)
    df = engine.getTestDataFrame('Voltage')
    assert len(df) == 2
    assert df['SerialNumber'].tolist() == ['SN_A', 'SN_B']


def test_measurementEngine_10000logsSingleTest(tmp_path):
    TOTAL_LOGS = 10_000
    
    log_template = (
        "Operator;tester;;;;;;;;;\n"
        "UUT Serial Number;SN_{idx:06d};;;;;;;;;\n"
        "Test Socket Index;1;;;;;;;;;\n"
        ";;;;;;;;;;\n"
        "Sequence;Step Name;Status;Date;Time;Timefromstart;Value;Units;LimitLow;Limithigh;Normal\n"
        "1;V_Core;Passed;06-08-2024;01:23:06;0.05;{val:.4f};[V];3.000;3.600;-\n"
        "FOOTER_END_1\n"
        "FOOTER_END_2\n"
        "FOOTER_END_3\n"
    )
    
    for i in range(TOTAL_LOGS):
        hh = (i // 3600) % 24
        mm = (i // 60) % 60
        ss = i % 60
        filename = f"20250211_{hh:02d}{mm:02d}{ss:02d}_BF_sample_{i}.csv"
        file_path = tmp_path / filename
        
        # Random 3.3 value
        val = 3.3 + (i % 20) * 0.01
        file_path.write_text(log_template.format(idx=i, val=val), encoding='utf-8')

    engine = MeasurementEngine()
    engine.setProcessorType('FWK / Ipses / BEC')

    result = engine.processFolder(str(tmp_path), isAppendTests=False, useMultiprocessing=True)

    assert 'V_Core' in result
    df = result['V_Core']
    
    assert isinstance(df, pd.DataFrame)
    assert len(df) == TOTAL_LOGS
    assert df['Value'].dtype == 'float64'
    assert df['LSL'].iloc[0] == 3.0
    assert df['USL'].iloc[0] == 3.6
    assert df['SerialNumber'].nunique() == TOTAL_LOGS
    
    assert df['Site'].unique().tolist() == ['1']