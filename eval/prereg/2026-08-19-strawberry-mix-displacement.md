# Pre-registration — displace wheat with strawberry, once the seed line stops starving it

Written **before** any gate seed was burned, at commit `acd7244`.
Fixes `n`, the seed band and the decision rule in advance.

## What is being tested

Whether shifting a large share of the farm from WHEAT (`ongoing: False`, tile
destroyed on harvest, ~1.0 unit-actions per tile-day held) to STRAWBERRY
(`ongoing: True`, tile held ~17 days on one PLANT) raises banked money by
lifting standing-crop occupancy on a labor-saturated crew.

**This is NOT the config-only A/B it looks like.** `strawberry_tile_target`
already exists and has already been screened dead at 6/8/11/16/24/32. The
measurements below show why those screens could not have tested the
intervention, and what has to change in code first. The gate specified here
runs against a **frozen incumbent**, not a config baseline.

## Why this is on the table at all

Standing-crop census, 4 seeds, band 661200, days 10–28, both seats from the
same episodes (`eval/recon/2026-08-18-occupancy-*.json`, PR #78):

| | mean standing | mean bare ground | crop mix (tile-days) |
| --- | --- | --- | --- |
| champion | 42.0 | **39.4** | WHEAT 87% · MELON 13% |
| `tape-thunder-719` | 58.4 | **1.3** | STRAWBERRY 45% · WHEAT 42% · MELON 13% |

We leave ~39 tiles of plantable ground idle every day. Thunder leaves 1.3, and
does it with 45% of its tile-days on a crop that never needs replanting. Seed
supply, the plant quota, crew size and post-harvest tile state are each ruled
out by measurement in `docs/recon/occupancy.md`.

## The blocker, measured before writing any code

Ran the shipped agent at `strawberry_tile_target = 31` (the largest zone the
fixed `STRAWBERRY_REFERENCE_QUADRANTS = ("NW","NE")` frame can hold — capacity
is exactly 31 tiles from index 18), seed 661300, vs `tape-thunder-719`:

| | baseline (target 0) | target 31 |
| --- | --- | --- |
| mean standing, days 10–28 | 42.0 | **42.5** |
| strawberry zone peak | — | **13 of 31** |
| first day WHEAT appears on the board | day 1 | **day 14** |
| WHEAT seed pool, days 0–13 | funded | **0** |

**No occupancy gain, and the first half of the game is strictly worse.** The
zone reserves 31 tiles and fills 13; the rest sits bare while the wheat rush
cannot start.

The cause is the seed budget order, not the zone. `plan.py:171-177` funds
strawberry seed **ahead of** wheat seed (`plan.py:184-190`), and
`strawberry_seed_target = min(2 * strawberry_plant_daily_cap, empty_strawberry_tiles)`
is `min(12, 31) = 12` per day at $100 each — **$1,200/day of demand placed
ahead of wheat's $10 seeds**. Early cash is fully consumed and the $10
workhorse gets nothing for fourteen days.

Note the reservation trap itself is **not** the problem: `dispatch.py:497-513`
already falls an unclaimable strawberry-zone tile through to a WHEAT plant
once the daily cap is spent. That fall-through fires correctly. The wheat
tasks are emitted and then skipped at `dispatch.py:702/720/734` because
`seed_budgets["WHEAT"]` is zero.

## The code change under test

1. **Fund the wheat seed line before strawberry's.** Wheat is the early cash
   engine and the cheapest ground-holder per dollar; strawberry is a
   mid-game asset. Move the strawberry seed block after the wheat block in
   `plan.py`.
2. **Size the strawberry seed target to cash, not to zone.** Cap the daily
   strawberry seed spend so a large zone cannot monopolise the budget.

Both are `plan.py` changes. Neither touches `dispatch.py`. The zone size stays
a `PolicyConfig` knob so the gate can sweep it.

## Predictions, registered in advance

Written before the gate runs, so a miss is visible rather than reinterpretable:

- WHEAT appears on the board by **day 2**, as at baseline, at every arm.
- Strawberry zone fill rises **above 13/31**. If it does not, cash is not the
  binding constraint and the whole thesis is wrong — stop, do not sweep.
- Mean standing, days 10–28, rises **above 45** at the best arm (baseline
  42.0). Occupancy is the mechanism; if it does not move, money moving is
  luck.
- `opponent_mean_delta` stays within **±3,000**. The wheat screen was voided
  as a price artifact by a `+18,265` reading; strawberry withdrawal could do
  the same in reverse.

## Gate protocol

Standard, unchanged from `docs/`:

- **Frozen incumbent required** — this is a code change. Freeze from
  `acd7244` via `harness.frozen.freeze_incumbent`, and verify it
  **behaviourally**, not with `assert_disjoint` alone: run the frozen copy
  through `tools/recon-scripts/occupancy.py` and confirm it reproduces the
  baseline signature (mean standing 42.0, mean bare 39.4, no wheat delay).
  Module identity is not behaviour.
- **Screen** n=20. **Confirm** n=64+ on a **disjoint** band.
- **Bands.** 661200–661203 and 661300 are burned by the recon above. Screen
  from **661400**; confirm on a disjoint band starting **661600**.
- **Arms.** Zone sizes 12 / 20 / 31. Not 6/8/11/16/24/32 — those are the
  already-dead satellite sizes and re-running them tests nothing new.
- **Decision rule.** Intersection–union: `ci_lower` > $1,000 on thunder and
  > $0 on barnyard, metac95 and mirror, no vetoes.
- Read `opponent_mean_delta`, `n_regressed` and `skew_delta` **before** the
  bound, every time.
- **Predict power from the arm being run**, not a neighbour. Dispersion is
  arm-specific; a prior prereg carried `sd_delta ~4,086` across arms and
  observed 15,098 and 19,417.

## Kill criteria

Stop and record a negative rather than widening the search if:

- Zone fill stays at or below 13/31 after the seed-order change — cash was
  not the constraint, and the remaining candidate is labor, which the
  day-boundary result already suggests does not convert.
- Mean standing does not clear 45 at any arm.
- `opponent_mean_delta` exceeds ±3,000 — the result is a price artifact and
  the money reading is not ours to claim.

## What this does not establish

Occupancy is an intermediate, not the objective. Thunder is a **replay tape**:
its board shows what a strong build looks like, not that we can execute one.
And our own economy model says strawberry crashes to its floor within ~62
units (`docs/recon/economy.md:63`), while a prior session measured its price
*rising* 120→250 across an episode because town shops drain it and neither
player supplies it. **Those two readings are not reconciled.** If the gate
passes, that contradiction has to be resolved before the result is trusted at
ladder scale, because a mix built on a crop that crashes under two-sided
supply would fail exactly when both players adopt it.

---

# CORRECTION — appended 2026-08-19, after implementing the registered change

**The diagnosis above is wrong, and the registered predictions failed.** Left
in place rather than edited, per this file's own rule.

## What was predicted, and what happened

The seed-ordering change was implemented (`plan.py`, wheat block moved ahead
of strawberry's), TDD'd, gate-green, and **proven a bit-exact no-op at the
shipped default** — the occupancy census reproduces
`eval/recon/2026-08-18-occupancy-661200/661201.json` exactly, both seats.

At `strawberry_tile_target = 31`, seed 661300, the run is **byte-identical to
the pre-change run**: mean standing 42.5, zone peak 13 of 31, wheat still
absent until day 14, wheat seed pool still 0 across days 0–13.

| registered prediction | result |
| --- | --- |
| WHEAT on the board by day 2 | **FAILED** — still day 14 |
| zone fill above 13/31 | **FAILED** — still 13 |
| mean standing above 45 | **FAILED at 31** (42.5); met at target 12, but by zone size, not by this change |

## The real blocker: zone geometry, not budget order

`policy.py:281-285` builds `wheat_tiles` as the live tile universe minus the
melon, pasture and strawberry sets. Early game only NW+NE are unlocked, which
is **49 tiles**, and:

```
 8 melon + 10 pasture + 31 strawberry = 49
```

**Wheat gets zero tiles.** `plantable_target_tiles` is therefore 0, so
`seed_target = min(0, 2*quota) = 0` and the wheat line buys nothing *at any
position in the budget order*. Wheat only returns when SW unlocks and adds 25
tiles — which lands around day 13, and is exactly the observed day-14 delay.

Measured wheat-zone size by strawberry target, NW+NE unlocked: **31 / 19 / 11
/ 0** at strawberry 0 / 12 / 20 / 31.

The `$1,200/day of strawberry seed demand` story in the body above is real
arithmetic about the seed line, but it is **not what produced the day-14
delay**. The seed line never got the chance to matter because the wheat zone
was empty. I inferred a budget cause from a budget-shaped symptom and did not
check the geometry first.

## Consequence for the registered gate

**Arm 31 is unrunnable by construction** and must be dropped — it is not a
mix, it is a wheat deletion for the first thirteen days. The arm list becomes
**12 / 20**, and any arm must be checked against the wheat-zone table above
before it is screened.

The seed-ordering change measures at **+1.0 standing at target 12 and +0.4 at
target 20, one seed** — noise, and not evidence for anything. It is not
promoted. Following the `perf/day-boundary-guard` precedent (#77), the
implementation stays on an unmerged branch with its tests rather than landing
on a rationale that has been falsified.

## What the geometry actually implies

Thunder runs ~33 strawberry **and** ~12 wheat **and** ~13 melon
simultaneously — 58 standing — which the fixed `("NW","NE")` strawberry frame
cannot express at all, because that frame holds only 31 tiles total after
melon and pasture take theirs. Reaching a thunder-shaped mix needs the
strawberry zone to extend past NW+NE, and `STRAWBERRY_REFERENCE_QUADRANTS` is
deliberately fixed **because a drifting zone orphans a live 17-day plant and
weeds it two days later** (`constants.py`, and the pasture bug that motivated
it).

So the next question is not a knob and not a seed order. It is whether a
strawberry zone can be **anchored to a growing frame without drifting** —
pinning tiles as they are claimed rather than recomputing a slice. That is a
real design problem and it is the actual blocker on this whole line.
