"""Diagnose the dispatcher's economy day-by-day (money / plants / seeds / hands).

Usage: python dispatch_diag.py [--seed N] [--days K]
"""
from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from kaggle_environments import make  # noqa: E402

import dispatcher_agent as da  # noqa: E402
from kaggriculture_real import KIND_PLANT, KIND_WEED, KIND_PASTURE, KIND_COOP  # noqa: E402


def plant_stats(farm):
    from collections import Counter
    c = Counter()
    for row in farm.get("tiles", []):
        for t in row:
            if isinstance(t, dict) and t.get("kind") == KIND_PLANT:
                c[t.get("crop")] += 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": args.seed})
    env.run([da.agent, "starter"])
    steps = env.steps

    day = 0
    print(f"{'day':>3} {'money':>8} {'hands':>5} {'plants':>6} {'M':>3} {'S':>3} {'W':>3} "
          f"{'seedsM':>5} {'seedsS':>5} {'seedsW':>5} {'shedVal':>8} {'mktOrders':>5}")
    for st in steps:
        obs = st[0].get("observation")
        if not obs:
            continue
        d = int(obs.get("day", 0))
        if d != day:
            continue
        hour = int(obs.get("hour", 0))
        if hour != 0:
            continue
        farm = obs["farms"][0]
        private = obs.get("private", {})
        seeds = private.get("seeds", {})
        money = float(farm.get("money", 0.0))
        hands = len(farm.get("hands", []))
        pl = plant_stats(farm)
        shed = private.get("shed", {})
        prices = obs.get("market", {}).get("prices", {})
        shed_val = sum(int(q or 0) * prices.get(k, 0) for k, q in shed.items() if k not in ("COW", "SHEEP", "GOOSE"))
        # count market orders that were issued this step
        mo = st[0].get("action", {}) or {}
        mo = mo.get("market", [])
        print(f"{day:>3} {money:>8.0f} {hands:>5} {sum(pl.values()):>6} "
              f"{pl.get('MELON', 0):>3} {pl.get('STRAWBERRY', 0):>3} {pl.get('WHEAT', 0):>3} "
              f"{int(seeds.get('MELON', 0)):>5} {int(seeds.get('STRAWBERRY', 0)):>5} {int(seeds.get('WHEAT', 0)):>5} "
              f"{shed_val:>8.0f} {len(mo):>5}")
        day += 1
        if day > args.days:
            break

    print("\nfinal reward:", steps[-1][0].get("reward"))


if __name__ == "__main__":
    main()
