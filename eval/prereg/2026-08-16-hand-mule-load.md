# Pre-registration — `hand_mule_load` 9 → 20 (disable the hand-mule)

Written **before** the confirm run was launched, at commit `ff8266a`.
Its purpose is to fix `n`, the seed bands, and the decision rule in advance,
so the verdict cannot be produced by choosing a stopping point after the fact.

## What is being tested

`PolicyConfig.hand_mule_load` (default `9`, `packages/agent/src/agent/dispatch.py:23-25`)
is the carried-unit threshold at which a hand (unit index >= 1) is pulled out of
the field-task race and walks to the shed to `DROP`
(`packages/agent/src/agent/dispatch.py:640-644`).

**Measured saturation, this session:** `hand_mule_load` in `{20, 24, 32}` produce
byte-identical results — identical `mean_delta` (4374.6875), `sd_delta`
(14777.549057214896), `skew_delta` (0.268770069488856) and `min_delta` (-17236.0)
at `--seed-base 610000 --n-seeds 8` on `tape-thunder-719`. Ledgers:

- `eval/gates/2026-08-16T21-20-46Z-champion-vs-zoo_tape-thunder-719-money.json` (20)
- `eval/gates/2026-08-16T21-21-46Z-champion-vs-zoo_tape-thunder-719-money.json` (24)
- `eval/gates/2026-08-16T21-22-48Z-champion-vs-zoo_tape-thunder-719-money.json` (32)

Therefore the arm is **not a tuning value**. Any value >= 20 means "the hand-mule
never fires". This is a binary on/off contrast, and `20` is the canonical
representative of the OFF arm.

Control: `hand_mule_load=9` against the stock baseline returns `mean_delta=0.0`,
`sd_delta=0.0`, `n_regressed=0/8`
(`eval/gates/2026-08-16T21-19-51Z-champion-vs-zoo_tape-thunder-719-money.json`) —
the config path is wired and the engine is deterministic given a seed.

## Prior evidence (screen + two confirms, all ledgered)

| tape | band | n | mean_delta | ci_lower | n_regressed |
|---|---|---|---|---|---|
| thunder | 591000 | 20 (screen) | +3,304 | -1,488 | 7/20 |
| thunder | 592000 | 64 | +556 | -2,426 | 37/64 |
| thunder | 603000 | 64 | +4,781 | +2,099 | 20/64 |
| barnyard | 603000 | 64 | +1,513 | -1,781 | 29/64 |

Pooling the two thunder confirms by hand (n=128): mean +2,669, sd 13,702,
one-sided 95% t `ci_lower` **+662** — short of the $1,000 primary bar.

The two thunder bands are exchangeable. The engine has no seed-indexed scenario
table: every seed instantiates a bit-identical starting world, and the seed's
entire influence is a per-day weed roll and a shop-unlock draw
(`kaggriculture.py:856-878`, engine pinned at `kaggle-environments==1.32.6`).
The 592000-vs-603000 gap is sampling, not structure.

## Why n has to be this large

Across-seed correlation between the candidate and baseline arms is only
**0.38-0.57** (measured on the three ledgers above), and **0 of 192 seeds** have a
delta near zero — on a knob that binds on well under 1% of normal-day fetches.

Cause: `_spawn_weeds` (`kaggriculture.py:823-827`) calls `rng.random()` only on
empty tiles, so the number of draws consumed is a function of policy behaviour.
Any policy change shifts the draw count, which shifts that day's shop-unlock
draw, which decoheres the trajectory. Same-seed pairing therefore removes only
38-57% of variance, not the 65.8-99.97% claimed in
`packages/harness/src/harness/money_gate.py:9`.

This is **endogenous to making any change at all** and cannot be fixed by a
common-random-numbers refinement. More seeds is the only available lever.
`sd_delta` ~13-16k is the floor, so `mde_80` at n=64 is ~$4,000 — no knob worth
less than that is detectable at the repo's default confirm size.

> ### CORRECTION (appended same session, after the melon confirm)
>
> **The two sentences above in bold are wrong and are retracted.** They are left
> in place rather than edited away, because the prereg's whole purpose is that it
> cannot be rewritten after seeing a result.
>
> The *mechanism* survives: `_spawn_weeds` short-circuits, so the RNG draw count
> really is policy-dependent, and a policy change really can desynchronize the
> weed/shop stream. That is code, and it is checkable.
>
> What does **not** survive is the inference that 38-57% is a floor, that
> `sd_delta` ~13-16k is irreducible, or that no CRN refinement could help.
> Recomputing pairing quality across all 30 ledgered arms with per-seed data
> gives a range of **-17.8% to +94.5%**:
>
> | arm | var. reduction | sd_delta |
> |---|---|---|
> | `strawberry_tile_target: 32` | **-17.8%** (worse than independent) | 14,335 |
> | `melon_tile_target: 20` | -13.2% | 19,029 |
> | `hand_mule_load: 20` (four runs) | 38.0% - 56.5% | 12,855 - 15,786 |
> | melon crop-keyed fix (n=128) | **81.8%** | 7,283 |
> | `melon_tile_target: 18` | 86.2% | 5,957 |
> | `wheat_rush_tiles: 40` | **94.5%** | 4,086 |
>
> Pairing quality tracks how violently an arm perturbs the trajectory, which is
> consistent with the mechanism — but it is arm-specific, not a property of the
> harness, and low-perturbation arms measure cleanly at n=20.
>
> The genuinely interesting residue, which is a **hypothesis and not a finding**:
> `hand_mule_load`, documented as binding on under 1% of normal-day fetches,
> decoheres *more* than the melon fix, which changes 27% of all HARVEST fires and
> directly empties tiles. That is backwards on any "bigger behavioural change
> decoheres more" story. It is what a noise-mediated effect looks like next to a
> mechanism-mediated one, but nothing here establishes that, and it must not be
> cited as if it did.
>
> This correction was produced by checking the claim against every arm on disk
> instead of against the one arm that motivated it.

## Fixed design (locked before launch)

Band: **620000**, disjoint from every burned band. Nested across tapes, so all
four tapes share their first 256 seeds.

| tape | threshold | n | seeds |
|---|---|---|---|
| barnyard-719 | > $0 | **768** | 620000-620767 |
| thunder-719 (primary) | > $1,000 | **512** | 620000-620511 |
| metac95-720 | > $0 | **256** | 620000-620255 |
| mirror-719 | > $0 | **256** | 620000-620255 |

Sizing is 80% power at the observed point estimates:
thunder needs n >= 417 to clear $1,000; barnyard needs n >= 674 to clear $0.
Barnyard is the binding constraint and is run **first** — if it fails, the
intersection-union rule is already lost and the remaining three tapes are not run.

`--workers 9`. Every run is ledgered under `eval/gates/`; `--no-ledger` is not used.

## Decision rule (per `eval/README.md`, unchanged)

PROMOTE only if **all** hold:

1. `ci_lower > 1000` on thunder-719, and `ci_lower > 0` on barnyard-719,
   metac95-720 and mirror-719;
2. `vetoes == []` on every tape;
3. `skew_delta` is read on every tape. The t bound's one-sided level degrades
   under strong left skew (0.0753 at skew -1.75, 0.1196 at -6.2). If any tape
   whose bound only just clears its bar also has `skew_delta < -1.0`, the result
   is reported as **inconclusive**, not as a pass.

Otherwise: **not promoted**. A failure here is recorded as "the effect is real but
does not clear the bar at n=<the n actually run>", with the interval, and
explicitly **not** as "labor does not convert to money" — the distinction that
`ad97540` got wrong and `cf71c5e` retracted.

No additional seeds will be added to a tape after seeing its result. If a tape
lands inside its own noise band the honest report is the interval, not a re-run.
