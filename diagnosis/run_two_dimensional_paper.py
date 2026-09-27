#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Iterable

from drsim.models.two_dimensional_paper import Topology, diagnose


MASTER_SEED = 42
DEFAULT_FAULT_COUNTS = (1, 2, 3, 4, 5, 10, 15, 20, 25, 30, 35, 50, 100)
TOPOLOGIES = {
    "square71": Topology("square71", 71, 71, 5000),
    "legacy5x1000": Topology("legacy5x1000", 5, 1000, 5000),
}
RAW_FIELDS = (
    "Topology", "Rows", "Columns", "ActiveCells", "PaddingCells",
    "Trial", "FaultCount", "FaultIds", "SAF0Count", "SAF1Count", "TDFCount",
    "SuspectCount", "SuspectIds", "TruePositives", "FalsePositives", "FalseNegatives",
    "Precision", "Recall", "Jaccard", "Occupancy", "ExactSetFlag", "FullUniverseFlag",
    "FailedHCount", "FailedVCount", "FailedDCount",
)
SUMMARY_FIELDS = (
    "Topology", "Rows", "Columns", "FaultCount", "Trials",
    "MeanPrecision", "MedianPrecision", "StdDevPrecision", "CI95PrecisionLow", "CI95PrecisionHigh",
    "MeanRecall", "MeanJaccard", "MeanOccupancy", "MeanSuspectCount", "ExactSetRate", "FullUniverseRate",
)


@dataclass(frozen=True)
class FaultSpec:
    cell_id: int
    kind: str
    direction: str | None = None
    delay_ns: float | None = None


def derive_trial_seed(scenario_type: str, fault_count: int, trial: int) -> int:
    text = f"master_{MASTER_SEED}_{scenario_type}_F_{fault_count}_trial_{trial}"
    return int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32)


def generate_faults(fault_count: int, seed: int) -> tuple[FaultSpec, ...]:
    if not 0 <= fault_count <= 5000:
        raise ValueError("fault_count must be between 0 and 5000")
    sampled = random.Random(seed).sample(list(range(5000)), fault_count)
    rng = random.Random(seed)
    faults = []
    for cell_id in sampled:
        kind = rng.choice(("SAF0", "SAF1", "TDF"))
        if kind == "TDF":
            direction = rng.choice(("rise", "fall"))
            delay_ns = rng.uniform(5.5, 7.5)
        else:
            direction = None
            delay_ns = None
        faults.append(FaultSpec(cell_id, kind, direction, delay_ns))
    return tuple(faults)


def _serialize_ids(ids: Iterable[int]) -> str:
    return ";".join(str(cell_id) for cell_id in sorted(ids))


def evaluate_trial(topology: Topology, fault_count: int, trial: int) -> dict[str, object]:
    seed = derive_trial_seed("Permanent", fault_count, trial)
    faults = generate_faults(fault_count, seed)
    active = frozenset(fault.cell_id for fault in faults)
    result = diagnose(topology, active)
    suspects = result.suspects
    tp = len(suspects & active)
    fp = len(suspects - active)
    fn = len(active - suspects)
    precision = tp / len(suspects) if suspects else (1.0 if not active else 0.0)
    recall = tp / len(active) if active else (1.0 if not suspects else 0.0)
    union = suspects | active
    jaccard = len(suspects & active) / len(union) if union else 1.0
    kinds = {kind: sum(fault.kind == kind for fault in faults) for kind in ("SAF0", "SAF1", "TDF")}
    return {
        "Topology": topology.name,
        "Rows": topology.rows,
        "Columns": topology.columns,
        "ActiveCells": topology.active_cells,
        "PaddingCells": topology.rows * topology.columns - topology.active_cells,
        "Trial": trial,
        "FaultCount": fault_count,
        "FaultIds": _serialize_ids(active),
        "SAF0Count": kinds["SAF0"],
        "SAF1Count": kinds["SAF1"],
        "TDFCount": kinds["TDF"],
        "SuspectCount": len(suspects),
        "SuspectIds": _serialize_ids(suspects),
        "TruePositives": tp,
        "FalsePositives": fp,
        "FalseNegatives": fn,
        "Precision": f"{precision:.12f}",
        "Recall": f"{recall:.12f}",
        "Jaccard": f"{jaccard:.12f}",
        "Occupancy": f"{len(suspects) / topology.active_cells:.12f}",
        "ExactSetFlag": int(suspects == active),
        "FullUniverseFlag": int(len(suspects) == topology.active_cells),
        "FailedHCount": len(result.failed_h),
        "FailedVCount": len(result.failed_v),
        "FailedDCount": len(result.failed_d),
    }


def _read_rows(raw_path: Path) -> list[dict[str, str]]:
    if not raw_path.exists():
        return []
    with raw_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def generate_summary(raw_path: Path, summary_path: Path) -> None:
    rows = _read_rows(raw_path)
    groups: dict[tuple[str, int], list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault((row["Topology"], int(row["FaultCount"])), []).append(row)
    temporary = summary_path.with_suffix(summary_path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS, lineterminator="\n")
        writer.writeheader()
        for topology_name, fault_count in sorted(groups, key=lambda item: (item[0], item[1])):
            group = sorted(groups[(topology_name, fault_count)], key=lambda row: int(row["Trial"]))
            precision = [float(row["Precision"]) for row in group]
            recall = [float(row["Recall"]) for row in group]
            jaccard = [float(row["Jaccard"]) for row in group]
            occupancy = [float(row["Occupancy"]) for row in group]
            suspect_count = [int(row["SuspectCount"]) for row in group]
            p_mean = mean(precision)
            p_std = pstdev(precision)
            half = 1.96 * p_std / math.sqrt(len(group))
            writer.writerow({
                "Topology": topology_name,
                "Rows": group[0]["Rows"],
                "Columns": group[0]["Columns"],
                "FaultCount": fault_count,
                "Trials": len(group),
                "MeanPrecision": f"{p_mean:.12f}",
                "MedianPrecision": f"{median(precision):.12f}",
                "StdDevPrecision": f"{p_std:.12f}",
                "CI95PrecisionLow": f"{max(0.0, p_mean-half):.12f}",
                "CI95PrecisionHigh": f"{min(1.0, p_mean+half):.12f}",
                "MeanRecall": f"{mean(recall):.12f}",
                "MeanJaccard": f"{mean(jaccard):.12f}",
                "MeanOccupancy": f"{mean(occupancy):.12f}",
                "MeanSuspectCount": f"{mean(suspect_count):.6f}",
                "ExactSetRate": f"{mean(int(row['ExactSetFlag']) for row in group):.12f}",
                "FullUniverseRate": f"{mean(int(row['FullUniverseFlag']) for row in group):.12f}",
            })
    os.replace(temporary, summary_path)


def run_sweep(topology_names: Iterable[str], fault_counts: Iterable[int], trials: int, output_dir: Path) -> None:
    if trials <= 0:
        raise ValueError("trials must be positive")
    names = tuple(topology_names)
    counts = tuple(fault_counts)
    unknown = set(names) - set(TOPOLOGIES)
    if unknown:
        raise ValueError(f"unknown topologies: {sorted(unknown)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "permanent_raw.csv"
    checkpoint_path = output_dir / "checkpoint.json"
    existing_rows = _read_rows(raw_path)
    existing = {(row["Topology"], int(row["FaultCount"]), int(row["Trial"])) for row in existing_rows}
    write_header = not raw_path.exists()
    with raw_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_FIELDS, lineterminator="\n")
        if write_header:
            writer.writeheader()
            handle.flush()
        for name in names:
            topology = TOPOLOGIES[name]
            for fault_count in counts:
                print(f"START topology={name} F={fault_count} trials={trials}", flush=True)
                for trial in range(trials):
                    key = (name, fault_count, trial)
                    if key in existing:
                        continue
                    writer.writerow(evaluate_trial(topology, fault_count, trial))
                    handle.flush()
                    existing.add(key)
                    state = {
                        topology_name: {
                            str(count): sum((topology_name, count, t) in existing for t in range(trials))
                            for count in counts
                        }
                        for topology_name in names
                    }
                    _atomic_json(checkpoint_path, state)
                print(f"DONE topology={name} F={fault_count}", flush=True)
    final_state = {
        name: {str(count): sum((name, count, trial) in existing for trial in range(trials)) for count in counts}
        for name in names
    }
    _atomic_json(checkpoint_path, final_state)
    generate_summary(raw_path, output_dir / "summary.csv")
    metadata = {
        "master_seed": MASTER_SEED,
        "fault_counts": list(counts),
        "trials": trials,
        "topologies": {
            name: {
                "rows": TOPOLOGIES[name].rows,
                "columns": TOPOLOGIES[name].columns,
                "active_cells": TOPOLOGIES[name].active_cells,
                "padding_cells": TOPOLOGIES[name].rows * TOPOLOGIES[name].columns - TOPOLOGIES[name].active_cells,
            }
            for name in names
        },
        "model": "paper boundary-origin alternating H/V staircase paths",
    }
    _atomic_json(output_dir / "reproduction.json", metadata)


def _comma_strings(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _comma_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in _comma_strings(value))


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper-faithful 2D permanent-fault sweep")
    parser.add_argument("--topologies", default="square71,legacy5x1000")
    parser.add_argument("--fault-counts", default=",".join(map(str, DEFAULT_FAULT_COUNTS)))
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=Path("results/two_dimensional_paper_faithful"))
    args = parser.parse_args()
    names = _comma_strings(args.topologies)
    counts = _comma_ints(args.fault_counts)
    print(f"RUN topologies={names} fault_counts={counts} trials={args.trials}", flush=True)
    run_sweep(names, counts, args.trials, args.output_dir)
    print("TWO_DIMENSIONAL_PAPER_SWEEP_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
