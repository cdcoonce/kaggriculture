"""Third-party episode data hygiene (#28, part of #21).

Guards against accidentally committing a real competitor's episode replay
(non-PASS agent actions from someone other than us) under docs/recon/ or
eval/. Files that legitimately need to be there are explicitly allowlisted
by filename with a provenance citation.
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SCAN_ROOTS = (REPO / "docs" / "recon", REPO / "eval")

EXCLUDED_DIRS = {"frozen", "__pycache__"}

ALLOWLIST = (
    # Raw agent-0 stdout/stderr log dump from validation episode 90301508
    # (submission 55284206, "Charles Coonce"): a flat list of
    # {duration, stdout, stderr} records, not an episode replay — no
    # steps/action/player-identifier schema. See docs/recon/runner-facts.md
    # lines 3-5.
    "probe-episode-logs-90301508-0.json",
)


def _iter_json_files(roots=SCAN_ROOTS):
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
            for filename in filenames:
                if filename.endswith(".json.gz") or filename.endswith(".json"):
                    yield Path(dirpath) / filename


def _load_json(path: Path):
    if path.name.endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(path.read_text(encoding="utf-8"))


def _step_actions(steps) -> list:
    actions = []
    for step in steps:
        if not isinstance(step, list):
            continue
        for agent_entry in step:
            if isinstance(agent_entry, dict) and "action" in agent_entry:
                actions.append(agent_entry["action"])
    return actions


def _is_pass_action(action) -> bool:
    if action == "PASS":
        return True
    if isinstance(action, dict):
        return (
            action.get("farmer") == ["PASS"]
            and action.get("hands") == []
            and action.get("market") == []
        )
    return False


def _has_unvetted_actions(path: Path) -> bool:
    data = _load_json(path)
    if not isinstance(data, dict):
        return False
    steps = data.get("steps")
    if not isinstance(steps, list):
        return False
    actions = _step_actions(steps)
    if not actions:
        return False
    return not all(_is_pass_action(a) for a in actions)


def _find_violations(roots=SCAN_ROOTS) -> list[Path]:
    return [
        path
        for path in _iter_json_files(roots)
        if path.name not in ALLOWLIST and _has_unvetted_actions(path)
    ]


def test_no_unvetted_third_party_episode_data() -> None:
    violations = _find_violations()
    assert not violations, f"unvetted non-PASS third-party actions found in: {violations}"


def test_probe_server_replay_is_pass_only_episode() -> None:
    path = REPO / "docs" / "recon" / "probe-server-replay.json.gz"
    data = _load_json(path)
    assert "steps" in data
    actions = _step_actions(data["steps"])
    assert actions, "expected per-agent action entries in steps"
    assert all(_is_pass_action(a) for a in actions)


def test_probe_episode_logs_allowlisted_and_not_episode_schema() -> None:
    path = REPO / "docs" / "recon" / "probe-episode-logs-90301508-0.json"
    assert path.name in ALLOWLIST
    data = _load_json(path)
    assert isinstance(data, list)
    assert not _has_unvetted_actions(path)


def test_teeth_synthetic_non_pass_action_is_caught(tmp_path: Path) -> None:
    """Teeth-check A: a synthetic third-party replay with a non-PASS action
    outside the allowlist must fail the walk."""
    recon_dir = tmp_path / "docs" / "recon"
    recon_dir.mkdir(parents=True)
    bad_file = recon_dir / "synthetic-third-party-episode.json"
    bad_file.write_text(
        json.dumps(
            {
                "steps": [
                    [
                        {"action": "PASS"},
                        {"action": {"farmer": ["PLANT", 2, 3], "hands": [], "market": []}},
                    ]
                ],
                "info": {
                    "Agents": [{"Name": "Charles Coonce"}, {"Name": "Someone Else"}],
                },
            }
        )
    )
    assert _find_violations((recon_dir,)) == [bad_file]


def test_teeth_allowlist_entry_suppresses_matching_filename(tmp_path: Path) -> None:
    """Teeth-check B (allowlist mechanism): a would-be-violating file that
    shares the allowlisted filename must be suppressed by the allowlist
    itself, not merely by lacking a `steps` key."""
    recon_dir = tmp_path / "docs" / "recon"
    recon_dir.mkdir(parents=True)
    shadow = recon_dir / "probe-episode-logs-90301508-0.json"
    shadow.write_text(json.dumps({"steps": [[{"action": "PASS"}, {"action": "PLANT"}]]}))
    assert _find_violations((recon_dir,)) == []
