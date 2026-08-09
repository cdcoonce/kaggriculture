"""chaos-legal-random: seeded uniformly-random-but-legal actions (zoo #21,
EXTENDED registry only -- see harness.zoo's module docstring for the
gate-zoo-vs-extended-zoo split). This fixture's job is crash-surface
sweeping, not gating: it joins ``EXTENDED``/``extended_zoo()``, not
``gate_zoo()``.

"Legal" here means vocabulary-legal, not situationally-valid: every op name
is a real engine op and every arg is well-typed and drawn from the
engine's real value space (crop/item/animal names), per
``_apply_unit_action`` and ``_parse_order`` in
``kaggle_environments/envs/kaggriculture/kaggriculture.py``. Contextually
invalid actions (e.g. WATERing an unplanted tile) are vocabulary-legal and
deliberately left un-filtered -- the engine silently no-ops them, which is
exactly the crash-surface property this fixture exists to exercise.

RNG seeding: ``obs`` carries no episode seed, and the step-0 observation is
byte-identical across every configured seed (nothing in the engine's
``_initialize`` touches an RNG). A one-time step-0 hash would therefore
produce the same seed integer regardless of the actual configured seed,
making this fixture's whole action sequence seed-invariant -- defeating the
point of a chaos sweep. Instead, this fixture re-derives a fresh
``random.Random`` from the FULL current observation on every single call:
genuine cross-seed variation appears as soon as the engine's own per-seed
randomness (weed spawning, town shop unlocks -- both first invoked at the
first end-of-day boundary) makes two seeds' observation streams diverge.
Before that point (day 0), this fixture's actions are necessarily identical
across all seeds -- a known, documented limitation of this design, not a
claim of full seed-sensitivity from turn 0.

Stateless like wheat_spam.py: every call's RNG and actions are a pure
function of that call's own ``obs``, so ``make_agent()`` returns a plain
closure with no mutable state.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable
from typing import Any

CROPS: tuple[str, ...] = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS: tuple[str, ...] = ("GOOSE", "COW", "SHEEP")
PRODUCTS: tuple[str, ...] = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
)
PICKUP_ITEMS: tuple[str, ...] = PRODUCTS + ANIMALS
BUY_PRODUCT_ITEMS: tuple[str, ...] = ("WHEAT", "FERTILIZER")

# 17 unit-op shapes (_apply_unit_action, kaggriculture.py:298-507).
UNIT_OPS: tuple[str, ...] = (
    "PASS",
    "NORTH",
    "SOUTH",
    "EAST",
    "WEST",
    "PLANT",
    "WATER",
    "HARVEST",
    "DIG",
    "DROP",
    "PICKUP",
    "FERTILIZE",
    "BUILD_COOP",
    "BUILD_PASTURE",
    "PLACE",
    "FEED",
    "COLLECT_FERTILIZER",
    "CARE",
)

# 6 market-op shapes (_process_market / _parse_order, kaggriculture.py:608-626).
MARKET_OPS: tuple[str, ...] = ("HIRE", "BUY_LAND", "BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL")

MIN_QTY = 1
MAX_QTY = 5  # this fixture's own bound -- keeps sampled orders realistic-shaped
MAX_MARKET_ORDERS = 3  # this fixture's own bound -- well under the engine's 10-order cap


def _sample_unit_action(rng: random.Random) -> list[Any]:
    op = rng.choice(UNIT_OPS)
    if op == "PLANT":
        return [op, rng.choice(CROPS)]
    if op == "PICKUP":
        return [op, rng.choice(PICKUP_ITEMS), rng.randint(MIN_QTY, MAX_QTY)]
    if op == "PLACE":
        return [op, rng.choice(ANIMALS), rng.randint(MIN_QTY, MAX_QTY)]
    return [op]


def _sample_market_order(rng: random.Random) -> list[Any]:
    op = rng.choice(MARKET_OPS)
    if op in ("HIRE", "BUY_LAND"):
        return [op]
    if op == "BUY_SEED":
        return [op, rng.choice(CROPS), rng.randint(MIN_QTY, MAX_QTY)]
    if op == "BUY_PRODUCT":
        return [op, rng.choice(BUY_PRODUCT_ITEMS), rng.randint(MIN_QTY, MAX_QTY)]
    if op == "BUY_ANIMAL":
        return [op, rng.choice(ANIMALS), rng.randint(MIN_QTY, MAX_QTY)]
    return [op, rng.choice(PRODUCTS), rng.randint(MIN_QTY, MAX_QTY)]  # SELL


def _rng_for(obs: Any) -> random.Random:
    """A fresh RNG derived from the full current observation -- see module
    docstring for why this is re-derived every call rather than once at
    step 0."""
    structure = {
        "step": obs["step"],
        "day": obs["day"],
        "hour": obs["hour"],
        "player": obs["player"],
        "farms": obs["farms"],
        "market": obs["market"],
        "town": obs["town"],
        "private": obs["private"],
    }
    serialized = json.dumps(structure, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode()).digest()
    return random.Random(int.from_bytes(digest, "big"))


def make_agent() -> Callable[[Any], dict[str, Any]]:
    """Return a fresh, stateless chaos-legal-random agent callable."""

    def agent(obs: Any) -> dict[str, Any]:
        rng = _rng_for(obs)
        player = obs["player"]
        farm = obs["farms"][player]
        num_hands = len(farm["hands"])

        farmer_action = _sample_unit_action(rng)
        hands_actions = [_sample_unit_action(rng) for _ in range(num_hands)]

        num_orders = rng.randint(0, MAX_MARKET_ORDERS)
        market = [_sample_market_order(rng) for _ in range(num_orders)]

        return {"farmer": farmer_action, "hands": hands_actions, "market": market}

    return agent
