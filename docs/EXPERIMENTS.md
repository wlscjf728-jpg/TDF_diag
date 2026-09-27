# Experiments

Run from the repository root. Generated output stays in ignored `build/` or `results/` directories.

## Software regression

```sh
make test
```

The 57 tests cover fault activation, observations, diagnosis, metrics, scenarios and reproducible 2D sweeps. Captured output: `evidence/verification/python_tests.txt`.

## Behavioral RTL

```sh
python3 scripts/run_rtl.py
```

| Suite | Testbench | Behavior |
|---|---|---|
| core | TB_spare_scan_top | Representative 72-position, five-chain detection/readout |
| permanent | TB_step3_phase12 | Multiple permanent and transition-delay effects |
| intermittent | TB_step3_phase34 | Opportunity-dependent activation and representative subsets |
| grouping | TB_step2_phase1 | Multi-bank grouping and baseline |
| compact | TB_compact_production | OR-compressed evidence |
| logger | TB_step5_compression | Packing, reduction, capacity and overflow |

Logs: `build/<suite>/compile.log` and `run.log`. Nonzero exit, FAIL/FATAL or missing PASS markers cause failure. The recorded six-suite execution used VCS R-2020.12-SP1.

## Reference-method sweep

```sh
python3 scripts/reproduce_diagnosis.py --trials 1 --output-dir results/my-smoke
python3 scripts/reproduce_diagnosis.py --trials 100
```

Output directories must be empty to prevent checkpoint/data mixing. The model uses five 1,000-cell chains and seed 42. Permanent counts are 15,20,25,30; intermittent injected counts are 35,40,45,50.

SA0/SA1/TDF classes are equally likely. TDF delay spans 5.5–7.5 ns against a 5 ns capture margin. Intermittent sites have twelve opportunities and activation probability 0.5.

A one-trial-per-count run produces 208 rows: four permanent counts × four methods, plus four intermittent counts × twelve opportunities × four methods. Examples: `evidence/verification/smoke_*_raw.csv`.

## Separate 2D experiment

```sh
python3 diagnosis/run_two_dimensional_paper.py --topologies square71 --fault-counts 15,20,25,30,35 --trials 100 --output-dir results/2d
python3 diagnosis/run_two_dimensional_paper_intermittent.py --topologies square71 --injected-counts 35,40,45,50 --trials 100 --output-dir results/2d
```

Horizontal, vertical and diagonal observations use a 71-by-71 array with 5,000 active cells and 41 padding cells. Retain topology labels when comparing datasets.

## Summaries and integrity

```sh
make summarize
python3 scripts/verify_sources.py
```

The summary tool recomputes raw-record statistics, preserves separate timing checks, and validates logger capacity arithmetic. See [Data](DATA.md) for metric definitions.

Change RTL dimensions together with testbench widths. For software comparisons, keep topology, active-fault definition and opportunity filtering explicit. EDA scripts require external licensed setup and are not part of this quick-start regression.
