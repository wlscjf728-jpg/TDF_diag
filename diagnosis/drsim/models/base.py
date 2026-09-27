from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable

from ..domain import Cell, DiagnosticPath, Pattern, Scenario
from ..fault_engine import observe_path


NATIVE_SENSITIZATION_PATTERNS = (
    Pattern.constant(0),
    Pattern.constant(1),
    Pattern.transition(0, 1),
    Pattern.transition(1, 0),
)


def detectable_cells(scenario: Scenario) -> frozenset[Cell]:
    detected = set()
    for fault in scenario.faults:
        path = DiagnosticPath(f"probe_{fault.cell.chain}_{fault.cell.index}", (fault.cell,))
        if any(
            observe_path(path, pattern, scenario, scenario.opportunity).failed
            for pattern in NATIVE_SENSITIZATION_PATTERNS
        ):
            detected.add(fault.cell)
    return frozenset(detected)


def connected_indication_groups(
    candidates: Iterable[Cell],
    memberships: Callable[[Cell], frozenset[Hashable]],
) -> tuple[frozenset[Cell], ...]:
    candidates = list(candidates)
    mem_cache = {cell: memberships(cell) for cell in candidates}
    remaining = set(candidates)
    groups = []
    while remaining:
        seed = min(remaining)
        group = {seed}
        frontier = [seed]
        remaining.remove(seed)
        while frontier:
            current = frontier.pop()
            labels = mem_cache[current]
            linked = {cell for cell in remaining if labels & mem_cache[cell]}
            remaining.difference_update(linked)
            group.update(linked)
            frontier.extend(linked)
        groups.append(frozenset(group))
    return tuple(groups)


def indication_names(groups: tuple[frozenset[Cell], ...]) -> frozenset[str]:
    return frozenset(f"group_{index}" for index in range(len(groups)))

