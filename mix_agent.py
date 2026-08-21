"""mix_agent v2: purearch base trace + c27's clone-detection front-run +
maturity-aware opponent front-run.

Aug-20 re-validation: a clone-only variant (maturity OFF) had a HIGHER margin
vs purearch (+4.09k/j vs +2.47k/j, 20 seeds), but the maturity overlay
converts margin into WINS — the metric the ladder actually rates. H2H direct
v2(maturity) vs v3(clone-only) = 11-1, and vs c27 = 11-1 (clone-only only
3-9). The maturity overlay is therefore KEPT ON (see _ENABLE_MATURITY_FRONT_RUN).

How it works: purearch's strong trace is the base (it beats non-clones).
c27's clone-detection front-run fires when the opponent looks like a clone
(similar build -> same glut -> sell premium ~2 turns before the joint dump).
The maturity overlay generalizes beyond clones: it sells shed premium product
when the OPPONENT's production is near-mature (imminent dump), regardless of
clone status.

Usage: import mix_agent; mix_agent.agent(obs) — self-contained (stdlib only)
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))

import purearch_opponent as pa  # noqa: E402
import c27_agent  # noqa: E402

_FRONT_RUN_HORIZON = 2
_FRONT_RUN_ITEMS = ("MELON", "STRAWBERRY", "MILK", "WOOL")
_BASE_PRICE = {"MELON": 250, "STRAWBERRY": 120, "MILK": 160, "WOOL": 200}
_GLUT_WEIGHT = {"MELON": 3.5, "STRAWBERRY": 2.0, "MILK": 2.0, "WOOL": 3.2}


def _front_run_purearch(action, obs, step):
    """Sell the premium purearch is about to dump, before the clone's glut."""
    if c27_agent._CLONE_CONFIDENCE < 2 or _FRONT_RUN_HORIZON <= 0:
        return
    orders = list(action.get("market", []) or [])
    if len(orders) >= 10:
        return
    already = {}
    for order in orders:
        if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
            already[order[1]] = already.get(order[1], 0) + max(0, int(order[2] or 0))
    planned = {}
    end = min(len(pa._MARKET_TRACE), step + _FRONT_RUN_HORIZON + 1)
    for future_step in range(step + 1, end):
        distance = future_step - step
        for order in pa._MARKET_TRACE[future_step]:
            if not (isinstance(order, list) and len(order) >= 3
                    and order[0] == "SELL" and order[1] in _FRONT_RUN_ITEMS):
                continue
            item = order[1]
            quantity = max(0, int(order[2] or 0))
            if item not in planned:
                planned[item] = [distance, quantity]
            else:
                planned[item][1] += quantity
    shed = (obs.get("private") or {}).get("shed") or {}
    prices = ((obs.get("market") or {}).get("prices") or {})
    choices = []
    for item, (distance, quantity) in planned.items():
        available = max(0, int(shed.get(item, 0) or 0) - already.get(item, 0))
        quantity = min(available, quantity)
        if quantity <= 0:
            continue
        price = float(prices.get(item, _BASE_PRICE[item]) or 0)
        priority = (price * quantity * _GLUT_WEIGHT[item]
                    + (_FRONT_RUN_HORIZON + 1 - distance) * _BASE_PRICE[item])
        choices.append((priority, item, quantity))
    if choices:
        choices.sort(reverse=True)
        _, item, quantity = choices[0]
        orders.append(["SELL", item, quantity])
        action["market"] = orders[:10]


# Maturity-aware opponent front-run: fire when the OPPONENT's production is
# near-mature (imminent dump), regardless of clone status. Measured strictly
# >= clone-only front-run (vs purearch 1-12: +2605 10-2 vs +2568 9-3; vs c27
# +2114 8-0 vs +1783 7-1). Sells the shed product NOW before their glut.
_OPP_THRESH = {"STRAWBERRY": 4, "MELON": 3, "MILK": 3, "WOOL": 2}
_OPP_MAX_DAY = {"STRAWBERRY": 10, "MELON": 12}
# Aug-20 sweep: the maturity overlay costs ~1.6k/game in MARGIN vs purearch
# (clone-only +4.09k/j vs +2.47k/j, 20 seeds), BUT it converts to more WINS:
# h2h v2(maturity) vs v3(clone-only) = 11-1; vs c27 = 11-1 (v3 only 3-9).
# The ladder rates W/D/L, not margin, so the maturity overlay STAYS ON.
_ENABLE_MATURITY_FRONT_RUN = True


def _mature_opp_front_run(action, obs, step):
    farms = obs.get("farms", [])
    if len(farms) < 2:
        return
    tiles = farms[1].get("tiles", []) or []
    day = int(obs.get("day", 0) or 0)
    prod = {"STRAWBERRY": 0, "MELON": 0, "MILK": 0, "WOOL": 0}
    for row in tiles:
        for t in row:
            if not isinstance(t, dict):
                continue
            if t.get("kind") == "PLANT":
                c = t.get("crop")
                if c in ("STRAWBERRY", "MELON"):
                    age = day - int(t.get("planted_day", day))
                    if age >= _OPP_MAX_DAY[c] - 2 and int(t.get("yield_units", 0) or 0) > 0:
                        prod[c] += 1
            elif t.get("animal"):
                p = {"COW": "MILK", "SHEEP": "WOOL"}.get(t["animal"])
                if p and int(t.get("yield_units", 0) or 0) > 0:
                    prod[p] += 1
    orders = list(action.get("market", []) or [])
    if len(orders) >= 10:
        return
    already = set()
    for o in orders:
        if isinstance(o, list) and len(o) >= 2 and o[0] == "SELL":
            already.add(o[1])
    shed = (obs.get("private") or {}).get("shed") or {}
    for item, thresh in _OPP_THRESH.items():
        if prod.get(item, 0) >= thresh and item not in already \
                and int(shed.get(item, 0) or 0) > 0 and len(orders) < 10:
            orders.append(["SELL", item, int(shed.get(item, 0) or 0)])
            already.add(item)
    action["market"] = orders[:10]


# Order-slot sell-first (market-chess insight): market orders process by
# position — a SELL in an earlier slot alters the price a later-slot SELL
# faces (the opponent's). Put the premium sells FIRST so the opponent's
# later sells get a worse price. Zero capital cost (reordering only).
# Measured vs purearch seeds 1-12: +3355 (11-1) vs +2605 (10-2) baseline.
_FRONT_FIRST_ITEMS = ("MELON", "STRAWBERRY", "MILK", "WOOL")


def _sell_first(action, obs, step):
    market = list(action.get("market", []) or [])
    sells = []
    others = []
    for o in market:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
            sells.append(o)
        else:
            others.append(o)
    sells.sort(key=lambda o: (o[1] not in _FRONT_FIRST_ITEMS, -(o[2] or 0)))
    action["market"] = (sells + others)[:10]
    return action


def agent(obs, config=None):
    step = min(int(obs.get("step", 0) or 0), len(pa._MARKET_TRACE) - 1)
    # Clone-profile lifecycle (same reset rule as c27_agent).
    if step == 0 or step <= c27_agent._LAST_STEP:
        c27_agent._CLONE_CONFIDENCE = 0
    c27_agent._LAST_STEP = step
    c27_agent._update_clone_profile(obs, step)
    # Base = purearch's proven trace (its agent also handles terminal).
    action = pa.agent(obs, config)
    # Overlay 1: front-run vs clones (scheduled-glut proxy).
    _front_run_purearch(action, obs, step)
    # Overlay 2: front-run vs any opponent with near-mature premium production.
    # ON (see _ENABLE_MATURITY_FRONT_RUN): it converts margin into WINS.
    if _ENABLE_MATURITY_FRONT_RUN:
        _mature_opp_front_run(action, obs, step)
    # Overlay 3: order-slot sell-first (premium sells process before the
    # opponent's later-slot sells, worsening their price).
    return _sell_first(action, obs, step)


if __name__ == "__main__":
    from kaggle_environments import make
    import statistics
    seeds = [1, 2, 3, 4]
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "starter"])
        print(f"seed {s} vs starter:", env.steps[-1][0]["reward"])
