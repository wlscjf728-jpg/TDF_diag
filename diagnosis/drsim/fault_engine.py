from __future__ import annotations

from .domain import CAPTURE_MARGIN_NS, DiagnosticPath, Fault, FaultKind, Observation, Pattern, Scenario, Transition


def _sensitized(fault: Fault, launch: int, capture: int) -> bool:
    if fault.kind is FaultKind.SAF0:
        return capture == 1
    if fault.kind is FaultKind.SAF1:
        return capture == 0
    if fault.kind is FaultKind.TDF:
        if fault.delay_ns is not None and fault.delay_ns <= CAPTURE_MARGIN_NS:
            return False
        direction = Transition.RISE if (launch, capture) == (0, 1) else Transition.FALL if (launch, capture) == (1, 0) else None
        return direction is fault.transition
    return False


def observe_path(
    path: DiagnosticPath,
    pattern: Pattern,
    scenario: Scenario,
    opportunity: int,
) -> Observation:
    positions = {cell: index for index, cell in enumerate(path.cells)}
    detected = set()
    for fault in scenario.faults:
        position = positions.get(fault.cell)
        if position is None or not fault.is_active(opportunity):
            continue
        launch, capture = pattern.values_at(position)
        if _sensitized(fault, launch, capture):
            detected.add(fault.cell)
    cells = frozenset(detected)
    return Observation(path.name, bool(cells), cells)
