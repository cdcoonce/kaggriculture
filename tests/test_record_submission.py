"""Submission ledger CLI: cross-check + same-line eviction guard (epic #21, issue #41)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness.submissions import read_submission  # noqa: E402

from record_submission import main, read_bundle_sha256, read_line_entries  # noqa: E402


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


def _write_submission_entry(
    submissions_dir: Path, *, submission_id: str, line: str, uploaded_at: str, tag: str
) -> None:
    submissions_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "submission_id": submission_id,
        "candidate_sha": "priorsha",
        "line": line,
        "bundle_sha256": None,
        "tag": tag,
        "uploaded_at": uploaded_at,
        "artifact_ref": None,
        "note": None,
    }
    (submissions_dir / f"sub-{submission_id}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


# --- unit helpers -------------------------------------------------------------


def test_read_bundle_sha256_parses_manifest_line(tmp_path: Path) -> None:
    digest = "deadbeefcafe" + "0" * 52
    manifest = tmp_path / "MANIFEST.txt"
    manifest.write_text(f"sha256 {digest}  submission.tar.gz\n")
    assert read_bundle_sha256(manifest) == digest


def test_read_line_entries_filters_by_line(tmp_path: Path) -> None:
    submissions_dir = tmp_path / "submissions"
    _write_submission_entry(
        submissions_dir,
        submission_id="1",
        line="A",
        uploaded_at="2026-01-01T00:00:00Z",
        tag="sub-1",
    )
    _write_submission_entry(
        submissions_dir,
        submission_id="2",
        line="B",
        uploaded_at="2026-01-01T00:00:00Z",
        tag="sub-2",
    )
    entries = read_line_entries(submissions_dir, "A")
    assert [e.submission_id for e in entries] == ["1"]


def test_read_line_entries_empty_when_dir_missing(tmp_path: Path) -> None:
    assert read_line_entries(tmp_path / "nope", "A") == []


# --- main(): cross-check guard -------------------------------------------------


def test_main_refuses_when_no_passing_promotion(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gates_dir = tmp_path / "gates"
    eval_dir = tmp_path / "eval"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="othersha", passed=True)

    rc = main(
        [
            "--submission-id",
            "1",
            "--candidate-sha",
            "deadbeef",
            "--line",
            "A",
            "--uploaded-at",
            "2026-08-09T00:00:00Z",
            "--bundle-sha256",
            "ab" * 32,
            "--gates-dir",
            str(gates_dir),
            "--eval-dir",
            str(eval_dir),
        ]
    )
    captured = capsys.readouterr()
    assert rc != 0
    assert captured.out == ""
    assert "deadbeef" in captured.err
    assert not (eval_dir / "submissions").exists()


# --- main(): same-line eviction guard ------------------------------------------


def test_main_refuses_eviction_without_confirm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gates_dir = tmp_path / "gates"
    eval_dir = tmp_path / "eval"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)
    _write_submission_entry(
        eval_dir / "submissions",
        submission_id="111",
        line="A",
        uploaded_at="2026-08-01T00:00:00Z",
        tag="sub-111",
    )

    rc = main(
        [
            "--submission-id",
            "222",
            "--candidate-sha",
            "deadbeef",
            "--line",
            "A",
            "--uploaded-at",
            "2026-08-09T00:00:00Z",
            "--bundle-sha256",
            "ab" * 32,
            "--gates-dir",
            str(gates_dir),
            "--eval-dir",
            str(eval_dir),
        ]
    )
    captured = capsys.readouterr()
    assert rc != 0
    assert "111" in captured.out + captured.err
    assert not (eval_dir / "submissions" / "sub-222.json").exists()


def test_main_succeeds_with_confirm_evict_and_prefixes_note(tmp_path: Path) -> None:
    gates_dir = tmp_path / "gates"
    eval_dir = tmp_path / "eval"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)
    _write_submission_entry(
        eval_dir / "submissions",
        submission_id="111",
        line="A",
        uploaded_at="2026-08-01T00:00:00Z",
        tag="sub-111",
    )

    rc = main(
        [
            "--submission-id",
            "222",
            "--candidate-sha",
            "deadbeef",
            "--line",
            "A",
            "--uploaded-at",
            "2026-08-09T00:00:00Z",
            "--bundle-sha256",
            "ab" * 32,
            "--note",
            "manual note",
            "--gates-dir",
            str(gates_dir),
            "--eval-dir",
            str(eval_dir),
            "--confirm-evict",
        ]
    )
    assert rc == 0

    written = eval_dir / "submissions" / "sub-222.json"
    assert written.exists()
    record = read_submission(written)
    assert record.note == "[evicts 111] manual note"


def test_main_evict_note_prefix_only_when_note_omitted(tmp_path: Path) -> None:
    gates_dir = tmp_path / "gates"
    eval_dir = tmp_path / "eval"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)
    _write_submission_entry(
        eval_dir / "submissions",
        submission_id="111",
        line="A",
        uploaded_at="2026-08-01T00:00:00Z",
        tag="sub-111",
    )

    rc = main(
        [
            "--submission-id",
            "222",
            "--candidate-sha",
            "deadbeef",
            "--line",
            "A",
            "--uploaded-at",
            "2026-08-09T00:00:00Z",
            "--bundle-sha256",
            "ab" * 32,
            "--gates-dir",
            str(gates_dir),
            "--eval-dir",
            str(eval_dir),
            "--confirm-evict",
        ]
    )
    assert rc == 0
    record = read_submission(eval_dir / "submissions" / "sub-222.json")
    assert record.note == "[evicts 111] "


# --- main(): end-to-end round-trip on an empty line ----------------------------


def test_main_succeeds_end_to_end_round_trip(tmp_path: Path) -> None:
    gates_dir = tmp_path / "gates"
    eval_dir = tmp_path / "eval"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)

    rc = main(
        [
            "--submission-id",
            "999",
            "--candidate-sha",
            "deadbeef",
            "--line",
            "A",
            "--uploaded-at",
            "2026-08-09T12:00:00Z",
            "--bundle-sha256",
            "cd" * 32,
            "--tag",
            "sub-999",
            "--artifact-ref",
            "git:deadbeef:dist/submission.tar.gz",
            "--note",
            "first upload on this line",
            "--gates-dir",
            str(gates_dir),
            "--eval-dir",
            str(eval_dir),
        ]
    )
    assert rc == 0

    written = eval_dir / "submissions" / "sub-999.json"
    record = read_submission(written)
    assert record.submission_id == "999"
    assert record.candidate_sha == "deadbeef"
    assert record.line == "A"
    assert record.bundle_sha256 == "cd" * 32
    assert record.tag == "sub-999"
    assert record.uploaded_at == "2026-08-09T12:00:00Z"
    assert record.artifact_ref == "git:deadbeef:dist/submission.tar.gz"
    assert record.note == "first upload on this line"


def test_main_defaults_tag_and_artifact_ref_when_omitted(tmp_path: Path) -> None:
    gates_dir = tmp_path / "gates"
    eval_dir = tmp_path / "eval"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)

    rc = main(
        [
            "--submission-id",
            "999",
            "--candidate-sha",
            "deadbeef",
            "--line",
            "A",
            "--uploaded-at",
            "2026-08-09T12:00:00Z",
            "--bundle-sha256",
            "cd" * 32,
            "--gates-dir",
            str(gates_dir),
            "--eval-dir",
            str(eval_dir),
        ]
    )
    assert rc == 0
    record = read_submission(eval_dir / "submissions" / "sub-999.json")
    assert record.tag == "sub-999"
    assert record.artifact_ref == "git:deadbeef:dist/submission.tar.gz"
    assert record.note is None


# --- bundle-sha256 fallback from dist/MANIFEST.txt -----------------------------


def test_main_falls_back_to_manifest_when_bundle_sha256_omitted(tmp_path: Path) -> None:
    gates_dir = tmp_path / "gates"
    eval_dir = tmp_path / "eval"
    digest = "deadbeefcafe" + "0" * 52
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    manifest = dist_dir / "MANIFEST.txt"
    manifest.write_text(f"sha256 {digest}  submission.tar.gz\n")
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)

    rc = main(
        [
            "--submission-id",
            "999",
            "--candidate-sha",
            "deadbeef",
            "--line",
            "A",
            "--uploaded-at",
            "2026-08-09T12:00:00Z",
            "--gates-dir",
            str(gates_dir),
            "--eval-dir",
            str(eval_dir),
            "--manifest",
            str(manifest),
        ]
    )
    assert rc == 0
    record = read_submission(eval_dir / "submissions" / "sub-999.json")
    assert record.bundle_sha256 == digest
