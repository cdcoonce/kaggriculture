"""
Local determinism cross-check: run one local PASS-vs-PASS episode (fresh
seed, chosen by the engine since we pass seed=None / default config) and
verify the SAME laws (price law, town-consumption law, structural spot
checks, weed-boundary law) hold against the locally-produced trajectory,
using the identical common_checks functions used against the server
replay. This guards against a bug in the check scripts themselves rather
than a genuine local/server engine difference: if these checks somehow
always pass trivially (e.g. because of a check-script bug), running them
against a LOCAL trajectory generated independently of the replay is a
different data source and exercises the same code paths.
"""
import argparse
import importlib.metadata
import json
import sys

from pathlib import Path

from kaggle_environments import make

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common_checks as cc  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force-legacy-law",
        action="store_true",
        help=(
            "Debug/discrimination control: override the town-consumption law "
            "dispatch to always use the legacy day-scaled schedule, even "
            "under an engine >= 1.32.6. Used to prove the checker actually "
            "discriminates the two laws on real data (see issue #43 AC5)."
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    engine_version = importlib.metadata.version("kaggle-environments")

    env = make("kaggriculture", debug=True)
    env.reset(num_agents=2)
    env.run(["pass", "pass"])

    cfg = dict(env.configuration)
    default_center_interval = (
        12 if cc.parse_version(engine_version) < cc.FLAT_LAW_MIN_VERSION else 24
    )
    turns_per_day = int(cfg.get("turnsPerDay", 24))
    shop_interval = int(cfg.get("townShopSellInterval", 4))
    center_interval = int(cfg.get("townCenterSellInterval", default_center_interval))
    unlock_interval = int(cfg.get("townShopUnlockInterval", 3))
    board_size = int(cfg.get("boardSize", 10))
    starting_money = int(cfg.get("startingMoney", 3000))

    steps_raw = env.steps
    obs_list = [step[0].observation for step in steps_raw]
    action_steps = [[ag.action for ag in step] for step in steps_raw]

    report = {}
    report["n_steps"] = len(obs_list)
    report["configuration_used"] = cfg
    report["info_seed"] = env.info.get("seed") if hasattr(env, "info") else None

    # PASS-only sanity (should be, since we used the built-in pass agent)
    non_pass = []
    for i, step in enumerate(steps_raw):
        for ag_idx, ag in enumerate(step):
            act = ag.action if not isinstance(ag.action, dict) else ag.action
            if not isinstance(act, dict):
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
    # PASS-only-by-construction, but still routed through the shared guard
    # (episode_is_pass_only) so the guard's behavior is exercised and
    # provable here rather than merely assumed.
    report["pass_only_guard_verification"] = cc.episode_is_pass_only(action_steps)

    report["price_law"] = cc.price_law_check(obs_list, turns_per_day=turns_per_day)
    report["town_law"] = cc.town_consumption_law_check(
        obs_list,
        engine_version,
        shop_interval=shop_interval,
        center_interval=center_interval,
        unlock_interval=unlock_interval,
        turns_per_day=turns_per_day,
        force_legacy_law=args.force_legacy_law,
    )
    report["structural"] = cc.structural_checks(
        obs_list, board_size=board_size, starting_money=starting_money
    )
    report["weed_boundary"] = cc.weed_boundary_check(obs_list, turns_per_day=turns_per_day)

    last_step = steps_raw[-1]
    final_rewards = [ag.reward for ag in last_step]
    final_farms_money = [ag.observation["farms"][p]["money"] for p, ag in enumerate(last_step)]
    report["final_rewards"] = {
        "final_rewards": final_rewards,
        "final_farms_money": final_farms_money,
        "rewards_match_money": final_rewards == final_farms_money,
    }

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
