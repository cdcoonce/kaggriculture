# Replay fixture provenance

These are gzipped Kaggle episode replay JSONs used by `tools/parity/check_replay.py`
to cross-check the local `kaggle_environments` engine against a server-produced
trajectory. All three are **self-play validation episodes** (`type:
EPISODE_TYPE_VALIDATION`, both seats' `submissionId` identical, both seats'
`teamId` = `16664096`, both `TeamNames` = `"Charles Coonce"`) — i.e. Charles's
own submission playing itself. No third-party competitor data (no opposing
Kaggle team's strategy) is present in any of these files.

Fetched 2026-08-08, via the unauthenticated recipe documented in
`docs/recon/episode-api-recipes.md` (confirmed working in kaggriculture issue
#23's comments):

```
curl -s "https://www.kaggle.com/competitions/episodes/{episodeId}/replay.json" -o replay.json
```

then gzipped locally (`gzip -9`) before committing.

| File                                    | Episode id | Submission | Model | Fetched    | Source URL                                                          |
| --------------------------------------- | ---------- | ---------- | ----- | ---------- | ------------------------------------------------------------------- |
| `episode-91087847-m2b-selfplay.json.gz` | 91087847   | 55358390   | M2b   | 2026-08-08 | `https://www.kaggle.com/competitions/episodes/91087847/replay.json` |
| `episode-90826392-m2a-selfplay.json.gz` | 90826392   | 55334684   | M2a   | 2026-08-08 | `https://www.kaggle.com/competitions/episodes/90826392/replay.json` |
| `episode-90563134-m1-selfplay.json.gz`  | 90563134   | 55309517   | M1    | 2026-08-08 | `https://www.kaggle.com/competitions/episodes/90563134/replay.json` |

Each episode was located via the submission's episode list
(`POST https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes`,
body `{"submissionId": <id>}`, unauthenticated) by filtering for
`type == "EPISODE_TYPE_VALIDATION"` and both agents sharing the same
`submissionId` — the same self-play-validation-episode pattern already used
for `docs/recon/probe-server-replay.json.gz` (episode 90301508, submission
55284206, see `docs/recon/episode-api-recipes.md`), except these three carry
real (non-PASS) actions from the tuned agent rather than a PASS-only probe,
so they exercise `_apply_unit_action` / `_process_market` / farming /
husbandry code paths that the PASS-only probe replay cannot.

Raw (ungzipped) sizes were 20,046,455 / 19,403,874 / 28,334,628 bytes; gzipped
sizes are 274,020 / 264,121 / 328,072 bytes respectively (all well under the
10 MB fixture budget).

Placement note: this directory is intentionally outside `docs/recon/` and
`eval/` — the two directories issue #28's third-party-data hygiene test walks
— since these fixtures are structurally different from what that test's
PASS-only-or-allowlisted rule is designed to gate (real, non-PASS own-agent
actions). If #28 lands and its hygiene walker is ever widened to cover this
directory, these three files should be added to that test's allowlist rather
than removed — they are own-team data, not third-party data.
