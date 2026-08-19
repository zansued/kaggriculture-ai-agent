"""Oracle attempt: repair layers for the TOP agent's raw trace.

The top agent (10 COW + 4 SHEEP, 33 strawberry, land d6/d11) beats purearch
8/10 in the replays, but its raw trace collapses to ~34k vs starter (vs
purearch's raw 173k) because its actions are ADAPTIVE (state-coupled). The
repair hypothesis: the trace's biggest waste is mass feed-wheat buying (70
BUY_PRODUCT WHEAT orders) for animals that never get placed in the frozen
replay, plus a liquidity crunch (money ~$0 days 1-10 while the shed fills).

Repair layers (config-gated):
  gate_feed   drop BUY_PRODUCT WHEAT when placed+shed animals < min_animals
  liquidate   when money < floor, force-sell the highest-value shed products
              (front-loads cash so buys don't stall the economy)
  keep_lands  keep BUY_LAND orders (they expand production on the trace's
              actual footprint)

Measurement: vs starter (fast proxy) then h2h vs purearch (the real target).

Usage: python top_trace_oracle.py [--gate-feed 4] [--liquidate 300] [--seeds 1,2]
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
sys.path.insert(0, os.path.join(_HERE, "src"))

import trace_agent  # noqa: E402
from kaggle_environments import make  # noqa: E402

TRACE = "data/kawasagi/trace_92730021_p1.json"


def _count_animals(obs):
    """Placed animals + animals in shed/inventory."""
    player = int(obs.get("player", 0) or 0)
    farm = obs["farms"][player]
    n = 0
    for row in farm.get("tiles", []):
        for t in row:
            if isinstance(t, dict) and t.get("animal"):
                n += 1
    shed = obs.get("private", {}).get("shed", {})
    invs = obs.get("private", {}).get("inventories", [])
    for a in ("COW", "SHEEP", "GOOSE"):
        n += int(shed.get(a, 0) or 0)
        n += sum(int(i.get(a, 0) or 0) for i in invs)
    return n


def _best_sells(shed, prices, cap=4):
    """Highest-value non-animal shed products."""
    items = []
    for k, v in shed.items():
        if k in ("COW", "SHEEP", "GOOSE"):
            continue
        q = int(v or 0)
        if q <= 0:
            continue
        items.append((prices.get(k, 0) * q, q, k))
    items.sort(reverse=True)
    return [["SELL", k, q] for _, q, k in items[:cap]]


def make_oracle(gate_feed=4, liquidate=300):
    base = trace_agent.load_trace_agent(TRACE)

    def agent(obs, config=None):
        action = base(obs, config)
        money = float(obs["farms"][int(obs.get("player", 0) or 0)].get("money", 0.0))
        shed = obs.get("private", {}).get("shed", {})
        prices = obs.get("market", {}).get("prices", {})
        day = int(obs.get("day", 0) or 0)

        # 1) GATE FEED: drop BUY_PRODUCT WHEAT when we don't have enough animals.
        market = []
        n_animals = _count_animals(obs)
        for o in action.get("market", []):
            if o and o[0] == "BUY_PRODUCT" and len(o) >= 2 and o[1] == "WHEAT" and n_animals < gate_feed:
                continue  # animals we can't place don't need feed
            market.append(o)

        # 2) LIQUIDATE: when cash is low and the shed holds value, sell the most
        #    valuable products FIRST (front-load cash so buys don't stall).
        if liquidate is not None and money < liquidate:
            forced = _best_sells(shed, prices)
            # Prepend forced sells (highest priority in the market queue).
            market = forced + market

        action["market"] = market[:10]
        return action

    return agent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate-feed", type=int, default=4, help="drop feed buys if animals < N (0=off)")
    ap.add_argument("--liquidate", type=int, default=300, help="force-sell when money < N (0=off)")
    ap.add_argument("--seeds", default="1,2")
    ap.add_argument("--opponent", default="starter", choices=["starter", "purearch"])
    args = ap.parse_args()
    seeds = [int(v) for v in args.seeds.split(",")]

    if args.opponent == "purearch":
        import purearch_opponent as pa
        opp = pa.agent
    else:
        opp = "starter"

    agent = make_oracle(gate_feed=args.gate_feed, liquidate=args.liquidate)
    rs = []
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, opp])
        rs.append(env.steps[-1][0]["reward"])
    print(f"gate_feed={args.gate_feed} liquidate={args.liquidate} vs {args.opponent}: "
          f"mean={statistics.mean(rs):.0f} per_seed={[int(x) for x in rs]}")


if __name__ == "__main__":
    main()
