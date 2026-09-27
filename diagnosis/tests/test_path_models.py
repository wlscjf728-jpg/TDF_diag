import unittest

from drsim.domain import Cell, Fault, FaultKind, Scenario
from drsim.models.reconfigurable import ReconfigurableModel
from drsim.models.two_dimensional import TwoDimensionalModel
from drsim.observations import generate_all_observations


def scenario(*faults: Fault) -> Scenario:
    return Scenario("model_case", "unit", faults, opportunity=0)


def saf0(chain: int, index: int) -> Fault:
    return Fault(Cell(chain, index), FaultKind.SAF0)


class PathModelTest(unittest.TestCase):
    def test_two_dimensional_single_fault_is_native_intersection(self):
        expected = Cell(2, 17)
        scen = scenario(saf0(2, 17))
        obs = generate_all_observations(scen)

        result = TwoDimensionalModel().diagnose(obs)

        self.assertEqual(result.suspects, frozenset({expected}))
        self.assertEqual(len(result.indications), 1)

    def test_two_dimensional_staircase_diagonal_is_non_orthogonal(self):
        expected = frozenset({Cell(0, 0), Cell(0, 1), Cell(1, 0), Cell(1, 1)})
        scen = scenario(saf0(0, 0), saf0(1, 1))
        obs = generate_all_observations(scen)

        result = TwoDimensionalModel().diagnose(obs)

        self.assertEqual(result.suspects, expected)

    def test_two_dimensional_three_fault_masking_produces_ghost_candidates(self):
        # True faults at (2, 3), (3, 2), (4, 3) must produce suspects containing ghost candidates (2, 2) and (3, 3)
        scen = scenario(saf0(2, 3), saf0(3, 2), saf0(4, 3))
        obs = generate_all_observations(scen)

        result = TwoDimensionalModel().diagnose(obs)

        self.assertTrue({Cell(2, 2), Cell(3, 3)} <= result.suspects)

    def test_reconfigurable_single_fault_finishes_in_first_stage(self):
        expected = Cell(1, 9)
        scen = scenario(saf0(1, 9))
        obs = generate_all_observations(scen)

        result = ReconfigurableModel().diagnose(obs)

        self.assertEqual(result.suspects, frozenset({expected}))
        self.assertEqual(dict(result.trace)["stage_count"], "1")

    def test_reconfigurable_uses_second_stage_for_ambiguous_multiple_faults(self):
        scen = scenario(saf0(0, 0), saf0(1, 1), saf0(2, 2))
        obs = generate_all_observations(scen)

        result = ReconfigurableModel().diagnose(obs)

        self.assertEqual(dict(result.trace)["stage_count"], "2")
        self.assertTrue({Cell(0, 0), Cell(1, 1), Cell(2, 2)} <= result.suspects)

    def test_no_detectable_fault_produces_no_indication(self):
        scen = scenario()
        obs = generate_all_observations(scen)

        result = TwoDimensionalModel().diagnose(obs)

        self.assertFalse(result.indications)
        self.assertFalse(result.suspects)


if __name__ == "__main__":
    unittest.main()

