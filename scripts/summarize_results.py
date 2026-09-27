#!/usr/bin/env python3
"""Summarize supplied experiment data without manuscript-specific comparisons."""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).resolve().parents[1]

def read(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))

def write(out,name,rows):
    if not rows:
        raise ValueError(f'No rows for {name}')
    with (out/name).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)

def summarize(raw,scenario):
    groups=defaultdict(list)
    field='FaultCount' if scenario=='permanent' else 'InjectedFaultCount'
    for r in raw:
        groups[(r.get('Topology','5x1000'),r.get('Method','two_dimensional'),int(r[field]))].append(r)
    output=[]
    for (topology,method,count),rows in sorted(groups.items()):
        active=[r for r in rows if scenario=='permanent' or int(r['ActiveFaultCount'])>0]
        output.append(dict(scenario=scenario,topology=topology,method=method,
            fault_count=count,observations=len(rows),active_observations=len(active),
            inactive_observations=len(rows)-len(active),
            mean_suspects=mean(int(r['SuspectCount']) for r in active) if active else '',
            mean_precision=mean(float(r['Precision']) for r in active) if active else '',
            mean_recall=mean(float(r['Recall']) for r in active) if active else '',
            observations_with_false_negatives=sum(int(r['FalseNegatives'])>0 for r in active)))
    return output

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,default=ROOT/'results/summary')
    args=parser.parse_args()
    out=args.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)
    for folder,label in [('recalculated_v2','reference_methods'),('two_dimensional_paper_faithful','two_dimensional')]:
        data=[]
        for scenario in ['permanent','intermittent']:
            raw=read(ROOT/'evidence/diagnosis'/folder/f'{scenario}_raw.csv')
            data.extend(summarize(raw,scenario))
        write(out,f'{label}.csv',data)
        print(f'{label}: {len(data)} configuration groups')
    timing=read(ROOT/'evidence/timing/summary_with_scan_mux.csv')
    write(out,'timing_zero_skew.csv',[r for r in timing if float(r['lockup_skew'])==0])
    logger=read(ROOT/'evidence/logger/step5_compression_summary.csv')
    for r in logger:
        if int(r['stored_events'])!=min(int(r['detected_events']),32):
            raise ValueError(f'Unexpected logger capacity: {r["case"]}')
        if int(r['compact_log_bits'])!=16*int(r['stored_events']):
            raise ValueError(f'Unexpected record size: {r["case"]}')
        for key,denominator in [('reduction_vs_full_pct',2880),('reduction_vs_rawB_pct',288)]:
            if abs(float(r[key])-100*(1-int(r['compact_log_bits'])/denominator))>.011:
                raise ValueError(f'Unexpected reduction: {r["case"]}')
    write(out,'logger.csv',logger)
    print(f'Logger: {len(logger)} cases; 16-bit records, capacity 32')
    print(f'Summaries written to {out}')

if __name__=='__main__':
    main()
