from __future__ import annotations

from drsim.domain import CHAIN_COUNT, CHAIN_LENGTH, Cell, Fault, FaultKind, Pattern, Transition, Scenario
from drsim.simulator import ScanSimulator
from drsim.models.base import NATIVE_SENSITIZATION_PATTERNS, detectable_cells

class LazyDict(dict):
    def __init__(self, factory_dict):
        self.factory_dict = factory_dict
        self.cached = {}

    def __getitem__(self, key):
        if key in self.cached:
            return self.cached[key]
        if key in self.factory_dict:
            val = self.factory_dict[key]()
            self.cached[key] = val
            return val
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        return key in self.factory_dict or key in self.cached

    def keys(self):
        return self.factory_dict.keys()


_GOLDEN_H = {}
_GOLDEN_V = {}
_GOLDEN_D = {}
_GOLDEN_RECON = {}
_GOLDEN_LRL = {}
_GOLDEN_RLR = {}
_GOLDEN_PAIRS_CACHE = {}

_H_CACHE = {}
_V_CACHE = {}
_D_CACHE = {}
_RECON_CACHE = {}
_REVERSIBLE_CACHE = {}


def clear_observations_cache():
    global _H_CACHE, _V_CACHE, _D_CACHE, _RECON_CACHE, _REVERSIBLE_CACHE
    _H_CACHE.clear()
    _V_CACHE.clear()
    _D_CACHE.clear()
    _RECON_CACHE.clear()
    _REVERSIBLE_CACHE.clear()


class LazyPairs(dict):
    def __init__(self, active_faults, opportunity):
        self.active_faults = active_faults
        self.opportunity = opportunity
        self.cached = {}

    def __bool__(self):
        return True

    def __len__(self):
        return 20

    def __getitem__(self, pair):
        if not self.active_faults:
            global _GOLDEN_PAIRS_CACHE
            if pair in _GOLDEN_PAIRS_CACHE:
                return _GOLDEN_PAIRS_CACHE[pair]
                
        if pair in self.cached:
            return self.cached[pair]
        if not (isinstance(pair, tuple) and len(pair) == 2 and 0 <= pair[0] < 5 and 0 <= pair[1] < 5):
            raise KeyError(pair)
            
        failed, good = pair
        # Simulate pair on demand
        sim = ScanSimulator()
        sim.load_and_capture(Pattern.constant(0), self.active_faults, self.opportunity)
        flush0_outputs = []
        for _ in range(CHAIN_LENGTH):
            flush0_outputs.append(sim.shift_h([0] * CHAIN_COUNT))

        sim = ScanSimulator()
        sim.load_and_capture(Pattern.constant(1), self.active_faults, self.opportunity)
        flush1_outputs = []
        for _ in range(CHAIN_LENGTH):
            flush1_outputs.append(sim.shift_h([1] * CHAIN_COUNT))

        capture_res = {}
        for pattern in NATIVE_SENSITIZATION_PATTERNS:
            sim = ScanSimulator()
            sim.load_and_capture(pattern, self.active_faults, self.opportunity)
            outputs = []
            for _ in range(CHAIN_LENGTH):
                outputs.append(sim.shift_h([0] * CHAIN_COUNT))
            capture_res[pattern.name] = tuple(outputs)

        sim = ScanSimulator()
        for c in range(CHAIN_COUNT):
            for i in range(CHAIN_LENGTH):
                sim.grid[c][i] = 1 if c == failed else 0
        sim.apply_faults_during_shift(self.active_faults, self.opportunity)
        sim.duplicate(failed, good)
        sa0_outputs = []
        for _ in range(CHAIN_LENGTH):
            sa0_outputs.append(sim.shift_h([0] * CHAIN_COUNT))

        sim = ScanSimulator()
        for c in range(CHAIN_COUNT):
            for i in range(CHAIN_LENGTH):
                sim.grid[c][i] = 0 if c == failed else 1
        sim.apply_faults_during_shift(self.active_faults, self.opportunity)
        sim.duplicate(failed, good)
        sa1_outputs = []
        for _ in range(CHAIN_LENGTH):
            sa1_outputs.append(sim.shift_h([0] * CHAIN_COUNT))

        sim = ScanSimulator()
        for c in range(CHAIN_COUNT):
            for i in range(CHAIN_LENGTH):
                if c == good or c == failed:
                    sim.grid[c][i] = 1 - (i % 2)
                else:
                    sim.grid[c][i] = 0
        sim.apply_faults_during_shift(self.active_faults, self.opportunity)

        old_grid = [row[:] for row in sim.grid]
        for i in range(CHAIN_LENGTH - 1, 0, -1):
            sim.grid[good][i] = old_grid[good][i-1]
        sim.grid[good][0] = 0

        for i in range(CHAIN_LENGTH - 1, -1, -1):
            prev_val = old_grid[failed][i]
            next_val = old_grid[failed][i-1] if i > 0 else 0
            tdf_fault = None
            for fault in self.active_faults:
                if (fault.cell.chain == failed
                    and fault.cell.index == i
                    and fault.kind == FaultKind.TDF
                    and fault.is_active(self.opportunity)
                    and fault.is_observable(self.opportunity)):
                    tdf_fault = fault
                    break
            if tdf_fault is not None:
                trans = None
                if prev_val == 0 and next_val == 1:
                    trans = Transition.RISE
                elif prev_val == 1 and next_val == 0:
                    trans = Transition.FALL
                if trans is not None and trans == tdf_fault.transition:
                    sim.grid[failed][i] = prev_val
                else:
                    sim.grid[failed][i] = next_val
            else:
                sim.grid[failed][i] = next_val

        sim.apply_faults_during_shift(self.active_faults, self.opportunity)

        for i in range(CHAIN_LENGTH):
            sim.grid[good][i] = 0
        sim.apply_faults_during_shift(self.active_faults, self.opportunity)
        sim.duplicate(failed, good)

        tdf_outputs = []
        for _ in range(CHAIN_LENGTH):
            tdf_outputs.append(sim.shift_h([0] * CHAIN_COUNT))

        res = {
            "flush0": tuple(flush0_outputs),
            "flush1": tuple(flush1_outputs),
            "capture": capture_res,
            "sa0": tuple(sa0_outputs),
            "sa1": tuple(sa1_outputs),
            "tdf": tuple(tdf_outputs),
        }
        self.cached[pair] = res
        if not self.active_faults:
            _GOLDEN_PAIRS_CACHE[pair] = res
        return res

    def __contains__(self, pair):
        return isinstance(pair, tuple) and len(pair) == 2 and 0 <= pair[0] < 5 and 0 <= pair[1] < 5

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def generate_all_observations(scenario: Scenario) -> dict:
    faults = scenario.faults
    opportunity = scenario.opportunity

    # Filter active faults and make them permanent (active_opportunities = None)
    active_faults = []
    for f in faults:
        if f.is_observable(opportunity):
            v_fault = Fault(f.cell, f.kind, f.transition, f.delay_ns, active_opportunities=None)
            active_faults.append(v_fault)
    active_faults = tuple(active_faults)
    
    cache_key = (frozenset(active_faults), CHAIN_LENGTH)

    def get_two_dimensional():
        def run_h_sim(sim_faults):
            if not sim_faults:
                global _GOLDEN_H
                if CHAIN_LENGTH in _GOLDEN_H:
                    return _GOLDEN_H[CHAIN_LENGTH]
            res = {}
            for pattern in NATIVE_SENSITIZATION_PATTERNS:
                sim = ScanSimulator()
                sim.load_and_capture(pattern, sim_faults, 0)
                outputs = []
                for _ in range(CHAIN_LENGTH):
                    outputs.append(sim.shift_h([0] * CHAIN_COUNT))
                res[pattern.name] = tuple(outputs)
            if not sim_faults:
                _GOLDEN_H[CHAIN_LENGTH] = res
            return res

        def run_v_sim(sim_faults):
            if not sim_faults:
                global _GOLDEN_V
                if CHAIN_LENGTH in _GOLDEN_V:
                    return _GOLDEN_V[CHAIN_LENGTH]
            res = {}
            for pattern in NATIVE_SENSITIZATION_PATTERNS:
                sim = ScanSimulator()
                sim.load_and_capture(pattern, sim_faults, 0)
                outputs = []
                for _ in range(CHAIN_COUNT):
                    outputs.append(sim.shift_v([0] * CHAIN_LENGTH))
                res[pattern.name] = tuple(outputs)
            if not sim_faults:
                _GOLDEN_V[CHAIN_LENGTH] = res
            return res

        def run_d_sim(sim_faults):
            if not sim_faults:
                global _GOLDEN_D
                if CHAIN_LENGTH in _GOLDEN_D:
                    return _GOLDEN_D[CHAIN_LENGTH]
            res = {}
            for pattern in NATIVE_SENSITIZATION_PATTERNS:
                sim = ScanSimulator()
                sim.load_and_capture(pattern, sim_faults, 0)
                outputs = []
                for s in range(2 * CHAIN_LENGTH):
                    if s % 2 == 0:
                        out = sim.shift_h([0] * CHAIN_COUNT)
                    else:
                        out = sim.shift_v([0] * CHAIN_LENGTH)
                    outputs.append(out)
                res[pattern.name] = tuple(outputs)
            if not sim_faults:
                _GOLDEN_D[CHAIN_LENGTH] = res
            return res

        global _H_CACHE, _V_CACHE, _D_CACHE
        if cache_key in _H_CACHE:
            h_res = _H_CACHE[cache_key]
        else:
            h_res = run_h_sim(active_faults)
            _H_CACHE[cache_key] = h_res

        if cache_key in _V_CACHE:
            v_res = _V_CACHE[cache_key]
        else:
            v_res = run_v_sim(active_faults)
            _V_CACHE[cache_key] = v_res

        if cache_key in _D_CACHE:
            d_res = _D_CACHE[cache_key]
        else:
            d_res = run_d_sim(active_faults)
            _D_CACHE[cache_key] = d_res

        return {
            "H": h_res,
            "H_golden": run_h_sim(()),
            "V": v_res,
            "V_golden": run_v_sim(()),
            "D": d_res,
            "D_golden": run_d_sim(()),
        }

    def get_reconfigurable():
        def run_recon_sim(sim_faults, configs):
            if not sim_faults:
                global _GOLDEN_RECON
                if CHAIN_LENGTH in _GOLDEN_RECON:
                    return _GOLDEN_RECON[CHAIN_LENGTH]
            res = {}
            from drsim.simulator import _RECON_ROTATIONS_CACHE
            
            for config in configs:
                config_res = {}
                key = (config, CHAIN_LENGTH)
                if key in _RECON_ROTATIONS_CACHE:
                    rotations = _RECON_ROTATIONS_CACHE[key]
                else:
                    rotations = [0] * CHAIN_LENGTH
                    curr_rot = 0
                    for idx in range(1, CHAIN_LENGTH):
                        boundary = idx
                        ctrl = 2 if boundary % 25 == 0 else (1 if boundary % 5 == 0 else 0)
                        if config & (1 << ctrl):
                            curr_rot += 1
                        rotations[idx] = curr_rot
                    _RECON_ROTATIONS_CACHE[key] = rotations
                
                virtual_faults = []
                for fault in sim_faults:
                    cell = fault.cell
                    p = (cell.chain + rotations[cell.index]) % CHAIN_COUNT
                    v_cell = Cell(p, cell.index)
                    v_fault = Fault(v_cell, fault.kind, fault.transition, fault.delay_ns, fault.active_opportunities)
                    virtual_faults.append(v_fault)
                virtual_faults = tuple(virtual_faults)
                
                for pattern in NATIVE_SENSITIZATION_PATTERNS:
                    sim = ScanSimulator()
                    sim.load_and_capture(pattern, sim_faults, 0)
                    
                    v_grid = [[sim.grid[(p - rotations[idx]) % CHAIN_COUNT][idx] for idx in range(CHAIN_LENGTH)] for p in range(CHAIN_COUNT)]
                    
                    v_sim = ScanSimulator()
                    v_sim.grid = v_grid
                    v_sim.faults = virtual_faults
                    v_sim.opportunity = 0
                    
                    outputs = []
                    for _ in range(CHAIN_LENGTH):
                        outputs.append(v_sim.shift_h([0] * CHAIN_COUNT))
                    config_res[pattern.name] = tuple(outputs)
                res[config] = config_res
            if not sim_faults:
                _GOLDEN_RECON[CHAIN_LENGTH] = res
            return res

        global _RECON_CACHE
        if cache_key in _RECON_CACHE:
            recon_res = _RECON_CACHE[cache_key]
        else:
            recon_res = run_recon_sim(active_faults, range(8))
            _RECON_CACHE[cache_key] = recon_res

        return {
            "configs": recon_res,
            "configs_golden": run_recon_sim((), range(8)),
        }

    def get_reversible():
        def run_reversible_sim(sim_faults):
            if not sim_faults:
                global _GOLDEN_LRL, _GOLDEN_RLR
                if CHAIN_LENGTH in _GOLDEN_LRL and CHAIN_LENGTH in _GOLDEN_RLR:
                    return _GOLDEN_LRL[CHAIN_LENGTH], _GOLDEN_RLR[CHAIN_LENGTH]
            res_lrl = {}
            res_rlr = {}
            for pattern in NATIVE_SENSITIZATION_PATTERNS:
                # LRL
                sim = ScanSimulator()
                sim.load_and_capture(pattern, sim_faults, 0)
                outputs = []
                for _ in range(CHAIN_LENGTH):
                    outputs.append(sim.shift_h([0] * CHAIN_COUNT))
                for _ in range(CHAIN_LENGTH):
                    outputs.append(sim.shift_reverse([0] * CHAIN_COUNT))
                res_lrl[pattern.name] = tuple(outputs)

                # RLR
                sim = ScanSimulator()
                sim.load_and_capture(pattern, sim_faults, 0)
                outputs = []
                for _ in range(CHAIN_LENGTH):
                    outputs.append(sim.shift_reverse([0] * CHAIN_COUNT))
                for _ in range(CHAIN_LENGTH):
                    outputs.append(sim.shift_h([0] * CHAIN_COUNT))
                res_rlr[pattern.name] = tuple(outputs)

            if not sim_faults:
                _GOLDEN_LRL[CHAIN_LENGTH] = res_lrl
                _GOLDEN_RLR[CHAIN_LENGTH] = res_rlr
            return res_lrl, res_rlr

        global _REVERSIBLE_CACHE
        if cache_key in _REVERSIBLE_CACHE:
            lrl_faulty, rlr_faulty = _REVERSIBLE_CACHE[cache_key]
        else:
            lrl_faulty, rlr_faulty = run_reversible_sim(active_faults)
            _REVERSIBLE_CACHE[cache_key] = (lrl_faulty, rlr_faulty)

        lrl_golden, rlr_golden = run_reversible_sim(())
        return {
            "LRL": lrl_faulty,
            "LRL_golden": lrl_golden,
            "RLR": rlr_faulty,
            "RLR_golden": rlr_golden,
        }

    def get_data_duplication():
        return {
            "pairs": LazyPairs(active_faults, 0),
            "pairs_golden": LazyPairs((), 0),
        }

    return LazyDict({
        "two_dimensional": get_two_dimensional,
        "reconfigurable": get_reconfigurable,
        "reversible": get_reversible,
        "data_duplication": get_data_duplication,
    })
