"""Agent spec resolution and single-game execution (eval protocol, issue #4).

Kept deliberately picklable: ``play_game`` is a module-level function taking
only string specs, so it can run under
``concurrent.futures.ProcessPoolExecutor`` without pickling live callables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Outcome = Literal["win", "loss", "tie"]

# Statuses a seat passes through during a normal, non-crashed run. Anything
# else observed at any step (not just the last — the engine may force a
# terminal DONE with frozen money after an earlier crash) counts as a crash.
_NON_CRASH_STATUSES = {"ACTIVE", "DONE"}


@dataclass(frozen=True)
class GameRow:
    """The outcome of one played episode, from the candidate's perspective."""

    seed: int
    candidate_seat: int
    candidate_money: float
    opponent_money: float
    outcome: Outcome
    candidate_crashed: bool
    opponent_crashed: bool


def resolve_agent(spec: str, agent_config: dict[str, Any] | None = None) -> Any:
    """Resolve an agent spec string to something ``env.run`` accepts.

    Import-and-construct happens lazily inside this function (not at module
    scope) so a fresh, stateless policy is built per call — required for
    correctness across worker processes and across games within one process.

    ``agent_config`` overrides the champion policy's tuning knobs
    (``agent.policy.PolicyConfig``) and is only meaningful for the
    ``"champion"`` and ``"champion-unshelled"`` specs; passing it for any
    other spec raises, since a silently-dropped override would be
    indistinguishable from one that took effect.

    ``"champion-unshelled"`` returns the raw ``make_policy(...)`` callable
    without ``agent.shell.wrap``'s never-raise boundary — for crash-only
    smoke checks that need a policy exception to actually surface.
    """
    if spec not in {"champion", "champion-unshelled"} and agent_config is not None:
        raise ValueError(
            f"agent_config is only supported for the 'champion' and "
            f"'champion-unshelled' specs, got {spec!r}"
        )
    if spec.startswith("builtin:"):
        return spec.removeprefix("builtin:")
    if spec == "champion":
        from agent.policy import PolicyConfig, make_policy
        from agent.shell import wrap

        policy_config = PolicyConfig(**agent_config) if agent_config is not None else None
        return wrap(make_policy(policy_config=policy_config))
    if spec == "champion-unshelled":
        from agent.policy import PolicyConfig, make_policy

        policy_config = PolicyConfig(**agent_config) if agent_config is not None else None
        return make_policy(policy_config=policy_config)
    if spec.startswith("zoo:"):
        from harness.zoo import gate_zoo

        name = spec.removeprefix("zoo:")
        member = gate_zoo()[name]
        return member() if callable(member) else member
    if spec.startswith("frozen:"):
        import importlib
        import os
        import sys
        from pathlib import Path

        from harness.frozen import assert_disjoint, frozen_package_name

        name = spec.removeprefix("frozen:")
        pkg = frozen_package_name(name)

        dest_root = Path(os.environ.get("KAGG_FROZEN_ROOT", Path.cwd() / "eval" / "frozen"))
        dest_root_str = str(dest_root.resolve())
        if dest_root_str not in sys.path:
            sys.path.insert(0, dest_root_str)

        policy = importlib.import_module(f"{pkg}.policy")
        shell = importlib.import_module(f"{pkg}.shell")
        assert_disjoint(name)

        return shell.wrap(policy.make_policy())
    raise ValueError(f"unknown agent spec: {spec!r}")


def classify_outcome(
    candidate_money: float, opponent_money: float, candidate_crashed: bool
) -> Outcome:
    """Determine win/loss/tie from the candidate's perspective.

    A crashed candidate loses regardless of its frozen money total.
    """
    if candidate_crashed:
        return "loss"
    if candidate_money == opponent_money:
        return "tie"
    return "win" if candidate_money > opponent_money else "loss"


def _seat_crashed(steps: list[Any], seat: int) -> bool:
    return any(step[seat].status not in _NON_CRASH_STATUSES for step in steps)


def play_game(
    seed: int,
    candidate_seat: int,
    candidate: str,
    opponent: str,
    extra_config: dict[str, Any] | None = None,
    agent_config: dict[str, Any] | None = None,
) -> GameRow:
    """Play one episode and return the outcome from the candidate's view.

    Module-level and picklable by design (specs are plain strings) so it can
    run under ``concurrent.futures.ProcessPoolExecutor``.

    ``agent_config`` is forwarded only into the candidate's ``resolve_agent``
    call, never the opponent's — a candidate-side override must never
    silently retune the opponent in a self-play or champion-vs-champion gate.
    """
    from kaggle_environments import make

    opponent_seat = 1 - candidate_seat
    agents: list[Any] = [None, None]
    agents[candidate_seat] = resolve_agent(candidate, agent_config)
    agents[opponent_seat] = resolve_agent(opponent)

    configuration = {"seed": seed, **(extra_config or {})}
    env = make("kaggriculture", configuration=configuration)
    env.run(agents)

    final = env.steps[-1]
    farms = final[0].observation.farms
    candidate_money = farms[candidate_seat]["money"]
    opponent_money = farms[opponent_seat]["money"]
    candidate_crashed = _seat_crashed(env.steps, candidate_seat)
    opponent_crashed = _seat_crashed(env.steps, opponent_seat)
    outcome = classify_outcome(candidate_money, opponent_money, candidate_crashed)

    return GameRow(
        seed=seed,
        candidate_seat=candidate_seat,
        candidate_money=candidate_money,
        opponent_money=opponent_money,
        outcome=outcome,
        candidate_crashed=candidate_crashed,
        opponent_crashed=opponent_crashed,
    )
