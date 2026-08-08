"""
Run all seedless parity checks against a captured server replay, using the
LOCAL kaggle_environments package's constants and market_price() as the
oracle.

Defaults to the committed own-episode fixture (M2b self-play, episode
91087847 -- see packages/harness/tests/fixtures/replays/PROVENANCE.md) but
accepts any replay path, plain .json or gzipped .json.gz, as an argument.

Prints a JSON report to stdout.
"""
import argparse
import gzip
import json
import sys

import importlib.metadata

from pathlib import Path

from kaggle_environments import make

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPLAY_PATH = (
    REPO_ROOT
    / "packages"
    / "harness"
    / "tests"
    / "fixtures"
    / "replays"
    / "episode-91087847-m2b-selfplay.json.gz"
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common_checks as cc  # noqa: E402


def load_replay(path: Path) -> dict:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "replay_path",
        nargs="?",
        type=Path,
        default=DEFAULT_REPLAY_PATH,
        help=f"Path to a replay .json or .json.gz (default: {DEFAULT_REPLAY_PATH.relative_to(REPO_ROOT)})",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    data = load_replay(args.replay_path)

    report = {}

    # --- 1. Engine metadata ---
    report["metadata"] = {
        "replay_module_version": data.get("module_version"),
        "replay_env_version": data.get("version"),
        "replay_name": data.get("name"),
        "local_kaggle_environments_version": importlib.metadata.version("kaggle-environments"),
        "local_env_spec_version": None,  # filled below
    }

    env = make("kaggriculture", debug=True)
    report["metadata"]["local_env_spec_version"] = env.specification.get("version")
    report["metadata"]["local_env_spec_name"] = env.specification.get("name")

    # --- 2. Configuration parity ---
    replay_cfg = dict(data["configuration"])
    local_cfg = dict(env.configuration)
    all_keys = sorted(set(replay_cfg.keys()) | set(local_cfg.keys()))
    cfg_diffs = []
    for k in all_keys:
        rv = replay_cfg.get(k, "<MISSING>")
        lv = local_cfg.get(k, "<MISSING>")
        if rv != lv:
            cfg_diffs.append({"key": k, "replay_value": rv, "local_default": lv})
    report["configuration"] = {
        "replay_config": replay_cfg,
        "local_default_config": local_cfg,
        "diffs": cfg_diffs,
        "diff_count": len(cfg_diffs),
    }

    # --- extract per-step player-0 observations in step order ---
    steps_raw = data["steps"]
    obs_list = [step[0]["observation"] for step in steps_raw]
    # sanity: steps are contiguous by "step" field
    step_field_ok = all(
        obs_list[i].get("step") == i for i in range(len(obs_list))
    )
    report["step_index_sanity"] = {"contiguous_0_indexed": step_field_ok, "n_steps": len(obs_list)}

    turns_per_day = int(replay_cfg.get("turnsPerDay", 24))
    shop_interval = int(replay_cfg.get("townShopSellInterval", 4))
    center_interval = int(replay_cfg.get("townCenterSellInterval", 12))
    unlock_interval = int(replay_cfg.get("townShopUnlockInterval", 3))
    board_size = int(replay_cfg.get("boardSize", 10))
    starting_money = int(replay_cfg.get("startingMoney", 3000))

    # --- action PASS-only verification ---
    non_pass = []
    for i, step in enumerate(steps_raw):
        for ag_idx, ag in enumerate(step):
            act = ag.get("action")
            if act is None:
                continue
            farmer_a = act.get("farmer")
            hands_a = act.get("hands") or []
            market_a = act.get("market") or []
            if farmer_a != ["PASS"] or hands_a != [] or market_a != []:
                non_pass.append({"step": i, "agent": ag_idx, "action": act})
    report["pass_only_verification"] = {
        "non_pass_action_count": len(non_pass),
        "sample": non_pass[:10],
    }

    # --- 3. Price-function law ---
    report["price_law"] = cc.price_law_check(obs_list, turns_per_day=turns_per_day)

    # --- 4. Town-consumption law ---
    report["town_law"] = cc.town_consumption_law_check(
        obs_list,
        shop_interval=shop_interval,
        center_interval=center_interval,
        unlock_interval=unlock_interval,
        turns_per_day=turns_per_day,
    )

    # --- 5. Structural spot-checks ---
    report["structural"] = cc.structural_checks(
        obs_list, board_size=board_size, starting_money=starting_money
    )

    # weed boundary check
    report["weed_boundary"] = cc.weed_boundary_check(obs_list, turns_per_day=turns_per_day)

    # final rewards == final money
    final_rewards = data.get("rewards")
    final_statuses = data.get("statuses")
    last_step = steps_raw[-1]
    final_farms_money = [ag["observation"]["farms"][p]["money"] for p, ag in enumerate(last_step)]
    # also check each agent's own reported `reward` field at final step
    per_agent_final_reward_field = [ag.get("reward") for ag in last_step]
    report["final_rewards"] = {
        "top_level_rewards": final_rewards,
        "top_level_statuses": final_statuses,
        "final_farms_money": final_farms_money,
        "per_agent_reward_field_at_last_step": per_agent_final_reward_field,
        "rewards_match_money": final_rewards == final_farms_money,
    }

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
