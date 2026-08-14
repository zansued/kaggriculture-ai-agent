"""Switch hybrid: run the purearch trace for steps 0..K, then hand the whole
farm to the reactive FarmBrain for the rest.

Idea: purearch's fixed production schedule is a tight optimum (~181k vs starter)
but it ignores the opponent. The reactive reacts to actual state/market. If we
inherit purearch's early-game production (land, 14 animals, crops) and let the
reactive drive the late game, we get near-trace production PLUS adaptive market
timing — which could win head-to-head against other traces.

Usage:
    python hybrid_switch.py --switch 20 --opponent starter --seeds 1,2,3,4
    python hybrid_switch.py --switch 20 --opponent purearch --seeds 1..8   # h2h
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "src"))
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))

import kaggriculture_real as kr  # noqa: E402
import purearch_opponent  # noqa: E402
from kaggle_environments import make  # noqa: E402


def make_agent(switch_day: int | None, reactive_kwargs: dict | None = None):
    brain = kr.FarmBrain(**(reactive_kwargs or {}))

    def _agent(obs, _cfg=None):
        step = int(obs.get("step", 0) or 0)
        if switch_day is None or step < switch_day * 24:
            return purearch_opponent.agent(obs, _cfg)
        return brain.decide(obs)

    return _agent


def run_game(agent, opponent, seed, steps: int):
    env = make("kaggriculture", configuration={"episodeSteps": steps, "seed": seed})
    env.run([agent, opponent])
    last = env.steps[-1]
    s0, s1 = last[0], last[1]
    return (s0["reward"], s1["reward"], s0["status"], s1["status"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--switch", type=int, default=None,
                    help="day to switch trace->reactive (None = purearch only)")
    ap.add_argument("--opponent", default="starter", help="starter|random|purearch")
    ap.add_argument("--seeds", default="1,2,3,4")
    ap.add_argument("--steps", type=int, default=720)
    ap.add_argument("--kwargs", default=None, help="JSON dict for reactive FarmBrain")
    args = ap.parse_args()
    seeds = [int(x) for x in args.seeds.split(",")]
    opp = {"purearch": purearch_opponent.agent}.get(args.opponent, args.opponent)
    kwargs = {}
    if args.kwargs:
        import json
        kwargs.update(json.loads(args.kwargs))

    name = f"switch@{args.switch}" if args.switch is not None else "purearch"
    agent = make_agent(args.switch, kwargs)
    print(f"=== hybrid_switch {name} vs '{args.opponent}' seeds={seeds} ===", flush=True)
    results = []
    for seed in seeds:
        try:
            r0, r1, st0, st1 = run_game(agent, opp, seed, args.steps)
            ok = st0 == "DONE" and r0 is not None
            results.append((r0, r1, ok))
            print(f"  [seed {seed:>2}] {'OK' if ok else f'BAD({st0})'}  mine={r0}  opp={r1}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  [seed {seed:>2}] EXC {type(e).__name__}: {e}", flush=True)
    valid = [r for r in results if r[2]]
    if valid:
        mine = [r[0] for r in valid]
        o = [r[1] for r in valid if r[1] is not None]
        wins = sum(1 for r in valid if r[0] > (r[1] or 0))
        print(f"  SUMMARY mean={statistics.mean(mine):.1f} median={statistics.median(mine):.1f} "
              f"min={min(mine):.1f} max={max(mine):.1f} win_rate={wins/len(valid):.3f} (n={len(valid)})")


if __name__ == "__main__":
    main()
