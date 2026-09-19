#!/usr/bin/env python3
"""Record a Kaggle submission ledger entry (epic #21, issue #41).

Run by a human after actually executing the ``kaggle competitions submit``
command printed by ``submit.py`` and receiving a Kaggle-assigned
``submission_id`` back. Refuses to write unless ``--candidate-sha`` matches a
passing champion promotion entry in ``eval/gates/``, and refuses to evict an
existing same-line entry in ``eval/submissions/`` without ``--confirm-evict``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness.ledger import find_passing_promotion, promotion_refusal_reason
from harness.submissions import SubmissionRecord, read_submission, write_submission


def read_bundle_sha256(manifest_path: Path) -> str:
    """Parse the ``sha256 <hex>  submission.tar.gz`` line ``build.py`` writes."""
    return manifest_path.read_text().split()[1]


def read_line_entries(submissions_dir: Path, line: str) -> list[SubmissionRecord]:
    """Return every existing ``eval/submissions/`` entry on ``line``, read-only."""
    if not submissions_dir.exists():
        return []
    entries = []
    for path in sorted(submissions_dir.glob("*.json")):
        record = read_submission(path)
        if record.line == line:
            entries.append(record)
    return entries


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
    parser.add_argument("--gates-dir", default="eval/gates")
    parser.add_argument("--eval-dir", default="eval")
    parser.add_argument("--manifest", default="dist/MANIFEST.txt")
    args = parser.parse_args(argv)

    gates_dir = Path(args.gates_dir)
    promotion = find_passing_promotion(gates_dir, args.candidate_sha)
    if promotion is None:
        print(promotion_refusal_reason(gates_dir, args.candidate_sha), file=sys.stderr)
        return 1

    bundle_sha256 = args.bundle_sha256
    if bundle_sha256 is None:
        bundle_sha256 = read_bundle_sha256(Path(args.manifest))

    eval_dir = Path(args.eval_dir)
    submissions_dir = eval_dir / "submissions"
    existing = read_line_entries(submissions_dir, args.line)

    note = args.note
    if existing:
        latest = max(existing, key=lambda r: r.uploaded_at)
        if not args.confirm_evict:
            print(
                f"line {args.line!r} already has submission {latest.submission_id} "
                f"(tag={latest.tag}) uploaded at {latest.uploaded_at}; "
                "pass --confirm-evict to evict it",
                file=sys.stderr,
            )
            return 1
        note = f"[evicts {latest.submission_id}] " + (args.note if args.note is not None else "")

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
    path = write_submission(record, eval_dir)
    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
