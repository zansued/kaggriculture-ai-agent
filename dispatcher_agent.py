"""Learned dispatcher agent: mimics the top agent's adaptive hand policy.

A RandomForest classifier (trained on 10 top-agent replays) predicts each
unit's ACTION TYPE from state features (position, current tile, distances,
prices, time). A greedy target selector picks the concrete tile/direction
for that action. The market logic comes from the cronograma (seed bursts,
sell shed, buy hands/animals/land).

The classifier captures the top agent's POLICY (75% acc on held-out replays),
generalizing across states — unlike a raw trace (state-coupled).

Usage: python dispatcher_agent.py (demo); h2h via h2h_bench.py
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "data", "kawasagi"))
sys.path.insert(0, os.path.join(_HERE, "src"))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
from kaggle_environments import make  # noqa: E402

import dispatch_extract as de  # noqa: E402
import kaggriculture_real as kr  # noqa: E402
from cronograma_agent import CronogramaAgent  # noqa: E402

# Load the trained classifier (path relative to repo root).
_MODEL_PATH = os.path.join(_HERE, "data", "kawasagi", "dispatcher_model.joblib")
_CLF = joblib.load(_MODEL_PATH) if os.path.exists(_MODEL_PATH) else None

# The market logic (seed bursts, sells, hires, buys).
_brain = CronogramaAgent()


def _nearest(farm, pred, hx, hy):
    """Nearest tile matching pred(tile)->bool. `tile` may be None (empty).
    Skips LOCKED tiles. Returns (x,y) or None."""
    tiles = farm.get("tiles", [])
    best = None
    best_d = 10 ** 9
    for y in range(len(tiles)):
        for x in range(len(tiles[y])):
            t = tiles[y][x]
            if t == "LOCKED" or (isinstance(t, str) and not isinstance(t, dict)):
                continue
            if pred(t):
                d = abs(x - hx) + abs(y - hy)
                if d < best_d:
                    best_d = d
                    best = (x, y)
    return best


def _move(x, y, tx, ty, tiles):
    """Move one step toward (tx,ty), avoiding LOCKED tiles. Returns action."""
    if tx < x:
        nx, ny = x - 1, y
        op = "WEST"
    elif tx > x:
        nx, ny = x + 1, y
        op = "EAST"
    elif ty < y:
        nx, ny = x, y - 1
        op = "NORTH"
    elif ty > y:
        nx, ny = x, y + 1
        op = "SOUTH"
    else:
        return ["PASS"]
    if 0 <= nx < len(tiles) and 0 <= ny < len(tiles) and tiles[ny][nx] != "LOCKED":
        return [op]
    # Blocked: try alternate axis.
    if tx != x and 0 <= y + (1 if ty > y else -1) < len(tiles) and tiles[y + (1 if ty > y else -1)][x] != "LOCKED":
        return ["SOUTH" if ty > y else "NORTH"]
    if ty != y and 0 <= x + (1 if tx > x else -1) < len(tiles) and tiles[y][x + (1 if tx > x else -1)] != "LOCKED":
        return ["EAST" if tx > x else "WEST"]
    return ["PASS"]


def _execute(cls, obs, farm, private, day, hour, hi, pos):
    """Map classifier class -> concrete action for the hand at pos."""
    tiles = farm.get("tiles", [])
    size = len(tiles)
    hx, hy = pos
    tile = tiles[hy][hx] if (0 <= hy < size and 0 <= hx < size) else None
    inv = (private.get("inventories") or [{}])[hi] if hi < len(private.get("inventories", [])) else {}
    shed = private.get("shed", {})

    is_plant = isinstance(tile, dict) and tile.get("kind") == kr.KIND_PLANT
    is_anim = isinstance(tile, dict) and (tile.get("kind") == kr.KIND_PASTURE or tile.get("kind") == kr.KIND_COOP) and tile.get("animal")
    is_weed = isinstance(tile, dict) and tile.get("kind") == kr.KIND_WEED
    is_empty = tile is None

    def _go_act(target, act):
        if target is None:
            return ["PASS"]
        if (hx, hy) == target:
            return act
        return _move(hx, hy, target[0], target[1], tiles)

    def _p(d):
        return isinstance(d, dict)

    # OVERRIDE (survival): on an unwatered plant -> WATER. Without this the
    # classifier over-plants and crops die (measured: 0 plants by day 8).
    if is_plant and not tile.get("watered_today", False):
        return ["WATER"]
    # OVERRIDE (expansion): the classifier under-predicts planting in sparse
    # farms (it predicts WATER on the one existing plant). If the farm has few
    # plants and seeds are available, PLANT at the nearest empty tile.
    seeds = private.get("seeds", {})
    n_plants = sum(1 for row in farm.get("tiles", []) for t in row
                   if isinstance(t, dict) and t.get("kind") == kr.KIND_PLANT)
    plant_crop = None
    for crop in ("MELON", "STRAWBERRY", "WHEAT", "CARROT"):
        if int(seeds.get(crop, 0) or 0) > 0:
            plant_crop = crop
            break
    if plant_crop is not None and n_plants < 12:
        if is_empty:
            return ["PLANT", plant_crop]
        target = _nearest(farm, lambda t: t is None, hx, hy)
        if target is not None:
            return _go_act(target, ["PLANT", plant_crop])

    # WATER
    if cls == de.ACTION_CLASSES["WATER"]:
        if is_plant and not tile.get("watered_today", False):
            return ["WATER"]
        return _go_act(_nearest(farm, lambda t: _p(t) and t.get("kind") == kr.KIND_PLANT and not t.get("watered_today", False), hx, hy), ["WATER"])
    # HARVEST
    if cls == de.ACTION_CLASSES["HARVEST"]:
        if is_plant and int(tile.get("yield_units", 0) or 0) > 0:
            return ["HARVEST"]
        if is_anim and int(tile.get("yield_units", 0) or 0) > 0:
            return ["HARVEST"]
        return _go_act(_nearest(farm, lambda t: _p(t) and t.get("kind") == kr.KIND_PLANT and int(t.get("yield_units", 0) or 0) > 0, hx, hy), ["HARVEST"])
    # DIG
    if cls == de.ACTION_CLASSES["DIG"]:
        if is_weed:
            return ["DIG"]
        return _go_act(_nearest(farm, lambda t: _p(t) and t.get("kind") == kr.KIND_WEED, hx, hy), ["DIG"])
    # FEED
    if cls == de.ACTION_CLASSES["FEED"]:
        if is_anim and not tile.get("fed_today", False):
            if inv.get("WHEAT", 0) > 0:
                return ["FEED"]
            return _go_act(kr._shed_tile(farm), ["PICKUP", "WHEAT", 1])
        return _go_act(_nearest(farm, lambda t: _p(t) and (t.get("kind") == kr.KIND_PASTURE or t.get("kind") == kr.KIND_COOP) and t.get("animal") and not t.get("fed_today", False), hx, hy), ["FEED"])
    # CARE
    if cls == de.ACTION_CLASSES["CARE"]:
        if is_anim and not tile.get("cared_today", False):
            return ["CARE"]
        return _go_act(_nearest(farm, lambda t: _p(t) and (t.get("kind") == kr.KIND_PASTURE or t.get("kind") == kr.KIND_COOP) and t.get("animal") and not t.get("cared_today", False), hx, hy), ["CARE"])
    # COLLECT_FERTILIZER
    if cls == de.ACTION_CLASSES["COLLECT_FERTILIZER"]:
        if is_anim and tile.get("fertilizer_available", False):
            return ["COLLECT_FERTILIZER"]
        return _go_act(_nearest(farm, lambda t: _p(t) and (t.get("kind") == kr.KIND_PASTURE or t.get("kind") == kr.KIND_COOP) and t.get("fertilizer_available", False), hx, hy), ["COLLECT_FERTILIZER"])
    # FERTILIZE
    if cls == de.ACTION_CLASSES["FERTILIZE"]:
        if is_plant and tile.get("crop") == "STRAWBERRY":
            return ["FERTILIZE"]
        return _go_act(_nearest(farm, lambda t: _p(t) and t.get("kind") == kr.KIND_PLANT and t.get("crop") == "STRAWBERRY", hx, hy), ["FERTILIZE"])
    # PLANT_*
    for crop, cls_id in [("WHEAT", 7), ("STRAWBERRY", 8), ("MELON", 9), ("CARROT", 10)]:
        if cls == de.ACTION_CLASSES["PLANT_" + crop]:
            if is_empty:
                return ["PLANT", crop]
            return _go_act(_nearest(farm, lambda t: t is None, hx, hy), ["PLANT", crop])
    # PICKUP (restock wheat for feeding) — only if shed actually has wheat.
    if cls == de.ACTION_CLASSES["PICKUP"]:
        if int(shed.get("WHEAT", 0) or 0) <= 0:
            return ["PASS"]
        st = kr._shed_tile(farm)
        if (hx, hy) == st:
            return ["PICKUP", "WHEAT", 1]
        return _go_act(st, ["PICKUP", "WHEAT", 1])
    # PLACE (deposit at shed)
    if cls == de.ACTION_CLASSES["PLACE"]:
        if is_anim and inv.get("COW", 0) > 0:
            return ["PLACE", "COW", 1]
        st = kr._shed_tile(farm)
        if (hx, hy) == st:
            for item, qty in inv.items():
                if qty > 0 and item not in ("COW", "SHEEP", "GOOSE"):
                    return ["PLACE", item, qty]
            return ["PASS"]
        return _go_act(st, ["PASS"])
    # BUILD_PASTURE
    if cls == de.ACTION_CLASSES["BUILD_PASTURE"]:
        if is_empty:
            return ["BUILD_PASTURE"]
        return _go_act(_nearest(farm, lambda t: t is None, hx, hy), ["BUILD_PASTURE"])
    # MOVE: toward the nearest "task" — plant (unwatered/mature), weed, animal,
    # or EMPTY tile (to plant). Without empty-tile targets the early game
    # collapses to PASS (farm is empty).
    if cls == de.ACTION_CLASSES["MOVE"]:
        def _is_task(t):
            if t is None:
                return True  # empty tile -> go plant
            if not isinstance(t, dict):
                return False
            k = t.get("kind")
            if k == kr.KIND_PLANT:
                return not t.get("watered_today", False) or int(t.get("yield_units", 0) or 0) > 0
            if k == kr.KIND_WEED:
                return True
            if k == kr.KIND_PASTURE or k == kr.KIND_COOP:
                return t.get("animal") is not None
            return False
        target = _nearest(farm, _is_task, hx, hy)
        return _go_act(target, ["PASS"]) if target is not None else ["PASS"]
    # PASS: still, if there's an empty tile and seeds, plant wheat (override
    # the learned default when the farm is idle).
    if cls == de.ACTION_CLASSES["PASS"]:
        seeds = private.get("seeds", {})
        if int(seeds.get("WHEAT", 0) or 0) > 0:
            target = _nearest(farm, lambda t: t is None, hx, hy)
            if target is not None:
                return _go_act(target, ["PLANT", "WHEAT"])
        return ["PASS"]
    return ["PASS"]


def agent(obs, config=None):
    if _CLF is None:
        raise RuntimeError("dispatcher model not found; run train_dispatcher.py first")
    player = int(obs.get("player", 0) or 0)
    farm = obs["farms"][player]
    private = obs.get("private", {})
    prices = obs.get("market", {}).get("prices", {})
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)

    # Market orders (cronograma logic).
    market = _brain._market(obs, farm, private, day, hour)

    # Unit actions from the classifier.
    positions = [farm["farmer"]] + list(farm.get("hands", []))
    actions = []
    for hi, pos in enumerate(positions):
        feats = de.featurize_hand(obs, farm, private, prices, day, hour, hi, pos)
        cls = int(_CLF.predict([feats])[0])
        actions.append(_execute(cls, obs, farm, private, day, hour, hi, pos))

    farmer = actions[0] if actions else ["PASS"]
    hands = actions[1:] if len(actions) > 1 else []
    return kr.build_action(farmer, hands, market)


if __name__ == "__main__":
    for s in (1, 2):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "starter"])
        print(f"seed {s} vs starter:", env.steps[-1][0]["reward"])
