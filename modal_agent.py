"""modal_agent: shared-opening shop-routed base (Moon's "sacada #1") — SINGLE AGENT.

Instead of switching between trace_agent instances (which corrupts repair
state), we replay PUREARCH (purearch_opponent, which handles its own repairs)
and SWAP the animal TYPE at the specific divergence steps based on the town's
shops. This is safe because:
  - 10c4s differs from purearch ONLY at: steps 200-201 (BUY SHEEP -> COW) +
    unit steps 205/209/212 (PICKUP/PLACE SHEEP -> COW).
  - 6c8s differs ONLY at: steps 257-258 (BUY COW -> SHEEP) + their placement.
So we modify the base action at those steps; everything else (repairs, feed,
care, market) stays purearch's.

Route pick (cached once the first 2 shops are known, ~day 6):
  >=2 milk shops (PIZZA/ICE_CREAM/SMOOTHIE) -> t10 (10c4s, milk-heavy)
  YARN_STORE in first 2                    -> t68 (6c8s, yarn-heavy)
  else                                     -> base (8c6s)

The mix's market overlays (front-run, market-flow, sell-first) are added on
top. Usage: import modal_agent; modal_agent.agent(obs)
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
sys.path.insert(0, os.path.join(_HERE, "src"))

import purearch_opponent as pa  # noqa: E402
import mix_agent  # noqa: E402

_MILK_SHOPS = ("PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP")
_T10_BUY_STEPS = {200, 201}          # BUY SHEEP -> COW
_T10_PLACE_STEPS = {205, 209, 212}   # PICKUP/PLACE SHEEP -> COW
_T68_BUY_STEPS = {257, 258}          # BUY COW -> SHEEP
_ROUTE = {0: None, 1: None}


def _pick_route(obs):
    shops = list(obs.get("town", {}).get("unlocked_shops", []) or [])
    if len(shops) < 2:
        return None
    first2 = shops[:2]
    milk = sum(s in _MILK_SHOPS for s in first2)
    if milk >= 2:
        return "t10"
    if "YARN_STORE" in first2:
        return "t68"
    return "base"


def _swap(action, step, route):
    """Swap animal types at the divergence steps."""
    if route == "t10" and step in _T10_BUY_STEPS:
        for o in action.get("market", []) or []:
            if len(o) >= 2 and o[0] == "BUY_ANIMAL" and o[1] == "SHEEP":
                o[1] = "COW"
    if route == "t10" and step in _T10_PLACE_STEPS:
        for key in ("farmer", "hands"):
            acts = action.get(key, [])
            if key == "farmer":
                acts = [acts]
            for a in acts:
                if isinstance(a, list) and len(a) >= 2 and a[1] == "SHEEP" and a[0] in ("PICKUP", "PLACE"):
                    a[1] = "COW"
            if key == "farmer":
                action["farmer"] = acts[0]
            else:
                action["hands"] = acts
    if route == "t68" and step in _T68_BUY_STEPS:
        for o in action.get("market", []) or []:
            if len(o) >= 2 and o[0] == "BUY_ANIMAL" and o[1] == "COW":
                o[1] = "SHEEP"
    return action


def agent(obs, config=None):
    step = int(obs.get("step", 0) or 0)
    seat = int(obs.get("player", 0) or 0)
    if step == 0:
        _ROUTE[seat] = None
    # Decide the route only once the first 2 shops are visible (~day 6),
    # well before the day-8 divergence. Until then it's the shared opening.
    if _ROUTE[seat] is None:
        r = _pick_route(obs)
        if r is not None:
            _ROUTE[seat] = r
    route = _ROUTE[seat] or "base"

    # Full mix pipeline (purearch trace + repairs + all overlays), then swap
    # the animal TYPE at the divergence steps for the chosen modal route.
    action = mix_agent.agent(obs, config)
    return _swap(action, step, route)


if __name__ == "__main__":
    import statistics
    from kaggle_environments import make
    seeds = list(range(1, 13))
    ms = []
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, pa.agent])
        last = env.steps[-1]
        ms.append(last[0]["reward"] - last[1]["reward"])
    print(f"modal_agent vs purearch 1-12: {statistics.mean(ms):+.0f} "
          f"({sum(1 for m in ms if m > 0)}-{sum(1 for m in ms if m < 0)})")
