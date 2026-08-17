"""Opponent-aware sell overlay on the purearch trace.

Hypothesis: purearch's aggressive selling wins vs starter AND vs weak
opponents, but against a strong opponent that FLOODS the same premium
products, both crash the price. An opponent-aware overlay sells aggressively
BY DEFAULT (preserves the production engine) but DRIBBLES a premium product
when the opponent's public farm shows a big supply of it — letting the
opponent crash the price while we hold and sell after they deplete.

The opponent's farm is visible in obs['farms'][1-player]['tiles'].

Usage: python opponent_aware_trace.py (demo); h2h via h2h_bench.py
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
import purearch_opponent as pa  # noqa: E402

# Products we dribble if the opponent floods them.
PREMIUM = ("MILK", "STRAWBERRY", "WOOL", "EGG")
DRIBBLE_RATE = 4  # per-turn cap when opponent floods
OPP_THRESHOLD = {
    "MILK": 6,       # opponent has >= 6 cows -> floods milk
    "STRAWBERRY": 12,  # opponent has >= 12 strawberry -> floods
    "WOOL": 6,       # >= 6 sheep
    "EGG": 6,        # >= 6 geese
}


def _opp_supply(obs):
    """Count opponent's animals/crops by premium product driver."""
    player = int(obs.get("player", 0) or 0)
    opp = 1 - player
    farms = obs.get("farms", [])
    if not (0 <= opp < len(farms)):
        return {}
    tiles = farms[opp].get("tiles", [])
    cows = sheep = geese = strawberry = 0
    for y in range(len(tiles)):
        for x in range(len(tiles[y])):
            t = tiles[y][x]
            if not isinstance(t, dict):
                continue
            a = t.get("animal")
            if a == "COW":
                cows += 1
            elif a == "SHEEP":
                sheep += 1
            elif a == "GOOSE":
                geese += 1
            if t.get("kind") == "PLANT" and t.get("crop") == "STRAWBERRY":
                strawberry += 1
    return {"MILK": cows, "WOOL": sheep, "EGG": geese, "STRAWBERRY": strawberry}


def agent(obs, config=None):
    trace = pa.agent(obs, config)
    market = [o for o in trace.get("market", []) if o[0] != "SELL"]
    try:
        opp_supply = _opp_supply(obs)
        day = int(obs.get("day", 0) or 0)
        shed = obs["private"].get("shed", {})
        # Find the trace's SELL orders and cap premium ones the opponent floods.
        sells = []
        for o in trace.get("market", []):
            if o and o[0] == "SELL" and len(o) >= 3:
                item, qty = o[1], o[2]
                if day < 28 and item in PREMIUM and opp_supply.get(item, 0) >= OPP_THRESHOLD.get(item, 99):
                    qty = min(qty, DRIBBLE_RATE)  # opponent floods -> dribble
                if qty > 0:
                    sells.append(["SELL", item, qty])
        market = (market + sells)[:10]
    except Exception:
        market = trace.get("market", [])[:10]
    return {"farmer": trace.get("farmer", ["PASS"]), "hands": trace.get("hands", []), "market": market}


if __name__ == "__main__":
    from kaggle_environments import make
    for s in (1, 2):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "starter"])
        print(f"seed {s} vs starter:", env.steps[-1][0]["reward"])
