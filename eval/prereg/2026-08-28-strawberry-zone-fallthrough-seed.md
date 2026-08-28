# Pre-registration — let the wheat seed line see the ground the dispatcher already plants

Written **before** any gate seed was burned, at commit `0d366b9`
(`feat/strawberry-mix-displacement`, [PR #83](https://github.com/cdcoonce/kaggriculture/pull/83)).
Fixes `n`, the seed bands and the decision rule in advance.

Successor to `eval/prereg/2026-08-19-strawberry-mix-displacement.md`, which was
**killed on its own criteria the same day it landed**. That kill is the reason
this file exists: it removed the cash blocker and found a second one of a
different kind behind it. This registers the second one as its own
intervention rather than widening the predecessor, which is what the
predecessor's kill criteria existed to prevent.

## What is being tested

Whether funding the wheat seed line against the ground the **dispatcher is
already willing to plant wheat on** — rather than against a tile set that
excludes the strawberry zone entirely — converts reserved-but-idle zone ground
into standing wheat, and whether that converts into banked money.

## The defect: the planner and the dispatcher disagree about wheat's tiles

`dispatch.py:497-513` already falls an unclaimable strawberry-zone tile
through to a WHEAT plant. Its own comment calls this "the reservation trap,
fixed rather than inherited," and it is correct: once the daily strawberry cap
is spent or the planting window has shut, an empty zone tile goes to wheat
instead of being held for a crop that can no longer profitably go in it.

`policy.py:305` computes the planner's wheat target as
`_plantable_targets(view, wheat_tiles)`, where

```python
wheat_tiles = [t for t in tiles
               if t not in melon_set and t not in pasture_set and t not in strawberry_set]
```

**The zone is subtracted outright.** So the dispatcher is willing to plant
wheat on ground the planner will not buy seed for, and the fall-through cannot
fire because the shed is empty. Neither module is wrong on its own; they
disagree, and the disagreement is invisible in both.

## The measurement, taken before writing any code

`plan_day`'s own kwargs recorded per day, seed 661200 vs `zoo:tape-thunder-719`,
`strawberry_tile_target = 31`, at `0d366b9` (i.e. **with** the predecessor's
cash fix already in):

| day | wheat `plantable_target_tiles` | empty zone tiles | wheat seeds | money |
| --- | --- | --- | --- | --- |
| d00 | **0** | 15 | 0 | 3,000 |
| d07 | **0** | 21 | 0 | 26 |
| d12 | **0** | 17 | 0 | 106 |
| d13 | 23 | 15 | 23 | 3,598 |

**Wheat's plantable target is exactly zero for thirteen days while 21 tiles
sit empty.** It does not lose a budget contest — it never asks, because its
target is 0. Day 13 is when SW unlocks and ground appears outside the zone.

Note the money column: $0–165 through d12. The farm is broke because nothing
is producing, which is the loop this closes. At `strawberry_tile_target = 20`
the zone is small enough to leave wheat some ground and WHEAT reaches the
board on day 1, which is the contrast that identifies the zone as the cause.

## The code change under test

One change, in `policy.py`. The wheat seed target counts, in addition to
`wheat_tiles`, the empty strawberry-zone tiles the dispatcher would fall
through to wheat on this turn — the zone tiles beyond the strawberry daily
plant cap, and the whole empty zone once the strawberry planting window has
shut.

**Reservation semantics are NOT changed.** The zone keeps its fixed reference
frame and its size; `strawberry_tiles` is untouched. Nothing is planted that
the dispatcher would not already have planted. Only the seed line's arithmetic
moves, so the 17-day-plant invariant `STRAWBERRY_REFERENCE_QUADRANTS` protects
is not in play.

**Explicitly out of scope**, so a miss cannot be rescued by reaching for it:
capping the zone as a share of currently-unlocked ground, ramping the zone by
day, changing `strawberry_plant_daily_cap`, and anything in `dispatch.py`.

## Predictions, registered in advance

Written before the change is made, so a miss is visible rather than
reinterpretable. All on seeds 661200–661203 vs `zoo:tape-thunder-719`, days
10–28, seat 0 — the predecessor's recon band and window, so the numbers are
directly comparable.

- At target 31, wheat `plantable_target_tiles` is **> 0 on day 0**. This is
  the mechanism itself; if it does not move, the change did not do what it
  says and nothing else is worth reading.
- At target 31, WHEAT reaches the board by **day 2** (currently day 14).
- At target 31, days 0–13 wheat seed pool rises **above 23**.
- Mean standing, days 10–28, rises **above 34.4** at the best arm.
- At target 31, mean bare ground falls **below 21.3**.
- **Control:** at target 12 the zone already leaves wheat ground and WHEAT
  already reaches the board on day 1, so this change should be close to
  neutral there — mean standing within **±1.0** of its current 32.7. A large
  move at 12 means the mechanism story is wrong and the arms are not measuring
  what this file claims.
- `opponent_mean_delta` stays within **±3,000**.

### The 34.4 bar is inherited deliberately, not re-derived

34.4 is the predecessor's comparator: the **blocked** arm — strawberry on,
cash blocker present — not the dormant baseline of 31.4. The predecessor
missed it at 34.1. It is carried over unchanged. Lowering a bar after a miss
is the exact move a pre-registration exists to prevent, and 34.4 remains the
honest question: does the fixed build beat the broken one.

## Gate protocol

- **Frozen incumbent required.** Freeze from `0d366b9` and verify it
  **behaviourally** — run the frozen copy through
  `tools/recon-scripts/occupancy.py` and confirm it reproduces that build's
  signature (mean standing 34.1 / bare 23.1 at target 31, 31.4 / 29.2 at
  target 0). `assert_disjoint` is not behaviour, and `#73` is open precisely
  because it only inspects `{pkg}.policy`.
- **Intermediate first.** The occupancy predictions above are checked before
  any gate seed is burned. If they miss, stop — do not gate.
- **Screen** n=20 from band **661400**. **Confirm** n=64+ from a disjoint band
  starting **661600**. Both inherited unburned from the predecessor.
- **Arms.** `strawberry_tile_target` 12 / 20 / 31. 12 is the control above,
  not a candidate.
- **Decision rule.** Intersection–union: `ci_lower` > $1,000 on thunder and
  > $0 on barnyard, metac95 and mirror, no vetoes.
- Read `opponent_mean_delta`, `n_regressed` and `skew_delta` **before** the
  bound, every time.
- **Predict power from the arm being run**, not a neighbour — dispersion is
  arm-specific, and a prior prereg carried `sd_delta ~4,086` while observing
  15,098 and 19,417.

## Kill criteria

Stop and record a negative rather than widening the search if:

- Wheat's `plantable_target_tiles` at target 31 is still 0 on day 0.
- WHEAT still fails to reach the board by day 2 at target 31.
- Mean standing does not clear 34.4 at any arm.
- Target 12 moves more than ±1.0 in mean standing — the arms are not
  measuring the claimed mechanism and the whole reading is suspect.
- `opponent_mean_delta` exceeds ±3,000.

## Two-sided supply (DIAGNOSTIC, not part of the decision rule)

Carried forward verbatim from the predecessor, which registered it and never
reached it. `docs/recon/economy.md:63` says strawberry crashes to its floor
within ~62 units, while a prior session measured its price *rising* 120→250
because town shops drain it and neither player supplies it. Those readings are
not reconciled, and a mix built on a crop that crashes under two-sided supply
fails exactly when both players adopt it.

`zoo:kernel-sokolovsky-2883` is itself a heavy strawberry supplier — 300 units
across d16–d29 — which makes this testable for the first time.

- **Run** the winning arm and the frozen incumbent against
  `zoo:kernel-sokolovsky-2883`, paired seeds, band **661800**, n=32 seeds.
- **Diagnostic only. It does NOT gate promotion.** The champion loses that
  matchup 0–200; requiring a pass would be an unreachable bar, and moving it
  after seeing the result is the sin this file exists to prevent.
- **Registered reading:** the arm's paired money delta against the frozen
  incumbent *in the kernel matchup*, against the same delta in the thunder
  matchup. If the gain does not survive against a co-supplier, the result is
  reported as contested-fragile and the ladder claim is withdrawn regardless
  of whether the promotion gate passed.

## What this does not establish

Occupancy is an intermediate, not the objective, and the predecessor is the
standing proof that the two can move in opposite directions: fixing its cash
blocker raised wheat's seed pool from 0 to 23 and moved mean standing *down*,
34.4 → 34.1. Clearing the intermediate here buys the right to run the money
gate. It does not predict the gate's result, and the gate is what decides.
