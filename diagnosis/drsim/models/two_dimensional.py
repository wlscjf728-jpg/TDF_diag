from __future__ import annotations

from ..domain import CHAIN_COUNT, CHAIN_LENGTH, Cell, DiagnosisResult, Scenario
from .base import connected_indication_groups, detectable_cells, indication_names


def _diagonal_path_id(cell: Cell) -> int:
    """Return the non-orthogonal staircase-path bin for alternating H/V shifts."""
    return (cell.index - cell.chain) // 2


class TwoDimensionalModel:
    name = "two_dimensional"

    def diagnose(self, observations: dict) -> DiagnosisResult:
        if not isinstance(observations, dict):
            from ..observations import generate_all_observations
            observations = generate_all_observations(observations)

        td_obs = observations.get("two_dimensional", observations)

        # Find failed H-chains
        failed_h = set()
        h_faulty = td_obs["H"]
        h_golden = td_obs["H_golden"]
        for pattern in h_faulty:
            for t in range(len(h_faulty[pattern])):
                for c in range(len(h_faulty[pattern][t])):
                    if h_faulty[pattern][t][c] != h_golden[pattern][t][c]:
                        failed_h.add(c)
        failed_h = frozenset(failed_h)

        # Find failed V-columns
        failed_v = set()
        v_faulty = td_obs["V"]
        v_golden = td_obs["V_golden"]
        for pattern in v_faulty:
            for t in range(len(v_faulty[pattern])):
                for col in range(len(v_faulty[pattern][t])):
                    if v_faulty[pattern][t][col] != v_golden[pattern][t][col]:
                        failed_v.add(col)
        failed_v = frozenset(failed_v)

        # Find failed diagonal paths
        failed_d = set()
        d_faulty = td_obs["D"]
        d_golden = td_obs["D_golden"]
        for pattern in d_faulty:
            for s in range(len(d_faulty[pattern])):
                if s % 2 == 0:
                    for c in range(len(d_faulty[pattern][s])):
                        if d_faulty[pattern][s][c] != d_golden[pattern][s][c]:
                            c_origin = c - s // 2
                            i_origin = (CHAIN_LENGTH - 1) - s // 2
                            if 0 <= c_origin < 5 and 0 <= i_origin < CHAIN_LENGTH:
                                failed_d.add(_diagonal_path_id(Cell(c_origin, i_origin)))
                else:
                    for col in range(len(d_faulty[pattern][s])):
                        if d_faulty[pattern][s][col] != d_golden[pattern][s][col]:
                            c_origin = 4 - s // 2
                            i_origin = col - (s + 1) // 2
                            if 0 <= c_origin < 5 and 0 <= i_origin < CHAIN_LENGTH:
                                failed_d.add(_diagonal_path_id(Cell(c_origin, i_origin)))
        failed_d = frozenset(failed_d)

        if not failed_h or not failed_v or not failed_d:
            return DiagnosisResult(frozenset(), frozenset(), (("patterns", "H,V,D"),))

        candidates = frozenset(
            Cell(chain, index)
            for chain in range(CHAIN_COUNT)
            for index in range(CHAIN_LENGTH)
            if chain in failed_h
            and index in failed_v
            and _diagonal_path_id(Cell(chain, index)) in failed_d
        )

        def memberships(cell: Cell) -> frozenset:
            return frozenset(
                {("H", cell.chain), ("V", cell.index), _diagonal_path_id(cell)}
            )

        groups = connected_indication_groups(candidates, memberships)
        trace = (
            ("patterns", "horizontal,vertical,diagonal"),
            ("failed_h", ",".join(map(str, sorted(failed_h)))),
            ("failed_v", ",".join(map(str, sorted(failed_v)))),
            ("failed_d", ",".join(map(str, sorted(failed_d)))),
            ("candidate_count", str(len(candidates))),
        )
        return DiagnosisResult(indication_names(groups), candidates, trace)



