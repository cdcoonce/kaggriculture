"""Crash-only smoke gate for CI (issue #29).

Runs the unshelled champion candidate against six paired-seed slices of the
gate zoo's scripted opponents and fails iff any game raises, times out, or
``GateResult.any_candidate_crash`` is true. This is deliberately NOT a
statistical promotion gate — no win-rate or Wilson-CI assertion here, since
Actions' shared runners can trip the agent's soft time budget for reasons
unrelated to code correctness. The full promotion bar lives in the Mac
nightly orchestrator (#4/#12).

Opponent roster and split (100 paired seeds / 200 games total): the six
scripted members named in issue #29, 17/17/17/17/16/16. A seventh scripted
member (``public-baseline-approx``) landed in ``harness.zoo.SCRIPTED`` after
this split was fixed (issue #40, same day) and is intentionally excluded
pending a follow-up issue to fold it into the split.
"""

from __future__ import annotations

import sys

from harness.gate import run_gate

CANDIDATE = "champion-unshelled"

OPPONENTS: list[tuple[str, int]] = [
    ("wheat-spam", 17),
    ("melon-dumper", 17),
    ("melon-rusher", 17),
    ("index-front-runner", 17),
    ("land-rush-hoarder", 16),
    ("fert-market-crasher", 16),
]


def main() -> int:
    any_crash = False
    seed_base = 0
    for name, n_seeds in OPPONENTS:
        result = run_gate(
            candidate=CANDIDATE,
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
