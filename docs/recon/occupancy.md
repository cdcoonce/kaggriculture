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
