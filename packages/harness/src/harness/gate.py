"""Promotion-gate runner: paired seeds, both seats, parallel or sequential.

Eval protocol, issue #4.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any

from harness.episodes import GameRow, play_game
from harness.stats import (
    CATASTROPHIC_TAIL_FLOOR,
    CATASTROPHIC_TAIL_QUANTILE,
    GateVerdict,
    MoneyVerdict,
    gate_verdict,
    money_verdict,
)

#: Specs whose policy is built from ``agent.policy.PolicyConfig`` and therefore
#: accept an ``agent_config`` override (see ``harness.episodes.resolve_agent``).
TUNABLE_SPECS = frozenset({"champion", "champion-unshelled"})


def is_tunable(spec: str) -> bool:
    """Whether ``spec`` accepts a PolicyConfig override.

    A predicate rather than ``spec in TUNABLE_SPECS`` because frozen spec names
    are dynamic (``frozen:<name>``) and cannot be enumerated in a frozenset.
    Frozen specs are tunable so a code change can be A/B'd at the same knob
    setting on both arms; see ``harness.episodes.resolve_agent``. Builtin and
    zoo specs are still refused, because they have no PolicyConfig at all and
    an override would be silently dropped.
    """
    return spec in TUNABLE_SPECS or spec.startswith("frozen:")


@dataclass(frozen=True)
class GateResult:
    """Aggregate outcome of a full gate run."""

    candidate: str
    opponent: str
    gate_type: str
    n_seeds: int
    seed_base: int
    seeds: list[int]
    rows: list[GameRow]
    wins: int
    losses: int
    ties: int
    verdict: GateVerdict
    any_candidate_crash: bool
    extra_config: dict[str, Any] | None
    agent_config: dict[str, Any] | None
    threshold: float


def _play_seed_pair(
    seed: int,
    candidate: str,
    opponent: str,
    extra_config: dict[str, Any] | None,
    agent_config: dict[str, Any] | None,
) -> list[GameRow]:
    return [
        play_game(seed, 0, candidate, opponent, extra_config, agent_config),
        play_game(seed, 1, candidate, opponent, extra_config, agent_config),
    ]


def run_gate(
    candidate: str,
    opponent: str,
    n_seeds: int,
    seed_base: int,
    workers: int = 8,
    extra_config: dict[str, Any] | None = None,
    gate_type: str = "promotion",
    threshold: float = 0.5,
    agent_config: dict[str, Any] | None = None,
) -> GateResult:
    """Run a candidate-vs-opponent gate over paired seeds, both seats.

    Each seed in ``range(seed_base, seed_base + n_seeds)`` produces two
    games: the candidate as seat 0 and as seat 1. Sequential (``workers<=1``)
    and parallel (``ProcessPoolExecutor``) execution modes both call the
    module-level, picklable ``harness.episodes.play_game``.

    macOS/spawn caveat: with ``workers > 1`` the CALLING script must guard its
    entry point with ``if __name__ == "__main__":`` — spawn re-imports the
    caller's main module in every worker, and an unguarded module-level call
    recurses into a BrokenProcessPool.

    ``agent_config`` overrides the candidate champion's ``PolicyConfig`` (see
    ``harness.episodes.resolve_agent``); it is passed as a plain picklable
    dict so it survives ``ProcessPoolExecutor`` worker re-import.

    ``workers`` is forced to 1 when ``candidate == "champion-unshelled"``: that
    spec resolves to a bound closure from ``make_policy()``, which is not
    guaranteed picklable, so parallel workers are out of scope for it.
    """
    if candidate == "champion-unshelled":
        workers = 1
    seeds = list(range(seed_base, seed_base + n_seeds))
    rows: list[GameRow] = []

    if workers <= 1:
        for seed in seeds:
            rows.extend(_play_seed_pair(seed, candidate, opponent, extra_config, agent_config))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(play_game, seed, seat, candidate, opponent, extra_config, agent_config)
                for seed in seeds
                for seat in (0, 1)
            ]
            rows = [future.result() for future in futures]

    wins = sum(1 for row in rows if row.outcome == "win")
    losses = sum(1 for row in rows if row.outcome == "loss")
    ties = sum(1 for row in rows if row.outcome == "tie")
    verdict = gate_verdict(wins=wins, losses=losses, ties=ties, threshold=threshold)
    any_candidate_crash = any(row.candidate_crashed for row in rows)

    return GateResult(
        candidate=candidate,
        opponent=opponent,
        gate_type=gate_type,
        n_seeds=n_seeds,
        seed_base=seed_base,
        seeds=seeds,
        rows=rows,
        wins=wins,
        losses=losses,
        ties=ties,
        verdict=verdict,
        any_candidate_crash=any_candidate_crash,
        extra_config=extra_config,
        agent_config=agent_config,
        threshold=threshold,
    )


@dataclass(frozen=True)
class SeedMoney:
    """One paired observation: both seats averaged, both arms."""

    seed: int
    candidate_money: float
    baseline_money: float
    delta: float


@dataclass(frozen=True)
class MoneyGateResult:
    """A two-arm, same-seed, same-opponent paired money gate."""

    candidate: str
    agent_config: dict[str, Any] | None
    baseline: str
    baseline_agent_config: dict[str, Any] | None
    opponent: str
    opponent_digest: str | None
    gate_type: str
    n_seeds: int
    seed_base: int
    seeds: list[int]
    candidate_result: GateResult
    baseline_result: GateResult
    per_seed: list[SeedMoney]
    money_verdict: MoneyVerdict
    opponent_mean_delta: float
    min_opponent_money: float
    candidate_canary_ran: bool
    candidate_canary_crashed: bool
    baseline_canary_ran: bool
    baseline_canary_crashed: bool
    extra_config: dict[str, Any] | None
    threshold: float
    # Veto knobs are carried on the result, not just consumed, so a ledger
    # entry can record them and `rerun-ledger` can reproduce the SAME vetoes.
    # Without them a run that legitimately lowered `opponent_money_floor`
    # (any non-tape opponent) replays under the tape-calibrated default and
    # reports a mismatch that is really a knob the ledger forgot.
    alpha: float
    min_seeds: int
    catastrophic_tail_quantile: float
    catastrophic_tail_floor: float
    candidate_money_floor: float
    opponent_money_floor: float
    degenerate_seed_fraction: float


def _seat_mean(rows: Sequence[GameRow], attribute: str) -> dict[int, float]:
    by_seed: dict[int, dict[int, float]] = {}
    for row in rows:
        seats = by_seed.setdefault(row.seed, {})
        if row.candidate_seat in seats:
            raise ValueError(
                f"seed {row.seed} contributes seat {row.candidate_seat} more than once"
            )
        seats[row.candidate_seat] = float(getattr(row, attribute))

    collapsed: dict[int, float] = {}
    for seed, seats in by_seed.items():
        if set(seats) != {0, 1}:
            raise ValueError(
                f"seed {seed} is missing a seat: got seats {sorted(seats)}, need [0, 1]"
            )
        collapsed[seed] = (seats[0] + seats[1]) / 2.0
    return collapsed


def seat_mean_money(rows: Sequence[GameRow]) -> dict[int, float]:
    """Collapse both seats of each seed into one seat-averaged observation.

    Raises ``ValueError`` unless every seed contributes exactly seats
    ``{0, 1}``. A seed with one usable seat is not a half-observation; it is
    a broken run, and silently keeping it would break the pairing the whole
    statistic rests on.
    """
    return _seat_mean(rows, "candidate_money")


def seat_mean_opponent_money(rows: Sequence[GameRow]) -> dict[int, float]:
    """Same collapse, over ``GameRow.opponent_money``."""
    return _seat_mean(rows, "opponent_money")


def _by_seat(rows: Sequence[GameRow], attribute: str) -> dict[int, dict[int, float]]:
    """``{seat: {seed: money}}`` -- the same rows WITHOUT collapsing the seats.

    Used only by the liveness floors; the money statistic always collapses.
    """
    split: dict[int, dict[int, float]] = {}
    for row in rows:
        seat = split.setdefault(row.candidate_seat, {})
        if row.seed in seat:
            raise ValueError(
                f"seed {row.seed} contributes seat {row.candidate_seat} more than once"
            )
        seat[row.seed] = float(getattr(row, attribute))
    return split


def seat_split_money(rows: Sequence[GameRow]) -> dict[int, dict[int, float]]:
    """``{seat: {seed: candidate_money}}``."""
    return _by_seat(rows, "candidate_money")


def seat_split_opponent_money(rows: Sequence[GameRow]) -> dict[int, dict[int, float]]:
    """``{seat: {seed: opponent_money}}``."""
    return _by_seat(rows, "opponent_money")


def _fraction_at_or_below(by_seed: Mapping[int, float], floor: float) -> float:
    """Fraction of SEEDS whose money sits at or below ``floor``.

    The unit is the seed, matching the statistic. The per-GAME form this
    replaced (``any(row.candidate_money <= floor)``) is a hair trigger with
    no tolerance at all: ONE game in 80 turned a measured +$18,764 gain whose
    bound cleared the threshold 14.7x into INVALID. It is also perverse --
    the larger the true improvement, the worse the comparison arm looks and
    the likelier the veto fires on it.
    """
    if not by_seed:
        return 0.0
    return sum(1 for money in by_seed.values() if money <= floor) / len(by_seed)


def _worst_seat_fraction_at_or_below(
    by_seat: Mapping[int, Mapping[int, float]], floor: float
) -> float:
    """Largest per-SEAT fraction of seeds at or below ``floor``.

    The floors keep the seed as the unit of the FRACTION and drop the seat
    AVERAGING, which is a different thing and was the defect: a seed's money
    is ``(seat0 + seat1) / 2``, so an arm banking the $2,000 starting-cash
    signature in seat 0 and a healthy $37,167 in seat 1 averages to $19,583
    on every seed and no floor could see it (adversarial2/q6). Under the
    per-game rule this replaced, every seat-0 row was under the floor.

    Averaging the two seats is right for the money STATISTIC -- it is what
    makes one observation one seed and buys the 2-60x variance reduction --
    and wrong for a liveness floor, which is asking whether the agent is
    playing at all. Splitting by seat keeps the seed unit for both.

    Measured on this machine over three healthy 40-seed arms against
    ``zoo:tape-thunder-719``, the per-seat fraction at or below the $3,000
    floor is 0.000 in both seats (per-seat minima $14,080-$21,443), and the
    deliberate ``wheat_rush_tiles=0`` regression reaches only 0.025 in seat
    0. The 0.25 trigger keeps its margin.
    """
    if not by_seat:
        return 0.0
    return max(_fraction_at_or_below(by_seed, floor) for by_seed in by_seat.values())


def _degenerate_fraction(
    seed_means: Mapping[int, float], by_seat: Mapping[int, Mapping[int, float]], floor: float
) -> float:
    """UNION of the seed-averaged and per-seat readings: whichever is worse.

    Neither reading alone dominates the other. A seed can fail the
    seed-averaged reading while passing every per-seat reading: floor
    $3,000, seed A at seat0 $2,900 / seat1 $3,100 and seed B at seat0 $3,500 /
    seat1 $2,500 -- each SEAT'S fraction at or below the floor is 1/2 (one
    bad seed each), but BOTH seeds' seat-averaged money is exactly $3,000, so
    the seed-averaged fraction is 2/2. An arm that alternates which seat is
    weak, seed to seed, spreads its badness across two seat-split
    populations and reads as half as degenerate as it is under
    ``_worst_seat_fraction_at_or_below`` alone; the seed-averaged reading
    catches that shape, and the seat-split reading still catches the
    complementary shape it was built for (one seat dead every seed, see
    ``_worst_seat_fraction_at_or_below``). Taking the union of both closes
    each reading's blind spot with the other.
    """
    return max(
        _fraction_at_or_below(seed_means, floor),
        _worst_seat_fraction_at_or_below(by_seat, floor),
    )


def opponent_digest(opponent: str) -> str | None:
    """``"sha256:<hex>"`` of the file backing ``zoo:tape-<stem>`` or
    ``zoo:kernel-<stem>``, else None.

    Tapes and kernel plans are both machine-local and uncommitted, and
    nothing else identifies which bytes a run used: a different
    ``thunder-719.json`` (or ``sokolovsky-2883.json``) on another machine
    produces different money under an identical ledger identity, silently.
    ``None`` for every spec matching neither prefix, and for a file that is
    not present on this machine.
    """
    if opponent.startswith("zoo:tape-"):
        from harness.zoo.tape_player import tape_path

        path = tape_path(opponent.removeprefix("zoo:tape-"))
    elif opponent.startswith("zoo:kernel-"):
        from harness.zoo.kernel_player import kernel_path

        path = kernel_path(opponent.removeprefix("zoo:kernel-"))
    else:
        return None

    if not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run_money_gate(
    candidate: str,
    opponent: str,
    n_seeds: int,
    seed_base: int,
    *,
    baseline: str,
    baseline_agent_config: dict[str, Any] | None = None,
    agent_config: dict[str, Any] | None = None,
    workers: int = 8,
    extra_config: dict[str, Any] | None = None,
    threshold: float = 1000.0,
    alpha: float = 0.05,
    min_seeds: int = 8,
    catastrophic_tail_quantile: float = CATASTROPHIC_TAIL_QUANTILE,
    catastrophic_tail_floor: float = CATASTROPHIC_TAIL_FLOOR,
    candidate_money_floor: float = 3000.0,
    opponent_money_floor: float = 10000.0,
    degenerate_seed_fraction: float = 0.25,
    canary_seeds: int = 6,
    run_canary: bool = True,
    gate_type: str = "money",
) -> MoneyGateResult:
    """Play candidate and baseline over the SAME seeds against the SAME opponent.

    Both arms run inside this one call: identical opponent, identical seeds,
    identical ``extra_config``, identical engine build. Pairing is worth
    2-60x (measured 65.8%-99.97% variance reduction), and it is fictional
    unless the baseline is replayed here rather than cached from an earlier
    run.

    A veto NEVER drops a seed, it invalidates the run. Dropping crashed seeds
    would break pairing, silently change ``n``, and condition the sample on
    candidate-induced survival -- a candidate that breaks on its worst seeds
    would outscore one that never breaks.

    ``degenerate_seed_fraction`` is the tolerance on the money floors, applied
    as the UNION of two readings (see ``_degenerate_fraction``): the
    ``candidate_degenerate`` / ``baseline_degenerate`` / ``opponent_degenerate``
    vetoes fire only when at least this FRACTION of seeds sits at or below the
    relevant floor, on EITHER the seat-averaged seed money or the worst single
    seat. The default 0.25 is chosen from both ends of the gap it has to
    separate: a genuinely dead arm returns starting cash on ~100% of seeds
    (the whole point of the floor), while the worst healthy arm ever measured
    here put 1 seed of 40 -- 2.5% -- under $3,000 as an ordinary low tail. 25%
    is ten times the observed healthy rate and four times below the dead-arm
    rate, so neither end is close to the line.

    ``gate_type`` defaults to ``"money"``, which keeps these entries out of
    ``harness.ledger.find_passing_promotion``'s ``"promotion"`` filter and
    therefore out of the Kaggle upload path. ``verdict.passed`` on the
    candidate arm keeps meaning WIN RATE; the money PASS lives only in
    ``money_verdict.passed``.

    ``money_verdict.passed`` promotes on EXPECTED money and nothing else --
    see ``MoneyVerdict`` for the full limitation. A candidate that is worse on
    most seeds can still PASS if a minority of seeds pays for it; read
    ``money_verdict.n_regressed`` and ``money_verdict.tail_quantile`` before
    treating a PASS here as a promotion decision.

    macOS/spawn caveat inherited from ``run_gate``: with ``workers > 1`` the
    CALLING script must guard its entry point with
    ``if __name__ == "__main__":``.
    """
    if n_seeds < 1:
        raise ValueError(f"run_money_gate needs n_seeds >= 1, got {n_seeds}")
    if agent_config is not None and not is_tunable(candidate):
        raise ValueError(
            f"agent_config is only supported for {sorted(TUNABLE_SPECS)} and "
            f"'frozen:' specs, got candidate {candidate!r}"
        )
    if baseline_agent_config is not None and not is_tunable(baseline):
        raise ValueError(
            f"baseline_agent_config is only supported for {sorted(TUNABLE_SPECS)} "
            f"and 'frozen:' specs, got baseline {baseline!r}"
        )

    # The `champion` shell catches BaseException and returns pass_action(), so
    # `candidate_crashed` is structurally unreachable for a shelled champion:
    # a policy faulting on 100% of turns still reports any_candidate_crash
    # False. The unshelled canary is the only way to surface that.
    candidate_canary_ran = False
    candidate_canary_crashed = False
    baseline_canary_ran = False
    baseline_canary_crashed = False
    #
    # NOTE the predicate here is TUNABLE_SPECS, not is_tunable: the canary
    # substitutes `champion-unshelled`, i.e. the LIVE agent. That is a valid
    # proxy only for a champion arm. A frozen arm is different code, so the
    # canary would smoke-test something the gate is not running -- it stays
    # skipped for frozen specs even though they now accept a config.
    if run_canary:
        if candidate in TUNABLE_SPECS:
            candidate_canary_ran = True
            candidate_canary_crashed = run_gate(
                candidate="champion-unshelled",
                opponent=opponent,
                n_seeds=canary_seeds,
                seed_base=seed_base,
                workers=1,
                extra_config=extra_config,
                gate_type="money-canary",
                agent_config=agent_config,
            ).any_candidate_crash
        # Shipped defaults are already smoke-tested by CI's strength_gate; a
        # TUNED baseline is not, so it gets its own canary.
        if baseline in TUNABLE_SPECS and baseline_agent_config is not None:
            baseline_canary_ran = True
            baseline_canary_crashed = run_gate(
                candidate="champion-unshelled",
                opponent=opponent,
                n_seeds=canary_seeds,
                seed_base=seed_base,
                workers=1,
                extra_config=extra_config,
                gate_type="money-canary",
                agent_config=baseline_agent_config,
            ).any_candidate_crash

    candidate_result = run_gate(
        candidate=candidate,
        opponent=opponent,
        n_seeds=n_seeds,
        seed_base=seed_base,
        workers=workers,
        extra_config=extra_config,
        gate_type=gate_type,
        threshold=0.5,
        agent_config=agent_config,
    )
    baseline_result = run_gate(
        candidate=baseline,
        opponent=opponent,
        n_seeds=n_seeds,
        seed_base=seed_base,
        workers=workers,
        extra_config=extra_config,
        gate_type=gate_type,
        threshold=0.5,
        agent_config=baseline_agent_config,
    )

    candidate_by_seed = seat_mean_money(candidate_result.rows)
    baseline_by_seed = seat_mean_money(baseline_result.rows)
    if set(candidate_by_seed) != set(baseline_by_seed):
        raise ValueError(
            "the two arms did not play the same seeds -- the pairing is fictional: "
            f"candidate={sorted(candidate_by_seed)} baseline={sorted(baseline_by_seed)}"
        )
    seeds = sorted(candidate_by_seed)
    per_seed = [
        SeedMoney(
            seed=seed,
            candidate_money=candidate_by_seed[seed],
            baseline_money=baseline_by_seed[seed],
            delta=candidate_by_seed[seed] - baseline_by_seed[seed],
        )
        for seed in seeds
    ]

    candidate_opponent = seat_mean_opponent_money(candidate_result.rows)
    baseline_opponent = seat_mean_opponent_money(baseline_result.rows)
    # Records the market-suppression signature: a tuning arm can gain money
    # by starving the opponent rather than by farming better.
    opponent_mean_delta = sum(candidate_opponent[seed] for seed in seeds) / len(seeds) - sum(
        baseline_opponent[seed] for seed in seeds
    ) / len(seeds)
    all_rows = list(candidate_result.rows) + list(baseline_result.rows)
    min_opponent_money = min(row.opponent_money for row in all_rows)

    extra_vetoes: list[str] = []
    if candidate_result.any_candidate_crash:
        extra_vetoes.append("candidate_crash")
    if baseline_result.any_candidate_crash:
        extra_vetoes.append("baseline_crash")
    if any(row.opponent_crashed for row in all_rows):
        extra_vetoes.append("opponent_crash")
    candidate_seats = seat_split_money(candidate_result.rows)
    baseline_seats = seat_split_money(baseline_result.rows)
    if (
        _degenerate_fraction(candidate_by_seed, candidate_seats, candidate_money_floor)
        >= degenerate_seed_fraction
    ):
        extra_vetoes.append("candidate_degenerate")
    if (
        _degenerate_fraction(baseline_by_seed, baseline_seats, candidate_money_floor)
        >= degenerate_seed_fraction
    ):
        extra_vetoes.append("baseline_degenerate")
    candidate_opponent_seats = seat_split_opponent_money(candidate_result.rows)
    baseline_opponent_seats = seat_split_opponent_money(baseline_result.rows)
    opponent_by_seat = {
        seat: {
            seed: min(money, baseline_opponent_seats[seat][seed]) for seed, money in by_seed.items()
        }
        for seat, by_seed in candidate_opponent_seats.items()
    }
    # Seed-averaged combination of the two arms' opponent money, matching the
    # `min` combination `opponent_by_seat` already applies per seat: the
    # weaker of the two arms' opponent readings on that seed is the one that
    # can actually reveal a starved or silently-dead opponent.
    opponent_by_seed = {
        seed: min(candidate_opponent[seed], baseline_opponent[seed]) for seed in seeds
    }
    if (
        _degenerate_fraction(opponent_by_seed, opponent_by_seat, opponent_money_floor)
        >= degenerate_seed_fraction
    ):
        extra_vetoes.append("opponent_degenerate")
    if candidate_canary_crashed or baseline_canary_crashed:
        extra_vetoes.append("canary_crash")

    verdict = money_verdict(
        candidate_by_seed,
        baseline_by_seed,
        threshold=threshold,
        alpha=alpha,
        min_seeds=min_seeds,
        catastrophic_tail_quantile=catastrophic_tail_quantile,
        catastrophic_tail_floor=catastrophic_tail_floor,
        extra_vetoes=extra_vetoes,
    )

    return MoneyGateResult(
        candidate=candidate,
        agent_config=agent_config,
        baseline=baseline,
        baseline_agent_config=baseline_agent_config,
        opponent=opponent,
        opponent_digest=opponent_digest(opponent),
        gate_type=gate_type,
        n_seeds=n_seeds,
        seed_base=seed_base,
        seeds=seeds,
        candidate_result=candidate_result,
        baseline_result=baseline_result,
        per_seed=per_seed,
        money_verdict=verdict,
        opponent_mean_delta=opponent_mean_delta,
        min_opponent_money=min_opponent_money,
        candidate_canary_ran=candidate_canary_ran,
        candidate_canary_crashed=candidate_canary_crashed,
        baseline_canary_ran=baseline_canary_ran,
        baseline_canary_crashed=baseline_canary_crashed,
        extra_config=extra_config,
        threshold=threshold,
        alpha=alpha,
        min_seeds=min_seeds,
        catastrophic_tail_quantile=catastrophic_tail_quantile,
        catastrophic_tail_floor=catastrophic_tail_floor,
        candidate_money_floor=candidate_money_floor,
        opponent_money_floor=opponent_money_floor,
        degenerate_seed_fraction=degenerate_seed_fraction,
    )
