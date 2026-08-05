"""Single-process throughput benchmark for kaggriculture episodes.

Runs N episodes of make('kaggriculture').run(['starter','starter']) sequentially
in one process, at default step count (720), and reports episodes/sec.
"""
import time
import sys
from kaggle_environments import make

N_EPISODES = int(sys.argv[1]) if len(sys.argv) > 1 else 20

def run_one_episode():
    env = make('kaggriculture', debug=False)
    env.run(['starter', 'starter'])
    return env.configuration.get('episodeSteps')

def main():
    # warmup (JIT / import caches / etc.) - one untimed episode
    run_one_episode()

    times = []
    t_start = time.perf_counter()
    for i in range(N_EPISODES):
        t0 = time.perf_counter()
        steps = run_one_episode()
        t1 = time.perf_counter()
        times.append(t1 - t0)
    t_end = time.perf_counter()

    total_wall = t_end - t_start
    eps_per_sec = N_EPISODES / total_wall
    avg_ep_time = sum(times) / len(times)
    min_ep = min(times)
    max_ep = max(times)

    print(f"episodes={N_EPISODES}")
    print(f"total_wall_sec={total_wall:.3f}")
    print(f"episodes_per_sec={eps_per_sec:.4f}")
    print(f"avg_episode_sec={avg_ep_time:.4f}")
    print(f"min_episode_sec={min_ep:.4f}")
    print(f"max_episode_sec={max_ep:.4f}")
    print(f"seconds_per_episode_avg={avg_ep_time:.4f}")

if __name__ == '__main__':
    main()
