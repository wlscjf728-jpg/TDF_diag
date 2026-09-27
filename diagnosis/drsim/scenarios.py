from __future__ import annotations

from itertools import product

from .domain import Cell, Fault, FaultKind, Scenario, Transition


# Exact target order used by TB_spare_scan_top.v and TB_step3_phase{12,34}.v.
REPRESENTATIVE_CELLS = (
    Cell(0, 0),
    Cell(3, 0),
    Cell(1, 35),
    Cell(4, 35),
    Cell(2, 71),
)

PERMANENT_FAULTS = (
    Fault(REPRESENTATIVE_CELLS[0], FaultKind.SAF1),
    Fault(REPRESENTATIVE_CELLS[1], FaultKind.SAF1),
    Fault(REPRESENTATIVE_CELLS[2], FaultKind.SAF0),
    Fault(REPRESENTATIVE_CELLS[3], FaultKind.SAF0),
    Fault(REPRESENTATIVE_CELLS[4], FaultKind.SAF0),
)

INTERMITTENT_MASKS = (0, 1, 5, 4, 0, 18, 16, 2, 0, 12, 8, 0)


def _controlled_tdf_cases() -> list[Scenario]:
    cases = []
    serial = 0
    for cell in REPRESENTATIVE_CELLS:
        for direction in (Transition.RISE, Transition.FALL):
            for delay in (4.0, 6.0):
                cases.append(
                    Scenario(
                        f"controlled_tdf_{serial:02d}",
                        "controlled_tdf",
                        (Fault(cell, FaultKind.TDF, direction, delay_ns=delay),),
                        opportunity=serial,
                        metadata=(("delay_ns", str(int(delay))),),
                    )
                )
                serial += 1
    return cases


def _permanent_multiple_cases() -> list[Scenario]:
    selections = ((0, 3), (2, 3), (1, 2, 4), (0, 4))
    return [
        Scenario(
            f"permanent_multiple_{number}",
            "permanent_multiple",
            tuple(PERMANENT_FAULTS[index] for index in selected),
            opportunity=number,
            metadata=(("source", "TB_step3_phase12"),),
        )
        for number, selected in enumerate(selections)
    ]


def _multiple_tdf_cases() -> list[Scenario]:
    definitions = (
        ((0, Transition.FALL, 6.0), (3, Transition.RISE, 6.0)),
        ((1, Transition.FALL, 4.0), (4, Transition.RISE, 6.0)),
        ((2, Transition.RISE, 6.0), (3, Transition.RISE, 6.0)),
        ((0, Transition.FALL, 4.0), (4, Transition.RISE, 4.0)),
    )
    return [
        Scenario(
            f"multiple_tdf_{number}",
            "multiple_tdf",
            tuple(
                Fault(REPRESENTATIVE_CELLS[index], FaultKind.TDF, direction, delay_ns=delay)
                for index, direction, delay in definition
            ),
            opportunity=number,
            metadata=(("source", "TB_step3_phase12"),),
        )
        for number, definition in enumerate(definitions)
    ]


def _intermittent_cases() -> list[Scenario]:
    active_by_fault = tuple(
        frozenset(opportunity for opportunity, mask in enumerate(INTERMITTENT_MASKS) if mask & (1 << index))
        for index in range(len(REPRESENTATIVE_CELLS))
    )
    faults = tuple(
        Fault(
            fault.cell,
            fault.kind,
            active_opportunities=active_by_fault[index],
        )
        for index, fault in enumerate(PERMANENT_FAULTS)
    )
    return [
        Scenario(
            f"intermittent_{opportunity:02d}",
            "intermittent_opportunity",
            faults,
            opportunity=opportunity,
            metadata=(("active_mask", f"{mask:05b}"),),
        )
        for opportunity, mask in enumerate(INTERMITTENT_MASKS)
    ]


def _activation_subset_cases() -> list[Scenario]:
    cases = []
    for subset, bits in enumerate(product((0, 1), repeat=5)):
        # itertools places the first coordinate in the most-significant position;
        # reverse it to match Verilog active_set[index].
        selected = tuple(index for index, active in enumerate(reversed(bits)) if active)
        cases.append(
            Scenario(
                f"activation_subset_{subset:02d}",
                "activation_subset",
                tuple(PERMANENT_FAULTS[index] for index in selected),
                opportunity=subset,
                metadata=(("active_mask", f"{subset:05b}"),),
            )
        )
    return cases


def build_common_suite() -> tuple[Scenario, ...]:
    return tuple(
        _controlled_tdf_cases()
        + _permanent_multiple_cases()
        + _multiple_tdf_cases()
        + _intermittent_cases()
        + _activation_subset_cases()
    )
