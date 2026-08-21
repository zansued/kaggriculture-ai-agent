"""mix_marketflow: port of Moon V56's market-flow horizon inference into the mix.

Moon V56 (public ~2736-2913) crushes our mix 8-0 (+21k). Its edge is a
market-flow preempt that LEARNS the opponent's sale horizon (1-6) from public
market inventory deltas, instead of a fixed 2-turn lookahead. This works even
against non-clone opponents (whose farm doesn't reveal the glut).

Mechanism (ported from the public Moon V56 source):
  1. _observe: each step, compute opponent_supply = market_inventory_delta
     + town_drain - own_sells. If the opponent sold EXTRA beyond what purearch
     (our base trace) planned to sell at that step, score each horizon 1-6 by
     how well it matches. Evidence decays over time.
  2. _adaptive_horizon(item): the best-scoring horizon per item.
  3. _preempt_mf: sell premium now (from shed) at the adaptive horizon, capped
     by the trace's planned future sale + max batch. Falls back to horizon 1.

The base "planned" reference is PUREARCH's trace (our mix base). Clone gate:
only fire when the opponent's public signature is clone-like (distance <= 6).

Usage: import mix_marketflow; mix_marketflow.agent(obs) — self-contained.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))

import mix_agent  # noqa: E402
import purearch_opponent as pa  # noqa: E402
import c27_agent  # noqa: E402

_PREMIUM = ("MELON", "STRAWBERRY", "MILK", "WOOL")
_BASE_PRICE = {"MELON": 250, "STRAWBERRY": 120, "MILK": 160, "WOOL": 200}
_SHOP_PRODUCTS = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}
_ADAPT_MAX_OPP_HORIZON = 6
_ADAPT_MIN_EVIDENCE = 1.50
_ADAPT_DECAY = 0.999
_PREEMPT_MIN_FUTURE_QUANTITY = 4
_PREEMPT_MAX_BATCH = 12
_PREEMPT_MAX_CLONE_DISTANCE = 6
_PREEMPT_FRACTION = 1.0
_PREEMPT_START = 120
_PREEMPT_STOP = 680

_RACE_STATE = {0: {}, 1: {}}


def _get(d, k, default=None):
    return d.get(k, default) if isinstance(d, dict) else default


def _seat(obs):
    return int(obs.get("player", 0) or 0)


def _public_signature(farm):
    counts = {item: 0 for item in (
        "COW", "SHEEP", "GOOSE", "WHEAT", "CARROT", "TOMATO",
        "STRAWBERRY", "MELON", "PASTURE", "COOP", "WEED")}
    for row in farm.get("tiles", []) or []:
        for tile in row or []:
            if not isinstance(tile, dict):
                continue
            for key in ("animal", "crop", "kind"):
                v = tile.get(key)
                if v in counts:
                    counts[v] += 1
                    break
    return (len(farm.get("hands", []) or []),
            tuple(sorted(farm.get("unlocked_quadrants", []) or [])),
            tuple(counts[item] for item in sorted(counts)))


def _clone_distance(obs):
    farms = list(_get(obs, "farms", []) or [])
    if len(farms) < 2:
        return 10 ** 9
    left, right = _public_signature(farms[0]), _public_signature(farms[1])
    return (abs(left[0] - right[0])
            + 3 * abs(len(left[1]) - len(right[1]))
            + sum(abs(a - b) for a, b in zip(left[2], right[2])))


def _planned_premium(step, item):
    """Purearch's (our base trace's) planned premium SELL at `step`."""
    if not (0 <= step < len(pa._MARKET_TRACE)):
        return 0
    return sum(
        max(0, int(o[2])) for o in pa._MARKET_TRACE[step]
        if len(o) >= 3 and o[0] == "SELL" and o[1] == item
    )


def _town_drain(step, shops, item):
    drain = 0
    if step % 4 == 0:
        for shop in shops or ():
            products = _SHOP_PRODUCTS.get(shop, ())
            if item in products:
                drain += 2 if len(products) == 1 else 1
    if step % 24 == 0:
        drain += 1
    return drain


def _race_state(obs, step):
    seat = _seat(obs)
    state = _RACE_STATE[seat]
    if step == 0 or step < int(state.get("last_step", -1)):
        state = {
            "last_step": -1, "inventory": {}, "prices": {}, "own_sells": {}, "shops": (),
            "scores": {item: {h: 0.0 for h in range(1, _ADAPT_MAX_OPP_HORIZON + 1)} for item in _PREMIUM},
            "evidence": {item: 0.0 for item in _PREMIUM},
            "horizon": {item: 1 for item in _PREMIUM},
        }
        _RACE_STATE[seat] = state
    return state


def _observe(obs, step):
    state = _race_state(obs, step)
    market = _get(obs, "market", {}) or {}
    current = dict(_get(market, "inventory", {}) or {})
    current_prices = dict(_get(market, "prices", {}) or {})
    previous = dict(state.get("inventory", {}) or {})
    previous_prices = dict(state.get("prices", {}) or {})
    prev_step = int(state.get("last_step", -1))

    for item in _PREMIUM:
        state["evidence"][item] *= _ADAPT_DECAY
        for h in state["scores"][item]:
            state["scores"][item][h] *= _ADAPT_DECAY

    if previous and prev_step == step - 1 and _clone_distance(obs) <= _PREEMPT_MAX_CLONE_DISTANCE:
        own = dict(state.get("own_sells", {}) or {})
        shops = tuple(state.get("shops", ()) or ())
        for item in _PREMIUM:
            if float(previous_prices.get(item, 2) or 0) <= 1 or float(current_prices.get(item, 2) or 0) <= 1:
                continue
            delta = int(current.get(item, 0) or 0) - int(previous.get(item, 0) or 0)
            opp_supply = delta + _town_drain(prev_step, shops, item) - int(own.get(item, 0) or 0)
            extra = opp_supply - _planned_premium(prev_step, item)
            if extra < _PREEMPT_MIN_FUTURE_QUANTITY:
                continue
            state["evidence"][item] += 1.0
            for h in range(1, _ADAPT_MAX_OPP_HORIZON + 1):
                expected = _planned_premium(prev_step + h, item)
                if expected > 0:
                    sim = min(extra, expected) / float(max(extra, expected))
                    state["scores"][item][h] += 1.0 + sim

    # Refresh shops / own-sell ledger from the action we emitted last step.
    state["shops"] = tuple(obs.get("town", {}).get("unlocked_shops", []) or [])
    state["inventory"] = current
    state["prices"] = current_prices
    state["last_step"] = step

    # Derive horizons from evidence.
    for item in _PREMIUM:
        if state["evidence"][item] >= _ADAPT_MIN_EVIDENCE:
            best_h = max(range(1, _ADAPT_MAX_OPP_HORIZON + 1),
                        key=lambda h: state["scores"][item][h])
            state["horizon"][item] = best_h


def _record_own_sells(obs, action, step):
    state = _race_state(obs, step)
    own = {}
    for o in action.get("market", []) or []:
        if len(o) >= 3 and o[0] == "SELL" and o[1] in _PREMIUM:
            own[o[1]] = own.get(o[1], 0) + max(0, int(o[2] or 0))
    state["own_sells"] = own


def _preempt_mf(action, obs, step):
    if not (_PREEMPT_START <= step < _PREEMPT_STOP):
        return action
    if _clone_distance(obs) > _PREEMPT_MAX_CLONE_DISTANCE:
        return action
    market = list(action.get("market") or [])
    if len(market) >= 10:
        return action
    shed = (obs.get("private") or {}).get("shed") or {}
    prices = _get(_get(obs, "market", {}) or {}, "prices", {}) or {}
    remaining = {item: int(shed.get(item, 0) or 0) for item in _PREMIUM}
    for o in market:
        if len(o) >= 3 and o[0] == "SELL":
            remaining[o[1]] = max(0, remaining.get(o[1], 0) - max(0, int(o[2])))
    already = set()
    for o in market:
        if len(o) >= 2 and o[0] == "SELL":
            already.add(o[1])
    choices = []
    state = _race_state(obs, step)
    for item in _PREMIUM:
        if item in already:
            continue
        if float(_get(prices, item, 0) or 0) < 1:
            continue
        preferred = int(state["horizon"].get(item, 1))
        for h in range(preferred, 0, -1):
            fq = _planned_premium(step + h, item)
            if fq < _PREEMPT_MIN_FUTURE_QUANTITY:
                continue
            target = min(max(0, remaining.get(item, 0) or 0), fq,
                         _PREEMPT_MAX_BATCH, max(1, round(fq * _PREEMPT_FRACTION)))
            if target > 0:
                choices.append((float(_get(prices, item, 0) or 0) * target, item, target, h))
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


def agent(obs, config=None):
    step = int(obs.get("step", 0) or 0)
    action = mix_agent.agent(obs, config)
    _observe(obs, step)
    action = _preempt_mf(action, obs, step)
    action = mix_agent._sell_first(action, obs, step)
    _record_own_sells(obs, action, step)
    return action


if __name__ == "__main__":
    from kaggle_environments import make
    import statistics
    seeds = list(range(1, 13))
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, pa.agent])
        last = env.steps[-1]
        print(f"seed {s}: d={last[0]['reward']-last[1]['reward']:+.0f}")
