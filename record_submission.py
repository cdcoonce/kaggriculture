#!/usr/bin/env python3
"""Submission ledger recorder (epic #21, issue #41).

Run by a human after actually executing the `kaggle competitions submit`
command printed by submit.py and receiving a Kaggle-assigned submission ID
back. Refuses to write a ledger entry (eval/submissions/) unless the
candidate SHA has a matching passing champion promotion entry in
eval/gates/, and refuses to evict an already-occupied line without
--confirm-evict.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness.ledger import find_passing_promotion
from harness.submissions import SubmissionRecord, read_submission, write_submission

EVAL_DIR = Path("eval")
GATES_DIR = EVAL_DIR / "gates"
SUBMISSIONS_DIR = EVAL_DIR / "submissions"
MANIFEST_PATH = Path("dist/MANIFEST.txt")


def parse_bundle_sha256(manifest_path: Path) -> str:
    """Parse the sha256 hex digest out of a MANIFEST.txt line written by build.py."""
    return manifest_path.read_text(encoding="utf-8").split()[1]


def find_existing_line_entries(submissions_dir: Path, line: str) -> list[SubmissionRecord]:
    """Return existing submission records for ``line``, read via #30's reader."""
    return [
        record
        for path in sorted(submissions_dir.glob("*.json"))
        if (record := read_submission(path)).line == line
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission-id", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--line", required=True)
    parser.add_argument("--bundle-sha256")
    parser.add_argument("--tag")
    parser.add_argument("--uploaded-at", required=True)
    parser.add_argument("--artifact-ref")
    parser.add_argument("--note")
    parser.add_argument("--confirm-evict", action="store_true")
    args = parser.parse_args(argv)

    if find_passing_promotion(GATES_DIR, args.candidate_sha) is None:
        print(
            f"no passing champion promotion entry found for candidate-sha "
            f"{args.candidate_sha!r} in {GATES_DIR}",
            file=sys.stderr,
        )
        return 1

    note = args.note
    existing = find_existing_line_entries(SUBMISSIONS_DIR, args.line)
    if existing:
        prior = max(existing, key=lambda r: r.uploaded_at)
        if not args.confirm_evict:
            print(
                f"line {args.line!r} already has submission_id={prior.submission_id!r} "
                f"(tag={prior.tag!r}); pass --confirm-evict to evict it",
                file=sys.stderr,
            )
            return 1
        note = f"[evicts {prior.submission_id}] " + (args.note if args.note is not None else "")

    bundle_sha256 = args.bundle_sha256
    if bundle_sha256 is None:
        bundle_sha256 = parse_bundle_sha256(MANIFEST_PATH)

    tag = args.tag if args.tag is not None else f"sub-{args.submission_id}"
    artifact_ref = (
        args.artifact_ref
        if args.artifact_ref is not None
        else f"git:{args.candidate_sha}:dist/submission.tar.gz"
    )

    record = SubmissionRecord(
        submission_id=args.submission_id,
        candidate_sha=args.candidate_sha,
        line=args.line,
        bundle_sha256=bundle_sha256,
        tag=tag,
        uploaded_at=args.uploaded_at,
        artifact_ref=artifact_ref,
        note=note,
    )
    path = write_submission(record, EVAL_DIR)
    print(str(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
