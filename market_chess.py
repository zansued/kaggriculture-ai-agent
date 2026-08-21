"""Market Chess overlays on top of mix_agent (modify market orders only).

Per the deep-research report, production + selling are coupled — do NOT touch
the base schedule. These overlays change ONLY market orders:

  1. TOWN SCALP: buy WHEAT right before a known town-consumption tick (shops
     every 4 turns, town center every 24), sell the position next turn. The
     engine processes market orders BEFORE town consumption, so the town's
     deterministic drain creates a positive buy/sell spread. Small q, strict
     cash/shed guards, sell-first on the close.

  2. SELL-FIRST (order-slot front-run): market orders process by position —
     a SELL in an earlier slot alters the price an opponent sale in a later
     slot faces. Reorder the market list so high-threat premium sells come
     first (before the trace's baseline sells).

  3. PRICE-FLOOR DENIAL: when the opponent has heavy near-mature premium
     exposure, sell just enough of my shed stock to drag their sale price
     down — but STOP before the $1 floor (sales at $1 add no supply, so
     denial past the floor is worthless).

Guards are conservative: never break the production cash flow.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))

import mix_agent  # noqa: E402
import purearch_opponent as pa  # noqa: E402

# ---- Town scalp config ----------------------------------------------------- #
_SCALP_MIN_DRAIN = 3       # only scalp when the known wheat drain >= this
_SCALP_Q = 5               # wheat units to buy per scalp
_SCALP_CASH_RESERVE = 10000  # keep this much cash (protect production)
_SCALP_MAX_PRICE = 38      # don't scalp if wheat already expensive
_SCALP_DAY_START = 15      # only scalp late (production cash is established)
_WHEAT_SHOPS = {"BAKERY", "PIZZA_SHOP", "BRUNCH_SPOT", "ICE_CREAM_SHOP", "FARMERS_MARKET"}
_scalp_pos = 0             # current scalp position (units bought, pending sell)


def _known_wheat_drain(obs, step):
    """Deterministic wheat drain this turn: shops every 4 turns + town center
    every 24 turns (market orders process BEFORE town consumption)."""
    drain = 0
    if step % 4 == 0:
        shops = obs.get("town", {}).get("unlocked_shops", []) or []
        drain += sum(1 for s in shops if s in _WHEAT_SHOPS)
    if step % 24 == 0:
        drain += 1
    return drain


def _town_scalp(action, obs, step):
    """Open on a known consumption tick, close next turn (sell-first)."""
    global _scalp_pos
    money = float(obs["farms"][int(obs.get("player", 0) or 0)].get("money", 0.0))
    prices = obs.get("market", {}).get("prices", {})
    shed = obs.get("private", {}).get("shed", {})
    wheat_price = float(prices.get("WHEAT", 25) or 25)
    market = list(action.get("market", []) or [])

    # CLOSE: if we hold a scalp position, sell it FIRST (before baseline).
    if _scalp_pos > 0:
        market = [["SELL", "WHEAT", _scalp_pos]] + market
        _scalp_pos = 0

    # OPEN: on a known drain tick, buy q wheat as the LAST order.
    drain = _known_wheat_drain(obs, step)
    day = int(obs.get("day", 0) or 0)
    if (_scalp_pos == 0 and drain >= _SCALP_MIN_DRAIN
            and day >= _SCALP_DAY_START
            and wheat_price <= _SCALP_MAX_PRICE
            and money >= _SCALP_CASH_RESERVE + _SCALP_Q * wheat_price
            and len(market) < 10
            and int(shed.get("WHEAT", 0) or 0) + _SCALP_Q <= 60):  # shed guard
        market.append(["BUY_PRODUCT", "WHEAT", _SCALP_Q])
        _scalp_pos = _SCALP_Q

    action["market"] = market[:10]
    return action


# ---- Price-floor capped denial -------------------------------------------- #
_DENIAL_FLOOR_GUARD = 2  # don't sell into denial if price would fall below this
_DENIAL_DAY_START = 10   # forced-liquidation pressure matters from ~d10
_DENIAL_MIN_EXP = 4      # opponent near-mature exposure threshold


def _price_floor_denial(action, obs, step):
    """Sell shed premium to drag the opponent's near-mature exposure down,
    capped BEFORE the $1 floor (sales at $1 add no supply)."""
    farms = obs.get("farms", [])
    if len(farms) < 2:
        return action
    day = int(obs.get("day", 0) or 0)
    if day < _DENIAL_DAY_START:
        return action
    tiles = farms[1].get("tiles", []) or []
    # Opponent near-mature premium exposure.
    threat = {}
    for row in tiles:
        for t in row:
            if not isinstance(t, dict):
                continue
            if t.get("kind") == "PLANT":
                c = t.get("crop")
                if c in ("STRAWBERRY", "MELON"):
                    age = day - int(t.get("planted_day", day))
                    if age >= (10 if c == "STRAWBERRY" else 12) - 2 and int(t.get("yield_units", 0) or 0) > 0:
                        threat[c] = threat.get(c, 0) + 1
            elif t.get("animal"):
                p = {"COW": "MILK", "SHEEP": "WOOL"}.get(t["animal"])
                if p and int(t.get("yield_units", 0) or 0) > 0:
                    threat[p] = threat.get(p, 0) + 1
    # Denial: opponent exposure high, I have shed stock of the same product.
    shed = obs.get("private", {}).get("shed", {})
    prices = obs.get("market", {}).get("prices", {})
    market = list(action.get("market", []) or [])
    already = set()
    for o in market:
        if isinstance(o, list) and len(o) >= 2 and o[0] == "SELL":
            already.add(o[1])
    for item, opp_exp in threat.items():
        if opp_exp < _DENIAL_MIN_EXP:
            continue
        if item in already:
            continue
        qty = int(shed.get(item, 0) or 0)
        price = float(prices.get(item, 0) or 0)
        if qty <= 0 or price <= _DENIAL_FLOOR_GUARD or len(market) >= 10:
            continue
        # Sell a chunk (not all — cap before the floor). Front-load it.
        sell_q = min(qty, max(3, opp_exp // 2))
        market.insert(0, ["SELL", item, sell_q])
        already.add(item)
    action["market"] = market[:10]
    return action


# Order-slot sell-first: market orders process by position — a SELL in an
# earlier slot alters the price a later-slot SELL faces. Put the premium
# sells (which compete with the opponent's glut) FIRST, so the opponent's
# later sells get a worse price. Zero capital cost (just reordering).
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
    # Sort sells: premium products first (glut competitors), then by value.
    sells.sort(key=lambda o: (o[1] not in _FRONT_FIRST_ITEMS, -(o[2] or 0)))
    action["market"] = (sells + others)[:10]
    return action


def agent(obs, config=None):
    action = mix_agent.agent(obs, config)
    action = _town_scalp(action, obs, int(obs.get("step", 0) or 0))
    action = _price_floor_denial(action, obs, int(obs.get("step", 0) or 0))
    action = _sell_first(action, obs, int(obs.get("step", 0) or 0))
    return action


if __name__ == "__main__":
    from kaggle_environments import make
    import statistics
    seeds = [1, 2, 3, 4]
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "starter"])
        print(f"seed {s} vs starter:", env.steps[-1][0]["reward"])
