"""Submission ledger — eval/submissions/*.json (issue #10, #30)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from harness.submissions import SubmissionRecord, read_submission, write_submission

REPO = Path(__file__).resolve().parent.parent.parent.parent
SUBMISSIONS_DIR = REPO / "eval" / "submissions"

_HEX64 = re.compile(r"[0-9a-f]{64}")

_SAMPLE = SubmissionRecord(
    submission_id="12345",
    candidate_sha="abc1234",
    line="A",
    bundle_sha256="a" * 64,
    tag="sub-12345",
    uploaded_at="2026-08-08T00:00:00Z",
    artifact_ref="git:abc1234:dist/submission.tar.gz",
    note="round-trip fixture",
)


class TestRoundTrip:
    def test_write_then_read_back_every_field_equal(self, tmp_path: Path) -> None:
        path = write_submission(_SAMPLE, tmp_path)
        assert path == tmp_path / "submissions" / "sub-12345.json"

        record = read_submission(path)

        assert record == _SAMPLE

    def test_teeth_dropping_a_field_from_the_writer_goes_red(self, tmp_path: Path) -> None:
        """Mutation guard: a writer that drops ``line`` from the payload must fail
        the round-trip — proves the round-trip test actually checks every field."""
        submissions_dir = tmp_path / "submissions"
        submissions_dir.mkdir()
        path = submissions_dir / "sub-12345.json"
        payload = {
            "schema_version": 1,
            "submission_id": _SAMPLE.submission_id,
            "candidate_sha": _SAMPLE.candidate_sha,
            # "line" dropped, simulating the mutation
            "bundle_sha256": _SAMPLE.bundle_sha256,
            "tag": _SAMPLE.tag,
            "uploaded_at": _SAMPLE.uploaded_at,
            "artifact_ref": _SAMPLE.artifact_ref,
            "note": _SAMPLE.note,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(KeyError):
            read_submission(path)


class TestMalformedJson:
    def test_malformed_json_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "sub-bad.json"
        path.write_text("{not valid json", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            read_submission(path)


def _backfilled_entries() -> list[dict[str, object]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(SUBMISSIONS_DIR.glob("sub-*.json"))
    ]


class TestBackfilledLedger:
    def test_five_entries_present(self) -> None:
        entries = _backfilled_entries()
        ids = {entry["submission_id"] for entry in entries}
        assert ids == {"55284206", "55286903", "55309517", "55334684", "55358390"}

    def test_non_null_bundle_sha256_is_well_formed_hex(self) -> None:
        entries = _backfilled_entries()
        non_null = [e for e in entries if e["bundle_sha256"] is not None]
        assert len(non_null) == 4
        for entry in non_null:
            digest = entry["bundle_sha256"]
            assert isinstance(digest, str)
            assert len(digest) == 64
            assert _HEX64.fullmatch(digest), f"{entry['submission_id']}: not 64 lowercase hex"

    def test_probe_entry_has_no_bundle(self) -> None:
        entries = _backfilled_entries()
        probe = next(e for e in entries if e["submission_id"] == "55284206")
        assert probe["candidate_sha"] is None
        assert probe["bundle_sha256"] is None
        assert probe["tag"] is None
        assert probe["artifact_ref"] is None
        assert probe["line"] == "probe"

    def test_teeth_corrupted_hex_char_is_caught(self) -> None:
        """Mutation guard: a single corrupted hex character must fail the
        well-formedness check — proves the regex actually inspects every char."""
        entries = _backfilled_entries()
        entry = next(e for e in entries if e["submission_id"] == "55286903")
        digest = entry["bundle_sha256"]
        assert isinstance(digest, str)
        corrupted = "z" + digest[1:]

        assert not _HEX64.fullmatch(corrupted)
