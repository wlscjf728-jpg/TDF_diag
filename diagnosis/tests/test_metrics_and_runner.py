import tempfile
import unittest
from pathlib import Path

from drsim.metrics import CaseRecord, summarize
from drsim.reporting import write_reports
from drsim.runner import run_all


def record(
    method: str,
    indication_count: int,
    suspect_count: int,
    fault_active: bool,
) -> CaseRecord:
    return CaseRecord(
        method=method,
        scenario_id=f"case_{indication_count}_{suspect_count}_{fault_active}",
        category="unit",
        fault_active=fault_active,
        fault_cells=(),
        indication_count=indication_count,
        suspect_count=suspect_count,
        case_dr=(suspect_count / indication_count) if indication_count else None,
        native_operation_count=0,
        trace=(),
    )


class MetricsAndRunnerTest(unittest.TestCase):
    def test_pooled_dr_uses_summed_cardinalities(self):
        rows = (record("m", 1, 5, True), record("m", 2, 8, True))

        self.assertEqual(summarize(rows)[0].pooled_dr, 13 / 3)

    def test_coverage_counts_all_fault_active_cases(self):
        rows = (
            record("m", 1, 5, True),
            record("m", 0, 0, True),
            record("m", 0, 0, False),
        )

        self.assertEqual(summarize(rows)[0].indication_coverage, 1 / 2)

    def test_full_runner_produces_four_rows_per_scenario(self):
        rows = run_all()

        self.assertEqual(len(rows), 72 * 4)
        self.assertEqual(len({row.method for row in rows}), 4)

    def test_reports_are_byte_deterministic(self):
        rows = run_all()
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            write_reports(rows, Path(first))
            write_reports(rows, Path(second))

            for filename in ("cases.csv", "cases.json", "summary.md"):
                self.assertEqual(
                    (Path(first) / filename).read_bytes(),
                    (Path(second) / filename).read_bytes(),
                )


    def test_summary_states_indication_semantics_and_proposed_baseline(self):
        with tempfile.TemporaryDirectory() as output:
            write_reports(run_all(), Path(output))
            summary = (Path(output) / "summary.md").read_text()

        self.assertIn("Method-Native Indication Semantics", summary)
        self.assertIn("Proposed analytical baseline: DR = Nsp = 5", summary)

    def test_model_does_not_access_ground_truth(self):
        from drsim.scenarios import build_common_suite
        from drsim.observations import generate_all_observations
        from drsim.runner import MODELS
        from drsim.domain import Scenario

        class BlockedScenario(Scenario):
            def __init__(self, scenario):
                object.__setattr__(self, "scenario_id", scenario.scenario_id)
                object.__setattr__(self, "category", scenario.category)
                object.__setattr__(self, "faults", scenario.faults)
                object.__setattr__(self, "opportunity", scenario.opportunity)
                object.__setattr__(self, "metadata", scenario.metadata)
                object.__setattr__(self, "_blocked", False)

            def __getattribute__(self, name):
                if name in ("faults", "opportunity"):
                    if object.__getattribute__(self, "_blocked"):
                        raise AttributeError(f"Access to {name} is blocked")
                return object.__getattribute__(self, name)

        scenarios = build_common_suite()
        self.assertTrue(len(scenarios) > 0)
        scenario = scenarios[0]

        wrapped = BlockedScenario(scenario)
        observations = generate_all_observations(wrapped)
        object.__setattr__(wrapped, "_blocked", True)

        for model in MODELS:
            res = model.diagnose(observations)
            self.assertIsNotNone(res)


if __name__ == "__main__":
    unittest.main()
