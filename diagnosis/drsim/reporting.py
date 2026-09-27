from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .metrics import CaseRecord, MetricSummary, summarize


def _case_dict(row: CaseRecord) -> dict[str, object]:
    return {
        "method": row.method,
        "scenario_id": row.scenario_id,
        "category": row.category,
        "fault_active": row.fault_active,
        "fault_cells": list(row.fault_cells),
        "indication_count": row.indication_count,
        "suspect_count": row.suspect_count,
        "case_dr": row.case_dr,
        "native_operation_count": row.native_operation_count,
        "trace": dict(row.trace),
    }


def _fmt(value: float | None) -> str:
    return "--" if value is None else f"{value:.6f}"


def _summary_table(title: str, summaries: tuple[MetricSummary, ...]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Method | Category | Pooled DR | Indication coverage | Active cases | Indicated cases | Σ|I| | Σ|S| |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summaries:
        lines.append(
            "| "
            + " | ".join(
                (
                    item.method,
                    item.category,
                    _fmt(item.pooled_dr),
                    _fmt(item.indication_coverage),
                    str(item.active_cases),
                    str(item.indicated_cases),
                    str(item.indication_sum),
                    str(item.suspect_sum),
                )
            )
            + " |"
        )
    lines.append("")
    return lines


def write_reports(records: Iterable[CaseRecord], output_dir: Path) -> None:
    rows = tuple(sorted(records, key=lambda row: (row.method, row.scenario_id)))
    output_dir.mkdir(parents=True, exist_ok=True)

    dictionaries = [_case_dict(row) for row in rows]
    with (output_dir / "cases.json").open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(dictionaries, handle, indent=2, sort_keys=True)
        handle.write("\n")

    csv_fields = (
        "method",
        "scenario_id",
        "category",
        "fault_active",
        "fault_cells",
        "indication_count",
        "suspect_count",
        "case_dr",
        "native_operation_count",
        "trace",
    )
    with (output_dir / "cases.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields, lineterminator="\n")
        writer.writeheader()
        for item in dictionaries:
            writer.writerow(
                {
                    **item,
                    "fault_cells": ";".join(item["fault_cells"]),
                    "case_dr": "" if item["case_dr"] is None else f"{item['case_dr']:.12g}",
                    "trace": json.dumps(item["trace"], sort_keys=True, separators=(",", ":")),
                }
            )

    lines = [
        "# DR Reference Comparison Results",
        "",
        "These values come from the common 5 × 72 blind-entry path-level model. Native operation counts are method-specific trace counts and are not compared as cycle-equivalent timing.",
        "",
        "Proposed analytical baseline: DR = Nsp = 5. The proposed method was already evaluated in the manuscript and is not re-simulated here.",
        "",
        "## Method-Native Indication Semantics",
        "",
        "- Data Duplication: a resolved chain/cell result is one indication; absence of any good chain produces one unresolved chip-level indication with 360 suspects.",
        "- Reconfigurable: candidates connected by the same failed path-set evidence form one final intersection region.",
        "- Reversible: each failed-chain interval bounded by the LRL/RLR first-failure observations is one indication.",
        "- Two-Dimensional: candidates connected through failed horizontal, vertical, or non-orthogonal staircase-diagonal paths form one candidate group.",
        "",
    ]
    lines.extend(_summary_table("Overall", summarize(rows)))
    lines.extend(_summary_table("By Scenario Category", summarize(rows, by_category=True)))
    with (output_dir / "summary.md").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))

