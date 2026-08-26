"""wheat_base_v1 — agente determinístico wheat-heavy com coordenação por papel.

Correções vs v0 (que não jogava):
  1. Cadeia PICKUP->PLACE com estado por unit (animais saem do shed p/ pastagem).
  2. Rega diária de TODAS as plantas (sobrevivência, não só na janela).
  3. Orçamento controlado (HIRE/LAND/ANIMAIS limitados por dia e por caixa).
  4. Layout fixo (pastagens + melon + wheat) para reduzir decisão em tempo real.

Serve de GERADOR de fita: o build_wheat_base.py roda este agente num seed e
grava as ações (a fita). A fita embutida no bundle final reproduz a economia.

Este agente também é jogável diretamente (mas lento); o objetivo é gerar a fita.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Layout fixo da fazenda (coordenadas dentro do quadrante NW 5x5)
PASTURES = [(0, 0), (1, 0), (0, 1), (1, 1)]          # 4 pastagens (COW/SHEEP)
MELON_TILES = [(3, 0), (4, 0), (2, 1), (3, 1), (4, 1), (2, 2), (3, 2), (4, 2)]
# O resto do NW vira wheat. NE é comprado e também vira wheat.

ANIMALS = {"COW": 2, "SHEEP": 2}
CROP_TIMING = {"WHEAT": (2, 4), "CARROT": (2, 3), "MELON": (10, 12),
               "TOMATO": (8, 8), "STRAWBERRY": (10, 10)}

PARAMS = {
    "n_cow": 2, "n_sheep": 2,
    "wheat_target": 22,          # tiles de wheat (NW+NE)
    "melon_target": 4,
    "hands_target": 6,
    "buy_land": True,            # compra NE no d1
    "wheat_reserve": 25,
    "sell_wheat_from": 9,
}


class WheatBaseV1:
    def __init__(self):
        self.op_state = {}

    def _state(self, seat):
        return self.op_state.setdefault(seat, {
            "role": {},          # unit idx -> estado (ex: {"carrying": "COW"})
            "bought": {"COW": 0, "SHEEP": 0},
            "land": False,
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

    def _shed_tile(self, farm):
        return (4, 4)  # shed access (o farmer nasce aqui)

    # ------------------------------------------------------------ planning
    def _plan(self, obs, seat, day, step):
        """Gera lista de tarefas (rank, tipo, alvo, args)."""
        farm = self._farm(obs, seat)
        private = obs.get("private", {}) or {}
        tiles = farm.get("tiles", []) or []
        st = self._state(seat)
        tasks = []
        shed = private.get("shed", {}) or {}

        # (1) construir pastagens se faltar
        n_pasture = sum(1 for row in tiles for t in row if isinstance(t, dict) and t.get("kind") == "PASTURE")
        if n_pasture < len(PASTURES) and day < 4:
            for xy in PASTURES:
                x, y = xy
                if not (isinstance(tiles[y][x], dict) and tiles[y][x].get("kind") == "PASTURE"):
                    tasks.append((-110, "BUILD_PASTURE", xy, None))

        # (2) PICKUP animais do shed (units SEM animal, perto do shed)
        for animal in ("COW", "SHEEP"):
            if int(shed.get(animal, 0) or 0) > 0:
                tasks.append((-100, "PICKUP", self._shed_tile(farm), (animal,)))

        # (3) PLACE animais: para cada pastagem vazia, um unit QUE CARREGA o animal
        carrying = {}
        invs = private.get("inventories") or [{}]
        for i, inv in enumerate(invs):
            for a in ("COW", "SHEEP"):
                if int((inv or {}).get(a, 0) or 0) > 0:
                    carrying[i] = a
        for y, row in enumerate(tiles):
            for x, t in enumerate(row):
                if isinstance(t, dict) and t.get("kind") == "PASTURE" and not t.get("animal"):
                    tasks.append((-95, "PLACE", (x, y), None))

        # (4) FEED animais não alimentados (unit com wheat)
        for x, y, t in self._animals(farm):
            if not t.get("fed_today", False):
                tasks.append((-90, "FEED", (x, y), None))

        # (5) COLLECT_FERTILIZER
        for x, y, t in self._animals(farm):
            if t.get("fertilizer_available", False):
                tasks.append((-85, "COLLECT_FERT", (x, y), None))

        # (6) HARVEST plantas prontas
        for x, y, t in self._plants(farm):
            if int(t.get("yield_units", 0) or 0) > 0:
                tasks.append((-80, "HARVEST", (x, y), None))

        # (7) HARVEST animais com produto
        for x, y, t in self._animals(farm):
            if int(t.get("yield_units", 0) or 0) > 0:
                tasks.append((-75, "HARVEST", (x, y), None))

        # (8) WATER toda planta não regada (sobrevivência)
        for x, y, t in self._plants(farm):
            if not t.get("watered_today", False):
                tasks.append((-70, "WATER", (x, y), None))

        # (9) FERTILIZE plantas não fertilizadas (se houver fert)
        fert = int(shed.get("FERTILIZER", 0) or 0) + sum(
            int((inv or {}).get("FERTILIZER", 0) or 0) for inv in invs)
        if fert > 0:
            for x, y, t in self._plants(farm):
                if int(t.get("fertilized_until_day", -1) or -1) < day:
                    tasks.append((-60, "FERTILIZE", (x, y), None))

        # (10) PLANT wheat/melon
        seeds = private.get("seeds", {}) or {}
        n_wheat = sum(1 for _, _, t in self._plants(farm) if t.get("crop") == "WHEAT")
        n_melon = sum(1 for _, _, t in self._plants(farm) if t.get("crop") == "MELON")
        if day <= 1 and n_melon < PARAMS["melon_target"] and int(seeds.get("MELON", 0) or 0) > 0:
            for xy in MELON_TILES:
                x, y = xy
                if tiles[y][x] is None:
                    tasks.append((-50, "PLANT", xy, ("MELON",)))
                    break
        elif n_wheat < PARAMS["wheat_target"] and int(seeds.get("WHEAT", 0) or 0) > 0:
            q = "NW" if n_wheat < 14 else "NE"
            empt = self._empty(farm, q)
            if empt:
                tasks.append((-50, "PLANT", empt[0], ("WHEAT",)))

        # (11) CARE animais
        for x, y, t in self._animals(farm):
            if not t.get("cared_today", False):
                tasks.append((-40, "CARE", (x, y), None))

        # (12) DIG weeds
        for y, row in enumerate(tiles):
            for x, t in enumerate(row):
                if isinstance(t, dict) and t.get("kind") == "WEED":
                    tasks.append((-30, "DIG", (x, y), None))

        tasks.sort(key=lambda t: t[0])
        return tasks

    # -------------------------------------------------------------- action
    def decide(self, obs, config=None):
        seat = int(obs.get("player", 0) or 0) or int(obs.get("index", 0) or 0)
        step = int(obs.get("step", 0) or 0)
        day = int(obs.get("day", 0) or 0)
        farm = self._farm(obs, seat)
        private = obs.get("private", {}) or {}
        st = self._state(seat)
        farmer_pos = tuple(farm.get("farmer", [4, 4]))
        hands_pos = [tuple(h) for h in (farm.get("hands") or [])]
        invs = private.get("inventories") or [{}]

        tasks = self._plan(obs, seat, day, step)

        # units disponíveis
        units = [(0, farmer_pos)] + [(i + 1, hands_pos[i]) for i in range(len(hands_pos))]
        cmds = {0: ["PASS"]}
        for i in range(len(hands_pos)):
            cmds[i + 1] = ["PASS"]
        assigned = set()

        for _, kind, target, args in tasks:
            # seleciona o unit livre mais próximo e que pode executar
            best = None
            best_d = 999
            for idx, pos in units:
                if idx in assigned:
                    continue
                # capacidades
                if kind == "PICKUP":
                    if any(int((invs[idx] or {}).get(a, 0) or 0) > 0 for a in ("COW", "SHEEP")):
                        continue  # já carrega animal
                if kind == "PLACE":
                    if not any(int((invs[idx] or {}).get(a, 0) or 0) > 0 for a in ("COW", "SHEEP")):
                        continue  # precisa carregar animal
                if kind == "FEED":
                    if int((invs[idx] or {}).get("WHEAT", 0) or 0) <= 0:
                        continue  # precisa carregar wheat
                d = self._manhattan(pos, target)
                if d < best_d:
                    best_d = d
                    best = (idx, pos)
            if best is None:
                continue
            idx, pos = best
            assigned.add(idx)
            if kind == "PLACE":
                inv = invs[idx] or {}
                animal = next((a for a in ("COW", "SHEEP") if int(inv.get(a, 0) or 0) > 0), None)
                cmd = ["PLACE", animal] if animal else None
            else:
                cmd = self._unit_cmd(kind, target, args, pos)
            if cmd:
                cmds[idx] = cmd

        action = {
            "farmer": cmds[0],
            "hands": [cmds[i + 1] for i in range(len(hands_pos))],
            "market": self._market(obs, seat, day, step),
        }
        return action

    def _unit_cmd(self, kind, target, args, pos):
        if pos != target:
            return self._move(pos, target)
        if kind == "FEED":
            return ["FEED"]
        if kind == "COLLECT_FERT":
            return ["COLLECT_FERTILIZER"]
        if kind == "HARVEST":
            return ["HARVEST"]
        if kind == "WATER":
            return ["WATER"]
        if kind == "FERTILIZE":
            return ["FERTILIZE"]
        if kind == "CARE":
            return ["CARE"]
        if kind == "BUILD_PASTURE":
            return ["BUILD_PASTURE"]
        if kind == "DIG":
            return ["DIG"]
        if kind == "PICKUP":
            return ["PICKUP", args[0], 1]
        if kind == "PLACE":
            # o animal carregado (qualquer um que o unit tenha)
            return ["PLACE"]
        if kind == "PLANT":
            return ["PLANT", args[0]]
        return ["PASS"]

    def _move(self, pos, target):
        dx, dy = target[0] - pos[0], target[1] - pos[1]
        if abs(dx) >= abs(dy):
            return ["EAST"] if dx > 0 else ["WEST"]
        return ["SOUTH"] if dy > 0 else ["NORTH"]

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
        n_melon = sum(1 for _, _, t in self._plants(farm) if t.get("crop") == "MELON")
        n_cow = sum(1 for _, _, t in self._animals(farm) if t.get("animal") == "COW") + int(shed.get("COW", 0) or 0)
        n_sheep = sum(1 for _, _, t in self._animals(farm) if t.get("animal") == "SHEEP") + int(shed.get("SHEEP", 0) or 0)

        # HIRE: até hands_target, só com caixa de sobra (step < 4 do dia)
        if n_hands < PARAMS["hands_target"] and day < 12 and step % 24 < 4 and money > 250:
            need = PARAMS["hands_target"] - n_hands
            market += [["HIRE"]] * min(need, 10 - len(market))

        # BUY_LAND NE no d1 (1000)
        if PARAMS["buy_land"] and not st["land"] and day == 1 and money > 1200 and "NE" not in unlocked:
            market.append(["BUY_LAND"])
            st["land"] = True

        # BUY_ANIMAL — no máximo 1 por dia (orçamento)
        if day < 5 and step % 24 < 4:
            bought_today = st["bought"].get(f"today_{day}", 0)
            if bought_today < 1:
                if n_cow < PARAMS["n_cow"] and money > 480 and len(market) < 10:
                    market.append(["BUY_ANIMAL", "COW", 1])
                    st["bought"]["COW"] += 1
                    st["bought"][f"today_{day}"] = bought_today + 1
                elif n_sheep < PARAMS["n_sheep"] and money > 580 and len(market) < 10:
                    market.append(["BUY_ANIMAL", "SHEEP", 1])
                    st["bought"]["SHEEP"] += 1
                    st["bought"][f"today_{day}"] = bought_today + 1

        # BUY_SEED
        if day <= 20 and n_wheat < PARAMS["wheat_target"] and int(seeds.get("WHEAT", 0) or 0) < 6 and money > 50 and len(market) < 10:
            market.append(["BUY_SEED", "WHEAT", min(6, PARAMS["wheat_target"] - n_wheat)])
        if day == 0 and n_melon < PARAMS["melon_target"] and int(seeds.get("MELON", 0) or 0) < PARAMS["melon_target"] and money > 600 and len(market) < 10:
            market.append(["BUY_SEED", "MELON", PARAMS["melon_target"]])

        # SELL
        self._sell(market, day, shed)

        return market[:10]

    def _sell(self, market, day, shed):
        if 10 <= day <= 12 and int(shed.get("MELON", 0) or 0) > 0 and len(market) < 10:
            market.append(["SELL", "MELON", int(shed.get("MELON", 0) or 0)])
        if 12 <= day <= 14 and int(shed.get("MILK", 0) or 0) > 0 and len(market) < 10:
            market.append(["SELL", "MILK", int(shed.get("MILK", 0) or 0)])
        if day >= 26 and int(shed.get("WOOL", 0) or 0) > 0 and len(market) < 10:
            market.append(["SELL", "WOOL", int(shed.get("WOOL", 0) or 0)])
        w = int(shed.get("WHEAT", 0) or 0)
        if day >= PARAMS["sell_wheat_from"] and w > PARAMS["wheat_reserve"] and len(market) < 10:
            market.append(["SELL", "WHEAT", w - PARAMS["wheat_reserve"]])


_BRAIN = WheatBaseV1()


def agent(obs, config=None):
    return _BRAIN.decide(obs, config)


# ---------------------------------------------------------------------------
# Modo gerador de fita
# ---------------------------------------------------------------------------
def generate_tape(seed: int, steps: int = 720):
    """Roda o agente num seed e grava as ações por step (a fita).

    Uso: tape = generate_tape(seed=1) -> lista[dict] de 720 ações.
    """
    from kaggle_environments import make

    brain = WheatBaseV1()
    tape = []

    def wrapper(obs, config=None):
        action = brain.decide(obs, config)
        step = int((obs or {}).get("step", 0) or 0)
        if len(tape) <= step:
            tape.append(action)
        else:
            tape[step] = action
        return action

    env = make("kaggriculture", configuration={"episodeSteps": steps, "seed": seed})
    env.run([wrapper, wrapper])
    return tape
