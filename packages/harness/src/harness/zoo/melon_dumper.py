"""melon-dumper: a wheat-modest, melon-burst archetype that HOLDS its melon
harvest until a trigger fires, then dumps the entire backlog (and everything
harvested from then on) at index 0 with no price floor, for the rest of the
game (zoo #M2b, hardened v2).

Modeled directly on the ladder-observed opponent archetype that motivated
M2b: 231-270 melons sold cumulative, concentrated into a ~138-unit dump over
days 11-13 that crashed the shared melon price. v1 of this fixture (10 melon
tiles, sell-on-sight every turn, no hold) only produced ~99 melons spread
across the whole game and never crashed the price below the champion's
original $195 static floor -- a severity gap discovered from the M2b
comparative run's per-day trace (recovered-value delta only +$1963, at the
+$2k stop bar, with melon price never dipping under $222). v2 hardens the
archetype to actually match the observed severity:

- ~20 melon tiles (up from 10), planted in a staggered burst across the
  first few days (``MELON_DAILY_PLANT_CAP``, not a single-turn dump) so the
  crew can actually keep the whole zone watered rather than losing half of
  it to the 2-consecutive-unwatered weed rule -- concentrated enough
  (tuned to 3 days) that most of the zone shares a harvest-ready day
  (planted_day + ``MELON_HARVEST_AGE``), producing a real multi-day BURST
  once the backlog releases, not just a big cumulative total spread thin.
- HOLD: zero MELON sells at all until the trigger (shed melon >=
  ``MELON_HOLD_SHED_TRIGGER`` (40), OR day >= ``MELON_HOLD_DAY_TRIGGER``
  (12), whichever comes first) fires -- a real backlog accumulates instead
  of trickling out one harvest at a time.
- DUMP: once triggered, a ONE-WAY LATCH (not re-evaluated every turn) flips
  this fixture into permanent dump mode: every turn any melon sits in the
  shed, sell all of it, no floor, no cap -- and keep replanting/harvesting
  melon for the rest of the game, so the dumping continues rather than
  being a single one-off event.
- The wheat zone shrank from 8 to 4 tiles: the NW quadrant is only 24 tiles
  total excluding the shed corner, and melon's now-20-tile zone claims the
  rest. Still enough to fund seeds/hires while melon is held unsold.

This is no longer fully stateless like wheat-spam or melon-dumper v1: the
hold/dump switch is a genuine one-way latch, which needs real cross-turn
memory to stay latched (a purely obs-derived recomputation would flap back
to "hold" the instant shed drops back under 40 while day is still < 12,
contradicting "dump for the rest of the game"). ``make_agent()`` therefore
closes over a small mutable dict -- the same pattern ``agent.policy.make_
policy`` uses for its own trackers -- including a step-0 reset guard in case
a runner ever reuses one closure across episodes.

Acceptance test: this fixture's own teeth-check lives in
``harness.tests.test_melon_dumper``'s ``TestSeverityAcceptance`` class,
gating it against the three ladder-derived severity numbers (cumulative >=
180, a 3-day window >= 90, and melon price < $180 for >= 3 consecutive days)
so it can't silently regress back into decoration.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Position = tuple[int, int]

SHED_TILE: Position = (4, 4)
CARRY_THRESHOLD = 6  # walk-to-shed-and-DROP once a unit carries this much of either crop
TURNS_PER_DAY = 24
HANDS_PER_DAY = 5  # bumped from v1's 2 -- a 20-tile melon zone needs more daily crew throughput

MELON_ZONE_SIZE = 20  # "~20 melon tiles" -- the hardened burst archetype
WHEAT_ZONE_SIZE = 4  # shrunk from v1's 8: NW's 24 non-shed tiles are now mostly melon's
MELON_HARVEST_AGE = 12  # melon max_yield_day
WHEAT_HARVEST_AGE = 4  # wheat max_yield_day
MELON_LAST_PLANT_DAY = 19  # 10 growth days to first yield; day 19 is the last with any runway
WHEAT_LAST_PLANT_DAY = 25  # 4 growth days; day 25 is the last that can mature
MELON_SEED_COST = 80
WHEAT_SEED_COST = 10

# Tuned empirically against the TestSeverityAcceptance bar (see its
# docstring in harness.tests.test_melon_dumper): a first pass at cap=3
# (7-day fill) cleared cumulative (204) and the price-duration criterion but
# only hit a 54-melon best 3-day window (needs >= 90) -- tiles staggered
# across 7 planting days become harvest-ready across 7 different days too
# (planted_day + MELON_HARVEST_AGE), trickling out ~18/day instead of
# bursting. Widening the cap to 7 (3-day fill) concentrates most of the zone
# onto the same handful of harvest-ready days, producing a real burst (114
# in 3 days) instead of just a bigger cumulative total spread thin.
MELON_DAILY_PLANT_CAP = 7  # fills the 20-tile zone in 3 days (0-2)
MELON_HOLD_SHED_TRIGGER = 40  # dump trigger: shed backlog reaches this many
MELON_HOLD_DAY_TRIGGER = 12  # dump trigger: this day arrives -- whichever comes first


def _compute_zones(
    center: Position = SHED_TILE,
) -> tuple[tuple[Position, ...], tuple[Position, ...]]:
    """(melon_zone, wheat_zone): the nearest ``MELON_ZONE_SIZE`` tiles to
    ``center`` claim melon, the next ``WHEAT_ZONE_SIZE`` claim wheat -- 24
    tiles total, an exact fit for the NW quadrant's non-shed 5x5-minus-1
    universe. Deterministic: sorted by Manhattan distance, then (y, x)."""
    cx, cy = center
    candidates = [(x, y) for y in range(5) for x in range(5) if (x, y) != center]
    candidates.sort(key=lambda p: (abs(p[0] - cx) + abs(p[1] - cy), p[1], p[0]))
    melon_zone = tuple(candidates[:MELON_ZONE_SIZE])
    wheat_zone = tuple(candidates[MELON_ZONE_SIZE : MELON_ZONE_SIZE + WHEAT_ZONE_SIZE])
    return melon_zone, wheat_zone


MELON_TILES, WHEAT_TILES = _compute_zones()
MELON_SET = frozenset(MELON_TILES)
ALL_TILES = MELON_TILES + WHEAT_TILES
TARGET_SET = frozenset(ALL_TILES)


def _step_toward(x: int, y: int, tx: int, ty: int) -> list[str]:
    """One cardinal step toward (tx, ty); resolves x before y."""
    if x < tx:
        return ["EAST"]
    if x > tx:
        return ["WEST"]
    if y < ty:
        return ["SOUTH"]
    if y > ty:
        return ["NORTH"]
    return ["PASS"]


def _is_weed(tile: Any) -> bool:
    return isinstance(tile, dict) and tile.get("kind") == "WEED"


def _is_plant(tile: Any) -> bool:
    return isinstance(tile, dict) and tile.get("kind") == "PLANT"


def _grown_tile_need(tile: Any, day: int, harvest_age: int) -> str | None:
    """Naive water/harvest rule for a tile that's already a WEED or a live
    PLANT (crop-agnostic beyond ``harvest_age``): dig weeds, water any day
    not yet watered (no yield-window awareness needed -- watering outside a
    window is a harmless engine no-op, and still prevents the weed
    conversion), harvest once ripe. Returns "DIG", "WATER", "HARVEST", or
    None. Empty tiles (planting) are handled by the caller, which needs the
    per-turn daily-cap/staggering context this pure function doesn't have."""
    if _is_weed(tile):
        return "DIG"
    if _is_plant(tile):
        if not tile.get("watered_today", False):
            return "WATER"
        if tile.get("yield_units", 0) > 0 and (day - tile.get("planted_day", day)) >= harvest_age:
            return "HARVEST"
    return None


def _nearest_unclaimed(
    pos: Position, needy: list[Position], claimed: set[Position]
) -> Position | None:
    candidates = [t for t in needy if t not in claimed]
    if not candidates:
        return None
    x, y = pos
    return min(candidates, key=lambda t: (abs(t[0] - x) + abs(t[1] - y), ALL_TILES.index(t)))


def make_agent() -> Callable[[Any], dict[str, Any]]:
    """Return a fresh melon-dumper agent callable with its own episode-scoped
    hold/dump latch closed over (see module docstring for why this can't be
    fully stateless like wheat-spam or melon-dumper v1)."""
    state: dict[str, Any] = {"dump_mode": False, "last_step": -1}

    def agent(obs: Any) -> dict[str, Any]:
        player = obs["player"]
        farm = obs["farms"][player]
        private = obs["private"]
        seeds = private["seeds"]
        shed = private["shed"]
        step = obs["step"]
        day = step // TURNS_PER_DAY
        tiles = farm["tiles"]
        board_h = len(tiles)
        board_w = len(tiles[0]) if board_h else 0

        if step == 0 or step < state["last_step"]:
            state["dump_mode"] = False
        state["last_step"] = step

        def tile_at(x: int, y: int) -> Any:
            if 0 <= x < board_w and 0 <= y < board_h:
                return tiles[y][x]
            return "LOCKED"

        shed_melon = shed.get("MELON", 0)
        if not state["dump_mode"] and (
            shed_melon >= MELON_HOLD_SHED_TRIGGER or day >= MELON_HOLD_DAY_TRIGGER
        ):
            state["dump_mode"] = True

        # Empty melon tiles eligible for PLANT this turn: capped and chosen
        # deterministically (board order), staggering the 20-tile zone's
        # fill across several days instead of racing to plant all of them
        # the instant seeds land (module docstring explains why).
        melon_planted_today = sum(
            1
            for pos in MELON_TILES
            if isinstance(tile_at(*pos), dict)
            and tile_at(*pos).get("kind") == "PLANT"
            and tile_at(*pos).get("planted_day") == day
        )
        melon_plant_budget = max(0, MELON_DAILY_PLANT_CAP - melon_planted_today)
        empty_melon = [pos for pos in MELON_TILES if tile_at(*pos) is None]
        plantable_melon_today = set(empty_melon[:melon_plant_budget])

        def need_at(pos: Position) -> str | None:
            tile = tile_at(*pos)
            if pos in MELON_SET:
                if tile is None:
                    if day <= MELON_LAST_PLANT_DAY and pos in plantable_melon_today:
                        return "PLANT"
                    return None
                return _grown_tile_need(tile, day, MELON_HARVEST_AGE)
            if tile is None:
                return "PLANT" if day <= WHEAT_LAST_PLANT_DAY else None
            return _grown_tile_need(tile, day, WHEAT_HARVEST_AGE)

        unit_positions: list[Position] = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        inventories = private["inventories"]

        needy_tiles = [pos for pos in ALL_TILES if need_at(pos) is not None]

        # First pass: units already standing on a needy tile claim it outright.
        claimed: set[Position] = set()
        on_tile_need: dict[int, str] = {}
        for idx, pos in enumerate(unit_positions):
            if pos in TARGET_SET:
                need = need_at(pos)
                if need is not None:
                    on_tile_need[idx] = need
                    claimed.add(pos)

        remaining_melon_seeds = seeds.get("MELON", 0)
        remaining_wheat_seeds = seeds.get("WHEAT", 0)
        unit_actions: list[list[str]] = []
        for idx, pos in enumerate(unit_positions):
            x, y = pos
            if tile_at(x, y) == "LOCKED":
                unit_actions.append(_step_toward(x, y, *SHED_TILE))
                continue

            need = on_tile_need.get(idx)
            if need == "PLANT":
                if pos in MELON_SET:
                    if remaining_melon_seeds > 0:
                        remaining_melon_seeds -= 1
                        unit_actions.append(["PLANT", "MELON"])
                        continue
                elif remaining_wheat_seeds > 0:
                    remaining_wheat_seeds -= 1
                    unit_actions.append(["PLANT", "WHEAT"])
                    continue
                # No seed left for this unit's crop this turn -- fall through to idling.
            elif need is not None:
                unit_actions.append([need])
                continue

            inv = inventories[idx] if idx < len(inventories) else {}
            carried = (inv.get("WHEAT", 0) + inv.get("MELON", 0)) if isinstance(inv, dict) else 0
            if carried >= CARRY_THRESHOLD:
                if pos == SHED_TILE:
                    unit_actions.append(["DROP"])
                else:
                    unit_actions.append(_step_toward(x, y, *SHED_TILE))
                continue

            target = _nearest_unclaimed(pos, needy_tiles, claimed)
            if target is None:
                unit_actions.append(["PASS"])
                continue
            claimed.add(target)
            unit_actions.append(_step_toward(x, y, *target))

        farmer_action = unit_actions[0]
        hands_actions = unit_actions[1:]

        market: list[list[Any]] = []
        # Melon leads at index 0 -- but ONLY once the hold trigger has
        # latched (see module docstring). Before that: zero melon sells, on
        # purpose -- the whole point of this fixture is a real backlog.
        if state["dump_mode"] and shed_melon > 0:
            market.append(["SELL", "MELON", shed_melon])
        if shed.get("WHEAT", 0) > 0:
            market.append(["SELL", "WHEAT", 99999])
        if step % TURNS_PER_DAY == 0:
            for _ in range(HANDS_PER_DAY):
                market.append(["HIRE"])
            if day <= MELON_LAST_PLANT_DAY:
                needed_melon = max(0, len(plantable_melon_today) - seeds.get("MELON", 0))
                if needed_melon > 0:
                    affordable = int(farm["money"] // MELON_SEED_COST)
                    to_buy = min(needed_melon, affordable)
                    if to_buy > 0:
                        market.append(["BUY_SEED", "MELON", to_buy])
            if day <= WHEAT_LAST_PLANT_DAY:
                needed_wheat = max(
                    0,
                    sum(
                        1 for pos in WHEAT_TILES if tile_at(*pos) is None or _is_weed(tile_at(*pos))
                    )
                    - seeds.get("WHEAT", 0),
                )
                if needed_wheat > 0:
                    affordable = int(farm["money"] // WHEAT_SEED_COST)
                    to_buy = min(needed_wheat, affordable)
                    if to_buy > 0:
                        market.append(["BUY_SEED", "WHEAT", to_buy])

        return {"farmer": farmer_action, "hands": hands_actions, "market": market}

    return agent
