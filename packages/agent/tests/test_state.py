"""Cross-turn state: the step-0 reset guard (StateTracker) and the melon
opponent-sell attribution / CONTESTED latch (MelonMarketMemory, M2b).

Engine-verified timing (see docs/recon/engine-mechanics.md + direct
pass-vs-pass simulation against kaggle_environments 1.32.4): town-center
consumption is applied while processing the turn whose observation had
hour in {0, 12} (old step % 12 == 0), but that inventory change is only
VISIBLE in the *next* observation -- hour 1 or hour 13. All synthetic
observations below that are meant to land on/off a town tick use those
verified hours, not the hour-0/12 "fires at" hours and not hour 11/23.
"""

from __future__ import annotations

from typing import Any

from agent.state import MelonMarketMemory, StateTracker


def obs_at(step: int, *, inv: int = 10000, price: float = 250.0) -> dict[str, Any]:
    """A minimal engine-shaped observation with just the melon market fields
    MelonMarketMemory reads."""
    return {
        "step": step,
        "market": {"inventory": {"MELON": inv}, "prices": {"MELON": price}},
    }


# --- StateTracker (pre-existing; the step-0 reset guard other tests lean on) -


def test_state_tracker_resets_on_step_zero_after_a_late_step() -> None:
    tracker = StateTracker()
    tracker.observe({"step": 500})
    assert tracker.episode_turns == 1
    tracker.observe({"step": 0})
    assert tracker.episode_turns == 1
    assert tracker.last_step == 0


# --- MelonMarketMemory: baseline / plumbing -----------------------------------


def test_first_observation_only_establishes_a_baseline() -> None:
    mem = MelonMarketMemory()
    mem.observe(obs_at(0, inv=10000, price=250.0))
    assert mem.contested is False
    assert mem.cumulative_opponent_melons == 0
    assert mem.prev_inventory == 10000
    assert mem.rolling_price_max == 250.0


def test_step_zero_reset_guard_mirrors_state_tracker() -> None:
    mem = MelonMarketMemory()
    # A prior episode ran to a late step and looked contested...
    mem.observe(obs_at(100, inv=10000, price=250.0))
    mem.observe(obs_at(101, inv=10300, price=180.0))  # huge, unexplained jump
    mem.observe(obs_at(102, inv=10600, price=120.0))
    assert mem.contested is True
    # ...but the runner reused the process for a fresh episode (step 0 again).
    mem.observe(obs_at(0, inv=10000, price=250.0))
    assert mem.contested is False
    assert mem.cumulative_opponent_melons == 0


def test_our_own_sell_last_turn_is_netted_out_of_the_delta() -> None:
    mem = MelonMarketMemory()
    mem.observe(obs_at(100, inv=10000, price=250.0))  # hour 4, no town tick
    mem.record_our_melon_sell(2)  # we sold 2 melon this turn
    mem.observe(obs_at(101, inv=10002, price=249.0))  # hour 5: +2 inventory, all ours
    assert mem.cumulative_opponent_melons == 0
    assert mem.contested is False


def test_rolling_price_max_tracks_the_last_24_turns() -> None:
    mem = MelonMarketMemory()
    for i, price in enumerate([200.0, 260.0, 210.0]):
        mem.observe(obs_at(100 + i, inv=10000, price=price))
    assert mem.rolling_price_max == 260.0


# --- Teeth-check (a): CONTESTED latches on an opponent-dump-shaped sequence,
# and does NOT fire on a town-draw-only sequence. ------------------------------


def test_detector_latches_on_synthetic_opponent_dump_sequence() -> None:
    """Inventory keeps rising well beyond what town consumption ever removes,
    and we never record a sale of our own -- exactly the shape of an
    unexplained opponent dump. Hours (4, 5, 6) are deliberately off the town
    tick (1, 13) so the whole delta is attributable to a seller."""
    mem = MelonMarketMemory()
    mem.observe(obs_at(100, inv=10000, price=250.0))  # day 4, hour 4
    mem.observe(obs_at(101, inv=10006, price=240.0))  # day 4, hour 5: +6
    assert mem.contested is False  # 6 < 12, not latched yet
    mem.observe(obs_at(102, inv=10013, price=225.0))  # day 4, hour 6: +7 -> cumulative 13
    assert mem.contested is True
    assert mem.cumulative_opponent_melons == 13
    assert mem.contested_since_day == 4


def test_detector_does_not_fire_on_town_draw_only_sequence() -> None:
    """A pure two-pass game's actual melon-inventory trace (engine-verified):
    town center pulls exactly 1/tick pre-day-10, visible at hour 1 and 13
    every day, and nothing else ever touches melon inventory. No opponent
    sale exists in this trace at all -- the detector must stay quiet."""
    mem = MelonMarketMemory()
    ticks = [
        (0, 10000),
        (1, 9999),
        (13, 9998),
        (25, 9997),
        (37, 9996),
        (49, 9995),
        (61, 9994),
    ]
    for step, inv in ticks:
        mem.observe(obs_at(step, inv=inv, price=250.0 + (10000 - inv)))
    assert mem.contested is False
    assert mem.cumulative_opponent_melons == 0


def test_town_draw_scales_with_the_day_multiplier_and_stays_uncontested() -> None:
    """Same town-draw-only shape as above but spanning the day-10 (2x) and
    day-20 (4x) multiplier steps -- each delta below EXACTLY matches its
    day's scheduled multiplier (not just <= 0), so this only passes if the
    day-threshold lookup itself is right, not merely because max(0, ...)
    clamps a wrong-but-still-negative answer down to zero. Hand-picked,
    non-contiguous steps (this is a synthetic unit test of the multiplier
    table, not a full-game replay) -- only the delta between consecutive
    observations matters to the tracker."""
    mem = MelonMarketMemory()
    ticks = [
        (9 * 24, 10000),  # day 9 baseline (no delta on the first observation)
        (9 * 24 + 1, 9999),  # day 9, hour 1, mult 1: exact -1
        (9 * 24 + 13, 9998),  # day 9, hour 13, mult 1: exact -1
        (10 * 24 + 1, 9996),  # day 10, hour 1, mult 2: exact -2
        (10 * 24 + 13, 9994),  # day 10, hour 13, mult 2: exact -2
        (19 * 24 + 1, 9992),  # day 19, hour 1, mult 2: exact -2 (hand-picked delta)
        (19 * 24 + 13, 9990),  # day 19, hour 13, mult 2: exact -2
        (20 * 24 + 1, 9986),  # day 20, hour 1, mult 4: exact -4
        (20 * 24 + 13, 9982),  # day 20, hour 13, mult 4: exact -4
    ]
    for step, inv in ticks:
        mem.observe(obs_at(step, inv=inv, price=250.0))
    assert mem.contested is False
    assert mem.cumulative_opponent_melons == 0


# --- Day-over-day mean price drop trigger -------------------------------------


def test_contested_latches_on_a_big_day_over_day_mean_price_drop() -> None:
    mem = MelonMarketMemory()
    # A full, uneventful day 0 at ~250.
    for hour in range(24):
        mem.observe(obs_at(hour, inv=10000, price=250.0))
    assert mem.contested is False
    # Day 1 opens with price crashed by an off-screen dump (inventory delta
    # is irrelevant here -- this test isolates the price-drop trigger).
    mem.observe(obs_at(24, inv=10000, price=180.0))  # day 1, hour 0: mean-so-far 180
    assert mem.contested is True
    assert mem.contested_since_day == 1


def test_small_day_over_day_drop_stays_uncontested() -> None:
    mem = MelonMarketMemory()
    for hour in range(24):
        mem.observe(obs_at(hour, inv=10000, price=250.0))
    mem.observe(obs_at(24, inv=10000, price=245.0))  # day 1: -5, single-digit noise
    assert mem.contested is False


# --- days_since_contested ------------------------------------------------------


def test_days_since_contested_counts_from_the_latch_day() -> None:
    mem = MelonMarketMemory()
    mem.observe(obs_at(100, inv=10000, price=250.0))
    mem.observe(obs_at(101, inv=10006, price=240.0))
    mem.observe(obs_at(102, inv=10013, price=225.0))  # latches on day 4
    assert mem.days_since_contested(4) == 0
    assert mem.days_since_contested(7) == 3


def test_days_since_contested_is_zero_when_not_contested() -> None:
    mem = MelonMarketMemory()
    mem.observe(obs_at(0, inv=10000, price=250.0))
    assert mem.days_since_contested(10) == 0


# --- Teeth-check (g): a malformed observation degrades to not-contested, ------
# never raises, and never PASS-loops the agent by propagating. ----------------


def test_malformed_observation_degrades_to_not_contested_never_raises() -> None:
    mem = MelonMarketMemory()
    mem.observe({"step": 0})  # no "market" key at all
    assert mem.contested is False

    mem.observe({"step": 1, "market": None})  # market present but None
    assert mem.contested is False

    mem.observe({"step": 2, "market": {"inventory": "not-a-dict", "prices": []}})
    assert mem.contested is False

    mem.observe("not even a dict")  # type: ignore[arg-type]
    assert mem.contested is False

    mem.observe({"step": "banana", "market": {}})  # non-numeric step
    assert mem.contested is False


def test_malformed_observation_after_a_real_latch_does_not_unlatch() -> None:
    """A single poisoned observation must not erase an already-detected
    crash -- un-latching mid-crash would resurrect the static-floor bug this
    tracker exists to fix."""
    mem = MelonMarketMemory()
    mem.observe(obs_at(100, inv=10000, price=250.0))
    mem.observe(obs_at(101, inv=10006, price=240.0))
    mem.observe(obs_at(102, inv=10013, price=225.0))
    assert mem.contested is True

    # inventory is a truthy non-dict: market.get("inventory") or {} keeps the
    # string as-is (truthy short-circuits the fallback), so .get("MELON", 0)
    # genuinely raises AttributeError -- this exercises the try/except path,
    # not just the defensive "or {}" fallback.
    mem.observe({"step": 103, "market": {"inventory": "garbage"}})
    assert mem.contested is True  # still latched
