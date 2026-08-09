"""Kaggle submission ledger — every upload appends a committed JSON record.

Companion to ``eval/gates/`` (``harness.ledger``): where a gate ledger entry
records a local match, a submission ledger entry records an actual Kaggle
upload — the candidate SHA, the bundle digest, and the ``sub-<id>`` tag that
names it (``eval/submissions/README.md``, issue #10 / #30).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SubmissionRecord:
    """One Kaggle submission, as described to the harness by the repo owner."""

    submission_id: str
    candidate_sha: str | None
    line: str
    bundle_sha256: str | None
    tag: str | None
    uploaded_at: str
    artifact_ref: str | None
    note: str | None


def write_submission(record: SubmissionRecord, eval_dir: Path) -> Path:
    """Write ``record`` as a JSON ledger entry and return the written path.

    Deterministic filename (``sub-<id>.json``); ``uploaded_at`` is supplied
    by the caller rather than generated here.
    """
    submissions_dir = eval_dir / "submissions"
    submissions_dir.mkdir(parents=True, exist_ok=True)
    path = submissions_dir / f"sub-{record.submission_id}.json"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "submission_id": record.submission_id,
        "candidate_sha": record.candidate_sha,
        "line": record.line,
        "bundle_sha256": record.bundle_sha256,
        "tag": record.tag,
        "uploaded_at": record.uploaded_at,
        "artifact_ref": record.artifact_ref,
        "note": record.note,
    }

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def read_submission(path: Path) -> SubmissionRecord:
    """Read a ``sub-<id>.json`` ledger entry back into a ``SubmissionRecord``."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SubmissionRecord(
        submission_id=payload["submission_id"],
        candidate_sha=payload["candidate_sha"],
        line=payload["line"],
        bundle_sha256=payload["bundle_sha256"],
        tag=payload["tag"],
        uploaded_at=payload["uploaded_at"],
        artifact_ref=payload["artifact_ref"],
        note=payload["note"],
    )
