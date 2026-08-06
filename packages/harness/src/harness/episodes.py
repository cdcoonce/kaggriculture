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


def resolve_agent(spec: str) -> Any:
    """Resolve an agent spec string to something ``env.run`` accepts.

    Import-and-construct happens lazily inside this function (not at module
    scope) so a fresh, stateless policy is built per call — required for
    correctness across worker processes and across games within one process.
    """
    if spec.startswith("builtin:"):
        return spec.removeprefix("builtin:")
    if spec == "champion":
        from agent.policy import make_policy
        from agent.shell import wrap

        return wrap(make_policy())
    if spec.startswith("zoo:"):
        from harness.zoo import gate_zoo

        name = spec.removeprefix("zoo:")
        member = gate_zoo()[name]
        return member() if callable(member) else member
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
) -> GameRow:
    """Play one episode and return the outcome from the candidate's view.

    Module-level and picklable by design (specs are plain strings) so it can
    run under ``concurrent.futures.ProcessPoolExecutor``.
    """
    from kaggle_environments import make

    opponent_seat = 1 - candidate_seat
    agents: list[Any] = [None, None]
    agents[candidate_seat] = resolve_agent(candidate)
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
