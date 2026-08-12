"""Fail-closed behavior for the detect-agent-changes `id: filter` step (#52).

Parses the actual `run:` script out of ci.yml (not a copy) so a regression in
the workflow file itself turns these tests red. GitHub Actions expression
placeholders (``${{ ... }}``) are resolved by the Actions runner, not bash --
each test substitutes literal values before executing the rendered script
with ``bash -e -c``, matching this step's real unspecified-shell default.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
ZERO_SHA = "0" * 40


def _load_filter_script() -> str:
    workflow = yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text())
    for step in workflow["jobs"]["detect-agent-changes"]["steps"]:
        if step.get("id") == "filter":
            run_script = step["run"]
            assert isinstance(run_script, str)
            return run_script
    raise AssertionError("id: filter step not found in detect-agent-changes job")


def _render(script: str, *, event_name: str, base: str, head: str) -> str:
    rendered = script
    for placeholder, value in {
        "${{ github.event_name }}": event_name,
        "${{ github.event.pull_request.base.sha }}": base,
        "${{ github.event.pull_request.head.sha }}": head,
        "${{ github.event.before }}": base,
        "${{ github.event.after }}": head,
    }.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def _run_filter(
    script: str, repo: Path, tmp_path: Path, *, base: str, head: str
) -> tuple[subprocess.CompletedProcess[str], str]:
    output_file = tmp_path / "github_output"
    output_file.write_text("")
    rendered = _render(script, event_name="push", base=base, head=head)
    result = subprocess.run(
        ["bash", "-e", "-c", rendered],
        cwd=repo,
        env={**os.environ, "GITHUB_OUTPUT": str(output_file)},
        capture_output=True,
        text=True,
    )
    return result, output_file.read_text()


def _init_repo(repo: Path) -> str:
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    return _head_sha(repo)


def _head_sha(repo: Path) -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def _commit_file(repo: Path, relpath: str, contents: str) -> str:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)
    subprocess.run(["git", "add", relpath], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", f"touch {relpath}"], cwd=repo, check=True)
    return _head_sha(repo)


def test_agent_change_sets_true(tmp_path: Path) -> None:
    script = _load_filter_script()
    repo = tmp_path / "repo"
    base = _init_repo(repo)
    head = _commit_file(repo, "packages/agent/src/thing.py", "x = 1\n")

    result, output = _run_filter(script, repo, tmp_path, base=base, head=head)

    assert result.returncode == 0, result.stderr
    assert "agent-changed=true" in output
    assert "packages/agent/ changed" in result.stdout


def test_non_agent_change_sets_false(tmp_path: Path) -> None:
    script = _load_filter_script()
    repo = tmp_path / "repo"
    base = _init_repo(repo)
    head = _commit_file(repo, "packages/harness/src/thing.py", "x = 1\n")

    result, output = _run_filter(script, repo, tmp_path, base=base, head=head)

    assert result.returncode == 0, result.stderr
    assert "agent-changed=false" in output
    assert "did not change" in result.stdout


def test_unresolvable_base_defaults_to_true(tmp_path: Path) -> None:
    """Teeth-check target: revert the fail-closed branch and this goes red."""
    script = _load_filter_script()
    repo = tmp_path / "repo"
    _init_repo(repo)
    head = _head_sha(repo)

    result, output = _run_filter(script, repo, tmp_path, base=ZERO_SHA, head=head)

    assert result.returncode == 0, result.stderr
    assert "agent-changed=true" in output
    assert "unresolvable" in result.stdout
    assert "defaulting to run" in result.stdout
