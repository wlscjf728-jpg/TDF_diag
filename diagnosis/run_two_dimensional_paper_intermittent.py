#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Iterable

from drsim.models.two_dimensional_paper import diagnose
from run_two_dimensional_paper import TOPOLOGIES, _atomic_json, _serialize_ids, derive_trial_seed


DEFAULT_INJECTED_COUNTS = (5, 10, 15, 20, 25, 30, 35, 40, 45, 50)
OPPORTUNITIES = tuple(range(12))
RAW_FIELDS = (
    "Topology", "Rows", "Columns", "ActiveCells", "PaddingCells", "Trial",
    "InjectedFaultCount", "Opportunity", "ActiveFaultCount", "InjectedFaultIds", "ActiveFaultIds",
    "InjectedSAF0Count", "InjectedSAF1Count", "InjectedTDFCount",
    "ActiveSAF0Count", "ActiveSAF1Count", "ActiveTDFCount",
    "SuspectCount", "SuspectIds", "TruePositives", "FalsePositives", "FalseNegatives",
    "Precision", "Recall", "Jaccard", "Occupancy", "ExactSetFlag", "FullUniverseFlag",
    "FailedHCount", "FailedVCount", "FailedDCount",
)
INJECTED_SUMMARY_FIELDS = (
    "Topology", "Rows", "Columns", "InjectedFaultCount", "Trials", "Opportunities", "ActiveOpportunities",
    "MeanActiveFaultCount", "MeanPrecision", "MedianPrecision", "StdDevPrecision",
    "CI95PrecisionLow", "CI95PrecisionHigh", "MeanRecall", "MeanJaccard", "MeanOccupancy",
    "MeanSuspectCount", "ExactSetRate", "FullUniverseRate",
)
ACTIVE_SUMMARY_FIELDS = (
    "Topology", "Rows", "Columns", "ActiveFaultCount", "Opportunities", "MeanPrecision",
    "MedianPrecision", "StdDevPrecision", "CI95PrecisionLow", "CI95PrecisionHigh",
    "MeanRecall", "MeanJaccard", "MeanOccupancy", "MeanSuspectCount", "ExactSetRate", "FullUniverseRate",
)


@dataclass(frozen=True)
class IntermittentFaultSpec:
    cell_id: int
    kind: str
    direction: str | None
    delay_ns: float | None
    active_opportunities: frozenset[int]


def generate_intermittent_faults(injected_count: int, seed: int) -> tuple[IntermittentFaultSpec, ...]:
    if not 0 <= injected_count <= 5000:
        raise ValueError("injected_count must be between 0 and 5000")
    sampled = random.Random(seed).sample(list(range(5000)), injected_count)
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
        active = frozenset(opportunity for opportunity in OPPORTUNITIES if rng.random() < 0.5)
        faults.append(IntermittentFaultSpec(cell_id, kind, direction, delay_ns, active))
    return tuple(faults)


def active_fault_ids(faults: Iterable[IntermittentFaultSpec], opportunity: int) -> frozenset[int]:
    if opportunity not in OPPORTUNITIES:
        raise ValueError("opportunity must be in range(12)")
    return frozenset(fault.cell_id for fault in faults if opportunity in fault.active_opportunities)


def _kind_counts(faults: Iterable[IntermittentFaultSpec]) -> dict[str, int]:
    values = tuple(faults)
    return {kind: sum(fault.kind == kind for fault in values) for kind in ("SAF0", "SAF1", "TDF")}


def evaluate_opportunity(topology_name: str, injected_count: int, trial: int, opportunity: int, faults: tuple[IntermittentFaultSpec, ...]) -> dict[str, object]:
    topology = TOPOLOGIES[topology_name]
    injected = frozenset(fault.cell_id for fault in faults)
    active = active_fault_ids(faults, opportunity)
    active_specs = tuple(fault for fault in faults if fault.cell_id in active)
    result = diagnose(topology, active)
    suspects = result.suspects
    tp = len(suspects & active)
    fp = len(suspects - active)
    fn = len(active - suspects)
    precision = tp / len(suspects) if suspects else (1.0 if not active else 0.0)
    recall = tp / len(active) if active else (1.0 if not suspects else 0.0)
    union = suspects | active
    jaccard = len(suspects & active) / len(union) if union else 1.0
    injected_kinds = _kind_counts(faults)
    active_kinds = _kind_counts(active_specs)
    return {
        "Topology": topology.name,
        "Rows": topology.rows,
        "Columns": topology.columns,
        "ActiveCells": topology.active_cells,
        "PaddingCells": topology.rows * topology.columns - topology.active_cells,
        "Trial": trial,
        "InjectedFaultCount": injected_count,
        "Opportunity": opportunity,
        "ActiveFaultCount": len(active),
        "InjectedFaultIds": _serialize_ids(injected),
        "ActiveFaultIds": _serialize_ids(active),
        "InjectedSAF0Count": injected_kinds["SAF0"],
        "InjectedSAF1Count": injected_kinds["SAF1"],
        "InjectedTDFCount": injected_kinds["TDF"],
        "ActiveSAF0Count": active_kinds["SAF0"],
        "ActiveSAF1Count": active_kinds["SAF1"],
        "ActiveTDFCount": active_kinds["TDF"],
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


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _metric_summary(group: list[dict[str, str]]) -> dict[str, str]:
    precision = [float(row["Precision"]) for row in group]
    recall = [float(row["Recall"]) for row in group]
    jaccard = [float(row["Jaccard"]) for row in group]
    occupancy = [float(row["Occupancy"]) for row in group]
    suspects = [int(row["SuspectCount"]) for row in group]
    p_mean = mean(precision)
    p_std = pstdev(precision)
    half = 1.96 * p_std / math.sqrt(len(group))
    return {
        "MeanPrecision": f"{p_mean:.12f}",
        "MedianPrecision": f"{median(precision):.12f}",
        "StdDevPrecision": f"{p_std:.12f}",
        "CI95PrecisionLow": f"{max(0.0, p_mean-half):.12f}",
        "CI95PrecisionHigh": f"{min(1.0, p_mean+half):.12f}",
        "MeanRecall": f"{mean(recall):.12f}",
        "MeanJaccard": f"{mean(jaccard):.12f}",
        "MeanOccupancy": f"{mean(occupancy):.12f}",
        "MeanSuspectCount": f"{mean(suspects):.6f}",
        "ExactSetRate": f"{mean(int(row['ExactSetFlag']) for row in group):.12f}",
        "FullUniverseRate": f"{mean(int(row['FullUniverseFlag']) for row in group):.12f}",
    }


def generate_summaries(raw_path: Path, injected_path: Path, active_path: Path) -> None:
    rows = _read_rows(raw_path)
    injected_groups: dict[tuple[str, int], list[dict[str, str]]] = {}
    active_groups: dict[tuple[str, int], list[dict[str, str]]] = {}
    for row in rows:
        injected_groups.setdefault((row["Topology"], int(row["InjectedFaultCount"])), []).append(row)
        active_count = int(row["ActiveFaultCount"])
        if active_count > 0:
            active_groups.setdefault((row["Topology"], active_count), []).append(row)

    temporary = injected_path.with_suffix(injected_path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=INJECTED_SUMMARY_FIELDS, lineterminator="\n")
        writer.writeheader()
        for topology_name, injected_count in sorted(injected_groups, key=lambda item: (item[0], item[1])):
            group = injected_groups[(topology_name, injected_count)]
            active = [row for row in group if int(row["ActiveFaultCount"]) > 0]
            metrics = _metric_summary(active)
            writer.writerow({
                "Topology": topology_name,
                "Rows": group[0]["Rows"],
                "Columns": group[0]["Columns"],
                "InjectedFaultCount": injected_count,
                "Trials": len({int(row["Trial"]) for row in group}),
                "Opportunities": len(group),
                "ActiveOpportunities": len(active),
                "MeanActiveFaultCount": f"{mean(int(row['ActiveFaultCount']) for row in group):.6f}",
                **metrics,
            })
    os.replace(temporary, injected_path)

    temporary = active_path.with_suffix(active_path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ACTIVE_SUMMARY_FIELDS, lineterminator="\n")
        writer.writeheader()
        for topology_name, active_count in sorted(active_groups, key=lambda item: (item[0], item[1])):
            group = active_groups[(topology_name, active_count)]
            writer.writerow({
                "Topology": topology_name,
                "Rows": group[0]["Rows"],
                "Columns": group[0]["Columns"],
                "ActiveFaultCount": active_count,
                "Opportunities": len(group),
                **_metric_summary(group),
            })
    os.replace(temporary, active_path)


def run_sweep(topology_names: Iterable[str], injected_counts: Iterable[int], trials: int, output_dir: Path) -> None:
    names = tuple(topology_names)
    counts = tuple(injected_counts)
    if trials <= 0:
        raise ValueError("trials must be positive")
    unknown = set(names) - set(TOPOLOGIES)
    if unknown:
        raise ValueError(f"unknown topologies: {sorted(unknown)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "intermittent_raw.csv"
    checkpoint_path = output_dir / "intermittent_checkpoint.json"
    rows = _read_rows(raw_path)
    existing = {
        (row["Topology"], int(row["InjectedFaultCount"]), int(row["Trial"]), int(row["Opportunity"]))
        for row in rows
    }
    write_header = not raw_path.exists()
    with raw_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_FIELDS, lineterminator="\n")
        if write_header:
            writer.writeheader()
            handle.flush()
        for name in names:
            for injected_count in counts:
                print(f"START topology={name} injected_F={injected_count} trials={trials}", flush=True)
                for trial in range(trials):
                    seed = derive_trial_seed("Intermittent", injected_count, trial)
                    faults = generate_intermittent_faults(injected_count, seed)
                    for opportunity in OPPORTUNITIES:
                        key = (name, injected_count, trial, opportunity)
                        if key in existing:
                            continue
                        writer.writerow(evaluate_opportunity(name, injected_count, trial, opportunity, faults))
                        handle.flush()
                        existing.add(key)
                    state = {
                        topology_name: {
                            str(count): sum(
                                all((topology_name, count, completed_trial, opportunity) in existing for opportunity in OPPORTUNITIES)
                                for completed_trial in range(trials)
                            )
                            for count in counts
                        }
                        for topology_name in names
                    }
                    _atomic_json(checkpoint_path, state)
                print(f"DONE topology={name} injected_F={injected_count}", flush=True)
    final_state = {
        name: {
            str(count): sum(
                all((name, count, trial, opportunity) in existing for opportunity in OPPORTUNITIES)
                for trial in range(trials)
            )
            for count in counts
        }
        for name in names
    }
    _atomic_json(checkpoint_path, final_state)
    generate_summaries(
        raw_path,
        output_dir / "intermittent_summary_by_injected.csv",
        output_dir / "intermittent_summary_by_active.csv",
    )
    _atomic_json(output_dir / "intermittent_reproduction.json", {
        "master_seed": 42,
        "injected_fault_counts": list(counts),
        "trials": trials,
        "opportunities": list(OPPORTUNITIES),
        "activation_probability": 0.5,
        "topologies": list(names),
        "model": "paper boundary-origin alternating H/V staircase paths",
    })


def _comma_strings(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _comma_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in _comma_strings(value))


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper-faithful 2D intermittent-fault sweep")
    parser.add_argument("--topologies", default="square71,legacy5x1000")
    parser.add_argument("--injected-counts", default=",".join(map(str, DEFAULT_INJECTED_COUNTS)))
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=Path("results/two_dimensional_paper_faithful"))
    args = parser.parse_args()
    names = _comma_strings(args.topologies)
    counts = _comma_ints(args.injected_counts)
    print(f"RUN topologies={names} injected_counts={counts} trials={args.trials} opportunities=12", flush=True)
    run_sweep(names, counts, args.trials, args.output_dir)
    print("TWO_DIMENSIONAL_PAPER_INTERMITTENT_SWEEP_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
