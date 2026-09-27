#!/usr/bin/env python3
"""Isolated reference-method sweep with explicit topology and fault counts."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'diagnosis'))
import run_large_scale_v2 as experiment

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--trials',type=int,default=100)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'results/reference_sweep')
    args=parser.parse_args()
    if args.trials<1:
        parser.error('trials must be positive')
    out=args.output_dir.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error('output directory must be empty (prevents checkpoint/data mixing)')
    out.mkdir(parents=True,exist_ok=True)
    experiment.RESULTS_DIR=out
    experiment.CHECKPOINT_PATH=out/'config.json'
    state={'permanent':{},'intermittent':{}}
    experiment.run_sweep('Permanent',[15,20,25,30],args.trials,out/'permanent_raw.csv',state,'permanent')
    experiment.run_sweep('Intermittent',[35,40,45,50],args.trials,out/'intermittent_raw.csv',state,'intermittent')
    experiment.generate_summaries(out/'permanent_raw.csv',out/'intermittent_raw.csv',
                                  out/'summary_by_fault_count.csv',out/'summary_by_active_count.csv')
    print('Completed reference-method sweep: 5 chains x 1000 cells; see output CSVs for per-trial metrics.')

if __name__=='__main__':
    main()
