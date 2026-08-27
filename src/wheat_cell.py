"""wheat_cell — coordenador adaptativo de ROTAÇÃO RÁPIDA de wheat (Fase 3).

Baseado no insight econômico: a vantagem do CropDusta é a PRODUTIVIDADE POR
TILE do wheat (rotação ~2.5x + fertilização), não a escala. Este coordenador
implementa o ciclo por tile:

    PLANT WHEAT -> WATER (d1-d3) -> FERTILIZE (se houver fert) -> HARVEST (d3+)
    -> replant IMEDIATO -> ...

Estratégia:
  - 2 quadrantes (NW + NE), wheat em ~40 tiles (rotação contínua).
  - FERTILIZER COMPRADO (BUY_PRODUCT) quando barato — sem depender de animais.
  - Strawberry/melon limitados (não crashar preço).
  - Venda contínua de wheat excedente (reserva de feed não necessária sem animais).

Este é um coordenador por ESTADO (não fita) — decide por observação.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PARAMS = {
    "quadrants": 2,             # NW + NE
    "wheat_target": 40,         # tiles de wheat simultâneos
    "hands_target": 8,
    "fert_buy_price": 40,       # comprar FERTILIZER se preço <= este
    "sell_wheat_from": 4,
    "wheat_reserve": 10,
}


class WheatCell:
    def __init__(self):
        self.op_state = {}

    def _state(self, seat):
        return self.op_state.setdefault(seat, {"land": set(), "bought_seed": 0})

    def _farm(self, obs, seat):
        farms = obs.get("farms", []) or []
        return farms[seat] if seat < len(farms) else {}

    def _plants(self, farm):
        out = []
        for y, row in enumerate(farm.get("tiles", []) or []):
            for x, t in enumerate(row):
                if isinstance(t, dict) and t.get("kind") == "PLANT":
                    out.append((x, y, t))
        return out

    def _manhattan(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _move(self, pos, target):
        dx, dy = target[0] - pos[0], target[1] - pos[1]
        if abs(dx) >= abs(dy):
            return "EAST" if dx > 0 else "WEST"
        return "SOUTH" if dy > 0 else "NORTH"

    def _decide_tile(self, tile, day, seeds, has_fert):
        """Decide a ação para um tile de wheat (ou vazio)."""
        if tile is None:
            if seeds > 0:
                return ("PLANT", "WHEAT")
            return None
        if not isinstance(tile, dict):
            return None
        if tile.get("kind") != "PLANT":
            return None
        crop = tile.get("crop")
        if crop != "WHEAT":
            # não-wheat: regar se não regado (sobrevivência), senão nada
            if not tile.get("watered_today", False):
                return ("WATER",)
            return None
        # wheat
        age = day - int(tile.get("planted_day", day))
        yield_u = int(tile.get("yield_units", 0) or 0)
        # colher só se maduro (age >= first_yield_day=2) E regado
        if age >= 2 and yield_u > 0 and tile.get("watered_today", False):
            return ("HARVEST",)          # rotaciona
        if not tile.get("watered_today", False):
            return ("WATER",)            # sobrevivência primeiro
        if age >= 2 and yield_u > 0:
            return ("HARVEST",)
        if has_fert and int(tile.get("fertilized_until_day", -1) or -1) < day:
            return ("FERTILIZE",)
        return None

    def decide(self, obs, config=None):
        seat = int(obs.get("player", 0) or 0) or int(obs.get("index", 0) or 0)
        step = int(obs.get("step", 0) or 0)
        day = int(obs.get("day", 0) or 0)
        if step == 0:
            self.op_state[seat] = {"land": set(), "bought_seed": 0}
        st = self._state(seat)
        farm = self._farm(obs, seat)
        private = obs.get("private", {}) or {}
        tiles = farm.get("tiles", []) or []
        seeds = int((private.get("seeds") or {}).get("WHEAT", 0) or 0)
        shed = private.get("shed", {}) or {}
        money = float(farm.get("money", 0) or 0)
        unlocked = set(farm.get("unlocked_quadrants") or [])

        # 1. definir alvos (tiles de wheat + vazios nos quadrantes liberados)
        n_wheat = sum(1 for _, _, t in self._plants(farm) if t.get("crop") == "WHEAT")
        has_fert = int(shed.get("FERTILIZER", 0) or 0) > 0
        target_tiles = []
        for y, row in enumerate(tiles):
            for x, t in enumerate(row):
                q = "NW" if x < 5 and y < 5 else "NE" if x >= 5 and y < 5 else "SW" if x < 5 and y >= 5 else "SE"
                if q not in unlocked:
                    continue
                act = self._decide_tile(t, day, seeds, has_fert)
                if act is None:
                    continue
                if act[0] == "PLANT" and n_wheat >= PARAMS["wheat_target"]:
                    continue
                if act[0] == "PLANT":
                    n_wheat += 1  # reserva o tile para wheat
                target_tiles.append((x, y, act))
        # ordena por prioridade: WATER/HARVEST (sobrevivência) > FERTILIZE > PLANT
        prio = {"HARVEST": 0, "WATER": 1, "FERTILIZE": 2, "PLANT": 3}
        target_tiles.sort(key=lambda tt: prio.get(tt[2][0], 9))

        # 2. atribuir units (farmer + hands) aos alvos
        farmer_pos = tuple(farm.get("farmer", [4, 4]))
        hands_pos = [tuple(h) for h in (farm.get("hands") or [])]
        units = [(0, farmer_pos)] + [(i + 1, hands_pos[i]) for i in range(len(hands_pos))]
        cmds = {0: ["PASS"]}
        for i in range(len(hands_pos)):
            cmds[i + 1] = ["PASS"]
        assigned = set()
        for x, y, act in target_tiles:
            best = None
            best_d = 999
            for idx, pos in units:
                if idx in assigned:
                    continue
                d = self._manhattan(pos, (x, y))
                if d < best_d:
                    best_d = d
                    best = (idx, pos)
            if best is None:
                continue
            idx, pos = best
            assigned.add(idx)
            if pos == (x, y):
                if act[0] == "PLANT":
                    cmds[idx] = ["PLANT", act[1]]
                elif act[0] == "FERTILIZE":
                    cmds[idx] = ["FERTILIZE"]
                elif act[0] == "HARVEST":
                    cmds[idx] = ["HARVEST"]
                else:
                    cmds[idx] = ["WATER"]
            else:
                m = self._move(pos, (x, y))
                cmds[idx] = [m] if m else ["PASS"]

        # 3. market (BUY_SEED PRIMEIRO — sementes são críticas)
        market = []
        n_hands = len(farm.get("hands") or [])

        # BUY_SEED WHEAT (prioridade máxima)
        if n_wheat < PARAMS["wheat_target"] and seeds < 12 and money > 60 and len(market) < 10:
            q = 12 if day == 0 else 8
            market.append(["BUY_SEED", "WHEAT", min(q, PARAMS["wheat_target"] - n_wheat)])

        # BUY_LAND NE d1
        if "NE" not in unlocked and "NE" not in st["land"] and day == 1 and money > 1200 and len(market) < 10:
            market.append(["BUY_LAND"])
            st["land"].add("NE")

        # HIRE
        if n_hands < PARAMS["hands_target"] and day < 14 and step % 24 < 4 and money > 150 and len(market) < 10:
            need = min(PARAMS["hands_target"] - n_hands, 10 - len(market))
            market += [["HIRE"]] * need

        # BUY_PRODUCT FERTILIZER (quando barato)
        fp = (obs.get("market") or {}).get("prices", {}).get("FERTILIZER", 100) or 100
        if fp <= PARAMS["fert_buy_price"] and money > 200 and len(market) < 10:
            market.append(["BUY_PRODUCT", "FERTILIZER", min(10, int(money // max(1, fp)))])

        # SELL WHEAT excedente
        w = int(shed.get("WHEAT", 0) or 0)
        if day >= PARAMS["sell_wheat_from"] and w > PARAMS["wheat_reserve"] and len(market) < 10:
            market.append(["SELL", "WHEAT", w - PARAMS["wheat_reserve"]])

        return {
            "farmer": cmds[0],
            "hands": [cmds[i + 1] for i in range(len(hands_pos))],
            "market": market[:10],
        }


_BRAIN = WheatCell()


def agent(obs, config=None):
    return _BRAIN.decide(obs, config)
