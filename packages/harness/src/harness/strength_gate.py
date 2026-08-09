"""Actions CI crash-only smoke check — NOT a strength verdict (issue #29).

Runs the raw, unshelled champion policy (``resolve_agent``'s
``"champion-unshelled"`` spec) against all six of ``harness.zoo.SCRIPTED``'s
gate-zoo opponents, 100 paired seeds (200 games) total. Fails iff any
opponent run reports a candidate crash. This deliberately does NOT assert on
win rate or the Wilson-CI lower bound -- that statistical bar is the Mac
nightly full promotion gate's job (#4); Actions' shared, variable-speed
runners can change how often the agent's soft time budget trips, which would
make a win-rate assertion flaky for reasons unrelated to code correctness.
"""

from __future__ import annotations

import sys

from harness.gate import run_gate
from harness.zoo import SCRIPTED

# 100 paired seeds total, split across SCRIPTED's six members in
# dict-iteration order: 17 each for the first four, 16 each for the last two
# (100 does not divide evenly by 6). Re-derive from gate_zoo()'s live
# SCRIPTED dict before changing this split -- it has already changed once
# since this job was specced (2026-08-09 quarantine resolution).
_STANDARD_SEEDS = 17
_REDUCED_SEEDS = 16
_REDUCED_OPPONENT_COUNT = 2


def main() -> int:
    names = list(SCRIPTED)
    reduced_from = len(names) - _REDUCED_OPPONENT_COUNT

    any_crash = False
    seed_base = 0
    for index, name in enumerate(names):
        n_seeds = _REDUCED_SEEDS if index >= reduced_from else _STANDARD_SEEDS
        result = run_gate(
            candidate="champion-unshelled",
            opponent=f"zoo:{name}",
            n_seeds=n_seeds,
            seed_base=seed_base,
            workers=1,
        )
        seed_base += n_seeds
        any_crash = any_crash or result.any_candidate_crash
        print(f"{name}: paired_seeds={n_seeds} any_candidate_crash={result.any_candidate_crash}")

    print("FAIL" if any_crash else "PASS")
    return 1 if any_crash else 0


if __name__ == "__main__":
    sys.exit(main())
