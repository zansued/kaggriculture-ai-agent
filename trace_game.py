"""Trace one game to understand where money comes from and where it's lost.

Instruments the FarmBrain to count SELL/PLANT market orders and samples
market prices and farm state per day.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import kaggriculture_real as kr
from kaggle_environments import make


def trace(seed: int = 1, steps: int = 720, opponent: str = "starter", **brain_kwargs):
    brain = kr.FarmBrain(**brain_kwargs)
    sells = {c: 0 for c in kr.PRODUCTS}
    buys_seed = {c: 0 for c in kr.CROPS}
    planted_daily = {}
    sells_daily = {}
    daily = {}
    first_plant_day = {}
    prices_by_day = {}
    shed_by_day = {}
    plants_by_day = {}   # day -> {crop: count}
    empty_by_day = {}    # day -> count of empty unlocked tiles
    weeds_by_day = {}    # day -> count of weed tiles

    def _agent(obs, _cfg=None):
        action = brain.decide(obs)
        day = obs.get("day", 0)
        for op in action.get("market", []):
            if op[0] == kr.SELL:
                sells[op[1]] += op[2]
                sells_daily.setdefault(day, {}).setdefault(op[1], 0)
                sells_daily[day][op[1]] += op[2]
            elif op[0] == kr.BUY_SEED:
                buys_seed[op[1]] += op[2]
        return action

    env = make("kaggriculture", configuration={"episodeSteps": steps, "seed": seed})
    env.run([_agent, opponent])

    prev_day = None
    for step_state in env.steps:
        obs = step_state[0]["observation"]
        if obs is None:
            continue
        day = obs.get("day", 0)
        hour = obs.get("hour", 0)
        if prev_day is None or day != prev_day:
            daily[day] = obs["farms"][0]["money"]
            prices_by_day[day] = dict(obs.get("market", {}).get("prices", {}))
            shed_by_day[day] = dict(obs.get("private", {}).get("shed", {}))
            prev_day = day
        farm = obs["farms"][0]
        tiles = farm.get("tiles", [])
        pc = plants_by_day.setdefault(day, {})
        ec = empty_by_day.setdefault(day, 0)
        wc = weeds_by_day.setdefault(day, 0)
        for y in range(len(tiles)):
            for x in range(len(tiles[y])):
                t = tiles[y][x]
                if isinstance(t, dict) and t.get("kind") == kr.KIND_PLANT:
                    c = t.get("crop")
                    pc[c] = pc.get(c, 0) + 1
                    if c not in first_plant_day:
                        first_plant_day[c] = day
                elif t is None:
                    ec += 1
                elif isinstance(t, dict) and t.get("kind") == kr.KIND_WEED:
                    wc += 1
        empty_by_day[day] = ec
        weeds_by_day[day] = wc

    last = env.steps[-1]
    reward = last[0]["reward"] if last[0] else None

    print("=" * 56)
    print(f"Seed {seed} vs '{opponent}': final reward={reward}  final_money={daily.get(max(daily), None)}")
    print(f"Total SELL orders: { {k: v for k, v in sells.items() if v} }")
    print(f"Total seed buys:   { {k: v for k, v in buys_seed.items() if v} }")
    print(f"First plant day:   {first_plant_day}")

    print("\nDay | money | melon px | empty | plants(M/S/T/W/C) | weeds | sells:")
    for d in sorted(daily):
        pr = prices_by_day.get(d, {})
        pc = plants_by_day.get(d, {})
        ec = empty_by_day.get(d, 0)
        wc = weeds_by_day.get(d, 0)
        sd = sells_daily.get(d, {})
        plants = " ".join(f"{k[0]}:{pc.get(k,0)}" for k in ["MELON","STRAWBERRY","TOMATO","WHEAT","CARROT"])
        parts = [f"{c}:{sd[c]}" for c in sorted(sd)]
        print(f"  {d:>2} | {daily[d]:>8.1f} | {pr.get('MELON','-'):>5} | {ec:>3} | {plants} "
              f"| {wc} | {' '.join(parts) if parts else '-'}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--opponent", default="starter")
    ap.add_argument("--steps", type=int, default=720)
    ap.add_argument("--crops", default=None, help="comma list of crops, e.g. 'MELON' or 'WHEAT,MELON'")
    ap.add_argument("--kwargs", default=None, help="JSON dict of FarmBrain kwargs, e.g. '{\"crops\":[\"MELON\"]}'")
    args = ap.parse_args()
    kwargs = {}
    if args.crops:
        kwargs["crops"] = args.crops.split(",")
    if args.kwargs:
        import json
        kwargs.update(json.loads(args.kwargs))
    trace(seed=args.seed, steps=args.steps, opponent=args.opponent, **kwargs)
