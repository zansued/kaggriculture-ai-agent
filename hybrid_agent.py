"""Hybrid agent: trace production engine + adaptive market-timing selling.

The purearch trace (fixed replay, ~181k local) is an extremely efficient
PRODUCTION schedule but sells everything blindly, flooding the market. This
hybrid keeps the trace's farmer/hand actions and its buying (animals/seeds/
feed), but REPLACES its SELL orders with our market-timed logic (price / shop /
opponent-aware). Idea: produce like the trace, but time sales to preserve
prices — which should beat other traces in head-to-head.

Run standalone: `python hybrid_agent.py` plays a demo game.
"""
from __future__ import annotations

import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "src"))
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))

import kaggriculture_real as kr  # noqa: E402
import purearch_opponent as pa  # noqa: E402

_brain = kr.FarmBrain()


def agent(obs, config=None):
    trace = pa.agent(obs, config)
    # Keep the trace's farmer/hand actions and its non-SELL market orders
    # (hiring, buying animals/seeds/feed). Drop its inflated SELL attempts.
    market = [o for o in trace.get("market", []) if o[0] != "SELL"]
    # Add our market-timed selling of what is actually in the shed.
    try:
        farm = obs["farms"][obs["player"]]
        private = obs["private"]
        prices = obs.get("market", {}).get("prices", {})
        sells, _ = _brain._plan_sells(obs, farm, private,
                                      int(obs.get("day", 0)), int(obs.get("hour", 0)), prices,
                                      reserve_feed=False)  # the trace manages its own feed
        market = (market + sells)[: kr.MAX_MARKET_ORDERS]
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
        print(f"seed {s} vs starter:", env.steps[-1][0]["reward"], env.steps[-1][0]["status"])
