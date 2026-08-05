# Kaggriculture Baseline Recon — 2026-08-04

Env: `kaggle_environments` (vendored in scratchpad venv), `kaggriculture` competition env.
Runner: `/private/tmp/.../scratchpad/kagg-venv/bin/python`, scripts under `scratchpad/recon-runs/`.

## 0. Timing

Single episode, starter vs random, 720 steps, seed=1: **0.987s wall clock**. All subsequent
5-episode-per-matchup batches ran in ~0.8-0.95s/episode — cheap enough to NOT need to reduce
episode counts. No batching constraints hit.

## 1. Matchup results (5 seeds each: 1,2,3,4,5; `configuration={"seed": N}`)

### starter vs random

| seed | money0 (starter) | money1 (random) | W/L/T  | seconds |
| ---- | ---------------- | --------------- | ------ | ------- |
| 1    | 3495             | 0               | P0 win | 0.92    |
| 2    | 3510             | 110             | P0 win | 0.88    |
| 3    | 3508             | 0               | P0 win | 0.94    |
| 4    | 3487             | 0               | P0 win | 0.89    |
| 5    | 3514             | 0               | P0 win | 0.92    |

Starter: mean 3503, min 3487, max 3514. Random: mean 22, min 0, max 110. **Starter wins 5/5.**
Random bankrupts itself almost every game (buys seeds/goes negative-adjacent and ends near $0);
it has no coherent sell loop.

### starter vs pass

| seed | money0 (starter) | money1 (pass) | W/L/T  | seconds |
| ---- | ---------------- | ------------- | ------ | ------- |
| 1    | 3491             | 3000          | P0 win | 0.84    |
| 2    | 3511             | 3000          | P0 win | 0.84    |
| 3    | 3487             | 3000          | P0 win | 0.88    |
| 4    | 3509             | 3000          | P0 win | 0.80    |
| 5    | 3487             | 3000          | P0 win | 0.83    |

Starter: mean 3497, min 3487, max 3511. Pass: exactly 3000 every game (starting money, untouched —
PASS with no market orders costs nothing). **Starter wins 5/5.** This means "do nothing" is a
perfectly stable, zero-cost baseline at exactly starting money — useful as a floor reference.

### starter vs starter (mirror)

| seed | money0 | money1 | W/L/T | seconds |
| ---- | ------ | ------ | ----- | ------- |
| 1    | 3495   | 3495   | Tie   | 0.82    |
| 2    | 3506   | 3506   | Tie   | 0.82    |
| 3    | 3499   | 3499   | Tie   | 0.84    |
| 4    | 3485   | 3485   | Tie   | 0.84    |
| 5    | 3493   | 3493   | Tie   | 0.82    |

Both sides: mean 3496, min 3485, max 3506. **5/5 exact ties** — money always identical to the
dollar across both players in every seed tested (see determinism note below for why).

**Takeaway on the starter baseline's ceiling:** over 720 steps / 30 days it nets roughly
+490 to +510 coins on top of the $3000 starting bank (~16-17% growth for the whole season),
using a single 5x5-quadrant tile and no land purchases, hires, animals, or fertilizer. This is a
very low bar — a competent agent that expands land, hires hands, and diversifies crops should
beat it by a wide margin. Random play is strictly worse than doing nothing (busts to near-zero).

## 2. Determinism check

Ran `starter vs starter`, seed=42, twice (`determinism_check.py`). Result:

- Run A: money0=3483, money1=3483
- Run B: money0=3483, money1=3483
- **Full step-by-step `farms` state compared at all 720 steps — zero divergence found anywhere**
  (not just final money; the entire per-step observation, including tile-level dicts, was
  byte-identical between runs).

Conclusion: **given an explicit `configuration={"seed": N}`, the environment is fully
deterministic end-to-end** (weed spawns, shop unlocks, town demand, market price drift all included)
for these built-in deterministic agents. The `"random"` agent is the only source of
nondeterminism observed, and that's from its own unseeded `random.Random()` instantiation inside
`random_agent`, not from the environment.

Side note from the mirror replay (see §4): although final money is identical across mirrored
starter agents, **the two players' tile grids are not necessarily identical mid-game** — e.g. at
step 360 (day 15, seed=7) player 1's tile (1,0) had spawned a WEED while player 0's had not, even
though both players run the identical starter policy under the identical global seed. Weed-spawn
RNG appears to be drawn independently per farm/player (not just once globally), so per-tile
board cosmetics can diverge between mirrored players even when the economically-relevant state
(bank balance, since starter only touches tile (4,4)) stays identical. This means bank-balance
determinism does NOT imply full board-state determinism is player-symmetric — it's just that
starter's strategy never looks at or is affected by any tile except its own farmer's square.

## 3. Starter agent strategy (source: `kaggriculture.py:1031-1060`, `starter_agent`)

Full logic, verbatim behavior:

- **Single-tile carrot loop.** Only ever acts on the tile under the main farmer's current position
  (which never moves — `farmer` action defaults to `["PASS"]` and no movement op is ever issued,
  so the farmer sits at spawn `(4,4)` — the shed-adjacent tile — for the entire game).
- **Build order:** none. Never buys land (`BUY_LAND`), never hires (`HIRE`), never builds
  coop/pasture, never buys animals, never fertilizes (`FERTILIZE`), never digs weeds (`DIG`).
- **What it plants:** CARROT only (`seed=$20`, `first_yield_day=2`, `max_yield_day=3`,
  `max_yield=4`, not ongoing). Buys 1 seed at a time whenever it holds zero carrot seeds and has
  ≥$20.
- **Care loop:** if standing on an empty tile and holding a seed → PLANT. If standing on its own
  growing carrot and age (`day - planted_day`) ≥ `max_yield_day` (3) → HARVEST. Otherwise, if not
  watered today → WATER. It waters every day the plant is alive and not yet harvestable, so it
  never suffers the 2-consecutive-missed-watering weed-conversion penalty.
- **Selling:** every turn, if shed holds any CARROT, sell the entire stack via `SELL`. No price
  awareness — sells immediately regardless of market price, one line item per turn (bounded only
  by `maxMarketOrdersPerTurn`=10, but it only ever issues at most 2 market orders/turn: one SELL,
  one BUY_SEED).
- **What it completely ignores:** the second, third, and fourth quadrant (`NE`/`SW`/`SE`, locked
  the whole game), farm hands (never hires any), all animals (goose/cow/sheep — no coop/pasture
  ever built), fertilizer (never applied, never collected even though its own carrot patch could
  produce it via nothing — fertilizer only comes from animals, which it never has), all other
  crops (wheat/tomato/strawberry/melon), the opponent's board entirely (no adversarial behavior —
  it's not even aware of `obs["farms"][1-player]`), and market price timing (always sells
  immediately rather than watching `market.prices.CARROT`).
- This is essentially the README's own "Wheat Loop" example pattern applied to Carrot: it's
  explicitly a minimal reference baseline, not a tuned strategy. There is enormous headroom above
  it (land, hands, animals, multi-crop diversification, price-aware selling/timing all untouched).

## 4. Money-over-time curve — starter vs starter mirror, seed=7

Sampled every 24 steps (once per in-game day) from `replay-starter-mirror.json`
(both players identical, since mirror match — starter's strategy is player/opponent-agnostic).

| day        | step | money (both players) | Δ from prior day |
| ---------- | ---- | -------------------- | ---------------- |
| 0          | 0    | 3000                 | —                |
| 1          | 24   | 2960                 | -40              |
| 2          | 48   | 2960                 | 0                |
| 3          | 72   | 2960                 | 0                |
| 4          | 96   | 2940                 | -20              |
| 5          | 120  | 3015                 | +75              |
| 6          | 144  | 3015                 | 0                |
| 7          | 168  | 2995                 | -20              |
| 8          | 192  | 3071                 | +76              |
| 9          | 216  | 3071                 | 0                |
| 10         | 240  | 3051                 | -20              |
| 11         | 264  | 3127                 | +76              |
| 12         | 288  | 3127                 | 0                |
| 13         | 312  | 3107                 | -20              |
| 14         | 336  | 3185                 | +78              |
| 15         | 360  | 3185                 | 0                |
| 16         | 384  | 3165                 | -20              |
| 17         | 408  | 3245                 | +80              |
| 18         | 432  | 3245                 | 0                |
| 19         | 456  | 3225                 | -20              |
| 20         | 480  | 3307                 | +82              |
| 21         | 504  | 3307                 | 0                |
| 22         | 528  | 3287                 | -20              |
| 23         | 552  | 3369                 | +82              |
| 24         | 576  | 3369                 | 0                |
| 25         | 600  | 3349                 | -20              |
| 26         | 624  | 3431                 | +82              |
| 27         | 648  | 3431                 | 0                |
| 28         | 672  | 3411                 | -20              |
| 29 (final) | 719  | 3495                 | +84              |

**Structure:** a clean repeating 3-day sawtooth — every 3rd day (harvest/sell day, sampled at the
day boundary right after) money jumps up (+75 to +84, growing slowly as CARROT's market price
rises with cumulative demand from town/shops depleting inventory), the next day is flat (0, no
new seed cost that day in this phase alignment), and the day after that dips -20 (net: -$20 seed
buy minus small friction, though seed cost is only $20 flat — the dip is exactly the seed cost).
Net trend is monotonically increasing and gently accelerating (early cycles ~+55/3-days net,
later cycles ~+62/3-days net) as the market carrot price drifts from $35 (I0 baseline) up toward
$40+ as cumulative sales draw down shared market inventory. No plateau or reversal by day 29 —
the curve is still climbing at game end, meaning starter's growth rate is bounded by its
single-tile throughput, not by the market saturating.

Full replay saved: `/private/tmp/.../scratchpad/recon-runs/replay-starter-mirror.json` (4.79MB, 720 steps).

## 5. Observation dict format

Confirmed against `AGENTS.md`'s documented schema — matches exactly, including field names,
nesting, and the private/public split. Full observation dumps written to
`scratchpad/recon-runs/obs_output.txt`.

**Step 0** (`player=0`, `day=0`, `hour=0`): both farms at `money=3000`, farmer at `[4,4]`,
`unlocked_quadrants=["NW"]` only, all tiles `None` (row 0 shown: `[None,None,None,None,None,
"LOCKED","LOCKED","LOCKED","LOCKED","LOCKED"]` — NW is the 5 unlocked columns, rest locked).
`private.seeds` and `private.shed` all zero. `market.inventory` flat at 10000 per product,
`market.prices` at documented base values (CARROT 35, WHEAT 25, TOMATO 60, STRAWBERRY 120,
MELON 250, EGG 50, MILK 160, WOOL 200, FERTILIZER 100). `town.unlocked_shops` empty.

**Step 360** (`day=15`, `hour=0`): money risen to 3185 both sides. `market.inventory` has drifted
down on every product (CARROT 9940, WHEAT 9834, MILK 9852, etc. — net consumption from town/shops
exceeding player sales) and `market.prices` risen correspondingly (CARROT 35→40, WHEAT 25→38,
MELON 250→283, MILK 160→266, WOOL 200→232 — premium/ongoing goods moved more than staples, as
documented). `town.unlocked_shops` now has 5 entries (`PIZZA_SHOP, BRUNCH_SPOT, SMOOTHIE_SHOP,
PET_CAFE, YARN_STORE`), consistent with `townShopUnlockInterval`=3 days having fired ~5 times by
day 15. Notably player 1's board shows a spontaneous `{"kind": "WEED"}` at tile (1,0) that
player 0's board doesn't have — see determinism note in §2.

No schema mismatches found; observation is exactly as documented in `AGENTS.md`.

## 6. Practical / API notes and surprises

- `kaggle_environments.make("kaggriculture", configuration={...}, debug=True)` + `env.run([a, b])`
  is synchronous, in-process, and returns after both agents finish 720 steps — no external
  process spawn overhead, hence the ~0.85-0.95s/episode speed. This is fast enough to run
  hundreds of episodes per minute; no need to reduce episode counts per matchup.
- `env.steps[-1][i].reward` is the final money for player `i` (float, e.g. `3495.0`) — same
  number as `farms[i]["money"]` at the final observation.
- Built-in agents are referenced purely by string name (`"starter"`, `"random"`, `"pass"`) — no
  import needed, resolved internally via the `agents = {"pass": pass_agent, "random":
random_agent, "starter": starter_agent}` dict at the bottom of `kaggriculture.py`.
- No warnings, deprecation notices, or errors emitted during any run (`debug=True` didn't surface
  anything beyond normal print/step behavior).
- `env.toJSON()` output is large — the single starter-mirror 720-step replay serialized to
  4.79MB of JSON. Budget for this if archiving many replays.
- The `"random"` agent instantiates its own `random.Random()` with no seed inside `random_agent`
  (kaggriculture.py:1005) — it is NOT controlled by `configuration.seed`. Only environment-level
  randomness (weed spawns, shop unlock selection, any RNG the engine itself owns) is seeded.
  This means starter-vs-random results will vary run-to-run even with the same `seed` in config —
  confirmed empirically isn't tested here directly but follows directly from the source; the 5
  starter-vs-random seeds above already show random's outcome varying (0, 110, 0, 0, 0) despite
  differing only in the seed value, consistent with random's unseeded internal RNG dominating its
  own variance rather than the configured seed doing so.
- `remainingOverageTime` field present in every observation (starts at 60) — presumably an
  agent-thinking-time budget field from the kaggle_environments framework, not documented in the
  kaggriculture AGENTS.md but harmless to ignore.
