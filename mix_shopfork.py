"""Shop-routed tomato fork (ported from Moon V56) for the purearch-based mix.

Moon's adaptive production: when the first 3 unlocked shops contain >=2
PIZZA_SHOP/FARMERS_MARKET (which demand TOMATO), shift part of the day-11
STRAWBERRY cohort to TOMATO — the shops drain tomato, so it holds value while
strawberry stays crowded. Surgical: only 3 plants / 3 seed buys, so it does
not restructure the trace.

Purearch's day-11 cohort (verified):
  seed buys:  step 275 (1), 280 (2)   -> 3 strawberry seeds
  plant acts: step 279, 281, 282      -> 3 PLANT STRAWBERRY
We convert exactly those 3 (buy at 275+280, plant at 279/281/282) to TOMATO.

The fork is gated at step 216 (day 9) when the first 3 shops are known.

Usage: import mix_shopfork; mix_shopfork.agent(obs) — wraps the mix.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))

import mix_agent  # noqa: E402

_TOMATO_SEED_STEPS = {275: 1, 280: 2}   # step -> qty of strawberry to convert
_TOMATO_PLANT_STEPS = {279, 281, 282}   # steps with a PLANT STRAWBERRY -> TOMATO
_TOMATO_SHOPS = ("FARMERS_MARKET", "PIZZA_SHOP")
_TOMATO_MIN_SHOPS = 2  # Moon's validated gate (>=2 tomato shops)
_TOMATO_STATE = {0: {}, 1: {}}


def _seat(obs):
    return int(obs.get("player", 0) or 0)


def _check_tomato(obs, step):
    """Activate the fork at day 9 (step 216) if >=2 tomato shops in first 3."""
    seat = _seat(obs)
    st = _TOMATO_STATE[seat]
    if step == 216:
        shops = list(obs.get("town", {}).get("unlocked_shops", []) or [])[:3]
        st["active"] = sum(s in _TOMATO_SHOPS for s in shops) >= _TOMATO_MIN_SHOPS
    if step == 0:
        st["active"] = False
        st["converted"] = 0
    return st


def _patch_seed(action, step, seat):
    """Convert strawberry seed buys at the fork steps to tomato."""
    qty = _TOMATO_SEED_STEPS.get(step)
    if not qty:
        return
    market = list(action.get("market", []) or [])
    for i, o in enumerate(market):
        if (len(o) >= 3 and o[0] == "BUY_SEED" and o[1] == "STRAWBERRY"
                and int(o[2] or 0) >= qty):
            market[i] = ["BUY_SEED", "TOMATO", qty]
            break
    action["market"] = market


def _patch_plant(action, step):
    """Convert a PLANT STRAWBERRY at a fork step to PLANT TOMATO."""
    if step not in _TOMATO_PLANT_STEPS:
        return
    farmer = action.get("farmer")
    if isinstance(farmer, list) and len(farmer) >= 2 and farmer[0] == "PLANT" and farmer[1] == "STRAWBERRY":
        action["farmer"] = ["PLANT", "TOMATO"]
        return
    hands = action.get("hands", [])
    for i, a in enumerate(hands):
        if isinstance(a, list) and len(a) >= 2 and a[0] == "PLANT" and a[1] == "STRAWBERRY":
            hands[i] = ["PLANT", "TOMATO"]
            action["hands"] = hands
            return


def agent(obs, config=None):
    step = int(obs.get("step", 0) or 0)
    seat = _seat(obs)
    st = _check_tomato(obs, step)
    action = mix_agent.agent(obs, config)
    if not st.get("active"):
        return action
    _patch_seed(action, step, seat)
    _patch_plant(action, step)
    return action


if __name__ == "__main__":
    from kaggle_environments import make
    import statistics
    import purearch_opponent as pa
    seeds = list(range(1, 13))
    ms = []
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, pa.agent])
        last = env.steps[-1]
        ms.append(last[0]["reward"] - last[1]["reward"])
    print(f"shopfork mix vs purearch: mean={statistics.mean(ms):+.0f} "
          f"({sum(1 for m in ms if m > 0)}-{sum(1 for m in ms if m < 0)})")
