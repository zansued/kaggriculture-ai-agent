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

# Market-flow horizon inference (ported from Moon V56, public). We learn the
# opponent's premium sale horizon (1-6) from public market inventory deltas,
# so the front-run preempts at the RIGHT lead time instead of a fixed 2.
_SHOP_PRODUCTS = {
    "BAKERY": ("EGG", "WHEAT"), "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"), "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"), "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"), "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}
_ADAPT_MAX_OPP_HORIZON = 6
_ADAPT_MIN_EVIDENCE = 1.50
_ADAPT_DECAY = 0.999
_MF_STATE = {0: {}, 1: {}}


def _mf_seat(obs):
    return int(obs.get("player", 0) or 0)


def _mf_planned(step, item):
    """Purearch's (our base trace's) planned premium SELL at `step`."""
    if not (0 <= step < len(pa._MARKET_TRACE)):
        return 0
    return sum(
        max(0, int(o[2])) for o in pa._MARKET_TRACE[step]
        if len(o) >= 3 and o[0] == "SELL" and o[1] == item
    )


def _mf_town_drain(step, shops, item):
    drain = 0
    if step % 4 == 0:
        for shop in shops or ():
            products = _SHOP_PRODUCTS.get(shop, ())
            if item in products:
                drain += 2 if len(products) == 1 else 1
    if step % 24 == 0:
        drain += 1
    return drain


def _mf_state(obs, step):
    seat = _mf_seat(obs)
    st = _MF_STATE[seat]
    if step == 0 or step < int(st.get("last_step", -1)):
        st = {
            "last_step": -1, "inventory": {}, "prices": {}, "own_sells": {}, "shops": (),
            "scores": {item: {h: 0.0 for h in range(1, _ADAPT_MAX_OPP_HORIZON + 1)} for item in _FRONT_RUN_ITEMS},
            "evidence": {item: 0.0 for item in _FRONT_RUN_ITEMS},
            "horizon": {item: 2 for item in _FRONT_RUN_ITEMS},
        }
        _MF_STATE[seat] = st
    return st


def _mf_observe(obs, step):
    st = _mf_state(obs, step)
    market = obs.get("market", {}) or {}
    current = dict(market.get("inventory", {}) or {})
    current_prices = dict(market.get("prices", {}) or {})
    previous = dict(st.get("inventory", {}) or {})
    previous_prices = dict(st.get("prices", {}) or {})
    prev_step = int(st.get("last_step", -1))
    for item in _FRONT_RUN_ITEMS:
        st["evidence"][item] *= _ADAPT_DECAY
        for h in st["scores"][item]:
            st["scores"][item][h] *= _ADAPT_DECAY
    if previous and prev_step == step - 1 and _mf_clone_dist(obs) <= 6:
        own = dict(st.get("own_sells", {}) or {})
        shops = tuple(st.get("shops", ()) or ())
        for item in _FRONT_RUN_ITEMS:
            if float(previous_prices.get(item, 2) or 0) <= 1 or float(current_prices.get(item, 2) or 0) <= 1:
                continue
            delta = int(current.get(item, 0) or 0) - int(previous.get(item, 0) or 0)
            opp_supply = delta + _mf_town_drain(prev_step, shops, item) - int(own.get(item, 0) or 0)
            extra = opp_supply - _mf_planned(prev_step, item)
            if extra < 4:
                continue
            st["evidence"][item] += 1.0
            for h in range(1, _ADAPT_MAX_OPP_HORIZON + 1):
                expected = _mf_planned(prev_step + h, item)
                if expected > 0:
                    sim = min(extra, expected) / float(max(extra, expected))
                    st["scores"][item][h] += 1.0 + sim
    st["shops"] = tuple(obs.get("town", {}).get("unlocked_shops", []) or [])
    st["inventory"] = current
    st["prices"] = current_prices
    st["last_step"] = step
    for item in _FRONT_RUN_ITEMS:
        if st["evidence"][item] >= _ADAPT_MIN_EVIDENCE:
            st["horizon"][item] = max(range(1, _ADAPT_MAX_OPP_HORIZON + 1),
                                     key=lambda h: st["scores"][item][h])


def _mf_horizon(obs, step, item):
    return int(_mf_state(obs, step).get("horizon", {}).get(item, _FRONT_RUN_HORIZON))


def _mf_clone_dist(obs):
    """Public-farm signature distance (Moon-style). <= 6 = clone-like."""
    farms = obs.get("farms", []) or []
    if len(farms) < 2:
        return 10 ** 9
    return c27_agent._signature_distance(
        c27_agent._public_signature(farms[0]),
        c27_agent._public_signature(farms[1]),
    )


def _preempt_mf(action, obs, step):
    """Adaptive-horizon preempt (Moon V56 style): sell premium now at the
    LEARNED opponent sale horizon, capped by the trace's planned future sale."""
    if _mf_clone_dist(obs) > 6:
        return action
    market = list(action.get("market", []) or [])
    if len(market) >= 10:
        return action
    shed = (obs.get("private") or {}).get("shed") or {}
    prices = ((obs.get("market") or {}).get("prices") or {})
    remaining = {item: int(shed.get(item, 0) or 0) for item in _FRONT_RUN_ITEMS}
    for o in market:
        if len(o) >= 3 and o[0] == "SELL":
            remaining[o[1]] = max(0, remaining.get(o[1], 0) - max(0, int(o[2])))
    already = set()
    for o in market:
        if len(o) >= 2 and o[0] == "SELL":
            already.add(o[1])
    choices = []
    for item in _FRONT_RUN_ITEMS:
        if item in already or remaining.get(item, 0) <= 0:
            continue
        if float(prices.get(item, 0) or 0) < 1:
            continue
        pref = _mf_horizon(obs, step, item)
        for h in range(pref, 0, -1):
            fq = _mf_planned(step + h, item)
            if fq < 4:
                continue
            target = min(remaining.get(item, 0), fq, 12, max(1, round(fq)))
            if target > 0:
                choices.append((float(prices.get(item, 0) or 0) * target, item, target, h))
                break
    if not choices:
        return action
    adapted = [c for c in choices if c[3] > 1]
    selected = [max(adapted)] if adapted else [max(choices)]
    for _, item, target, _h in selected:
        if len(market) >= 10:
            break
        market.append(["SELL", item, target])
    action["market"] = market[:10]
    return action


def _front_run_purearch(action, obs, step):
    """Sell the premium purearch is about to dump, before the clone's glut.
    Fixed 2-turn lookahead (the clone's scheduled glut proxy)."""
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
_OPP_THRESH = {"STRAWBERRY": 6, "MELON": 4, "MILK": 4, "WOOL": 3}
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
# (Threat-based refinement was WORSE — +3153 — simple premium-first is best.)
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
    # Market-flow horizon inference (observe BEFORE deciding).
    _mf_observe(obs, step)
    # Base = purearch's proven trace (its agent also handles terminal).
    action = pa.agent(obs, config)
    # Overlay 1: front-run vs clones (fixed 2-turn scheduled-glut proxy).
    _front_run_purearch(action, obs, step)
    # Overlay 2: front-run vs any opponent with near-mature premium production.
    # ON (see _ENABLE_MATURITY_FRONT_RUN): it converts margin into WINS.
    if _ENABLE_MATURITY_FRONT_RUN:
        _mature_opp_front_run(action, obs, step)
    # Overlay 3: adaptive-horizon preempt (Moon V56 market-flow inference).
    _preempt_mf(action, obs, step)
    # Overlay 4: order-slot sell-first (premium sells process before the
    # opponent's later-slot sells, worsening their price).
    action = _sell_first(action, obs, step)
    # Record our own sells for the market-flow ledger.
    st = _mf_state(obs, step)
    own = {}
    for o in action.get("market", []) or []:
        if len(o) >= 3 and o[0] == "SELL" and o[1] in _FRONT_RUN_ITEMS:
            own[o[1]] = own.get(o[1], 0) + max(0, int(o[2] or 0))
    st["own_sells"] = own
    return action


if __name__ == "__main__":
    from kaggle_environments import make
    import statistics
    seeds = [1, 2, 3, 4]
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "starter"])
        print(f"seed {s} vs starter:", env.steps[-1][0]["reward"])
