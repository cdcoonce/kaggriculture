"""CRN (common random numbers) seed-block primitive for racing rungs."""

import random

_RUNG_STRIDE = 1_000_003


def _combine(base_seed: int, rung: int, index: int) -> int:
    return (base_seed * _RUNG_STRIDE + rung) * _RUNG_STRIDE + index


def seed_block(rung: int, count: int, base_seed: int = 0) -> list[tuple[int, int]]:
    """Return `count` deterministic (seat_a_seed, seat_b_seed) pairs for `rung`.

    Same (rung, count, base_seed) always returns the same list (determinism
    -- CRN requires every trial at a rung to replay the identical games).
    Different `rung` values return pairwise-disjoint seed pairs, so racing
    rungs 25 -> 100 -> 400 (#7) never silently re-examine a smaller rung's
    games under a new label.
    """
    pairs = []
    for index in range(count):
        key = _combine(base_seed, rung, index)
        rng = random.Random(key)
        seat_a_seed = rng.getrandbits(63)
        seat_b_seed = rng.getrandbits(63)
        pairs.append((seat_a_seed, seat_b_seed))
    return pairs
