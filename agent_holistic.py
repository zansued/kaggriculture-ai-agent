"""agent_holistic — Agente REATIVO holístico (job-list greedy global).

Baseado no deep-research (docs/PESQUISA_DEEP.md): os tops usam um despachador
greedy GLOBAL (cada turno, o unit livre mais próximo faz a tarefa de maior
prioridade), NÃO fitas pré-computadas. Isso permite:
  - CARE + FEED no mesmo dia (multiplica produção animal ~3x)
  - colher cedo (melão d10) e replantar imediato (rotação)
  - reutilizar terra liberada (fertilizante vale)
  - reagir ao preço real (vendas adaptativas)

Sprint 1: esqueleto com job-list greedy + economia básica (wheat rotacionado +
melon + animais com CARE). Validar coordenação antes de otimizar economia.

Uso:  python -c "import agent_holistic; agent_holistic.test()"
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# layout
SHED_TILES = {(4, 4), (3, 4), (4, 3), (3, 3)}
PASTURES = [(0, 0), (1, 0)]  # 2 pastagens iniciais (COW)

PARAMS = {
    "hands_target": 8,
    "melon_early": 6,        # melões no d0
    "strawb_target": 8,      # strawberry limitada (não crashar)
    "wheat_target": 30,      # wheat rotacionado
    "sell_wheat_from": 5,
    "wheat_reserve": 10,
}


class AgentHolistic:
    def __init__(self):
        self.op_state = {}

    def _state(self, seat):
        return self.op_state.setdefault(seat, {
            "land": set(), "bought": {"COW": 0},
            "melon_planted": False, "strawb_planted": 0,
        })

    def _farm(self, obs, seat):
        farms = obs.get("farms", []) or []
        return farms[seat] if seat < len(farms) else {}

    def _tiles_of(self, farm):
        return farm.get("tiles", []) or []

    def _manhattan(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _move(self, pos, target):
        if pos == target:
            return None
        dx, dy = target[0] - pos[0], target[1] - pos[1]
        if abs(dx) >= abs(dy):
            return "EAST" if dx > 0 else "WEST"
        return "SOUTH" if dy > 0 else "NORTH"

    # ------------------------------------------------------------ task list
    def _collect_tasks(self, farm, private, day, st, unlocked):
        """Gera job-list hierárquica (prioridade). Cada task: (rank, tipo, (x,y), args)."""
        tiles = self._tiles_of(farm)
        shed = private.get("shed", {}) or {}
        seeds = private.get("seeds", {}) or {}
        tasks = []
        n_wheat = sum(1 for row in tiles for t in row if isinstance(t, dict)
                      and t.get("kind") == "PLANT" and t.get("crop") == "WHEAT")

        # (0) COLHER planta madura (rotação) — prioridade máx
        for y, row in enumerate(tiles):
            for x, t in enumerate(row):
                if isinstance(t, dict) and t.get("kind") == "PLANT":
                    crop = t.get("crop")
                    age = day - int(t.get("planted_day", day))
                    yield_u = int(t.get("yield_units", 0) or 0)
                    first_yd = {"WHEAT": 2, "CARROT": 2, "MELON": 10, "STRAWBERRY": 10, "TOMATO": 8}.get(crop, 10)
                    if yield_u > 0 and age >= first_yd:
                        tasks.append((0, "HARVEST", (x, y), None))

        # (1) ALIMENTAR + CUIDAR animais (CARE multiplica produção)
        for y, row in enumerate(tiles):
            for x, t in enumerate(row):
                if isinstance(t, dict) and "animal" in t:
                    if not t.get("fed_today", False):
                        tasks.append((1, "FEED", (x, y), None))
                    if not t.get("cared_today", False):
                        tasks.append((2, "CARE", (x, y), None))
                    if t.get("fertilizer_available", False):
                        tasks.append((3, "COLLECT_FERT", (x, y), None))
                    if int(t.get("yield_units", 0) or 0) > 0:
                        tasks.append((0, "HARVEST_AN", (x, y), None))

        # (2) REGAR plantas não regadas (sobrevivência)
        for y, row in enumerate(tiles):
            for x, t in enumerate(row):
                if isinstance(t, dict) and t.get("kind") == "PLANT" and not t.get("watered_today", False):
                    tasks.append((4, "WATER", (x, y), None))

        # (3) PLANTAR (melon d0, wheat depois, strawberry limitada)
        if not st["melon_planted"] and int(seeds.get("MELON", 0) or 0) > 0:
            for y, row in enumerate(tiles):
                for x, t in enumerate(row):
                    if t is None and x < 5 and y < 5:
                        tasks.append((5, "PLANT", (x, y), ("MELON",)))
                        st["melon_planted"] = True
                        break
                if st["melon_planted"]:
                    break
        elif n_wheat < PARAMS["wheat_target"] and int(seeds.get("WHEAT", 0) or 0) > 0:
            for y, row in enumerate(tiles):
                for x, t in enumerate(row):
                    if t is None:
                        tasks.append((6, "PLANT", (x, y), ("WHEAT",)))
                        break
                else:
                    continue
                break

        # (4) construir pastagem se precisar
        n_pasture = sum(1 for row in tiles for t in row if isinstance(t, dict) and t.get("kind") == "PASTURE")
        if n_pasture < len(PASTURES) and day < 3:
            for xy in PASTURES:
                x, y = xy
                if not (isinstance(tiles[y][x], dict) and tiles[y][x].get("kind") == "PASTURE"):
                    tasks.append((5, "BUILD_PASTURE", xy, None))
                    break

        # (5) PICKUP/PLACE de animais do shed
        n_carry = sum(1 for inv in (private.get("inventories") or [{}]) if int((inv or {}).get("COW", 0) or 0) > 0)
        n_pasture_free = sum(1 for row in tiles for t in row if isinstance(t, dict) and t.get("kind") == "PASTURE" and not t.get("animal"))
        if int(shed.get("COW", 0) or 0) > 0 and n_carry < n_pasture_free:
            tasks.append((7, "PICKUP", (4, 4), ("COW",)))
        for y, row in enumerate(tiles):
            for x, t in enumerate(row):
                if isinstance(t, dict) and t.get("kind") == "PASTURE" and not t.get("animal"):
                    tasks.append((7, "PLACE", (x, y), None))

        return sorted(tasks, key=lambda t: t[0])

    # ------------------------------------------------------------ dispatch
    def _dispatch(self, unit_idx, pos, tasks, tiles, invs, shed):
        """Para um unit, decide a ação (executa a task mais próxima que pode)."""
        for rank, kind, (tx, ty), args in tasks:
            # capacidades
            if kind == "FEED" and int((invs[unit_idx] or {}).get("WHEAT", 0) or 0) <= 0:
                # precisa pegar wheat do shed primeiro
                if int(shed.get("WHEAT", 0) or 0) > 0:
                    if pos in SHED_TILES:
                        return ["PICKUP", "WHEAT", 5]
                    return [self._move(pos, (4, 4)) or "PASS"]
                continue
            if kind == "PLACE" and not any(int((invs[unit_idx] or {}).get(a, 0) or 0) > 0 for a in ("COW", "SHEEP")):
                continue
            if kind == "PICKUP" and any(int((invs[unit_idx] or {}).get(a, 0) or 0) > 0 for a in ("COW", "SHEEP")):
                continue
            d = self._manhattan(pos, (tx, ty))
            if d <= 1:
                if kind == "HARVEST" or kind == "HARVEST_AN":
                    return ["HARVEST"]
                if kind == "FEED":
                    return ["FEED"]
                if kind == "CARE":
                    return ["CARE"]
                if kind == "COLLECT_FERT":
                    return ["COLLECT_FERTILIZER"]
                if kind == "WATER":
                    return ["WATER"]
                if kind == "PLANT":
                    return ["PLANT", args[0]]
                if kind == "BUILD_PASTURE":
                    return ["BUILD_PASTURE"]
                if kind == "PICKUP":
                    return ["PICKUP", args[0], 1]
                if kind == "PLACE":
                    animal = next((a for a in ("COW", "SHEEP") if int((invs[unit_idx] or {}).get(a, 0) or 0) > 0), None)
                    return ["PLACE", animal] if animal else ["PASS"]
            else:
                # move em direção ao alvo
                m = self._move(pos, (tx, ty))
                return [m] if m else ["PASS"]
        return ["PASS"]

    def decide(self, obs, config=None):
        seat = int(obs.get("player", 0) or 0) or int(obs.get("index", 0) or 0)
        step = int(obs.get("step", 0) or 0)
        day = int(obs.get("day", 0) or 0)
        if step == 0:
            self.op_state[seat] = {"land": set(), "bought": {"COW": 0},
                                   "melon_planted": False, "strawb_planted": 0}
        st = self._state(seat)
        farm = self._farm(obs, seat)
        private = obs.get("private", {}) or {}
        tiles = self._tiles_of(farm)
        unlocked = set(farm.get("unlocked_quadrants") or [])
        invs = private.get("inventories") or [{}]
        shed = private.get("shed", {}) or {}

        tasks = self._collect_tasks(farm, private, day, st, unlocked)
        if not tasks:
            tasks = []

        farmer_pos = tuple(farm.get("farmer", [4, 4]))
        hands_pos = [tuple(h) for h in (farm.get("hands") or [])]
        units = [(0, farmer_pos)] + [(i + 1, hands_pos[i]) for i in range(len(hands_pos))]

        cmds = {0: ["PASS"]}
        for i in range(len(hands_pos)):
            cmds[i + 1] = ["PASS"]
        assigned_tasks = set()

        for idx, pos in units:
            # pega a task mais próxima que o unit PODE fazer (não atribuída)
            best = None; bd = 999
            for ti, (rank, kind, (tx, ty), args) in enumerate(tasks):
                if ti in assigned_tasks:
                    continue
                # capacidade básica
                if kind == "FEED" and int((invs[idx] or {}).get("WHEAT", 0) or 0) <= 0 and int(shed.get("WHEAT", 0) or 0) <= 0:
                    continue
                if kind == "PLACE" and not any(int((invs[idx] or {}).get(a, 0) or 0) > 0 for a in ("COW", "SHEEP")):
                    continue
                d = self._manhattan(pos, (tx, ty))
                if d < bd:
                    bd = d; best = (ti, kind, (tx, ty), args)
            if best is not None:
                ti, kind, target, args = best
                assigned_tasks.add(ti)
                cmd = self._dispatch(idx, pos, [tasks[ti]], tiles, invs, shed)
                if cmd:
                    cmds[idx] = cmd

        market = self._market(obs, seat, farm, private, day, step, st, unlocked)
        return {
            "farmer": cmds[0],
            "hands": [cmds[i + 1] for i in range(len(hands_pos))],
            "market": market,
        }

    # ------------------------------------------------------------ market
    def _market(self, obs, seat, farm, private, day, step, st, unlocked):
        money = float(farm.get("money", 0) or 0)
        shed = private.get("shed", {}) or {}
        seeds = private.get("seeds", {}) or {}
        market = []
        n_hands = len(farm.get("hands") or [])
        tiles = self._tiles_of(farm)
        n_wheat = sum(1 for row in tiles for t in row if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == "WHEAT")

        # BUY_SEED (melon d0, wheat depois)
        if day == 0 and int(seeds.get("MELON", 0) or 0) < PARAMS["melon_early"] and money > 500 and len(market) < 10:
            market.append(["BUY_SEED", "MELON", PARAMS["melon_early"]])
        elif n_wheat < PARAMS["wheat_target"] and int(seeds.get("WHEAT", 0) or 0) < 10 and money > 50 and len(market) < 10:
            market.append(["BUY_SEED", "WHEAT", min(10, PARAMS["wheat_target"] - n_wheat)])

        # BUY_LAND NE d1
        if "NE" not in unlocked and "NE" not in st["land"] and day == 1 and money > 1200 and len(market) < 10:
            market.append(["BUY_LAND"]); st["land"].add("NE")

        # BUY_ANIMAL COW (d0-d3)
        n_cow = sum(1 for row in tiles for t in row if isinstance(t, dict) and t.get("animal") == "COW") + int(shed.get("COW", 0) or 0)
        if day < 4 and n_cow < 2 and money > 450 and len(market) < 10 and st["bought"]["COW"] < 2:
            market.append(["BUY_ANIMAL", "COW", 1]); st["bought"]["COW"] += 1

        # BUY_PRODUCT WHEAT p/ feed (antes do wheat próprio)
        if day < 5 and n_cow > 0 and int(shed.get("WHEAT", 0) or 0) < 15 and money > 150 and len(market) < 10:
            market.append(["BUY_PRODUCT", "WHEAT", min(15 - int(shed.get("WHEAT", 0) or 0), int(money // 30))])

        # HIRE
        if n_hands < PARAMS["hands_target"] and day < 14 and money > 150 and len(market) < 10:
            need = min(PARAMS["hands_target"] - n_hands, 10 - len(market))
            market += [["HIRE"]] * need

        # SELL (fracionado, simples)
        self._sell(market, day, shed, money)

        return market[:10]

    def _sell(self, market, day, shed, money):
        # milk/wheat excedente (fracionado)
        if int(shed.get("MILK", 0) or 0) > 0 and day >= 8 and len(market) < 10:
            market.append(["SELL", "MILK", min(int(shed.get("MILK", 0) or 0), 10)])
        w = int(shed.get("WHEAT", 0) or 0)
        if day >= PARAMS["sell_wheat_from"] and w > PARAMS["wheat_reserve"] and len(market) < 10:
            market.append(["SELL", "WHEAT", w - PARAMS["wheat_reserve"]])


_BRAIN = AgentHolistic()


def agent(obs, config=None):
    return _BRAIN.decide(obs, config)


def test(seeds=range(1, 4)):
    from kaggle_environments import make
    import statistics
    rs = []
    for seed in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([agent, agent])
        r = env.steps[-1][0]["reward"]
        rs.append(r)
        print(f"seed {seed}: {r:.0f}")
    print(f"media: {statistics.mean(rs):.0f}")


if __name__ == "__main__":
    test()
