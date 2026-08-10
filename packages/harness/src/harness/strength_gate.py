"""Crash-only smoke gate for CI (issue #29).

Runs the unshelled champion candidate against every ``harness.zoo.SCRIPTED``
member and fails iff any game raises, times out, or
``GateResult.any_candidate_crash`` is true. This is deliberately NOT a
statistical promotion gate — no win-rate or Wilson-CI assertion here, since
Actions' shared runners can trip the agent's soft time budget for reasons
unrelated to code correctness. The full promotion bar lives in the Mac
nightly orchestrator (#4/#12).

The roster and per-opponent seed count are derived from ``SCRIPTED`` at
runtime rather than hardcoded: the zoo has outrun a fixed list three times
already (most recently issue #40's ``public-baseline-approx``), and a
derived split means every future zoo fixture is smoke-tested for free.
``TOTAL_PAIRED_SEEDS`` paired seeds are split evenly across the roster in
dict-iteration order, with the remainder handed one extra each to the first
members in that order.
"""

from __future__ import annotations

import sys

from harness.gate import run_gate
from harness.zoo import SCRIPTED

CANDIDATE = "champion-unshelled"
TOTAL_PAIRED_SEEDS = 50


def _opponent_seed_counts(names: list[str], total: int = TOTAL_PAIRED_SEEDS) -> list[int]:
    """Split ``total`` paired seeds across ``names`` as evenly as possible.

    Each name gets ``total // len(names)``; the ``total % len(names)``
    remainder is handed one extra each to the first names in order.
    """
    base, remainder = divmod(total, len(names))
    return [base + 1 if i < remainder else base for i in range(len(names))]


def main() -> int:
    names = list(SCRIPTED)
    counts = _opponent_seed_counts(names)

    any_crash = False
    seed_base = 0
    for name, n_seeds in zip(names, counts, strict=True):
        result = run_gate(
            candidate=CANDIDATE,
            opponent=f"zoo:{name}",
            n_seeds=n_seeds,
            seed_base=seed_base,
            workers=1,
        )
        seed_base += n_seeds
        any_crash = any_crash or result.any_candidate_crash
        print(
            f"{name}: paired_seeds={n_seeds} any_candidate_crash={result.any_candidate_crash}",
            flush=True,
        )

    print("FAIL" if any_crash else "PASS", flush=True)
    return 1 if any_crash else 0


if __name__ == "__main__":
    sys.exit(main())
