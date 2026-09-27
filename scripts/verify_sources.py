#!/usr/bin/env python3
"""Check byte identity of curated originals; optionally verify the untouched source tree."""
import argparse
import csv
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--original-home',type=Path)
    args=parser.parse_args()
    count=0
    with (ROOT/'docs/source_manifest.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            targets=[ROOT/row['repository_path']]
            if args.original_home:
                targets.append(args.original_home/row['source_relative_to_original_home'])
            for path in targets:
                data=path.read_bytes()
                if len(data)!=int(row['source_bytes']) or hashlib.sha256(data).hexdigest()!=row['source_sha256']:
                    raise SystemExit(f'Integrity mismatch: {path}')
            count+=1
    print(f'PASS: {count} copied source files match recorded sizes and SHA-256 hashes'
          + ('; original source files also unchanged.' if args.original_home else '.'))

if __name__=='__main__':
    main()
