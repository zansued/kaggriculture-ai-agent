"""Probe de cadência de FEED/CARE de COWs no champion v19.

Acompanha cada COW do champion (por tile, seat do champion) dia a dia e mede:
  - dias de vida, dias fed, dias cared
  - prod_eve (noite produtiva) e se foi fed/cared
  - feeds em dias de diff par (fora de fase) vs ímpar (em fase)
  - runs de FEED diário (tripla) -> feeds redundantes (skip do meio)
  - máximo consecutive_unfed (risco de fuga)

Uso:
    python probe_cow_feed.py --seeds 1-3 --json results/probe_cow_feed.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
sys.path.insert(0, os.path.join(_HERE, "src"))

from kaggle_environments import make  # noqa: E402
import purearch_opponent  # noqa: E402
from clock_utils import logical_step  # noqa: E402


def parse_seeds(spec):
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",") if x]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="submissions/hybrid_v19/main.py")
    ap.add_argument("--seeds", default="1-3")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    spec = importlib.util.spec_from_file_location(
        "champ_feed", os.path.join(_HERE, args.agent))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    champ = m.agent

    cows_meta = []

    for seed in parse_seeds(args.seeds):
        for label in ("P0", "P1"):
            # champion_seat: 0 para P0, 1 para P1
            cseat = 0 if label == "P0" else 1
            agents = ([champ, purearch_opponent.agent] if label == "P0"
                      else [purearch_opponent.agent, champ])
            registry = {}

            def make_wrap(fn, my_seat, champ_seat, reg):
                def _a(obs, cfg=None):
                    obs = dict(obs)
                    obs["step"] = logical_step(obs)
                    act = fn(obs, cfg)
                    seat = 1 if int(obs.get("player", 0) or 0) == 1 else 0
                    if seat != champ_seat:   # só nos interessa o champion
                        return act
                    farms = obs.get("farms") or []
                    if seat >= len(farms):
                        return act
                    farm = farms[seat] or {}
                    day = int(obs.get("day", 0) or 0)
                    hour = int(obs.get("hour", 0) or 0)
                    tiles = farm.get("tiles") or []
                    for y, row in enumerate(tiles):
                        for x, t in enumerate(row):
                            if isinstance(t, dict) and t.get("animal") == "COW":
                                r = reg.setdefault(
                                    (x, y),
                                    {"placed": int(t.get("placed_day", day) or 0),
                                     "feeds": set(), "cares": set(), "max_unfed": 0})
                                r["placed"] = int(t.get("placed_day", r["placed"]) or 0)
                    if hour == 23:
                        for (x, y), r in reg.items():
                            try:
                                t = tiles[y][x]
                            except Exception:
                                continue
                            if not (isinstance(t, dict) and t.get("animal") == "COW"):
                                continue
                            if t.get("fed_today", False):
                                r["feeds"].add(day)
                            if t.get("cared_today", False):
                                r["cares"].add(day)
                            r["max_unfed"] = max(r["max_unfed"],
                                                 int(t.get("consecutive_unfed", 0) or 0))
                    return act
                return _a

            a0 = make_wrap(agents[0], 0, cseat, registry)
            a1 = make_wrap(agents[1], 1, cseat, registry)
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
            env.run([a0, a1])
            last = env.steps[-1]
            for (x, y), r in registry.items():
                if not r["feeds"] and not r["cares"]:
                    continue
                cows_meta.append({"seed": seed, "seat": label, "xy": [x, y],
                                  "placed": r["placed"], "feeds": sorted(r["feeds"]),
                                  "cares": sorted(r["cares"]), "max_unfed": r["max_unfed"]})

    stats = {"n_cows": 0, "alive_days_sum": 0, "fed_days_sum": 0, "care_days_sum": 0,
             "prod_eve": 0, "prod_eve_fed": 0, "prod_eve_uncared": 0,
             "feeds_odd": 0, "feeds_even": 0, "triple_runs_feeds": 0,
             "max_unfed_max": 0, "escapes": 0}
    for r in cows_meta:
        placed = r["placed"]
        feeds = r["feeds"]
        cares = r["cares"]
        all_days = set(feeds) | set(cares) | {placed}
        if not all_days:
            continue
        max_day = max(all_days)
        stats["n_cows"] += 1
        stats["alive_days_sum"] += (max_day - placed + 1)
        stats["fed_days_sum"] += len(feeds)
        stats["care_days_sum"] += len(cares)
        for d in range(placed, max_day + 1):
            if (d + 1) - placed - 8 >= 0 and ((d + 1) - placed - 8) % 2 == 0:
                stats["prod_eve"] += 1
                if d in feeds:
                    stats["prod_eve_fed"] += 1
                if d not in cares:
                    stats["prod_eve_uncared"] += 1
        for d in feeds:
            if (d - placed) % 2 == 0:
                stats["feeds_even"] += 1
            else:
                stats["feeds_odd"] += 1
        fset = set(feeds)
        stats["triple_runs_feeds"] += sum(1 for d in feeds
                                          if (d - 1) in fset and (d + 1) in fset)
        stats["max_unfed_max"] = max(stats["max_unfed_max"], r["max_unfed"])
        if r["max_unfed"] >= 2:
            stats["escapes"] += 1

    print("=== COW FEED CADENCE (champion v19) ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if stats["n_cows"]:
        ratio = stats["fed_days_sum"] / max(1, stats["alive_days_sum"])
        print(f"  feeds por vaca-dia: {ratio:.2f}")
        print(f"  feeds fora de fase (diff par): {stats['feeds_even']} | em fase: {stats['feeds_odd']}")
        print(f"  prod_eve fed: {stats['prod_eve_fed']}/{stats['prod_eve']} | uncared: {stats['prod_eve_uncared']}")
        print(f"  feeds redundantes (tripla diaria -> skip do meio): {stats['triple_runs_feeds']}")
        if stats["feeds_even"]:
            print(f"  share feeds fora de fase: {stats['feeds_even']/(stats['feeds_even']+stats['feeds_odd']):.0%}")
    if args.json:
        json.dump({"stats": stats, "per_cow": cows_meta},
                  open(os.path.join(_HERE, args.json), "w"), indent=1)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
