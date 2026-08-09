# Issue #29 — two acceptance criteria are mutually unsatisfiable

Implementation is complete and the review's blocking item is fixed. This file
flags one contradiction in the issue that needs a human decision; I did not
guess my way past it silently.

## The contradiction

Issue #29 asks for both:

- "runs 250 total paired seeds split across `harness.zoo.gate_zoo()`'s scripted
  members" (= 500 games), **and**
- "completes within an 8-minute budget on a standard 2-vCPU Actions runner".

Those cannot both hold. The 8-minute figure is derived from
`docs/recon/ci-compute-budget.md` §4, but that table's Actions throughput range
(1.019–1.427 eps/s, §3) is an extrapolation from the §2.1 benchmark, which was
measured `make('kaggriculture').run(['starter','starter'])` — **not** the
champion-vs-zoo matchup this job actually runs.

## Measurement

Measured on this machine via `harness.gate.run_gate(..., workers=2)`, 80 games
per row, same code path the workflow uses:

| matchup                      | s/game | eps/s |
| ---------------------------- | ------ | ----- |
| `builtin:starter` vs `builtin:starter` | 0.515 | 1.94 |
| `champion` vs `zoo:wheat-spam`         | 1.068 | 0.94 |
| `champion` vs `zoo:melon-dumper`       | 1.141 | 0.88 |

The starter row reproduces the doc's own baseline (§3 claims 1.019 eps/s
single-core with clean 2.00x scaling at 2 workers → ~2.04 eps/s; measured 1.94),
so the benchmark setup agrees with the doc. Champion-vs-zoo then costs **2.14x**
per episode.

Rescaling §4's Actions range by 2.14x: **0.475–0.666 eps/s → 500 games =
12.5–17.5 min** on a 2-vCPU runner. The issue's own note that the rejected
alternative would cost "~9–13 min" is subject to the same starter-vs-starter
understatement.

## What I shipped

I kept the mandated 250 paired seeds and set `timeout-minutes` from the
measurement (20 on the gate step, 25 on the job) so that a red `strength-gate`
means "the candidate crashed", not "the runner was slow" — a timeout tuned to an
unattainable budget would fail for exactly the runner-speed reasons the issue
cites when it forbids a win-rate assertion.

## The decision you own

1. **Accept ~13–18 min** for this job (what is shipped now), or
2. **Resize to fit 8 min** — roughly 110 paired seeds / 220 games total at the
   conservative 0.475 eps/s end, which would need the AC's "250" changed, or
3. **Re-benchmark §2.1 against champion-vs-zoo** and re-derive §4, then re-sight
   both numbers.

Only option 2 requires a code change here (one constant: `TOTAL_PAIRED_SEEDS`).
