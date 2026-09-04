"""Head-to-head benchmark between arbitrary agents over many seeds.

Usage:
    python h2h_bench.py purearch trace_10c4s --seeds 1-20
    python h2h_bench.py purearch reactive --seeds 1-20
    python h2h_bench.py purearch purearch --seeds 1-20   # mirror
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "src"))
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))

import purearch_opponent  # noqa: E402
from kaggle_environments import make  # noqa: E402

from src.clock_utils import clock_safe  # noqa: E402


def load_agent(name: str):
    """Return an agent function. name is one of:
    purearch | reactive | hybrid_switch | or a path to a submission main.py
    """
    if name == "purearch":
        return purearch_opponent.agent
    if name == "reactive":
        import kaggriculture_real as kr
        brain = kr.FarmBrain()
        return lambda obs, cfg=None: brain.decide(obs)
    if name.startswith("switch@"):
        import kaggriculture_real as kr
        day = int(name.split("@")[1])
        brain = kr.FarmBrain()
        def _a(obs, cfg=None):
            step = int(obs.get("step", 0) or 0)
            if step < day * 24:
                return purearch_opponent.agent(obs, cfg)
            return brain.decide(obs)
        return _a
    if os.path.isfile(name):
        spec = importlib.util.spec_from_file_location("subm", name)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.agent
    raise ValueError(f"unknown agent: {name}")


def parse_seeds(spec: str):
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",") if x]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent_a", help="agent for player 0")
    ap.add_argument("agent_b", help="agent for player 1 (or 'starter'/'random')")
    ap.add_argument("--seeds", default="1-8")
    ap.add_argument("--steps", type=int, default=720)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    agent_a = clock_safe(load_agent(args.agent_a))
    if args.agent_b in ("starter", "random"):
        agent_b = args.agent_b
    else:
        agent_b = clock_safe(load_agent(args.agent_b))
    seeds = parse_seeds(args.seeds)

    print(f"=== H2H {args.agent_a} (P0) vs {args.agent_b} (P1), seeds={seeds} ===", flush=True)
    wins_a = wins_b = ties = 0
    margins = []
    games = []
    for seed in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": args.steps, "seed": seed})
        env.run([agent_a, agent_b])
        last = env.steps[-1]
        r0 = last[0]["reward"] if last[0] else None
        r1 = last[1]["reward"] if last[1] else None
        st0 = last[0]["status"] if last[0] else None
        st1 = last[1]["status"] if last[1] else None
        if r0 is None or r1 is None or st0 != "DONE" or st1 != "DONE":
            print(f"  [seed {seed:>2}] BAD  r0={r0}({st0}) r1={r1}({st1})", flush=True)
            games.append({"seed": seed, "r0": r0, "r1": r1, "st0": st0, "st1": st1})
            continue
        if r0 > r1:
            wins_a += 1
        elif r1 > r0:
            wins_b += 1
        else:
            ties += 1
        margins.append(r0 - r1)
        games.append({"seed": seed, "r0": r0, "r1": r1, "st0": st0, "st1": st1})
        print(f"  [seed {seed:>2}] P0={r0:>7}  P1={r1:>7}  d={r0-r1:>+8}  "
              f"P0{'W' if r0>r1 else 'L' if r1>r0 else 'T'}", flush=True)

    n = len(margins)
    print(f"\n=== RESULT: {args.agent_a} {wins_a}-{wins_b} {args.agent_b} (ties={ties}, n={n}) ===")
    if n:
        import statistics
        print(f"  mean P0={statistics.mean(g['r0'] for g in games if g['r0'] is not None):.0f}  "
              f"mean P1={statistics.mean(g['r1'] for g in games if g['r1'] is not None):.0f}  "
              f"mean d={statistics.mean(margins):+.0f}  mind={min(margins):+}  maxd={max(margins):+}")
    if args.json:
        import json
        json.dump({"a": args.agent_a, "b": args.agent_b, "games": games,
                   "wins_a": wins_a, "wins_b": wins_b, "ties": ties}, open(args.json, "w"), indent=1)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
