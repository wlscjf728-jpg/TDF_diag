from __future__ import annotations

from ..domain import CHAIN_COUNT, CHAIN_LENGTH, Cell, DiagnosisResult


class ReversibleModel:
    name = "reversible"

    def diagnose(self, observations: dict | Scenario) -> DiagnosisResult:
        from ..domain import Scenario
        if isinstance(observations, Scenario):
            from drsim.observations import generate_all_observations
            observations = generate_all_observations(observations)

        if "reversible" in observations:
            obs = observations["reversible"]
        else:
            obs = observations

        suspects = set()
        indications = set()
        bounds = []
        failed_chains = []

        for chain in range(CHAIN_COUNT):
            # Find first failing cycle in LRL
            lrl_fail_cycle = None
            for pat in obs["LRL"]:
                lrl_f = obs["LRL"][pat]
                lrl_g = obs["LRL_golden"][pat]
                for i in range(CHAIN_LENGTH):
                    if lrl_f[i][chain] != lrl_g[i][chain]:
                        cycle_1indexed = i + 1
                        if lrl_fail_cycle is None or cycle_1indexed < lrl_fail_cycle:
                            lrl_fail_cycle = cycle_1indexed

            # Find first failing cycle in RLR
            rlr_fail_cycle = None
            for pat in obs["RLR"]:
                rlr_f = obs["RLR"][pat]
                rlr_g = obs["RLR_golden"][pat]
                for i in range(CHAIN_LENGTH):
                    if rlr_f[i][chain] != rlr_g[i][chain]:
                        cycle_1indexed = i + 1
                        if rlr_fail_cycle is None or cycle_1indexed < rlr_fail_cycle:
                            rlr_fail_cycle = cycle_1indexed

            # If either failed, it is a failed chain
            if lrl_fail_cycle is not None or rlr_fail_cycle is not None:
                failed_chains.append(chain)
                lower = lrl_fail_cycle - 1 if lrl_fail_cycle is not None else 0
                upper = CHAIN_LENGTH - rlr_fail_cycle if rlr_fail_cycle is not None else CHAIN_LENGTH - 1

                suspects.update(Cell(chain, (CHAIN_LENGTH - 1) - index) for index in range(lower, upper + 1))
                bounds.append(f"{chain}:{lower}-{upper}")
                indications.add(f"chain_{chain}_interval")

        trace = (
            ("patterns", "LRL,RLR"),
            ("failed_chains", ",".join(map(str, sorted(failed_chains)))),
            ("directional_bounds", ";".join(bounds)),
            ("candidate_count", str(len(suspects))),
        )
        return DiagnosisResult(frozenset(indications), frozenset(suspects), trace)

