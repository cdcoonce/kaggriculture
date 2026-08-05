# Kaggriculture "Daily Top Episodes Dataset" — Research Findings

Researched: 2026-08-04, via in-app browser (no sign-in), plus local ground-truth replay inspection.

## Source thread (discussion #731215)

URL: https://www.kaggle.com/competitions/kaggriculture/discussion/731215

- Posted by **Bovard Doerschuk-Tiberi**, tagged **KAGGLE STAFF**, 5 days ago (i.e. ~2026-07-30). Pinned/upvoted (11 votes).
- Full post text (thread has **0 comments** — nothing lazy-loads beyond the OP, confirmed via `read_page` showing "0 Comments" / "Please sign in to reply"):
  > "Each day we order episodes by the average rating of the agents playing (at the time). Then we download up to 20 GB of replays and make a new daily dataset! This should be helpful for everyone trying IL/BC, bootstrapping RL, or just gathering statistics."
- Links to: **https://www.kaggle.com/datasets/kaggle/kaggriculture-episodes-index**
- Nothing here required sign-in to read.

## The "index" dataset (kaggriculture-episodes-index)

Owner: Kaggle + 1 collaborator. Updated a day ago. CC0 license. Usability 4.12. No sign-in needed to view the Data Card or the manifest preview.

Description: "One row per published day pointing at the corresponding daily episode dataset."

Single file: **manifest.csv (888 B)**, 7 columns, 5 rows (one per published day so far):

| date       | daily_dataset_slug                | episode_count | total_bytes    | top_avg_score | median_avg_score |
| ---------- | --------------------------------- | ------------- | -------------- | ------------- | ---------------- |
| 2026-07-30 | kaggriculture-episodes-2026-07-30 | 864           | 13,639,221,377 | 1152.42       | 669.75           |
| 2026-07-31 | kaggriculture-episodes-2026-07-31 | 928           | 21,452,054,005 | 1427.01       | 1175.25          |
| 2026-08-01 | kaggriculture-episodes-2026-08-01 | 829           | 21,450,823,404 | 1580.56       | 1348.19          |
| 2026-08-02 | kaggriculture-episodes-2026-08-02 | 793           | 21,471,097,913 | 2627.21       | 2319.16          |
| 2026-08-03 | kaggriculture-episodes-2026-08-03 | 787           | 21,469,441,381 | 2960.13       | 2730.39          |

(each row also has `daily_dataset_url` pointing at `kaggle.com/datasets/kaggle/kaggriculture-episodes-<date>`)

**Cadence confirmed empirically**: one new dated child dataset per day, 5 published so far (started 2026-07-30, the day the pinned thread went up), most recent 2026-08-03 (today is 2026-08-04, so there's roughly a 1-day publish lag — no dataset for "today" yet at time of research). Total across 5 days: ~99.5 GB, 4,201 episodes. Each day is independently capped at 20 GiB (post text) / matches actual totals (~21.4–21.5 GB on the days it saturates the cap; first day 13.6 GB, presumably because fewer top-rated episodes existed yet).

Note: the dataset's own metadata field **"Update frequency" is literally set to "Unspecified"** on Kaggle's schema — the daily cadence is only asserted in free-text (staff post + dataset description), not encoded in the structured metadata. Flag this as a soft claim, not a hard guarantee.

## A single day's dataset (inspected kaggriculture-episodes-2026-08-03 in detail)

URL: https://www.kaggle.com/datasets/kaggle/kaggriculture-episodes-2026-08-03
Description: "This dataset contains JSON replays of completed episodes from a Kaggle simulations competition. Replays are selected daily, ranked by average agent rating, and capped at 20 GiB per day. See manifest.csv for the list of included episodes and their scores."

**File listing (Data Explorer, visible without sign-in):**

- **788 files total**, Version 1, **21.47 GB**.
- 787 of those are per-episode JSON files named `<EpisodeId>.json` (e.g. `89619023.json`, `89619585.json`, ...) — matches `episode_count=787` from the index row exactly (788 = 787 episode files + presumably `manifest.csv`, which the About-Dataset text explicitly says exists to list "included episodes and their scores," though I did not force-open it individually — file-list virtualization only rendered the first ~35 JSON filenames in the DOM).
- Average file size ≈ 21.47 GB / 787 ≈ **27.3 MB/episode**, matching the previewed file (`89619023.json`, 27.17 MB exactly).

**Per-episode JSON schema** (from Kaggle's in-browser JSON preview of `89619023.json`, truncated by their UI at the `steps` array but fully visible for everything else) — root has 11 keys:

```
configuration: { actTimeout, boardSize=10, episodeSteps=720, farmHandCostMult, marketParams,
                  maxMarketOrdersPerTurn, runTimeout, seed=NULL, shedCapacity, startingMoney,
                  townCenterSellInterval, townShopSellInterval, townShopUnlockInterval,
                  turnsPerDay, weedSpawnChance }
description: "Advanced farming simulation: two players each tend a 10x10 farm of four 5x5
              quadrants, growing crops, raising animals, hiring help, and trading with a
              dynamic market over one season."
id: "cd4ebe16-8ed3-11f1-bdda-0242ac130204"
info: { Agents: [2 items], EpisodeId: 89619023, LiveVideoPath: NULL, TeamNames: [2 items],
        seed: 1210621111 }
module_version: "1.32.2"
name: "kaggriculture"
rewards: [128111, 126071]           # final score per player
schema_version: 1
specification: { action, agents, configuration, info, observation, reward }  # the env's I/O spec
statuses: ["DONE", "DONE"]
steps: [ <episodeSteps items>, each a 2-item list ]   # truncated by Kaggle's previewer past item 12
```

This is the **standard `kaggle_environments` replay format** (same shape used for Halite/Lux AI/Hungry Geese-style sim competitions), and it is byte-for-byte structurally identical (same top-level key set minus `title`/`version`, same `configuration` block, same literal `description` string) to the locally generated replay I inspected directly (see below) — same game engine, `module_version` 1.32.2 (Kaggle, 2 days old) vs 1.32.4 (local, current), a trivial patch drift.

## Ground-truth replay-completeness check (local file, same engine)

Inspected `/private/tmp/.../scratchpad/recon-runs/replay-starter-mirror.json` (4.8 MB, a locally generated self-play match on the same `kaggriculture` env, 720 steps) directly with Python/`json`, reading structure only (no bulk printing):

- Top level: `steps` is a list of 720 entries. **Each entry is a list of exactly 2 dicts — one per agent/player.**
- Each per-agent dict has keys: `action, reward, info, observation, status`.
- **`action` is each agent's own submitted action for that step** — a full `{"farmer": [...], "hands": [...], "market": [...]}` structure per the game's action spec (verified non-empty/non-default actions appear at real turns, e.g. `{'farmer': ['PLANT', 'CARROT'], 'hands': [], 'market': [['BUY_SEED', 'CARROT', 1]]}`).
- **`observation` is that agent's own observation dict**, keys: `remainingOverageTime, step, player, farms, private, market, town, day, hour`. Critically, `observation.farms` is a **list of 2** farm-state dicts (`money, tiles, farmer, hands, unlocked_quadrants, hires_today`) — i.e. **both players' full farm state is visible in every observation**, not just the observing player's own farm. This is a full-information/perfect-information game (no fog of war between competitors), only `observation.private` (shed/seeds/inventories) is genuinely agent-private.
- `data["rewards"]` / `data["statuses"]` at the top level duplicate the final per-agent reward/status (`[3495.0, 3495.0]`, `["DONE","DONE"]` in this file — it was a mirror match, both agents ran the identical policy, hence identical rewards and identical per-step actions throughout, confirmed by diffing agent0 vs agent1 actions across steps 1–10, all equal).

**Verdict: replays carry BOTH players' complete per-turn actions, not just observations.** Every step in the JSON is a 2-element array (one full action+observation+reward+status record per agent), and this is exactly the shape the real Kaggle `89619023.json` preview showed for its `steps` array (`13 items` before truncation, each item shown as `[...] 2 items`). Given the identical engine, identical `configuration`/`description`, and identical steps-as-pairs shape, there is no structural reason to expect the real Kaggle daily-dataset files to differ from this local ground truth — they are dumped directly from the same `kaggle_environments` `.json_replay()`/episode-store mechanism. (I could not decompress a full real episode past step ~12 in-browser due to Kaggle's own preview truncation on the 27 MB file; this is a UI limitation, not an indication the file itself is smaller — the `configuration.episodeSteps=720` field inside that same real file confirms the full episode has 720 steps like the local one, so the real files are simply the same object, undownloaded.)

## Access path / auth

- Discussion thread, index dataset, and per-day dataset Data Cards (description, file list, sizes, JSON structure preview, activity/views/downloads stats, related notebooks) are **all visible without signing in**.
- **Download** and **Create Notebook** buttons are present but were not clicked (per constraints); standard Kaggle behavior requires sign-in (and for bulk/API pulls, a Kaggle API token) to actually pull file bytes — this is almost certainly where your "soon-to-be-fixed CLI auth" unlocks value: once authenticated, `kaggle datasets download kaggle/kaggriculture-episodes-2026-08-03` (or the index dataset, then loop dated children) becomes scriptable, giving programmatic access to the full 787-file/day, ~21 GB/day corpus rather than the single in-browser JSON preview.
- Competition itself ("Play in Browser", "Join Competition") also sits behind auth for interactive play/submission — not touched.

## Corroborating signal: community notebooks already built on this data

Listed under "Related Notebooks" on the per-day dataset pages (titles only, not opened):

- _Kaggriculture Replay Data Miner_
- _Kaggriculture Market Weather Report_
- _What actually wins on the Kaggriculture ladder_
- _Kaggriculture: What the Top Farms Do — a Live Meta_

These titles alone indicate the community is already using this dataset for meta/strategy analysis (opponent-behavior mining, market-price modeling), which is circumstantial support that the data is rich enough for the downstream uses below — but I did not open them to verify methodology.

---

# Summary for the caller

**What the dataset is:** A Kaggle-staff-maintained, two-level dataset pair for the Kaggriculture sim competition. Top: `kaggriculture-episodes-index` — a 5-row (so far), 7-column `manifest.csv` pointing to one child dataset per day. Each child (`kaggriculture-episodes-<date>`) contains **~787–928 individual episode JSON files/day** (one file per completed match) plus its own `manifest.csv` of episode scores, capped at 20 GiB/day, selecting the **top-rated episodes of that day** by average agent rating at time of play.

**Schema:** Standard `kaggle_environments` replay JSON — `configuration`, `description`, `info` (EpisodeId, TeamNames, Agents, seed), `rewards`, `statuses`, `specification`, and a `steps` array of length `episodeSteps` (720), where **every step is a 2-element list, one full record per player**, each record = `{action, observation, reward, info, status}`.

**Cadence:** Daily, since 2026-07-30 (5 days published as of 2026-08-04, ~1-day publish lag). Asserted only in free text; the dataset's structured "Update frequency" metadata field says "Unspecified."

**Size:** ~21–21.5 GB/day once saturated (20 GiB soft cap), ~787–928 episodes/day, ~27 MB/episode average. ~99.5 GB / 4,201 episodes accumulated across the 5 published days.

**Action-completeness verdict: BOTH players' full per-turn actions are included, not just observations.** Confirmed structurally against a local ground-truth replay from the identical engine (`module_version` 1.32.x): each step is a pair of complete per-agent records carrying that agent's actual submitted `action` dict alongside its `observation`. The game is also full-information (each observation's `farms` field lists both players' farm states), so even the "observation" half already contains the opponent's state, not just your own.

**Ranked list of what it enables:**

1. **Imitation-learning / behavior-cloning training data — high feasibility, best fit.** This is exactly what the staff post calls out ("helpful for everyone trying IL/BC"). Full (state, action) pairs for every step, for every player, from the highest-rated matches, refreshed daily — a directly consumable IL dataset with no extra instrumentation needed. The only downstream work is parsing/flattening ~800 replay JSONs/day into a supervised dataset.
2. **Reconstructing top opponents as local sparring partners — high feasibility, straightforward but heavier.** Because both players' actions and the full observation stream are present, you can train a policy (via BC/IL, or as a scripted-imitation baseline) that mimics a specific top-rated agent's move distribution, then run it locally inside the same `kaggle_environments` engine as a sparring bot. Fidelity depends on how well IL captures the strategy (won't be a perfect clone, but a good style-matched practice opponent), and requires cross-referencing `TeamNames`/`Agents` in each episode's `info` block (and the per-day `manifest.csv` scores) to pick out which files belong to which top agent.
3. **Regression scenarios from real losses — moderate feasibility, needs extra plumbing.** The data supports this (you can pull an episode where your submission lost, replay it step-by-step with the exact opposing actions and observations as a fixed regression fixture), but it requires you to already have episode IDs of your own losses (via the competition's own episode/submission history, not this dataset directly) and then locate/download those specific `<EpisodeId>.json` files — this dataset is a _top-rated_ sample, not indexed by "your matches," so it's most useful for building a general regression/eval harness (feed it any top episode as a fixed scenario) rather than specifically your own losses unless your submissions are themselves highly rated enough to appear in the daily top set.

Feasibility for all three is currently gated on the same thing: **auth to actually download files** (only in-browser previews/metadata are visible unauthenticated). Once CLI/API auth lands, all three become a straightforward `kaggle datasets download` + JSON-parsing exercise against a schema that's already fully understood.
