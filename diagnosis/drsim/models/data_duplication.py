from __future__ import annotations

from ..domain import CHAIN_COUNT, CHAIN_LENGTH, Cell, DiagnosisResult, physical_universe


class DataDuplicationModel:
    name = "data_duplication"

    def diagnose(self, observations: dict | Scenario) -> DiagnosisResult:
        from ..domain import Scenario
        if isinstance(observations, Scenario):
            from drsim.observations import generate_all_observations
            observations = generate_all_observations(observations)

        if "data_duplication" in observations:
            obs = observations["data_duplication"]
        else:
            obs = observations

        pairs = obs.get("pairs", {})
        pairs_golden = obs.get("pairs_golden", {})

        # If empty observations (e.g. no pairs simulated at all), return no suspects
        if not pairs:
            return DiagnosisResult(
                frozenset(),
                frozenset(),
                (("failed_chains", ""), ("good_chains", ""), ("evaluated_pair_count", "0")),
            )

        failed_chains = set()
        
        # Try to use standard H-scan observations from two_dimensional to avoid simulating ref pairs
        h_obs = observations.get("two_dimensional", {}).get("H")
        h_golden = observations.get("two_dimensional", {}).get("H_golden")
        
        if h_obs and h_golden:
            for c in range(CHAIN_COUNT):
                mismatch = False
                for pattern in h_obs:
                    for t in range(len(h_obs[pattern])):
                        if h_obs[pattern][t][c] != h_golden[pattern][t][c]:
                            mismatch = True
                            break
                    if mismatch:
                        break
                if mismatch:
                    failed_chains.add(c)
        else:
            # Fallback to checking ref_pairs
            for c in range(CHAIN_COUNT):
                ref_pair = (c, 1) if c == 0 else (c, 0)
                if ref_pair not in pairs or ref_pair not in pairs_golden:
                    continue
                
                mismatch = False
                # Check flush0
                for cycle in range(CHAIN_LENGTH):
                    if pairs[ref_pair]["flush0"][cycle][c] != pairs_golden[ref_pair]["flush0"][cycle][c]:
                        mismatch = True
                        break
                if not mismatch:
                    # Check flush1
                    for cycle in range(CHAIN_LENGTH):
                        if pairs[ref_pair]["flush1"][cycle][c] != pairs_golden[ref_pair]["flush1"][cycle][c]:
                            mismatch = True
                            break
                if not mismatch:
                    # Check capture
                    for pat_name in pairs[ref_pair]["capture"]:
                        for cycle in range(CHAIN_LENGTH):
                            if pairs[ref_pair]["capture"][pat_name][cycle][c] != pairs_golden[ref_pair]["capture"][pat_name][cycle][c]:
                                mismatch = True
                                break
                        if mismatch:
                            break
                if mismatch:
                    failed_chains.add(c)

        passed_chains = set(range(CHAIN_COUNT)) - failed_chains

        if not passed_chains:
            universe = physical_universe()
            trace = (
                ("failed_chains", ",".join(map(str, sorted(failed_chains)))),
                ("good_chains", ""),
                ("evaluated_pair_count", "0"),
                ("fallback", "full_360_cell_universe"),
            )
            return DiagnosisResult(
                frozenset({"unresolved_no_good_chain"}),
                universe,
                trace,
            )

        suspects = set()
        evaluated_pairs = []
        for failed in sorted(failed_chains):
            for good in sorted(passed_chains):
                pair = (failed, good)
                evaluated_pairs.append(pair)
                if pair not in pairs:
                    continue

                # Determine initial faulty state before shift
                faulty_initial = []
                for i in range(CHAIN_LENGTH):
                    cycle = CHAIN_LENGTH - 1 - i
                    if pairs[pair]["sa0"][cycle][good] == 0:
                        faulty_initial.append(0)
                    elif pairs[pair]["sa1"][cycle][good] == 1:
                        faulty_initial.append(1)
                    else:
                        faulty_initial.append(1 - (i % 2))

                for i in range(CHAIN_LENGTH):
                    cycle = CHAIN_LENGTH - 1 - i
                    # SA0 duplication check
                    if pairs[pair]["sa0"][cycle][good] == 0:
                        suspects.add(Cell(failed, i))
                    # SA1 duplication check
                    elif pairs[pair]["sa1"][cycle][good] == 1:
                        suspects.add(Cell(failed, i))
                    # TDF duplication check
                    else:
                        if i == 0:
                            has_transition = (faulty_initial[0] != 0)
                            expected_val = 0
                        else:
                            has_transition = (faulty_initial[i] != faulty_initial[i - 1])
                            expected_val = faulty_initial[i - 1]

                        if has_transition:
                            actual_val = pairs[pair]["tdf"][cycle][good]
                            if actual_val != expected_val:
                                suspects.add(Cell(failed, i))

                # Capture duplication check
                for pat_name in pairs[pair]["capture"]:
                    for cycle in range(CHAIN_LENGTH):
                        if pairs[pair]["capture"][pat_name][cycle][failed] != pairs_golden[pair]["capture"][pat_name][cycle][failed]:
                            suspects.add(Cell(failed, CHAIN_LENGTH - 1 - cycle))
                            break

        indications = frozenset(f"cell_{cell.chain}_{cell.index}" for cell in suspects)
        trace = (
            ("failed_chains", ",".join(map(str, sorted(failed_chains)))),
            ("good_chains", ",".join(map(str, sorted(passed_chains)))),
            ("evaluated_pair_count", str(len(evaluated_pairs))),
            ("evaluated_pairs", ";".join(f"{failed}->{good}" for failed, good in evaluated_pairs)),
            ("candidate_count", str(len(suspects))),
        )
        return DiagnosisResult(indications, frozenset(suspects), trace)
