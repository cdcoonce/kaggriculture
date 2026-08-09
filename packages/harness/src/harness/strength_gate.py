"""Crash-only smoke check for CI: candidate vs. every gate-zoo scripted member.

Actions CI-topology slice (#29, part of #12). This is a crash-only smoke
check, NOT a statistical promotion gate -- it never asserts on
``GateVerdict.passed``, win rate, or the Wilson-CI lower bound. That bar is
reserved for the Mac-run full promotion gate (#4); Actions' shared,
variable-speed runners can change how often the agent's soft time budget
trips, which would make a win-rate assertion flaky for reasons unrelated to
code correctness.

The candidate runs unshelled (``"champion-unshelled"``, see
``harness.episodes.resolve_agent``) so a policy crash is observable instead
of being coerced into a silent PASS by ``agent.shell.wrap``.

100 paired seeds (200 games) total, split across the six currently
registered ``harness.zoo.SCRIPTED`` members in dict-iteration order: 17
paired seeds each for the first four, 16 each for the remaining two (100
does not divide evenly by 6). Quarantine resolution 2026-08-09: a
250-paired-total run measured 12.5-17.5 min on a 2-vCPU Actions runner, over
the <=8-minute budget; 100 paired total lands ~5-7 min with margin.
"""

from __future__ import annotations

import sys

from harness.gate import run_gate
from harness.zoo import SCRIPTED

# First four SCRIPTED members get 17 paired seeds, remaining two get 16 --
# see module docstring. Re-derive this split from a fresh gate_zoo() read if
# SCRIPTED's roster ever changes; it has changed once already since #29 was
# drafted.
_PAIRED_SEED_COUNTS = (17, 17, 17, 17, 16, 16)


def main() -> int:
    names = list(SCRIPTED)
    if len(names) != len(_PAIRED_SEED_COUNTS):
        raise ValueError(
            f"harness.zoo.SCRIPTED has {len(names)} members but strength_gate's "
            f"seed split covers {len(_PAIRED_SEED_COUNTS)} -- re-derive the split"
        )

    any_crash = False
    seed_base = 0
    for name, n_seeds in zip(names, _PAIRED_SEED_COUNTS, strict=True):
        result = run_gate(
            candidate="champion-unshelled",
            opponent=f"zoo:{name}",
            n_seeds=n_seeds,
            seed_base=seed_base,
            workers=1,
        )
        seed_base += n_seeds
        print(f"{name}: paired_seeds={n_seeds} any_candidate_crash={result.any_candidate_crash}")
        if result.any_candidate_crash:
            any_crash = True

    print("FAIL" if any_crash else "PASS")
    return 1 if any_crash else 0


if __name__ == "__main__":
    sys.exit(main())
