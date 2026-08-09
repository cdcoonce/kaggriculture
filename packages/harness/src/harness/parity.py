"""Byte-exact, per-step, per-field replay comparator (issue #32).

Upgrades parity checking from the seedless, law-level checks in
``tools/parity/common_checks.py`` (price function, town-consumption
schedule, structural spot-checks) to a full observation-diff against an
independently re-simulated trajectory, using the replay's own recorded
per-step actions and its own configuration + seed.
"""

from __future__ import annotations

import gzip
import importlib.metadata
import json
from dataclasses import dataclass
from pathlib import Path

from kaggle_environments import make

# The only observation field that legitimately differs between a byte-exact
# local seed-0 replay and the server's own trajectory: real-time
# compute-budget bookkeeping (actTimeout/runTimeout accounting keyed to
# genuine wall-clock latency per Kaggle server request), not simulation
# state. See docs/recon/server-parity.md's exact-reproduction section.
EXCLUDED_OBSERVATION_FIELDS: frozenset[str] = frozenset({"remainingOverageTime"})


def load_replay(path: Path) -> dict:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as f:
        return json.load(f)


def replay_locally(data: dict) -> list[list[dict]]:
    """Independently re-simulate ``data``'s trajectory step by step.

    Builds the env from the replay's own configuration with the seed patched
    in from ``data["info"]["seed"]`` (the real seed, scrubbed from
    ``configuration`` in server replays), then drives it with each step's
    own recorded action (the action that PRODUCED that step's observation).
    """
    configuration = {**data["configuration"], "seed": data["info"]["seed"]}
    env = make("kaggriculture", configuration=configuration, debug=True)
    env.reset(num_agents=2)

    steps_raw = data["steps"]
    local_steps: list[list[dict]] = [
        [dict(env.steps[0][0].observation), dict(env.steps[0][1].observation)]
    ]
    for i in range(1, len(steps_raw)):
        actions = [steps_raw[i][0]["action"], steps_raw[i][1]["action"]]
        result = env.step(actions)
        local_steps.append([dict(result[0].observation), dict(result[1].observation)])
    return local_steps


@dataclass(frozen=True)
class Mismatch:
    step: int
    agent: int
    field: str


@dataclass(frozen=True)
class ParityReport:
    mismatches: tuple[Mismatch, ...]
    steps_compared: int

    @property
    def mismatch_count(self) -> int:
        return len(self.mismatches)


def compare_trajectories(
    replay_steps: list[list[dict]],
    local_steps: list[list[dict]],
    ignore_fields: frozenset[str] = EXCLUDED_OBSERVATION_FIELDS,
) -> ParityReport:
    """Diff two equal-length, equal-shape trajectories field by field.

    Each entry of ``replay_steps``/``local_steps`` is ``[obs_agent0,
    obs_agent1]``; each per-agent entry may be either a raw replay step dict
    (with an ``"observation"`` key alongside ``action``/``reward``/``status``,
    e.g. ``data["steps"][i][agent]``) or an already-bare observation dict
    (e.g. a ``replay_locally`` entry) -- the function unwraps the former and
    does not care which side is "replay" vs "local".
    """
    mismatches = []
    for step_idx, (replay_agents, local_agents) in enumerate(
        zip(replay_steps, local_steps, strict=True)
    ):
        for agent_idx, (replay_entry, local_entry) in enumerate(
            zip(replay_agents, local_agents, strict=True)
        ):
            replay_obs = replay_entry.get("observation", replay_entry)
            local_obs = local_entry.get("observation", local_entry)
            fields = set(replay_obs.keys()) | set(local_obs.keys())
            for field in fields:
                if field in ignore_fields:
                    continue
                replay_val = replay_obs.get(field)
                local_val = local_obs.get(field)
                if json.dumps(replay_val, sort_keys=True, default=str) != json.dumps(
                    local_val, sort_keys=True, default=str
                ):
                    mismatches.append(Mismatch(step=step_idx, agent=agent_idx, field=field))

    return ParityReport(mismatches=tuple(mismatches), steps_compared=len(replay_steps))


def installed_engine_version() -> str:
    return importlib.metadata.version("kaggle-environments")
