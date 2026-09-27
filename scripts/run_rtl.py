#!/usr/bin/env python3
"""Portable launch of the original RTL testbenches, in isolated build folders."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
CASES={
    'logger':('TB_step5_compression',['step5_compact_logger.v']),
    'permanent':('TB_step3_phase12',['top_module.v']),
    'intermittent':('TB_step3_phase34',['top_module.v']),
    'core':('TB_spare_scan_top',['top_module.v']),
    'grouping':('TB_step2_phase1',['top_module.v','step2_nsp_top.v']),
    'compact':('TB_compact_production',['top_module.v','step2_nsp_top.v','compact_production_top.v']),
}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--simulator',choices=['auto','iverilog','vcs'],default='auto')
    ap.add_argument('--cases',nargs='+',choices=list(CASES),default=list(CASES))
    args=ap.parse_args()
    simulator=args.simulator
    if simulator=='auto':
        simulator='iverilog' if shutil.which('iverilog') else 'vcs'
    if not shutil.which(simulator):
        raise SystemExit('Install Icarus Verilog or configure licensed VCS on PATH.')
    for name in args.cases:
        top,files=CASES[name]
        work=ROOT/'build'/name; work.mkdir(parents=True,exist_ok=True)
        sources=[str(ROOT/'rtl'/f) for f in files]+[str(ROOT/'tb'/f'{top}.v')]
        if simulator=='iverilog':
            compile_cmd=['iverilog','-g2012','-s',top,'-o','simv',*sources]
            run_cmd=['vvp','simv']
        else:
            compile_cmd=['vcs','-full64','-sverilog','-top',top,*sources,'-o','simv']
            run_cmd=['./simv']
        env=os.environ.copy(); env['LC_ALL']='C'
        for stage,cmd in [('compile',compile_cmd),('run',run_cmd)]:
            run=subprocess.run(cmd,cwd=work,env=env,text=True,stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,timeout=180)
            (work/f'{stage}.log').write_text(run.stdout)
            if run.returncode or (stage=='run' and re.search(r'\bFAIL(?:ED)?\b|\bFATAL\b',run.stdout)):
                raise SystemExit(f'{name} {stage} failed; inspect {work}/{stage}.log')
        if 'PASS' not in run.stdout:
            raise SystemExit(f'{name}: no explicit PASS marker; inspect run.log')
        print(name, ':', ' | '.join(line for line in run.stdout.splitlines() if 'PASS' in line or 'SUMMARY' in line)[-900:])

if __name__=='__main__':
    main()
