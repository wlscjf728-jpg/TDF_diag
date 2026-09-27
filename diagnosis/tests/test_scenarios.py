import unittest
from collections import Counter

from drsim.domain import Cell
from drsim.scenarios import REPRESENTATIVE_CELLS, build_common_suite


class ScenarioSuiteTest(unittest.TestCase):
    def test_representative_coordinates_match_existing_testbenches(self):
        self.assertEqual(
            REPRESENTATIVE_CELLS,
            (Cell(0, 0), Cell(3, 0), Cell(1, 35), Cell(4, 35), Cell(2, 71)),
        )

    def test_common_suite_contains_required_case_counts(self):
        counts = Counter(s.category for s in build_common_suite())

        self.assertEqual(counts["controlled_tdf"], 20)
        self.assertEqual(counts["permanent_multiple"], 4)
        self.assertEqual(counts["multiple_tdf"], 4)
        self.assertEqual(counts["intermittent_opportunity"], 12)
        self.assertEqual(counts["activation_subset"], 32)

    def test_controlled_delay_cases_use_four_and_six_ns(self):
        controlled = [s for s in build_common_suite() if s.category == "controlled_tdf"]
        delays = Counter(f.delay_ns for s in controlled for f in s.faults)

        self.assertEqual(delays, Counter({4.0: 10, 6.0: 10}))
        self.assertEqual(sum(s.fault_active for s in controlled), 10)

    def test_intermittent_schedule_matches_phase34(self):
        intermittent = [
            s for s in build_common_suite() if s.category == "intermittent_opportunity"
        ]
        active_cells = [
            frozenset(f.cell for f in s.faults if f.is_active(s.opportunity))
            for s in intermittent
        ]
        expected_masks = (0, 1, 5, 4, 0, 18, 16, 2, 0, 12, 8, 0)
        expected = [
            frozenset(REPRESENTATIVE_CELLS[i] for i in range(5) if mask & (1 << i))
            for mask in expected_masks
        ]

        self.assertEqual(active_cells, expected)

    def test_suite_is_deterministic(self):
        self.assertEqual(build_common_suite(), build_common_suite())


if __name__ == "__main__":
    unittest.main()
