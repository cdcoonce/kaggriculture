"""Frozen-incumbent materialization: renamed-package freeze + mirror guard.

Covers freeze_incumbent's git-archive-at-a-SHA extraction, its internal
import rewrite (agent.* -> frozen_<name>.*), the mirror-guard that catches
the historical sys.modules collision bug (a frozen incumbent silently
resolving to the SAME files as the live ``agent`` package, so "old vs new"
secretly ran new-vs-new), and resolve_agent's ``frozen:<name>`` spec form.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import types
from pathlib import Path

import pytest
from harness.episodes import resolve_agent
from harness.frozen import assert_disjoint, freeze_incumbent, frozen_package_name


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _write_agent_fixture(agent_dir: Path, const_value: str) -> None:
    """A minimal stand-in for packages/agent/src/agent: absolute internal imports."""
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "__init__.py").write_text("", encoding="utf-8")
    (agent_dir / "constants.py").write_text(f'CONST = "{const_value}"\n', encoding="utf-8")
    (agent_dir / "policy.py").write_text(
        "from agent.constants import CONST\n\n\ndef make_policy():\n    return {'const': CONST}\n",
        encoding="utf-8",
    )
    (agent_dir / "shell.py").write_text(
        "def wrap(policy):\n"
        "    def _act(*args, **kwargs):\n"
        "        return policy['const']\n"
        "    return _act\n",
        encoding="utf-8",
    )


@pytest.fixture
def fixture_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """A throwaway git repo (not the real repo's history) with two commits.

    Commit 1 ("v1") pins CONST to "sha1-value"; commit 2 ("v2") changes it to
    "sha2-value". Tests freeze commit 1 while HEAD sits at commit 2, to prove
    freeze_incumbent honors the pinned SHA rather than the current tree.
    """
    repo_root = tmp_path / "fixture_repo"
    repo_root.mkdir()
    _run_git(["init", "-q"], cwd=repo_root)
    _run_git(["config", "user.email", "test@example.com"], cwd=repo_root)
    _run_git(["config", "user.name", "Test"], cwd=repo_root)

    agent_dir = repo_root / "packages" / "agent" / "src" / "agent"

    _write_agent_fixture(agent_dir, "sha1-value")
    _run_git(["add", "-A"], cwd=repo_root)
    _run_git(["commit", "-q", "-m", "v1"], cwd=repo_root)
    sha1 = _run_git(["rev-parse", "HEAD"], cwd=repo_root)

    _write_agent_fixture(agent_dir, "sha2-value")
    _run_git(["add", "-A"], cwd=repo_root)
    _run_git(["commit", "-q", "-m", "v2"], cwd=repo_root)
    sha2 = _run_git(["rev-parse", "HEAD"], cwd=repo_root)

    return repo_root, sha1, sha2


class TestFrozenPackageName:
    def test_dashes_become_underscores(self) -> None:
        assert frozen_package_name("m1-fc23e66") == "frozen_m1_fc23e66"

    def test_plain_name_gets_frozen_prefix(self) -> None:
        assert frozen_package_name("chassis") == "frozen_chassis"


class TestFreezeIncumbent:
    def test_extracts_the_pinned_sha_not_head(
        self, fixture_repo: tuple[Path, str, str], tmp_path: Path
    ) -> None:
        repo_root, sha1, _sha2 = fixture_repo
        dest_root = tmp_path / "dest"

        freeze_incumbent(sha1, "t1", repo_root, dest_root)

        text = (dest_root / "frozen_t1" / "constants.py").read_text(encoding="utf-8")
        assert "sha1-value" in text
        assert "sha2-value" not in text

    def test_import_rewrite_targets_the_renamed_package(
        self, fixture_repo: tuple[Path, str, str], tmp_path: Path
    ) -> None:
        repo_root, sha1, _sha2 = fixture_repo
        dest_root = tmp_path / "dest"

        freeze_incumbent(sha1, "t2", repo_root, dest_root)

        text = (dest_root / "frozen_t2" / "policy.py").read_text(encoding="utf-8")
        assert "from frozen_t2.constants import CONST" in text
        assert "from agent." not in text
        assert "import agent" not in text

    def test_name_with_dashes_produces_a_valid_identifier_dir(
        self, fixture_repo: tuple[Path, str, str], tmp_path: Path
    ) -> None:
        repo_root, sha1, _sha2 = fixture_repo
        dest_root = tmp_path / "dest"

        dest = freeze_incumbent(sha1, "m1-fc23e66", repo_root, dest_root)

        assert dest == dest_root / "frozen_m1_fc23e66"
        assert (dest / "__init__.py").exists()

    def test_refreeze_is_idempotent_and_replaces_old_content(
        self, fixture_repo: tuple[Path, str, str], tmp_path: Path
    ) -> None:
        repo_root, sha1, sha2 = fixture_repo
        dest_root = tmp_path / "dest"

        freeze_incumbent(sha1, "t3", repo_root, dest_root)
        freeze_incumbent(sha2, "t3", repo_root, dest_root)

        text = (dest_root / "frozen_t3" / "constants.py").read_text(encoding="utf-8")
        assert "sha2-value" in text
        assert "sha1-value" not in text

        # No leftover scratch/tmp directories from the first freeze.
        leftovers = [p.name for p in dest_root.iterdir() if p.name != "frozen_t3"]
        assert leftovers == []

    def test_frozen_package_coexists_with_the_live_agent_package(
        self,
        fixture_repo: tuple[Path, str, str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import agent.policy as live_policy

        repo_root, sha1, _sha2 = fixture_repo
        dest_root = tmp_path / "dest"
        freeze_incumbent(sha1, "t4", repo_root, dest_root)

        monkeypatch.syspath_prepend(str(dest_root))
        frozen_policy = importlib.import_module("frozen_t4.policy")

        assert frozen_policy is not live_policy
        assert Path(frozen_policy.__file__).resolve() != Path(live_policy.__file__).resolve()
        # The live module was not displaced by the frozen import.
        assert sys.modules["agent.policy"] is live_policy


class TestAssertDisjoint:
    def test_raises_when_frozen_file_resolves_inside_the_live_agent_tree(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import agent.policy as live_policy

        fake = types.ModuleType("frozen_collision_a.policy")
        fake.__file__ = live_policy.__file__  # simulates the sys.modules mirror bug
        monkeypatch.setitem(sys.modules, "frozen_collision_a.policy", fake)

        with pytest.raises(RuntimeError, match="mirror bug"):
            assert_disjoint("collision-a")

    def test_raises_when_frozen_module_displaces_live_agent_module(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import agent.policy as live_policy

        # The historical bug: same identity in sys.modules under both keys.
        monkeypatch.setitem(sys.modules, "frozen_collision_b.policy", live_policy)

        with pytest.raises(RuntimeError, match="mirror bug"):
            assert_disjoint("collision-b")

    def test_raises_when_frozen_package_was_never_imported(self) -> None:
        with pytest.raises(RuntimeError, match="not been imported"):
            assert_disjoint("never-imported")

    def test_passes_for_a_genuinely_disjoint_frozen_module(
        self,
        fixture_repo: tuple[Path, str, str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo_root, sha1, _sha2 = fixture_repo
        dest_root = tmp_path / "dest"
        freeze_incumbent(sha1, "t5", repo_root, dest_root)

        monkeypatch.syspath_prepend(str(dest_root))
        importlib.import_module("frozen_t5.policy")

        assert_disjoint("t5")  # must not raise


class TestResolveAgentFrozenSpec:
    def test_returns_a_callable_built_from_the_frozen_code(
        self,
        fixture_repo: tuple[Path, str, str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo_root, sha1, _sha2 = fixture_repo
        dest_root = tmp_path / "dest"
        freeze_incumbent(sha1, "t6", repo_root, dest_root)
        monkeypatch.setenv("KAGG_FROZEN_ROOT", str(dest_root))

        agent = resolve_agent("frozen:t6")

        assert callable(agent)
        assert agent() == "sha1-value"

    def test_resolves_the_pinned_sha_even_though_head_moved_on(
        self,
        fixture_repo: tuple[Path, str, str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo_root, sha1, sha2 = fixture_repo
        assert sha1 != sha2  # HEAD is sha2; we freeze the older sha1
        dest_root = tmp_path / "dest"
        freeze_incumbent(sha1, "t7", repo_root, dest_root)
        monkeypatch.setenv("KAGG_FROZEN_ROOT", str(dest_root))

        agent = resolve_agent("frozen:t7")

        assert agent() == "sha1-value"
