"""Dispatcher v2 — classifier-driven units with a hard crop-lifecycle layer.

v1's bug: the classifier is out-of-distribution on an empty farm (it never
saw <12-plant states), so it PLANTs 1195 times, never HARVESTs, money dies by
day 8, reward 0.0.

v2 fixes:
  1. Crop lifecycle is a HARD override layer (highest priority):
       mature plant  -> HARVEST
       unwatered     -> WATER
       weed          -> DIG
       empty+seeds+cap -> PLANT (best crop per FarmBrain._preferred_crops)
  2. Units COORDINATE targets via an `assigned` set (no more 9 units piling
     onto the same empty tile).
  3. Market = FarmBrain._plan_sells (price-aware, sells every turn) + spread
     hand-hiring + seed-buffer buying (no more daily 5-melon+8-wheat burn).

The classifier still drives the non-crop texture (MOVE targets, PASS, animal
chores when animals exist).

Usage: python dispatcher_v2.py [--seed N]  (demo vs starter)
       h2h via h2h_bench.py --a dispatcher_v2
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

from kaggriculture_real import (  # noqa: E402
    CROPS, ANIMALS, SEASON_DAYS, MAX_MARKET_ORDERS,
    PASS, NORTH, SOUTH, EAST, WEST, MOVES,
    WATER, HARVEST, DIG, PLANT, BUILD_PASTURE,
    FEED, CARE, COLLECT_FERTILIZER, PICKUP, PLACE,
    BUY_SEED, BUY_ANIMAL, BUY_PRODUCT, SELL, HIRE, BUY_LAND,
    KIND_PLANT, KIND_WEED, KIND_PASTURE, KIND_COOP,
    build_action, my_farm, farmer_xy, _shed_tile, _fib, SHED_TILES,
)

_MODEL_PATH = os.path.join(_HERE, "data", "kawasagi", "dispatcher_model.joblib")
_CLF = joblib.load(_MODEL_PATH) if os.path.exists(_MODEL_PATH) else None

# Battle-tested selling + seed scoring from the reactive FarmBrain. We use
# livestock=True ONLY to activate two things: (a) _preferred_crops gates
# STRAWBERRY to day >= 4 (the top agent's schedule), (b) _plan_sells dribbles
# premium goods price-aware. animal_plan=[] means no animals are ever bought.
_fb = kr.FarmBrain(
    crops=["MELON", "WHEAT", "STRAWBERRY"],
    max_hands=8,
    animal_plan=[],
    seed_buffer=6,
    seed_buffers={"MELON": 8, "WHEAT": 8, "STRAWBERRY": 8},
    melon_plant_gate=240,
    premium_sell_per_turn=2,
    premium_sell_floor=100,
    livestock=True,
)


def _nearest(farm, pred, hx, hy, skip=None):
    """Nearest tile matching pred(tile). Skips LOCKED + `skip` tiles."""
    tiles = farm.get("tiles", [])
    best = None
    best_d = 10 ** 9
    skip = skip or set()
    for y in range(len(tiles)):
        for x in range(len(tiles[y])):
            if (x, y) in skip:
                continue
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
    return ["PASS"]


def _mature(tile, day):
    """True if a plant tile is ready to harvest (reactive's rule)."""
    if not (isinstance(tile, dict) and tile.get("kind") == KIND_PLANT):
        return False
    cd = CROPS.get(tile.get("crop"))
    if not cd:
        return False
    y = int(tile.get("yield_units", 0) or 0)
    if y <= 0:
        return False
    age = day - int(tile.get("planted_day", day))
    if cd["ongoing"]:
        return y >= cd["max_yield"]
    return age >= cd["max_yield_day"] or y >= cd["max_yield"]


def _count_plants(farm):
    tiles = farm.get("tiles", [])
    return sum(
        1 for row in tiles for t in row
        if isinstance(t, dict) and t.get("kind") == KIND_PLANT
    )


# LAND EXPERIMENT (NEGATIVE): enabling land + the 38/56 caps DROPS the reward
# (31.8k -> 13.7k/18.2k). The classifier's greedy coordinator thrashes across
# 75 tiles exactly like the reactive's — it can't maintain distant crops. Keep
# land OFF (best known config). Flip to True to re-test scaling.
_BUY_LAND = False


def _plant_cap(farm):
    """Production cap scales with unlocked quadrants when land is enabled.
    With land OFF we stay in NW (25 tiles): cap 20."""
    if not _BUY_LAND:
        return 20
    n_unlocked = len(farm.get("unlocked_quadrants", []))
    return 20 + 18 * (n_unlocked - 1)


def _market(obs, farm, private, day, hour):
    ops = []
    money = float(farm.get("money", 0.0))

    # 1) SELL the shed every turn (price-aware). Cash now beats sitting inventory.
    prices = obs.get("market", {}).get("prices", {})
    sell_ops, sell_proceeds = _fb._plan_sells(obs, farm, private, day, hour, prices, reserve_feed=False)
    ops.extend(sell_ops)
    money += sell_proceeds
    if len(ops) >= MAX_MARKET_ORDERS:
        return ops[:MAX_MARKET_ORDERS]

    # 2) LAND: buy NE (d7) then SW (d11) like the top agent, staggered, keeping
    #    a cash buffer so seed/feed budget is never starved. OFF by default
    #    (measured negative: 31.8k -> 13.7k/18.2k).
    if _BUY_LAND:
        n_unlocked = len(farm.get("unlocked_quadrants", []))
        land_day = (7, 11)[n_unlocked - 1] if n_unlocked < 3 else 99
        if day >= land_day and n_unlocked < 3:
            next_cost = (1000, 2000, 4000)[n_unlocked - 1]
            if money >= next_cost + 400:
                ops.append([BUY_LAND])
                money -= next_cost
        if len(ops) >= MAX_MARKET_ORDERS:
            return ops[:MAX_MARKET_ORDERS]

    # 3) HIRE hands, spread 2/turn (fib cost), up to max_hands. Hands reset daily.
    max_hands = 8
    n_hands = len(farm.get("hands", []))
    if n_hands < max_hands:
        n_hired = int(farm.get("hires_today", 0))
        for _ in range(min(2, max_hands - n_hands)):
            cost = _fib(n_hired)
            if money < cost:
                break
            ops.append([HIRE])
            money -= cost
            n_hired += 1
    if len(ops) >= MAX_MARKET_ORDERS:
        return ops[:MAX_MARKET_ORDERS]

    # 4) SEEDS to buffer (FarmBrain logic): buy 1 seed/turn per preferred crop
    #    while below the buffer AND cash > $800 floor (never starve the harvest).
    seeds = private.get("seeds", {})
    preferred = _fb._preferred_crops(obs, farm, day)
    for crop in preferred:
        buffer = _fb.seed_buffers.get(crop, _fb.seed_buffer)
        have = int(seeds.get(crop, 0) or 0)
        if have < buffer and money >= CROPS[crop]["seed"] and money > 800:
            ops.append([BUY_SEED, crop, 1])
            money -= CROPS[crop]["seed"]
            if len(ops) >= MAX_MARKET_ORDERS:
                break
    return ops[:MAX_MARKET_ORDERS]


def _execute(cls, obs, farm, private, day, hour, hi, pos, assigned):
    tiles = farm.get("tiles", [])
    size = len(tiles)
    hx, hy = pos
    tile = tiles[hy][hx] if (0 <= hy < size and 0 <= hx < size) else None
    inv = (private.get("inventories") or [{}])[hi] if hi < len(private.get("inventories", [])) else {}
    shed = private.get("shed", {})
    seeds = private.get("seeds", {})

    is_plant = isinstance(tile, dict) and tile.get("kind") == KIND_PLANT
    is_anim = isinstance(tile, dict) and (tile.get("kind") == KIND_PASTURE or tile.get("kind") == KIND_COOP) and tile.get("animal")
    is_weed = isinstance(tile, dict) and tile.get("kind") == KIND_WEED
    is_empty = tile is None

    def _go_act(target, act):
        if target is None:
            return ["PASS"]
        # Claim this target so later units pick a different one (no pileups).
        assigned.add(target)
        if (hx, hy) == target:
            return act
        return _move(hx, hy, target[0], target[1], tiles)

    def _p(d):
        return isinstance(d, dict)

    # === HARD CROP LIFECYCLE (highest priority, saves the economy) ===
    # 1) HARVEST mature plant (before watering — a mature unwatered plant
    #    should be harvested, not watered).
    if is_plant and _mature(tile, day):
        return ["HARVEST"]
    # 2) WATER unwatered plant (protect the investment).
    if is_plant and not tile.get("watered_today", False):
        return ["WATER"]
    # 3) DIG weed.
    if is_weed:
        return ["DIG"]
    # 4) PLANT on an empty tile when under capacity (coordinated via assigned).
    n_plants = _count_plants(farm)
    cap = _plant_cap(farm)
    if is_empty and n_plants < cap:
        crop = None
        for c in _fb._preferred_crops(obs, farm, day):
            if int(seeds.get(c, 0) or 0) > 0:
                crop = c
                break
        if crop is not None:
            return ["PLANT", crop]
    # 5) If not at capacity and seeds exist, go to the nearest empty tile
    #    (spread units: skip already-assigned tiles).
    if n_plants < cap:
        crop = None
        for c in _fb._preferred_crops(obs, farm, day):
            if int(seeds.get(c, 0) or 0) > 0:
                crop = c
                break
        if crop is not None:
            tgt = _nearest(farm, lambda t: t is None, hx, hy, skip=assigned)
            if tgt is not None:
                if (hx, hy) == tgt:
                    return ["PLANT", crop]
                return _go_act(tgt, ["PLANT", crop])

    # === CLASSIFIER-DRIVEN actions (non-crop texture) ===
    # WATER (unwatered plant elsewhere)
    if cls == de.ACTION_CLASSES["WATER"]:
        return _go_act(_nearest(farm, lambda t: _p(t) and t.get("kind") == KIND_PLANT and not t.get("watered_today", False), hx, hy, skip=assigned), ["WATER"])
    # HARVEST (mature elsewhere)
    if cls == de.ACTION_CLASSES["HARVEST"]:
        if is_anim and int(tile.get("yield_units", 0) or 0) > 0:
            return ["HARVEST"]
        return _go_act(_nearest(farm, lambda t: _p(t) and (t.get("kind") == KIND_PLANT and _mature(t, day) or (t.get("kind") in (KIND_PASTURE, KIND_COOP) and int(t.get("yield_units", 0) or 0) > 0)), hx, hy, skip=assigned), ["HARVEST"])
    # DIG
    if cls == de.ACTION_CLASSES["DIG"]:
        return _go_act(_nearest(farm, lambda t: _p(t) and t.get("kind") == KIND_WEED, hx, hy, skip=assigned), ["DIG"])
    # FEED
    if cls == de.ACTION_CLASSES["FEED"]:
        if is_anim and not tile.get("fed_today", False):
            if inv.get("WHEAT", 0) > 0:
                return ["FEED"]
            return _go_act(kr._shed_tile(farm), ["PICKUP", "WHEAT", 1])
        return _go_act(_nearest(farm, lambda t: _p(t) and (t.get("kind") == KIND_PASTURE or t.get("kind") == KIND_COOP) and t.get("animal") and not t.get("fed_today", False), hx, hy, skip=assigned), ["FEED"])
    # CARE
    if cls == de.ACTION_CLASSES["CARE"]:
        if is_anim and not tile.get("cared_today", False):
            return ["CARE"]
        return _go_act(_nearest(farm, lambda t: _p(t) and (t.get("kind") == KIND_PASTURE or t.get("kind") == KIND_COOP) and t.get("animal") and not t.get("cared_today", False), hx, hy, skip=assigned), ["CARE"])
    # COLLECT_FERTILIZER
    if cls == de.ACTION_CLASSES["COLLECT_FERTILIZER"]:
        if is_anim and tile.get("fertilizer_available", False):
            return ["COLLECT_FERTILIZER"]
        return _go_act(_nearest(farm, lambda t: _p(t) and (t.get("kind") == KIND_PASTURE or t.get("kind") == KIND_COOP) and t.get("fertilizer_available", False), hx, hy, skip=assigned), ["COLLECT_FERTILIZER"])
    # FERTILIZE
    if cls == de.ACTION_CLASSES["FERTILIZE"]:
        if is_plant and tile.get("crop") == "STRAWBERRY":
            return ["FERTILIZE"]
        return _go_act(_nearest(farm, lambda t: _p(t) and t.get("kind") == KIND_PLANT and t.get("crop") == "STRAWBERRY", hx, hy, skip=assigned), ["FERTILIZE"])
    # PLANT_* (classifier wants to plant a specific crop at an empty tile)
    for crop, cls_id in [("WHEAT", 7), ("STRAWBERRY", 8), ("MELON", 9), ("CARROT", 10)]:
        if cls == de.ACTION_CLASSES["PLANT_" + crop]:
            tgt = _nearest(farm, lambda t: t is None, hx, hy, skip=assigned)
            if tgt is None:
                return ["PASS"]
            if (hx, hy) == tgt:
                return ["PLANT", crop]
            return _go_act(tgt, ["PLANT", crop])
    # PICKUP (restock wheat)
    if cls == de.ACTION_CLASSES["PICKUP"]:
        if int(shed.get("WHEAT", 0) or 0) <= 0:
            return ["PASS"]
        st = kr._shed_tile(farm)
        if (hx, hy) == st:
            return ["PICKUP", "WHEAT", 1]
        return _go_act(st, ["PICKUP", "WHEAT", 1])
    # PLACE
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
        return _go_act(_nearest(farm, lambda t: t is None, hx, hy, skip=assigned), ["BUILD_PASTURE"])
    # MOVE: toward the nearest task (unwatered/mature plant, weed, animal, or
    # empty tile to plant).
    if cls == de.ACTION_CLASSES["MOVE"]:
        def _is_task(t):
            if t is None:
                return True
            if not isinstance(t, dict):
                return False
            k = t.get("kind")
            if k == KIND_PLANT:
                return _mature(t, day) or not t.get("watered_today", False)
            if k == KIND_WEED:
                return True
            if k == KIND_PASTURE or k == KIND_COOP:
                return t.get("animal") is not None
            return False
        target = _nearest(farm, _is_task, hx, hy, skip=assigned)
        return _go_act(target, ["PASS"]) if target is not None else ["PASS"]
    # PASS: stand still (crop overrides already tried to use the unit).
    return ["PASS"]


def agent(obs, config=None):
    if _CLF is None:
        raise RuntimeError("dispatcher model not found")
    player = int(obs.get("player", 0) or 0)
    farm = obs["farms"][player]
    private = obs.get("private", {})
    prices = obs.get("market", {}).get("prices", {})
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)

    market = _market(obs, farm, private, day, hour)

    positions = [farm["farmer"]] + list(farm.get("hands", []))
    assigned = set()
    actions = []
    for hi, pos in enumerate(positions):
        feats = de.featurize_hand(obs, farm, private, prices, day, hour, hi, pos)
        cls = int(_CLF.predict([feats])[0])
        act = _execute(cls, obs, farm, private, day, hour, hi, pos, assigned)
        # claim a target tile for coordination (only for move-to targets)
        actions.append(act)
    farmer = actions[0] if actions else ["PASS"]
    hands = actions[1:] if len(actions) > 1 else []
    return build_action(farmer, hands, market)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    for s in (args.seed, args.seed + 1):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "starter"])
        print(f"seed {s} vs starter:", env.steps[-1][0]["reward"])
