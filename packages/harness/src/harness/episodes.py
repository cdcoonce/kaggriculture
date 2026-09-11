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

    ``agent_config`` overrides a policy's tuning knobs
    (``agent.policy.PolicyConfig``). It is accepted for ``"champion"``,
    ``"champion-unshelled"`` and any ``"frozen:"`` spec; passing it for a
    builtin or zoo spec raises, since a silently-dropped override would be
    indistinguishable from one that took effect.

    A frozen spec resolves the override against **its own** frozen
    ``PolicyConfig``, not the live one. That is the whole point: an A/B on a
    code change has to run both arms at the same knob setting, and pinning the
    baseline at its defaults instead would price the knob and the code change
    together and then attribute the sum to the code. A frozen build that
    predates the knob rejects it loudly, naming the package, rather than
    quietly running at defaults.

    ``"champion-unshelled"`` returns the raw ``make_policy(...)`` callable
    without ``agent.shell.wrap``'s never-raise boundary — for crash-only
    smoke checks that need a policy exception to actually surface.
    """
    if (
        spec not in {"champion", "champion-unshelled"}
        and not spec.startswith("frozen:")
        and agent_config is not None
    ):
        raise ValueError(
            f"agent_config is only supported for the 'champion', "
            f"'champion-unshelled' and 'frozen:' specs, got {spec!r}"
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
        # Resolve against the EXTENDED roster, not the gate roster. Extended
        # members (chaos-legal-random since #39, and any machine-local tape)
        # were registered in a tier nothing could reach: `gate_zoo()` here made
        # `zoo:<extended-member>` a KeyError, so the sweep the zoo docstring
        # describes could never have run. Widening the lookup does NOT widen
        # the gate -- strength_gate iterates SCRIPTED directly, so the
        # promotion roster is unchanged and still machine-independent.
        from harness.zoo import extended_zoo

        name = spec.removeprefix("zoo:")
        member = extended_zoo()[name]
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

        if agent_config is None:
            return shell.wrap(policy.make_policy())
        try:
            policy_config = policy.PolicyConfig(**agent_config)
        except TypeError as exc:
            # Re-raised with the package name because the bare dataclass error
            # says only "PolicyConfig", which is indistinguishable from the
            # live one -- and the whole failure mode worth catching here is a
            # knob that exists today but did not exist at the frozen SHA.
            raise TypeError(
                f"frozen package {pkg!r} does not accept this agent_config: {exc}. "
                f"That build predates the knob; it cannot be gated at this arm."
            ) from exc
        return shell.wrap(policy.make_policy(policy_config=policy_config))
    if spec.startswith("public:"):
        # Pre-registered public-leader opponent panel (eval/prereg/
        # 2026-09-08-demand-aware-seasonal-controller.md): SHA-256-verified
        # against eval/opponents/public-leaders/panel.json and re-executed
        # into a brand-new namespace on every resolution, since these files
        # keep mutable module-level globals and worker processes are reused
        # across games. See harness.public_leaders for why and how.
        from harness.public_leaders import resolve_public_leader

        return resolve_public_leader(spec.removeprefix("public:"))
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
