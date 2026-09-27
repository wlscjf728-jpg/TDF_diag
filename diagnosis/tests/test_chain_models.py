import unittest

from drsim.domain import Cell, Fault, FaultKind, Scenario
from drsim.models.data_duplication import DataDuplicationModel
from drsim.models.reversible import ReversibleModel
from drsim.observations import generate_all_observations


def scenario(*faults: Fault) -> Scenario:
    return Scenario("chain_case", "unit", faults, opportunity=0)


def saf0(chain: int, index: int) -> Fault:
    return Fault(Cell(chain, index), FaultKind.SAF0)


class ChainModelTest(unittest.TestCase):
    def test_reversible_returns_interval_between_directional_bounds(self):
        obs = generate_all_observations(
            scenario(saf0(0, 8), saf0(0, 19))
        )
        result = ReversibleModel().diagnose(obs)

        self.assertEqual(
            result.suspects,
            frozenset(Cell(0, index) for index in range(8, 20)),
        )
        self.assertEqual(len(result.indications), 1)

    def test_reversible_uses_one_interval_per_failed_chain(self):
        obs = generate_all_observations(
            scenario(saf0(0, 8), saf0(2, 19))
        )
        result = ReversibleModel().diagnose(obs)

        self.assertEqual(result.suspects, frozenset({Cell(0, 8), Cell(2, 19)}))
        self.assertEqual(len(result.indications), 2)

    def test_data_duplication_enumerates_all_blind_ordered_pairs(self):
        actual = frozenset({Cell(0, 8), Cell(2, 19)})

        obs = generate_all_observations(
            scenario(saf0(0, 8), saf0(2, 19))
        )
        result = DataDuplicationModel().diagnose(obs)

        self.assertEqual(result.suspects, actual)
        self.assertEqual(dict(result.trace)["evaluated_pair_count"], "6")
        self.assertEqual(len(result.indications), 2)

    def test_data_duplication_without_good_chain_returns_full_universe(self):
        obs = generate_all_observations(
            scenario(*(saf0(chain, chain + 1) for chain in range(5)))
        )
        result = DataDuplicationModel().diagnose(obs)

        self.assertEqual(len(result.suspects), 360)
        self.assertEqual(result.indications, frozenset({"unresolved_no_good_chain"}))

    def test_chain_models_return_no_indication_for_no_detectable_fault(self):
        empty_obs = generate_all_observations(scenario())

        self.assertFalse(ReversibleModel().diagnose(empty_obs).indications)
        self.assertFalse(DataDuplicationModel().diagnose(empty_obs).indications)


if __name__ == "__main__":
    unittest.main()
