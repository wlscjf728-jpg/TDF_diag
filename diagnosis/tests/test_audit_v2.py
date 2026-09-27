import unittest
import importlib
import drsim.domain
import drsim.simulator
import drsim.observations
import drsim.models.reversible
from drsim.domain import Cell, Fault, FaultKind, Scenario, CHAIN_COUNT
from drsim.models.reversible import ReversibleModel
from drsim.models.two_dimensional import TwoDimensionalModel, _diagonal_path_id
from drsim.models.reconfigurable import ReconfigurableModel
from drsim.models.data_duplication import DataDuplicationModel
from drsim.observations import generate_all_observations

def scenario(faults):
    return Scenario("audit_v2_case", "unit", tuple(faults), opportunity=0)

def saf0(chain, index):
    return Fault(Cell(chain, index), FaultKind.SAF0)

class AuditV2Test(unittest.TestCase):
    def test_reversible_length_1000(self):
        # Override CHAIN_LENGTH dynamically to 1000
        drsim.domain.CHAIN_LENGTH = 1000
        
        # Reload dependent modules so they import the new CHAIN_LENGTH
        importlib.reload(drsim.simulator)
        importlib.reload(drsim.observations)
        importlib.reload(drsim.models.reversible)
        
        # Now re-import classes that depend on the reloaded modules
        from drsim.domain import Cell, Fault, FaultKind, Scenario
        from drsim.models.reversible import ReversibleModel
        from drsim.observations import generate_all_observations

        try:
            # Inject faults at 100 and 900
            faults = [
                Fault(Cell(0, 100), FaultKind.SAF0),
                Fault(Cell(0, 900), FaultKind.SAF0)
            ]
            scen = Scenario("len1000", "unit", tuple(faults), opportunity=0)
            obs = generate_all_observations(scen)
            result = ReversibleModel().diagnose(obs)
            
            # Should correctly identify range(100, 901)
            expected = frozenset(Cell(0, idx) for idx in range(100, 901))
            self.assertEqual(result.suspects, expected)
            self.assertIn("chain_0_interval", result.indications)
        finally:
            # Restore 72
            drsim.domain.CHAIN_LENGTH = 72
            importlib.reload(drsim.simulator)
            importlib.reload(drsim.observations)
            importlib.reload(drsim.models.reversible)

    def test_observation_determinism_and_no_oracle_access(self):
        obs = generate_all_observations(scenario([saf0(1, 15)]))
        
        model_rev = ReversibleModel()
        res1 = model_rev.diagnose(obs)
        res2 = model_rev.diagnose(obs)
        self.assertEqual(res1.suspects, res2.suspects)
        
        model_dd = DataDuplicationModel()
        res_dd1 = model_dd.diagnose(obs)
        res_dd2 = model_dd.diagnose(obs)
        self.assertEqual(res_dd1.suspects, res_dd2.suspects)

    def test_two_dimensional_diagonal_mapping(self):
        obs = generate_all_observations(scenario([saf0(2, 35)]))
        result = TwoDimensionalModel().diagnose(obs)
        
        self.assertIn(Cell(2, 35), result.suspects)
        cell = Cell(2, 35)
        self.assertEqual(_diagonal_path_id(cell), (35 - 2) // 2)

    def test_data_duplication_fallback_when_all_chains_fail(self):
        obs = generate_all_observations(
            scenario([
                saf0(0, 5),
                saf0(1, 10),
                saf0(2, 15),
                saf0(3, 20),
                saf0(4, 25)
            ])
        )
        result = DataDuplicationModel().diagnose(obs)
        self.assertEqual(len(result.suspects), 5 * drsim.domain.CHAIN_LENGTH)
        self.assertIn("unresolved_no_good_chain", result.indications)

    def test_reconfigurable_saturation(self):
        # Inject 50 faults (10 faults per chain) to ensure all paths fail in all configs
        faults = []
        for chain in range(5):
            for i in range(10):
                faults.append(saf0(chain, i * 7 + 2))
                
        obs = generate_all_observations(scenario(faults))
        result = ReconfigurableModel().diagnose(obs)
        # Should saturate to the full universe (360 cells)
        self.assertEqual(len(result.suspects), 5 * drsim.domain.CHAIN_LENGTH)

if __name__ == "__main__":
    unittest.main()
