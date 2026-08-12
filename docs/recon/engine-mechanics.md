# Kaggriculture — Ground-Truth Engine Mechanics

Source of truth: `kaggriculture.py` (1063 lines), `kaggriculture.json` (spec), plus
`kaggle_environments/core.py`, `agent.py`, `utils.py`, `schemas.json` for the
runner/timeout/validation layer. All line numbers below are against
`kaggle_environments/envs/kaggriculture/kaggriculture.py` unless another file is named.
Package version installed: whatever `pip install -U kaggle-environments` resolved to at
recon time (no version pin found in the venv metadata checked); read the file yourself
before relying on line numbers if you upgrade the package.

The bundled `AGENTS.md`/`README.md` in this env directory are **unusually accurate** —
they read like they were generated from (or kept in lockstep with) the code, not
marketing copy. Discrepancies found below are mostly _omissions_ (mechanics the code
enforces that the docs never mention), not contradictions. Flagged explicitly where a
doc claim is wrong or misleading.

---

## 1. Turn processing order (as implemented)

Actual order inside `interpreter()` (lines 871–942), per call to `env.step()`:

1. **Framework-level action ingestion** (`core.py` `Environment.step`, lines 256–293,
   _before_ the kaggriculture interpreter ever runs): each agent's returned action is
   checked for `DeadlineExceeded`/`BaseException`/schema-invalid and given a
   `status` (`TIMEOUT`/`ERROR`/`INVALID`) accordingly; a valid dict action is merged with
   defaults (see §2) and passed through.
2. **Farmer + hand unit actions, per player, farmer first** (lines 890–916). For each
   player: an atomic PLANT-oversubscription check runs against the seed count _as it
   stood at the start of this turn_ (before any market orders this turn resolve — see
   the sequencing gotcha below), then `_apply_unit_action` runs for the farmer (idx 0),
   then each hand in list order (idx 1, 2, …). **Units of the same player are applied
   sequentially, not simultaneously** — a farmer's DIG/DROP/HARVEST this turn is visible
   to that player's own hand's action later in the same turn (shared mutable
   `farm`/`private` dicts, no double-buffering). The two players' farmer/hand loops
   themselves are also sequential (player 0 fully, then player 1 fully) but this
   doesn't matter since each player only touches their own `farm`/`private`.
3. **`_process_market(state, env)`** (line 918) — resolves **both players'** market
   queues together, per-unit lockstep (§3). This is the only cross-player-interaction
   point in a turn.
4. **`_town_consume(env, state, step)`** (line 919) — town center / shop consumption,
   strictly _after_ the full market resolution for both players, never interleaved with
   it.
5. **`_decay_plants`** for both farms (lines 920–921) — post-max-lifespan yield decay.
6. **`_end_of_day`** (lines 922–923) — only on the last turn of a day
   (`(step+1) % turns_per_day == 0`); this still happens _after_ steps 2–5 have already
   run for that final turn, so the last turn of the day gets full market/town/decay
   processing before the day-refresh reset fires.
7. Step/day/hour counters advance and are broadcast (lines 925–933).
8. Terminal check (lines 936–940): `if step >= cfg.episodeSteps - 2: status="DONE"` for
   **all** players (regardless of prior status) and `reward = current money` — see §2 for
   why this matters for crashed/timed-out agents.

**Sequencing consequences worth knowing:**

- **BUY_SEED this turn does not unlock PLANT this turn.** Unit actions (step 2) are
  applied strictly before market orders (step 3) resolve, so a `PLANT` in the same
  turn's `farmer`/`hands` action is checked against the seed count _before_ that same
  turn's `BUY_SEED` lands. A naive agent that does `{"farmer": ["PLANT", "WHEAT"],
"market": [["BUY_SEED","WHEAT",1]]}` in one call gets a **silent no-op PLANT** every
  time; the seed only becomes usable next turn. This matches the documented order
  ("player actions" before "market actions") but is easy to miss when writing an agent.
- **Town consumption can never be sandwiched within a single turn** — it always runs
  once, after the _entire_ market queue for both players resolves. But because town
  ticks happen exactly every `townShopSellInterval`/`townCenterSellInterval` steps, and
  a town tick pulls inventory down (raising price via scarcity, since price rises as
  `inventory < I0`), the turn _immediately after_ a tick is the highest-price window
  for that tick's affected products until someone sells into it. This is a legitimate,
  code-verified timing lever, not documented explicitly anywhere (see Exploit
  Candidates).
- The final-2-steps `status = "DONE"` overwrite (line 938) is unconditional per agent —
  it fires even for an agent whose status had gone ERROR/TIMEOUT/INVALID mid-game. This
  is what saves a crashed agent's final reward from being nulled out (§2).

---

## 2. Action grammar & validation leniency

**Two layers of validation exist, and they behave very differently:**

### Framework layer (`core.py`, outside kaggriculture's control)

- `action` schema in `kaggriculture.json` (line 130-134) is `{"type": "object",
"default": {...}}` with **no nested property constraints at all**. Any dict, no matter
  what's inside `farmer`/`hands`/`market`, passes framework-level `jsonschema.validate`.
  Missing top-level keys (`farmer`, `hands`, `market`) are backfilled from the literal
  default dict (`utils.py` `default_schema`, lines 150–169) — e.g. an agent that forgets
  to return `"market"` silently gets `[]`.
- The **only** way to get framework-level `status="INVALID"` is to return something that
  isn't a dict at all (a list, string, `None`, etc. — fails `type: object`).
- If the agent function **raises**, `agent.py` `Agent.act` (lines 190–195) catches the
  exception, and `core.py` `step()` (lines 279–284) sets `status="ERROR"`.
- If the agent takes longer than `actTimeout` (1s per `kaggriculture.json`) **and** has
  exhausted its banked `remainingOverageTime` (starts at 60s, per-agent, not shared;
  `kaggriculture.json` line 128 overrides the base-schema default of 12s — `agent.py`
  line 220), the action becomes `DeadlineExceeded()` → `status="TIMEOUT"`.
  **There is no hard kill/interrupt** for a truly-hung agent (no signal-based or
  subprocess timeout is used) — `agent.act` just calls the function and waits for it to
  return; an infinite loop blocks the run indefinitely rather than being timed out.
- **Once a player's status becomes non-ACTIVE (ERROR/TIMEOUT/INVALID), `act_agent`
  (`core.py` line 173–180) never calls that agent's function again** — every future turn
  it silently substitutes the default action `{"farmer":["PASS"],"hands":[],"market":[]}`
  (via the same top-level-default backfill in §2's framework layer, since the "action"
  submitted is `None`). Status is **sticky**: `step()` copies forward the previous
  status (`{**self.state[index], "action": None}`, line 277) and nothing in
  kaggriculture.py resets it mid-game.
- `core.py` `__loop_through_interpreter` (line 636–637) forces `reward = None` on every
  step where `status in ["ERROR","INVALID","TIMEOUT"]`. **This does not zero out your
  final score**, though, because kaggriculture's own terminal-step code (§1 step 8)
  unconditionally overwrites `status → "DONE"` and `reward → current money` for
  **every** player in the last 2 recorded steps, regardless of what their status was
  before. Net effect: **a crash/timeout/malformed-action freezes your farm (defaults to
  PASS forever, tiles decay to weeds within 2 days, animals escape within 2 days, no
  further buys/sells) but your final reward is your frozen money at the moment of the
  crash, not `None` and not zero.** This is a real risk (you stop earning while the
  opponent keeps playing) but not an instant, total loss — worth confirming precisely
  because a naive read of the `reward=None` line could lead you to over- or
  under-estimate crash severity.
- The competition's live infra (Kaggle servers) may impose stricter timeouts than the
  local `kaggle_environments` defaults shown here (`actTimeout`/`runTimeout` are almost
  certainly reconfigured server-side); treat the 1s/60s numbers as what the **local**
  package enforces, not necessarily production.

### kaggriculture interpreter layer (inside `_apply_unit_action`, `_parse_order`, `_commit_unit`)

- Every single op is validated inline and **silently no-ops** on any illegal condition —
  malformed op names, wrong arg counts/types, insufficient funds/inventory, acting on a
  locked tile, acting on the wrong tile type, etc. There is no error signal, no partial
  effect beyond what explicitly succeeded, and no way for an agent to crash the episode
  through illegal in-game moves (only a genuine Python exception or non-dict return
  value can do that, both under the agent's own control).
- `PLANT` has one atomic-batch rule: total `PLANT <crop>` requests across
  farmer+hands for a player this turn are compared to the seed count once; if demand
  exceeds supply, **every** PLANT request for that crop this turn is replaced with
  `["PASS"]` (lines 897–916) — matches the doc's "if you try to plant too many, none are
  planted."
- Market order parsing (`_parse_order`, lines 608–626): `n <= 0` voids the whole order;
  non-int `n` voids the whole order; unknown op voids the order; a `SELL`/`BUY_*` order
  for an unhandled item (e.g. `BUY_PRODUCT` on anything but WHEAT/FERTILIZER) is aborted
  **for that queue slot only**, not retried — the remaining requested quantity is lost,
  not deferred.
- `maxMarketOrdersPerTurn` (default 10) truncates the queue with a plain Python slice
  (`q[:max_orders]`, line 537) — silent drop of extras, no error.

---

## 3. Market implementation

### `MARKET_PARAMS` (lines 41–51) — dumped verbatim:

| Item       | base | I0    | T   | below_func | below_target | above_func | above_target |
| ---------- | ---- | ----- | --- | ---------- | ------------ | ---------- | ------------ |
| WHEAT      | 25   | 10000 | 400 | sqrt       | 0.80         | log        | 0.20         |
| CARROT     | 35   | 10000 | 450 | log        | 0.20         | sqrt       | 0.70         |
| TOMATO     | 60   | 10000 | 200 | linear     | 0.40         | sqrt       | 0.60         |
| STRAWBERRY | 120  | 10000 | 100 | sqrt       | 0.70         | linear     | 1.60         |
| MELON      | 250  | 10000 | 300 | log        | 0.20         | sq         | 3.60         |
| EGG        | 50   | 10000 | 332 | linear     | 0.40         | log        | 0.20         |
| MILK       | 160  | 10000 | 122 | sqrt       | 0.60         | linear     | 1.60         |
| WOOL       | 200  | 10000 | 105 | log        | 0.20         | sq         | 3.20         |
| FERTILIZER | 100  | 10000 | 200 | linear     | 0.40         | linear     | 0.40         |

`PRICE_FLOOR = 1` (line 39). Every product/animal-product/fertilizer starts at market
inventory `I0 = 10000` (line 38, `_new_market`).

### Price function (`market_price`, lines 178–192)

```
if inv < I0:  f = below_func;  amp = below_target * base / f(T);  price = base + amp * f(I0 - inv)
else:         f = above_func;  amp = above_target * base / f(T);  price = base - amp * f(inv - I0)
price = max(1, round(price))
```

`f`: `linear=x`, `sq=x*x`, `sqrt=sqrt(x)`, `log=ln(1+x)`, `log10=log10(1+x)` (lines 54–61).
`amp` is derived, never stored. Per-resource overrides can be injected via
`configuration.marketParams` (sparse merge, `_resolve_market_params`, lines 64–72),
patching any subset of the 6 curve params per item — useful for building a local test
harness that stress-tests strategies against a deliberately softened/hardened market.

**Reachability note (not in docs):** the log-shaped `above_func` on WHEAT makes it
essentially glut-proof — solving `price(inv)=1` for wheat's curve requires inventory on
the order of `e^29` units above I0, physically unreachable in a 720-turn game. FERTILIZER's
linear above-curve, by contrast, hits the $1 floor at only ~495 units of net oversupply
above I0 (`amp = 0.4*100/200 = 0.2`; `100 - 0.2*x = 1 → x ≈ 495`), which **is** reachable
late-game from two players' worth of daily animal fertilizer collection. See Exploit
Candidates.

### One-unit-at-a-time concurrent interleaving (`_process_market`, lines 521–605)

- Queues are truncated to `maxMarketOrdersPerTurn` per player (line 537), then walked by
  **queue-slot index**, not by item: `for i in range(max_len)` where `max_len` is the
  longer of the two players' (truncated) queue lengths (line 539).
- At each slot index `i`, `HIRE`/`BUY_LAND` (atomic, non-quantity orders) are resolved
  once immediately, in player order 0-then-1 (lines 549–558), independent of any
  SELL/BUY at that same slot — no interaction with market inventory.
- Remaining SELL/BUY_PRODUCT/BUY_SEED/BUY_ANIMAL orders at that slot enter a **per-unit
  while-loop** (lines 561–605): each iteration, both players' _current_ price is quoted
  simultaneously off the _same_ live `market["inventory"]` snapshot (lines 567–585,
  `quoted[player_id]` computed for both before either commits) — this is what makes it
  "concurrent": neither player's price is affected by the other's commit for that same
  unit. Commits then happen sequentially in player order (lines 591–603), each mutating
  `market["inventory"]`, which _does_ feed into the price quoted for the _next_ unit in
  the while-loop (both players', symmetric). `market["prices"]` (the cached, agent-visible
  field) is only refreshed once per queue-slot-index, after its while-loop fully drains
  (line 605), not after every micro-unit.
- A player order that fails to commit (insufficient funds/inventory/shed room) is
  dropped entirely for the rest of that slot (`order_states[player_id] = None`, line 600) — it does not carry over to the next slot index; whatever quantity was
  unfulfilled is simply lost, not retried.
- Runaway-loop guard: 100,000 iterations max per slot (lines 562–566), prints a warning
  and aborts — never realistically hit given `maxMarketOrdersPerTurn` and real
  affordability limits, but note there's **no upper bound on the `n` an agent can
  request** in a single order (`_parse_order` only checks `n > 0`), so an agent
  requesting `["SELL","WHEAT",999999999]` is legal syntax; it just terminates early once
  the shed/money runs out.

### Buy vs sell quoting (asymmetric, deliberately — line 202, README)

- `SELL`: quoted at **pre-sale** inventory (`market_price(item, market["inventory"][item], ...)`, line 574).
- `BUY_PRODUCT`: quoted at **post-buy** inventory
  (`market_price(item, market["inventory"][item] - 1, ...)`, line 578) — so a same-price
  buy-then-sell round trip against an otherwise-static market nets exactly $0, as
  documented.
- `BUY_SEED`/`BUY_ANIMAL` are **fixed-price**, not inventory-driven at all — flat
  `CROPS[item]["seed"]` / `ANIMALS[item]["cost"]` (lines 579–582).

### $1 floor asymmetry (real, code-verified, undocumented consequence)

- `_commit_unit` SELL branch (lines 630–638): `if price > 1: market["inventory"][item]
+= 1` — a sale executed _at_ the $1 floor does **not** increment market inventory.
  Selling into an already-floored market is therefore a strict, side-effect-free $1/unit
  income floor: it neither drives the price further down (impossible, already floored)
  nor makes recovery any slower (since it doesn't add supply).
- `_commit_unit` BUY_PRODUCT branch (lines 639–649) has **no equivalent floor
  protection** — `market["inventory"][item] -= 1` unconditionally, even from a floored
  glut. This means buying WHEAT/FERTILIZER while the market is glutted (cheap, near the
  floor) actively drains inventory back toward `I0`, which is the _only_ lever (besides
  town consumption) that raises a crashed price back up. See Exploit Candidates.

### What `BUY_PRODUCT` allows

Only `WHEAT` and `FERTILIZER` (line 575, `item in ("WHEAT", "FERTILIZER")`). Every other
harvestable/product (`CARROT, TOMATO, STRAWBERRY, MELON, EGG, MILK, WOOL`) can only be
`SELL`'d, never bought back. **`GOOSE`/`COW`/`SHEEP` (the animals themselves) are not in
`PRODUCTS` at all (line 25) and cannot be `SELL`'d either** — see Exploit Candidates for
why this is a real footgun.

---

## 4. Crop and animal parameters (as implemented)

### `CROPS` (lines 12–17)

| Crop       | seed$ | first_yield_day | max_yield_day | interval | max_yield | ongoing |
| ---------- | ----- | --------------- | ------------- | -------- | --------- | ------- |
| WHEAT      | 10    | 2               | 4             | 0        | 6         | False   |
| CARROT     | 20    | 2               | 3             | 0        | 4         | False   |
| TOMATO     | 50    | 8               | 8             | 1        | 4         | True    |
| STRAWBERRY | 100   | 10              | 10            | 2        | 4         | True    |
| MELON      | 80    | 10              | 12            | 0        | 6         | False   |

Code matches the README's Object Types table exactly, including the README's own
correction notes (e.g. wheat/carrot only reach their listed max with fertilizer; melon's
ages 11–12 add nothing because base+per-watered-day hits the cap of 6 at age 10). Traced
and confirmed in code:

- **One-time crop yield (`_apply_unit_action` WATER branch, lines 375–388):**
  `_new_plant` starts `yield_units = 1` (base, line 209). Each `WATER` op, while
  `window_start <= age_days <= max_yield_day` where `window_start = ceil(max_yield_day/2)`
  (integer form `(max_yield_day+1)//2`, line 384), adds `+1` (or `+2` if
  `fertilized_until_day >= day`) to `yield_units`, capped at `max_yield`. Watering
  outside the window, or a second watering the same day (`watered_today` already True),
  is a no-op (but `watered_today` is still set True on the _first_ watering of the day
  regardless of window, since that flag also gates the weed-prevention check).
- **Ongoing crop yield (`_daily_refresh_plants`, lines 747–780):** production is
  schedule-driven, **not gated on same-day watering** — `days_since_first % interval ==
0` fires the tick regardless of whether the plant was watered that day; only the
  _magnitude_ depends on watering (`+1` base, `+2` if `fertilized_until_day >= current_day
and was_watered`). Watering is still mandatory to avoid the 2-consecutive-unwatered-day
  weed conversion, but **that check only requires watering every other day, not daily**
  (see §7 for the exploitable action-economy consequence).
- **Decay** (`_decay_plants`, lines 730–744): once `step >= max_lifespan_step`, on every
  step where `(step - max_lifespan_step) % 2 == 0` (i.e. starting _immediately_ at
  `max_lifespan_step` itself, then every other step), `yield_units -= 1`; hits 0 → tile
  becomes `{"kind": "WEED"}`. One-time crops set `max_lifespan_step` at plant time
  (`(planted_day + max_yield_day + 1) * turns_per_day`, line 210). Ongoing crops only get
  a `max_lifespan_step` assigned the day their cumulative `production_count` first
  reaches `max_yield` (line 779–780: `(next_day + 1) * turns_per_day`) — an ongoing crop
  that never reaches its production cap (e.g. neglected/under-watered so it weeds out
  first) never enters this decay path at all, it just weeds out via the
  2-unwatered-days rule instead.

### `ANIMALS` (lines 19–23)

| Animal | cost | structure | first_yield_day | interval | max_held | product |
| ------ | ---- | --------- | --------------- | -------- | -------- | ------- |
| GOOSE  | 300  | COOP      | 4               | 1        | 4        | EGG     |
| COW    | 400  | PASTURE   | 8               | 2        | 6        | MILK    |
| SHEEP  | 500  | PASTURE   | 6               | 3        | 6        | WOOL    |

- **Feeding** (`FEED` op, lines 482–490): flat cost 1 WHEAT from the acting unit's own
  inventory (must be `PICKUP`'d from shed first — wheat never auto-transfers), once per
  day per animal.
- **Escape rule** (`_daily_refresh_animals`, lines 783–811): `consecutive_unfed` starts
  at 0 on placement (survives its first unfed day), increments if not fed that day,
  resets to 0 if fed; `>= 2` → animal escapes, **structure remains** (reverts to bare
  `{"kind": structure}`, i.e. you keep the coop/pasture, just lose the animal and any
  banked yield/care state).
- **Production**: on `days_since_first % interval == 0` (where `days_since_first =
next_day - placed_day - first_yield_day`), base `+1` regardless of fed status that
  day, plus the banked `pending_care_bonus` **only if fed that day** (popped and zeroed
  either way once a production day is reached — see §7 for the silent-overflow trap).
  `yield_units` capped at `max_held`.
- **`fertilizer_available`** (line 809) is set `True` unconditionally at end of day for
  **every surviving animal**, independent of `fed_today`/`cared_today` — this is a
  genuinely free, feed-decoupled resource, confirmed in code exactly as the README
  states ("whether or not it was fed or cared for").
- `COLLECT_FERTILIZER` (lines 492–499) adds 1 `FERTILIZER` straight to the collecting
  unit's own field inventory (not the shed).

---

## 5. RNG

Exactly two RNG call sites, both inside `_end_of_day` (lines 838–868), both driven by a
single `random.Random` instance re-seeded fresh **every day**:

```python
seed = env.info.get("seed", 0)
rng = random.Random((seed * 1_000_003) ^ day)          # line 848-849
```

- **Weed spawning** (`_spawn_weeds`, lines 814–818): one `rng.random() < weed_chance`
  roll per empty-and-unlocked tile, iterated **per player, in player-index order** inside
  the same `for player_id, farm in enumerate(obs0.farms)` loop that also does
  `_daily_refresh_plants`/`_daily_refresh_animals`/inventory-drop (lines 851–860). Both
  players draw from the _same continuing stream_ for that day (player 0 consumes the
  first `board_size²` draws, player 1 the next `board_size²`) — the draws are **not
  mirrored/identical between players**, but both are equally "fair" samples from a
  deterministic-given-seed stream. Re-running with the same `seed` config value
  reproduces identical weed patterns for both players, useful for local regression
  testing of an agent against a fixed board.
- **Shop unlock choice** (lines 862–868): `rng.choice(sorted(remaining))` — one draw from
  the _same_ per-day `rng` instance, **after** both players' weed rolls for that day.
  There is exactly one shared `town` state, so this is inherently symmetric (no
  per-player draw needed).

**Episode seed resolution** (`resolve_episode_seed`, `utils.py` lines 199–…, called once
at `_initialize`, line 235): sourced from `env.info["seed"]` if already set, else
`configuration["seed"]` if the caller supplied one, else a fresh random 31-bit int; the
resolved value is written to `env.info["seed"]` (persists into the replay JSON, visible
post-hoc) and **cleared from `configuration`** so agents cannot read it from their
observation.

**Game is symmetric by construction beyond the RNG:** starting money, starting farm
layout (`_initial_tile`/`_default_spawn`, lines 143–152 — both players' farmer spawns
at the first NW shed-access tile, board indices identical for both since each player has
their own independent `board_size × board_size` grid, not a shared board), land-unlock
order/prices (`LAND_ORDER`, `LAND_PRICES`, fixed), hire-cost formula, and market curve
are all identical and independent per player. The only asymmetry any single episode can
produce is the specific tile-by-tile weed pattern (statistically fair, not literally
identical) and the shared shop-unlock order (identical exposure to both, since it's one
shared `town`). **No RNG touches the market price function itself, item availability, or
combat/interaction outcomes** — the market is fully deterministic given both players'
actions.

---

## 6. Timeouts and agent interface

- **Call signature**: `Agent.act` (`agent.py` lines 168–224) calls
  `self.agent(*args[:agent.__code__.co_argcount])` — so an agent function can declare
  `def agent(obs)` or `def agent(obs, config)`; the runner introspects arity via
  `__code__.co_argcount` and passes only as many positional args as declared. Both
  `obs` and `config` are passed as `structify`'d objects (dict access **and**
  attribute access both work, e.g. `obs["farms"]` and `obs.farms` are equivalent —
  README's example code uses dict-style throughout).
- **Observation construction** (`core.py` `__get_shared_state`, lines 754–768): built
  per-player each step from `state[0]` (the canonical/shared copy) merged with that
  player's own `state[position]` for non-shared fields, per the `shared:true/false`
  flags declared in `kaggriculture.json`'s `observation` block. `farms`, `market`,
  `town`, `day`, `hour`, `step` are `shared:true` (both players see identical values,
  including the **opponent's** `farms[opponent_idx]` entry — full visibility into
  opponent's tiles/money/farmer position/hand count/unlocked quadrants/`hires_today`).
  `player` and `private` are per-agent only.
- **Timing**: `actTimeout=1` second per turn (`kaggriculture.json` line 9),
  `remainingOverageTime` starts at 60s **per agent, not shared/pooled**
  (`kaggriculture.json` line 128, overriding the base schema's default of 12).
  `agent.py` line 220: `if duration - actTimeout > remainingOverageTime: action =
DeadlineExceeded()`. This is a chess-clock model — occasional slow turns are fine as
  long as cumulative overage across the whole 720-turn game stays under budget; there is
  no per-turn hard cap beyond that budget, and (per §2) **no forcible interrupt of a
  hung agent** — a true infinite loop stalls the entire run rather than timing out
  gracefully, since `agent.act` just calls and waits.
- **Exception handling**: caught in `agent.py` (lines 190–195), turned into
  `status="ERROR"` in `core.py`. **Never propagates to crash the environment or the
  other agent's turn** — confirmed sticky-PASS-forever behavior as described in §2.
- **`env.run(agents)`** (`core.py` lines 307–334) additionally enforces a whole-episode
  `runTimeout` (base-schema default 1200s / 20 min — not overridden by
  `kaggriculture.json`) across the local wall-clock run; exceeding it raises
  `DeadlineExceeded` at the `env.run()` call level, distinct from per-agent per-turn
  timeouts. This is a **local package default**; production Kaggle infra almost
  certainly enforces its own (undocumented here) limits.
- Multiprocessing: if every agent is `is_parallelizable` (true for file/URL agents, false
  for bare Python callables per `build_agent`, `agent.py` line 166), `core.py` uses a
  `multiprocessing.Pool` to call both agents' `act()` concurrently (line 740–743);
  otherwise it falls back to sequential `map()`. This only affects wall-clock speed of
  local testing, not game semantics.

---

## 7. Exploit / quirk candidates (read adversarially)

Ranked roughly by expected practical value.

1. **Fertilizer-market crash → cheap buyback (real, quantified).** `FERTILIZER` is one
   of only two `BUY_PRODUCT`-able goods and uses a _linear_ above-`I0` curve
   (`above_target=0.40`, `T=200` → `amp=0.2`), meaning only **~495 units of net
   oversupply** above `I0` crashes it to the $1 floor
   (`100 - 0.2·x = 1 → x ≈ 495`; lines 41–51, 178–192). Fertilizer is produced as a
   **free byproduct** of every surviving animal (line 809, no feed/care requirement),
   so a game with several animals per player over 30 days plausibly accumulates
   hundreds of units sold to the shared market late-game. Once floored, `BUY_PRODUCT
   FERTILIZER` (line 639–649) is **not** floor-protected on the inventory side (unlike
   `SELL`, lines 630–638) — buying at the floor actively pulls inventory back toward
   `I0`. Net: a player who tracks the shared market inventory can buy large amounts of
   fertilizer near $1/unit (vs. its $100 base) once the market gluts, then `FERTILIZE`
   every crop for the 2× yield bonus at a fraction of intended cost. This is a legitimate
   in-game read of a shared, visible signal (`market.inventory.FERTILIZER`,
   `market.prices.FERTILIZER`) — not a bug per se, but a real, code-verified,
   quantifiable edge that the docs never call out (they only describe fertilizer's curve
   parameters, not its reachability or the buy-side floor asymmetry).

2. **Stranded animals — no resale market (real footgun, likely undocumented pitfall).**
   `PRODUCTS` (line 25) — the only sellable-item whitelist — does **not** include
   `GOOSE`/`COW`/`SHEEP`. `BUY_ANIMAL` deposits the animal into `private["shed"]` under
   its own name (line 662, `_commit_unit`). There is **no code path** that ever removes
   an animal from the shed except `PLACE` onto a matching, empty, already-built
   structure (lines 449–462). Buying an animal before its structure is built, buying
   more animals than you have empty structures for, or simply mis-managing shed capacity
   (animals count toward the 100-item `shedCapacity` cap like anything else, line 659) **permanently strands that $300–500** with zero recovery mechanism. Nothing in
   the README explicitly warns that animals are non-refundable/non-resellable; it's only
   inferable from the `PRODUCTS` constant. High blast-radius mistake for a naive
   agent that queues `BUY_ANIMAL` speculatively.

3. **Town-tick price-timing arbitrage.** Town consumption (`_town_consume`, lines
   705–727) always runs strictly after both players' market queues resolve for a turn
   (§1), and pulls inventory down (raising price via scarcity) exactly every
   `townShopSellInterval`(4)/`townCenterSellInterval`(12) steps — 12 is a multiple of 4,
   so both fire together every 12 steps. Selling in bulk specifically on the turn
   immediately following a shared tick captures the freshest scarcity premium before
   anyone's own selling (or the opponent's) drives it back down; the market has **no
   automatic mean reversion** absent town consumption or `BUY_PRODUCT` — prices only
   move in response to explicit inventory changes (lines 630–664), so a price can sit
   depressed indefinitely if nobody buys/town doesn't demand it. Symmetric opportunity
   for both players (no player-order bias — quoting within a shared micro-round is
   simultaneous, §3), but exploitable by whichever agent actually times its dumps
   around the schedule vs. one that sells reactively every turn (e.g. `starter`, §8,
   which dumps the instant anything lands in shed).

4. **CARE-bonus silent overflow discard.** `pending_care_bonus` is only capped
   _indirectly_ by `max_held` at payout time (`_daily_refresh_animals`, lines 799–808):
   `tile["yield_units"] = min(max_held, yield_units + base + bonus)`, then
   `pending_care_bonus` is unconditionally reset to 0 (line 806) — any banked bonus
   beyond what fits under `max_held` is **silently discarded**, not carried forward.
   An agent that bulk-cares for many days without harvesting between production ticks
   wastes the excess. Also: skipping `FEED` on a day that happens to coincide with a
   scheduled production day **zeroes the entire bank** (not just that day's increment,
   per lines 804/806) even though it only costs 1 wheat to have avoided — a
   wheat-saving "feed every other day" strategy (viable for yield itself, §7.5) must
   special-case never-skip on scheduled production days if it wants to preserve CARE
   banking.

5. **Ongoing crops (TOMATO/STRAWBERRY) don't need daily watering for base yield —
   only for weed-prevention, and that only needs every-other-day.** Confirmed in
   `_daily_refresh_plants` (lines 747–780): scheduled production is gated on
   `days_since_first % interval == 0` only, never on `was_watered`; watering only
   affects whether the fertilizer-doubling applies that tick, and separately whether
   `consecutive_unwatered` resets (weed-prevention). This matches what the README
   already states plainly ("minimum of every other day") but is easy to under-use:
   a hand assigned to babysit an ongoing crop only strictly needs to visit every other
   day, freeing action-economy for other tiles the other days — worth encoding directly
   rather than re-deriving from the table.

6. **Fertilizer re-application waste (minor, no in-game warning).** `FERTILIZE`
   (lines 419–426) sets `fertilized_until_day = max(existing, day+2)` and always
   consumes 1 `FERTILIZER` from inventory via `_inv_take`, **even when the new value
   equals the existing one** (i.e., re-fertilizing a plant that's already covered
   through at least `day+2` burns a unit for zero additional benefit). No feedback is
   given to the agent; only detectable by reading `fertilized_until_day` in the tile
   dict before acting.

7. **Runaway order sizes are legal but harmless.** `_parse_order` (lines 608–626) only
   checks `n > 0`, no upper bound — `["SELL","WHEAT",10**9]` is syntactically valid and
   just terminates early once `_commit_unit` starts failing (empty shed / dry funds).
   The 100k-iteration safety valve (lines 562–566) exists for this case but is
   unreachable under realistic shed/money constraints. Not exploitable, but worth
   knowing you don't need to hand-compute exact sellable quantities — `SELL WHEAT
99999` is a safe idiom to mean "sell everything."

8. **HIRE spawn-on-locked-tile is real but self-limiting** (documented in the README
   almost verbatim, confirmed at `_spawn_hand`/`_default_spawn`, lines 510–518,
   147–152): the first hire of each day, before `NE` is purchased, lands on `(5,4)`
   which is `LOCKED`. Locked tiles are passable (line 314–318, `_apply_unit_action`
   movement branch) but every tile-action no-ops there (line 323–326), so that hand's
   _first_ turn is necessarily a movement-only turn before it can do anything useful —
   small but real action-economy tax that a naive "spawn and immediately WATER" hand
   script would silently waste.

9. **No protection against buying an animal with insufficient matching structures, and
   no atomic "build + place" — this is two separate turns minimum** (`BUILD_COOP`/
   `BUILD_PASTURE`, lines 437–447, is a farmer/hand op; `PLACE`, lines 449–480, requires
   already standing on a built, empty, matching structure). Combined with quirk #2, a
   scripted agent that does `BUY_ANIMAL` and `BUILD_COOP` in the same turn without
   sequencing the `PLACE` for a later turn (and without checking the structure actually
   finished building, given intra-turn ordering per §1) can easily end up with a
   stranded animal in the shed for one or more turns it didn't intend, or forever if
   the placement logic is buggy in the agent itself.

---

## 8. `starter` built-in agent — full strategy (lines 1031–1060)

- Single-tile, single-crop "carrot loop": operates **exclusively** on whatever tile the
  main farmer currently occupies (its spawn tile at `(4,4)` every day, since it never
  issues a movement op) — never explores or claims any of the other 99 tiles on a
  10×10 board.
- **Never uses hired hands** — `hands` is always `[]` in its returned action; never
  issues `HIRE`.
- **Never buys land** (`BUY_LAND`), never builds a coop/pasture, never touches animals
  at all.
- **Never fertilizes** — so it caps at CARROT's _unfertilized_ max yield of 3
  (`age >= max_yield_day(3)` triggers harvest, README-documented as the fertilizer-less
  ceiling; true max with fertilizer is 4).
- Seed logic: buys exactly 1 `CARROT` seed (`BUY_SEED CARROT 1`) whenever it holds zero
  seeds and has ≥ $20 (`CROPS["CARROT"]["seed"]`); replants immediately once the tile is
  empty and it has a seed.
- Watering logic: waters once per day while the plant exists and `watered_today` is
  False, every day from planting until harvest (age 0 through 2) — reaches the
  watering-window bonus every eligible day since it's the tile's sole occupant/visitor.
- Harvest trigger: age `>= max_yield_day` (3), immediate `HARVEST` op that turn — no
  attempt to squeeze extra bonus days beyond the max window.
- Selling logic: **unconditional** — any turn `shed["CARROT"] > 0`, it queues `SELL
CARROT <entire_stack>` regardless of current market price; zero price-awareness, zero
  batching/timing strategy (directly vulnerable to the town-tick timing arbitrage in
  Exploit Candidates #3).
- Relies entirely on the automatic end-of-day inventory→shed drop (never issues an
  explicit `DROP`/`PLACE` to move harvested carrots to shed itself); only reads from
  `private["shed"]` to decide what to sell.
- Net effect: a very weak, single-resource, single-tile economic engine that ignores
  ~99% of available board space, all animals, all other crops, hiring, and land
  expansion. It is explicitly documented as "a deterministic baseline," and the code
  confirms it is about as minimal as a legally-valid, self-sustaining agent can be —
  any agent that expands to even 2–3 tiles with basic price-awareness should clear it
  comfortably.

---

## Addendum (2026-08-11): town-center consumption law, 1.32.4 → 1.32.6

**Version history** (all engine-verified from replay `module_version`, `#42` comment
at 2026-08-08T20:43:39Z):

| Date     | Evidence                                | `module_version` | `townCenterSellInterval` |
| -------- | --------------------------------------- | ---------------- | ------------------------ |
| Aug 5    | probe ep 90301508                       | 1.32.4           | 12                       |
| ~Aug 6–7 | M1 fixture ep 90563134                  | 1.32.5           | 12                       |
| ~Aug 7–8 | M2a/M2b fixtures ep 90826392 / 91087847 | 1.32.6           | 24                       |
| Aug 8    | live ladder eps 91106026 / 91105152     | **1.32.6**       | **24**                   |

Live server config in full (`#42`, same comment): `townCenterSellInterval=24`,
`townShopSellInterval=4`, `townShopUnlockInterval=3`, `episodeSteps=720`,
`turnsPerDay=24` (⇒ 30-day season, `day = step // 24`), `boardSize=10`,
`startingMoney=3000`, `shedCapacity=100`, `maxMarketOrdersPerTurn=10`,
`weedSpawnChance=0.005`, `farmHandCostMult=1`.

**What changed — source-verified on both sides: the installed `1.32.6` package, and
the `1.32.4` wheel fetched from PyPI (2026-08-11)** (`kaggriculture.py`,
`_town_consume`, lines 715–736 — quoted verbatim):

```python
def _town_consume(env, state, step):
    obs0 = state[0].observation
    market = obs0.market
    town = obs0.town
    cfg = env.configuration
    shop_interval = max(1, int(get(cfg, "townShopSellInterval", 4)))
    center_interval = max(1, int(get(cfg, "townCenterSellInterval", 24)))

    if step % shop_interval == 0:
        # unlocked_shops may list the same shop more than once (shops are drawn
        # with replacement); each instance consumes independently.
        for shop_name in town.get("unlocked_shops", []):
            products = SHOPS[shop_name]
            multiplier = 2 if len(products) == 1 else 1
            for item in products:
                market["inventory"][item] -= multiplier

    if step % center_interval == 0:
        for item in TOWN_CENTER_PRODUCTS:
            market["inventory"][item] -= 1

    _refresh_prices(market)
```

`TOWN_CENTER_PRODUCTS = [p for p in PRODUCTS if p != "FERTILIZER"]` (line 101) — the
8 non-fertilizer products: WHEAT, CARROT, TOMATO, STRAWBERRY, MELON, EGG, MILK, WOOL.
`grep -n "TOWN_CENTER_DEMAND_SCHEDULE" kaggriculture.py` on the installed `1.32.6`
package returns **zero matches** — the constant is gone, confirmed directly (not just
via `#42`'s narrative).

1. **The day-scaled schedule is removed.** `#42` (comment at 2026-08-08T20:48:34Z)
   quotes the **1.32.4 value verbatim**: `TOWN_CENTER_DEMAND_SCHEDULE = [(20, 4), (10, 2),
(0, 1)]`. In `1.32.6` this constant does not exist; the `if step % center_interval
== 0` block above simply decrements every `TOWN_CENTER_PRODUCTS` item by a flat `1`,
   with no lookup, no day argument, no scaling of any kind.

2. **Orientation of the removed schedule — source-verified against the 1.32.4 wheel**
   (fetched from PyPI 2026-08-11). 1.32.4 carries `TOWN_CENTER_DEMAND_SCHEDULE =
[(20, 4), (10, 2), (0, 1)]` (`kaggriculture.py:104`), consumed in `_town_consume`
   as `center_mult = next(m for threshold, m in TOWN_CENTER_DEMAND_SCHEDULE if day >=
threshold)` (line 723): day ≥ 20 → 4×, day ≥ 10 → 2×, else 1× — town-center demand
   **ramped up** toward the end of the season under 1.32.4. Two pre-existing
   artifacts corroborate the same orientation: `docs/recon/economy.md` §2c prose
   ("Town center scales 1x→2x (day 10)→4x (day 20)") and #42's late-game 8×/day
   arithmetic. 1.32.6 removes this ramp entirely, flattening the curve at the
   _lowest_ point the old schedule ever reached. The same 1.32.4 source read also
   confirms the in-code `townCenterSellInterval` default of 12 in `_town_consume`
   (vs 24 in 1.32.6) — point 3's doubling holds at the code level, not just in
   server config.

3. **`townCenterSellInterval` default doubled 12 → 24**, both in the live server config
   (table above) and in the package's own code-level default (`get(cfg,
"townCenterSellInterval", 24)` at line 721, vs. the `1.32.4`-era default of 12 per
   `docs/recon/economy.md:11` and `docs/recon/engine-mechanics.md:448`).

4. **Cadence is a raw-step modulo, not a day-boundary check — pin this down precisely.**
   `step` (line 897, `step = get(obs0, "step", 0)`) is the global turn counter,
   incremented once per `interpreter()` call (once per `env.step()`), independent of
   `turnsPerDay`. `center_interval` fires on `step % center_interval == 0` against that
   raw counter. **It only reads as "once per day" because `turnsPerDay` is _also_
   configured to 24 right now** — `step % 24 == 0` happens to coincide with day
   boundaries (`day = step // turns_per_day`, line 898) purely because both constants
   share the value 24. If `turnsPerDay` and `townCenterSellInterval` ever diverge, the
   tick decouples from day boundaries; nothing in the code ties them together. Under
   1.32.4 (interval 12, turnsPerDay 24), the tick fired twice per day — a "half-day"
   cadence, not a daily one, matching `#42`'s own "1/half-day" phrasing.

5. **Unconditional, no threshold, no floor.** The flat `-1` (and the old schedule's
   multiplier draw) apply on every qualifying tick regardless of current town-center
   stock — there is no `if market["inventory"][item] > 0` guard anywhere in
   `_town_consume`, and `market["inventory"][item]` itself has no floor clamp (only the
   _derived price_, via `market_price()` → `max(PRICE_FLOOR, ...)`, line 193, is
   floored). In principle inventory can go negative; in practice `MARKET_I0 = 10000`
   (line 38) as the reference stock level makes this a non-issue at any realistic
   season length.

6. **Town-SHOP consumption is unaffected.** `SHOPS` composition, `townShopSellInterval`
   (unchanged at 4 across the whole `1.32.4`→`1.32.6` window per `#42`'s version table),
   `townShopUnlockInterval` (3), and the "2× for single-product shop, else 1×" rule
   (line 728) are all present, unchanged, in `1.32.6` and match the pre-existing
   `docs/recon/economy.md` shop model exactly (cross-checked below). `#42`'s audit only
   ever flags `townCenterSellInterval` as a changed config value — nothing in that
   thread, or in this source read, indicates the shop law moved.

7. **Price/market law untouched.** `MARKET_PARAMS` (lines 41–51 of `1.32.6`) is
   byte-identical to the values already recorded in `docs/recon/economy.md` §2a/§2b
   (base price and `T` per product match exactly — WHEAT 25/400, CARROT 35/450, TOMATO
   60/200, STRAWBERRY 120/100, MELON 250/300, EGG 50/332, MILK 160/122, WOOL 200/105,
   FERTILIZER 100/200). `#42` (comment at 2026-08-08T20:48:34Z) independently reports a
   direct diff between `1.32.4` and `1.32.6` `MARKET_PARAMS` as empty (all 9 products ×
   7 fields). Price law re-verified 0/6,480 across all four replay fixtures under
   1.32.4. What changed is **inventory drain speed**, not the price formula that
   consumes it.

**Citation-law note — do not cite the following as drift evidence.** `#42`'s own body
and its first comment originally cited "275–573 of 719 transitions mismatch per
fixture" as town-law-drift evidence. `#42`'s second comment (2026-08-08T20:48:34Z)
retracts that: `town_consumption_law_check` is PASS-only-episode-scoped and cannot
distinguish real market trades from town consumption in the three own-episode
fixtures (each holds 1,438 real trades), so those mismatch counts are **confounded**
and must not be used as evidence. The only clean fixture (the 1.32.4 probe,
PASS-only) replays 0/719 town-law mismatches under matching local 1.32.4 — consistent
with, not contradicting, everything above. The actual verification for this addendum
is the source-level diff (points 1–7) plus the independent byte-exact parity pass
(`#42`, comment 2026-08-08T21:00:17Z: 0/1,440 mismatched transitions reproducing both
1.32.6-recorded fixtures under local `1.32.6`).

---

## Addendum (2026-08-11): DROP at a full shed destroys the carried inventory

Engine-verified against the installed `1.32.6` source, `_apply_unit_action`'s DROP
branch (`kaggriculture.py:329–343`): for each carried item, `take = min(n, room)` is
deposited — and then `del inv[item]` runs **unconditionally**. Whatever does not fit
is not returned to the carrying unit; with `room = 0` an entire harvest load is
silently destroyed. There is no error, no partial carry-over, no signal.

Consequence: letting the shared 100-unit shed (`shedCapacity`, one pool for all
produce + fertilizer + unplaced animals) saturate converts every subsequent harvest
into a total loss even when the harvested product's market price is healthy. This is
the terminal stage of the champion-vs-meta-clone collapse diagnosed on #59
(instrumented replays, seeds 89377/89181/89356: crashed wool/milk held at static
floors → 100-unit backlog → wheat/egg harvests destroyed from ~day 20 → income zero,
hands 13→0, final money $65). Shed headroom is a **hard economic invariant**: a
destroyed harvest is worth $0, so any clearing price beats holding when headroom runs
out.

---

## Doc vs. Code discrepancies

Overall the README/AGENTS.md pair is _more_ precise than typical competition docs — most
"discrepancies" below are omissions (things the code enforces/permits that the docs never
state), not contradictions. None found where the docs actively assert something the code
contradicts.

| #   | Doc statement                                                                                                | Code reality                                                                                                                                                                                                                                                                                                               | Severity                         |
| --- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| 1   | Turn order lists "Market refresh" and "Income update" as separate post-hoc steps under "Update observations" | Money changes happen _inline_, inside `_commit_unit`, during market resolution itself (line 634, 646, 653, 661) — not as a distinct later phase. Externally the net effect (money reflects trades by next observation) is the same; it's a description simplification, not a functional gap.                               | cosmetic                         |
| 2   | Docs never state whether `GOOSE`/`COW`/`SHEEP` can be sold back                                              | They cannot — `PRODUCTS` (line 25) excludes animal names; only `SELL` targets in `PRODUCTS` are legal (line 573). Confirmed omission, real practical risk (Exploit #2).                                                                                                                                                    | **high**                         |
| 3   | Docs describe the price floor and "the floor remains responsive to subsequent buys"                          | True, but only documents the _sell_-side floor protection (no inventory increment at $1, line 636); never states the _buy_-side has no equivalent floor protection (inventory always decrements on `BUY_PRODUCT`, line 648, even from a floored glut) — this asymmetry is what makes fertilizer-buyback (Exploit #1) work. | medium                           |
| 4   | Docs describe watering/fertilizer bonus mechanics per crop type correctly                                    | Confirmed byte-for-byte against `_apply_unit_action` WATER branch and `_daily_refresh_plants` — no discrepancy found.                                                                                                                                                                                                      | n/a                              |
| 5   | Docs state actTimeout/overage/runTimeout style budgets generically                                           | These exact numbers (`actTimeout=1`, `remainingOverageTime=60`) are specific to this package's local defaults; production Kaggle infra timeout values are not verifiable from this codebase and may differ.                                                                                                                | informational                    |
| 6   | Nothing in the docs mentions PLANT-vs-BUY_SEED same-turn sequencing                                          | Confirmed real: unit actions resolve before market actions every turn (§1), so buy-then-plant same-turn silently fails the plant.                                                                                                                                                                                          | medium (agent-authoring pitfall) |

---

## Files read (full)

- `kaggriculture.py` (1063 lines) — engine core, fully read.
- `kaggriculture.json` (138 lines) — spec/config schema, fully read.
- `README.md` (362 lines), `AGENTS.md` (287 lines, not separately quoted above since its
  content is a strict subset/getting-started wrapper around README.md) — fully read.
- `kaggle_environments/core.py` — `Environment.step/run/reset`, `__run_interpreter*`,
  `__loop_through_interpreter`, `__agent_runner`, `__get_shared_state`, `done` property —
  relevant sections read in full.
- `kaggle_environments/agent.py` — `Agent.act`, `build_agent`, `UrlAgent` — read in full.
- `kaggle_environments/utils.py` — `resolve_episode_seed`, `default_schema`,
  `process_schema` — relevant sections read.
- `kaggle_environments/schemas.json` — base `configuration`/`state.observation`/`status`
  schema defaults — queried directly.
- Visualizer HTML bundles (`visualizer/default`, `visualizer/playable`) — **not** read;
  irrelevant to mechanics (pure front-end rendering of replay JSON).
