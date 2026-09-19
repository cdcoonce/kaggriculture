"""Money-gate ledger entries — eval/gates/*-money.json (eval protocol, issue #4)."""

from __future__ import annotations

import json
import math
from dataclasses import fields
from pathlib import Path

from harness.gate import MoneyGateResult, run_money_gate
from harness.ledger import (
    find_passing_promotion,
    json_float,
    promotion_refusal_reason,
    write_ledger,
    write_money_ledger,
)
from harness.stats import MoneyVerdict

TINY_CONFIG = {"episodeSteps": 48}
REPO_ROOT = Path(__file__).resolve().parents[3]

ROW_KEYS = {
    "seed",
    "candidate_seat",
    "candidate_money",
    "opponent_money",
    "outcome",
    "candidate_crashed",
    "opponent_crashed",
}


def _sample_money_result(n_seeds: int = 2) -> MoneyGateResult:
    return run_money_gate(
        "builtin:starter",
        "builtin:pass",
        n_seeds,
        5,
        baseline="builtin:starter",
        workers=1,
        extra_config=TINY_CONFIG,
        min_seeds=2,
        candidate_money_floor=0.0,
        opponent_money_floor=0.0,
        run_canary=False,
    )


def _write(tmp_path: Path, result: MoneyGateResult) -> Path:
    return write_money_ledger(
        result,
        tmp_path,
        candidate_commit="abc123",
        timestamp="2026-08-14T09-30-00Z",
    )


class TestWriteMoneyLedger:
    def test_money_ledger_lands_at_the_expected_path(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _sample_money_result())
        expected = (
            tmp_path / "gates" / "2026-08-14T09-30-00Z-builtin_starter-vs-builtin_pass-money.json"
        )
        assert path == expected
        assert path.exists()

    def test_money_ledger_schema_version_is_still_1(self, tmp_path: Path) -> None:
        # Purely additive: `identity.agent_config` landed the same way, and no
        # reader anywhere in the repo branches on the version. Bump only when
        # an EXISTING key changes meaning or disappears.
        payload = json.loads(_write(tmp_path, _sample_money_result()).read_text(encoding="utf-8"))
        assert payload["schema_version"] == 1

    def test_row_key_sets_are_unchanged_in_both_row_blocks(self, tmp_path: Path) -> None:
        # TEETH-CHECK. `test_ledger.py:82-90` pins the row key set with exact
        # set equality; `baseline_rows` is a new TOP-LEVEL block precisely so
        # that pin stays untouched.
        payload = json.loads(_write(tmp_path, _sample_money_result()).read_text(encoding="utf-8"))
        assert set(payload["rows"][0]) == ROW_KEYS
        assert set(payload["baseline_rows"][0]) == ROW_KEYS
        assert len(payload["rows"]) == 4
        assert len(payload["baseline_rows"]) == 4

    def test_money_verdict_block_round_trips_every_field(self, tmp_path: Path) -> None:
        result = _sample_money_result()
        payload = json.loads(_write(tmp_path, result).read_text(encoding="utf-8"))
        block = payload["money_verdict"]

        for field in fields(MoneyVerdict):
            recorded = block[field.name]
            live = getattr(result.money_verdict, field.name)
            if field.name in {"vetoes", "blockers"}:
                assert recorded == list(live)
            else:
                assert recorded == json_float(live) if isinstance(live, float) else recorded == live

        assert block["opponent_mean_delta"] == result.opponent_mean_delta
        assert block["min_opponent_money"] == result.min_opponent_money
        assert block["candidate_canary_ran"] is False
        assert block["candidate_canary_crashed"] is False
        assert block["baseline_canary_ran"] is False
        assert block["baseline_canary_crashed"] is False
        # Veto knobs must round-trip too, or `rerun-ledger` replays a
        # non-default run under the tape-calibrated defaults and reports a
        # mismatch that is really a forgotten knob.
        assert block["min_seeds"] == 2
        assert block["catastrophic_tail_quantile"] == 0.15
        assert block["catastrophic_tail_floor"] == 19000.0
        assert "degenerate_dispersion_ratio" not in block
        assert block["candidate_money_floor"] == 0.0
        assert block["opponent_money_floor"] == 0.0
        assert block["degenerate_seed_fraction"] == 0.25


def _reject_constant(literal: str) -> float:
    raise AssertionError(f"non-JSON literal {literal!r} in the ledger")


class TestLedgerIsValidJson:
    def test_a_vetoed_run_writes_null_not_negative_infinity(self, tmp_path: Path) -> None:
        # D7 TEETH-CHECK. `too_few_seeds` sets the bounds to -inf, and
        # `json.dumps` writes that as the bare token `-Infinity`. RFC 8259
        # has no such literal, so the entry is not JSON: every conforming
        # reader outside CPython rejects the committed file.
        result = run_money_gate(
            "builtin:starter",
            "builtin:pass",
            2,
            5,
            baseline="builtin:starter",
            workers=1,
            extra_config=TINY_CONFIG,
            min_seeds=8,
            candidate_money_floor=0.0,
            opponent_money_floor=0.0,
            run_canary=False,
        )
        assert result.money_verdict.vetoes == ("too_few_seeds",)
        assert result.money_verdict.ci_lower == -math.inf

        text = _write(tmp_path, result).read_text(encoding="utf-8")
        assert "Infinity" not in text
        assert "NaN" not in text

        payload = json.loads(text, parse_constant=_reject_constant)
        block = payload["money_verdict"]
        assert block["ci_lower"] is None
        assert block["ci_lower_mean"] is None
        assert block["ci_lower_hl"] is None

    def test_every_float_the_ledger_writes_survives_a_strict_parser(self, tmp_path: Path) -> None:
        text = _write(tmp_path, _sample_money_result()).read_text(encoding="utf-8")
        payload = json.loads(text, parse_constant=_reject_constant)
        assert payload["money_verdict"]["ci_lower"] is not None

    def test_json_float_maps_only_the_non_finite_values(self) -> None:
        assert json_float(0.0) == 0.0
        assert json_float(-1234.5) == -1234.5
        assert json_float(math.inf) is None
        assert json_float(-math.inf) is None
        assert json_float(math.nan) is None

    def test_identity_carries_baseline_and_digest(self, tmp_path: Path) -> None:
        payload = json.loads(_write(tmp_path, _sample_money_result()).read_text(encoding="utf-8"))
        identity = payload["identity"]
        assert identity["candidate"] == "builtin:starter"
        assert identity["candidate_commit"] == "abc123"
        assert identity["opponent"] == "builtin:pass"
        assert identity["gate_type"] == "money"
        assert identity["extra_config"] == TINY_CONFIG
        assert identity["agent_config"] is None
        assert identity["baseline"] == "builtin:starter"
        assert identity["baseline_agent_config"] is None
        assert identity["opponent_digest"] is None

    def test_verdict_block_is_the_candidate_arms_win_rate_verdict(self, tmp_path: Path) -> None:
        result = _sample_money_result()
        payload = json.loads(_write(tmp_path, result).read_text(encoding="utf-8"))
        verdict = payload["verdict"]
        assert set(verdict) == {
            "n_games",
            "wins",
            "losses",
            "ties",
            "score",
            "rate",
            "ci_lower",
            "threshold",
            "passed",
            "any_candidate_crash",
        }
        assert verdict["n_games"] == 4
        assert verdict["threshold"] == 0.5
        assert verdict["passed"] is result.candidate_result.verdict.passed

    def test_per_seed_and_manifest_blocks(self, tmp_path: Path) -> None:
        payload = json.loads(_write(tmp_path, _sample_money_result()).read_text(encoding="utf-8"))
        assert payload["seed_manifest"] == {"seed_base": 5, "n_seeds": 2, "seeds": [5, 6]}
        assert [entry["seed"] for entry in payload["per_seed"]] == [5, 6]
        assert set(payload["per_seed"][0]) == {
            "seed",
            "candidate_money",
            "baseline_money",
            "delta",
        }


class TestSubmissionGateStaysHonest:
    def test_find_passing_promotion_ignores_a_passing_money_entry(self, tmp_path: Path) -> None:
        # TEETH-CHECK. This is the test that would have caught a widening of
        # the Kaggle submission precondition: `gate_type="money"` must never
        # satisfy `find_passing_promotion`, no matter what `verdict.passed`
        # says.
        gates = tmp_path / "gates"
        path = _write(tmp_path, _sample_money_result())
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["identity"]["candidate"] = "champion"
        # Also swap the opponent for a non-trivial one: `_sample_money_result`
        # uses "builtin:pass" for unrelated reasons (a cheap deterministic
        # bot), and issue #166 would otherwise exclude it here too, breaking
        # this test's positive control below for a reason unrelated to what
        # it is checking (the gate_type filter, not the opponent filter).
        payload["identity"]["opponent"] = "zoo:pass"
        payload["verdict"]["passed"] = True
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        assert find_passing_promotion(gates, "abc123") is None

        payload["identity"]["gate_type"] = "promotion"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        assert find_passing_promotion(gates, "abc123") == path

    def test_find_passing_promotion_does_not_keyerror_on_a_money_entry(
        self, tmp_path: Path
    ) -> None:
        gates = tmp_path / "gates"
        _write(tmp_path, _sample_money_result())
        legacy = {
            "schema_version": 1,
            "identity": {
                "candidate": "champion",
                "candidate_commit": "deadbeef",
                "opponent": "frozen:m2a",
                "gate_type": "promotion",
                "extra_config": None,
            },
            "verdict": {"passed": True},
            "seed_manifest": {"seed_base": 0, "n_seeds": 1, "seeds": [0]},
            "rows": [],
        }
        (gates / "2026-01-01T00-00-00Z-champion-vs-frozen_m2a-promotion.json").write_text(
            json.dumps(legacy, indent=2), encoding="utf-8"
        )
        assert find_passing_promotion(gates, "deadbeef") is not None


def _write_promotion_entry(
    gates_dir: Path, *, filename: str, candidate_sha: str, opponent: str
) -> Path:
    """A minimal, schema-legal ``gate_type == "promotion"`` entry, passing, for
    ``candidate_sha`` against ``opponent``. Issue #166 fixtures only need
    ``identity`` + ``verdict.passed``; see
    ``test_find_passing_promotion_does_not_keyerror_on_a_money_entry`` above
    for the precedent of a hand-built legacy-shaped entry.
    """
    gates_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "schema_version": 1,
        "identity": {
            "candidate": "champion",
            "candidate_commit": candidate_sha,
            "opponent": opponent,
            "gate_type": "promotion",
            "extra_config": None,
        },
        "verdict": {"passed": True},
        "seed_manifest": {"seed_base": 0, "n_seeds": 1, "seeds": [0]},
        "rows": [],
    }
    path = gates_dir / filename
    path.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return path


class TestFindPassingPromotionExcludesTrivialOpponents:
    """Issue #166: a promotion gate is a win-rate gate, and a `builtin:*` or
    `TUNABLE_SPECS` opponent is beaten at rate 1.0 (or is not an external
    result at all) regardless of the candidate's real strength. These are the
    acceptance-criteria fixtures, red before the opponent filter existed."""

    def test_refuses_a_sha_carrying_only_a_passing_builtin_starter_entry(
        self, tmp_path: Path
    ) -> None:
        # Acceptance criterion 1. This is the exact loophole named in the
        # issue: `builtin:starter` is a do-nothing baseline beaten at rate
        # 1.0 by every champion build in the corpus.
        gates = tmp_path / "gates"
        _write_promotion_entry(
            gates, filename="a.json", candidate_sha="cafef00d", opponent="builtin:starter"
        )
        assert find_passing_promotion(gates, "cafef00d") is None

    def test_refuses_a_sha_carrying_only_a_passing_tunable_spec_entry(self, tmp_path: Path) -> None:
        # The second, independently-occurring instance from the issue: an
        # opponent of "champion" is a same-codebase config-vs-config
        # comparison (TUNABLE_SPECS), not an external result.
        gates = tmp_path / "gates"
        _write_promotion_entry(
            gates, filename="a.json", candidate_sha="fbfc258", opponent="champion"
        )
        assert find_passing_promotion(gates, "fbfc258") is None

    def test_refuses_a_sha_carrying_only_a_passing_champion_unshelled_entry(
        self, tmp_path: Path
    ) -> None:
        gates = tmp_path / "gates"
        _write_promotion_entry(
            gates, filename="a.json", candidate_sha="fbfc258", opponent="champion-unshelled"
        )
        assert find_passing_promotion(gates, "fbfc258") is None

    def test_accepts_a_passing_entry_against_a_zoo_opponent(self, tmp_path: Path) -> None:
        # Acceptance criterion 2: the fix must not become a blanket refusal.
        # `zoo:*` is neither `builtin:*` nor a TUNABLE_SPECS value.
        gates = tmp_path / "gates"
        path = _write_promotion_entry(
            gates, filename="a.json", candidate_sha="deadbeef", opponent="zoo:pass"
        )
        assert find_passing_promotion(gates, "deadbeef") == path

    def test_accepts_a_passing_entry_against_a_frozen_opponent(self, tmp_path: Path) -> None:
        # `frozen:*` is `is_tunable()` for A/B-at-the-same-knob purposes, but
        # it is NOT a `TUNABLE_SPECS` member and it IS an external result —
        # explicitly not excluded (Acceptance criterion 2, Anti-scope).
        gates = tmp_path / "gates"
        path = _write_promotion_entry(
            gates, filename="a.json", candidate_sha="deadbeef", opponent="frozen:m3b_live_b6ce655"
        )
        assert find_passing_promotion(gates, "deadbeef") == path

    def test_falls_through_a_trivial_entry_to_find_a_real_one(self, tmp_path: Path) -> None:
        # The fix filters the candidate set; it does not just refuse
        # whichever entry glob() happens to return first.
        gates = tmp_path / "gates"
        _write_promotion_entry(
            gates,
            filename="2026-09-19T00-00-00Z-champion-vs-builtin_pass-promotion.json",
            candidate_sha="deadbeef",
            opponent="builtin:pass",
        )
        real = _write_promotion_entry(
            gates,
            filename="2026-09-19T00-00-01Z-champion-vs-zoo_pass-promotion.json",
            candidate_sha="deadbeef",
            opponent="zoo:pass",
        )
        assert find_passing_promotion(gates, "deadbeef") == real

    def test_refusal_reason_names_the_excluded_opponent(self, tmp_path: Path) -> None:
        # Acceptance criterion 3, verified by substring assertion.
        gates = tmp_path / "gates"
        _write_promotion_entry(
            gates, filename="a.json", candidate_sha="cafef00d", opponent="builtin:starter"
        )
        reason = promotion_refusal_reason(gates, "cafef00d")
        assert "builtin:starter" in reason
        assert "excluded" in reason

    def test_refusal_reason_names_every_excluded_opponent_when_more_than_one(
        self, tmp_path: Path
    ) -> None:
        gates = tmp_path / "gates"
        _write_promotion_entry(
            gates, filename="a.json", candidate_sha="cafef00d", opponent="builtin:starter"
        )
        _write_promotion_entry(
            gates, filename="b.json", candidate_sha="cafef00d", opponent="champion"
        )
        reason = promotion_refusal_reason(gates, "cafef00d")
        assert "builtin:starter" in reason
        assert "champion" in reason
        assert "excluded" in reason

    def test_refusal_reason_is_generic_when_nothing_matches_at_all(self, tmp_path: Path) -> None:
        # No candidate/sha match at all -- not "an entry existed but was
        # excluded" -- so the message must not claim an opponent was excluded.
        gates = tmp_path / "gates"
        _write_promotion_entry(
            gates, filename="a.json", candidate_sha="othersha", opponent="builtin:starter"
        )
        reason = promotion_refusal_reason(gates, "cafef00d")
        assert "excluded" not in reason
        assert "cafef00d" in reason


class TestWriteLedgerDidNotDrift:
    def test_write_ledger_output_matches_the_committed_corpus_shape(self, tmp_path: Path) -> None:
        from harness.gate import run_gate

        result = run_gate(
            candidate="builtin:starter",
            opponent="builtin:pass",
            n_seeds=1,
            seed_base=5,
            workers=1,
            extra_config=TINY_CONFIG,
        )
        fresh = json.loads(
            write_ledger(
                result, tmp_path, candidate_commit="abc123", timestamp="2026-08-14T09-30-00Z"
            ).read_text(encoding="utf-8")
        )

        committed = sorted((REPO_ROOT / "eval" / "gates").glob("*-promotion.json"))
        assert committed, "the committed gate corpus is the golden reference here"
        golden = json.loads(committed[-1].read_text(encoding="utf-8"))

        assert set(fresh) == set(golden)
        assert set(fresh["identity"]) >= set(golden["identity"])
        assert set(fresh["verdict"]) == set(golden["verdict"])
        assert set(fresh["seed_manifest"]) == set(golden["seed_manifest"])
        assert set(fresh["rows"][0]) == set(golden["rows"][0]) == ROW_KEYS


class TestCommittedMoneyCorpus:
    def test_every_committed_money_entry_carries_a_money_verdict_block(self) -> None:
        # Per-entry invariant, never a count pin: `eval/gates/` is append-only
        # and a `len(glob(...)) == N` assertion goes red on every legitimate
        # new run. Passes vacuously while no money entry has been committed.
        for path in sorted((REPO_ROOT / "eval" / "gates").glob("*-money.json")):
            entry = json.loads(path.read_text(encoding="utf-8"))
            assert entry["identity"]["gate_type"] == "money", path
            assert entry["identity"]["baseline"], path
            block = entry["money_verdict"]
            assert isinstance(block["passed"], bool), path
            assert block["n_seeds"] >= 8, path
            assert isinstance(block["vetoes"], list), path
            assert len(entry["per_seed"]) == block["n_seeds"], path
