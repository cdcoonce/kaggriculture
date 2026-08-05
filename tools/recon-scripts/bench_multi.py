"""Multiprocessing scaling benchmark for kaggriculture episodes.

Spawns N worker processes, each running its own kaggle_environments env
instance and executing a share of the total episodes independently
(no shared state / no IPC per-step - just independent episode runs).
Reports aggregate episodes/sec for the whole batch (wall-clock across all
workers), which is what matters for tournament wall-clock time.
"""
import multiprocessing as mp
import time
import sys


def worker_run_episodes(n_episodes):
    # import inside worker so each process does its own clean import
    from kaggle_environments import make
    for _ in range(n_episodes):
        env = make('kaggriculture', debug=False)
        env.run(['starter', 'starter'])
    return n_episodes


def bench(n_workers, total_episodes):
    # divide total_episodes as evenly as possible across workers
    base = total_episodes // n_workers
    rem = total_episodes % n_workers
    per_worker = [base + (1 if i < rem else 0) for i in range(n_workers)]
    per_worker = [x for x in per_worker if x > 0]

    ctx = mp.get_context('spawn')
    t0 = time.perf_counter()
    with ctx.Pool(processes=len(per_worker)) as pool:
        results = pool.map(worker_run_episodes, per_worker)
    t1 = time.perf_counter()

    wall = t1 - t0
    total_done = sum(results)
    eps_per_sec = total_done / wall
    per_worker_eps_per_sec = eps_per_sec / len(per_worker)

    print(f"workers={len(per_worker)}")
    print(f"total_episodes={total_done}")
    print(f"wall_sec={wall:.3f}")
    print(f"aggregate_episodes_per_sec={eps_per_sec:.4f}")
    print(f"per_worker_episodes_per_sec={per_worker_eps_per_sec:.4f}")
    return eps_per_sec


if __name__ == '__main__':
    n_workers = int(sys.argv[1])
    total_episodes = int(sys.argv[2]) if len(sys.argv) > 2 else n_workers * 10
    bench(n_workers, total_episodes)
