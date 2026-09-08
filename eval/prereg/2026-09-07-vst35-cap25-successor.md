# Pre-registration: VST35 + valve soft cap 25 successor confirmation

Date: 2026-09-07 America/Phoenix
Candidate: `champion` at `ae698184d42e991fbea6cdd5b2163a949134f6a9`, CONFIG ONLY.
Incumbent: `frozen:m3d_vst35_93e2913`, materialized from shipped source
`93e2913bd59e59bb2c08269b93823726d1872de7`.
Status: **REGISTERED — no band-842000 data observed when this file was committed.**

## Why this successor

`valve_soft_threshold=35` is now the shipped default. The earlier registered
untested-knob screen measured `valve_soft_cap=25` only against the HML20
incumbent whose soft threshold was still 55. That arm recorded 127-73
(`rate=0.635`, Wilson lower 0.5663) and correctly missed that screen's fixed
0.65 selection bar. It remains **NOT SELECTED** under that registration.

The interaction `valve_soft_threshold=35` x `valve_soft_cap=25` is unmeasured:
the earlier threshold makes the soft tier fire more often, so the marginal
effect of its cap can differ. This registration tests that interaction against
the agent that actually ships. It does not revisit `max_owned_quadrants=3`,
W30, or any prior NOT PROMOTED ruling.

## Candidate-versus-shipped-default selection evidence

Exploratory selection ran before this prospective registration on fresh band
841000, n=100 seeds / 200 games per arm, both seats, using the committed
`harness.promotion_gate` instrument. These rows select whether to spend a
confirmation band; they cannot promote or change a source default.

| arm | record | rate | Wilson lower | crashes | ledger |
| --- | ---: | ---: | ---: | --- | --- |
| CTRL `{}` | 100-100-0 | 0.500 | 0.4314 | none | `eval/gates/2026-09-08T00-01-31Z-champion-vs-frozen_m3d_vst35_93e2913-promotion.json` |
| `{"valve_soft_cap":25}` | 122-78-0 | **0.610** | **0.5409** | none | `eval/gates/2026-09-08T00-03-12Z-champion-vs-frozen_m3d_vst35_93e2913-promotion.json` |

The pursuit rule was fixed before band 841000 ran: CTRL in [0.40, 0.60], no
candidate crashes, candidate rate >= 0.60, and candidate Wilson lower > 0.50.
The run is valid and the candidate clears that rule. No other value was tried.

## Registered confirmation design

- Candidate: `champion --agent-config '{"valve_soft_cap":25}'`.
- Opponent: `frozen:m3d_vst35_93e2913` from exact shipped source `93e2913`.
- Band: **842000**, disjoint from selection band 841000 and every cited prior.
- Size: **n=250 seeds / 500 games**, both seats.
- Instrument: `uv run python -u -m harness.promotion_gate`.
- Candidate source/config stays fixed while the run executes.
- Money remains diagnostic only; the decision uses head-to-head results.

## Decision rule fixed before band 842000

**INVALID** if the candidate crashes, the opponent identity is not the exact
frozen package above, fewer than 500 games complete, both seats are not played,
or the seed band/config differs from this document. Invalid data is diagnosed;
it is not reinterpreted or silently replaced with a neighboring band.

**CONFIRMED** only if all hold:

1. `rate >= 0.65`;
2. Wilson `ci_lower > 0.55`;
3. `any_candidate_crash == false`.

Otherwise the successor is **NOT CONFIRMED** and closes without an extension,
threshold change, alternate cap, or pooled reuse of band 841000. This is the
same full-confirmation strength bar used by the preceding untested-knob screen;
the 0.610 exploratory result did not weaken it.

## Consequence

A CONFIRMED result authorizes a source-default PR for `valve_soft_cap=25`, with
its own tests, bundle rebuild, and bit-identical gate reproduction. It does not
authorize merging, uploading a Kaggle submission, evicting a tracked
submission, or claiming live-ladder Elo. A NOT CONFIRMED result changes
nothing shipped and is recorded permanently.
