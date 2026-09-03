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

## AMENDMENT 1 — re-baselined at `9916ce5` (2026-08-28)

Written **before any gate seed was burned** under this amendment. The body
above was registered at `acd7244`. `b6ce655` ("stop buying the SE quadrant")
landed in between and changed how much ground the agent owns, so **every
absolute threshold in the body derives from a board that no longer exists**
and is void. They are restated here rather than reinterpreted later.

### Re-measurement at HEAD

Seeds 661200–661203 vs `zoo:tape-thunder-719`, seat 0, days 10–28 —
the same recon band and window the body used, re-run at `9916ce5`:

| | baseline (target 0) | target 31 (blocker probe) |
| --- | --- | --- |
| mean standing | **31.4** (body: 42.0) | **34.4** (body: 42.5) |
| mean bare ground | **29.2** (body: 39.4) | **21.3** |
| first day WHEAT appears | day 1 | **day 14** |
| WHEAT seed pool, days 0–13 | funded | **0** |
| strawberry zone peak | — | **15–17 of 31** (body: 13) |
| crop mix (tile-days) | WHEAT 83% · MELON 17% | WHEAT 50% · STRAWBERRY 32% · MELON 18% |

**The blocker is confirmed at HEAD and unchanged in kind.** `plan.py:204`
still funds the strawberry seed line ahead of wheat's at `plan.py:215`, and
`strawberry_seed_target` is still sized to the zone
(`min(2 * strawberry_plant_daily_cap, empty_strawberry_tiles)`), not to cash.
Wheat is starved for fourteen days exactly as recorded.

**One finding reverses.** The body recorded *no occupancy gain* from target 31
(42.0 → 42.5). On the smaller board the gain is real even with the blocker in
place: standing +9.6% and bare ground −27%. That makes the body's original
bar too easy, not too hard, so it is raised below.

### Restated predictions (these supersede the body's)

- WHEAT appears on the board by **day 2** at every arm. *(unchanged)*
- Strawberry zone fill rises **above 17/31** — above what the *unfixed* arm
  already reaches, not above the body's stale 13.
- Mean standing, days 10–28, rises **above 34.4** at the best arm. The
  comparator is the **blocker-probe arm**, not the dormant baseline: the fix
  has to beat the broken version of itself, or it has bought nothing.
- `opponent_mean_delta` stays within **±3,000**. *(unchanged)*

### Restated kill criteria (these supersede the body's)

- Zone fill stays at or below 17/31 after the seed-order change.
- Mean standing does not clear 34.4 at any arm.
- `opponent_mean_delta` exceeds ±3,000.

### Evidence admitted since the body was written

The body's stated weakness was that its only strong-build exemplar,
`tape-thunder-719`, is a replay tape — "its board shows what a strong build
looks like, not that we can execute one." A second exemplar now exists that
does not have that weakness. `zoo:kernel-sokolovsky-2883` is a ported public
competitor solution with observation-reactive repair, and it beats the
champion **0–200** (`ci_lower` 0.0000, ledger
`eval/gates/2026-08-25T15-22-30Z-…`) while banking a mean **$114,862**
against our **$64,041**.

Instrumented decomposition, 7 episodes on band 811000 (scratch probe, both
seats) — mean money gap, champion minus kernel:

```
d16 +9,497   d20 +1,503   d24 −19,682   d28 −33,543
late-game earn rate, d21–29:  champion +1,830/day   kernel +5,923/day  (3.2x)
```

**We are ahead through day 20 in all seven episodes and lose the last third
of every one.** The kernel's back half is standing-asset yield bought early:
37 strawberry seeds, all purchased days 3–10, sell **300 units** at 20–37/day
continuously from d16 to d29; 8 cows, all purchased by d8, sell 320 milk. Our
champion buys **zero** strawberry seed (`STRAWBERRY_TILE_TARGET = 0`,
dormant) and sells 563 wheat — a crop that destroys its tile on harvest and
consumes the replant labor that would otherwise run the back half.

This is independent corroboration of the body's thesis from a contested,
reactive opponent rather than a tape.

### New registered arm — two-sided supply (DIAGNOSTIC, not part of the decision rule)

The body flagged an unresolved contradiction: `docs/recon/economy.md:63` says
strawberry crashes to its floor within ~62 units, while a prior session
measured its price *rising* 120→250 because town shops drain it and neither
player supplies it. The kernel moves 300 units and still banks $114,862 —
but as the **only** supplier. A mix built on a crop that crashes under
two-sided supply would fail exactly when both players adopt it.

`zoo:kernel-sokolovsky-2883` makes that testable, because it is itself a
heavy strawberry supplier. Registered in advance:

- **Run** the winning arm and `frozen:m3b_straw_base_9916ce5` against
  `zoo:kernel-sokolovsky-2883`, paired seeds, band **661800**, n=32 seeds.
- **This is diagnostic and does NOT gate promotion.** The champion loses that
  matchup 0–200; requiring a pass would be an unreachable bar, and moving it
  after seeing the result is exactly the sin this file exists to prevent.
- **Registered reading:** the arm's paired money delta against the frozen
  incumbent *in the kernel matchup*, compared with the same delta in the
  thunder matchup. If the strawberry gain measured against thunder does not
  survive against a co-supplier, the result must be reported as
  contested-fragile and the ladder claim withdrawn — regardless of whether
  the promotion gate passed.

### Bands

Screen **661400**, confirm **661600** (both unchanged and disjoint from the
recon band). Kernel diagnostic band **661800**. Arms 12 / 20 / 31, unchanged.

---

## RESULT — killed on the registered intermediate (2026-08-28, `0d366b9`)

**Two kill criteria fired. No gate seed was burned. The bands registered
above (661400 screen, 661600 confirm, 661800 kernel diagnostic) are UNBURNED
and remain available to a successor.**

### The registered code change works

`0d366b9` lands both registered changes: wheat funded before strawberry, and
the strawberry seed line bounded by a share of uncommitted cash. Verified live
rather than assumed — days 0–13 WHEAT seed pool, seeds 661200–661203 vs
`zoo:tape-thunder-719`:

| arm | WHEAT seed pool, d0–13 |
| --- | --- |
| pre-fix, target 31 | **0** |
| fixed, target 31 | 23 |
| fixed, target 20 | 49–80 |
| fixed, target 12 | 111 |

Both guards are mutation-verified: re-injecting the zone-only sizing turns two
tests red (including the feed-cash test, which had **no teeth** as first
written and is recorded here because it passed before the fix); re-injecting
the old ordering turns the ordering test red.

### The registered thesis fails its own bar

| arm | mean standing (d10–28) | bare | zone peak | first WHEAT |
| --- | --- | --- | --- | --- |
| baseline (target 0) | 31.4 | 29.2 | — | day 1 |
| **pre-fix target 31 (the comparator)** | **34.4** | 21.3 | 15–17/31 | day 14 |
| fixed target 12 | 32.7 | 24.2 | 11/12 | day 1 |
| fixed target 20 | **34.1** | 22.4 | 9–16/20 | day 1 |
| fixed target 31 | 34.1 | 23.1 | 15–16/31 | day 14 |

- *"Mean standing rises above 34.4 at the best arm"* → best arm is **34.1**. **MISS.**
- *"Strawberry zone fill rises above 17/31"* → peak **16**. **MISS.**
- *"WHEAT appears by day 2 at every arm"* → holds at 12 and 20, **day 14 at 31**. **MISS.**

Both restated kill criteria fire. The result is recorded as a negative and the
promotion path stops here.

**AMENDMENT 1 is what makes this a clean kill.** Against the body's original
comparator — the dormant baseline at 31.4 — every fixed arm would have
"cleared" and this would have gone to a gate. Raising the bar to the
blocker-probe arm *before* measuring is the only reason the honest reading is
available: fixing the cash starvation makes standing crop go slightly **down**
(34.4 → 34.1), because the broken arm bought its standing by starving wheat
and leaving strawberry more ground to hold.

### What the kill actually found: a second blocker, of a different kind

The day-14 wheat delay survives the cash fix at target 31, so cash was never
the only thing holding wheat back. Day-by-day census at target 31 (seed
661200):

```
d07  standing 18  bare 21  {STRAWBERRY: 10, MELON: 8}  seeds {}
d12  standing 22  bare 16  {STRAWBERRY: 14, MELON: 8}  seeds {STRAWBERRY: 2}
d13  standing 24  bare 39  {STRAWBERRY: 16, MELON: 8}  seeds {WHEAT: 23, ...}
```

Wheat holds **zero seed through day 12 while 21 tiles sit bare**. It is not
outbid — it does not ask. `plantable_target_tiles` is computed over the
non-zone tiles only (`policy.py`, `_plantable_targets` against
`wheat_tiles = tiles - strawberry_set`), so ground reserved for strawberry is
invisible to the wheat seed target. The zone reserves 31 tiles; the strawberry
line can only plant ~10 of them that early against its own daily cap; the
remaining ~21 are reserved, bare, and unaskable.

The body noted that `dispatch.py:497-513` already falls an unclaimable
strawberry tile through to a WHEAT plant, and that the fall-through fires
correctly. It does — but it cannot fire without wheat seed in the shed, and
the seed never gets bought.

**This is a different intervention with a different mechanism (tile
reservation, not budget order) and it does not belong to this registration.**
Widening this prereg to cover it is exactly the search-widening its kill
criteria exist to prevent. It needs its own prereg, its own bands, and its own
prediction — written before the next measurement, not after this one.

### Disposition of `0d366b9`

Kept, dormant. `strawberry_tile_target` is still 0, so the change is a
bit-exact no-op on the shipped agent — verified by a day-by-day occupancy
census byte-identical to `frozen:m3b_straw_base_9916ce5` on all four seeds. It
fixes a real ordering defect that any future strawberry attempt would hit
first. **It is not a win and must not be recorded as one:** it moved no money,
cleared no gate, and its thesis was killed on the same day it landed.

---

## ADDENDUM — the Amendment-1 scratch probe's mid-game series is superseded by a committed instrument (2026-09-02)

Amendment 1's "Evidence admitted since the body was written" section reports
an "Instrumented decomposition, 7 episodes on band 811000 (scratch probe,
both seats)" — a mid-game money-gap series (`d16 +9,497 / d20 +1,503 /
d24 -19,682 / d28 -33,543`, earn rates d21-29 `champion +1,830/day / kernel
+5,923/day`), and the claim that the champion is "ahead through day 20 in
all seven episodes and lose[s] the last third of every one." That probe's
script and raw data were never committed. **Amendment 1's original text is
unchanged by this addendum** — this section supersedes its mid-game series
rather than editing it.

### What was built

`tools/recon-scripts/kernel_decomposition.py`, a committed, ledgered
instrument for the same comparison (champion at shipped default vs
`zoo:kernel-sokolovsky-2883`, seeds 811000-811006, champion seat 0), with
its output ledgered at
`eval/recon/2026-09-02-kernel-decomposition-811000.json`.

### The mid-game money-gap series does not reproduce

Under the committed instrument's convention (cash-only end-of-day money,
sampled at the engine's own `observation["day"]` boundary), the series reads:

```
d16 +9,644   d20 -142   d24 -26,909   d28 -43,071
earn rate d21-29: champion +2,474/day   kernel +7,607/day  (3.1x)
ahead at d20: 4/7   behind at d29: 7/7
```

This does not reproduce the scratch probe's published series (side by side):

| figure | scratch probe (Amendment 1) | committed instrument |
| --- | --- | --- |
| mean gap d16 | +9,497 | +9,644 |
| mean gap d20 | +1,503 | -142 |
| mean gap d24 | -19,682 | -26,909 |
| mean gap d28 | -33,543 | -43,071 |
| earn rate, champion | +1,830/day | +2,474/day |
| earn rate, kernel | +5,923/day | +7,607/day |
| ahead at d20, all seven | claimed | **4/7** — three seeds already behind |
| behind at d29, all seven | claimed | 7/7 — holds |

Roughly 19 conventions were tried across four families before settling on
the above as canonical: day-boundary sampling (start-of-day, end-of-day,
last-turn-of-day, and a sweep of non-standard turns-per-day values),
seat assignment (champion at seat 0, at seat 1, and seat-averaged pairing per
`harness.gate.seat_mean_money`), a seed-window sweep (811000 ± 100), and an
inventory-valuation family (cash plus held shed/hand stock at current price,
base price, or the champion's own floor price, with and without livestock at
purchase price — 7 variants). None reproduced the scratch probe's series
exactly. The inventory-valuation family moved every figure further from the
published numbers, not closer: the kernel's shed consistently outvalues the
champion's from mid-game on, so crediting held stock widens the gap and
drops ahead-at-d20 from 4/7 to 1/7. Full detail and the per-variant numbers
are in the script's own REPRODUCTION NOTE docstring.

### What is not in question

The engine, agent pairing, and seed handling are correct: the instrument's
seed-811000 final money (candidate $42,554 / opponent $97,131) matches
`eval/gates/2026-08-25T15-22-30Z-champion-vs-zoo_kernel-sokolovsky-2883-
promotion.json`'s seat-0 row cell for cell, on every one of the seven seeds.
This is not champion drift either — the only two commits between the
prereg's cited baseline (`9916ce5`) and the instrument's HEAD that touch
`packages/agent` are `aad11ae`/`0d366b9` (a provable no-op at
`strawberry_tile_target=0`) and a pure-addition harness module. The
mid-game series most likely came from a different, never-committed sampling
convention in the original scratch probe, or a transcription slip, rather
than a reproducible methodological choice.

### The six structural fingerprints stand verified exactly

Kernel: 37 strawberry seeds, all bought days 3-10; sells 300 strawberry
units, days 16-29 (submitted-order-quantity count — see below); 8 cows, all
bought by day 8; 320 milk sold. Champion: 0 strawberry seeds bought; 563
wheat sold. All six reproduce exactly, from seed 811000 alone (the kernel's
plan is seed-invariant on this fingerprint; the champion's wheat-sold total
varies by seed and only 811000 hits 563 exactly).

One caveat on the 300/320 figures: they count SUBMITTED market-order
quantity, not settled sales. Gating the same counts on the engine's
`_commit_unit` return value (i.e. what actually cleared the shed) gives a
lower, seed-varying figure — roughly 277-286 strawberry units and 197-215
milk actually settle, against 300 and 320 requested. The kernel's scripted
plan asks for a fixed schedule regardless of seed; not every ask fills. So
"sells 300 units" / "sells 320 milk" are what the kernel asked to sell, not
what it collected.

### Disposition

The scratch probe's mid-game money-gap series and its "ahead through day 20
in all seven" claim are superseded by the committed instrument above and
should not be cited going forward. The structural characterization of the
kernel's strategy (heavy strawberry and animal supplier, standing-asset
yield bought early and cashed out from mid-game, against a champion that
sells only wheat) stands, and the corrected series still shows the same
qualitative shape — ahead early, run down late — just with different
numbers and a less unanimous day-20 crossover than originally claimed. This
does not change the prereg's own RESULT (killed on the registered
intermediate) or the disposition of `0d366b9` above; it corrects only the
diagnostic evidence cited in Amendment 1's "Evidence admitted" section.
