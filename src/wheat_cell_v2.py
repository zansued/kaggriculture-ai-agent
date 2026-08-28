"""wheat_cell_v2 — rotação rápida de wheat + 2 COW (fert grátis + milk) + fertilização.

Fusão das lições:
  - wheat_cell: ciclo por tile PLANT->WATER->HARVEST(age>=2)->replant IMEDIATO.
  - wheat_base_v2: coordenação de animais (PICKUP->PLACE, FEED, COLLECT_FERT).
  - INSIGHT: fertilizar wheat só compensa com FERT GRÁTIS de animais (comprado
    sai caro: ~$100 por fert vs +$80 de yield).

Estratégia:
  - 2 COW d0-2 (produzem fert grátis + milk).
  - Wheat em 2 quadrantes (~40 tiles) com rotação rápida.
  - COLLECT_FERT das COW -> FERTILIZE nos wheat (yield 6 vs 4).
  - Vende wheat contínuo + milk no pico (d12-14).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASTURES = [(0, 0), (1, 0)]      # 2 pastagens (2 COW)
SHED = (4, 4)

PARAMS = {
    "n_cow": 2,
    "hands_target": 8,
    "wheat_target": 40,
    "sell_wheat_from": 4,
    "wheat_reserve": 10,
    "fert_buy_price": 50,        # fallback: comprar fert se barato (mas COW são a fonte)
}


class WheatCellV2:
    def __init__(self):
        self.op_state = {}

    def _state(self, seat):
        return self.op_state.setdefault(seat, {
            "land": set(), "bought": {"COW": 0}, "bought_seed": 0,
        })

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

    def _animals(self, farm):
        out = []
        for y, row in enumerate(farm.get("tiles", []) or []):
            for x, t in enumerate(row):
                if isinstance(t, dict) and "animal" in t:
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
        """Ação para tile de wheat/vazio. (rotação rápida)"""
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
            if not tile.get("watered_today", False):
                return ("WATER",)
            return None
        age = day - int(tile.get("planted_day", day))
        yield_u = int(tile.get("yield_units", 0) or 0)
        if age >= 2 and yield_u > 0 and tile.get("watered_today", False):
            return ("HARVEST",)
        if not tile.get("watered_today", False):
            return ("WATER",)
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
            self.op_state[seat] = {"land": set(), "bought": {"COW": 0}, "bought_seed": 0}
        st = self._state(seat)
        farm = self._farm(obs, seat)
        private = obs.get("private", {}) or {}
        tiles = farm.get("tiles", []) or []
        seeds = int((private.get("seeds") or {}).get("WHEAT", 0) or 0)
        shed = private.get("shed", {}) or {}
        money = float(farm.get("money", 0) or 0)
        unlocked = set(farm.get("unlocked_quadrants") or [])
        invs = private.get("inventories") or [{}]
        farmer_pos = tuple(farm.get("farmer", [4, 4]))
        hands_pos = [tuple(h) for h in (farm.get("hands") or [])]
        units = [(0, farmer_pos)] + [(i + 1, hands_pos[i]) for i in range(len(hands_pos))]
        cmds = {0: ["PASS"]}
        for i in range(len(hands_pos)):
            cmds[i + 1] = ["PASS"]
        assigned = set()

        # ============ TAREFAS (rank negativo = maior prioridade) ============
        tasks = []

        # (1) FEED animais não alimentados (foge em 2 dias)
        unfed = [a for a in self._animals(farm) if not a[2].get("fed_today", False)]
        if unfed and int(shed.get("WHEAT", 0) or 0) > 0:
            has_wheat = any(int((inv or {}).get("WHEAT", 0) or 0) > 0 for inv in invs)
            if not has_wheat:
                tasks.append((-130, "PICKUP_WHEAT", SHED, None))
        for x, y, t in unfed:
            tasks.append((-120, "FEED", (x, y), None))

        # (2) PICKUP->PLACE de COW (cadeia)
        n_carry = sum(1 for inv in invs if int((inv or {}).get("COW", 0) or 0) > 0)
        n_pasture_free = sum(1 for row in tiles for t in row if isinstance(t, dict) and t.get("kind") == "PASTURE" and not t.get("animal"))
        for y, row in enumerate(tiles):
            for x, t in enumerate(row):
                if isinstance(t, dict) and t.get("kind") == "PASTURE" and not t.get("animal"):
                    tasks.append((-115, "PLACE", (x, y), None))
        if n_carry < n_pasture_free and int(shed.get("COW", 0) or 0) > 0:
            tasks.append((-114, "PICKUP", SHED, ("COW",)))

        # (3) construir pastagens
        n_pasture = sum(1 for row in tiles for t in row if isinstance(t, dict) and t.get("kind") == "PASTURE")
        if n_pasture < len(PASTURES) and day < 3:
            for xy in PASTURES:
                x, y = xy
                if not (isinstance(tiles[y][x], dict) and tiles[y][x].get("kind") == "PASTURE"):
                    tasks.append((-113, "BUILD_PASTURE", xy, None))

        # (4) COLLECT_FERTILIZER disponível
        for x, y, t in self._animals(farm):
            if t.get("fertilizer_available", False):
                tasks.append((-100, "COLLECT_FERT", (x, y), None))

        # (5) HARVEST animais com produto (milk)
        for x, y, t in self._animals(farm):
            if int(t.get("yield_units", 0) or 0) > 0:
                tasks.append((-90, "HARVEST_AN", (x, y), None))

        # (6) CARE animais
        for x, y, t in self._animals(farm):
            if not t.get("cared_today", False):
                tasks.append((-85, "CARE", (x, y), None))

        # ============ ALVOS DE CROPS (rotação rápida) ============
        n_wheat = sum(1 for _, _, t in self._plants(farm) if t.get("crop") == "WHEAT")
        has_fert = int(shed.get("FERTILIZER", 0) or 0) > 0 or any(int((inv or {}).get("FERTILIZER", 0) or 0) > 0 for inv in invs)
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
                    n_wheat += 1
                tasks.append((-50, act[0], (x, y), act[1:] or None))

        # PICKUP_FERT: se há fert no shed e ninguém carrega, um unit busca
        n_carry_fert = sum(1 for inv in invs if int((inv or {}).get("FERTILIZER", 0) or 0) > 0)
        if int(shed.get("FERTILIZER", 0) or 0) > 0 and n_carry_fert == 0 and any(t[1] == "FERTILIZE" for t in tasks):
            tasks.append((-45, "PICKUP_FERT", SHED, None))

        # ordena por prioridade (rank menor primeiro)
        tasks.sort(key=lambda t: t[0])

        # ============ ATRIBUIÇÃO ============
        for rank, kind, target, args in tasks:
            if kind == "PLANT":
                # já reservado; comando abaixo
                pass
            best = None
            best_d = 999
            for idx, pos in units:
                if idx in assigned:
                    continue
                if kind == "PLACE" and not any(int((invs[idx] or {}).get(a, 0) or 0) > 0 for a in ("COW", "SHEEP")):
                    continue
                if kind == "PICKUP" and any(int((invs[idx] or {}).get(a, 0) or 0) > 0 for a in ("COW", "SHEEP")):
                    continue
                if kind == "PICKUP_WHEAT" and int((invs[idx] or {}).get("WHEAT", 0) or 0) > 0:
                    continue
                if kind == "FEED" and int((invs[idx] or {}).get("WHEAT", 0) or 0) <= 0:
                    continue
                if kind == "FERTILIZE" and int((invs[idx] or {}).get("FERTILIZER", 0) or 0) <= 0:
                    continue
                if kind == "PICKUP_FERT" and int((invs[idx] or {}).get("FERTILIZER", 0) or 0) > 0:
                    continue
                d = self._manhattan(pos, target)
                if d < best_d:
                    best_d = d
                    best = (idx, pos)
            if best is None:
                continue
            idx, pos = best
            assigned.add(idx)
            if pos == target:
                if kind == "PLANT":
                    cmds[idx] = ["PLANT", args[0]]
                elif kind == "FERTILIZE":
                    cmds[idx] = ["FERTILIZE"]
                elif kind == "PICKUP_FERT":
                    cmds[idx] = ["PICKUP", "FERTILIZER", 5]
                elif kind == "PICKUP":
                    cmds[idx] = ["PICKUP", args[0], 1]
                elif kind == "PICKUP_WHEAT":
                    cmds[idx] = ["PICKUP", "WHEAT", 10]
                elif kind == "FEED":
                    cmds[idx] = ["FEED"]
                elif kind == "COLLECT_FERT":
                    cmds[idx] = ["COLLECT_FERTILIZER"]
                elif kind == "HARVEST_AN":
                    cmds[idx] = ["HARVEST"]
                elif kind == "CARE":
                    cmds[idx] = ["CARE"]
                elif kind == "BUILD_PASTURE":
                    cmds[idx] = ["BUILD_PASTURE"]
                elif kind == "PLACE":
                    animal = next((a for a in ("COW", "SHEEP") if int((invs[idx] or {}).get(a, 0) or 0) > 0), None)
                    cmds[idx] = ["PLACE", animal] if animal else ["PASS"]
                else:
                    cmds[idx] = ["WATER"]
            else:
                m = self._move(pos, target)
                cmds[idx] = [m] if m else ["PASS"]

        # ============ MARKET ============
        market = []
        n_hands = len(farm.get("hands") or [])

        # BUY_SEED WHEAT (prioridade)
        if n_wheat < PARAMS["wheat_target"] and seeds < 12 and money > 60 and len(market) < 10:
            q = 12 if day == 0 else 8
            market.append(["BUY_SEED", "WHEAT", min(q, PARAMS["wheat_target"] - n_wheat)])

        # BUY_LAND NE d1
        if "NE" not in unlocked and "NE" not in st["land"] and day == 1 and money > 1200 and len(market) < 10:
            market.append(["BUY_LAND"])
            st["land"].add("NE")

        # BUY_ANIMAL COW (d0-d3, 1/dia)
        n_cow = sum(1 for _, _, t in self._animals(farm) if t.get("animal") == "COW") + int(shed.get("COW", 0) or 0)
        if day < 4 and n_cow < PARAMS["n_cow"] and money > 450 and len(market) < 10 and st["bought"]["COW"] < PARAMS["n_cow"]:
            market.append(["BUY_ANIMAL", "COW", 1])
            st["bought"]["COW"] += 1

        # BUY_PRODUCT WHEAT para FEED das COW (antes do wheat próprio)
        if day < 5 and n_cow > 0 and int(shed.get("WHEAT", 0) or 0) < 15 and money > 200 and len(market) < 10:
            market.append(["BUY_PRODUCT", "WHEAT", min(15 - int(shed.get("WHEAT", 0) or 0), int(money // 30))])

        # HIRE
        if n_hands < PARAMS["hands_target"] and day < 14 and step % 24 < 4 and money > 150 and len(market) < 10:
            need = min(PARAMS["hands_target"] - n_hands, 10 - len(market))
            market += [["HIRE"]] * need

        # SELL WHEAT excedente + MILK (pico d12-14)
        if 12 <= day <= 14 and int(shed.get("MILK", 0) or 0) > 0 and len(market) < 10:
            market.append(["SELL", "MILK", int(shed.get("MILK", 0) or 0)])
        w = int(shed.get("WHEAT", 0) or 0)
        if day >= PARAMS["sell_wheat_from"] and w > PARAMS["wheat_reserve"] and len(market) < 10:
            market.append(["SELL", "WHEAT", w - PARAMS["wheat_reserve"]])

        return {
            "farmer": cmds[0],
            "hands": [cmds[i + 1] for i in range(len(hands_pos))],
            "market": market[:10],
        }


_BRAIN = WheatCellV2()


def agent(obs, config=None):
    return _BRAIN.decide(obs, config)
