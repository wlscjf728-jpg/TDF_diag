from __future__ import annotations

from ..domain import CHAIN_COUNT, CHAIN_LENGTH, Cell, DiagnosisResult, Scenario
from .base import connected_indication_groups, detectable_cells, indication_names


FIRST_STAGE_CONFIGS = (0, 1, 3, 7)
SECOND_STAGE_CONFIGS = (2, 4, 5, 6)


def _control_for_boundary(boundary: int) -> int:
    if boundary % 25 == 0:
        return 2
    if boundary % 5 == 0:
        return 1
    return 0


_ROTATIONS_TABLE = []
for config in range(8):
    config_rot = [0] * (CHAIN_LENGTH + 1)
    curr_rot = 0
    for idx in range(1, CHAIN_LENGTH + 1):
        if config & (1 << _control_for_boundary(idx)):
            curr_rot += 1
        config_rot[idx] = curr_rot
    _ROTATIONS_TABLE.append(config_rot)


def _path_id(cell: Cell, config: int) -> int:
    return (cell.chain + _ROTATIONS_TABLE[config][cell.index]) % CHAIN_COUNT


def _get_failed_paths(recon_obs: dict, configs: tuple[int, ...]) -> dict[int, frozenset[int]]:
    failed = {}
    config_data = recon_obs["configs"]
    golden_data = recon_obs["configs_golden"]
    for config in configs:
        failed_paths = set()
        c_faulty = config_data[config]
        c_golden = golden_data[config]
        for pattern in c_faulty:
            for t in range(len(c_faulty[pattern])):
                for p in range(len(c_faulty[pattern][t])):
                    if c_faulty[pattern][t][p] != c_golden[pattern][t][p]:
                        failed_paths.add(p)
        failed[config] = frozenset(failed_paths)
    return failed


def _candidates(
    failed: dict[int, frozenset[int]], configs: tuple[int, ...]
) -> frozenset[Cell]:
    candidates = frozenset(
        cell
        for cell in (
            Cell(chain, index)
            for chain in range(CHAIN_COUNT)
            for index in range(CHAIN_LENGTH)
        )
        if all(_path_id(cell, config) in failed[config] for config in configs)
    )
    return candidates


class ReconfigurableModel:
    name = "reconfigurable"

    def diagnose(self, observations: dict) -> DiagnosisResult:
        if not isinstance(observations, dict):
            from ..observations import generate_all_observations
            observations = generate_all_observations(observations)

        recon_obs = observations.get("reconfigurable", observations)

        configs = FIRST_STAGE_CONFIGS
        failed = _get_failed_paths(recon_obs, configs)
        if not any(failed[config] for config in configs):
            return DiagnosisResult(frozenset(), frozenset(), (("stage_count", "1"),))

        candidates = _candidates(failed, configs)
        stage_count = 1
        if len(candidates) > 2:
            configs = FIRST_STAGE_CONFIGS + SECOND_STAGE_CONFIGS
            failed = _get_failed_paths(recon_obs, configs)
            candidates = _candidates(failed, configs)
            stage_count = 2

        def memberships(cell: Cell) -> frozenset[tuple[int, int]]:
            return frozenset((config, _path_id(cell, config)) for config in configs)

        groups = connected_indication_groups(candidates, memberships)
        trace = (
            ("stage_count", str(stage_count)),
            ("path_sets", ",".join(map(str, configs))),
            ("failed_paths", ";".join(
                f"{config}:{','.join(map(str, sorted(failed[config])))}" for config in configs
            )),
            ("candidate_count", str(len(candidates))),
        )
        return DiagnosisResult(indication_names(groups), candidates, trace)

