import csv
import json
import tempfile
import unittest
from pathlib import Path

from run_two_dimensional_paper import derive_trial_seed
from run_two_dimensional_paper_intermittent import (
    active_fault_ids,
    generate_intermittent_faults,
    run_sweep,
)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class PaperTwoDimensionalIntermittentTest(unittest.TestCase):
    def test_fault_schedule_matches_v2_random_call_order(self):
        seed = derive_trial_seed("Intermittent", 5, 0)
        self.assertEqual(seed, 2707017165)
        faults = generate_intermittent_faults(5, seed)
        self.assertEqual([fault.cell_id for fault in faults], [1854, 4467, 781, 593, 4524])
        self.assertEqual(faults[0].kind, "TDF")
        self.assertEqual(faults[0].direction, "rise")
        self.assertAlmostEqual(faults[0].delay_ns, 6.590799884, places=9)
        self.assertEqual(faults[0].active_opportunities, frozenset({0, 4, 7, 8, 11}))
        self.assertEqual(faults[1].active_opportunities, frozenset({0, 1, 2, 5, 6, 7, 9, 11}))

    def test_active_fault_ids_follow_each_opportunity(self):
        faults = generate_intermittent_faults(5, derive_trial_seed("Intermittent", 5, 0))
        self.assertEqual(active_fault_ids(faults, 0), frozenset({1854, 4467, 781, 593, 4524}))
        self.assertEqual(active_fault_ids(faults, 3), frozenset())
        self.assertEqual(active_fault_ids(faults, 10), frozenset({781, 4524}))

    def test_stale_checkpoint_does_not_duplicate_opportunity_rows(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            run_sweep(("square71",), (5,), 2, out)
            raw = out / "intermittent_raw.csv"
            before = raw.read_bytes()
            self.assertEqual(len(read_csv(raw)), 24)
            (out / "intermittent_checkpoint.json").write_text(json.dumps({"square71": {"5": 0}}))
            run_sweep(("square71",), (5,), 2, out)
            self.assertEqual(raw.read_bytes(), before)
            rows = read_csv(raw)
            keys = {(r["Topology"], r["InjectedFaultCount"], r["Trial"], r["Opportunity"]) for r in rows}
            self.assertEqual(len(keys), 24)

    def test_outputs_and_both_summaries_are_deterministic(self):
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            run_sweep(("square71", "legacy5x1000"), (5,), 2, Path(left))
            run_sweep(("square71", "legacy5x1000"), (5,), 2, Path(right))
            for filename in (
                "intermittent_raw.csv",
                "intermittent_summary_by_injected.csv",
                "intermittent_summary_by_active.csv",
            ):
                self.assertEqual((Path(left) / filename).read_bytes(), (Path(right) / filename).read_bytes())
            raw = read_csv(Path(left) / "intermittent_raw.csv")
            self.assertEqual(len(raw), 48)
            self.assertEqual(sum(int(row["FalseNegatives"]) for row in raw), 0)
            injected = read_csv(Path(left) / "intermittent_summary_by_injected.csv")
            self.assertEqual(len(injected), 2)
            for row in injected:
                matching = [r for r in raw if r["Topology"] == row["Topology"]]
                active = [r for r in matching if int(r["ActiveFaultCount"]) > 0]
                self.assertEqual(int(row["Opportunities"]), len(matching))
                self.assertEqual(int(row["ActiveOpportunities"]), len(active))
                expected = sum(float(r["Precision"]) for r in active) / len(active)
                self.assertAlmostEqual(float(row["MeanPrecision"]), expected, places=11)


if __name__ == "__main__":
    unittest.main()
