# Standing-crop occupancy — why the ground is empty

_Measured 2026-08-18. Instrument: `harness.occupancy` /
`tools/recon-scripts/occupancy.py`. Ledger: `eval/recon/2026-08-18-occupancy-*.json`
(4 seeds, band 661200, champion seat 0 vs `zoo:tape-thunder-719`, both seats
censused from the same episodes)._

## The headline

Days 10–28, mean over 4 seeds:

| | mean standing | **mean bare ground** | crop mix (tile-days) |
| --- | --- | --- | --- |
| champion | 42.0 | **39.4** | WHEAT 87% · MELON 13% |
| `tape-thunder-719` | 58.4 | **1.3** | STRAWBERRY 45% · WHEAT 42% · MELON 13% |

**The champion leaves ~39 tiles of plantable, empty ground idle every single
day. Thunder leaves 1.3.** That is the entire occupancy gap, and it is not
subtle — it is visible on every seed, on every day from 11 onward.

> **STALE (corrected 2026-09-06): the champion row above is a FOUR-QUADRANT
> agent and does not describe the shipped M3b.** This census ran 2026-08-18,
> a week before `MAX_OWNED_QUADRANTS = 3` landed in `b6ce655` (2026-08-25) —
> the very commit `frozen:m3b_live_b6ce655` is cut from. Peak `standing + bare`
> is **89** on all four ledgered seeds; three quadrants is only 74 tiles, so
> these numbers are arithmetically impossible for the agent that ships today.
> Re-measured on the current agent: **34.8 standing / 26.2 bare**, not
> 42.0 / 39.4. The
> thunder row is unaffected and reproduces (58.6 measured). See "Correcting the
> record, again" at the end of this file.

"Bare" here means literal `None` tiles: owned, unlocked, no structure, no
weed, immediately plantable. A WEED tile is excluded because it needs a `DIG`
first, so folding it in would overstate the available ground.

## What it is NOT

Each of these was a live hypothesis; each is ruled out by measurement, not by
argument.

- **Not seed supply.** On the days planting collapses to 0–2 actions, the
  wheat seed pool holds 39–40 seeds. Measured on the stall days themselves,
  not on a daily average.
- **Not the plant quota.** `plant_quota(day, active) = ceil(active/5)` is
  ~17–18/day at the live board size. Actual planting on stall days is 0–5.
  The quota is not binding when planting stops.
- **Not crew size.** The crew rebuilds identically every day (0→4→8→12→13).
  The market→labor coupling hypothesis — that a full sell book truncates the
  HIRE orders appended last, per `market.py:415` — is real in structure and
  dead in practice: **1 turn in 720** had a full 10-slot order book, and zero
  HIREs were ever dropped.
- **Not cohort synchronization, at least not distinguishingly.** The
  champion's age histogram is peaked with the peak walking one bin per day —
  but so is thunder's. Largest-age-bin share: champion 42%, thunder 44%. Both
  farm in cohorts; only one of them leaves the board empty.
- **Not post-harvest tile state.** A harvested wheat tile becomes `None` and
  is replantable the next turn. No `DIG` is required.

## What it is

Labor cost per tile-day held, driven by crop mix.

WHEAT is `ongoing: False` (engine `CROPS`), so harvest destroys the tile and
the whole cycle repeats every ~5 days: 1 PLANT + 3 WATER + 1 HARVEST ≈ **1.0
unit-actions per tile-day held**. STRAWBERRY is `ongoing: True` — the tile
survives harvest and holds ground for 16+ days on roughly 0.8 actions per
tile-day, most of that front-loaded.

A wheat monoculture therefore saturates the crew at ~42 worked tiles. Thunder
holds 58 tiles with the same crew because **45% of its tile-days are on a crop
that does not have to be replanted at all**. Its late game is explicit about
this: from day 21 it liquidates the strawberry patch (30→27→25→16→13→1) and
converts to a wheat rush (23→27→31→41→45→59) for the endgame.

## Why every strawberry arm measured dead

Prior screens sized strawberry as a **satellite**: 6/8/11/16/24/32 tiles added
on top of the full wheat rush. On a labor-saturated farm that is strictly
negative — it takes crew away from wheat and gives back less, and the zone
never fills (peak 13 of 16). Thunder does not run strawberry as a satellite.
It runs it as ~45% of the farm, **replacing** wheat rather than supplementing
it, which lowers total labor demand per tile-day held instead of raising it.

That is a different intervention from anything screened so far, and the
existing negative results do not bear on it.

## Caveats

- Thunder is a replay tape, so its board is near-identical across seeds
  (bare 1.3 on every one). It shows what a strong build looks like; it is not
  evidence that we could execute the same build.
- The instrument samples each day's **first turn**. Mid-day the board churns,
  so hour-0 is the only sample at which "standing" is comparable across days.
- The `IDLE` discriminator — units unassigned on turns where PLANT tasks
  exist — is **not** measured here; it needs dispatcher internals. `PASS`
  counts (1–8/day against ~300 unit-turns) are a proxy suggesting labor is
  near-fully consumed, but a proxy is not the number.
- Occupancy is an intermediate, not the objective. Money is. Holding more
  ground is only worth it if the crop sells, and this document does not
  establish that.

## Correcting the record

The figures in the previous handoff (champion oscillating 26.8–59.7, opponent
~61.0 flat) appear **nowhere** in `eval/` or the tree. They were never
ledgered. The direction was right; the numbers as reproduced here are
different, and the causal story attached to them — "replant latency" — is not
supported.

The instrument that handoff named as "the read", `strawberry_labor.py`'s
`alive_by_day`, filters `tile["crop"] == "STRAWBERRY"` and the shipped
champion sets `strawberry_tile_target = 0`. Run against the shipped agent it
returns `peak_alive: 0` on all thirty days. It could never have measured this.

## Correcting the record, again (2026-09-06)

The champion column of the headline table is **stale by six days and one gated
decision**, and two live pre-registrations cite it.

`MAX_OWNED_QUADRANTS = 3` — refusing the SE quadrant — landed 2026-08-25 in
`b6ce655` (kaggriculture#59, PR #81), gated at
`eval/prereg/2026-08-23-max-owned-quadrants.md`. This census ran 2026-08-18 and
was committed 2026-08-19 (`acd7244`), so its champion owned **all four
quadrants**.

The tell is in the committed ledgers themselves. `standing + bare` can never
exceed owned tiles, and three quadrants is 74 tiles (`target_tiles` excludes
`COOP_TILE`):

| ledger | mean standing | mean bare | peak `standing + bare` |
| --- | --- | --- | --- |
| `eval/recon/2026-08-18-occupancy-661200.json` | 42.9 | 38.2 | **89** |
| `eval/recon/2026-08-18-occupancy-661201.json` | 42.6 | 38.8 | **89** |
| `eval/recon/2026-08-18-occupancy-661202.json` | 42.0 | 39.6 | **89** |
| `eval/recon/2026-08-18-occupancy-661203.json` | 40.4 | 40.9 | **89** |

89 > 74 on every seed. Only a four-quadrant board can hold it.

Re-measured (`harness.crop_quadrant`, 3 seeds, band 900600, vs
`zoo:tape-thunder-719`, ledger
`eval/recon/2026-09-06-crop-quadrant-shipped-900600.json`) at `5528223` — M3b
plus `hand_mule_load` 20 from `96d8b41`: **34.8 standing** against **26.2
bare**, over days 10–28. Thunder in the same episodes: **58.3 standing / 1.3
bare**, confirming the 58.4 / 1.3 row is sound.

The mule change moved this: the same census before `96d8b41` read 31.3 standing
/ ~30 bare, so HML20 bought ~3.5 tiles of occupancy. Quote these figures with
the agent commit attached — that is the error this section exists to correct,
and it recurs every time the agent moves.

**What this does and does not change.** The qualitative finding stands: the
champion still leaves roughly as much ground bare as it farms, against a
thunder that leaves 1.3 tiles. What changes is the magnitude and the
denominator — the gap is ~26 idle tiles out of 74 owned, not ~39 out of 99, and
the crop-mix percentages in the headline row are for a board that no longer
exists.

`eval/prereg/2026-09-06-wheat-rush-tiles-cap.md` and
`eval/prereg/2026-09-06-w30-promotion-confirmation.md` both cite "42.0 standing
tiles with 39.4 bare" from this file as the sprawl story motivating the wheat
cap. **Neither result depends on it** — both explicitly record the mechanism as
hypothesis rather than result, and W30's 0.860 head-to-head is an outcome
measurement — but the figure they cite is off by about ten tiles in each
direction and should be quoted from the 2026-09-06 ledger instead.
