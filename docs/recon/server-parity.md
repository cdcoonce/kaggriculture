# Kaggriculture LOCAL vs SERVER Engine Parity — Findings

Replay: `probe-server-replay.json` (episode 90301508, both agents PASS-only, 720 steps)
Local engine: venv `kagg-venv`, `kaggle_environments` package, env `envs/kaggriculture/kaggriculture.py`
Scripts: `parity-check/common_checks.py`, `parity-check/check_replay.py`, `parity-check/check_local.py`
Raw output: `parity-check/replay_report.json`, `parity-check/local_report.json`

Methodology: the episode seed was treated as unknown. All checks below compare
**structure and deterministic law** (config, the price function, the town
consumption schedule, spawn/lock layout, reward wiring) rather than exact RNG
outcomes. A bonus exact-reproduction check is also reported (see end) since
`info.seed` turned out to be present in the replay's metadata, unscrubbed.

## 1. Engine metadata (verbatim)

| Field                                                              | Replay          | Local           |
| ------------------------------------------------------------------ | --------------- | --------------- |
| `module_version` (top-level)                                       | `1.32.4`        | —               |
| local `kaggle_environments` package version (`importlib.metadata`) | —               | `1.32.4`        |
| `version` (top-level, env spec version)                            | `0.1.0`         | —               |
| local `env.specification["version"]`                               | —               | `0.1.0`         |
| `name` / `env.specification["name"]`                               | `kaggriculture` | `kaggriculture` |

**MATCH.** Same package build, same env spec version.

## 2. Configuration parity

Replay `configuration` (15 keys) diffed key-by-key against `make("kaggriculture").configuration` defaults:

```
actTimeout: 1                  boardSize: 10                episodeSteps: 720
farmHandCostMult: 1            marketParams: {}              maxMarketOrdersPerTurn: 10
runTimeout: 1200               seed: null                    shedCapacity: 100
startingMoney: 3000            townCenterSellInterval: 12    townShopSellInterval: 4
townShopUnlockInterval: 3      turnsPerDay: 24                weedSpawnChance: 0.005
```

**0 of 15 keys differ.** Every value the server ran with is exactly the local package's default — the server did not pass any config overrides.

## 3. Price-function law (strongest seedless check)

For every step, recomputed each of the 9 products' price from the replay's
`market.inventory` using the **local** `market_price()` / `MARKET_PARAMS`
(base, I0=10000, T, below/above shape functions and targets, `round()` +
floor at 1), and compared to the replay's quoted `market.prices`.

- Steps with a market snapshot: 720/720
- Price points checked: **6,480** (720 steps × 9 products)
- **Mismatches: 0**

This validates base prices, I0, T, the below/above shape-function selection (linear/sq/sqrt/log per product), below/above targets, the amplitude derivation, rounding, and the price floor — all simultaneously, with zero deviation across the whole episode.

## 4. Town-consumption law

Both agents PASS every step (action `market` orders also empty — verified
below), so every market-inventory delta must come from town consumption
alone. Checked transitions between all 719 consecutive step pairs:

- Shop consumption: fires when `step % 4 == 0`; each currently-unlocked shop
  (from the town state visible in that step's observation) subtracts 1 unit
  from each product it sells, or 2 units if it's a single-product shop
  (`YARN_STORE`, `PET_CAFE`). **0 mismatches.**
- Town-center consumption: fires when `step % 12 == 0`; subtracts
  `center_mult` units from all 8 non-FERTILIZER products, where
  `center_mult` = 1 (day<10), 2 (10≤day<20), 4 (day≥20). **0 mismatches.**
- Shop-unlock cadence: unlock count only ever grows, by exactly 1, only at
  a day boundary where `next_day % 3 == 0`. **0 cadence violations** across
  all 6 shops that unlocked during the 30-day episode.

**Transitions checked: 719. Delta mismatches: 0. Unlock-cadence mismatches: 0.**

## 5. Structural spot-checks

| Check                              | Result                                                                                                                                                                                                                       |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Starting money both players = 3000 | MATCH (3000.0, 3000.0)                                                                                                                                                                                                       |
| Farmer spawn position both players | MATCH — both `[4,4]`, matching local `_default_spawn()` (first NWSE shed-access tile inside the always-unlocked NW quadrant, board_size=10 → half=5 → (4,4))                                                                 |
| Locked-quadrant layout at step 0   | MATCH — NW tiles `None` (unlocked/empty), NE/SW/SE tiles `"LOCKED"`, 0 mismatches across both farms' 100 tiles each                                                                                                          |
| Final rewards = final money        | MATCH — rewards `[3000.0, 3000.0]` = final `farms[*].money` `[3000.0, 3000.0]` (unchanged from starting money, correctly, since PASS-only actions and town consumption never touch the `money` field, only market inventory) |

## 6. Weed-boundary law

Because both agents PASS-only the whole episode, no `PLANT`/`WATER` actions
ever occur, so the only source of new `WEED` tiles is `_spawn_weeds()`
inside `_end_of_day` (tile-level RNG placement is unknowable without the
seed, but _timing_ is a hard law: it must only occur in the observation
immediately following a day boundary, i.e. at step index `s` where
`s % 24 == 0` and `s > 0`).

- Weed-spawn events observed: 6 (one small RNG-driven batch per day boundary that happened to roll a hit)
- Boundary violations: **0** — every single new-WEED tile transition landed exactly on a day-boundary step.

## 7. Local determinism cross-check (checker sanity guard)

Ran one local PASS-vs-PASS episode with the engine's own fresh random seed
(`info.seed = 398025338`, different from the replay's) through the **same**
check functions (`common_checks.py`), to rule out the check scripts
trivially passing regardless of input:

- Price law: 6,480 points checked, 0 mismatches
- Town law: 719 transitions, 0 delta mismatches, 0 unlock mismatches
- Structural checks: all pass (same invariants, same values — money/spawn/lock layout are seed-independent by design)
- Weed-boundary law: 5 events this run (different count than the replay's 6, as expected from a different seed), 0 boundary violations

Same laws hold, with a genuinely different RNG trace (different weed-spawn count) — confirms the checker distinguishes real trajectories rather than passing by construction.

## Bonus: exact-reproduction check (not part of the seedless methodology)

The replay's `info.seed` field was **not** scrubbed (`0`), even though
`configuration.seed` is `null` as designed (the engine's
`resolve_episode_seed()` intentionally clears it from `configuration` so
agents can't read it, but preserves it in `info` for replay reproducibility).
Since it was sitting there, I used it as a bonus, stronger check: ran
`make("kaggriculture", configuration={"seed": 0})` locally with PASS/PASS
agents and diffed **every field of every per-player observation** across
all 720 steps against the replay, byte-for-byte (JSON-normalized).

Result: **1,438 of 1,440 per-player-per-step observations differ in exactly
one field: `remainingOverageTime`** (real actTimeout/runTimeout compute-budget
bookkeeping, which depends on genuine wall-clock latency per Kaggle server
request — my local PASS agent calls are near-instant, so this field stays
near 60 instead of decaying like the server's did). Every other field —
`market.inventory`, `market.prices`, `town.unlocked_shops` (including which
specific shop unlocked and in what order), `farms[*].tiles` (including the
exact tile coordinates of every spawned weed), `farms[*].money`,
`farms[*].farmer`, `private.*`, `day`, `hour`, `step` — is **identical**.

Caveat: this bonus check relied on `info.seed` being present in the replay
metadata, which contradicts the "seed unknown" framing of the exercise —
treat it as a strong supplementary confirmation, not a substitute for the
seedless checks above (which stand on their own).

---

## PARITY VERDICT

**MATCHED (seedless, primary methodology):**

- Engine metadata: `module_version` 1.32.4 = local package 1.32.4; env spec version 0.1.0 = 0.1.0
- Configuration: 0/15 keys differ (server ran on unmodified local defaults)
- Price-function law: 0/6,480 mismatches across all 9 products, all 720 steps
- Town-consumption law: 0/719 transitions mismatched (shop ticks, town-center ticks with day-scaled multiplier, unlock cadence)
- Structural invariants: starting money, farmer spawn, locked-quadrant layout, final-reward-equals-money all match
- Weed-spawn timing law: 0/6 spawn events violate the day-boundary-only constraint
- Local determinism cross-check: identical laws hold on an independently-generated local trajectory (different seed), ruling out a checker bug as the explanation for zero mismatches

**MISMATCHED laws: none.**

**UNTESTABLE without the seed (by design of the seedless methodology):**

- Exact tile coordinates of weed spawns (only the _timing_ law is seedless-testable; _placement_ is RNG-dependent)
- Which specific shop unlocks at each unlock boundary (only the _cadence/count_ law is seedless-testable; shop _identity_ is `rng.choice()`-dependent)

**Overall verdict: PARITY CONFIRMED.** Every deterministic law and every
config value checked matches exactly, over the full 720-step episode, with
zero mismatches. The bonus exact-seed reproduction (info.seed=0) additionally
byte-matches the _entire_ trajectory including the two nominally
seed-dependent items above, with the sole difference being a real-time
compute-budget bookkeeping field unrelated to simulation logic. No evidence
of any local/server engine divergence was found.

**Single most important caveat:** all of this was validated on a **PASS-only
episode**. No PLANT/WATER/HIRE/BUY_LAND/market-order code paths were
exercised at all (0 non-PASS actions across all 1,440 agent-turns), so this
result says nothing about parity in `_apply_unit_action`, `_process_market`
(actual buy/sell order matching), farming/animal yield mechanics, hiring
costs, or land purchases — those remain unverified by this replay and would
need a replay (or local run) with real agent actions to check.
