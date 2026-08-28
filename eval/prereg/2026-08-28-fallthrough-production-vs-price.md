# Pre-registration — is the zone fall-through gain production, or revenue taken from the opponent?

Written **before** any seed on band 662000 was burned, at commit `e764f51`
(`feat/strawberry-zone-fallthrough-seed`, [PR #84](https://github.com/cdcoonce/kaggriculture/pull/84)).
Fixes `n`, the band, the decision points and the power guard in advance.

Successor to `eval/prereg/2026-08-28-strawberry-zone-fallthrough-seed.md`,
which cleared its bound on all four registered opponents and **fired its
`opponent_mean_delta` kill criterion on all four**. This file exists to settle
the single question that negative left open, with a threshold fixed **before**
the measurement rather than argued after it.

## The question

The fall-through change gains **+$15,157 mean** across four replay tapes
(`ci_lower` +9,642 to +11,574, no vetoes). In the same runs the opponent loses
**$4,640 to $12,537**. Two readings fit that:

1. **Production.** We plant the idle zone ground, grow more, and bank more.
   The opponent's fall is a side effect of the extra supply on shared prices.
2. **Price transfer.** Our gain is substantially revenue the opponent would
   otherwise have banked. Against a **replay tape**, which cannot adapt, that
   margin is measuring the tape's cliffs and will not transfer to the ladder.

The predecessor recorded a post-hoc argument for (1) — that a ±3,000 band
inherited from a prereg about *crop displacement* cannot survive an
intervention whose mechanism is planting far more wheat — and deliberately
refused to act on it, because it arrived after the veto fired.

## The instrument

`builtin:pass` takes no market action of any kind. Across the 2026-08-25
promotion sweep it ends every episode holding exactly its $3,000 opening
stake. **There is no revenue for us to take and no supply from it to move
prices.** A gain measured against it is production, by construction.

Run the same arm (`strawberry_tile_target = 31`) and the same frozen
incumbent, paired, against `builtin:pass`.

## Decision points, derived from the observed transfer BEFORE running

Under the strong form of reading (2), our tape gain decomposes as
`gain = production + transfer`, with `transfer` bounded above by the
opponent's own loss. Subtracting per opponent:

| opponent | gain | opponent loss | implied production |
| --- | --- | --- | --- |
| thunder | 15,308 | 5,587 | 9,721 |
| barnyard | 15,392 | 12,537 | **2,855** |
| metac95 | 14,550 | 6,854 | 7,696 |
| mirror | 15,377 | 4,640 | 10,737 |

So reading (2) at its most pessimistic predicts a `builtin:pass` gain near
**2,855**; the mean implied production is **7,752**; reading (1) with no
transfer at all predicts near **15,157**.

**Registered rule** on `mean_delta` vs `builtin:pass`, band 662000, n=32:

- **PRODUCTION** — `ci_lower` > **1,000** (the project's standing money-gate
  threshold, unchanged) **and** `mean_delta` ≥ **7,752**. The gain is not
  meaningfully explained by transfer. The predecessor's fired criterion is
  then reportable as mis-specified for this mechanism, and the change is
  eligible for a confirm run on the unburned band 661600.
- **PRICE** — `mean_delta` < **2,855**, i.e. below even the most pessimistic
  transfer-adjusted estimate. The effect is dominated by revenue transfer.
  Record a negative and stop; the strawberry line is closed.
- **INDETERMINATE** — anything between. Record as indeterminate. **Not**
  eligible for promotion, and not eligible for a re-read on a wider band
  without a new registration.

## Power guard, registered

The two decision points are **4,897** apart. Dispersion is arm-specific and is
not assumed from the tape runs: if the observed **`mde_80` exceeds 4,897**,
this run cannot distinguish the two hypotheses and the result is **not** a
null — it is underpowered. In that case extend `n` on the same band and say
so, rather than reading the point estimate. A failed gate is not a measured
absence.

## Ceiling-compression validity check, registered

Against a passive opponent both arms bank far more than they do in a contested
game (the shipped agent takes ~$99k off `builtin:pass`). If **both** arms are
near that ceiling the delta compresses for reasons unrelated to this question.
Registered check: report both absolute means. If the **baseline** arm's mean
exceeds **90,000**, the reading is ceiling-compressed and must be recorded as
INDETERMINATE regardless of the delta.

The incumbent at `strawberry_tile_target = 31` is wheat-starved until day 14
and is not expected anywhere near that, so this check is expected to pass —
which is exactly why it is written down now rather than invoked later.

## Bands and protocol

- **Band 662000**, n=32 paired seeds. **661600 stays reserved** for the
  predecessor's confirm run and must not be touched here.
- Frozen incumbent `frozen:straw_seedorder_0d366b9`, already behaviourally
  verified at this arm (34.1 standing / 23.1 bare at target 31, matching its
  build's signature).
- Secondary read, **no threshold and no decision weight**: the same comparison
  against `builtin:starter`, which banks ~$3,490 and so competes only
  marginally. Recorded for direction only.
- Read `mde_80`, `n_regressed` and both absolute means **before** the bound.

## What this does not establish

That the change is worth shipping. A PRODUCTION verdict buys one thing: the
right to run the predecessor's confirm on 661600 under its own rule. It does
not retire the standing gap that every gate in this project is fought against
replay tapes of one lineage, and it does not touch the fact that we still lose
the kernel matchup outright.

---

## RESULT — PRODUCTION, and the transfer hypothesis is refuted by its own sign (2026-08-28, `f52d064`)

### Registered guards, read before the bound as required

- **Instrument valid.** `opponent_mean_delta = 0.0`, `min_opponent_money =
  3000` — `builtin:pass` finished every one of the 64 episodes holding its
  untouched opening stake. There was no revenue to take.
- **Powered.** `mde_80 = 3,452`, under the registered 4,897 separation. This
  run can distinguish the two hypotheses.
- **Not ceiling-compressed.** Baseline mean **70,394**, under the registered
  90,000 limit.

### The verdict

```
mean_delta = +25,838   ci_lower = +23,542   n_regressed = 0/32   min_delta = +3,009
candidate_mean = 96,232   baseline_mean = 70,394
```

`ci_lower` +23,542 > 1,000 and `mean_delta` +25,838 ≥ 7,752. **PRODUCTION**,
by a factor of 3.3 over the decision point. **Every one of the 32 paired seeds
improved**, worst case +3,009.

Secondary read, `builtin:starter`, registered as directional only:
`mean_delta` **+23,019**, `ci_lower` +20,952, `n_regressed` 0/32,
`opponent_mean_delta` **+1.39**.

### The transfer hypothesis is not merely unsupported — it has the sign backwards

| opponent | competition | our gain |
| --- | --- | --- |
| `builtin:pass` | none — ends on its untouched $3,000 | **+25,838** |
| `builtin:starter` | marginal — banks ~$3.5k | +23,019 |
| four replay tapes | real | +15,157 |

Reading (2) predicted the gain would **collapse toward 2,855** once there was
no opponent to take revenue from. It **rose to 25,838** — the gain is largest
with no opponent at all and shrinks monotonically as competition rises.

The mechanism the data supports: the change produces roughly **$25.8k** more.
In contested play the extra supply depresses shared prices, so only about
**$15.2k** of it is realised — and that same price depression is what costs
the opponent $4,640–$12,537. **The opponent's loss is a consequence of our
production, not a transfer into our account.**

### Consequence, as registered

The predecessor's `opponent_mean_delta` band is **mis-specified for this
mechanism** — an intervention that plants substantially more wheat cannot
leave a wheat-selling opponent's revenue unmoved, and a band that forbids it
forbids the mechanism rather than the artifact. That was recorded in the
predecessor as a post-hoc hypothesis with no weight. It is now the outcome of
a test whose decision points were fixed before the measurement, so it is
reportable.

Per the rule registered above, the change is eligible for the predecessor's
confirm run on the unburned band **661600**. That is the only thing this
verdict licenses. It does not retire the standing gap that every gate here is
fought against replay tapes of one lineage, and it does not change that we
still lose the kernel matchup outright.
