"""Per-seat, per-item realized settlement, read from the engine's own commits.

Answers what a money delta structurally cannot: *where* a money difference
between two arms came from. A money gain can be revenue the arm earned or
spend the arm avoided, and the two have opposite implications -- an arm that
sells MORE into a shared market may simply be riding a price it lifted for
both players, while an arm that sells LESS and banks more cannot be.

Two engine facts make this exact rather than modelled:

- ``_commit_unit`` returns False and mutates nothing when an order cannot be
  filled (insufficient shed stock, insufficient money, full shed). A wrapper
  that records on CALL books rejected orders as fictional sales -- measured at
  26 of 80 EGG SELL calls on one seed. **Record on the return value.**
- ``_process_market`` clears both players unit-by-unit against one shared
  market, so a realized price is only knowable at commit time; recomputing it
  from a price law after the fact cannot see the interleaving.
- ``_do_hire`` and ``_do_buy_land`` **bypass** ``_commit_unit`` and write
  ``farm["money"]`` directly, and both return None whether or not they acted.
  They are therefore captured by differencing ``farm["money"]`` across the
  call, not by a return value. Before this was added, hire and land spend
  showed up only inside an undifferentiated residual, and a "cost-side"
  figure derived from that residual could not be attributed to either.

Seat is resolved by OBJECT IDENTITY against the farms list ``_process_market``
is working on, never by call order, and an unresolvable farm raises. A census
wired to the wrong seat returns clean, plausible, fictional numbers -- ``farms``
is re-broadcast to every seat, so nothing about a wrong-seat read looks wrong.

The shop roster is recorded alongside, because it is not independent of the
agent under test: ``_spawn_weeds`` advances the rng only for bare tiles and the
day's shop is drawn from that same stream, so any arm that changes occupancy
changes which shops exist to drain the market.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

SELL_OPS = ("SELL",)
BUY_OPS = ("BUY_PRODUCT", "BUY_SEED", "BUY_ANIMAL")

#: Spend keys for the two money paths that never reach ``_commit_unit``.
HIRE_KEY = "HIRE"
LAND_KEY = "BUY_LAND"


@dataclass
class Settlement:
    """One episode's realized settlement, per seat."""

    seed: int
    final_money: list[float]
    units: dict[int, dict[str, int]] = field(default_factory=dict)
    revenue: dict[int, dict[str, float]] = field(default_factory=dict)
    spend: dict[int, dict[str, float]] = field(default_factory=dict)
    shops: dict[str, int] = field(default_factory=dict)
    hires: dict[int, int] = field(default_factory=dict)
    calls: int = 0
    filled: int = 0
    rejected: int = 0

    def revenue_total(self, seat: int) -> float:
        return sum(self.revenue.get(seat, {}).values())

    def spend_total(self, seat: int) -> float:
        return sum(self.spend.get(seat, {}).values())

    def cost_side(self, seat: int) -> float:
        """Money not explained by realized revenue.

        ``final_money - starting - revenue`` would need the starting balance;
        this is the residual used pairwise between two arms, where the
        starting balance cancels: ``money_delta - revenue_delta``.

        ``_commit_unit``'s SELL branch is the engine's ONLY money inflow, so
        this residual is all outflow. That fact is pinned by
        ``test_sell_is_the_only_money_inflow_in_the_engine``, not merely
        asserted here -- an engine bump that added a subsidy or interest would
        silently turn this into a mixed residual with a green suite.
        """
        return self.final_money[seat] - self.revenue_total(seat)

    def hire_spend(self, seat: int) -> float:
        return self.spend.get(seat, {}).get(HIRE_KEY, 0.0)

    def land_spend(self, seat: int) -> float:
        return self.spend.get(seat, {}).get(LAND_KEY, 0.0)


class _Recorder:
    """Wraps the engine's settlement functions for one episode."""

    def __init__(self) -> None:
        self.units: dict[int, Counter[str]] = {0: Counter(), 1: Counter()}
        self.revenue: dict[int, Counter[str]] = {0: Counter(), 1: Counter()}
        self.spend: dict[int, Counter[str]] = {0: Counter(), 1: Counter()}
        self.hires: dict[int, int] = {0: 0, 1: 0}
        self.farms: list[Any] | None = None
        self.calls = 0
        self.filled = 0
        self.rejected = 0

    def seat_of(self, farm: Any) -> int:
        if self.farms is None:
            raise AssertionError(
                "settlement: _commit_unit fired before _process_market set the farms list; "
                "seat cannot be resolved and a guessed seat is worse than no measurement"
            )
        for i, candidate in enumerate(self.farms):
            if candidate is farm:
                return i
        raise AssertionError(
            "settlement: farm object not found in the market's farms list; "
            "refusing to attribute a commit to a guessed seat"
        )

    def record(self, ok: bool, op: str, item: str, price: float, farm: Any) -> None:
        self.calls += 1
        if not ok:
            self.rejected += 1
            return
        self.filled += 1
        seat = self.seat_of(farm)
        if op in SELL_OPS:
            self.units[seat][item] += 1
            self.revenue[seat][item] += float(price)
        elif op in BUY_OPS:
            self.spend[seat][f"{op}:{item}"] += float(price)

    def record_direct(self, key: str, farm: Any, spent: float) -> None:
        """Record a money path that never reaches ``_commit_unit``.

        ``spent`` is a measured ``farm["money"]`` decrease, so a call that
        no-opped (insufficient funds, all quadrants owned) records nothing --
        neither engine function reports success in its return value.
        """
        if spent <= 0:
            return
        seat = self.seat_of(farm)
        self.spend[seat][key] += float(spent)
        if key == HIRE_KEY:
            self.hires[seat] += 1


def measure(env: Any, recorder: _Recorder, seed: int) -> Settlement:
    """Build a Settlement from a finished episode and its recorder."""
    obs = env.steps[-1][0].observation
    farms = obs["farms"] if isinstance(obs, dict) else obs.farms
    town = (obs["town"] if isinstance(obs, dict) else obs.town) or {}
    return Settlement(
        seed=seed,
        final_money=[float(f.get("money", 0.0)) for f in farms],
        units={s: dict(recorder.units[s]) for s in (0, 1)},
        revenue={s: dict(recorder.revenue[s]) for s in (0, 1)},
        spend={s: dict(recorder.spend[s]) for s in (0, 1)},
        shops=dict(Counter(town.get("unlocked_shops", []))),
        hires=dict(recorder.hires),
        calls=recorder.calls,
        filled=recorder.filled,
        rejected=recorder.rejected,
    )


def play_with_settlement(
    seed: int,
    candidate: str,
    opponent: str,
    agent_config: dict[str, Any] | None = None,
    seat: int = 0,
) -> Settlement:
    """Run one episode with settlement recording active, then restore."""
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as engine

    from harness.episodes import resolve_agent

    recorder = _Recorder()
    original_pm = engine._process_market
    original_cu = engine._commit_unit
    original_hire = engine._do_hire
    original_land = engine._do_buy_land

    def pm_spy(state: Any, env_arg: Any) -> Any:
        recorder.farms = state[0].observation.farms
        return original_pm(state, env_arg)

    def cu_spy(
        op: str,
        item: str,
        price: float,
        farm: Any,
        private: Any,
        market: Any,
        shed_capacity: int = 100,
    ) -> bool:
        ok = original_cu(op, item, price, farm, private, market, shed_capacity)
        recorder.record(ok, op, item, price, farm)
        return ok

    def hire_spy(farm: Any, private: Any, board_size: int, *args: Any, **kwargs: Any) -> Any:
        before = farm["money"]
        result = original_hire(farm, private, board_size, *args, **kwargs)
        recorder.record_direct(HIRE_KEY, farm, before - farm["money"])
        return result

    def land_spy(farm: Any, board_size: int, *args: Any, **kwargs: Any) -> Any:
        before = farm["money"]
        result = original_land(farm, board_size, *args, **kwargs)
        recorder.record_direct(LAND_KEY, farm, before - farm["money"])
        return result

    engine._process_market = pm_spy
    engine._commit_unit = cu_spy
    engine._do_hire = hire_spy
    engine._do_buy_land = land_spy
    try:
        agents: list[Any] = [None, None]
        agents[seat] = (
            resolve_agent(candidate, agent_config) if agent_config else resolve_agent(candidate)
        )
        agents[1 - seat] = resolve_agent(opponent)
        env = make("kaggriculture", configuration={"seed": seed})
        env.run(agents)
    finally:
        engine._process_market = original_pm
        engine._commit_unit = original_cu
        engine._do_hire = original_hire
        engine._do_buy_land = original_land

    return measure(env, recorder, seed)
