# Issue #29 — pre-existing gate breakage owned by #24, NOT by this slice

## Status

Issue #29 is implemented in full. The three lint legs of the gate are green
(`ruff check`, `ruff format --check`, `mypy packages/agent/src`). The pytest
legs are **red at baseline**, for five failures that this slice neither causes
nor is permitted to fix.

## The five failures

```
FAILED packages/agent/tests/test_engine_integration.py::test_day_twelve_compounds
FAILED packages/harness/tests/test_drift.py::test_no_drift_against_installed_engine
FAILED packages/harness/tests/test_parity.py::test_seed0_probe_fixture_byte_exact
FAILED packages/harness/tests/test_parity.py::test_mutated_field_is_detected
FAILED packages/harness/tests/test_parity.py::test_excluded_field_is_ignored
```

## Root cause

`packages/harness/pyproject.toml:7` pins `kaggle-environments==1.32.6` (landed
by commit cb62521, "pin kaggle-environments ==1.32.6 + lock regen (#24
conductor prerequisite, per #42 ruling)", reachable here via the `origin/main`
merge at HEAD `aa36ba4`).

`packages/harness/src/harness/drift.py:105` still reads
`EXPECTED_ENGINE_VERSION = "1.32.4"`, and the comment immediately above it names
the owner of the follow-up explicitly:

```
# Transcribed from #11's resolution comment and the workspace's resolved lock
# (kaggle-environments==1.32.4 via the >=1.32.4 constraint). NOT from #24 -- #24 pins
# ==1.32.6 and will bump this constant when it lands (#24 AC 2).
EXPECTED_ENGINE_VERSION = "1.32.4"
```

**#24's pin landed; #24 AC 2 (bump this constant) did not.** The drift failure
is that constant, directly. The three parity failures are the seed-0 probe
replay fixture, recorded byte-exact against 1.32.4 and now compared against a
1.32.6 engine (1822 mismatches beginning at step 241 — an engine behavior
change, not a comparator bug; note `test_mutated_field_is_detected` reports
1823 = 1822 + its own injected mutation, i.e. the comparator is working
correctly). `test_day_twelve_compounds` is an engine-behavior checkpoint
(money 98.0 vs. a `> 100.0` floor) tuned against 1.32.4.

## Why this slice did not fix them

1. **Out of scope.** #29's footprint is `ci.yml`, `harness/strength_gate.py`,
   and the additive `"champion-unshelled"` spec in `episodes.py`/`gate.py`.
   None of `drift.py`, `parity.py`, the probe replay fixture, or
   `packages/agent/tests/` is named in #29's acceptance criteria. Editing them
   trips the scope gate and the adversarial reviewer's scope test.
2. **Import-independent from this slice.** The five failing modules import
   `harness.drift`, `harness.parity`, `agent.main`, and `kaggle_environments`.
   None imports `harness.gate`, `harness.episodes`, or `harness.strength_gate`
   — the only modules this slice touches. These failures reproduce with or
   without this diff.
3. **Two of the fixes are human-only.** Regenerating the byte-exact parity
   probe fixture and re-tuning the `test_day_twelve_compounds` money floor are
   re-baselining an engine-drift instrument against a new engine release. Under
   the role fence that is a human judgment call, not executor work — an
   executor that regenerates a drift fixture to make the drift test green has
   destroyed the instrument.

## Ask

Land #24 AC 2 (bump `EXPECTED_ENGINE_VERSION` to `1.32.6`, re-check
`EXPECTED_MARKET_PARAMS`, regenerate the seed-0 probe replay fixture, re-tune
the day-12 checkpoint) as its own slice. #29's last acceptance criterion —
"Root `uv run pytest -m 'not slow' -q` and `-m slow -q` stay green" — cannot be
satisfied on this base, because they are not green on this base to begin with.
