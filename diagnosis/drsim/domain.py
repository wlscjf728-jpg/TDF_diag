from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


CHAIN_COUNT = 5
CHAIN_LENGTH = 72
CAPTURE_MARGIN_NS = 5.0


class FaultKind(str, Enum):
    SAF0 = "SAF0"
    SAF1 = "SAF1"
    TDF = "TDF"


class Transition(str, Enum):
    RISE = "rise"
    FALL = "fall"


@dataclass(frozen=True, order=True)
class Cell:
    chain: int
    index: int

    def __post_init__(self) -> None:
        if not 0 <= self.chain < CHAIN_COUNT:
            raise ValueError(f"chain must be in [0, {CHAIN_COUNT - 1}]")
        if not 0 <= self.index < CHAIN_LENGTH:
            raise ValueError(f"index must be in [0, {CHAIN_LENGTH - 1}]")


@dataclass(frozen=True)
class Fault:
    cell: Cell
    kind: FaultKind
    transition: Transition | None = None
    delay_ns: float | None = None
    active_opportunities: frozenset[int] | None = None

    def __post_init__(self) -> None:
        if self.kind is FaultKind.TDF and self.transition is None:
            raise ValueError("TDF requires a transition direction")
        if self.kind is not FaultKind.TDF and self.transition is not None:
            raise ValueError("only TDF may specify a transition direction")

    def is_active(self, opportunity: int) -> bool:
        return self.active_opportunities is None or opportunity in self.active_opportunities

    def is_observable(self, opportunity: int) -> bool:
        if not self.is_active(opportunity):
            return False
        return not (
            self.kind is FaultKind.TDF
            and self.delay_ns is not None
            and self.delay_ns <= CAPTURE_MARGIN_NS
        )


@dataclass(frozen=True)
class Pattern:
    name: str
    launch_values: tuple[int, ...]
    capture_values: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.launch_values or not self.capture_values:
            raise ValueError("pattern values cannot be empty")
        if len(self.launch_values) != len(self.capture_values):
            raise ValueError("launch and capture lengths must match")
        if any(value not in (0, 1) for value in self.launch_values + self.capture_values):
            raise ValueError("pattern values must be binary")

    @classmethod
    def constant(cls, value: int, length: int = 1) -> Pattern:
        values = (value,) * length
        return cls(f"const{value}", values, values)

    @classmethod
    def transition(cls, launch: int, capture: int, length: int = 1) -> Pattern:
        return cls(f"{launch}{capture}", (launch,) * length, (capture,) * length)

    @classmethod
    def alternating(cls, first: int, length: int) -> Pattern:
        capture = tuple((first + index) % 2 for index in range(length))
        launch = tuple(1 - value for value in capture)
        return cls(f"alt{first}", launch, capture)

    def values_at(self, position: int) -> tuple[int, int]:
        slot = position % len(self.capture_values)
        return self.launch_values[slot], self.capture_values[slot]


@dataclass(frozen=True)
class DiagnosticPath:
    name: str
    cells: tuple[Cell, ...]
    direction: str = "forward"

    def __post_init__(self) -> None:
        if not self.cells:
            raise ValueError("diagnostic path cannot be empty")
        if self.direction not in {"forward", "reverse"}:
            raise ValueError("direction must be forward or reverse")


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    category: str
    faults: tuple[Fault, ...]
    opportunity: int
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def fault_active(self) -> bool:
        return any(fault.is_observable(self.opportunity) for fault in self.faults)


@dataclass(frozen=True)
class Observation:
    path_name: str
    failed: bool
    detected_faults: frozenset[Cell]


@dataclass(frozen=True)
class DiagnosisResult:
    indications: frozenset[str]
    suspects: frozenset[Cell]
    trace: tuple[tuple[str, str], ...]


def physical_universe() -> frozenset[Cell]:
    return frozenset(
        Cell(chain, index)
        for chain in range(CHAIN_COUNT)
        for index in range(CHAIN_LENGTH)
    )

