from drsim.domain import Cell, Fault, FaultKind, Pattern, Transition, CHAIN_COUNT, CHAIN_LENGTH

_RECON_ROTATIONS_CACHE = {}

class ScanSimulator:
    def __init__(self):
        self.grid = [[0 for _ in range(CHAIN_LENGTH)] for _ in range(CHAIN_COUNT)]
        self.faults = ()
        self.opportunity = 0

    def apply_faults_during_shift(self, faults, opportunity):
        for fault in faults:
            if fault.is_active(opportunity):
                if fault.kind == FaultKind.SAF0:
                    self.grid[fault.cell.chain][fault.cell.index] = 0
                elif fault.kind == FaultKind.SAF1:
                    self.grid[fault.cell.chain][fault.cell.index] = 1

    def load_and_capture(self, pattern, faults, opportunity):
        self.faults = faults
        self.opportunity = opportunity
        
        # Precompute active TDF map
        tdf_map = {}
        for fault in faults:
            if fault.kind == FaultKind.TDF and fault.is_active(opportunity):
                tdf_map[(fault.cell.chain, fault.cell.index)] = fault
        
        # 1. Initialize grid with launch values
        for c in range(CHAIN_COUNT):
            for i in range(CHAIN_LENGTH):
                launch_val, _ = pattern.values_at(c * CHAIN_LENGTH + i)
                self.grid[c][i] = launch_val
                
        # 2. Apply active stuck-at faults
        self.apply_faults_during_shift(faults, opportunity)
        
        # Save launch state for TDF evaluation
        launch_grid = [row[:] for row in self.grid]
        
        # 3. Capture and 4. Apply TDF faults
        for c in range(CHAIN_COUNT):
            for i in range(CHAIN_LENGTH):
                _, capture_val = pattern.values_at(c * CHAIN_LENGTH + i)
                prev_val = launch_grid[c][i]
                
                # Check for active TDF fault
                tdf_fault = tdf_map.get((c, i))
                
                if tdf_fault is not None:
                    trans = None
                    if prev_val == 0 and capture_val == 1:
                        trans = Transition.RISE
                    elif prev_val == 1 and capture_val == 0:
                        trans = Transition.FALL
                    
                    if (trans is not None 
                        and trans == tdf_fault.transition 
                        and tdf_fault.delay_ns is not None 
                        and tdf_fault.delay_ns > 5.0):
                        self.grid[c][i] = prev_val
                    else:
                        self.grid[c][i] = capture_val
                else:
                    self.grid[c][i] = capture_val
                    
        # 5. Apply active stuck-at faults again
        self.apply_faults_during_shift(faults, opportunity)

    def shift_h(self, scan_in):
        outputs = tuple(self.grid[c][CHAIN_LENGTH - 1] for c in range(CHAIN_COUNT))
        for c in range(CHAIN_COUNT):
            self.grid[c] = [scan_in[c]] + self.grid[c][:-1]
        self.apply_faults_during_shift(self.faults, self.opportunity)
        return outputs

    def shift_v(self, scan_in):
        outputs = tuple(self.grid[CHAIN_COUNT - 1])
        for row in range(CHAIN_COUNT - 1, 0, -1):
            self.grid[row] = self.grid[row - 1]
        self.grid[0] = list(scan_in)
        self.apply_faults_during_shift(self.faults, self.opportunity)
        return outputs

    def shift_reverse(self, scan_in):
        outputs = tuple(self.grid[c][0] for c in range(CHAIN_COUNT))
        for c in range(CHAIN_COUNT):
            self.grid[c] = self.grid[c][1:] + [scan_in[c]]
        self.apply_faults_during_shift(self.faults, self.opportunity)
        return outputs

    def _control_for_boundary(self, boundary: int) -> int:
        if boundary % 25 == 0:
            return 2
        if boundary % 5 == 0:
            return 1
        return 0

    def _get_rotations(self, index: int, config: int) -> int:
        return sum(
            1
            for boundary in range(1, index + 1)
            if config & (1 << self._control_for_boundary(boundary))
        )

    def shift_reconfigurable(self, config, scan_in):
        key = (config, CHAIN_LENGTH)
        if key in _RECON_ROTATIONS_CACHE:
            rotations = _RECON_ROTATIONS_CACHE[key]
        else:
            rotations = [0] * CHAIN_LENGTH
            curr_rot = 0
            for idx in range(1, CHAIN_LENGTH):
                if config & (1 << self._control_for_boundary(idx)):
                    curr_rot += 1
                rotations[idx] = curr_rot
            _RECON_ROTATIONS_CACHE[key] = rotations

        outputs = [0] * CHAIN_COUNT
        rot_last = rotations[CHAIN_LENGTH - 1]
        for p in range(CHAIN_COUNT):
            chain = (p - rot_last) % CHAIN_COUNT
            outputs[p] = self.grid[chain][CHAIN_LENGTH - 1]

        # In-place shift from right to left
        for idx in range(CHAIN_LENGTH - 1, 0, -1):
            rot_diff = rotations[idx] - rotations[idx - 1]
            if rot_diff == 0:
                for c in range(CHAIN_COUNT):
                    self.grid[c][idx] = self.grid[c][idx - 1]
            else:
                old_col = [self.grid[c][idx - 1] for c in range(CHAIN_COUNT)]
                for c in range(CHAIN_COUNT):
                    self.grid[c][idx] = old_col[(c + rot_diff) % CHAIN_COUNT]

        # Shift in scan_in at column 0
        for c in range(CHAIN_COUNT):
            self.grid[c][0] = scan_in[c]

        self.apply_faults_during_shift(self.faults, self.opportunity)
        return tuple(outputs)


    def duplicate(self, failed, good):
        for i in range(CHAIN_LENGTH):
            self.grid[good][i] = self.grid[failed][i]
        self.apply_faults_during_shift(self.faults, self.opportunity)



