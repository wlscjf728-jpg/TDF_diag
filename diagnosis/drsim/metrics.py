from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CaseRecord:
    method: str
    scenario_id: str
    category: str
    fault_active: bool
    fault_cells: tuple[str, ...]
    indication_count: int
    suspect_count: int
    case_dr: float | None
    native_operation_count: int
    trace: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class MetricSummary:
    method: str
    category: str
    pooled_dr: float | None
    indication_coverage: float | None
    active_cases: int
    indicated_cases: int
    indication_sum: int
    suspect_sum: int


def _summarize_group(
    method: str, category: str, rows: tuple[CaseRecord, ...]
) -> MetricSummary:
    indicated = tuple(row for row in rows if row.indication_count > 0)
    active = tuple(row for row in rows if row.fault_active)
    indication_sum = sum(row.indication_count for row in indicated)
    suspect_sum = sum(row.suspect_count for row in indicated)
    pooled = suspect_sum / indication_sum if indication_sum else None
    covered = sum(row.indication_count > 0 for row in active)
    coverage = covered / len(active) if active else None
    return MetricSummary(
        method,
        category,
        pooled,
        coverage,
        len(active),
        covered,
        indication_sum,
        suspect_sum,
    )


def summarize(
    records: Iterable[CaseRecord], *, by_category: bool = False
) -> tuple[MetricSummary, ...]:
    groups: dict[tuple[str, str], list[CaseRecord]] = defaultdict(list)
    for row in records:
        category = row.category if by_category else "overall"
        groups[(row.method, category)].append(row)
    return tuple(
        _summarize_group(method, category, tuple(groups[(method, category)]))
        for method, category in sorted(groups)
    )

