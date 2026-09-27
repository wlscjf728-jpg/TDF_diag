import csv
import json
import tempfile
import unittest
from pathlib import Path

from run_two_dimensional_paper import (
    derive_trial_seed,
    generate_faults,
    run_sweep,
)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class PaperTwoDimensionalRunnerTest(unittest.TestCase):
    def test_seed_and_sample_match_v2_permanent_convention(self):
        seed = derive_trial_seed("Permanent", 3, 7)
        self.assertEqual(seed, 2777342362)
        faults = generate_faults(3, seed)
        self.assertEqual([fault.cell_id for fault in faults], [4217, 3263, 279])

    def test_fault_generation_is_deterministic_and_observable(self):
        seed = derive_trial_seed("Permanent", 15, 0)
        first = generate_faults(15, seed)
        second = generate_faults(15, seed)
        self.assertEqual(first, second)
        self.assertEqual([fault.cell_id for fault in first[:10]], [4500, 4226, 3624, 3431, 942, 3985, 3573, 1729, 1346, 2315])
        self.assertTrue(all(fault.delay_ns is None or fault.delay_ns > 5.0 for fault in first))

    def test_resume_does_not_duplicate_rows_when_checkpoint_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            run_sweep(("square71",), (1, 2), 3, out)
            raw = out / "permanent_raw.csv"
            first_bytes = raw.read_bytes()
            rows = read_csv(raw)
            self.assertEqual(len(rows), 6)
            (out / "checkpoint.json").write_text(json.dumps({"square71": {"1": 0, "2": 0}}))
            run_sweep(("square71",), (1, 2), 3, out)
            self.assertEqual(raw.read_bytes(), first_bytes)
            rows = read_csv(raw)
            keys = {(r["Topology"], r["FaultCount"], r["Trial"]) for r in rows}
            self.assertEqual(len(keys), 6)

    def test_summary_is_deterministic_and_contains_expected_single_fault_metrics(self):
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            run_sweep(("square71", "legacy5x1000"), (1, 3), 4, Path(left))
            run_sweep(("square71", "legacy5x1000"), (1, 3), 4, Path(right))
            self.assertEqual(
                (Path(left) / "permanent_raw.csv").read_bytes(),
                (Path(right) / "permanent_raw.csv").read_bytes(),
            )
            self.assertEqual(
                (Path(left) / "summary.csv").read_bytes(),
                (Path(right) / "summary.csv").read_bytes(),
            )
            rows = read_csv(Path(left) / "summary.csv")
            single = [row for row in rows if row["FaultCount"] == "1"]
            self.assertEqual(len(single), 2)
            for row in single:
                self.assertEqual(float(row["MeanPrecision"]), 1.0)
                self.assertEqual(float(row["MeanRecall"]), 1.0)
                self.assertEqual(float(row["ExactSetRate"]), 1.0)


if __name__ == "__main__":
    unittest.main()
