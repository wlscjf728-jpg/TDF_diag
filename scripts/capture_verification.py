#!/usr/bin/env python3
"""Record unit tests and compare fresh smoke/RTL results with archived data."""
import csv
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def rows(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))

def main():
    out=ROOT/'evidence/verification'; out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy(); env['PYTHONPATH']=str(ROOT/'diagnosis')
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','diagnosis/tests','-v'],
        cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True)
    (out/'python_tests.txt').write_text(result.stdout)
    tests=int(re.search(r'Ran (\d+) tests',result.stdout)[1])
    suites=[]
    for name in ['logger','permanent','intermittent','core','grouping','compact']:
        source=ROOT/'build'/name/'run.log'
        log=source.read_text()
        if 'PASS' not in log or re.search(r'\bFAIL(?:ED)?\b|\bFATAL\b',log):
            raise RuntimeError(f'RTL result not passed: {source}')
        shutil.copyfile(source,out/f'rtl_{name}.log')
        suites.append(name)
    fresh=ROOT/'build/logger/step5_compression_summary.csv'
    assert rows(fresh)==rows(ROOT/'evidence/logger/step5_compression_summary.csv')
    shutil.copyfile(fresh,out/'logger_summary.csv')
    matched=0
    for scenario in ['permanent','intermittent']:
        keys=['Trial','FaultCount','Method'] if scenario=='permanent' else ['Trial','InjectedFaultCount','Opportunity','Method']
        history={tuple(r[k] for k in keys):r for r in rows(ROOT/f'evidence/diagnosis/recalculated_v2/{scenario}_raw.csv')}
        smoke_path=ROOT/f'results/smoke/{scenario}_raw.csv'
        for row in rows(smoke_path):
            old=history[tuple(row[k] for k in keys)]
            assert row==old,(scenario,row,old)
            matched+=1
        shutil.copyfile(smoke_path,out/f'smoke_{scenario}_raw.csv')
    compiler_log=(ROOT/'build/logger/compile.log').read_text()
    version=re.search(r'Version\s+(\S+)',compiler_log)
    simulator=('VCS '+version[1]) if 'Chronologic VCS' in compiler_log and version else 'not identified in compile log'
    summary=dict(python=platform.python_version(),unit_tests_passed=tests,
        rtl_suites_passed=suites,rtl_simulator=simulator,
        fresh_logger_equals_archived=True,fresh_smoke_rows_equal_archived=matched,
        full_100_trial_sweep_rerun=False,synthesis_or_sta_rerun=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main()
