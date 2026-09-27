import itertools
import unittest

from drsim.models.two_dimensional_paper import Topology, diagnose, staircase_paths


def symbolic_memberships(topology: Topology):
    grid = [[None] * topology.columns for _ in range(topology.rows)]
    memberships = [[set() for _ in range(topology.columns)] for _ in range(topology.rows)]
    for step in range(2 * (topology.rows + topology.columns)):
        if step % 2 == 0:
            for row in range(topology.rows):
                grid[row] = [("H", row)] + grid[row][:-1]
        else:
            for row in range(topology.rows - 1, 0, -1):
                grid[row] = grid[row - 1][:]
            grid[0] = [("V", column) for column in range(topology.columns)]
        for row in range(topology.rows):
            for column in range(topology.columns):
                if grid[row][column] is not None:
                    memberships[row][column].add(grid[row][column])
    return {
        topology.to_id(row, column): frozenset(memberships[row][column])
        for row in range(topology.rows)
        for column in range(topology.columns)
        if topology.is_active(row, column)
    }


def oracle_diagnose(topology: Topology, fault_ids):
    paths = symbolic_memberships(topology)
    coordinates = [topology.to_coord(cell_id) for cell_id in fault_ids]
    failed_h = {row for row, _ in coordinates}
    failed_v = {column for _, column in coordinates}
    failed_d = set().union(*(paths[cell_id] for cell_id in fault_ids))
    return frozenset(
        cell_id
        for cell_id in topology.active_ids()
        if topology.to_coord(cell_id)[0] in failed_h
        and topology.to_coord(cell_id)[1] in failed_v
        and paths[cell_id] <= failed_d
    )


class PaperTwoDimensionalTest(unittest.TestCase):
    def setUp(self):
        self.topology = Topology("paper_grid", 7, 7, 49)

    def ids(self, *coordinates):
        return frozenset(self.topology.to_id(row, column) for row, column in coordinates)

    def test_single_fault_is_exact(self):
        faults = self.ids((2, 3))
        self.assertEqual(diagnose(self.topology, faults).suspects, faults)

    def test_figure4_same_row_two_faults_are_exact(self):
        faults = self.ids((2, 1), (2, 2))
        self.assertEqual(diagnose(self.topology, faults).suspects, faults)

    def test_figure5_diagonal_paths_remove_crossed_ghosts(self):
        faults = self.ids((3, 1), (4, 2))
        self.assertEqual(diagnose(self.topology, faults).suspects, faults)

    def test_figure8_keeps_exactly_two_masked_ghosts(self):
        faults = self.ids((1, 2), (2, 1), (3, 2))
        expected = faults | self.ids((1, 1), (2, 2))
        self.assertEqual(diagnose(self.topology, faults).suspects, expected)

    def test_closed_form_paths_match_symbolic_shift_oracle(self):
        for topology in (
            Topology("square", 5, 5, 25),
            Topology("wide", 4, 7, 28),
            Topology("tall", 7, 4, 28),
        ):
            oracle = symbolic_memberships(topology)
            for cell_id in topology.active_ids():
                row, column = topology.to_coord(cell_id)
                self.assertEqual(staircase_paths(row, column), oracle[cell_id])

    def test_small_grid_one_and_two_fault_diagnosis_matches_oracle(self):
        topology = Topology("small", 4, 5, 20)
        cells = tuple(topology.active_ids())
        for count in (1, 2):
            for faults_tuple in itertools.combinations(cells, count):
                faults = frozenset(faults_tuple)
                result = diagnose(topology, faults)
                self.assertEqual(result.suspects, oracle_diagnose(topology, faults))
                self.assertTrue(faults <= result.suspects)

    def test_padding_cells_are_never_suspects(self):
        topology = Topology("padded", 3, 3, 8)
        result = diagnose(topology, frozenset({7}))
        self.assertTrue(result.suspects <= frozenset(range(8)))
        self.assertNotIn(8, result.suspects)


if __name__ == "__main__":
    unittest.main()
