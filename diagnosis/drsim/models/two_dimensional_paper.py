from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


PathLabel = tuple[str, int]


@dataclass(frozen=True)
class Topology:
    name: str
    rows: int
    columns: int
    active_cells: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("topology name cannot be empty")
        if self.rows <= 0 or self.columns <= 0:
            raise ValueError("topology dimensions must be positive")
        if not 0 < self.active_cells <= self.rows * self.columns:
            raise ValueError("active_cells must fit inside the topology")

    def active_ids(self) -> range:
        return range(self.active_cells)

    def to_coord(self, cell_id: int) -> tuple[int, int]:
        if not 0 <= cell_id < self.active_cells:
            raise ValueError(f"cell_id {cell_id} is outside the active universe")
        return divmod(cell_id, self.columns)

    def to_id(self, row: int, column: int) -> int:
        if not (0 <= row < self.rows and 0 <= column < self.columns):
            raise ValueError(f"coordinate ({row}, {column}) is outside the topology")
        return row * self.columns + column

    def is_active(self, row: int, column: int) -> bool:
        if not (0 <= row < self.rows and 0 <= column < self.columns):
            return False
        return self.to_id(row, column) < self.active_cells


@dataclass(frozen=True)
class Paper2DDiagnosis:
    suspects: frozenset[int]
    failed_h: frozenset[int]
    failed_v: frozenset[int]
    failed_d: frozenset[PathLabel]


def staircase_paths(row: int, column: int) -> frozenset[PathLabel]:
    if row < 0 or column < 0:
        raise ValueError("row and column must be non-negative")
    if row > column:
        delta = row - column
        return frozenset({("H", delta - 1), ("H", delta)})
    if column > row:
        delta = column - row
        return frozenset({("V", delta - 1), ("V", delta)})
    return frozenset({("H", 0), ("V", 0)})


def symbolic_staircase_memberships(topology: Topology) -> dict[int, frozenset[PathLabel]]:
    return {
        cell_id: staircase_paths(*topology.to_coord(cell_id))
        for cell_id in topology.active_ids()
    }


def diagnose(topology: Topology, fault_ids: Iterable[int]) -> Paper2DDiagnosis:
    faults = frozenset(fault_ids)
    for cell_id in faults:
        topology.to_coord(cell_id)
    if not faults:
        return Paper2DDiagnosis(frozenset(), frozenset(), frozenset(), frozenset())

    coordinates = {cell_id: topology.to_coord(cell_id) for cell_id in faults}
    failed_h = frozenset(row for row, _ in coordinates.values())
    failed_v = frozenset(column for _, column in coordinates.values())
    failed_d = frozenset(
        path
        for row, column in coordinates.values()
        for path in staircase_paths(row, column)
    )

    suspects = frozenset(
        cell_id
        for cell_id in topology.active_ids()
        for row, column in (topology.to_coord(cell_id),)
        if row in failed_h
        and column in failed_v
        and staircase_paths(row, column) <= failed_d
    )
    return Paper2DDiagnosis(suspects, failed_h, failed_v, failed_d)
