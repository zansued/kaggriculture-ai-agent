"""Generic trace-driven opponent with the purearch robustness layer.

Loads a trace {units, markets} from a JSON file and exposes an `agent(obs)`
that replays the schedule, applying purearch's repair layers:
  * _sort_market        — reorder SELL orders by price/value, keep BUY orders
  * _repair_pasture     — DIG weeds before BUILD_PASTURE
  * _repair_late_wheat  — DIG weeds before late PLANT WHEAT
  * _terminal_action    — dump all products at end

Usage:
    import trace_agent
    agent = trace_agent.load_trace_agent("path/to/trace.json")
"""
from __future__ import annotations

import copy
import json

_PRODUCTS = {
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER",
}
_SELL_TIE_PRIORITY = {
    "WOOL": 8, "MELON": 7, "MILK": 6, "STRAWBERRY": 5,
    "CARROT": 4, "FERTILIZER": 3, "WHEAT": 2, "EGG": 1,
}
_NON_SELL_PRIORITY = {
    "HIRE": 0,
    "BUY_ANIMAL": 1,
    "BUY_LAND": 2,
    "BUY_SEED": 3,
    "BUY_PRODUCT": 4,
}

# Optional price gating: when non-None, _sort_market drops SELL orders for a
# product when its current price is below the gate. Products with no gate are
# always sold. Kept as a module global so experiments can toggle it.
PRICE_GATES = None  # e.g. {"MILK": 120, "STRAWBERRY": 80, "MELON": 150}


def enable_price_gates(gates):
    global PRICE_GATES
    PRICE_GATES = dict(gates) if gates else None


def _make_globals():
    return {
        "_UNIT_TRACE": None,
        "_MARKET_TRACE": None,
        "_PENDING_PASTURE": None,
        "_FARMER_SHIFT_END": None,
        "_PENDING_PLANT": None,
        "_PENDING_WATER": None,
        "_WATER_SHIFT": None,
        "_REPAIR_ACTIVATED": False,
    }


def _tile_at(farm, position):
    if not isinstance(position, (list, tuple)) or len(position) != 2:
        return "OUT_OF_BOUNDS"
    x, y = map(int, position)
    tiles = farm.get("tiles", []) or []
    if not (0 <= y < len(tiles) and 0 <= x < len(tiles[y])):
        return "OUT_OF_BOUNDS"
    return tiles[y][x]


def _base_action(obs, G):
    step = min(max(int(obs.get("step", 0) or 0), 0), len(G["_UNIT_TRACE"]) - 1)
    action = copy.deepcopy(G["_UNIT_TRACE"][step])
    action["market"] = copy.deepcopy(G["_MARKET_TRACE"][step])
    return action


def _sort_market(action, obs):
    step = int(obs.get("step", 0) or 0)
    if not (300 <= step < 716):
        return action
    orders = list(action.get("market", []) or [])[:10]
    prices = ((obs.get("market", {}) or {}).get("prices", {}) or {})

    gates = PRICE_GATES or {}
    sells = []
    others = []
    for index, order in enumerate(orders):
        if order and order[0] == "SELL" and len(order) >= 3:
            item = str(order[1])
            quantity = max(0, int(order[2] or 0))
            price = max(0, int(prices.get(item, 0) or 0))
            gate = gates.get(item)
            if gate is not None and price < gate:
                continue  # hold the product instead of selling into a crash
            sells.append((-(price * quantity), -price, -quantity, -_SELL_TIE_PRIORITY.get(item, 0), index, order))
        else:
            op = str(order[0]) if order else ""
            others.append((_NON_SELL_PRIORITY.get(op, 99), index, order))
    sells.sort()
    others.sort()
    action["market"] = [x[-1] for x in sells] + [x[-1] for x in others]
    return action


def _best_terminal_item(inventory, prices):
    choices = []
    for item, quantity in (inventory or {}).items():
        quantity = int(quantity or 0)
        if item not in _PRODUCTS or quantity <= 0:
            continue
        price = int(prices.get(item, 0) or 0)
        choices.append((price * quantity, price, quantity, _SELL_TIE_PRIORITY.get(item, 0), item))
    return max(choices, default=None)


def _terminal_action(obs):
    private = obs.get("private", {}) or {}
    inventories = private.get("inventories", []) or []
    shed = private.get("shed", {}) or {}
    prices = ((obs.get("market", {}) or {}).get("prices", {}) or {})
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", []) or []
    farm = farms[player] if 0 <= player < len(farms) else {}
    hand_count = len(farm.get("hands", []) or [])

    placed = {}
    farmer = ["PASS"]
    if inventories:
        choice = _best_terminal_item(inventories[0], prices)
        if choice is not None:
            _, _, quantity, _, item = choice
            farmer = ["PLACE", item, quantity]
            placed[item] = placed.get(item, 0) + quantity

    hands = []
    for index in range(hand_count):
        inv = inventories[index + 1] if index + 1 < len(inventories) else {}
        choice = _best_terminal_item(inv, prices)
        if choice is None:
            hands.append(["PASS"])
        else:
            _, _, quantity, _, item = choice
            hands.append(["PLACE", item, quantity])
            placed[item] = placed.get(item, 0) + quantity

    totals = {}
    for item in _PRODUCTS:
        quantity = int(shed.get(item, 0) or 0) + int(placed.get(item, 0) or 0)
        if quantity > 0:
            totals[item] = quantity
    ordered = sorted(
        totals,
        key=lambda item: (
            int(prices.get(item, 0) or 0) * totals[item],
            int(prices.get(item, 0) or 0),
            totals[item],
            _SELL_TIE_PRIORITY.get(item, 0),
        ),
        reverse=True,
    )
    return {
        "farmer": farmer,
        "hands": hands,
        "market": [["SELL", item, totals[item]] for item in ordered[:10]],
    }


def _repair_pasture(obs, action, G):
    step = int(obs.get("step", 0) or 0)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", []) or []
    if not (0 <= player < len(farms)):
        return action
    farm = farms[player] or {}
    hands = farm.get("hands", []) or []
    hand_actions = list(action.get("hands", []) or [])

    if G["_FARMER_SHIFT_END"] is not None:
        if step <= G["_FARMER_SHIFT_END"]:
            previous = max(0, step - 1)
            action["farmer"] = copy.deepcopy(G["_UNIT_TRACE"][previous]["farmer"])
        else:
            G["_FARMER_SHIFT_END"] = None

    if G["_PENDING_PASTURE"] is not None:
        channel, actor, position, expected_step = G["_PENDING_PASTURE"]
        if step == expected_step:
            if channel == "farmer":
                current = farm.get("farmer")
                if list(current or []) == position and _tile_at(farm, current) is None:
                    action["farmer"] = ["BUILD_PASTURE"]
            elif 0 <= actor < len(hands) and actor < len(hand_actions):
                if list(hands[actor]) == position and _tile_at(farm, hands[actor]) is None:
                    hand_actions[actor] = ["BUILD_PASTURE"]
        G["_PENDING_PASTURE"] = None

    farmer_position = farm.get("farmer")
    farmer_tile = _tile_at(farm, farmer_position)
    if action.get("farmer") == ["BUILD_PASTURE"] and isinstance(farmer_tile, dict) and farmer_tile.get("kind") == "WEED":
        action["farmer"] = ["DIG"]
        if step % 24 >= 20:
            G["_FARMER_SHIFT_END"] = (step // 24 + 1) * 24 - 1
        G["_PENDING_PASTURE"] = ("farmer", None, list(farmer_position), step + 1)

    for actor, requested in enumerate(hand_actions[:len(hands)]):
        if G["_PENDING_PASTURE"] is not None:
            break
        if requested != ["BUILD_PASTURE"]:
            continue
        if isinstance(_tile_at(farm, hands[actor]), dict) and _tile_at(farm, hands[actor]).get("kind") == "WEED":
            hand_actions[actor] = ["DIG"]
            G["_PENDING_PASTURE"] = ("hands", actor, list(hands[actor]), step + 1)
            break
    action["hands"] = hand_actions
    return action


def _repair_late_wheat(obs, action, G):
    step = int(obs.get("step", 0) or 0)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", []) or []
    if not (0 <= player < len(farms)):
        return action
    farm = farms[player] or {}
    positions = farm.get("hands", []) or []
    hand_actions = list(action.get("hands", []) or [])
    seeds = ((obs.get("private", {}) or {}).get("seeds", {}) or {})

    if G["_WATER_SHIFT"] is not None:
        actor, end_step = G["_WATER_SHIFT"]
        if step <= end_step and actor < len(hand_actions):
            previous = max(0, step - 1)
            prev_hands = G["_UNIT_TRACE"][previous]["hands"]
            if actor < len(prev_hands):
                hand_actions[actor] = copy.deepcopy(prev_hands[actor])
        else:
            G["_WATER_SHIFT"] = None

    if G["_PENDING_WATER"] is not None:
        position, planter, expected_step = G["_PENDING_WATER"]
        if step == expected_step and isinstance(_tile_at(farm, position), dict):
            actor = next((i for i, p in enumerate(positions) if i != planter and i < len(hand_actions) and list(p) == position), planter if planter < len(hand_actions) else None)
            if actor is not None:
                hand_actions[actor] = ["WATER"]
                G["_WATER_SHIFT"] = (actor, (step // 24 + 1) * 24 - 1)
        G["_PENDING_WATER"] = None

    if G["_PENDING_PLANT"] is not None:
        actor, crop, position, expected_step = G["_PENDING_PLANT"]
        if step == expected_step and actor < len(positions) and actor < len(hand_actions) and list(positions[actor]) == position and _tile_at(farm, positions[actor]) is None and int(seeds.get(crop, 0) or 0) > 0:
            hand_actions[actor] = ["PLANT", crop]
            G["_PENDING_WATER"] = (list(position), actor, step + 1)
        G["_PENDING_PLANT"] = None

    if step == 636:
        for actor, requested in enumerate(hand_actions[:len(positions)]):
            if requested != ["PLANT", "WHEAT"]:
                continue
            tile = _tile_at(farm, positions[actor])
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                hand_actions[actor] = ["DIG"]
                G["_PENDING_PLANT"] = (actor, "WHEAT", list(positions[actor]), step + 1)
                G["_REPAIR_ACTIVATED"] = True
                break
    action["hands"] = hand_actions
    return action


def load_trace_agent(trace_path: str):
    with open(trace_path, encoding="utf-8") as f:
        trace = json.load(f)
    G = _make_globals()
    G["_UNIT_TRACE"] = trace["units"]
    G["_MARKET_TRACE"] = trace["markets"]

    def agent(obs, config=None):
        step = int(obs.get("step", 0) or 0)
        if step == 0:
            for k in G:
                if k.startswith("_PENDING") or k in ("_WATER_SHIFT", "_FARMER_SHIFT_END"):
                    G[k] = None
                elif k == "_REPAIR_ACTIVATED":
                    G[k] = False

        if step >= 716:
            return _terminal_action(obs)

        action = _base_action(obs, G)
        action = _sort_market(action, obs)
        action = _repair_pasture(obs, action, G)
        action = _repair_late_wheat(obs, action, G)
        return action

    return agent
