"""kernel-player: plays a decoded action plan ported from a published Kaggle
competitor solution ("Sokolovsky"), self-repairing against the live
observation rather than replaying blind (zoo issue -- kernel-player family).

Unlike tape-player (``harness.zoo.tape_player``), which replays a fixed,
observation-blind action tape, a kernel-player member reads the same
720-entry embedded-plan shape but layers three observation-reactive repair
passes on top of it every turn:

- ``_repair_blocked_route``: if a unit's plan action this turn is
  ``BUILD_PASTURE`` or ``PLANT`` and the tile it is standing on has become a
  WEED, override to ``DIG`` and record a recovery transaction; the next turn
  retries the original intended action, then for up to ``_RECOVERY_TAIL``
  further turns replays the previous step's planned action for that unit
  while the tile catches back up.
- ``_sync_hands``: reconciles the plan entry's ``hands`` array length
  against the live observation's actual hand count, exactly like
  ``harness.zoo.tape_player._align_hands``.
- ``_advance_premium_sales`` / ``_settle_lead`` (plus their helpers
  ``_next_sale_qty``, ``_town_pull``, ``_pickup_commitment``,
  ``_scheduled_sale``, ``_same_turn_drop``): pull tomorrow's premium-item
  (MELON/MILK/STRAWBERRY/WOOL) SELL order forward into today when shop-demand
  pull is zero and the shed already has the stock, then net the pulled-
  forward quantity back out of tomorrow's replayed SELL order so the same
  units are never sold twice.

Like a tape, the decoded plan JSON is third-party competition data and is
deliberately MACHINE-LOCAL -- never committed to this repo (see
``DEFAULT_KERNEL_DIR``). ``discover_kernels()`` scans that directory at call
time and is wired into ``harness.zoo.extended_zoo()`` only, never
``harness.zoo.gate_zoo()``: a checkout without any kernel files populated
must still produce the exact same gate roster as one that has them, so the
gate stays reproducible and machine-independent by construction, not by
convention -- the same contract ``tape_player``'s own docstring states.

Closure state, not module state: the original submission this is ported from
kept two mutable module-level globals (a lead-book and a recovery-book, each
keyed by seat 0/1) reset opportunistically whenever ``obs["step"]`` was 0 or
went backwards. The harness pools worker processes and reuses modules across
episodes, so module-level state keyed only by seat can leak between episodes
-- and even between two concurrently-live agents playing the SAME seat.
``make_kernel_agent()`` closes over a single lead-state dict and a single
recovery-state dict instead, the same pattern ``harness.zoo.melon_dumper``'s
hold/dump latch and ``harness.zoo.meta_clone``'s watering tracker use for
their own episode-scoped state: a factory call produces exactly one agent for
exactly one seat in exactly one episode, so no seat keying is needed inside
the closure at all. The step-regression reset is kept as a defensive belt but
should never fire in normal use.

Fallback observability: the ported ``agent()`` wraps its whole body in a
blanket ``except Exception`` that returns an all-PASS action, faithful to the
original submission's own safety net. Left silent, that net would also hide
the PORT's own bugs -- a broken kernel-player degrades to a paralyzed
opponent with no crash and no failing test, and every subsequent gate run
against it would report a plausible-looking but entirely fictitious win for
whatever candidate it faced. The returned agent therefore exposes
``agent.fallback_count`` (incremented on every fallback) and
``agent.last_error`` (the last exception's type and message, so a test
failure can say WHY) as plain attributes on the callable. Nothing is ever
printed or logged.
"""

from __future__ import annotations

import copy
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

#: Default kernel directory, overridable at call time via the
#: ``KAGGRICULTURE_KERNEL_DIR`` environment variable (see ``_kernel_dir``).
DEFAULT_KERNEL_DIR = Path.home() / ".kaggriculture" / "kernels"

_REQUIRED_KEYS = frozenset({"farmer", "hands", "market"})

_PREMIUM: tuple[str, ...] = ("MELON", "MILK", "STRAWBERRY", "WOOL")
_SHED_LIMIT = 100
_RECOVERY_TAIL = 8
_SHOP_MAP: dict[str, tuple[str, ...]] = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}


def _kernel_dir() -> Path:
    """Resolve the kernel directory from the environment.

    Resolved at CALL time, not import time, so tests can monkeypatch
    ``KAGGRICULTURE_KERNEL_DIR`` (module-level resolution would freeze the
    directory the first time this module gets imported in a process) --
    matches ``harness.zoo.tape_player._tape_dir``."""
    override = os.environ.get("KAGGRICULTURE_KERNEL_DIR")
    return Path(override) if override else DEFAULT_KERNEL_DIR


def kernel_path(stem: str) -> Path:
    """Absolute path of the plan file backing ``zoo:kernel-<stem>``.

    Resolved at CALL time via ``_kernel_dir()``, matching
    ``discover_kernels``."""
    return _kernel_dir() / f"{stem}.json"


def load_plan(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate a decoded kernel plan JSON file.

    A valid plan is a nonempty JSON list, every entry of which is an object
    carrying at least ``farmer``, ``hands``, and ``market`` keys -- the same
    shape ``harness.zoo.tape_player.load_tape`` validates, since both
    represent one entry per engine step. Raises ``ValueError`` (with the
    offending path/entry named) on any structural problem -- caller decides
    whether that's fatal (``load_plan`` used directly) or skip-worthy
    (``discover_kernels``)."""
    path = Path(path)
    with path.open() as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"plan {path}: expected a JSON list, got {type(data).__name__}")
    if not data:
        raise ValueError(f"plan {path}: plan is empty")

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"plan {path}: entry {i} is not an object")
        missing = _REQUIRED_KEYS - entry.keys()
        if missing:
            raise ValueError(f"plan {path}: entry {i} missing keys {sorted(missing)}")

    return data


def _read(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    if callable(getter):
        return getter(key, default)
    return getattr(value, key, default)


def _clone_action(action: Any) -> dict[str, Any]:
    action = copy.deepcopy(action or {})
    return {
        "farmer": list(action.get("farmer") or ["PASS"]),
        "hands": [list(order or ["PASS"]) for order in action.get("hands") or []],
        "market": [list(order) for order in action.get("market") or []],
    }


def _player_id(obs: Any) -> int:
    return 1 if int(_read(obs, "player", 0) or 0) == 1 else 0


def _farm_state(obs: Any, seat: int) -> Any:
    farms = list(_read(obs, "farms", []) or [])
    return farms[seat] if seat < len(farms) else {}


def _sync_hands(action: dict[str, Any], obs: Any) -> dict[str, Any]:
    action = _clone_action(action)
    expected = len(_read(_farm_state(obs, _player_id(obs)), "hands", []) or [])
    hands = list(action.get("hands") or [])
    if len(hands) < expected:
        hands.extend([["PASS"] for _ in range(expected - len(hands))])
    action["hands"] = [list(order or ["PASS"]) for order in hands[:expected]]
    return action


def _tile_here(farm: Any, position: Any) -> Any:
    try:
        x, y = (int(position[0]), int(position[1]))
        return (_read(farm, "tiles", []) or [])[y][x]
    except (IndexError, TypeError, ValueError):
        return "LOCKED"


def _plan_for_unit(plan: list[dict[str, Any]], step: int, actor: Any) -> list[Any]:
    trace = plan[min(max(int(step), 0), len(plan) - 1)] or {}
    if actor == "farmer":
        return list(trace.get("farmer") or ["PASS"])
    hands = trace.get("hands", []) or []
    return list(hands[actor] if actor < len(hands) else ["PASS"])


def _repair_blocked_route(
    plan: list[dict[str, Any]],
    obs: Any,
    action: dict[str, Any],
    step: int,
    recovery_state: dict[str, Any],
) -> dict[str, Any]:
    action = _sync_hands(action, obs)
    seat = _player_id(obs)
    if step == 0 or step < int(recovery_state.get("last_step", -1)):
        recovery_state.clear()
        recovery_state.update({"last_step": step, "active": {}})
    recovery_state["last_step"] = step
    farm = _farm_state(obs, seat)
    positions = [_read(farm, "farmer"), *list(_read(farm, "hands", []) or [])]
    unit_actions = [action.get("farmer", ["PASS"]), *list(action.get("hands") or [])]
    active = recovery_state.setdefault("active", {})
    for actor, transaction in list(active.items()):
        index = 0 if actor == "farmer" else int(actor) + 1
        if index >= len(unit_actions):
            active.pop(actor, None)
            continue
        age = step - int(transaction["start"])
        if age == 1:
            unit_actions[index] = list(transaction["intended"])
        elif 2 <= age <= 1 + _RECOVERY_TAIL:
            unit_actions[index] = _plan_for_unit(plan, step - 1, actor)
        else:
            active.pop(actor, None)
    for index, (position, intended) in enumerate(zip(positions, unit_actions, strict=False)):
        actor = "farmer" if index == 0 else index - 1
        if actor in active or not isinstance(intended, list) or not intended:
            continue
        if intended[0] not in ("BUILD_PASTURE", "PLANT"):
            continue
        tile = _tile_here(farm, position)
        if not isinstance(tile, dict) or tile.get("kind") != "WEED":
            continue
        active[actor] = {"start": step, "intended": list(intended)}
        unit_actions[index] = ["DIG"]
    action["farmer"] = unit_actions[0] if unit_actions else ["PASS"]
    action["hands"] = unit_actions[1:]
    return _sync_hands(action, obs)


def _lead_state(lead_state: dict[str, Any], step: int) -> dict[str, Any]:
    if step == 0 or step < int(lead_state.get("last_step", -1)):
        lead_state.clear()
        lead_state.update({"last_step": step, "due_step": -1, "due": {}})
    lead_state["last_step"] = step
    if 0 <= int(lead_state.get("due_step", -1)) < step:
        lead_state["due_step"], lead_state["due"] = (-1, {})
    return lead_state


def _town_pull(obs: Any, item: str, step: int) -> int:
    demand = 1 if item != "FERTILIZER" and step % 24 == 0 else 0
    if step % 4 != 0:
        return demand
    town = _read(obs, "town", {}) or {}
    for shop in list(_read(town, "unlocked_shops", []) or []):
        products = _SHOP_MAP.get(shop, ())
        if item in products:
            demand += 2 if len(products) == 1 else 1
    return demand


def _next_sale_qty(plan: list[dict[str, Any]], step: int, item: str) -> int:
    future = step + 1
    if not 0 <= future < len(plan):
        return 0
    return sum(
        max(0, int(order[2]))
        for order in plan[future].get("market") or []
        if len(order) >= 3 and order[0] == "SELL" and order[1] == item
    )


def _pickup_commitment(action: dict[str, Any], item: str) -> int:
    reserve = 0
    for order in [action.get("farmer", ["PASS"]), *list(action.get("hands") or [])]:
        if (
            isinstance(order, (list, tuple))
            and len(order) >= 2
            and order[0] == "PICKUP"
            and order[1] == item
        ):
            try:
                reserve += max(0, int(order[2])) if len(order) >= 3 else 1
            except (TypeError, ValueError):
                reserve += 1
    return reserve


def _scheduled_sale(action: dict[str, Any], item: str) -> int:
    return sum(
        max(0, int(order[2]))
        for order in action.get("market") or []
        if len(order) >= 3 and order[0] == "SELL" and order[1] == item
    )


def _settle_lead(action: dict[str, Any], state: dict[str, Any], step: int) -> dict[str, Any]:
    if int(state.get("due_step", -1)) != step:
        return action
    due = {
        str(item): max(0, int(quantity)) for item, quantity in dict(state.get("due", {})).items()
    }
    action = _clone_action(action)
    market = []
    for raw in action.get("market") or []:
        order = list(raw)
        if len(order) >= 3 and order[0] == "SELL" and order[1] in due and due[order[1]] > 0:
            requested = max(0, int(order[2]))
            reduction = min(requested, due[order[1]])
            requested -= reduction
            due[order[1]] -= reduction
            if requested <= 0:
                continue
            order[2] = requested
        market.append(order)
    action["market"] = market[:10]
    state["due_step"], state["due"] = (-1, {})
    return action


def _same_turn_drop(obs: Any, action: dict[str, Any], item: str) -> int:
    private = _read(obs, "private", {}) or {}
    shed = _read(private, "shed", {}) or {}
    inventories = list(_read(private, "inventories", []) or [])

    farm = _farm_state(obs, _player_id(obs))
    tiles = _read(farm, "tiles", []) or []
    size = len(tiles) or 10
    half = size // 2
    access = {
        (half - 1, half - 1),
        (half, half - 1),
        (half - 1, half),
        (half, half),
    }

    positions = [
        _read(farm, "farmer", [0, 0]),
        *list(_read(farm, "hands", []) or []),
    ]
    orders = [
        action.get("farmer", ["PASS"]),
        *list(action.get("hands") or []),
    ]

    room = max(
        0,
        _SHED_LIMIT - sum(max(0, int(value or 0)) for value in shed.values()),
    )
    credit = 0

    for index, (position, order) in enumerate(zip(positions, orders, strict=False)):
        if room <= 0:
            break
        if not isinstance(order, list) or not order or order[0] != "DROP":
            continue

        try:
            pos = (int(position[0]), int(position[1]))
        except (TypeError, ValueError, IndexError):
            continue

        if pos not in access:
            continue

        inventory = inventories[index] if index < len(inventories) else {}
        load = sum(max(0, int(value or 0)) for value in (inventory or {}).values())

        if load <= 0:
            continue

        # Partial DROP order depends on dict insertion order. Only use a
        # deposit when the complete inventory fits, otherwise stay
        # conservative -- same trade-off the original submission makes.
        if load > room:
            room = 0
            continue

        credit += max(0, int((inventory or {}).get(item, 0) or 0))
        room -= load

    return credit


def _advance_premium_sales(
    plan: list[dict[str, Any]],
    action: dict[str, Any],
    obs: Any,
    state: dict[str, Any],
    step: int,
) -> dict[str, Any]:
    if not _PREMIUM:
        return action
    private = _read(obs, "private", {}) or {}
    shed = _read(private, "shed", {}) or {}
    moved: dict[str, int] = {}
    action = _clone_action(action)
    for item in _PREMIUM:
        target = _next_sale_qty(plan, step, item)
        if target <= 0 or _town_pull(obs, item, step) > 0:
            continue
        stock = max(0, int(_read(shed, item, 0) or 0)) + _same_turn_drop(obs, action, item)
        reserve = _pickup_commitment(action, item) + _scheduled_sale(action, item)
        quantity = min(target, max(0, stock - reserve))
        if quantity <= 0:
            continue
        market = [list(order) for order in action.get("market") or []]
        existing = next(
            (
                order
                for order in market
                if len(order) >= 3 and order[0] == "SELL" and order[1] == item
            ),
            None,
        )
        if existing is not None:
            existing[2] = max(0, int(existing[2])) + quantity
        elif len(market) < 10:
            market.append(["SELL", item, quantity])
        else:
            continue
        action["market"] = market[:10]
        moved[item] = moved.get(item, 0) + quantity
    if moved:
        state["due_step"] = step + 1
        state["due"] = moved
    return action


def make_kernel_agent(plan: list[dict[str, Any]]) -> Callable[[Any], dict[str, Any]]:
    """Return an agent callable that plays ``plan``, patched every turn by
    the three observation-reactive repair layers described in the module
    docstring, with its own episode-scoped lead-state and recovery-state
    dicts closed over -- no seat keying needed, since one factory call is one
    agent for one seat for one episode (see the module docstring's "Closure
    state" section).

    The whole body runs under a blanket ``except Exception``, faithful to
    the original submission: any failure degrades to a safe all-PASS action.
    Unlike the original, that fallback is OBSERVABLE: every trip increments
    ``agent.fallback_count`` and records ``agent.last_error`` on the returned
    callable (see the module docstring's "Fallback observability" section).
    Nothing is ever printed."""
    lead_state: dict[str, Any] = {"last_step": -1, "due_step": -1, "due": {}}
    recovery_state: dict[str, Any] = {"last_step": -1, "active": {}}

    def agent(obs: Any) -> dict[str, Any]:
        try:
            step = min(max(0, int(_read(obs, "step", 0) or 0)), len(plan) - 1)
            action = _repair_blocked_route(
                plan, obs, _clone_action(plan[step]), step, recovery_state
            )
            state = _lead_state(lead_state, step)
            action = _settle_lead(action, state, step)
            action = _advance_premium_sales(plan, action, obs, state, step)
            return _sync_hands(action, obs)
        except Exception as exc:
            agent.fallback_count += 1
            agent.last_error = f"{type(exc).__name__}: {exc}"
            farm = _farm_state(obs, _player_id(obs))
            return {
                "farmer": ["PASS"],
                "hands": [["PASS"] for _ in _read(farm, "hands", []) or []],
                "market": [],
            }

    agent.fallback_count = 0
    agent.last_error = None
    return agent


def discover_kernels() -> dict[str, Callable[[], Callable[[Any], dict[str, Any]]]]:
    """Scan the kernel directory for top-level ``*.json`` files and return
    ``{"kernel-<stem>": factory}`` for each one that loads cleanly.

    Returns ``{}`` if the directory doesn't exist -- a machine with no
    kernels populated is a normal, fully-supported state, not an error.
    Never raises: a malformed plan file is skipped silently, with nothing
    written to stdout (a gate run parses stdout, so this must stay silent).
    Each returned factory is zero-arg and produces a fresh agent closure per
    call, matching every other zoo member's factory contract. A bare
    ``glob("*.json")`` only matches paths whose OWN name ends in ``.json``,
    so a sibling research-artifact directory (e.g. ``sokolovsky-2883/`` next
    to ``sokolovsky-2883.json``) is never descended into or mistaken for a
    plan file."""
    kernel_dir = _kernel_dir()
    if not kernel_dir.is_dir():
        return {}

    discovered: dict[str, Callable[[], Callable[[Any], dict[str, Any]]]] = {}
    for stem in sorted(path.stem for path in kernel_dir.glob("*.json")):
        try:
            plan = load_plan(kernel_path(stem))
        except (ValueError, OSError):
            continue

        def factory(plan: list[dict[str, Any]] = plan) -> Callable[[Any], dict[str, Any]]:
            return make_kernel_agent(plan)

        discovered[f"kernel-{stem}"] = factory

    return discovered
