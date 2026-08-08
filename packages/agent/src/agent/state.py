"""Per-episode state tracking.

The runner may reuse a process across episodes, so every tracker here resets
itself whenever it sees step 0 (runner-facts decision, issue #15).
"""

from __future__ import annotations

from collections import deque
from typing import Any

TURNS_PER_DAY = 24


class StateTracker:
    """Minimal episode-scoped memory with a step-0 reset guard."""

    def __init__(self) -> None:
        self.episode_turns: int = 0
        self.last_step: int = -1

    def observe(self, obs: dict[str, Any]) -> None:
        step = int(obs.get("step", 0))
        if step == 0 or step < self.last_step:
            self.reset()
        self.last_step = step
        self.episode_turns += 1

    def reset(self) -> None:
        self.episode_turns = 0
        self.last_step = -1


# Engine-verified against kaggle_environments 1.32.4 (direct pass-vs-pass
# simulation, cross-checked with kaggriculture.py's _town_consume): town
# consumption is applied while processing the turn whose OWN observation had
# hour in {0, 12} (old_step % townCenterSellInterval(12) == 0), but that
# mutation to market["inventory"] only becomes VISIBLE in the *next*
# observation -- hour 1 or hour 13, never hour 0/12 and never hour 11/23.
TOWN_TICK_HOURS = (1, 13)

# TOWN_CENTER_DEMAND_SCHEDULE from the engine: [(20, 4), (10, 2), (0, 1)].
_TOWN_CENTER_MULT_THRESHOLDS: tuple[tuple[int, int], ...] = ((20, 4), (10, 2), (0, 1))

ROLLING_PRICE_WINDOW = 24
CONTESTED_CUMULATIVE_THRESHOLD = 12.0
CONTESTED_PRICE_DROP_THRESHOLD = 25.0


def _town_center_multiplier(day: int) -> int:
    for threshold, mult in _TOWN_CENTER_MULT_THRESHOLDS:
        if day >= threshold:
            return mult
    return 1  # unreachable (0 is the last threshold) -- defensive fallback only


def _town_draw(day: int, hour: int) -> int:
    """Melon units the town center is expected to have pulled out of the
    shared market inventory, visible in THIS observation. Melon is in no
    SHOPS entry (town-center-only demand), so this is the entire scheduled
    draw -- zero on every hour but the two post-tick reveal hours."""
    if hour not in TOWN_TICK_HOURS:
        return 0
    return _town_center_multiplier(day)


class MelonMarketMemory:
    """Cross-turn melon-market tracker (M2b): opponent-sell attribution, a
    rolling price ceiling, and the CONTESTED latch that switches
    ``market.py``'s melon policy from the static floor to the dynamic
    crash-response one.

    Opponent attribution per turn:
        opponent_sold = max(0, (inv_now - inv_prev) + town_draw - our_sold_last_turn)
    ``inv_now``/``inv_prev`` are the shared ``market["inventory"]["MELON"]``
    reading this turn and last; ``town_draw`` is the scheduled center draw
    (zero except at ``TOWN_TICK_HOURS``); ``our_sold_last_turn`` is whatever
    quantity ``record_our_melon_sell`` was told about after the previous
    ``observe`` call (the engine fills a SELL order fully against shed
    contents, so "what we ordered, clamped by what we held" is exact, not an
    estimate). CONTESTED latches -- true for the rest of the episode -- the
    moment cumulative opponent melons reach 12 or a day-over-day mean price
    drop reaches 25.

    Step-0 reset guard mirrors ``StateTracker`` (the runner may reuse a
    process across episodes). Never-crash law: ``observe`` never raises --
    any error while reading a malformed observation is swallowed and this
    turn's update is simply skipped, preserving whatever was already known
    rather than letting a bad turn corrupt state or (worse) propagate up
    through the safety shell and PASS-loop the agent for the rest of the
    game. A tracker that has never successfully latched CONTESTED reports
    False (the safe default); one that HAS already latched stays latched
    through a single bad observation too -- un-latching mid-crash would
    resurrect the exact static-floor bug this class exists to fix.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._last_step: int = -1
        self.prev_inventory: int | None = None
        self.cumulative_opponent_melons: float = 0.0
        self.contested: bool = False
        self.contested_since_day: int | None = None
        self._price_window: deque[float] = deque(maxlen=ROLLING_PRICE_WINDOW)
        self.rolling_price_max: float = 0.0
        self._current_day: int | None = None
        self._day_price_sum: float = 0.0
        self._day_price_count: int = 0
        self.prev_day_mean: float | None = None
        self.current_day_mean: float | None = None
        self._pending_our_sell: int = 0

    def record_our_melon_sell(self, qty: int) -> None:
        """Record this turn's actual MELON sell quantity (0 if none), read
        back by next turn's ``observe`` to net our own sale out of the
        opponent-attribution delta. Best-effort clamp to a non-negative int
        -- the never-crash law lives in ``observe``, not here, but a caller
        passing garbage shouldn't corrupt next turn's math."""
        try:
            self._pending_our_sell = max(0, int(qty))
        except (TypeError, ValueError):
            self._pending_our_sell = 0

    def days_since_contested(self, current_day: int) -> int:
        if not self.contested or self.contested_since_day is None:
            return 0
        return max(0, int(current_day) - self.contested_since_day)

    def observe(self, obs: dict[str, Any]) -> None:
        try:
            self._observe(obs)
        except Exception:
            # Never-crash law: skip this turn's update rather than raise or
            # corrupt state. A prior latch survives; a never-latched tracker
            # stays "not contested" (see class docstring).
            pass

    def _observe(self, obs: dict[str, Any]) -> None:
        step = int(obs.get("step", 0))
        if step == 0 or step < self._last_step:
            self.reset()
        self._last_step = step

        day = step // TURNS_PER_DAY
        hour = step % TURNS_PER_DAY
        market = obs.get("market") or {}
        inventory = market.get("inventory") or {}
        prices = market.get("prices") or {}
        inv_now = int(inventory.get("MELON", 0))
        price_now = float(prices.get("MELON", 0.0))

        if self.prev_inventory is not None:
            town_draw = _town_draw(day, hour)
            opponent_sold = max(
                0, (inv_now - self.prev_inventory) + town_draw - self._pending_our_sell
            )
            self.cumulative_opponent_melons += opponent_sold
        self.prev_inventory = inv_now
        self._pending_our_sell = 0

        self._price_window.append(price_now)
        self.rolling_price_max = max(self._price_window)

        if self._current_day is None:
            self._current_day = day
        elif day != self._current_day:
            self.prev_day_mean = self.current_day_mean
            self._current_day = day
            self._day_price_sum = 0.0
            self._day_price_count = 0
        self._day_price_sum += price_now
        self._day_price_count += 1
        self.current_day_mean = self._day_price_sum / self._day_price_count

        if self.cumulative_opponent_melons >= CONTESTED_CUMULATIVE_THRESHOLD:
            self._latch(day)
        elif (
            self.prev_day_mean is not None
            and (self.prev_day_mean - self.current_day_mean) >= CONTESTED_PRICE_DROP_THRESHOLD
        ):
            self._latch(day)

    def _latch(self, day: int) -> None:
        if not self.contested:
            self.contested = True
            self.contested_since_day = day
