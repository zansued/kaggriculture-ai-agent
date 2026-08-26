"""wheat_base_v2 — gerador de fita wheat-heavy inspirado na coreografia do Moon.

Lições aplicadas (do Moon e das refutações):
  1. HANDS escalam: 5 no d0 -> 10-12 no d8+. Rega precisa de mão de obra.
  2. WATER é a tarefa dominante (prioridade ALTA, todas as plantas diariamente).
  3. Layout compacto (pastagens perto do shed) para minimizar viagem.
  4. Replantio contínuo de wheat após cada colheita (rotação).
  5. Poucos animais (2 COW) no início para reduzir complexidade de coordenação.

Objetivo do v2: sobreviver (sem WEED) e escalar para 100 tiles. Se coordena,
gera a fita via build_wheat_base e itera a economia.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASTURES = [(0, 0), (1, 0)]          # 2 pastagens (2 COW)
SHED = (4, 4)

PARAMS = {
    "n_cow": 2,
    "hands_target": 8,
    "wheat_target": 40,              # tiles de wheat (NW+NE+SW)
    "buy_land": True,                # NE d1, SW d5
    "wheat_reserve": 25,
    "sell_wheat_from": 9,
}


class WheatBaseV2:
    def __init__(self):
        self.op_state = {}

    def _state(self, seat):
        return self.op_state.setdefault(seat, {
            "bought": {"COW": 0},
            "land": {"NE": False, "SW": False, "SE": False},
        })

    # ------------------------------------------------------------- helpers
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

    def _empty(self, farm, quadrant=None):
        out = []
        for y, row in enumerate(farm.get("tiles", []) or []):
            for x, t in enumerate(row):
                if t is None:
                    q = "NW" if x < 5 and y < 5 else "NE" if x >= 5 and y < 5 else "SW" if x < 5 and y >= 5 else "SE"
                    if quadrant is None or q == quadrant:
                        out.append((x, y))
        return out

    def _manhattan(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    # ------------------------------------------------------------ planning
    def _plan(self, obs, seat, day, step):
        farm = self._farm(obs, seat)
        private = obs.get("private", {}) or {}
        tiles = farm.get("tiles", []) or []
        st = self._state(seat)
        tasks = []
        shed = private.get("shed", {}) or {}
        seeds = private.get("seeds", {}) or {}
        invs = private.get("inventories") or [{}]

        # --- URGENTE: PICKUP->PLACE de animais (cadeia completa, PLACE primeiro) ---
        n_carry_cow = sum(1 for inv in invs if int((inv or {}).get("COW", 0) or 0) > 0)
        n_pasture_free = sum(1 for row in tiles for t in row if isinstance(t, dict) and t.get("kind") == "PASTURE" and not t.get("animal"))
        for y, row in enumerate(tiles):
            for x, t in enumerate(row):
                if isinstance(t, dict) and t.get("kind") == "PASTURE" and not t.get("animal"):
                    tasks.append((-140, "PLACE", (x, y), None))
        if n_carry_cow < n_pasture_free and int(shed.get("COW", 0) or 0) > 0:
            tasks.append((-130, "PICKUP", SHED, ("COW",)))

        # --- URGENTE: alimentar animais (foge em 2 dias) ---
        # PICKUP WHEAT do shed se algum animal não alimentado e alguém sem wheat
        unfed = [a for a in self._animals(farm) if not a[2].get("fed_today", False)]
        if unfed and int(shed.get("WHEAT", 0) or 0) > 0:
            has_wheat = any(int((inv or {}).get("WHEAT", 0) or 0) > 0 for inv in invs)
            if not has_wheat:
                tasks.append((-121, "PICKUP_WHEAT", SHED, None))
        for x, y, t in unfed:
            tasks.append((-120, "FEED", (x, y), None))

        # --- construir pastagens ---
        n_pasture = sum(1 for row in tiles for t in row if isinstance(t, dict) and t.get("kind") == "PASTURE")
        if n_pasture < len(PASTURES) and day < 3:
            for xy in PASTURES:
                x, y = xy
                if not (isinstance(tiles[y][x], dict) and tiles[y][x].get("kind") == "PASTURE"):
                    tasks.append((-115, "BUILD_PASTURE", xy, None))

        # --- WATER: TODA planta não regada (prioridade máx de sobrevivência) ---
        for x, y, t in self._plants(farm):
            if not t.get("watered_today", False):
                tasks.append((-110, "WATER", (x, y), None))

        # --- HARVEST plantas prontas ---
        for x, y, t in self._plants(farm):
            if int(t.get("yield_units", 0) or 0) > 0:
                tasks.append((-100, "HARVEST", (x, y), None))

        # --- PLANT wheat (replantio + expansão) ---
        n_wheat = sum(1 for _, _, t in self._plants(farm) if t.get("crop") == "WHEAT")
        if n_wheat < PARAMS["wheat_target"] and int(seeds.get("WHEAT", 0) or 0) > 0:
            qs = ["NW", "NE", "SW"]
            for q in qs:
                if q in (farm.get("unlocked_quadrants") or []):
                    empt = self._empty(farm, q)
                    if empt:
                        tasks.append((-95, "PLANT", empt[0], ("WHEAT",)))
                        break

        # --- DIG weeds ---
        for y, row in enumerate(tiles):
            for x, t in enumerate(row):
                if isinstance(t, dict) and t.get("kind") == "WEED":
                    tasks.append((-90, "DIG", (x, y), None))

        # --- COLLECT_FERTILIZER ---
        for x, y, t in self._animals(farm):
            if t.get("fertilizer_available", False):
                tasks.append((-80, "COLLECT_FERT", (x, y), None))

        # --- FERTILIZE plantas não fertilizadas (se houver fert) ---
        fert = int(shed.get("FERTILIZER", 0) or 0) + sum(
            int((inv or {}).get("FERTILIZER", 0) or 0) for inv in invs)
        if fert > 2:
            for x, y, t in self._plants(farm):
                if int(t.get("fertilized_until_day", -1) or -1) < day:
                    tasks.append((-70, "FERTILIZE", (x, y), None))

        # --- HARVEST animais com produto ---
        for x, y, t in self._animals(farm):
            if int(t.get("yield_units", 0) or 0) > 0:
                tasks.append((-60, "HARVEST", (x, y), None))

        # --- CARE animais ---
        for x, y, t in self._animals(farm):
            if not t.get("cared_today", False):
                tasks.append((-40, "CARE", (x, y), None))

        tasks.sort(key=lambda t: t[0])
        return tasks

    # -------------------------------------------------------------- action
    def decide(self, obs, config=None):
        seat = int(obs.get("player", 0) or 0) or int(obs.get("index", 0) or 0)
        step = int(obs.get("step", 0) or 0)
        day = int(obs.get("day", 0) or 0)
        # RESET de estado a cada novo jogo (step 0)
        if step == 0:
            self.op_state[seat] = {
                "bought": {"COW": 0},
                "land": {"NE": False, "SW": False, "SE": False},
            }
        farm = self._farm(obs, seat)
        private = obs.get("private", {}) or {}
        farmer_pos = tuple(farm.get("farmer", [4, 4]))
        hands_pos = [tuple(h) for h in (farm.get("hands") or [])]
        invs = private.get("inventories") or [{}]

        tasks = self._plan(obs, seat, day, step)
        units = [(0, farmer_pos)] + [(i + 1, hands_pos[i]) for i in range(len(hands_pos))]
        cmds = {0: ["PASS"]}
        for i in range(len(hands_pos)):
            cmds[i + 1] = ["PASS"]
        assigned = set()

        for _, kind, target, args in tasks:
            best = None
            best_d = 999
            for idx, pos in units:
                if idx in assigned:
                    continue
                if kind == "PICKUP" and any(int((invs[idx] or {}).get(a, 0) or 0) > 0 for a in ("COW", "SHEEP")):
                    continue
                if kind == "PICKUP_WHEAT" and int((invs[idx] or {}).get("WHEAT", 0) or 0) > 0:
                    continue
                if kind == "PLACE" and not any(int((invs[idx] or {}).get(a, 0) or 0) > 0 for a in ("COW", "SHEEP")):
                    continue
                if kind == "FEED" and int((invs[idx] or {}).get("WHEAT", 0) or 0) <= 0:
                    continue
                d = self._manhattan(pos, target)
                if d < best_d:
                    best_d = d
                    best = (idx, pos)
            if best is None:
                continue
            idx, pos = best
            assigned.add(idx)
            if kind == "PLACE" and pos == target:
                inv = invs[idx] or {}
                animal = next((a for a in ("COW", "SHEEP") if int(inv.get(a, 0) or 0) > 0), None)
                cmd = ["PLACE", animal] if animal else None
            else:
                cmd = self._unit_cmd(kind, target, args, pos)
            if cmd:
                cmds[idx] = cmd

        return {
            "farmer": cmds[0],
            "hands": [cmds[i + 1] for i in range(len(hands_pos))],
            "market": self._market(obs, seat, day, step),
        }

    def _unit_cmd(self, kind, target, args, pos):
        if pos != target:
            dx, dy = target[0] - pos[0], target[1] - pos[1]
            return ["EAST" if abs(dx) >= abs(dy) and dx > 0 else "WEST" if abs(dx) >= abs(dy) else "SOUTH" if dy > 0 else "NORTH"]
        if kind == "FEED":
            return ["FEED"]
        if kind == "WATER":
            return ["WATER"]
        if kind == "HARVEST":
            return ["HARVEST"]
        if kind == "DIG":
            return ["DIG"]
        if kind == "COLLECT_FERT":
            return ["COLLECT_FERTILIZER"]
        if kind == "FERTILIZE":
            return ["FERTILIZE"]
        if kind == "CARE":
            return ["CARE"]
        if kind == "BUILD_PASTURE":
            return ["BUILD_PASTURE"]
        if kind == "PICKUP":
            return ["PICKUP", args[0], 1]
        if kind == "PICKUP_WHEAT":
            return ["PICKUP", "WHEAT", 10]
        if kind == "PLANT":
            return ["PLANT", args[0]]
        return ["PASS"]

    # -------------------------------------------------------------- market
    def _market(self, obs, seat, day, step):
        farm = self._farm(obs, seat)
        private = obs.get("private", {}) or {}
        st = self._state(seat)
        money = float(farm.get("money", 0) or 0)
        shed = private.get("shed", {}) or {}
        seeds = private.get("seeds", {}) or {}
        unlocked = farm.get("unlocked_quadrants") or []
        market = []

        n_hands = len(farm.get("hands") or [])
        n_wheat = sum(1 for _, _, t in self._plants(farm) if t.get("crop") == "WHEAT")
        n_cow = sum(1 for _, _, t in self._animals(farm) if t.get("animal") == "COW") + int(shed.get("COW", 0) or 0)

        # BUY_SEED WHEAT (mais no d0) — PRIORIDADE antes de HIRE
        if day <= 20 and n_wheat < PARAMS["wheat_target"] and int(seeds.get("WHEAT", 0) or 0) < 12 and money > 60 and len(market) < 10:
            q = 15 if day == 0 else 8
            market.append(["BUY_SEED", "WHEAT", min(q, PARAMS["wheat_target"] - n_wheat)])

        # BUY_PRODUCT WHEAT para FEED das COW (antes do wheat próprio maturar)
        w_shed = int(shed.get("WHEAT", 0) or 0)
        if day < 3 and (n_cow > 0 or st["bought"]["COW"] > 0) and w_shed < 12 and money > 250 and len(market) < 10:
            market.append(["BUY_PRODUCT", "WHEAT", min(12 - w_shed, int(money // 30))])

        # BUY_LAND NE d1, SW d5
        if PARAMS["buy_land"]:
            if not st["land"]["NE"] and day == 1 and money > 1200 and "NE" not in unlocked:
                market.append(["BUY_LAND"])
                st["land"]["NE"] = True
            elif not st["land"]["SW"] and day == 5 and money > 2500 and "NE" in unlocked and "SW" not in unlocked:
                market.append(["BUY_LAND"])
                st["land"]["SW"] = True

        # BUY_ANIMAL COW
        if day < 4 and n_cow < PARAMS["n_cow"] and money > 450 and len(market) < 10 and st["bought"]["COW"] < PARAMS["n_cow"]:
            market.append(["BUY_ANIMAL", "COW", 1])
            st["bought"]["COW"] += 1

        # HIRE (escalar hands) — o Moon contrata até d27; caixa limita
        if n_hands < PARAMS["hands_target"] and day < 27 and step % 24 < 4 and money > 150 and len(market) < 10:
            max_now = 5 if day == 0 else 10
            need = min(PARAMS["hands_target"] - n_hands, max_now, 10 - len(market))
            market += [["HIRE"]] * need

        # SELL
        self._sell(market, day, shed)

        return market[:10]

    def _sell(self, market, day, shed):
        # MILK: vender sempre que houver (produção d8+, pico d12-14)
        if 8 <= day <= 20 and int(shed.get("MILK", 0) or 0) > 0 and len(market) < 10:
            market.append(["SELL", "MILK", int(shed.get("MILK", 0) or 0)])
        if day >= 26 and int(shed.get("WOOL", 0) or 0) > 0 and len(market) < 10:
            market.append(["SELL", "WOOL", int(shed.get("WOOL", 0) or 0)])
        w = int(shed.get("WHEAT", 0) or 0)
        if day >= PARAMS["sell_wheat_from"] and w > PARAMS["wheat_reserve"] and len(market) < 10:
            market.append(["SELL", "WHEAT", w - PARAMS["wheat_reserve"]])


_BRAIN = WheatBaseV2()


def agent(obs, config=None):
    return _BRAIN.decide(obs, config)
