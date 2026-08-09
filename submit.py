#!/usr/bin/env python3
"""Bundle-exec submission gate, run with no environment-creation step (epic #21, issue #31).

Extracts the built submission tarball, then refuses to print a submit
command unless the extracted bundle clears four checks in order: the
import allowlist, the import-time budget, a rehearsal run directly
against the interpreter already on PATH, and a matching passing
promotion entry in the eval/gates/ ledger. Read-only — never writes to
eval/gates/, eval/submissions/, or Kaggle; only ever prints the
`kaggle competitions submit` command for a human to run.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from harness.importlaw import IMPORT_TIME_BUDGET_S, find_violations
from harness.ledger import find_passing_promotion


def extract_bundle(bundle_path: Path, dest: Path) -> Path:
    """Unpack ``bundle_path`` into ``dest`` and return ``dest``."""
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(bundle_path) as tar:
        tar.extractall(dest, filter="data")
    return dest


def check_import_allowlist(agent_dir: Path) -> list[tuple[Path, str]]:
    """Return import-allowlist violations in the extracted ``agent/`` tree."""
    return find_violations(agent_dir)


def check_import_time_budget(extracted_root: Path) -> float:
    """Return the elapsed seconds to import ``agent.main`` from the extracted bundle."""
    code = "import time; t = time.perf_counter(); import agent.main; print(time.perf_counter() - t)"
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(extracted_root),
    )
    return float(out.stdout.strip())


def run_rehearsal(extracted_root: Path, seeds: list[int]) -> bool:
    """Play a mirror match at every seed against the interpreter already on PATH;
    return False on the first crash."""
    from kaggle_environments import make

    main_path = str(extracted_root / "main.py")
    for seed in seeds:
        env = make("kaggriculture", configuration={"seed": seed}, debug=True)
        try:
            env.run([main_path, main_path])
        except Exception:
            return False
        if [s.status for s in env.steps[-1]] != ["DONE", "DONE"]:
            return False
    return True


def build_submit_command(bundle_path: Path, candidate_sha: str) -> str:
    return f'kaggle competitions submit kaggriculture -f {bundle_path} -m "{candidate_sha}"'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--bundle", default="dist/submission.tar.gz")
    parser.add_argument("--gates-dir", default="eval/gates")
    parser.add_argument("--rehearsal-seeds", type=int, default=100)
    parser.add_argument("--seed-base", type=int, default=90000)
    args = parser.parse_args(argv)

    bundle_path = Path(args.bundle)
    with tempfile.TemporaryDirectory() as tmp:
        extracted_root = extract_bundle(bundle_path, Path(tmp) / "extracted")
        agent_dir = extracted_root / "agent"

        violations = check_import_allowlist(agent_dir)
        if violations:
            for path, module in violations:
                print(f"import-allowlist violation: {path} imports {module!r}", file=sys.stderr)
            return 1

        elapsed = check_import_time_budget(extracted_root)
        if elapsed >= IMPORT_TIME_BUDGET_S:
            print(
                f"import-time budget exceeded: {elapsed:.2f}s >= {IMPORT_TIME_BUDGET_S}s",
                file=sys.stderr,
            )
            return 1

        seeds = list(range(args.seed_base, args.seed_base + args.rehearsal_seeds))
        if not run_rehearsal(extracted_root, seeds):
            print(
                "rehearsal failed: a mirror-match episode did not reach [DONE, DONE]",
                file=sys.stderr,
            )
            return 1

        promotion = find_passing_promotion(Path(args.gates_dir), args.candidate_sha)
        if promotion is None:
            print(
                f"no passing champion promotion found in {args.gates_dir} "
                f"for candidate {args.candidate_sha}",
                file=sys.stderr,
            )
            return 1

    print(build_submit_command(bundle_path, args.candidate_sha))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
