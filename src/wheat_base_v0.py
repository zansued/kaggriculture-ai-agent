"""wheat_base_v0 — protótipo reativo da base wheat-heavy (Fase 3).

Valida a ECONOMIA wheat-heavy (docs/WHEAT_BASE_DESIGN.md):
  - wheat em volume com FERTILIZAÇÃO (yield 4->6, +50%) e rotação
  - animais (COW+SHEEP) como motor de FERTILIZER + produtos premium
  - vendas por TIMING (melon d10-12, milk d12-14, strawb d15-16, wool d27)
  - fertilizante NUNCA vendido barato — usado em FERTILIZE

v0.1: corrige bugs de sobrevivência (rega diária, market com estado,
      construção de pastagem, prioridade de sementes).

Uso:  python -c "from src.wheat_base_v0 import agent; ..."  ou via h2h_bench.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
CROPS = {"WHEAT": (10, 6), "CARROT": (20, 4), "TOMATO": (50, 4),
         "STRAWBERRY": (100, 4), "MELON": (80, 6)}
ANIMALS = {"GOOSE": ("EGG", 4), "COW": ("MILK", 6), "SHEEP": ("WOOL", 6)}
SHED_TILES = {(3, 3), (4, 3), (3, 4), (4, 4)}
MOVE_D = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
BASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
        "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}

# janela de rega que dá yield (dias após plantio) + maturidade/primeiro yield
CROP_TIMING = {
    "WHEAT": (2, 4), "CARROT": (2, 3), "MELON": (10, 12),
    "TOMATO": (8, 8), "STRAWBERRY": (10, 10),
}

PARAMS = {
    "n_cow": 2, "n_sheep": 2,
    "wheat_target": 15,          # tiles de wheat simultâneos (NW 5x5)
    "melon_early": 0,
    "hands_target": 6,
    "fert_threshold": 4,         # fertilizar enquanto houver fert disponível
    "wheat_reserve": 20,         # reserva de feed
    "sell_wheat_from": 9,
    "buy_land": False,
}


def _get(d, k, default=None):
    if isinstance(d, dict):
        return d.get(k, default)
    return getattr(d, k, default)


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _move_toward(pos, target):
    if pos == target:
        return None
    dx, dy = target[0] - pos[0], target[1] - pos[1]
    if abs(dx) >= abs(dy):
        return "EAST" if dx > 0 else "WEST"
    return "SOUTH" if dy > 0 else "NORTH"


class WheatBaseV0:
    def __init__(self):
        self.op_state = {}

    def _state(self, seat):
        return self.op_state.setdefault(seat, {
            "bought": {"COW": 0, "SHEEP": 0, "NE": False, "SW": False, "SE": False},
            "hired_peak": 0,
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

    def _empty_tiles(self, farm, only_quadrant=None):
        out = []
        for y, row in enumerate(farm.get("tiles", []) or []):
            for x, t in enumerate(row):
                if t is None:
                    if only_quadrant is None:
                        out.append((x, y))
                    else:
                        q = "NW" if x < 5 and y < 5 else "NE" if x >= 5 and y < 5 else "SW" if x < 5 and y >= 5 else "SE"
                        if q == only_quadrant:
                            out.append((x, y))
        return out

    # ------------------------------------------------------------ planning
    def _plan_tasks(self, obs, seat, day, step):
        farm = self._farm(obs, seat)
        private = obs.get("private", {}) or {}
        tiles = farm.get("tiles", []) or []
        tasks = []
        unlocked = set(farm.get("unlocked_quadrants") or [])

        # (a) FEED animais não alimentados — foge em 2 dias
        for x, y, t in self._animals(farm):
            if not t.get("fed_today", False):
                tasks.append((-100, "FEED", (x, y), None))

        # (b) construir pastagem/coop se faltar estrutura para animais planejados
        n_pasture = sum(1 for row in tiles for t in row if isinstance(t, dict) and t.get("kind") == "PASTURE")
        n_animals = len(self._animals(farm))
        if n_pasture < 4 and day < 4:
            for x, y in self._empty_tiles(farm):
                if x < 5 and y < 5:
                    tasks.append((-95, "BUILD_PASTURE", (x, y), None))
                    break

        # (c) COLLECT_FERTILIZER disponível
        for x, y, t in self._animals(farm):
            if t.get("fertilizer_available", False):
                tasks.append((-90, "COLLECT_FERT", (x, y), None))

        # (d) HARVEST plantas prontas (yield > 0)
        for x, y, t in self._plants(farm):
            if int(t.get("yield_units", 0) or 0) > 0:
                tasks.append((-85, "HARVEST", (x, y), None))

        # (e) HARVEST animais com produto
        for x, y, t in self._animals(farm):
            if int(t.get("yield_units", 0) or 0) > 0:
                tasks.append((-80, "HARVEST", (x, y), None))

        # (f) WATER — regar TODA planta não regada (sobrevivência; na janela dá yield)
        for x, y, t in self._plants(farm):
            if not t.get("watered_today", False):
                tasks.append((-70, "WATER", (x, y), None))

        # (g) FERTILIZE plantas não fertilizadas se houver fert disponível
        fert_avail = self._count_fert(obs, private)
        if fert_avail >= PARAMS["fert_threshold"]:
            for x, y, t in self._plants(farm):
                if int(t.get("fertilized_until_day", -1) or -1) < day:
                    tasks.append((-60, "FERTILIZE", (x, y), None))

        # (h) PLANT — wheat contínuo (expansão + replantio após colheita)
        seeds = private.get("seeds", {}) or {}
        n_wheat = sum(1 for _, _, t in self._plants(farm) if t.get("crop") == "WHEAT")
        if n_wheat < PARAMS["wheat_target"] and int(seeds.get("WHEAT", 0) or 0) > 0:
            for x, y in self._empty_tiles(farm, "NW"):
                tasks.append((-50, "PLANT", (x, y), ("WHEAT",)))
                break

        # (i) PLACE animais do shed
        shed = private.get("shed", {}) or {}
        for animal in ("COW", "SHEEP"):
            if int((shed or {}).get(animal, 0) or 0) > 0:
                for y, row in enumerate(tiles):
                    for x, t in enumerate(row):
                        if isinstance(t, dict) and t.get("kind") == "PASTURE" and not t.get("animal"):
                            tasks.append((-40, "PLACE", (x, y), (animal,)))
                            break
                    else:
                        continue
                    break

        # (j) CARE animais não cuidados
        for x, y, t in self._animals(farm):
            if not t.get("cared_today", False):
                tasks.append((-30, "CARE", (x, y), None))

        tasks.sort(key=lambda t: t[0])
        return tasks

    def _count_fert(self, obs, private):
        shed = private.get("shed", {}) or {}
        n = int(shed.get("FERTILIZER", 0) or 0)
        for inv in (private.get("inventories") or []):
            n += int((inv or {}).get("FERTILIZER", 0) or 0)
        return n

    # -------------------------------------------------------------- action
    def decide(self, obs, config=None):
        seat = int(obs.get("player", 0) or 0) or int(obs.get("index", 0) or 0)
        step = int(obs.get("step", 0) or 0)
        day = int(obs.get("day", 0) or 0)
        farm = self._farm(obs, seat)
        farmer_pos = list(farm.get("farmer", [4, 4]))
        hands_pos = [list(h) for h in (farm.get("hands") or [])]

        tasks = self._plan_tasks(obs, seat, day, step)

        cmds = {0: ["PASS"]}
        for i in range(len(hands_pos)):
            cmds[i + 1] = ["PASS"]
        assigned = set()

        for _, kind, target, args in tasks:
            best = None
            best_d = 999
            all_units = [(0, tuple(farmer_pos))] + [(i + 1, tuple(h)) for i, h in enumerate(hands_pos)]
            for idx, pos in all_units:
                if idx in assigned:
                    continue
                d = _manhattan(pos, target)
                if d < best_d:
                    best_d = d
                    best = (idx, pos)
            if best is None:
                continue
            idx, pos = best
            assigned.add(idx)
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
            m = _move_toward(pos, target)
            return [m] if m else ["PASS"]
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
        if kind == "PLACE":
            return ["PLACE", args[0]]
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
        prices = (obs.get("market") or {}).get("prices", {}) or {}
        unlocked = farm.get("unlocked_quadrants") or []
        market = []

        n_hands = len(farm.get("hands") or [])
        n_cow = sum(1 for _, _, t in self._animals(farm) if t.get("animal") == "COW") + int(shed.get("COW", 0) or 0)
        n_sheep = sum(1 for _, _, t in self._animals(farm) if t.get("animal") == "SHEEP") + int(shed.get("SHEEP", 0) or 0)
        n_wheat = sum(1 for _, _, t in self._plants(farm) if t.get("crop") == "WHEAT")

        # HIRE — só no início do dia e com dinheiro de sobra
        if n_hands < PARAMS["hands_target"] and day < 14 and step % 24 < 4 and money > 300:
            need = PARAMS["hands_target"] - n_hands
            market += [["HIRE"]] * min(need, 10 - len(market))

        # BUY_LAND — opcional (default off no protótipo)
        if PARAMS["buy_land"]:
            if day == 0 and "NE" not in unlocked and money > 1500 and not st["bought"]["NE"]:
                market.append(["BUY_LAND"])
                st["bought"]["NE"] = True
            elif day >= 3 and "NE" in unlocked and "SW" not in unlocked and money > 2800 and not st["bought"]["SW"]:
                market.append(["BUY_LAND"])
                st["bought"]["SW"] = True

        # BUY_ANIMAL COW + SHEEP (primeiros dias)
        if day < 5:
            if n_cow < PARAMS["n_cow"] and money > 450 and len(market) < 10 and st["bought"]["COW"] < PARAMS["n_cow"]:
                market.append(["BUY_ANIMAL", "COW", 1])
                st["bought"]["COW"] += 1
            elif n_sheep < PARAMS["n_sheep"] and money > 550 and len(market) < 10 and st["bought"]["SHEEP"] < PARAMS["n_sheep"]:
                market.append(["BUY_ANIMAL", "SHEEP", 1])
                st["bought"]["SHEEP"] += 1

        # BUY_SEED — WHEAT (manter estoque)
        if day <= 20 and n_wheat < PARAMS["wheat_target"] and int(seeds.get("WHEAT", 0) or 0) < 6 and money > 60 and len(market) < 10:
            market.append(["BUY_SEED", "WHEAT", min(6, PARAMS["wheat_target"] - n_wheat)])

        # SELL por timing
        self._sell_orders(market, day, shed, prices)

        return market[:10]

    def _sell_orders(self, market, day, shed, prices):
        if 10 <= day <= 12 and int(shed.get("MELON", 0) or 0) > 0 and len(market) < 10:
            market.append(["SELL", "MELON", int(shed.get("MELON", 0) or 0)])
        if 12 <= day <= 14 and int(shed.get("MILK", 0) or 0) > 0 and len(market) < 10:
            market.append(["SELL", "MILK", int(shed.get("MILK", 0) or 0)])
        if 15 <= day <= 16 and int(shed.get("STRAWBERRY", 0) or 0) > 0 and len(market) < 10:
            market.append(["SELL", "STRAWBERRY", int(shed.get("STRAWBERRY", 0) or 0)])
        if day >= 26 and int(shed.get("WOOL", 0) or 0) > 0 and len(market) < 10:
            market.append(["SELL", "WOOL", int(shed.get("WOOL", 0) or 0)])
        w = int(shed.get("WHEAT", 0) or 0)
        if day >= PARAMS["sell_wheat_from"] and w > PARAMS["wheat_reserve"] and len(market) < 10:
            market.append(["SELL", "WHEAT", w - PARAMS["wheat_reserve"]])


_BRAIN = WheatBaseV0()


def agent(obs, config=None):
    return _BRAIN.decide(obs, config)
