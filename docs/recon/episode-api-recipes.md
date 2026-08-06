# kaggriculture PROBE log retrieval — findings (2026-08-05)

## Bottom line

- **Episode replay JSON: retrieved successfully**, unauthenticated, saved to
  `probe-server-replay.json` (4,338,821 bytes / ~4.3MB, not ~27MB as estimated).
- _*PROBE_* stdout lines: NOT retrieved._* The only endpoint that serves per-agent
  stdout logs (`GET /competitions/episodes/{id}/agents/{idx}/logs.json`) returns
  `401 {"error":{"message":"Unauthenticated"}}` both unauthenticated and with the
  `~/.kaggle/access_token` Bearer credential. Root cause identified below — this is
  a hard wall under the task's constraints (no interactive login permitted).
- Confirmed: **the replay JSON does not embed agent stdout/logs** — no `"logs"` key
  per step, no `PROBE` strings anywhere in the file. A separate logs endpoint really
  is necessary; there's no way around it via the replay.

## Episode identified

Episode **90301508**, `EPISODE_TYPE_VALIDATION`, self-play (both agents are
submission 55284206, "Charles Coonce" vs "Charles Coonce"), created
2026-08-06T00:37:54Z, ended 2026-08-06T00:39:46Z, state COMPLETED. This is the
submission's first episode (earliest `createTime` in the returned list), matching
the "self-play validation episode" description. `episodeSteps: 720`, matching the
step=719 probe line's plausibility.

Full episode list for submission 55284206 (9 episodes, newest first), for reference:

| episode id   | createTime    | type           | opponent submissionId    |
| ------------ | ------------- | -------------- | ------------------------ |
| 90307293     | 01:08:54Z     | PUBLIC         | 55277332                 |
| 90306564     | 01:04:51Z     | PUBLIC         | 55221380                 |
| 90305823     | 01:00:51Z     | PUBLIC         | 55268337                 |
| 90305075     | 00:56:51Z     | PUBLIC         | 55252224                 |
| 90304315     | 00:52:50Z     | PUBLIC         | 55272894                 |
| 90303572     | 00:48:53Z     | PUBLIC         | 55281242                 |
| 90302818     | 00:44:50Z     | PUBLIC         | 55265540                 |
| 90302063     | 00:40:50Z     | PUBLIC         | 55284025                 |
| **90301508** | **00:37:54Z** | **VALIDATION** | (self-play, no opponent) |

## PROBE_FACTS / PROBE_CONFIG / PROBE_STEP content

**Not recovered.** All attempts to reach the agent-logs endpoint (both
unauthenticated and with the Kaggle OAuth access token) returned:

```
HTTP/2 401
content-type: application/json; charset=utf-8
{"error":{"message":"Unauthenticated"}}
```

for both `agentIndex=0` and `agentIndex=1` of episode 90301508. No PROBE_FACTS,
PROBE_CONFIG, or PROBE_STEP lines were obtained from any episode.

### Why the authenticated fallback (method 3) didn't work — root-caused, not just retried

I read the installed `kagglesdk` package source
(`.../kagglesdk/kaggle_env.py`, `kaggle_http_client.py`, `kaggle_creds.py`) to
understand what `~/.kaggle/access_token` actually is (I did not read the token
value itself — only the library code that consumes it):

- `~/.kaggle/access_token` is a bare OAuth **Bearer access token** (12-hour
  default expiry per `KaggleCredentials.DEFAULT_ACCESS_TOKEN_EXPIRATION`),
  read by `kagglesdk.kaggle_env.get_access_token_from_env()` and attached as
  `Authorization: Bearer <token>` by `KaggleHttpClient.BearerAuth`.
- That Bearer token authenticates calls to the **official Kaggle v1 JSON-RPC
  API** (`{service_name}/{request_name}` under `/v1/`, served at
  `api.kaggle.com` in prod). I inspected
  `kagglesdk/competitions/types/episode.py` and
  `kagglesdk/competitions/services/competition_api_service.py` — the official
  SDK has **no episode-replay or episode-logs surface at all**. Simulation
  episode logs are a **website-only feature**, not part of the public API.
- The `/competitions/episodes/{id}/agents/{idx}/logs.json` route (discovered
  via JS bundle, see below) is a **website download route**, gated by a real
  browser **session cookie** from an interactive login — not by OAuth Bearer
  tokens. That's why the Bearer attempt gets the identical `401
Unauthenticated` response as the fully unauthenticated attempt: the token
  is being presented to a credential-check code path that was never designed
  to accept that credential type.
- Getting past this would require an actual interactive Kaggle login (entering
  credentials / establishing a session cookie), which is outside the read-only,
  non-interactive scope of this task and is excluded by the standing safety
  rules against entering credentials or creating authenticated sessions. I did
  not attempt it.

I verified this is a real dead end, not just a guess: I navigated the browser
(unauthenticated) to `https://www.kaggle.com/competitions/kaggriculture/submissions`
and got Kaggle's generic "We can't find that page" — confirming that owner-only
submission/log views are simply unreachable without a real login in this session.

## Working endpoint recipes (exact commands)

### 1. List episodes for a submission (unauthenticated, works)

```
curl -s -X POST "https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes" \
  -H "Content-Type: application/json" \
  -d '{"submissionId": 55284206}'
```

Returns `{"episodes": [...]}`, most recent first, each with `id`, `createTime`,
`endTime`, `state`, `type` (`EPISODE_TYPE_PUBLIC` / `EPISODE_TYPE_VALIDATION`),
and `agents[]` (each agent has `submissionId`, `reward`, `updatedScore`,
`teamId`, optional `index`).

Note: `GetEpisodeReplay` on this same `api/i/competitions.EpisodeService/`
namespace (as hypothesized in the task) does **not** exist — every casing
variant (`episodeId`, `EpisodeId`, `episode_id`, `Id`, `id`) returned a plain
`404` HTML page, not a JSON error, meaning the method name itself is wrong,
not the field casing. The real replay-serving route is below.

### 2. Fetch one full episode replay JSON (unauthenticated, works — used for the deliverable)

```
curl -s "https://www.kaggle.com/competitions/episodes/90301508/replay.json" \
  -o probe-server-replay.json
```

Simple `GET`, no POST body, no auth needed. Confirmed via live browser network
capture (`GET .../replay.json → 200`, triggered when opening
`?dialog=episodes-episode-90301508` on the leaderboard page) and reproduced
standalone with curl — identical result.

### 3. Fetch episode metadata (unauthenticated, works — discovered via browser)

```
curl -s -X POST "https://www.kaggle.com/api/i/competitions.EpisodeService/GetEpisode" \
  -H "Content-Type: application/json" \
  -d '{"id": 90301508}'
```

Actually the exact working request body/headers used by the site's own JS could
not be independently reproduced with plain curl (my direct attempts with `id`,
`Id`, `episodeId`, `EpisodeId` all returned `400` with empty body) — this one
was only confirmed by reading the live network request from the browser after
loading the dialog URL. It returns episode + team metadata (score, team name,
submission count) — no logs, no PROBE content. Not needed for the deliverable
since replay.json alone answers the "one full replay" ask.

### 4. Agent stdout logs (endpoint identified, but returns 401 — NOT retrieved)

Discovered by downloading and grepping the site's JS bundle
(`CompetitionDetail.03a2b683d2745b6d.js`) for the `downloadLogs` grid-column
handler:

```js
onClick: function() {
  return (0,nb.O)("/competitions/episodes/".concat(t,"/agents/").concat(e.row.agentIndex,"/logs.json"))
}
```

i.e. the real pattern is:

```
GET https://www.kaggle.com/competitions/episodes/{episodeId}/agents/{agentIndex}/logs.json
```

Tried both unauthenticated and with the Bearer token:

```
curl -s "https://www.kaggle.com/competitions/episodes/90301508/agents/0/logs.json"
curl -s "https://www.kaggle.com/competitions/episodes/90301508/agents/1/logs.json"
curl -s -H "Authorization: Bearer $(cat ~/.kaggle/access_token)" \
  "https://www.kaggle.com/competitions/episodes/90301508/agents/0/logs.json"
curl -s -H "Authorization: Bearer $(cat ~/.kaggle/access_token)" \
  "https://www.kaggle.com/competitions/episodes/90301508/agents/1/logs.json"
```

All four: `HTTP 401`, body `{"error":{"message":"Unauthenticated"}}`. See root
cause above.

## Saved replay JSON

Path: `probe-server-replay.json` (in the scratchpad root, as requested)
Size: 4,338,821 bytes (~4.1 MiB)
Source: episode **90301508** (the self-play validation episode)

Top-level keys: `configuration`, `description`, `id`, `info`, `module_version`,
`name`, `rewards`, `schema_version`, `specification`, `statuses`, `steps`,
`title`, `version`

- `configuration`: `actTimeout`, `boardSize`=10, `episodeSteps`=720,
  `farmHandCostMult`, `marketParams`, `maxMarketOrdersPerTurn`=10,
  `runTimeout`=1200, `seed`=null (top-level config seed is null; the real seed
  used is `info.seed`=0), `shedCapacity`=100, `startingMoney`=3000,
  `townCenterSellInterval`=12, `townShopSellInterval`=4,
  `townShopUnlockInterval`, `turnsPerDay`, `weedSpawnChance`
- `info`: `Agents` (both "Charles Coonce"), `EpisodeId`=90301508,
  `LiveVideoPath`=null, `TeamNames`=["Charles Coonce","Charles Coonce"],
  `seed`=0
- `steps`: list of 720 steps; each step is a 2-element list (one dict per
  agent) with keys `action`, `info`, `observation`, `reward`, `status`.
  `observation` per agent has `day`, `farms`, `hour`, `market`, `player`,
  `private`, `remainingOverageTime`, `step` (agent 0 only), `town`.
  **Per-step `info` is an empty dict `{}` for every agent/step checked — no
  stdout/log content embedded anywhere in the replay.**

Confirmed via `grep -o "PROBE[A-Za-z_]*"` over the whole file: **zero matches**.
So: **logs are not embedded in replays for this competition** — a separate
logs endpoint really is required, and that endpoint (see #4 above) is
session-cookie-gated and unreachable without an interactive login, which is
out of scope for this task.

## Scratch files

Working files are under `probe-chase/`:

- `attempt1.json` — full `ListEpisodes` response (9 episodes)
- `replay_90301508_v2.json` — the replay JSON (source copy of the deliverable)
- `logs_90301508_agent0.json`, `logs_90301508_agent1.json` — the 401 responses
  (unauthenticated)
- `logs_90301508_agent0_auth.json`, `logs_90301508_agent1_auth.json` — the 401
  responses (Bearer-authenticated)
- `jsbundles/` — downloaded JS assets used to find the `downloadLogs` endpoint
  pattern (grep target: `CompetitionDetail.03a2b683d2745b6d.js`)
