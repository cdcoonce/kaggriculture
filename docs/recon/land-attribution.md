# Where the owned-quadrant cap's money comes from

Instrument: `harness.settlement` (`packages/harness/src/harness/settlement.py`),
CLI `tools/recon-scripts/land_attribution.py`.
Ledgers: `eval/recon/2026-08-23-land-attribution-barnyard-663300.json`,
`eval/recon/2026-08-23-land-attribution-thunder-663310.json`.
No agent behavior changes; `dist/` untouched.

## Why a money delta was not enough

A money gain can be revenue an arm **earned** or spend an arm **avoided**, and
the two have opposite implications. The #75 pattern — capping
`wheat_rush_tiles` and paying the blind tape ~4x what it paid us — is what a
supply-withdrawal artifact looks like.

**An earlier version of this document argued that an arm which sells *less*
and banks more "cannot be that thing." That was wrong, and it was the sentence
the whole argument rested on: #75 was itself a cap, i.e. selling less.
Selling less into a shared market is the *signature* of supply withdrawal, not
a defence against it.** The split below is still worth having — it says where
the money came from — but it acquits nothing on its own.

`opponent_mean_delta` is the standing veto against the first case. On the
`max_owned_quadrants=3` screen it fired on barnyard at **+6,438**, outside the
±3,000 band.

**How that was actually resolved, stated up front so this document is not
misread as the resolution:** the veto trip did not reproduce. At n=64 on a
disjoint band barnyard's `opponent_mean_delta` is **−1,091**, and all four
tapes sit inside ±3,000 (`eval/gates/2026-08-23T21-*`). The threshold is a
fixed dollar bound on a statistic whose SE scales with n — 2,558 at n=20,
1,034 at n=64 — and under a true zero it fires on at least one of four tapes
roughly half the time at screen n. It was an underpowered-measurement
artifact, and re-measurement is what settled it. This instrument explains the
channels; it did not and could not license overriding the veto.

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

**The gain is cost-side, and opponent-invariant.** ~$11,800–12,200 per season
on every opponent tried, as it must be — it is our own spending decision and
does not depend on who we play.

**The decomposition is now measured, not inferred.** `_do_hire` and
`_do_buy_land` bypass `_commit_unit` and write `farm["money"]` directly, so an
earlier version of this document could only assert the split arithmetically —
and contradicted itself by saying elsewhere that the instrument could not
separate the two. Both paths are now captured by differencing `farm["money"]`
across the call (`eval/recon/2026-08-23-land-attribution-hireland-663340.json`,
n=4 vs barnyard):

| | cap=4 | cap=3 | saving |
|---|---|---|---|
| hire spend / season | 11,492–11,505 (317–318 hires) | 3,104–3,117 (263–264) | **+8,388** every seed |
| land spend | 7,000 | 3,000 | **+4,000** (exactly SE) |
| measured total | | | **+12,388** |
| cost-side residual | | | +12,008 to +12,170 |
| **unattributed** | | | **−218 to −380** |

The unattributed remainder is small and has a known sign: seat-0 market spend
*rises* on every seed (we buy wheat back at the price we lifted). This also
settles **prediction 2** of the prereg — hire spend/season below $4,000 — which
until now was unmeasured.

The mechanism is the engine's: `_end_of_day` empties `farm["hands"]`, so the
whole fibonacci ladder is re-paid daily, and `hands_target` scales with
`active_tiles`.

**Revenue falls on both tapes.** We sell *less* wheat (units −129 to −164 per
seed) and bank more. Whatever the money gain is, it is not revenue captured
from a price we lifted.

## The opponent delta has two channels, and the smaller one is us

Every opponent revenue delta carries **`units +0`**: the tape sells an
identical schedule and is paid differently.

**Do not use `units +0` as evidence of anything.** A replay tape's tile grid is
bit-identical between these arms — its bare-tile count is 0–2 on 28 of 29 days,
so it consumes essentially no rng draws — which makes `units +0` **forced by
construction** for any replay-tape opponent. It cannot discriminate "the shop
draw moved the price" from "we withdrew supply and moved the price," and an
earlier version of this document used it as if it could.

**Channel 1 — supply withdrawal, real and consistent.** We sell 129–164 fewer
WHEAT units per seed, `market_price` is monotonically decreasing in inventory,
and `_commit_unit` SELL increments that inventory. The opponent's WHEAT revenue
delta across the eight recon seeds is **+1,331 / +1,152 / +2,650 / +365 /
+2,171 / +3,528 / +811 / +1,322** — **8/8 positive, mean +1,666 gross, ~+1,276
net** of its own increased buy-back. Both seats' realized wheat $/unit rise on
8/8 seeds. This is the #75 mechanism, present and measured, at roughly 15% the
size of the cost saving. **It is a known cost of this arm, not an absent one.**

**Channel 2 — the shop draw, larger but sign-flipping.** Seed 663300's tape gain
is +17,197 STRAWBERRY, a market the champion never trades
(`strawberry_tile_target` is 0), so that term cannot be supply withdrawal. But
across all eight seeds STRAWBERRY runs +17,197 / −17,438 / +8,746 / +4,761 /
+3,114 / +5,727 / −2,209 / −2,017 — sign-flipping, sd ≈ 9,000, mean +2,235. An
earlier version of this document generalized from the single largest term of an
n=4 sample and called this channel "the cause." It is the *noisier* channel;
the consistent one is wheat.

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

**This is a mediator, not a confound.** The roster shift is *caused by* the
treatment (bare-tile count is downstream of the land cap), so it cannot be
subtracted out and the arm cannot be acquitted of it. What it can be is
*averaged over*: its per-seed direction is essentially random, which is why
barnyard's opponent delta moves from +6,438 at n=20 to −1,091 at n=64.

## Scope of the defect

**This is not specific to this arm or this tape. Every gate in `eval/gates/`
is affected.** Any arm that changes bare-tile count shifts the shop draw, so
"paired" seeds do not pair such arms: the reported `sd_delta` is honest
dispersion, not a variance-reduced pair sd, and effective power is below what
it implies. The shift is treatment-correlated but its per-seed direction is
essentially random, so it should behave as variance rather than bias at n=20+.

Filed separately; not fixed here.

## What this does not establish

- It does not separate *why* the crew shrinks from *that* it shrinks. Hire and
  land spend are now measured separately, but `hands_target` is a function of
  `active_tiles`, so the two are causally chained rather than independent.
- **It did not, and could not, clear the barnyard veto.** The `cost_side`
  /`revenue` split is about **seat 0**; `opponent_mean_delta` is about **seat
  1**. Establishing that our gain is cost-side is logically independent of
  whether the opponent was paid a price we lifted — and pointed at seat 1, this
  instrument says it partly was. The veto was resolved by re-measuring at n=64,
  not by this document.
- It says nothing about whether the saved cost beats the foregone revenue. The
  confirm gate answers that: `ci_lower` +5,991 to +7,780 on money across four
  tapes at n=64, and margin `ci_lower` positive on all four
  (+3,552 to +7,003), with 5–13/64 seeds regressing on margin against 2–7/64
  on money and a worst seed of −29,242.
