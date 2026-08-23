# Where the owned-quadrant cap's money comes from

Instrument: `harness.settlement` (`packages/harness/src/harness/settlement.py`),
CLI `tools/recon-scripts/land_attribution.py`.
Ledgers: `eval/recon/2026-08-23-land-attribution-barnyard-663300.json`,
`eval/recon/2026-08-23-land-attribution-thunder-663310.json`.
No agent behavior changes; `dist/` untouched.

## Why a money delta was not enough

A money gain can be revenue an arm **earned** or spend an arm **avoided**, and
the two have opposite implications. An arm that sells *more* into a shared
market may be riding a price it lifted for both players — the #75 pattern,
where capping wheat paid the blind tape ~4x what it paid us. An arm that sells
*less* and banks more cannot be that thing.

`opponent_mean_delta` is the standing veto against the first case. On the
`max_owned_quadrants=3` screen it fired on barnyard at **+6,438**, outside the
±3,000 band. This instrument exists to test the mechanism the veto proxies
for, rather than argue about the threshold.

## Method

Wrap the engine's own settlement, and record **only on a `True` return**:
`_commit_unit` returns False and mutates nothing when an order cannot be
filled, so recording on the CALL books rejects as fictional sales (measured at
26 of 80 EGG SELL calls on one seed). Seat comes from **object identity**
against the farms list `_process_market` holds — never call order — and an
unresolvable farm raises rather than guessing. `farms` is re-broadcast to
every seat, so a wrong-seat read produces clean, plausible, fictional numbers
and looks like nothing is wrong.

Teeth in `packages/harness/tests/test_settlement.py`: rejects excluded (with a
companion test proving the excluded reject carried real value, so the
exclusion is not a no-op); identity not equality (two farms with identical
contents must not collapse to one seat); unknown farm raises; commit before
`_process_market` raises.

## Result

Champion at `max_owned_quadrants` 4 → 3, both seats recorded, n=4 seeds per
tape.

| tape | cost-side Δ | spread | revenue Δ | spread |
|---|---|---|---|---|
| `tape-barnyard-719` (663300–663303) | **+11,824** | **235** | −2,127 | 5,019 |
| `tape-thunder-719` (663310–663313) | **+11,952** | **468** | −6,849 | 10,865 |

Two things follow.

**The gain is cost-side, and opponent-invariant.** ~$11,800–12,000 per season
on both tapes, as it must be — it is our own spending decision and does not
depend on who we play. It decomposes as $4,000 of SE land plus ~$7,900 of crew
that is never re-rented: `_end_of_day` empties `farm["hands"]`, so the whole
fibonacci ladder is re-paid daily, and `hands_target` scales with
`active_tiles`.

**Revenue falls on both tapes.** We sell *less* wheat (units −129 to −164 per
seed) and bank more. Whatever the money gain is, it is not revenue captured
from a price we lifted.

## The opponent delta is a shop-draw artifact, not supply withdrawal

Every opponent revenue delta carries **`units +0`**: the tape sells an
identical schedule and is paid differently. Seed 663300's tape gain is
+17,197 **STRAWBERRY** — a market the champion never trades
(`strawberry_tile_target` is 0). Capping our land cannot vacate a book we were
never in.

The cause is upstream of the market entirely. `_spawn_weeds` advances the rng
only for bare tiles, and the day's shop is then drawn `rng.choice(sorted(SHOPS))`
from that same stream, so **the shop roster is downstream of our own
occupancy**. Measured:

```
663302  cap=4: YARN_STORE x3, BAKERY x1, no FARMERS_MARKET
        cap=3: YARN_STORE x2, BAKERY x2, FARMERS_MARKET x1
663303  cap=4: YARN_STORE x2, BAKERY x2, no PET_CAFE
        cap=3: YARN_STORE x1, FARMERS_MARKET x2, PET_CAFE x1, SMOOTHIE_SHOP x2
```

Different shops, different drain, different prices — for both seats, on
identical volumes. Seed 663303 shows it plainly: YARN_STORE (the only wool
consumer) drops 2 → 1 and WOOL revenue falls for *both* players.

## Scope of the defect

**This is not specific to this arm or this tape. Every gate in `eval/gates/`
is affected.** Any arm that changes bare-tile count shifts the shop draw, so
"paired" seeds do not pair such arms: the reported `sd_delta` is honest
dispersion, not a variance-reduced pair sd, and effective power is below what
it implies. The shift is treatment-correlated but its per-seed direction is
essentially random, so it should behave as variance rather than bias at n=20+.

Filed separately; not fixed here.

## What this does not establish

- It does not decompose the cost saving into land ($4,000) versus crew
  (~$7,900). Both move together and this instrument does not separate them.
- It does not make the barnyard money bound clean. It shows the veto fired on
  a mechanism orthogonal to the intervention; the bound remains confounded by
  the shop draw, as do all four tapes' bounds to a lesser degree.
- It says nothing about whether $11,800 of saved cost beats the ~$5,000–7,000
  of foregone revenue on every tape. That is what the confirm gate measures.
