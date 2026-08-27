"""hybrid_expand — fita FarmBrain (NW) + coordenador dedicado para wheat no NE.

Estratégia: o FarmBrain coordena bem o NW (25 tiles, ~70k). A terra NE (x>=5,
y<5) é simples (wheat puro) — um mini-coordenador dedica HANDS EXTRAS para
plantar/regar/colher wheat lá, sem sobrecarregar a coordenação do FarmBrain.

Isso escala a produção para 2 quadrantes sem depender do greedy escalar.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# fita do FarmBrain (gerada previamente)
TAPE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "replays", "farmbrain_tape.json")
_TAPE = json.load(open(TAPE_PATH)) if os.path.exists(TAPE_PATH) else None

# tiles do NE para wheat (sem colisão com o shed)
NE_TILES = [(x, y) for x in range(5, 10) for y in range(0, 5)]
# ordem de plantio (perto do shed primeiro)
NE_TILES.sort(key=lambda t: abs(t[0] - 4) + abs(t[1] - 4))

PARAMS = {
    "extra_hands": 3,          # hands extras dedicados ao NE
    "ne_wheat_target": 18,     # tiles de wheat no NE
    "sell_wheat_from": 9,
    "wheat_reserve": 20,
}


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _move_toward(pos, target):
    if pos == target:
        return None
    dx, dy = target[0] - pos[0], target[1] - pos[1]
    if abs(dx) >= abs(dy):
        return "EAST" if dx > 0 else "WEST"
    return "SOUTH" if dy > 0 else "NORTH"


class HybridExpand:
    def __init__(self):
        self.op_state = {}

    def _state(self, seat):
        return self.op_state.setdefault(seat, {"land_ne": False})

    def decide(self, obs, config=None):
        seat = int(obs.get("player", 0) or 0) or int(obs.get("index", 0) or 0)
        step = int(obs.get("step", 0) or 0)
        day = int(obs.get("day", 0) or 0)
        st = self._state(seat)
        farm = (obs.get("farms") or [])[seat]
        private = obs.get("private", {}) or {}
        tiles = farm.get("tiles", []) or []

        # 1. ação base da fita do FarmBrain (para farmer + hands originais)
        base_action = _TAPE[min(step, 719)] if _TAPE else {"farmer": ["PASS"], "hands": [], "market": []}
        base_action = {k: list(v) if isinstance(v, list) else v for k, v in base_action.items()}
        base_hands = list(base_action.get("hands") or [])
        base_market = list(base_action.get("market") or [])

        # 2. hands extras (índices além dos da fita)
        n_base_hands = len(base_hands)
        hands_pos = [list(h) for h in (farm.get("hands") or [])]
        extra_pos = hands_pos[n_base_hands:] if len(hands_pos) > n_base_hands else []
        invs = private.get("inventories") or [{}]

        extra_cmds = []
        n_wheat_ne = sum(1 for row in tiles for t in row if isinstance(t, dict) and t.get("kind") == "PLANT"
                         and t.get("crop") == "WHEAT" and t.get("x", None) is None
                         and any(t == (row.index(t), y) for y, r2 in enumerate(tiles) for row2 in [r2]))  # placeholder
        # conta wheat no NE corretamente
        n_wheat_ne = 0
        ne_set = set(NE_TILES)
        for y, row in enumerate(tiles):
            for x, t in enumerate(row):
                if (x, y) in ne_set and isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == "WHEAT":
                    n_wheat_ne += 1

        for i in range(PARAMS["extra_hands"]):
            if i >= len(extra_pos):
                extra_cmds.append(["PASS"])
                continue
            pos = tuple(extra_pos[i])
            x, y = pos
            # se no NE, planta/regar/colher; senão anda para o NE
            in_ne = x >= 5 and y < 5
            tile = tiles[y][x] if (0 <= y < len(tiles) and 0 <= x < len(tiles[y])) else None

            # colher wheat maduro no NE
            if in_ne and isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("yield_units", 0) > 0:
                extra_cmds.append(["HARVEST"])
                continue
            # regar wheat não regado no NE
            if in_ne and isinstance(tile, dict) and tile.get("kind") == "PLANT" and not tile.get("watered_today", False):
                extra_cmds.append(["WATER"])
                continue
            # plantar wheat em tile vazio do NE (se tiver semente)
            if in_ne and tile is None and n_wheat_ne < PARAMS["ne_wheat_target"] and int(private.get("seeds", {}).get("WHEAT", 0) or 0) > 0:
                extra_cmds.append(["PLANT", "WHEAT"])
                continue
            # andar para o tile NE mais próximo (vazio ou wheat)
            target = None
            best_d = 999
            for tx, ty in NE_TILES:
                t = tiles[ty][tx]
                if t is None or (isinstance(t, dict) and t.get("kind") == "PLANT"):
                    d = _manhattan(pos, (tx, ty))
                    if d < best_d:
                        best_d = d
                        target = (tx, ty)
            if target:
                m = _move_toward(pos, target)
                extra_cmds.append([m] if m else ["PASS"])
            else:
                extra_cmds.append(["PASS"])

        # 3. market: BUY_LAND NE + HIRE extras + BUY_SEED WHEAT
        market = list(base_market)
        unlocked = farm.get("unlocked_quadrants") or []
        money = float(farm.get("money", 0) or 0)

        if PARAMS["extra_hands"] > 0 and not st["land_ne"] and day == 0 and "NE" not in unlocked and money > 1200 and len(market) < 10:
            market.append(["BUY_LAND"])
            st["land_ne"] = True

        n_hands_total = len(hands_pos)
        if day < 3 and n_hands_total < n_base_hands + PARAMS["extra_hands"] and money > 200 and len(market) < 10:
            need = n_base_hands + PARAMS["extra_hands"] - n_hands_total
            market += [["HIRE"]] * min(need, 10 - len(market))

        # BUY_SEED WHEAT para o NE
        if day <= 15 and n_wheat_ne < PARAMS["ne_wheat_target"] and int(private.get("seeds", {}).get("WHEAT", 0) or 0) < 6 and money > 50 and len(market) < 10:
            market.append(["BUY_SEED", "WHEAT", min(6, PARAMS["ne_wheat_target"] - n_wheat_ne)])

        # SELL wheat excedente (NE)
        shed_w = int(private.get("shed", {}).get("WHEAT", 0) or 0)
        if day >= PARAMS["sell_wheat_from"] and shed_w > PARAMS["wheat_reserve"] and len(market) < 10:
            market.append(["SELL", "WHEAT", shed_w - PARAMS["wheat_reserve"]])

        return {
            "farmer": base_action.get("farmer", ["PASS"]),
            "hands": base_hands + extra_cmds,
            "market": market[:10],
        }


_BRAIN = HybridExpand()


def agent(obs, config=None):
    return _BRAIN.decide(obs, config)
