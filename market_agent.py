"""Market agent: purearch production + balanced-rate sell policy.

Hypothesis: purearch's aggressive selling maximizes revenue vs a weak starter
(volume beats price), but in HEAD-TO-HEAD vs a strong opponent the mutual
flooding crashes prices for BOTH, and the winner is whoever sells at a rate
that sustains prices while still moving inventory.

The top agent (ep92730021, 132k+ h2h) sells at a BALANCED rate:
  MILK 6-30/day, STRAWBERRY 6-36/day, WOOL 4-18/day (premium dribble)
  WHEAT 8-149/day (volume, dumps late)
  FERTILIZER all (aggressive, it decays)
  MELON early, all
  CARROT minor

This agent keeps the purearch production schedule (farmer/hands + buying) but
replaces SELL orders with this rate-limited policy. Test vs purearch h2h: if
it wins, the market edge is real and submission-worthy.

Usage: python market_agent.py  (plays a demo); h2h via h2h_bench.py
"""
from __future__ import annotations

import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "src"))
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))

import purearch_opponent as pa  # noqa: E402

# Balanced per-turn sell caps from the top agent's observed rates.
SELL_CAPS = {
    "MILK": 20,
    "STRAWBERRY": 15,
    "WOOL": 10,
    "EGG": 10,
    "MELON": 999,      # one-time, sell all (early)
    "WHEAT": 999,      # volume crop, sell all (hold feed reserve below)
    "CARROT": 999,
    "FERTILIZER": 999,  # decays fast, sell all
}
FEED_RESERVE_PER_ANIMAL = 2
DUMP_DAY = 28  # final days: sell everything


def _feed_reserve(obs):
    """Keep wheat for feeding animals (like the trace does implicitly)."""
    farm = obs["farms"][obs["player"]]
    tiles = farm.get("tiles", [])
    n_animals = sum(
        1 for y in range(len(tiles)) for x in range(len(tiles[y]))
        if isinstance(tiles[y][x], dict) and tiles[y][x].get("animal")
    )
    return n_animals * FEED_RESERVE_PER_ANIMAL


def agent(obs, config=None):
    trace = pa.agent(obs, config)
    # Keep trace's farmer/hands + non-SELL market orders (hiring, buys).
    market = [o for o in trace.get("market", []) if o[0] != "SELL"]
    try:
        private = obs["private"]
        shed = private.get("shed", {})
        prices = obs.get("market", {}).get("prices", {})
        day = int(obs.get("day", 0) or 0)
        feed_reserve = _feed_reserve(obs)
        sells = []
        for item, amount in shed.items():
            qty = int(amount)
            if qty <= 0 or item in ("COW", "SHEEP", "GOOSE"):
                continue
            if item == "WHEAT" and day < DUMP_DAY:
                qty = max(0, qty - feed_reserve)  # keep feed wheat
            cap = SELL_CAPS.get(item, 999)
            if day >= DUMP_DAY:
                cap = 999  # dump everything in final days
            if cap < 999:
                qty = min(qty, cap)
            if qty > 0:
                sells.append(["SELL", item, qty])
        market = (market + sells)[:10]
    except Exception:
        pass
    return {
        "farmer": trace.get("farmer", ["PASS"]),
        "hands": trace.get("hands", []),
        "market": market,
    }


if __name__ == "__main__":
    from kaggle_environments import make
    for s in (1, 2):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "starter"])
        print(f"seed {s} vs starter:", env.steps[-1][0]["reward"])
