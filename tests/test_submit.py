"""Venv-free bundle-exec submission gate (epic #21, issue #31)."""

from __future__ import annotations

import io
import json
import re
import sys
import tarfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness.importlaw import IMPORT_TIME_BUDGET_S  # noqa: E402

from build import ENTRY  # noqa: E402
from submit import (  # noqa: E402
    build_submit_command,
    check_import_allowlist,
    check_import_time_budget,
    extract_bundle,
    main,
    run_rehearsal,
)

PASS_MAIN = (
    'def agent(obs, config=None):\n    return {"farmer": ["PASS"], "hands": [], "market": []}\n'
)
PASS_AGENT_FILES = {"__init__.py": "", "main.py": PASS_MAIN}
BAD_IMPORT_AGENT_FILES = {"__init__.py": "import pandas\n", "main.py": PASS_MAIN}
SLOW_IMPORT_AGENT_FILES = {"__init__.py": "import time\ntime.sleep(2)\n", "main.py": PASS_MAIN}
CRASH_AGENT_FILES = {
    "__init__.py": "",
    "main.py": (
        "def agent(obs, config=None):\n"
        '    if obs["step"] == 3:\n'
        '        raise RuntimeError("boom")\n'
        '    return {"farmer": ["PASS"], "hands": [], "market": []}\n'
    ),
}


@pytest.fixture(autouse=True)
def _fresh_agent_import_cache():
    """Different fixture bundles share the top-level ``agent`` package name; without
    this, sys.modules caches the first-loaded bundle's agent.main across tests run in
    the same process (never an issue in production, where one process handles one
    bundle)."""

    def purge() -> None:
        for name in [n for n in sys.modules if n == "agent" or n.startswith("agent.")]:
            del sys.modules[name]

    purge()
    yield
    purge()


def _build_fixture_bundle(dest_tar: Path, agent_files: dict[str, str]) -> Path:
    """Tar build.ENTRY as main.py plus ``agent_files`` under agent/, mirroring build.py's layout."""
    with tarfile.open(dest_tar, "w:gz") as tar:

        def add_bytes(name: str, data: bytes) -> None:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        add_bytes("main.py", ENTRY.encode())
        for relname, content in agent_files.items():
            add_bytes(f"agent/{relname}", content.encode())
    return dest_tar


def _write_promotion_entry(
    gates_dir: Path,
    *,
    filename: str,
    candidate_sha: str,
    passed: bool,
    opponent: str = "builtin_pass",
) -> None:
    gates_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "identity": {
            "candidate": "champion",
            "candidate_commit": candidate_sha,
            "opponent": opponent,
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


# --- unit tests for the individual functions --------------------------------


def test_extract_bundle_lays_out_main_and_agent(tmp_path: Path) -> None:
    bundle = _build_fixture_bundle(tmp_path / "bundle.tar.gz", PASS_AGENT_FILES)
    dest = extract_bundle(bundle, tmp_path / "extracted")
    assert (dest / "main.py").read_text() == ENTRY
    assert (dest / "agent" / "main.py").read_text() == PASS_MAIN


def test_check_import_allowlist_flags_violation(tmp_path: Path) -> None:
    """Teeth-check: applied through the submit.py wrapper, not find_violations directly."""
    bad = tmp_path / "sneaky.py"
    bad.write_text("import pandas\nfrom torch import nn\n")
    flagged = {name for _, name in check_import_allowlist(tmp_path)}
    assert flagged == {"pandas", "torch"}


def test_check_import_allowlist_clean_tree(tmp_path: Path) -> None:
    bundle = _build_fixture_bundle(tmp_path / "bundle.tar.gz", PASS_AGENT_FILES)
    dest = extract_bundle(bundle, tmp_path / "extracted")
    assert check_import_allowlist(dest / "agent") == []


def test_check_import_time_budget_within_budget(tmp_path: Path) -> None:
    bundle = _build_fixture_bundle(tmp_path / "bundle.tar.gz", PASS_AGENT_FILES)
    dest = extract_bundle(bundle, tmp_path / "extracted")
    elapsed = check_import_time_budget(dest)
    assert elapsed < IMPORT_TIME_BUDGET_S


def test_build_submit_command_formats_expected_string() -> None:
    cmd = build_submit_command(Path("dist/submission.tar.gz"), "abc123")
    assert cmd == 'kaggle competitions submit kaggriculture -f dist/submission.tar.gz -m "abc123"'


@pytest.mark.slow
def test_run_rehearsal_true_for_passing_agent(tmp_path: Path) -> None:
    bundle = _build_fixture_bundle(tmp_path / "bundle.tar.gz", PASS_AGENT_FILES)
    dest = extract_bundle(bundle, tmp_path / "extracted")
    assert run_rehearsal(dest, [1, 2]) is True


@pytest.mark.slow
def test_run_rehearsal_false_on_crash(tmp_path: Path) -> None:
    bundle = _build_fixture_bundle(tmp_path / "bundle.tar.gz", CRASH_AGENT_FILES)
    dest = extract_bundle(bundle, tmp_path / "extracted")
    assert run_rehearsal(dest, [1]) is False


# --- main() end-to-end and refusal paths -------------------------------------


def test_main_refuses_on_import_allowlist_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _build_fixture_bundle(tmp_path / "bundle.tar.gz", BAD_IMPORT_AGENT_FILES)
    gates_dir = tmp_path / "gates"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)

    rc = main(
        [
            "--candidate-sha",
            "deadbeef",
            "--bundle",
            str(bundle),
            "--gates-dir",
            str(gates_dir),
        ]
    )
    captured = capsys.readouterr()
    assert rc != 0
    assert captured.out == ""
    assert "pandas" in captured.err


@pytest.mark.slow
def test_main_refuses_on_import_time_budget(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _build_fixture_bundle(tmp_path / "bundle.tar.gz", SLOW_IMPORT_AGENT_FILES)
    gates_dir = tmp_path / "gates"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)

    rc = main(
        [
            "--candidate-sha",
            "deadbeef",
            "--bundle",
            str(bundle),
            "--gates-dir",
            str(gates_dir),
        ]
    )
    captured = capsys.readouterr()
    assert rc != 0
    assert captured.out == ""
    assert "budget" in captured.err


@pytest.mark.slow
def test_main_refuses_on_rehearsal_crash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _build_fixture_bundle(tmp_path / "bundle.tar.gz", CRASH_AGENT_FILES)
    gates_dir = tmp_path / "gates"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)

    rc = main(
        [
            "--candidate-sha",
            "deadbeef",
            "--bundle",
            str(bundle),
            "--gates-dir",
            str(gates_dir),
            "--rehearsal-seeds",
            "1",
            "--seed-base",
            "1",
        ]
    )
    captured = capsys.readouterr()
    assert rc != 0
    assert captured.out == ""
    assert "rehearsal" in captured.err


@pytest.mark.slow
def test_main_refuses_on_missing_promotion_ledger_entry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _build_fixture_bundle(tmp_path / "bundle.tar.gz", PASS_AGENT_FILES)
    gates_dir = tmp_path / "gates"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="othersha", passed=True)

    rc = main(
        [
            "--candidate-sha",
            "deadbeef",
            "--bundle",
            str(bundle),
            "--gates-dir",
            str(gates_dir),
            "--rehearsal-seeds",
            "1",
            "--seed-base",
            "1",
        ]
    )
    captured = capsys.readouterr()
    assert rc != 0
    assert captured.out == ""
    assert "deadbeef" in captured.err


@pytest.mark.slow
def test_main_refuses_and_names_the_excluded_opponent_for_a_trivial_only_entry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Issue #166: a passing promotion entry against `builtin:starter` alone
    must not authorize an upload, and the refusal must name it so the
    failure mode is not indistinguishable from "nothing was ever run".
    """
    bundle = _build_fixture_bundle(tmp_path / "bundle.tar.gz", PASS_AGENT_FILES)
    gates_dir = tmp_path / "gates"
    _write_promotion_entry(
        gates_dir,
        filename="a.json",
        candidate_sha="deadbeef",
        passed=True,
        opponent="builtin:starter",
    )

    rc = main(
        [
            "--candidate-sha",
            "deadbeef",
            "--bundle",
            str(bundle),
            "--gates-dir",
            str(gates_dir),
            "--rehearsal-seeds",
            "1",
            "--seed-base",
            "1",
        ]
    )
    captured = capsys.readouterr()
    assert rc != 0
    assert captured.out == ""
    assert "builtin:starter" in captured.err
    assert "excluded" in captured.err


@pytest.mark.slow
def test_main_succeeds_when_the_promotion_opponent_is_not_trivial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Issue #166 must not become a blanket refusal: a passing entry against
    a non-`builtin:*`, non-`TUNABLE_SPECS` opponent still authorizes the
    upload.
    """
    monkeypatch.chdir(tmp_path)
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    _build_fixture_bundle(dist_dir / "submission.tar.gz", PASS_AGENT_FILES)
    gates_dir = tmp_path / "eval" / "gates"
    _write_promotion_entry(
        gates_dir,
        filename="a.json",
        candidate_sha="deadbeef",
        passed=True,
        opponent="zoo:pass",
    )

    rc = main(["--candidate-sha", "deadbeef", "--rehearsal-seeds", "2", "--seed-base", "1"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == (
        'kaggle competitions submit kaggriculture -f dist/submission.tar.gz -m "deadbeef"'
    )


@pytest.mark.slow
def test_main_succeeds_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    _build_fixture_bundle(dist_dir / "submission.tar.gz", PASS_AGENT_FILES)
    gates_dir = tmp_path / "eval" / "gates"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)

    rc = main(
        [
            "--candidate-sha",
            "deadbeef",
            "--rehearsal-seeds",
            "2",
            "--seed-base",
            "1",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == (
        'kaggle competitions submit kaggriculture -f dist/submission.tar.gz -m "deadbeef"'
    )


@pytest.mark.slow
def test_main_never_writes_to_eval_dir_on_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    _build_fixture_bundle(dist_dir / "submission.tar.gz", PASS_AGENT_FILES)
    gates_dir = tmp_path / "eval" / "gates"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)
    eval_dir = tmp_path / "eval"
    before = sorted(p.relative_to(eval_dir) for p in eval_dir.rglob("*"))

    main(["--candidate-sha", "deadbeef", "--rehearsal-seeds", "2", "--seed-base", "1"])

    after = sorted(p.relative_to(eval_dir) for p in eval_dir.rglob("*"))
    assert after == before
    assert not (tmp_path / "eval" / "submissions").exists()


def test_main_never_writes_to_eval_dir_on_refuse(tmp_path: Path) -> None:
    bundle = _build_fixture_bundle(tmp_path / "bundle.tar.gz", BAD_IMPORT_AGENT_FILES)
    gates_dir = tmp_path / "eval" / "gates"
    _write_promotion_entry(gates_dir, filename="a.json", candidate_sha="deadbeef", passed=True)
    eval_dir = tmp_path / "eval"
    before = sorted(p.relative_to(eval_dir) for p in eval_dir.rglob("*"))

    main(
        [
            "--candidate-sha",
            "deadbeef",
            "--bundle",
            str(bundle),
            "--gates-dir",
            str(gates_dir),
        ]
    )

    after = sorted(p.relative_to(eval_dir) for p in eval_dir.rglob("*"))
    assert after == before


# --- no-venv static guard, with a teeth-check on the guard itself -----------

_VENV_RE = re.compile(r"\b(venv|virtualenv|pip install|uv sync)\b")


def test_submit_py_contains_no_venv_invocation() -> None:
    assert _VENV_RE.search((REPO / "submit.py").read_text()) is None


def test_teeth_venv_guard_flags_injected_venv_call() -> None:
    """Teeth-check: the regex-based guard actually flags a venv call, proving it has teeth."""
    injected = '\nsubprocess.run(["python", "-m", "venv", "x"])\n'
    tampered = (REPO / "submit.py").read_text() + injected
    assert _VENV_RE.search(tampered) is not None
