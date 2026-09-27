from __future__ import annotations

from .metrics import CaseRecord
from .models.base import detectable_cells
from .models.data_duplication import DataDuplicationModel
from .models.reconfigurable import ReconfigurableModel
from .models.reversible import ReversibleModel
from .models.two_dimensional import TwoDimensionalModel
from .observations import generate_all_observations
from .scenarios import build_common_suite


MODELS = (
    DataDuplicationModel(),
    ReconfigurableModel(),
    ReversibleModel(),
    TwoDimensionalModel(),
)


def _native_operation_count(method: str, trace: dict[str, str]) -> int:
    if method == "two_dimensional":
        return 3
    if method == "reconfigurable":
        path_sets = trace.get("path_sets", "")
        return len(path_sets.split(",")) if path_sets else 4
    if method == "reversible":
        return 2
    if method == "data_duplication":
        return 1 + int(trace.get("evaluated_pair_count", "0"))
    raise ValueError(f"unknown method: {method}")


def run_all() -> tuple[CaseRecord, ...]:
    rows = []
    for scenario in build_common_suite():
        detectable = detectable_cells(scenario)
        observations = generate_all_observations(scenario)
        for model in MODELS:
            result = model.diagnose(observations)
            if not detectable <= result.suspects:
                missing = sorted(detectable - result.suspects)
                raise ValueError(
                    f"{model.name}/{scenario.scenario_id} omits detectable faults: {missing}"
                )
            trace = dict(result.trace)
            indication_count = len(result.indications)
            suspect_count = len(result.suspects)
            rows.append(
                CaseRecord(
                    method=model.name,
                    scenario_id=scenario.scenario_id,
                    category=scenario.category,
                    fault_active=scenario.fault_active,
                    fault_cells=tuple(
                        f"{fault.cell.chain}:{fault.cell.index}:{fault.kind.value}"
                        for fault in sorted(
                            scenario.faults,
                            key=lambda item: (item.cell.chain, item.cell.index, item.kind.value),
                        )
                        if fault.is_active(scenario.opportunity)
                    ),
                    indication_count=indication_count,
                    suspect_count=suspect_count,
                    case_dr=(suspect_count / indication_count) if indication_count else None,
                    native_operation_count=_native_operation_count(model.name, trace),
                    trace=result.trace,
                )
            )
    return tuple(sorted(rows, key=lambda row: (row.method, row.scenario_id)))

