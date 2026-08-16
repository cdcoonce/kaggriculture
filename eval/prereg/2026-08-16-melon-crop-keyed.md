# Pre-registration — schedule a standing crop off the crop, not the zone

Written **before** the confirm run was launched, at commit `bdadb15`.
Fixes `n`, the seed bands and the decision rule in advance.

## What is being tested

`bdadb15` changes one key in `_field_tasks`: the branch that schedules a tile
already holding a plant now reads `tile["crop"] == "MELON"` instead of
`(x, y) in melon_tiles`. The zone still decides what gets **planted**; only the
standing crop's own schedule now reads off the crop. Strawberry already worked
this way and says so in a comment; melon did not.

This is a **code change**, so the baseline is a frozen incumbent
(`frozen:premelon-ff8266a`, materialized from `ff8266a` via
`harness.frozen.freeze_incumbent`), not a config-only A/B. Disjointness was
verified before use: the frozen copy still contains the zone-keyed
`elif is_melon:` in the plant branch, the live tree does not, the frozen copy
contains the crop-keyed branch nowhere, and its imports are rewritten off the
live `agent` package.

## Mechanism, measured before any gate was run

`melon_tiles` is a proximity-ordered prefix of `target_tiles`, and a `BUY_LAND`
re-orders `target_tiles` — `constants.py` states this outright and pins the
pasture zone to a fixed frame because of it. So the melon zone sheds tiles that
already hold a melon and admits tiles that already hold wheat.

Measured on three episodes (seeds 620900-620902), seat 0 vs `tape-thunder-719`,
reading each action at index `i` against the observation at `i-1` (the alignment
premise was checked first: 1107 farmer moves, 0 disagreements):

| | HARVEST fired | effective | dead | rate |
|---|---|---|---|---|
| `ff8266a` (zone-keyed) | 1,165 | 849 | 316 | **27.1%** |
| `bdadb15` (crop-keyed) | 901 | 901 | 0 | **0.0%** |

Every one of the 316 dead fires hit the `first_yield_day` guard, was MELON, and
was out-of-zone. **None hit `yield_units <= 0`** — the cause named in the
previous handoff is not the cause. Effective harvests rise 849 → 901 (+6.1%),
so this is not only less waste: the melons are worked on melon's schedule
instead of being hammered at age 5 and left past ripeness.

## Screen (already run, ledgered)

`eval/gates/2026-08-16T21-38-08Z-champion-vs-zoo_tape-thunder-719-money.json`
— thunder, band 630000, n=20:
mean +5,187, median +6,815, sd 9,032, `ci_lower` **+1,695**, `n_regressed` 4/20,
skew -0.54, vetoes none. PASS against the $1,000 primary bar at n=20.

## Fixed design (locked before launch)

Band **631000**, disjoint from 630000 and from every band burned to date.

| tape | threshold | n | seeds |
|---|---|---|---|
| thunder-719 (primary) | > $1,000 | 128 | 631000-631127 |
| barnyard-719 | > $0 | 128 | 631000-631127 |
| metac95-720 | > $0 | 128 | 631000-631127 |
| mirror-719 | > $0 | 128 | 631000-631127 |

n=128 is twice the documented confirm size. At the screen's sd it gives
`ci_lower` ~ +3,900 on thunder; it still clears $1,000 if the true sd is the
13-16k seen on other arms and the true mean is as low as +3,100.

**No tape gets additional seeds after its result is seen.** If a tape lands
inside its own noise band, the reported answer is the interval, not a re-run.

## Decision rule (per `eval/README.md`, unchanged)

PROMOTE only if all hold: `ci_lower > 1000` on thunder **and** `ci_lower > 0` on
barnyard, metac95 and mirror; `vetoes == []` everywhere; and `skew_delta` read on
every tape — any tape that only just clears its bar while `skew_delta < -1.0` is
reported **inconclusive**, not passed.

## Operational note that invalidated an earlier run

The money gate resolves `champion` from the **live working tree**, and
`run_money_gate` builds a fresh `ProcessPoolExecutor` per arm. Editing
`packages/agent/**` while a gate is in flight can therefore give the candidate
arm one code version and the baseline arm another. A `hand_mule_load` confirm
launched at 21:25:28Z was discarded for exactly this reason; it never completed,
so no ledger was written and nothing false entered the record. **No agent source
is edited while these four runs are in flight.**
