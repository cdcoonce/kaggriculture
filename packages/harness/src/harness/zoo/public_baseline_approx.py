"""public-baseline-approx: an approximation of the publicly documented
"Barnyard Economist v5" notebook baseline (zoo #10, gate-zoo cap member).

Source: ``docs/recon/public-meta.md``, item 1 -- "[STRONG STATR] Baseline
Agent | LB 950+" by Roman Rozen. Concretely stated in the source and used
as-is here: the opening $3,000 bankroll goes into livestock BEFORE land
(``public-meta.md:68-69``, "do not spend on land before day 4"), a wheat
"filler crop" keeps the pen from ever blocking (``public-meta.md:65-66``),
and roles are a pure function of unlocked quadrants rather than being
recomputed from cash/herd size every turn (``public-meta.md:63-64``) -- this
fixture never buys land, so with only NW ever unlocked that function has
exactly one possible output for the whole game, trivially satisfying the fix.

Everything else (herd composition, zone sizes, hand count, "never" instead
of "not before day 4" for land) is a default chosen by this spec, since the
source's own build diary doesn't give concrete numbers for them -- see the
issue body for the full accounting. No melon, no fertilizer, no land, ever;
animals exist for the day-0 livestock-first spend and the ongoing FEED/CARE
loop only, not a husbandry-to-market pipeline.

Stateless and deterministic: every decision is derived fresh from ``obs``
each call, so a factory-returned closure carries no cross-episode state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Position = tuple[int, int]

SHED_TILE: Position = (4, 4)
SHED_ACCESS_TILES: tuple[Position, ...] = ((4, 4), (5, 4), (4, 5), (5, 5))
SHED_ACCESS_SET = frozenset(SHED_ACCESS_TILES)

TURNS_PER_DAY = 24
HANDS_PER_DAY = 3  # default chosen here; the source gives no concrete number

COOP_ZONE_SIZE = 2  # 1 tile per GOOSE
PASTURE_ZONE_SIZE = 4  # 1 tile per COW/SHEEP
WHEAT_ZONE_SIZE = 18  # default chosen here; the source names the crop, not a tile count

WHEAT_HARVEST_AGE = 4  # WHEAT max_yield_day
WHEAT_LAST_PLANT_DAY = 25  # 4 growth days; day 25 is the last that can mature
WHEAT_SEED_COST = 10

# Herd: 2 GOOSE + 2 COW + 2 SHEEP -- a small, modest, symmetric default (the
# source states "livestock first" without giving v5's own concrete numbers).
ANIMAL_TARGETS: dict[str, int] = {"GOOSE": 2, "COW": 2, "SHEEP": 2}
ANIMAL_COST: dict[str, int] = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
# Reserve banked before any WHEAT surplus is sold, once the herd is up and
# running: roughly two days' worth of the herd's flat 6/day FEED
# consumption -- enough to ride out a short gap, without holding back so
# much that selling (and therefore the farm's own income) never resumes.
FEED_RESERVE = 12
# Reserve required before the very first PLACE of a newly bought animal: the
# filler crop's own harvest cadence arrives in periodic bursts (self-clearing
# WHEAT replants and matures on roughly the same cycle across the whole
# zone) rather than a smooth daily trickle, so an empty-herd farm needs a
# much bigger bank before introducing any animal, to bridge the trough
# before the next burst without a single FEED miss.
PLACEMENT_RESERVE = 40


def _compute_zones(
    center: Position = SHED_TILE,
) -> tuple[tuple[Position, ...], tuple[Position, ...], tuple[Position, ...]]:
    """(coop_zone, pasture_zone, wheat_zone): the nearest ``COOP_ZONE_SIZE`` tiles to
    ``center`` claim COOP, the next ``PASTURE_ZONE_SIZE`` claim PASTURE, the next
    ``WHEAT_ZONE_SIZE`` claim WHEAT. Deterministic: sorted by Manhattan distance,
    then (y, x) -- the same sort every sibling fixture uses."""
    cx, cy = center
    candidates = [(x, y) for y in range(5) for x in range(5) if (x, y) != center]
    candidates.sort(key=lambda p: (abs(p[0] - cx) + abs(p[1] - cy), p[1], p[0]))
    coop = tuple(candidates[:COOP_ZONE_SIZE])
    pasture = tuple(candidates[COOP_ZONE_SIZE : COOP_ZONE_SIZE + PASTURE_ZONE_SIZE])
    wheat_start = COOP_ZONE_SIZE + PASTURE_ZONE_SIZE
    wheat = tuple(candidates[wheat_start : wheat_start + WHEAT_ZONE_SIZE])
    return coop, pasture, wheat


COOP_TILES, PASTURE_TILES, WHEAT_TILES = _compute_zones()
COOP_SET = frozenset(COOP_TILES)
PASTURE_SET = frozenset(PASTURE_TILES)
STRUCTURE_TILES = COOP_TILES + PASTURE_TILES
ALL_ZONE_TILES = COOP_TILES + PASTURE_TILES + WHEAT_TILES


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


def _zone_need(pos: Position, tile: Any, day: int) -> str | None:
    """What action (if any) a unit standing on zone tile ``pos`` should take.

    Returns one of "DIG", "BUILD_COOP", "BUILD_PASTURE", "PLANT", "WATER",
    "HARVEST", or None. COOP/PASTURE tiles need one-time BUILD_*; once built
    (tile is a dict, animal or not) there is nothing further for this
    function to say -- animal care is handled separately by
    ``_animal_care_need``.
    """
    if _is_weed(tile):
        return "DIG"
    if pos in COOP_SET:
        return "BUILD_COOP" if tile is None else None
    if pos in PASTURE_SET:
        return "BUILD_PASTURE" if tile is None else None
    # WHEAT filler zone.
    if tile is None:
        return "PLANT" if day <= WHEAT_LAST_PLANT_DAY else None
    if _is_plant(tile):
        if not tile.get("watered_today", False):
            return "WATER"
        if tile.get("yield_units", 0) > 0 and (day - tile.get("planted_day", day)) >= WHEAT_HARVEST_AGE:
            return "HARVEST"
    return None


def _animal_care_need(tile: dict[str, Any]) -> str | None:
    """What a unit standing on a placed-animal tile should do: "CARE" first
    (free, no precondition), then "FEED" (needs WHEAT in inventory, checked
    by the caller), or None once both are done for the day."""
    if not tile.get("cared_today", False):
        return "CARE"
    if not tile.get("fed_today", False):
        return "FEED"
    return None


def _nearest_unclaimed(
    pos: Position, needy: list[Position], claimed: set[Position], order_tiles: tuple[Position, ...]
) -> Position | None:
    candidates = [t for t in needy if t not in claimed]
    if not candidates:
        return None
    x, y = pos
    return min(candidates, key=lambda t: (abs(t[0] - x) + abs(t[1] - y), order_tiles.index(t)))


def _most_urgent_unclaimed(
    pos: Position,
    needy: list[Position],
    claimed: set[Position],
    urgency: dict[Position, int],
    order_tiles: tuple[Position, ...],
) -> Position | None:
    """Like ``_nearest_unclaimed``, but ranks by ``urgency`` (higher first)
    before distance. COOP sits closer to the shed than PASTURE by
    construction, so pure nearest-first feed routing starves COW/SHEEP in
    favor of GOOSE every time wheat is scarce; ranking by each animal's own
    ``consecutive_unfed`` count instead makes sure whichever animal is
    closest to escaping gets fed first, regardless of zone distance."""
    candidates = [t for t in needy if t not in claimed]
    if not candidates:
        return None
    x, y = pos
    return min(
        candidates,
        key=lambda t: (
            -urgency.get(t, 0),
            abs(t[0] - x) + abs(t[1] - y),
            order_tiles.index(t),
        ),
    )


def make_agent() -> Callable[[Any], dict[str, Any]]:
    """Return a fresh, stateless public-baseline-approx agent callable."""

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

        def tile_at(x: int, y: int) -> Any:
            if 0 <= x < board_w and 0 <= y < board_h:
                return tiles[y][x]
            return "LOCKED"

        unit_positions: list[Position] = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        inventories = private["inventories"]

        zone_needs: dict[Position, str] = {}
        for pos in ALL_ZONE_TILES:
            need = _zone_need(pos, tile_at(*pos), day)
            if need is not None:
                zone_needs[pos] = need

        care_needs: dict[Position, str] = {}
        for pos in STRUCTURE_TILES:
            t = tile_at(*pos)
            if isinstance(t, dict) and "animal" in t:
                need = _animal_care_need(t)
                if need is not None:
                    care_needs[pos] = need

        coop_empties = [
            pos
            for pos in COOP_TILES
            if isinstance(tile_at(*pos), dict)
            and tile_at(*pos).get("kind") == "COOP"
            and "animal" not in tile_at(*pos)
        ]
        pasture_empties = [
            pos
            for pos in PASTURE_TILES
            if isinstance(tile_at(*pos), dict)
            and tile_at(*pos).get("kind") == "PASTURE"
            and "animal" not in tile_at(*pos)
        ]

        totals: dict[str, int] = {}
        any_animal_placed = False
        for animal in ("GOOSE", "COW", "SHEEP"):
            placed = sum(
                1
                for pos in STRUCTURE_TILES
                if isinstance(tile_at(*pos), dict) and tile_at(*pos).get("animal") == animal
            )
            if placed > 0:
                any_animal_placed = True
            carried = sum(inv.get(animal, 0) for inv in inventories if isinstance(inv, dict))
            totals[animal] = placed + carried + shed.get(animal, 0)

        feed_candidates = [pos for pos, need in care_needs.items() if need == "FEED"]
        care_only_candidates = [pos for pos, need in care_needs.items() if need == "CARE"]
        zone_candidates = list(zone_needs.keys())
        feed_needed_count = len(feed_candidates)
        feed_urgency = {pos: tile_at(*pos).get("consecutive_unfed", 0) for pos in feed_candidates}

        # Wheat takes 4 growth days to first harvest (planted day 0 -> earliest
        # harvest day 4) and the self-clearing filler crop's own harvest cadence
        # then arrives in periodic bursts rather than a smooth daily trickle, so
        # an animal placed the instant a single unit of WHEAT exists would still
        # starve (2 consecutive unfed days) in the trough before the next burst.
        # Keep newly bought animals parked in the shed -- never picked up, never
        # placed -- until the wheat pipeline has banked a real buffer
        # (``PLACEMENT_RESERVE``), so PLACE always happens with enough feed
        # already in reach to bridge a gap between bursts. Once the herd has
        # started going down (``any_animal_placed``), the gate stays open for
        # the rest of the burst even if a later FEED draws the shed back
        # under the threshold mid-placement -- otherwise the last one or two
        # animals of the batch can get stranded in the shed indefinitely,
        # waiting for a bar that ongoing consumption keeps them from ever
        # re-crossing.
        wheat_available = shed.get("WHEAT", 0) + sum(
            inv.get("WHEAT", 0) for inv in inventories if isinstance(inv, dict)
        )
        place_gate_open = any_animal_placed or wheat_available >= PLACEMENT_RESERVE

        claimed: set[Position] = set()
        remaining_wheat_seeds = seeds.get("WHEAT", 0)
        unit_actions: list[list[str]] = []
        # Reserve navigation priority for shed WHEAT fetches whenever any
        # animal still needs feed today (see the on-tile PICKUP branch
        # below), instead of leaving it to fall out of the zone/care work
        # fallback -- with a large WHEAT zone's worth of standing demand,
        # that fallback otherwise never goes empty and starves the herd of
        # its own feed supply. Capped at the number of animals still needing
        # feed (never more units than there is work for).
        shed_fetch_budget = feed_needed_count

        for idx, pos in enumerate(unit_positions):
            x, y = pos
            tile = tile_at(x, y)
            if tile == "LOCKED":
                unit_actions.append(_step_toward(x, y, *SHED_TILE))
                continue

            inv_raw = inventories[idx] if idx < len(inventories) else {}
            inv = inv_raw if isinstance(inv_raw, dict) else {}

            zneed = zone_needs.get(pos)
            if zneed == "PLANT":
                if remaining_wheat_seeds > 0:
                    remaining_wheat_seeds -= 1
                    unit_actions.append(["PLANT", "WHEAT"])
                    claimed.add(pos)
                    continue
                # No seeds left for this unit this turn -- fall through.
            elif zneed is not None:
                unit_actions.append([zneed])
                claimed.add(pos)
                continue

            cneed = care_needs.get(pos)
            if cneed == "CARE":
                unit_actions.append(["CARE"])
                claimed.add(pos)
                continue
            if cneed == "FEED" and inv.get("WHEAT", 0) > 0:
                unit_actions.append(["FEED"])
                claimed.add(pos)
                continue

            if (
                place_gate_open
                and isinstance(tile, dict)
                and tile.get("kind") in ("COOP", "PASTURE")
                and "animal" not in tile
            ):
                kind = tile["kind"]
                if kind == "COOP" and inv.get("GOOSE", 0) > 0:
                    unit_actions.append(["PLACE", "GOOSE"])
                    claimed.add(pos)
                    continue
                if kind == "PASTURE" and inv.get("COW", 0) > 0:
                    unit_actions.append(["PLACE", "COW"])
                    claimed.add(pos)
                    continue
                if kind == "PASTURE" and inv.get("SHEEP", 0) > 0:
                    unit_actions.append(["PLACE", "SHEEP"])
                    claimed.add(pos)
                    continue

            if pos in SHED_ACCESS_SET:
                picked = False
                if place_gate_open:
                    for animal in ("GOOSE", "COW", "SHEEP"):
                        if shed.get(animal, 0) > 0 and totals[animal] <= ANIMAL_TARGETS[animal]:
                            unit_actions.append(["PICKUP", animal, 1])
                            picked = True
                            break
                if (
                    not picked
                    and feed_needed_count > 0
                    and shed.get("WHEAT", 0) > 0
                    and inv.get("WHEAT", 0) == 0
                ):
                    qty = min(shed.get("WHEAT", 0), feed_needed_count)
                    unit_actions.append(["PICKUP", "WHEAT", qty])
                    picked = True
                if picked:
                    continue

            carried_wheat = inv.get("WHEAT", 0)
            target: Position | None = None
            # Carried WHEAT is routed to a feed target immediately, and
            # straight back to the shed the instant no feed target is
            # reachable -- never left to accumulate in a wandering unit's own
            # inventory, which would starve every OTHER unit's PICKUP-based
            # feed pipeline of shed stock while the herd waits.
            if carried_wheat > 0:
                target = _most_urgent_unclaimed(pos, feed_candidates, claimed, feed_urgency, ALL_ZONE_TILES)
                if target is None:
                    target = SHED_TILE
            if target is None:
                for animal in ("GOOSE", "COW", "SHEEP"):
                    if inv.get(animal, 0) > 0:
                        pool = coop_empties if animal == "GOOSE" else pasture_empties
                        target = _nearest_unclaimed(pos, pool, claimed, ALL_ZONE_TILES)
                        if target is None:
                            fallback = COOP_TILES if animal == "GOOSE" else PASTURE_TILES
                            target = _nearest_unclaimed(pos, list(fallback), claimed, ALL_ZONE_TILES)
                        break
            if (
                target is None
                and shed_fetch_budget > 0
                and shed.get("WHEAT", 0) > 0
                and inv.get("WHEAT", 0) == 0
            ):
                target = _nearest_unclaimed(pos, list(SHED_ACCESS_TILES), claimed, SHED_ACCESS_TILES)
                if target is not None:
                    shed_fetch_budget -= 1
            if target is None:
                target = _nearest_unclaimed(
                    pos, zone_candidates + care_only_candidates, claimed, ALL_ZONE_TILES
                )
            if target is None:
                wants_animal = any(
                    shed.get(a, 0) > 0 and totals[a] <= ANIMAL_TARGETS[a] for a in ("GOOSE", "COW", "SHEEP")
                )
                if wants_animal:
                    target = _nearest_unclaimed(pos, list(SHED_ACCESS_TILES), claimed, SHED_ACCESS_TILES)

            if target is None:
                unit_actions.append(["PASS"])
                continue
            claimed.add(target)
            unit_actions.append(_step_toward(x, y, *target))

        farmer_action = unit_actions[0]
        hands_actions = unit_actions[1:]

        market: list[list[Any]] = []
        wheat_shed = shed.get("WHEAT", 0)
        surplus = wheat_shed - FEED_RESERVE
        if surplus > 0:
            market.append(["SELL", "WHEAT", surplus])

        if step % TURNS_PER_DAY == 0:
            for _ in range(HANDS_PER_DAY):
                market.append(["HIRE"])

            if day <= WHEAT_LAST_PLANT_DAY:
                capacity_needed = sum(
                    1 for pos in WHEAT_TILES if tile_at(*pos) is None or _is_weed(tile_at(*pos))
                )
                needed_wheat_seed = max(0, capacity_needed - seeds.get("WHEAT", 0))
                if needed_wheat_seed > 0:
                    affordable = int(farm["money"] // WHEAT_SEED_COST)
                    to_buy = min(needed_wheat_seed, affordable)
                    if to_buy > 0:
                        market.append(["BUY_SEED", "WHEAT", to_buy])

            for animal in ("GOOSE", "COW", "SHEEP"):
                need = ANIMAL_TARGETS[animal] - totals[animal]
                if need > 0:
                    cost = ANIMAL_COST[animal]
                    affordable = int(farm["money"] // cost)
                    to_buy = min(need, affordable)
                    if to_buy > 0:
                        market.append(["BUY_ANIMAL", animal, to_buy])

        return {"farmer": farmer_action, "hands": hands_actions, "market": market}

    return agent
