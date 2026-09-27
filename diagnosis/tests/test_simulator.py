import unittest
from drsim.domain import Cell, Fault, FaultKind, Pattern, Transition
from drsim.simulator import ScanSimulator

class TestScanSimulator(unittest.TestCase):
    def test_initialization_and_fault_free_capture(self):
        sim = ScanSimulator()
        self.assertEqual(len(sim.grid), 5)
        for row in sim.grid:
            self.assertEqual(len(row), 72)
            self.assertTrue(all(val == 0 for val in row))
            
        pattern = Pattern.constant(1)
        sim.load_and_capture(pattern, faults=(), opportunity=0)
        for row in sim.grid:
            self.assertTrue(all(val == 1 for val in row))

    def test_saf_and_horizontal_shift_contamination(self):
        # SAF1 at chain 0, index 5
        fault = Fault(Cell(0, 5), FaultKind.SAF1)
        sim = ScanSimulator()
        
        # Load all 0s pattern
        pattern = Pattern.constant(0)
        sim.load_and_capture(pattern, faults=(fault,), opportunity=0)
        
        # Verify cell at index 5 is stuck at 1, others are 0
        self.assertEqual(sim.grid[0][5], 1)
        self.assertEqual(sim.grid[0][4], 0)
        self.assertEqual(sim.grid[0][6], 0)
        
        # Shift horizontally 3 times with scan_in = [0, 0, 0, 0, 0]
        # At each step, the stuck-at cell forces 1, so the 1 shifts downstream
        out1 = sim.shift_h([0, 0, 0, 0, 0]) # output of index 71 before shift is 0
        out2 = sim.shift_h([0, 0, 0, 0, 0])
        out3 = sim.shift_h([0, 0, 0, 0, 0])
        
        # Verify values downstream: cell 5 is stuck at 1.
        # After 3 shifts: cell 6, 7, 8 should have received the shifted 1.
        self.assertEqual(sim.grid[0][5], 1) # still 1 due to SAF
        self.assertEqual(sim.grid[0][6], 1) # shifted from 5 (shift 1)
        self.assertEqual(sim.grid[0][7], 1) # shifted from 6 (shift 2)
        self.assertEqual(sim.grid[0][8], 1) # shifted from 7 (shift 3)
        self.assertEqual(sim.grid[0][9], 0)

    def test_multiple_saf_contamination_and_masking(self):
        # SAF1 at Cell(0, 10), SAF0 at Cell(0, 15)
        f1 = Fault(Cell(0, 10), FaultKind.SAF1)
        f2 = Fault(Cell(0, 15), FaultKind.SAF0)
        sim = ScanSimulator()
        
        sim.load_and_capture(Pattern.constant(0), faults=(f1, f2), opportunity=0)
        
        # Verify initial state: Cell 10 is 1, Cell 15 is 0
        self.assertEqual(sim.grid[0][10], 1)
        self.assertEqual(sim.grid[0][15], 0)
        
        # Shift 10 times. The 1 from Cell 10 should travel towards 15.
        # But when it passes 15, it will be masked (forced to 0) by the SAF0 at 15.
        for _ in range(10):
            sim.shift_h([0]*5)
            
        # Cell 10 is still 1
        self.assertEqual(sim.grid[0][10], 1)
        # Cells 11-14 should be 1
        self.assertTrue(all(sim.grid[0][idx] == 1 for idx in range(11, 15)))
        # Cell 15 must be 0 (stuck-at)
        self.assertEqual(sim.grid[0][15], 0)
        # Cells 16+ should be 0 (the 1s were masked to 0 when passing cell 15)
        self.assertTrue(all(sim.grid[0][idx] == 0 for idx in range(16, 21)))

    def test_tdf_delay_selectivity(self):
        # TDF slow-to-rise on Cell(1, 10), delay = 4.0 ns (should pass)
        f_pass = Fault(Cell(1, 10), FaultKind.TDF, Transition.RISE, delay_ns=4.0)
        # TDF slow-to-rise on Cell(1, 20), delay = 6.0 ns (should fail)
        f_fail = Fault(Cell(1, 20), FaultKind.TDF, Transition.RISE, delay_ns=6.0)
        
        sim = ScanSimulator()
        # Transition pattern: launch = 0, capture = 1
        pattern = Pattern.transition(0, 1)
        
        sim.load_and_capture(pattern, faults=(f_pass, f_fail), opportunity=0)
        
        # Cell 10 successfully transitioned to 1
        self.assertEqual(sim.grid[1][10], 1)
        # Cell 20 failed transition, retained launch value (0)
        self.assertEqual(sim.grid[1][20], 0)

    def test_intermittent_faults(self):
        # SAF1 active only at opportunity 2
        f = Fault(Cell(2, 10), FaultKind.SAF1, active_opportunities=frozenset({2}))
        sim = ScanSimulator()
        
        # Opportunity 1: fault not active
        sim.load_and_capture(Pattern.constant(0), faults=(f,), opportunity=1)
        self.assertEqual(sim.grid[2][10], 0)
        
        # Opportunity 2: fault active
        sim.load_and_capture(Pattern.constant(0), faults=(f,), opportunity=2)
        self.assertEqual(sim.grid[2][10], 1)

    def test_vertical_shift(self):
        sim = ScanSimulator()
        # Set distinct values in grid cells for column 5:
        # grid[row][5] = row for row 0..4
        for r in range(5):
            sim.grid[r][5] = r
            
        # Shift vertically towards row 4. scan_in has 72 elements.
        scan_in = [9] * 72
        out = sim.shift_v(scan_in)
        
        # The output before shift at row 4 should be 4
        self.assertEqual(out[5], 4)
        # New values in grid at col 5 should be shifted:
        # grid[0][5] = 9, grid[1][5] = 0, grid[2][5] = 1, grid[3][5] = 2, grid[4][5] = 3
        self.assertEqual(sim.grid[0][5], 9)
        self.assertEqual(sim.grid[1][5], 0)
        self.assertEqual(sim.grid[2][5], 1)
        self.assertEqual(sim.grid[3][5], 2)
        self.assertEqual(sim.grid[4][5], 3)

    def test_reverse_shift(self):
        sim = ScanSimulator()
        # Set cell 0 of chain 1 to 1, cell 1 to 0
        sim.grid[1][0] = 1
        sim.grid[1][1] = 0
        
        scan_in = [0] * 5
        out = sim.shift_reverse(scan_in)
        
        # Read output at index 0 before shift is 1
        self.assertEqual(out[1], 1)
        # Cell 0 gets the value from Cell 1 (which was 0)
        self.assertEqual(sim.grid[1][0], 0)

    def test_reconfigurable_shift(self):
        sim = ScanSimulator()
        # Initial grid is all 0s
        sim.grid[0][4] = 1 # cell at chain 0, index 4
        
        # Shift once under config 2
        sim.shift_reconfigurable(config=2, scan_in=[0]*5)
        # Verify that the 1 from Cell(0, 4) shifted to Cell(4, 5)
        self.assertEqual(sim.grid[4][5], 1)
        self.assertEqual(sim.grid[0][5], 0)

    def test_diagonal_shift(self):
        # Diagonal shifting uses alternating H and V shifts.
        sim = ScanSimulator()
        # Put 1 in Cell(0, 0)
        sim.grid[0][0] = 1
        
        # Shift H: Cell(0, 0) value -> Cell(0, 1)
        sim.shift_h([0]*5)
        self.assertEqual(sim.grid[0][1], 1)
        
        # Shift V: Cell(0, 1) value -> Cell(1, 1)
        sim.shift_v([0]*72)
        self.assertEqual(sim.grid[1][1], 1)
        self.assertEqual(sim.grid[0][1], 0)





if __name__ == "__main__":
    unittest.main()
