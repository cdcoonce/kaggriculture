# Pre-registration: clone-aware premium-sale front-run

Date: 2026-09-07 America/Phoenix
Base: `2b0ab29324fca4e0ea4a36c9b86171b9242d61d6` (`main`).
Shipped-source comparator: `frozen:m3d_vst35_93e2913`, materialized from
`93e2913bd59e59bb2c08269b93823726d1872de7`.
Status: **REGISTERED — no implementation or outcome data observed.**

## Observed tactic and evidence boundary

Public replay analysis found convergence among five top agents on roughly the
same three-quadrant, 8-cow/5-sheep schedule. The strongest isolated reported
difference was market timing: selling one turn before an expected shared-market
dump produced 6-0 with mean margin +1,865.7, and the timing wrapper beat its
otherwise-identical base tape 14-2. These are public replay observations, not
source code. The hidden policy, memory, and causal contribution outside the
sampled tapes are unknown.

This experiment reconstructs one mechanism only: when both public farms are
near-clones and the opponent's public tiles expose imminent premium-product
harvest pressure, sell our already-shed stock of that product now, capped, even
if the ordinary batching/floor router would wait. It does not copy the common
herd/field layout, add strawberry, change cap=3, change HML20/VST35, or alter a
registered verdict.

## Implementation contract fixed before code

- New `PolicyConfig` boolean, default `False`; shipped behavior stays unchanged.
- Near-clone means equal unlocked-quadrant count and aggregate absolute
  difference <= 4 across public WHEAT/MELON/STRAWBERRY/COW/SHEEP tile counts.
- Pressure products are MELON, STRAWBERRY, MILK, and WOOL whose corresponding
  opponent crop/animal tiles already hold harvestable yield.
- A pressured product may bypass the ordinary satellite blocked-hour and price
  floor/peak wait, but retains its normal per-turn quantity cap.
- No prediction from opponent private shed, unit inventories, hidden state, or
  source is permitted; those are not observable in a live match.
- The bundle must remain import-clean, deterministic, and crash-free.

## Test-first behavioral gate

Before any local matchup:

1. default-off produces the same market orders as the shipped router;
2. a near-clone with public harvest pressure advances the matching capped sale;
3. a dissimilar opponent, empty opponent yield, or unrelated product does not;
4. malformed/missing opponent public state fails closed to shipped behavior;
5. full repository tests, Ruff, format, mypy, and rebuilt-bundle freshness pass.

Failure to establish any item closes the implementation before outcome data.

## Stage A — selection against exact shipped default

- Opponent: `frozen:m3d_vst35_93e2913`.
- Band: **843000**.
- Size: n=100 seeds / 200 games, both seats.
- Candidate: tactic enabled; all other defaults unchanged.
- Instrument: `harness.promotion_gate`, with committed ledger.

**INVALID** on any candidate crash, wrong opponent/config/band, fewer than 200
games, or failure to play both seats.

**ALIVE** only if rate >= 0.60 and Wilson lower > 0.50. Otherwise **CLOSED**;
no confirmation, alternate similarity threshold, product subset, or band reuse.

## Stage B — confirmation and live-submission guards

Runs only if Stage A is ALIVE.

Primary confirmation:

- Opponent `frozen:m3d_vst35_93e2913`;
- band **844000**, n=250 / 500 games, both seats;
- **CONFIRMED** only if rate >= 0.65, Wilson lower > 0.55, and no crashes.

If primary confirmation passes, run two disjoint robustness guards:

- exact live M3b source `b6ce655a6b011905d7560b0a48f640dab485a84d`,
  band **845000**, n=100 / 200 games;
- exact live M3a source `48487b6`, band **846000**, n=100 / 200 games.

Each guard requires rate >= 0.90 and no candidate crashes. Either failure makes
the overall verdict **NOT PROMOTED**. These guards are regression checks, not
claims that local rates calibrate to live-field Elo.

## Stage A result

Stage A ran after the registration and implementation commits on the fixed
band 843000 against `frozen:m3d_vst35_93e2913`, with
`{"clone_front_run": true}` and candidate source
`77c8f0106d0bb8c7d22dfb535bca7837e42f8937`.

- Record: 165-35-0 over 200 games (both seats), rate 0.825.
- Wilson lower bound: 0.7663556880107202.
- Candidate crashes: none.
- Ledger: `eval/gates/2026-09-08T01-02-18Z-champion-vs-frozen_m3d_vst35_93e2913-promotion.json`.
- Registered verdict: **ALIVE** (`0.825 >= 0.60` and `0.7664 > 0.50`).

The generic CLI printed `PASS` because its configured lower-bound threshold was
0.50; the registered point-rate criterion above is independently satisfied.
Per the prospective protocol, Stage B is now eligible to run unchanged.

## Consequence

Only all-green Stage B evidence can recommend making the tactic a source
default. It does not authorize merging that change or uploading a Kaggle
submission. Any failed registered criterion is append-only and final for this
intervention.
