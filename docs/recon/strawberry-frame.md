# The strawberry reference frame — why widening it does not buy thunder's shape

_Measured 2026-09-06 at `5528223` (main, i.e. M3b + `hand_mule_load` 20 from
`96d8b41`) plus this branch's `strawberry_frame_live` flag. Instrument:
`harness.crop_quadrant` / `tools/recon-scripts/crop_quadrant.py`. Ledgers:
`eval/recon/2026-09-06-crop-quadrant-{thunder,shipped,straw24-fixedframe,straw24-liveframe}-900600.json`
(3 seeds, recon band 900600, champion seat 0). Recon only — no gate was run and
no gate band was burned._

_Agent version matters here and is called out because it changed the answer:
these numbers were first taken pre-`96d8b41` and re-taken after it. The
structural finding is identical; the money column flipped sign, which is itself
part of the finding (see below)._

## The question

`constants.py` pins `STRAWBERRY_REFERENCE_QUADRANTS = ("NW", "NE")` and
`policy.py` calls `strawberry_tiles()` with that fixed tuple, while
`melon_tiles()` tracks the live `unlocked_quadrants`. The proposal was that this
frozen frame is what killed every strawberry arm ever gated — that the zone was
structurally unable to express the shape `zoo:tape-thunder-719` runs, and that
widening it to include SW would reopen the line.

It does not. The frame is real and thunder's SW share is real, and widening the
frame still buys **32 strawberry tile-days in SW against thunder's 241**.

## What thunder actually does

Days 10–28 tile-days, `zoo:tape-thunder-719` (identical on all three seeds — it
is a replay tape):

| crop | NW | NE | SW | total |
| --- | --- | --- | --- | --- |
| STRAWBERRY | 79 | 184 | **241** | **504** |

SW is **47.8%** of thunder's strawberry tile-days. The figure is exact and
reproduces. Earlier doubt about it came from summing all 30 days instead of the
10–28 window this repo reports on everywhere else.

## The mechanism is fill latency, not land timing

**The champion buys SW a day EARLIER than thunder and still never fills it.**
Seed 900600, SW quadrant only:

| day | champion SW | thunder SW |
| --- | --- | --- |
| 10 | 19 bare, 6 standing | not yet owned |
| 11 | 19 bare, 6 standing | 3 bare, 20 standing (6 melon + 14 strawberry) |
| 12 | 16 bare, 9 standing | **0 bare**, 24 standing (9 melon + 15 strawberry) |
| 13–16 | 14–16 bare, every day | 0 bare |

Buying the land was never the constraint. Filling it is.

## Why widening the frame does not reproduce that

`STRAWBERRY_PLANT_CUTOFF_DAY = 12` (`dispatch.py`), and turning strawberry on
delays the agent's *own* SW purchase past its *own* cutoff — measured across 16
seed-seats per arm with no variance:

| agent_config | SW owned by | last strawberry planting |
| --- | --- | --- |
| shipped defaults | day 10–11 | — (target 0) |
| `{strawberry_tile_target: 6}` | day 12 | day 0 |
| `{strawberry_tile_target: 12}` | day 12 | day 12 |
| `{strawberry_tile_target: 20}` | day 12–13 | day 11–12 |
| `{strawberry_tile_target: 24, wheat_rush_tiles: 30}` | **day 13** | day 12 |
| `{strawberry_tile_target: 31}` | **day 13** | day 12 |

Strawberry's $100/seed spend competes with the $2,000 SW land reserve that
`plan.py` gates behind `animals_done`. Every strawberry arm pushes its own land
buy toward its own planting cutoff. Even six tiles costs a day or two.

The overlap that survives is **hours, not days**, and a first-turn-of-day census
hides it: SW is bought mid-day-12 and a strawberry or two goes in during the
remaining hours (`planted_day=12`). That is the entire reach of a live frame.

## Measured effect of the flag

`strawberry_frame_live=True` vs the shipped fixed frame, same seeds and seats
(`{strawberry_tile_target: 24, wheat_rush_tiles: 30}`, seed 900600, days 10–28):

| STRAWBERRY tile-days | fixed frame | live frame |
| --- | --- | --- |
| NW | 95 | 63 |
| NE | 129 | 97 |
| SW | 0 | **32** |
| **total** | **224** | **192** |

Widening the frame makes the strawberry patch **smaller**.
`strawberry_tiles()` slices `target_tiles(unlocked)[18:18+target]`, so a wider
`unlocked` re-orders the whole universe nearest-shed-first and collides
differently with `pasture_tiles()`, which stays pinned to `("NW","NE")`. At
`target=24` the live frame nets 18 tiles where the fixed frame nets 24. It is
not a superset.

Paired per-game money, 16 games per arm (band 900500, opponent
`frozen:m3b_live_b6ce655`), mean candidate delta live-minus-fixed:

| arm | games differing | mean Δ candidate $ | same, pre-`96d8b41` |
| --- | --- | --- | --- |
| `straw24 + wheat30` | 16/16 | **−3,607** | +1,193 |
| `straw31` satellite | 15/16 | **−2,689** | −3,421 |
| `straw20` | 16/16 | −1,977 | −1,922 |
| `straw12` | 16/16 | −182 | −504 |
| `straw6` | 2/16 | +19 | −32 |

At the current agent the live frame is **negative on every arm large enough to
matter**. It was not, one commit ago: the largest arm flipped from +1,193 to
−3,607 when `hand_mule_load` changed, a knob with nothing to do with strawberry
or quadrants. An effect whose sign is decided by an unrelated labor constant is
not a mechanism — it is the flag's largest real consequence showing through,
which is **which tiles wheat is excluded from after day 12**, when nothing can
plant strawberry on the reserved ground at all.

## Conclusion

A gate on the frame alone would measure zone re-slicing, and a null would be
recorded as "strawberry is closed for good" on evidence that never tested the
thesis. The frame is a real constraint sitting behind a closed door; the door is
the day-12 cutoff and the arm's own land-buy delay.

Anything that revisits this needs the interlock, not the constant: the frame
widened **and** the day-10/11 land buy preserved against strawberry's seed
spend, and probably `strawberry_plant_daily_cap` raised above 6 — two plantable
days at 6/day is 12 tiles against thunder's 15. Those constants were calibrated
for a three-quadrant wheat monoculture and have never been swept together.

**Do not mirror any of this onto pastures.** `dispatch.py` gates pasture chores
on zone membership with no animal-generic fallback, so a drifting pasture frame
silently starves placed animals — the failure `PASTURE_REFERENCE_QUADRANTS`
exists to prevent. Crops are safe because dispatch keys standing-crop scheduling
on `tile.get("crop")` (commit `01a5123`), now pinned for strawberry by
`test_strawberry_evicted_from_the_zone_keeps_strawberry_timing`.

## Caveats

- Recon, not a gate. Three seeds for the census, 16 games per arm for the money
  A/B. Directional only; nothing here is a promotion result.
- The money A/B moves tile occupancy, so kaggriculture#82 applies: it is a
  mechanism read, not a paired estimate.
- Thunder is a replay tape. It shows what a strong build looks like; it is not
  evidence we could execute the same build.
- Every number here is agent-version-dependent. Re-measure before citing against
  a tree that has moved.
