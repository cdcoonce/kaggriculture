# kaggriculture engine-mechanics invariant tests

Engine source read: `kaggle_environments/envs/kaggriculture/kaggriculture.py`
(kaggle_environments 1.32.4). Verified against the real engine, not guessed.

## Final pytest run

```
3 passed in 0.79s
```

(`test_same_turn_buy_plant_noops`, `test_fresh_plant_unwatered_weeds_overnight`,
`test_animals_cannot_be_sold` — all green.)

## Engine-behavior facts confirmed (useful for future scripted agents)

- **Action shape**: an agent returns
  `{"farmer": [op, *args], "hands": [[op, *args], ...], "market": [[op, *args], ...]}`.
  `farmer`/`hands` are unit-action lists (`PLANT <crop>`, `WATER`, `HARVEST`,
  `PASS`, movement, etc.); `market` is a list of order lists
  (`BUY_SEED <crop> <n>`, `BUY_ANIMAL <animal> <n>`, `BUY_PRODUCT <item> <n>`,
  `SELL <item> <n>`, `HIRE`, `BUY_LAND`).

- **Turn resolution order** (`interpreter()` in kaggriculture.py): for every
  player, all unit actions (farmer + hands) are applied first via
  `_apply_unit_action`; only _after_ every player's unit actions have run does
  `_process_market` execute everyone's market orders. So a same-turn
  `BUY_SEED` + `PLANT` always has the `PLANT` see zero seeds — there is also
  an "atomic PLANT validation" pre-pass that checks `PLANT` demand against
  the _current_ (pre-market) `private["seeds"]` count and silently rewrites
  any over-demanded `PLANT` to `PASS` before unit actions even run.

- **`obs["step"]` indexing**: the action an agent returns while it sees
  `obs["step"] == k` lands in `env.steps[k + 1]`. `env.steps[0]` is the
  post-reset, pre-any-action snapshot (also `step == 0`).

- **Planting day counts as unwatered**: `_new_plant` sets
  `consecutive_unwatered = 1` at creation (not 0), so a plant only needs to
  survive _one_ unwatered day-boundary refresh to become
  `{"kind": "WEED"}` — not two, despite the daily-refresh check being
  `consecutive_unwatered >= 2`. Watering on the planting day resets it to 0
  at the next boundary and the plant survives.

- **Day boundary**: with default `turnsPerDay == 24`, the end-of-day refresh
  fires while processing the turn where `obs.step == 23` (the 24th turn),
  i.e. `(step + 1) % turnsPerDay == 0`. That result lands in
  `env.steps[24]` (day 1, hour 0).

- **`SELL` silently rejects non-`PRODUCTS` items**: `PRODUCTS` is the crop /
  animal-product / fertilizer list and does **not** include animal names
  (`GOOSE`, `COW`, `SHEEP`). `_process_market`'s per-unit loop only quotes
  `SELL` when `item in PRODUCTS`; anything else falls into the "malformed
  sub-op" branch and the whole order is dropped before any shed or money
  check runs. Animals genuinely cannot be sold via `SELL` — there's no shed
  check being bypassed, the op is rejected outright.

- **`BUY_ANIMAL` pricing is flat**: unlike `SELL`/`BUY_PRODUCT`, which price
  off the market's supply/demand curve (`market_price`), `BUY_ANIMAL` always
  quotes `ANIMALS[item]["cost"]` (300 for `GOOSE`) regardless of market
  inventory.

- **Farm/tile layout**: `farm["farmer"]` is `[x, y]`; tiles are indexed
  `farm["tiles"][y][x]` (row-major, y first). The default spawn tile for a
  fresh farm is inside the always-unlocked NW quadrant and starts as an
  empty (`None`) tile, so a farmer can `PLANT` immediately without moving.

## Environment setup notes

- The venv's Python had no `pip` at all; had to run
  `python -m ensurepip --upgrade` before `python -m pip install pytest`.
- `weedSpawnChance` was set to `0.0` in every test's configuration purely for
  determinism/readability. It turned out not to be load-bearing either way:
  `_spawn_weeds` only ever mutates tiles that are currently `None`, and every
  tile this suite inspects already holds a `PLANT` (or is the untouched
  planting tile) by the time weeds could spawn on it.
