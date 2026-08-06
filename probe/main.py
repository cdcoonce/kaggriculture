"""M0a probe agent — Kaggriculture runner environment reconnaissance.

PASSes every turn; emits environment facts to stdout at step 0 and
overage-bank checkpoints at a few later steps. Facts are recovered from the
episode's agent logs. Must never crash: a sticky ERROR would freeze the farm
and void the probe.
"""

import json
import sys
import time

_PROBED = False
_T0 = None

_PACKAGES = [
    "numpy",
    "scipy",
    "pandas",
    "sklearn",
    "torch",
    "tensorflow",
    "onnxruntime",
    "numba",
    "polars",
    "xgboost",
    "lightgbm",
    "kaggle_environments",
]


def _probe_env():
    facts = {"python": sys.version, "platform": sys.platform}
    try:
        import os

        facts["cpu_count"] = os.cpu_count()
    except Exception as exc:
        facts["cpu_count_err"] = repr(exc)
    pkgs = {}
    for name in _PACKAGES:
        try:
            mod = __import__(name)
            pkgs[name] = getattr(mod, "__version__", "present")
        except Exception:
            pkgs[name] = None
    facts["packages"] = pkgs
    return facts


def agent(obs, config=None):
    global _PROBED, _T0
    try:
        now = time.time()
        if _T0 is None:
            _T0 = now
        if not _PROBED:
            _PROBED = True
            print("PROBE_FACTS " + json.dumps(_probe_env()), flush=True)
            if config is not None:
                try:
                    print("PROBE_CONFIG " + json.dumps(dict(config)), flush=True)
                except Exception:
                    print("PROBE_CONFIG_REPR " + repr(config)[:2000], flush=True)
        if isinstance(obs, dict) and obs.get("step") in (1, 100, 360, 719):
            print(
                "PROBE_STEP step={} t={:.3f} overage={}".format(
                    obs.get("step"), now - _T0, obs.get("remainingOverageTime")
                ),
                flush=True,
            )
    except Exception as exc:
        try:
            print("PROBE_ERR " + repr(exc)[:500], flush=True)
        except Exception:
            pass
    return {"farmer": ["PASS"], "hands": [], "market": []}
