"""Submission ledger recorder CLI (epic #21, issue #41)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from harness.submissions import SubmissionRecord, read_submission, write_submission

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from record_submission import (  # noqa: E402
    find_existing_line_entries,
    main,
    parse_bundle_sha256,
)


def _write_promotion_entry(
    gates_dir: Path, *, filename: str, candidate_sha: str, passed: bool
) -> None:
    gates_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "identity": {
            "candidate": "champion",
            "candidate_commit": candidate_sha,
            "opponent": "builtin_pass",
            "gate_type": "promotion",
            "extra_config": None,
        },
        "verdict": {
            "n_games": 10,
            "wins": 10,
            "losses": 0,
            "ties": 0,
            "score": 10.0,
            "rate": 1.0,
            "ci_lower": 0.9,
            "threshold": 0.5,
            "passed": passed,
            "any_candidate_crash": False,
        },
        "seed_manifest": {"seed_base": 1, "n_seeds": 10, "seeds": list(range(1, 11))},
        "rows": [],
    }
    (gates_dir / filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")


_PRIOR = SubmissionRecord(
    submission_id="111",
    candidate_sha="priorsha",
    line="A",
    bundle_sha256="priorsha256",
    tag="sub-111",
    uploaded_at="2026-08-01T00:00:00Z",
    artifact_ref="git:priorsha:dist/submission.tar.gz",
    note=None,
)


# --- unit tests for the individual functions --------------------------------


def test_parse_bundle_sha256_reads_hex_token(tmp_path: Path) -> None:
    digest = "ab" * 32
    manifest = tmp_path / "MANIFEST.txt"
    manifest.write_text(f"sha256 {digest}  submission.tar.gz\n")
    assert parse_bundle_sha256(manifest) == digest


def test_find_existing_line_entries_filters_by_line(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    write_submission(_PRIOR, eval_dir)
    write_submission(
        SubmissionRecord(
            submission_id="222",
            candidate_sha="othersha",
            line="B",
            bundle_sha256=None,
            tag=None,
            uploaded_at="2026-08-02T00:00:00Z",
            artifact_ref=None,
            note=None,
        ),
        eval_dir,
    )
    found = find_existing_line_entries(eval_dir / "submissions", "A")
    assert [r.submission_id for r in found] == ["111"]


def test_find_existing_line_entries_empty_dir(tmp_path: Path) -> None:
    assert find_existing_line_entries(tmp_path / "eval" / "submissions", "A") == []


# --- main() end-to-end and refusal paths -------------------------------------


def test_main_refuses_without_passing_promotion(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    gates_dir = tmp_path / "eval" / "gates"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="othersha", passed=True)

    rc = main(
        [
            "--submission-id",
            "999",
            "--candidate-sha",
            "deadbeef",
            "--line",
            "A",
            "--bundle-sha256",
            "abc123",
            "--uploaded-at",
            "2026-08-09T00:00:00Z",
        ]
    )
    captured = capsys.readouterr()
    assert rc != 0
    assert not (tmp_path / "eval" / "submissions").exists()
    assert "deadbeef" in captured.err


def test_main_refuses_on_occupied_line_without_confirm(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    gates_dir = tmp_path / "eval" / "gates"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)
    write_submission(_PRIOR, tmp_path / "eval")

    rc = main(
        [
            "--submission-id",
            "222",
            "--candidate-sha",
            "deadbeef",
            "--line",
            "A",
            "--bundle-sha256",
            "newsha256",
            "--uploaded-at",
            "2026-08-09T00:00:00Z",
        ]
    )
    captured = capsys.readouterr()
    assert rc != 0
    assert not (tmp_path / "eval" / "submissions" / "sub-222.json").exists()
    assert "111" in captured.out + captured.err


def test_main_succeeds_with_confirm_evict(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    gates_dir = tmp_path / "eval" / "gates"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)
    write_submission(_PRIOR, tmp_path / "eval")

    rc = main(
        [
            "--submission-id",
            "222",
            "--candidate-sha",
            "deadbeef",
            "--line",
            "A",
            "--bundle-sha256",
            "newsha256",
            "--uploaded-at",
            "2026-08-09T00:00:00Z",
            "--confirm-evict",
            "--note",
            "M2c cycle",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    written_path = Path(captured.out.strip())
    assert written_path == Path("eval/submissions/sub-222.json")
    record = read_submission(written_path)
    assert record.note == "[evicts 111] M2c cycle"


def test_main_succeeds_with_confirm_evict_no_note(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    gates_dir = tmp_path / "eval" / "gates"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)
    write_submission(_PRIOR, tmp_path / "eval")

    rc = main(
        [
            "--submission-id",
            "222",
            "--candidate-sha",
            "deadbeef",
            "--line",
            "A",
            "--bundle-sha256",
            "newsha256",
            "--uploaded-at",
            "2026-08-09T00:00:00Z",
            "--confirm-evict",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    record = read_submission(Path(captured.out.strip()))
    assert record.note == "[evicts 111] "


def test_main_succeeds_end_to_end_round_trip(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    gates_dir = tmp_path / "eval" / "gates"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)

    rc = main(
        [
            "--submission-id",
            "333",
            "--candidate-sha",
            "deadbeef",
            "--line",
            "B",
            "--bundle-sha256",
            "cafef00d",
            "--tag",
            "custom-tag",
            "--uploaded-at",
            "2026-08-09T01:02:03Z",
            "--artifact-ref",
            "git:deadbeef:dist/submission.tar.gz",
            "--note",
            "manual test",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0

    written_path = Path(captured.out.strip())
    assert written_path == Path("eval/submissions/sub-333.json")
    record = read_submission(written_path)
    assert record == SubmissionRecord(
        submission_id="333",
        candidate_sha="deadbeef",
        line="B",
        bundle_sha256="cafef00d",
        tag="custom-tag",
        uploaded_at="2026-08-09T01:02:03Z",
        artifact_ref="git:deadbeef:dist/submission.tar.gz",
        note="manual test",
    )


def test_main_applies_defaults_when_optional_args_omitted(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    gates_dir = tmp_path / "eval" / "gates"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    digest = "deadbeefcafe" + "0" * 52
    (dist_dir / "MANIFEST.txt").write_text(f"sha256 {digest}  submission.tar.gz\n")

    rc = main(
        [
            "--submission-id",
            "444",
            "--candidate-sha",
            "deadbeef",
            "--line",
            "C",
            "--uploaded-at",
            "2026-08-09T02:00:00Z",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    record = read_submission(Path(captured.out.strip()))
    assert record.bundle_sha256 == digest
    assert record.tag == "sub-444"
    assert record.artifact_ref == "git:deadbeef:dist/submission.tar.gz"
    assert record.note is None
