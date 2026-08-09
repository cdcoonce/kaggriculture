"""public-baseline-approx: an approximation of the public Kaggle notebook
"Barnyard Economist v5" by Roman Rozen (``docs/recon/public-meta.md``,
item 1), the 10th and final gate-zoo member under the "~10 members" cap
(``harness.zoo.__init__``).

Concretely sourced from the notebook's own stated structural fixes:
livestock-first spending of the opening $3,000 bankroll (never buys land),
a self-clearing 4-day WHEAT filler crop so the pen is never blocked, and
roles as a pure function of unlocked quadrants (trivially satisfied here,
since this fixture never buys land and only NW is ever unlocked).

Everything else -- herd composition (2 GOOSE + 2 COW + 2 SHEEP), zone
sizes, hand count -- is a default chosen by this spec, not stated by the
notebook; see the issue body for the full accounting. Fertilizer, melon,
and any animal-product (EGG/MILK/WOOL) harvest-and-sell pipeline are out of
scope: this fixture's animals exist only for the day-0 livestock burst and
the ongoing FEED/CARE loop the source emphasizes.

BUY_ANIMAL orders fire from day 0 (money goes into livestock first, per the
source), landing bought animals in the shed immediately. Moving them out of
the shed onto their COOP/PASTURE tile is delayed until MIN_PLACEMENT_DAY,
because FEED draws WHEAT from a unit's own inventory and the WHEAT filler
zone cannot produce a harvest before day 4 -- placing earlier would starve
every animal before the first harvest ever lands. See MIN_PLACEMENT_DAY's
own docstring for the exact mechanics.

Stateless and deterministic: every decision is derived fresh from ``obs``
each call, so a factory-returned closure carries no cross-episode state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Position = tuple[int, int]

SHED_TILE: Position = (4, 4)
TURNS_PER_DAY = 24
HANDS_PER_DAY = 3
CARRY_THRESHOLD = 6  # walk-to-shed-and-DROP once a unit is carrying this much WHEAT
HARVEST_AGE = 4  # wheat max_yield_day; harvesting at this age captures full yield
LAST_PLANT_DAY = 25  # wheat needs 4 growth days; day 25 is the last that can mature
SEED_COST = 10
HERD_FEED_PER_DAY = 6  # 1 FEED per animal per day, herd fixed at 6
# The 8-tile WHEAT zone harvests in waves (tiles replanted together tend to
# mature together, ~HARVEST_AGE days apart) rather than a steady daily
# trickle, so the shed reserve has to bridge a whole wave-to-wave gap, not
# just one day -- a 1-day floor (== HERD_FEED_PER_DAY) leaves FEED stranded
# with 0 WHEAT on every day between waves. Reserve a full harvest cycle's
# worth of feed before selling any surplus.
RESERVE_WHEAT = HERD_FEED_PER_DAY * HARVEST_AGE * 2

# A wheat tile planted day 0 is not HARVEST-eligible until day 4 (planted_day
# + HARVEST_AGE); FEED consumes WHEAT from a unit's own inventory, and a
# placed-but-unfed animal escapes after 2 consecutive unfed days. Fetching
# animals out of the shed onto their tiles is gated behind this day so no
# animal is ever placed before the WHEAT supply exists to feed it -- animals
# bought before this day simply wait, uncounted against FEED, in the shed
# (shed inventory carries no fed/consecutive-unfed state of its own).
MIN_PLACEMENT_DAY = 4

HERD: tuple[tuple[str, int], ...] = (("GOOSE", 2), ("COW", 2), ("SHEEP", 2))
ANIMAL_STRUCTURE: dict[str, str] = {"GOOSE": "COOP", "COW": "PASTURE", "SHEEP": "PASTURE"}
ANIMAL_COST: dict[str, int] = {"GOOSE": 300, "COW": 400, "SHEEP": 500}


def _compute_target_tiles(n: int = 24, center: Position = SHED_TILE) -> tuple[Position, ...]:
    """The ``n`` NW-quadrant tiles nearest ``center``, excluding it.

    Deterministic: sorted by Manhattan distance, then (y, x) for stable
    tie-breaking. Keeping the shed corner itself out of the set leaves it
    clear for DROP/PICKUP.
    """
    cx, cy = center
    candidates = [(x, y) for y in range(5) for x in range(5) if (x, y) != center]
    candidates.sort(key=lambda p: (abs(p[0] - cx) + abs(p[1] - cy), p[1], p[0]))
    return tuple(candidates[:n])


_ALL_TILES = _compute_target_tiles()
COOP_TILES: tuple[Position, ...] = _ALL_TILES[0:2]
PASTURE_TILES: tuple[Position, ...] = _ALL_TILES[2:6]
WHEAT_TILES: tuple[Position, ...] = _ALL_TILES[6:22]
COOP_SET = frozenset(COOP_TILES)
PASTURE_SET = frozenset(PASTURE_TILES)
WHEAT_SET = frozenset(WHEAT_TILES)
BUILD_TILES: tuple[Position, ...] = COOP_TILES + PASTURE_TILES
ANIMAL_ZONE_TILES: tuple[Position, ...] = COOP_TILES + PASTURE_TILES


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


def _wheat_need(tile: Any, day: int) -> str | None:
    """What action (if any) a unit standing on a WHEAT-zone ``tile`` should take.

    Returns one of "DIG", "PLANT", "WATER", "HARVEST", or None.
    """
    if _is_weed(tile):
        return "DIG"
    if tile is None:
        return "PLANT" if day <= LAST_PLANT_DAY else None
    if _is_plant(tile):
        if not tile.get("watered_today", False):
            return "WATER"
        if tile.get("yield_units", 0) > 0 and (day - tile.get("planted_day", day)) >= HARVEST_AGE:
            return "HARVEST"
    return None


def _nearest_unclaimed(
    pos: Position, candidates: list[Position], claimed: set[Position]
) -> Position | None:
    options = [t for t in candidates if t not in claimed]
    if not options:
        return None
    x, y = pos
    return min(options, key=lambda t: (abs(t[0] - x) + abs(t[1] - y), t[1], t[0]))


def _animal_accounted(
    tile_at: Callable[[int, int], Any],
    shed: dict[str, int],
    inventories: list[Any],
    animal: str,
) -> int:
    """Total ``animal`` this farm owns right now: placed + in shed + carried."""
    tiles_count = sum(
        1
        for p in ANIMAL_ZONE_TILES
        if isinstance(tile_at(*p), dict) and tile_at(*p).get("animal") == animal
    )
    shed_count = shed.get(animal, 0)
    carried_count = sum(inv.get(animal, 0) for inv in inventories if isinstance(inv, dict))
    return tiles_count + shed_count + carried_count


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

        coop_build = [p for p in COOP_TILES if tile_at(*p) is None]
        pasture_build = [p for p in PASTURE_TILES if tile_at(*p) is None]
        build_needed = coop_build + pasture_build

        coop_open = [
            p
            for p in COOP_TILES
            if isinstance(tile_at(*p), dict)
            and tile_at(*p).get("kind") == "COOP"
            and "animal" not in tile_at(*p)
        ]
        pasture_open = [
            p
            for p in PASTURE_TILES
            if isinstance(tile_at(*p), dict)
            and tile_at(*p).get("kind") == "PASTURE"
            and "animal" not in tile_at(*p)
        ]

        animal_tiles = [
            p for p in ANIMAL_ZONE_TILES if isinstance(tile_at(*p), dict) and "animal" in tile_at(*p)
        ]
        feed_needed = [p for p in animal_tiles if not tile_at(*p).get("fed_today")]
        care_needed = [p for p in animal_tiles if not tile_at(*p).get("cared_today")]

        claimed_build: set[Position] = set()
        claimed_place: set[Position] = set()
        claimed_feed: set[Position] = set()
        claimed_care: set[Position] = set()
        claimed_wheat: set[Position] = set()
        fetched_animal_this_turn = {"GOOSE": 0, "COW": 0, "SHEEP": 0}
        fetched_wheat_this_turn = 0

        remaining_seeds = seeds.get("WHEAT", 0)

        # Fixed daily roles, assigned by unit position rather than tracked
        # across calls (this agent is stateless): once building is done,
        # idx 0 (farmer) becomes a dedicated WHEAT-zone worker and idx 1
        # (first hand) becomes a dedicated feed courier (shed WHEAT ->
        # hungry animal). Splitting these off by identity, rather than by
        # "whoever happens to be carrying WHEAT this turn", is what makes
        # WHEAT banking possible at all: without a role split, any unit that
        # harvests WHEAT immediately reroutes to feed the moment an animal is
        # hungry (true on almost every day with a 6-animal herd), so the shed
        # reserve never accumulates and a single zero-harvest day empties it
        # -- see RESERVE_WHEAT's docstring for the reserve-sizing math this
        # is protecting. idx >= 2 keep the original build/fetch/wheat-zone/
        # care chain, since the herd's fixed 6-tile care load and the zone's
        # own maintenance need more than one spare worker once both
        # dedicated roles are carved out.
        dedicated_roles = not build_needed

        unit_actions: list[list[str]] = []
        for idx, pos in enumerate(unit_positions):
            x, y = pos
            tile = tile_at(x, y)
            if tile == "LOCKED":
                unit_actions.append(_step_toward(x, y, *SHED_TILE))
                continue

            inv = inventories[idx] if idx < len(inventories) else {}
            inv = inv if isinstance(inv, dict) else {}
            is_wheat_farmer = idx == 0 and dedicated_roles
            is_feed_courier = idx == 1 and dedicated_roles

            # Priority 1: carrying an animal -> deliver it to its structure.
            animal_carried = next((a for a in ("GOOSE", "COW", "SHEEP") if inv.get(a, 0) > 0), None)
            if animal_carried is not None:
                open_slots = coop_open if ANIMAL_STRUCTURE[animal_carried] == "COOP" else pasture_open
                target = _nearest_unclaimed(pos, open_slots, claimed_place)
                if target is not None:
                    claimed_place.add(target)
                    if target == pos:
                        unit_actions.append(["PLACE", animal_carried])
                    else:
                        unit_actions.append(_step_toward(x, y, *target))
                    continue

            if is_feed_courier:
                # Priority 2 (feed courier only): carrying shed-fetched WHEAT
                # -> deliver it to the nearest hungry animal.
                if inv.get("WHEAT", 0) > 0:
                    target = _nearest_unclaimed(pos, feed_needed, claimed_feed)
                    if target is not None:
                        claimed_feed.add(target)
                        if target == pos:
                            unit_actions.append(["FEED"])
                        else:
                            unit_actions.append(_step_toward(x, y, *target))
                        continue

                # Priority 2b (feed courier only): not carrying -> fetch from
                # the shed reserve for any still-unclaimed hungry animal.
                remaining_feed_targets = [p for p in feed_needed if p not in claimed_feed]
                if remaining_feed_targets:
                    available_wheat = shed.get("WHEAT", 0) - fetched_wheat_this_turn
                    if available_wheat > 0:
                        if pos == SHED_TILE:
                            n = min(len(remaining_feed_targets), available_wheat)
                            fetched_wheat_this_turn += n
                            unit_actions.append(["PICKUP", "WHEAT", n])
                        else:
                            unit_actions.append(_step_toward(x, y, *SHED_TILE))
                        continue
                # Nothing to fetch or deliver right now -- fall through to
                # WHEAT-zone overflow work below, same as idx >= 2.

            if not is_wheat_farmer and not is_feed_courier:
                # Priority 3: build any still-empty COOP/PASTURE tile.
                target = _nearest_unclaimed(pos, build_needed, claimed_build)
                if target is not None:
                    claimed_build.add(target)
                    if target == pos:
                        op = "BUILD_COOP" if target in COOP_SET else "BUILD_PASTURE"
                        unit_actions.append([op])
                    else:
                        unit_actions.append(_step_toward(x, y, *target))
                    continue

                # Priority 4: fetch a bought animal waiting in the shed (gated
                # by MIN_PLACEMENT_DAY -- see its docstring for why).
                fetch_animal = None
                for animal in ("GOOSE", "COW", "SHEEP") if day >= MIN_PLACEMENT_DAY else ():
                    available = shed.get(animal, 0) - fetched_animal_this_turn[animal]
                    if available <= 0:
                        continue
                    open_slots = coop_open if ANIMAL_STRUCTURE[animal] == "COOP" else pasture_open
                    if any(p not in claimed_place for p in open_slots):
                        fetch_animal = animal
                        break
                if fetch_animal is not None:
                    if pos == SHED_TILE:
                        fetched_animal_this_turn[fetch_animal] += 1
                        unit_actions.append(["PICKUP", fetch_animal, 1])
                    else:
                        unit_actions.append(_step_toward(x, y, *SHED_TILE))
                    continue

            # Priority 6: work the WHEAT filler zone (dig/plant/water/harvest).
            # Ranked above CARE: CARE only affects a placed animal's pending
            # yield bonus, which this fixture never harvests or sells (EGG/
            # MILK/WOOL are out of scope), while WHEAT production is the only
            # thing standing between the herd and starvation -- see
            # RESERVE_WHEAT's docstring.
            if pos in WHEAT_SET and pos not in claimed_wheat:
                need = _wheat_need(tile, day)
                if need == "PLANT":
                    if remaining_seeds > 0:
                        remaining_seeds -= 1
                        claimed_wheat.add(pos)
                        unit_actions.append(["PLANT", "WHEAT"])
                        continue
                    # No seeds left for this unit this turn -- fall through.
                elif need is not None:
                    claimed_wheat.add(pos)
                    unit_actions.append([need])
                    continue

            needy_wheat = [
                p for p in WHEAT_TILES if p not in claimed_wheat and _wheat_need(tile_at(*p), day) is not None
            ]
            target = _nearest_unclaimed(pos, needy_wheat, claimed_wheat)
            if target is not None:
                claimed_wheat.add(target)
                unit_actions.append(_step_toward(x, y, *target))
                continue

            # Priority 7: care for a placed animal that hasn't been cared for today.
            target = _nearest_unclaimed(pos, care_needed, claimed_care)
            if target is not None:
                claimed_care.add(target)
                if target == pos:
                    unit_actions.append(["CARE"])
                else:
                    unit_actions.append(_step_toward(x, y, *target))
                continue

            # Priority 8: carrying a full load of WHEAT with nowhere urgent to
            # put it -> walk it back to the shed.
            if inv.get("WHEAT", 0) >= CARRY_THRESHOLD:
                if pos == SHED_TILE:
                    unit_actions.append(["DROP"])
                else:
                    unit_actions.append(_step_toward(x, y, *SHED_TILE))
                continue

            import os
            if os.environ.get("PBA_DEBUG"):
                with open(os.environ["PBA_DEBUG"], "a") as f:
                    f.write(
                        f"PASS-fallback step={step} idx={idx} pos={pos} is_wheat_farmer={is_wheat_farmer} "
                        f"is_feed_courier={is_feed_courier} build_needed={build_needed} "
                        f"needy_wheat_len={len(needy_wheat)} claimed_wheat={claimed_wheat}\n"
                    )
            unit_actions.append(["PASS"])

        farmer_action = unit_actions[0]
        hands_actions = unit_actions[1:]

        market: list[list[Any]] = []

        # Livestock first: self-terminating once each animal count reaches its
        # target, since deficit becomes <= 0 and no further orders are queued.
        for animal, target_count in HERD:
            accounted = _animal_accounted(tile_at, shed, inventories, animal)
            deficit = target_count - accounted
            if deficit > 0:
                affordable = int(farm["money"] // ANIMAL_COST[animal])
                to_buy = min(deficit, affordable)
                if to_buy > 0:
                    market.append(["BUY_ANIMAL", animal, to_buy])

        if step % TURNS_PER_DAY == 0:
            for _ in range(HANDS_PER_DAY):
                market.append(["HIRE"])
            if day <= LAST_PLANT_DAY:
                capacity_needed = sum(
                    1 for p in WHEAT_TILES if tile_at(*p) is None or _is_weed(tile_at(*p))
                )
                needed = max(0, capacity_needed - seeds.get("WHEAT", 0))
                if needed > 0:
                    affordable = int(farm["money"] // SEED_COST)
                    to_buy = min(needed, affordable)
                    if to_buy > 0:
                        market.append(["BUY_SEED", "WHEAT", to_buy])

        shed_wheat = shed.get("WHEAT", 0)
        if shed_wheat > RESERVE_WHEAT:
            market.append(["SELL", "WHEAT", shed_wheat - RESERVE_WHEAT])

        return {"farmer": farmer_action, "hands": hands_actions, "market": market}

    return agent
