"""market_agent variant: trace_10c4s (10 COW + 4 SHEEP) production + top-agent
balanced sell rates. Tests whether the 10+4 production needs the rebalanced
sell schedule (milk dribble, etc.) to beat purearch in h2h.

The top agent (ep92730021 P1) beats purearch 8/10 in our 10 replays. Its
coherent schedule = 10+4 animals + 33 strawberry + balanced sells. trace_10c4s
has the 10+4 production but kept purearch's aggressive sell schedule. This
agent rebalances the sells.
"""
from __future__ import annotations

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))

# Load trace_10c4s as the base agent
_SUBMISSION = os.path.join(_HERE, "submissions", "trace_10c4s", "main.py")
_spec = importlib.util.spec_from_file_location("t10", _SUBMISSION)
_t10 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_t10)

SELL_CAPS = {
    "MILK": 20,
    "STRAWBERRY": 15,
    "WOOL": 10,
    "EGG": 10,
    "MELON": 999,
    "WHEAT": 999,
    "CARROT": 999,
    "FERTILIZER": 999,
}
FEED_RESERVE_PER_ANIMAL = 2
DUMP_DAY = 28


def _feed_reserve(obs):
    farm = obs["farms"][obs["player"]]
    tiles = farm.get("tiles", [])
    n_animals = sum(
        1 for y in range(len(tiles)) for x in range(len(tiles[y]))
        if isinstance(tiles[y][x], dict) and tiles[y][x].get("animal")
    )
    return n_animals * FEED_RESERVE_PER_ANIMAL


def agent(obs, config=None):
    base = _t10.agent(obs, config)
    market = [o for o in base.get("market", []) if o[0] != "SELL"]
    try:
        private = obs["private"]
        shed = private.get("shed", {})
        day = int(obs.get("day", 0) or 0)
        feed_reserve = _feed_reserve(obs)
        sells = []
        for item, amount in shed.items():
            qty = int(amount)
            if qty <= 0 or item in ("COW", "SHEEP", "GOOSE"):
                continue
            if item == "WHEAT" and day < DUMP_DAY:
                qty = max(0, qty - feed_reserve)
            cap = SELL_CAPS.get(item, 999)
            if day >= DUMP_DAY:
                cap = 999
            if cap < 999:
                qty = min(qty, cap)
            if qty > 0:
                sells.append(["SELL", item, qty])
        market = (market + sells)[:10]
    except Exception:
        pass
    return {"farmer": base.get("farmer", ["PASS"]), "hands": base.get("hands", []), "market": market}


if __name__ == "__main__":
    from kaggle_environments import make
    for s in (1, 2):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "starter"])
        print(f"seed {s} vs starter:", env.steps[-1][0]["reward"])
