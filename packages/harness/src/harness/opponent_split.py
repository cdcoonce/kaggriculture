"""Decompose a money gate's OPPONENT money delta into mechanism buckets.

kaggriculture#82 named the daily shop-roster draw as a mediator that any
occupancy-moving arm disturbs (see ``harness.shop_roster``). The 2026-09-05
hand-mule-load third registration's addendum made the consequence concrete: a
redirection criterion that bounds the WHOLE ``opponent_mean_delta`` cannot
tell genuine market suppression apart from that mediator's noise or from a
fixed-price affordability cascade -- and it fired on exactly that ambiguity
(thunder -3,997, mirror -3,928) after every intersection-union money bar had
cleared. Its addendum recorded, as hypothesis only, that the +/-$3,000 band
was inherited from the strawberry-closure convention without ever being
priced against a mechanism. This module is the mechanism-aware instrument
the successor registration
(``eval/prereg/2026-09-05-hand-mule-load-successor-registration.md``) needs
before any new run: it decomposes the opponent's seat-averaged, arm-diffed
money delta into

- ``traded_market``  -- settled SELL revenue minus settled BUY_PRODUCT cost,
  summed over items the CHAMPION side (candidate or baseline) also traded.
  This is the only channel the champion's own market behavior prices.
- ``untraded_market`` -- the same settled market flows, but for items the
  champion never touched -- roster-draw / weed-roll mediator noise
  (kaggriculture#82), not a market the champion's behavior could have moved.
- ``fixed_price`` -- BUY_SEED / BUY_ANIMAL / HIRE / BUY_LAND spend, all at
  catalog or fib prices no order ever clears against. Differs across arms
  only through affordability and fill cascades, never through a shared price.

HAZARDS:

- SUBMITTED-vs-SETTLED: an order the engine REJECTS (insufficient stock,
  insufficient money, a full shed) moves no money at all, but a recorder
  keyed on ``action['market']`` books it anyway -- measured at 26 of 80 EGG
  SELL calls, worth a fictional $1,201 on one seed
  (``harness.settlement``'s own docstring). This module reads ONLY
  ``harness.settlement.Settlement``'s already-settled ``revenue`` /
  ``spend`` maps, never a raw action. Counting submitted orders instead is
  mutation check (e) in the PR that introduced this module.
- SEAT: the gate plays each seed at BOTH candidate seats per arm
  (``harness.gate._play_seed_pair`` / ``run_gate``), and the opponent
  ALWAYS sits at ``1 - candidate_seat``, never at ``candidate_seat`` itself.
  Reading the candidate's own seat instead returns a clean, plausible,
  wrong-player's numbers with nothing about it looking wrong -- see
  ``episode_opponent_flows`` and mutation check (c).
- SIGN: every bucket is a contribution to the OPPONENT's money DELTA between
  the candidate and baseline arms. Revenue is a positive contribution, every
  cost is a negative one, so the three buckets sum to the seat-averaged,
  arm-diffed total BY CONSTRUCTION -- a bucket is never independently
  re-derived in a way that could silently break that identity.

Design notes: pure stdlib plus existing ``harness`` imports. The arithmetic
(``opponent_flows``, ``champion_traded_items``, ``bucket_seed``,
``episode_opponent_flows``) is deliberately factored out of ``split_ledger``
so it is unit-testable against hand-built ``harness.settlement.Settlement``
fixtures, with no engine and no tape required.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any

from harness.settlement import Settlement, play_with_settlement

#: ``configuration["startingMoney"]`` default in the engine itself
#: (``kaggle_environments.envs.kaggriculture.kaggriculture``). Read here only
#: to compute the conservation identity's baseline; never used to configure a
#: replay.
DEFAULT_STARTING_MONEY = 3000.0


def opponent_flows(
    settlement: Settlement, opponent_seat: int
) -> tuple[dict[str, float], dict[str, float]]:
    """Split one seat's settled money into market-priced vs fixed-price flows.

    Returns ``(per_item_market, fixed_price_map)``:

    - ``per_item_market[item]`` is settled SELL revenue minus settled
      BUY_PRODUCT cost, for every item that appears on EITHER side -- the
      only two order types that clear against the shared market
      (``harness.settlement.SELL_OPS`` / the ``BUY_PRODUCT`` half of
      ``BUY_OPS``). An item with a buyback but no sell still appears, priced
      as a pure negative.
    - ``fixed_price_map`` holds every OTHER spend key (``BUY_SEED:*``,
      ``BUY_ANIMAL:*``, ``HIRE``, ``BUY_LAND``) as a NEGATIVE contribution --
      money only ever leaves a seat through these four paths, never arrives.
    """
    revenue = settlement.revenue.get(opponent_seat, {})
    spend = settlement.spend.get(opponent_seat, {})

    buyback_items = {
        key.removeprefix("BUY_PRODUCT:") for key in spend if key.startswith("BUY_PRODUCT:")
    }
    per_item_market = {
        item: revenue.get(item, 0.0) - spend.get(f"BUY_PRODUCT:{item}", 0.0)
        for item in set(revenue) | buyback_items
    }
    fixed_price_map = {
        key: -value for key, value in spend.items() if not key.startswith("BUY_PRODUCT:")
    }
    return per_item_market, fixed_price_map


def episode_opponent_flows(
    settlement: Settlement, candidate_seat: int
) -> tuple[dict[str, float], dict[str, float]]:
    """``opponent_flows`` for the seat the CANDIDATE does NOT occupy.

    The gate always plays the opponent at ``1 - candidate_seat``
    (``harness.episodes.play_game``: ``opponent_seat = 1 - candidate_seat``),
    never at ``candidate_seat`` itself. Reading ``candidate_seat`` here
    instead would split the CANDIDATE's own money as if it were the
    opponent's -- clean, plausible, and wrong. See mutation check (c).
    """
    return opponent_flows(settlement, 1 - candidate_seat)


def episode_residual(
    settlement: Settlement, seat: int, final_money: float, starting_money: float
) -> float:
    """How far ``final_money`` is from everything ``opponent_flows`` explains.

    Zero on a consistent episode:
    ``final_money == starting_money + sum(per_item_market) + sum(fixed_price_map)``.
    Takes ``final_money`` / ``starting_money`` as explicit arguments, rather
    than reading ``settlement.final_money[seat]`` itself, so a caller can
    check a LEDGER's recorded money against this SAME settlement's flows --
    which is exactly what ``split_ledger`` does.
    """
    per_item_market, fixed_price_map = opponent_flows(settlement, seat)
    return (
        final_money - starting_money - sum(per_item_market.values()) - sum(fixed_price_map.values())
    )


def champion_traded_items(
    settlements: Sequence[Settlement], champion_seats: Sequence[int]
) -> set[str]:
    """Union of items the CHAMPION side settled a SELL or BUY_PRODUCT in.

    ``champion_seats[i]`` is the seat the champion -- whichever arm's own
    agent, candidate or baseline -- occupied in ``settlements[i]``; the two
    sequences are zipped positionally, one entry per episode of the run. A
    champion BUY_SEED / BUY_ANIMAL touches no shared market and does NOT put
    an item in this set (see the module docstring's bucket definitions).
    """
    if len(settlements) != len(champion_seats):
        raise ValueError(
            "settlements and champion_seats must be the same length, "
            f"got {len(settlements)} and {len(champion_seats)}"
        )
    items: set[str] = set()
    for settlement, seat in zip(settlements, champion_seats, strict=True):
        revenue = settlement.revenue.get(seat, {})
        spend = settlement.spend.get(seat, {})
        items.update(revenue)
        items.update(
            key.removeprefix("BUY_PRODUCT:") for key in spend if key.startswith("BUY_PRODUCT:")
        )
    return items


def _seat_average(a: Mapping[str, float], b: Mapping[str, float]) -> dict[str, float]:
    """Mean of two per-episode maps over the union of both keys.

    Mirrors ``harness.gate._seat_mean``'s ``(seats[0] + seats[1]) / 2.0``, in
    the same argument order, so a caller that feeds this the seat-0 episode
    first and the seat-1 episode second stays IEEE-identical to the gate's
    own seat-averaged statistic.
    """
    return {key: (a.get(key, 0.0) + b.get(key, 0.0)) / 2.0 for key in set(a) | set(b)}


def _diff(a: Mapping[str, float], b: Mapping[str, float]) -> dict[str, float]:
    """``a - b`` over the union of both maps' keys."""
    return {key: a.get(key, 0.0) - b.get(key, 0.0) for key in set(a) | set(b)}


def ledger_form_opponent_mean_delta(
    candidate_seat_means: Mapping[int, float],
    baseline_seat_means: Mapping[int, float],
) -> float:
    """gate.py's own association for ``opponent_mean_delta`` -- diff-of-means.

    Replicates gate.py lines 516-522 exactly: ``sum(candidate)/n -
    sum(baseline)/n`` over sorted seeds. This is NOT interchangeable with
    mean-of-diffs (``sum(c_i - b_i)/n``): both are exact up to the division,
    but an ``n`` with an odd factor rounds the two associations differently
    (observed ~5e-12 apart on the real metac95 n=384 ledger). Bit-equality
    with the ledgered value requires this form.
    """
    if set(candidate_seat_means) != set(baseline_seat_means):
        raise ValueError("the two arms did not cover the same seeds")
    seeds = sorted(candidate_seat_means)
    n = len(seeds)
    return (
        sum(candidate_seat_means[seed] for seed in seeds) / n
        - sum(baseline_seat_means[seed] for seed in seeds) / n
    )


@dataclass(frozen=True)
class SeedSplit:
    """One seed's opponent money delta: seat-averaged per arm, then arm-diffed."""

    seed: int
    traded_market: float
    untraded_market: float
    fixed_price: float
    total: float


@dataclass(frozen=True)
class SplitResult:
    """The full decomposition of one money ledger's opponent delta."""

    seeds: list[SeedSplit]
    traded_items: list[str]
    mean_traded_market: float
    mean_untraded_market: float
    mean_fixed_price: float
    mean_total: float
    max_residual: float


def bucket_seed(
    seed: int,
    candidate_ep0: tuple[Mapping[str, float], Mapping[str, float]],
    candidate_ep1: tuple[Mapping[str, float], Mapping[str, float]],
    baseline_ep0: tuple[Mapping[str, float], Mapping[str, float]],
    baseline_ep1: tuple[Mapping[str, float], Mapping[str, float]],
    traded_items: set[str] | frozenset[str],
) -> SeedSplit:
    """Seat-average each arm's two episodes, arm-diff, then bucket by ``traded_items``.

    Each ``*_epN`` argument is one episode's ``(per_item_market,
    fixed_price_map)`` pair for the OPPONENT's seat (e.g. from
    ``episode_opponent_flows``), where ``N`` is the CANDIDATE's (or
    baseline's, for the baseline arm) seat in that episode -- ``ep0`` is the
    episode where that arm's own agent sat at seat 0. Buckets sum to
    ``total`` by construction; swapping the candidate and baseline arguments
    flips the sign of every bucket (see the arm-swap mutation check in
    ``test_opponent_split.py``).
    """
    candidate_market = _seat_average(candidate_ep0[0], candidate_ep1[0])
    candidate_fixed = _seat_average(candidate_ep0[1], candidate_ep1[1])
    baseline_market = _seat_average(baseline_ep0[0], baseline_ep1[0])
    baseline_fixed = _seat_average(baseline_ep0[1], baseline_ep1[1])

    diff_market = _diff(candidate_market, baseline_market)
    diff_fixed = _diff(candidate_fixed, baseline_fixed)

    traded_market = sum(value for item, value in diff_market.items() if item in traded_items)
    untraded_market = sum(value for item, value in diff_market.items() if item not in traded_items)
    fixed_price = sum(diff_fixed.values())

    return SeedSplit(
        seed=seed,
        traded_market=traded_market,
        untraded_market=untraded_market,
        fixed_price=fixed_price,
        total=traded_market + untraded_market + fixed_price,
    )


#: The four episode keys ``split_ledger`` reconstructs per seed -- candidate
#: arm at both seats, then baseline arm at both seats. Shared by
#: ``_play_seed_episodes`` (the sequential, single-task-per-seed path) and
#: ``split_ledger``'s parallel path (one ``ProcessPoolExecutor`` task per
#: key) so the two paths can never drift on what a "seed's episodes" means.
_EPISODE_KEYS: tuple[str, str, str, str] = ("candidate0", "candidate1", "baseline0", "baseline1")


def _episode_task_args(
    key: str,
    seed: int,
    candidate: str,
    opponent: str,
    baseline: str,
    agent_config: dict[str, Any] | None,
    baseline_agent_config: dict[str, Any] | None,
) -> tuple[int, str, str, dict[str, Any] | None, int]:
    """The exact positional ``play_with_settlement(seed, spec, opponent,
    config, seat)`` args for one episode ``key`` (one of ``_EPISODE_KEYS``).

    Pulled out of ``split_ledger``'s parallel branch so a fast test can
    assert, without ever touching ``ProcessPoolExecutor`` or the engine, that
    every submitted task's arguments are plain picklable data (a seed int, two
    spec strings, an ``agent_config`` dict-or-``None``, a seat int -- never a
    resolved agent or a ``Settlement``/``_Recorder`` object) in the order
    ``play_with_settlement`` itself expects. ``key``'s own trailing digit is
    its seat; the ``"candidate"``/``"baseline"`` prefix picks that arm's spec
    and config, exactly as ``_play_seed_episodes`` (the sequential path)
    does inline.
    """
    if key.startswith("candidate"):
        spec, config = candidate, agent_config
    else:
        spec, config = baseline, baseline_agent_config
    return seed, spec, opponent, config, int(key[-1])


def _play_seed_episodes(
    seed: int,
    candidate: str,
    opponent: str,
    baseline: str,
    agent_config: dict[str, Any] | None,
    baseline_agent_config: dict[str, Any] | None,
) -> dict[str, Settlement]:
    """Play one seed's four episodes exactly as ``harness.gate.run_money_gate`` does.

    Candidate arm at both seats, then baseline arm at both seats -- matching
    ``harness.gate._play_seed_pair`` / ``run_gate``'s seat/agent construction
    (each arm's OWN agent goes through ``resolve_agent(spec, that arm's
    agent_config)``; the opponent never receives an ``agent_config``). Kept
    module-level and picklable, like ``harness.episodes.play_game``, so it
    can run under ``ProcessPoolExecutor`` -- but ``split_ledger`` only ever
    hands it to the pool on the SEQUENTIAL (``workers <= 1``) path, mirroring
    ``run_gate``'s own restriction of the bundled ``_play_seed_pair`` helper
    to its ``workers <= 1`` branch (see ``split_ledger``'s parallel branch,
    which submits ``harness.settlement.play_with_settlement`` directly, one
    task per episode, matching ``run_gate``'s per-episode granularity).
    """
    return {
        "candidate0": play_with_settlement(seed, candidate, opponent, agent_config, seat=0),
        "candidate1": play_with_settlement(seed, candidate, opponent, agent_config, seat=1),
        "baseline0": play_with_settlement(seed, baseline, opponent, baseline_agent_config, seat=0),
        "baseline1": play_with_settlement(seed, baseline, opponent, baseline_agent_config, seat=1),
    }


def _row_opponent_money(
    rows: list[dict[str, Any]], seed: int, candidate_seat: int, *, arm: str
) -> float:
    for row in rows:
        if row["seed"] == seed and row["candidate_seat"] == candidate_seat:
            return float(row["opponent_money"])
    raise ValueError(
        f"opponent_split: no {arm} row for seed {seed} candidate_seat {candidate_seat}"
    )


def split_ledger(
    ledger: dict[str, Any],
    *,
    progress: Callable[[int, int], None] | None = None,
    workers: int = 1,
) -> SplitResult:
    """Decompose a money-gate ledger's opponent delta into mechanism buckets.

    Reconstructs the FOUR settled episodes ``harness.gate.run_money_gate``
    played for every seed in ``ledger["seed_manifest"]["seeds"]`` (candidate
    arm at both seats, baseline arm at both seats), via
    ``harness.settlement.play_with_settlement`` -- settled fills, never
    submitted orders. Every episode is checked TWICE before anything is
    bucketed:

    1. the conservation identity holds for the opponent's seat
       (``episode_residual`` is exactly zero), and
    2. the replayed opponent money matches the ledger's own recorded row
       EXACTLY (``rows`` for the candidate arm, ``baseline_rows`` for the
       baseline arm, keyed by ``candidate_seat``).

    Only once every episode has passed both checks are the champion-traded
    items unioned (``champion_traded_items``) and each seed bucketed
    (``bucket_seed``). The aggregate ``mean_total`` is then checked against
    the ledger's own ``money_verdict.opponent_mean_delta`` with exact ``==``
    -- the whole run raises rather than return a decomposition of a run this
    instrument could not faithfully reproduce.

    ASSOCIATION HAZARD: that aggregate must be computed with gate.py's OWN
    association -- diff-of-means (``sum(cand)/n - sum(base)/n``, gate.py's
    ``opponent_mean_delta`` at its lines 516-522), never mean-of-diffs
    (``sum(cand_i - base_i)/n``). Every per-episode money value here is a
    dyadic rational (integer prices, seat-means halve them once), so sums
    are exact -- but dividing by an ``n`` with an odd factor rounds, and the
    two associations round DIFFERENTLY: on the real metac95 n=384 ledger
    they disagree by ~5e-12, which the exact ``==`` correctly refused. At
    power-of-two n (256, 512) the division is exact and both associations
    coincide, which is why the defect hid on thunder/mirror/barnyard.
    ``ledger_form_opponent_mean_delta`` is that replication;
    ``mean_total`` reports its value so the decomposition's headline number
    is bit-identical to the ledger's. Per-seed ``SeedSplit.total`` values
    remain exact per-seed sums of their own buckets.

    ``workers`` parallelizes the replay with ``ProcessPoolExecutor`` exactly
    the way ``harness.gate.run_gate`` does: submit every task up front, then
    collect in submission order. The default of 1 runs sequentially
    in-process via ``_play_seed_episodes`` (one seed's four episodes per
    call) -- what every test in this module (and the fast path generally)
    exercises. ``workers > 1`` submits ``harness.settlement.
    play_with_settlement`` directly, ONE TASK PER EPISODE (four tasks per
    seed), mirroring ``run_gate``'s own split: its bundled
    ``_play_seed_pair`` helper runs only the ``workers <= 1`` branch, and its
    ``workers > 1`` branch submits the raw per-episode ``play_game`` so no
    single task holds more than one game's worth of work. Submitting the
    bundled ``_play_seed_episodes`` to the pool instead would still be
    module-level and picklable, but a task four times the size of gate.py's
    quadruples the blast radius of any one slow or wedged episode and
    coarsens load balancing across ``workers`` -- a real divergence from the
    "mirrors run_gate's pattern" this module's own introducing PR claimed,
    and the shape of the reported ``--workers 8`` stall on a 512-seed ledger.
    ``progress(seed_index, n_seeds)`` (0-based) is called once per seed,
    after that seed's four episodes are collected but before verification --
    for the CLI to report progress on a long replay.

    A non-empty ``identity.extra_config`` is refused (``NotImplementedError``)
    before any game is played: ``harness.settlement.play_with_settlement``
    does not forward ``extra_config`` into the engine's own configuration the
    way ``harness.episodes.play_game`` does, so a replay under a non-default
    config would silently diverge from the recorded run instead of raising on
    a genuine mismatch. No committed ledger in this repo sets a non-null
    ``extra_config`` today.
    """
    identity = ledger["identity"]
    candidate = identity["candidate"]
    opponent = identity["opponent"]
    baseline = identity["baseline"]
    agent_config = identity.get("agent_config")
    baseline_agent_config = identity.get("baseline_agent_config")
    extra_config = identity.get("extra_config")
    if extra_config:
        raise NotImplementedError(
            "opponent_split cannot replay a ledger recorded with a non-empty "
            f"identity.extra_config ({extra_config!r}): harness.settlement."
            "play_with_settlement does not forward extra_config to the engine, "
            "so a replay would silently diverge from the recorded run rather "
            "than raising on a real mismatch."
        )
    starting_money = float((extra_config or {}).get("startingMoney", DEFAULT_STARTING_MONEY))

    seeds = sorted(ledger["seed_manifest"]["seeds"])
    n_seeds = len(seeds)
    rows = ledger["rows"]
    baseline_rows = ledger["baseline_rows"]

    seed_episodes: dict[int, dict[str, Settlement]] = {}
    if workers <= 1:
        for index, seed in enumerate(seeds):
            seed_episodes[seed] = _play_seed_episodes(
                seed, candidate, opponent, baseline, agent_config, baseline_agent_config
            )
            if progress is not None:
                progress(index, n_seeds)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            # One ``play_with_settlement`` task per EPISODE (four per seed),
            # matching ``harness.gate.run_gate``'s per-episode
            # ``pool.submit(play_game, seed, seat, candidate, opponent, ...)``
            # granularity instead of bundling a seed's four episodes
            # (``_play_seed_episodes``) into one task -- see this function's
            # docstring for why that bundling was the bug.
            futures = {
                (seed, key): pool.submit(
                    play_with_settlement,
                    *_episode_task_args(
                        key,
                        seed,
                        candidate,
                        opponent,
                        baseline,
                        agent_config,
                        baseline_agent_config,
                    ),
                )
                for seed in seeds
                for key in _EPISODE_KEYS
            }
            for index, seed in enumerate(seeds):
                seed_episodes[seed] = {key: futures[(seed, key)].result() for key in _EPISODE_KEYS}
                if progress is not None:
                    progress(index, n_seeds)

    #: ``arm_rows[key] = (row list, candidate_seat for that row lookup)``.
    arm_rows = {
        "candidate0": (rows, 0),
        "candidate1": (rows, 1),
        "baseline0": (baseline_rows, 0),
        "baseline1": (baseline_rows, 1),
    }

    all_settlements: list[Settlement] = []
    all_champion_seats: list[int] = []
    max_residual = 0.0
    opponent_money: dict[tuple[str, int, int], float] = {}

    for seed in seeds:
        for key, settlement in seed_episodes[seed].items():
            row_source, candidate_seat = arm_rows[key]
            arm = "candidate" if key.startswith("candidate") else "baseline"
            opponent_seat = 1 - candidate_seat

            recorded_opponent_money = _row_opponent_money(row_source, seed, candidate_seat, arm=arm)
            final_money = settlement.final_money[opponent_seat]
            if final_money != recorded_opponent_money:
                raise ValueError(
                    f"opponent_split: seed {seed} arm={arm} candidate_seat={candidate_seat} "
                    f"opponent_seat={opponent_seat}: replayed opponent money {final_money!r} "
                    f"!= ledgered {recorded_opponent_money!r}"
                )

            residual = episode_residual(settlement, opponent_seat, final_money, starting_money)
            max_residual = max(max_residual, abs(residual))
            if residual != 0.0:
                raise ValueError(
                    f"opponent_split: seed {seed} arm={arm} candidate_seat={candidate_seat} "
                    f"opponent_seat={opponent_seat}: conservation residual {residual!r} != 0"
                )

            all_settlements.append(settlement)
            all_champion_seats.append(candidate_seat)
            opponent_money[(arm, seed, candidate_seat)] = final_money

    traded_items = champion_traded_items(all_settlements, all_champion_seats)

    seed_splits: list[SeedSplit] = []
    for seed in seeds:
        episodes = seed_episodes[seed]
        candidate_ep0 = episode_opponent_flows(episodes["candidate0"], candidate_seat=0)
        candidate_ep1 = episode_opponent_flows(episodes["candidate1"], candidate_seat=1)
        baseline_ep0 = episode_opponent_flows(episodes["baseline0"], candidate_seat=0)
        baseline_ep1 = episode_opponent_flows(episodes["baseline1"], candidate_seat=1)
        seed_splits.append(
            bucket_seed(
                seed, candidate_ep0, candidate_ep1, baseline_ep0, baseline_ep1, traded_items
            )
        )

    mean_traded_market = sum(s.traded_market for s in seed_splits) / n_seeds
    mean_untraded_market = sum(s.untraded_market for s in seed_splits) / n_seeds
    mean_fixed_price = sum(s.fixed_price for s in seed_splits) / n_seeds

    candidate_seat_means = {
        seed: (opponent_money[("candidate", seed, 0)] + opponent_money[("candidate", seed, 1)])
        / 2.0
        for seed in seeds
    }
    baseline_seat_means = {
        seed: (opponent_money[("baseline", seed, 0)] + opponent_money[("baseline", seed, 1)]) / 2.0
        for seed in seeds
    }
    mean_total = ledger_form_opponent_mean_delta(candidate_seat_means, baseline_seat_means)

    ledgered_delta = ledger["money_verdict"]["opponent_mean_delta"]
    if mean_total != ledgered_delta:
        raise ValueError(
            f"opponent_split: aggregate mean_total {mean_total!r} != ledgered "
            f"money_verdict.opponent_mean_delta {ledgered_delta!r}"
        )

    return SplitResult(
        seeds=seed_splits,
        traded_items=sorted(traded_items),
        mean_traded_market=mean_traded_market,
        mean_untraded_market=mean_untraded_market,
        mean_fixed_price=mean_fixed_price,
        mean_total=mean_total,
        max_residual=max_residual,
    )
