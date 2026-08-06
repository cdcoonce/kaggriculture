# Kaggle Runner Facts (M0a probe, verified 2026-08-05)

Source: agent stdout logs of validation episode 90301508 (submission 55284206), retrieved via
`/competitions/episodes/90301508/agents/0/logs.json` (session-cookie-gated; raw copy committed
alongside as `probe-episode-logs-90301508-0.json`).

## PROBE_FACTS (verbatim)

```json
{
  "python": "3.11.13 (main, Jun  4 2025, 08:57:29) [GCC 11.4.0]",
  "platform": "linux",
  "cpu_count": 2,
  "packages": {
    "numpy": "2.4.6",
    "scipy": "1.15.3",
    "pandas": "2.2.3",
    "sklearn": null,
    "torch": "2.6.0+cu124",
    "tensorflow": null,
    "onnxruntime": null,
    "numba": null,
    "polars": "1.25.0",
    "xgboost": null,
    "lightgbm": null,
    "kaggle_environments": "1.32.4"
  }
}
```

## PROBE_CONFIG (verbatim)

```json
{
  "seed": null,
  "episodeSteps": 720,
  "actTimeout": 1,
  "runTimeout": 1200,
  "boardSize": 10,
  "startingMoney": 3000,
  "maxMarketOrdersPerTurn": 10,
  "turnsPerDay": 24,
  "shedCapacity": 100,
  "weedSpawnChance": 0.005,
  "townShopUnlockInterval": 3,
  "townShopSellInterval": 4,
  "townCenterSellInterval": 12,
  "farmHandCostMult": 1,
  "marketParams": {},
  "__raw_path__": "/kaggle_simulations/agent/main.py"
}
```

## PROBE_STEP (timeout accounting)

```
step=1   t=44.577  overage=16.442
step=100 t=50.384  overage=16.442
step=360 t=65.934  overage=16.442
```

## Implications (load-bearing)

1. **Runner Python is 3.11.13** — local dev/gates must build and test agent code against 3.11
   (local venv is 3.13.5; add a 3.11 interpreter for agent-code CI). No 3.12+/3.13-only syntax
   in the submission tree.
2. **numpy 2.4.6, scipy, pandas, polars are PRESENT; torch 2.6.0+cu124 is PRESENT** (CUDA build,
   CPU-usable). Absent: sklearn, tensorflow, onnxruntime, numba, xgboost, lightgbm.
   The learned-components kill-signal ("stdlib-only runner") did NOT fire; the numpy go-signal DID.
3. **The import sweep cost ~43.5 s of the 60 s overage bank** (vs ~8 s locally) — almost certainly
   dominated by the torch import on 2 slow vCPUs. Consequences: (a) module-level imports must be
   lean — importing torch spends most of the episode's safety margin; (b) a numpy-only inference
   path keeps ~52 s of bank free; (c) after init, PASS turns drained ZERO additional overage —
   the 1 s/turn budget is comfortable.
4. **Default config confirmed empirically** — every value matches local defaults; `marketParams`
   is empty (no server-side overrides); seed is null in validation.
5. **Engine version parity: server runs kaggle_environments 1.32.4 — identical to local.**
   (Law-level parity analysis of the captured replay runs separately → server-parity ticket.)
6. Submission unpacks to `/kaggle_simulations/agent/main.py` — relative-path asset loading in the
   submission must anchor on `__file__`, not CWD.
