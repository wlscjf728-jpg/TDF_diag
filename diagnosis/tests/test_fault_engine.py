import unittest

from drsim.domain import (
    Cell,
    DiagnosticPath,
    Fault,
    FaultKind,
    Pattern,
    Scenario,
    Transition,
)
from drsim.fault_engine import observe_path


def single_path(cell: Cell, direction: str = "forward") -> DiagnosticPath:
    return DiagnosticPath("p0", (cell,), direction)


def single_fault_scenario(fault: Fault) -> Scenario:
    return Scenario("case", "unit", (fault,), opportunity=0)


class FaultEngineTest(unittest.TestCase):
    def test_saf0_is_detected_only_when_one_is_applied(self):
        cell = Cell(0, 3)
        scenario = single_fault_scenario(Fault(cell, FaultKind.SAF0))

        self.assertTrue(observe_path(single_path(cell), Pattern.constant(1), scenario, 0).failed)
        self.assertFalse(observe_path(single_path(cell), Pattern.constant(0), scenario, 0).failed)

    def test_saf1_is_detected_only_when_zero_is_applied(self):
        cell = Cell(0, 4)
        scenario = single_fault_scenario(Fault(cell, FaultKind.SAF1))

        self.assertTrue(observe_path(single_path(cell), Pattern.constant(0), scenario, 0).failed)
        self.assertFalse(observe_path(single_path(cell), Pattern.constant(1), scenario, 0).failed)

    def test_tdf_requires_matching_transition_direction(self):
        cell = Cell(1, 4)
        scenario = single_fault_scenario(Fault(cell, FaultKind.TDF, Transition.RISE))

        self.assertTrue(observe_path(single_path(cell), Pattern.transition(0, 1), scenario, 0).failed)
        self.assertFalse(observe_path(single_path(cell), Pattern.transition(1, 0), scenario, 0).failed)

    def test_tdf_below_capture_margin_is_not_observed(self):
        cell = Cell(1, 7)
        scenario = single_fault_scenario(
            Fault(cell, FaultKind.TDF, Transition.RISE, delay_ns=4.0)
        )

        self.assertFalse(observe_path(single_path(cell), Pattern.transition(0, 1), scenario, 0).failed)

    def test_intermittent_fault_uses_activation_opportunity(self):
        cell = Cell(2, 5)
        fault = Fault(cell, FaultKind.SAF1, active_opportunities=frozenset({2}))
        scenario = Scenario("intermittent", "unit", (fault,), opportunity=2)

        self.assertFalse(observe_path(single_path(cell), Pattern.constant(0), scenario, 1).failed)
        self.assertTrue(observe_path(single_path(cell), Pattern.constant(0), scenario, 2).failed)

    def test_multiple_faults_are_retained_in_observation(self):
        cells = (Cell(0, 1), Cell(3, 20))
        scenario = Scenario(
            "multiple",
            "unit",
            tuple(Fault(cell, FaultKind.SAF0) for cell in cells),
            opportunity=0,
        )
        path = DiagnosticPath("multi", cells)

        observation = observe_path(path, Pattern.constant(1), scenario, 0)

        self.assertEqual(observation.detected_faults, frozenset(cells))


if __name__ == "__main__":
    unittest.main()
