"""zc_core — Coordenador de ZONAS (projeto estrutural, Sprint 0-1).

Base da NOVA economia (docs/SPRINTS.md). Substitui a fita Moon por um
coordenador por estado com ZONAS dedicadas por hand:
  - Cada hand é dono de uma zona (conjunto de tiles).
  - Ciclo por tile: PLANT -> WATER -> HARVEST(age>=2) -> replant IMEDIATO.
  - Zonas disjuntas => sem colisão => coordenação simples e escalável.

Sprint 0-1: motor de WHEAT rotacionado (sem premium/animais ainda).
Meta: reward > 12k no seed 1 (referência: wheat_cell 5.4k).

Uso:  python -c "import zc_core; zc_core.test()"
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Zonas por quadrante (cada zona = um hand)
ZONAS = {
    "NW": [(x, y) for x in range(0, 5) for y in range(0, 5)],
    "NE": [(x, y) for x in range(5, 10) for y in range(0, 5)],
    "SW": [(x, y) for x in range(0, 5) for y in range(5, 10)],
    "SE": [(x, y) for x in range(5, 10) for y in range(5, 10)],
}

PARAMS = {
    "hands_target": 10,
    "wheat_target": 60,          # tiles de wheat simultâneos (NW+NE+SW)
    "buy_land": True,            # NE d1, SW d5
    "sell_wheat_from": 5,
    "wheat_reserve": 10,
}


class ZCCore:
    def __init__(self):
        self.op_state = {}

    def _state(self, seat):
        return self.op_state.setdefault(seat, {"land": set(), "seed_bought": 0})

    def _farm(self, obs, seat):
        farms = obs.get("farms", []) or []
        return farms[seat] if seat < len(farms) else {}

    def _manhattan(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _move(self, pos, target):
        dx, dy = target[0] - pos[0], target[1] - pos[1]
        if abs(dx) >= abs(dy):
            return "EAST" if dx > 0 else "WEST"
        return "SOUTH" if dy > 0 else "NORTH"

    def _decide_tile(self, tile, day, seeds):
        """Ação para um tile na zona (foco wheat rotacionado)."""
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
            return ("HARVEST",)          # rotação rápida
        if not tile.get("watered_today", False):
            return ("WATER",)
        if age >= 2 and yield_u > 0:
            return ("HARVEST",)
        return None

    def decide(self, obs, config=None):
        seat = int(obs.get("player", 0) or 0) or int(obs.get("index", 0) or 0)
        step = int(obs.get("step", 0) or 0)
        day = int(obs.get("day", 0) or 0)
        if step == 0:
            self.op_state[seat] = {"land": set(), "seed_bought": 0}
        st = self._state(seat)
        farm = self._farm(obs, seat)
        private = obs.get("private", {}) or {}
        tiles = farm.get("tiles", []) or []
        seeds = int((private.get("seeds") or {}).get("WHEAT", 0) or 0)
        money = float(farm.get("money", 0) or 0)
        unlocked = set(farm.get("unlocked_quadrants") or [])
        hands_pos = [tuple(h) for h in (farm.get("hands") or [])]

        # ---- zonas ativas (quadrantes desbloqueados) ----
        active_zones = [q for q in ZONAS if q in unlocked] or ["NW"]

        # ---- atribuir hands às zonas (hand i -> zona i % n_zones) ----
        n_zones = len(active_zones)
        hand_zone = [active_zones[i % n_zones] for i in range(len(hands_pos))]

        # ---- alvos por zona (prioridade: colher > regar > plantar) ----
        # para cada hand, acha o melhor tile NA SUA ZONA
        cmds = {0: ["PASS"]}
        for i in range(len(hands_pos)):
            cmds[i + 1] = ["PASS"]
        assigned_zones = set()

        # conta wheat para limitar plantio
        n_wheat = sum(1 for row in tiles for t in row if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == "WHEAT")

        # ---- coleta de alvos globais (rega prioritária) ----
        unwatered = []
        harvestable = []
        plantable = []
        for y, row in enumerate(tiles):
            for x, t in enumerate(row):
                if not isinstance(t, dict):
                    if t is None and n_wheat < PARAMS["wheat_target"]:
                        plantable.append((x, y))
                    continue
                if t.get("kind") == "PLANT":
                    crop = t.get("crop")
                    age = day - int(t.get("planted_day", day))
                    yield_u = int(t.get("yield_units", 0) or 0)
                    if not t.get("watered_today", False):
                        unwatered.append((x, y))
                    elif crop == "WHEAT" and age >= 2 and yield_u > 0:
                        harvestable.append((x, y))
                    elif crop != "WHEAT" and not t.get("watered_today", False):
                        unwatered.append((x, y))

        # atribui cada hand: REGA (prioridade) > COLHEITA > PLANTA > zona
        for hi, pos in enumerate(hands_pos):
            # 1. regar tile não regado mais próximo (global)
            if unwatered:
                best = min(unwatered, key=lambda p: self._manhattan(pos, p))
                dx, dy = best[0]-pos[0], best[1]-pos[1]
                if abs(dx)+abs(dy) <= 1:
                    cmds[hi+1] = ["WATER"]
                else:
                    cmds[hi+1] = [self._move(pos, best)]
                continue
            # 2. colher wheat maduro mais próximo
            if harvestable:
                best = min(harvestable, key=lambda p: self._manhattan(pos, p))
                dx, dy = best[0]-pos[0], best[1]-pos[1]
                if abs(dx)+abs(dy) <= 1:
                    cmds[hi+1] = ["HARVEST"]
                else:
                    cmds[hi+1] = [self._move(pos, best)]
                continue
            # 3. plantar wheat em tile vazio
            if plantable and seeds > 0:
                best = plantable[0]
                dx, dy = best[0]-pos[0], best[1]-pos[1]
                if abs(dx)+abs(dy) <= 1:
                    cmds[hi+1] = ["PLANT", "WHEAT"]
                else:
                    cmds[hi+1] = [self._move(pos, best)]
                continue
            # 4. senão: zona (produção)
            zona = hand_zone[hi]
            zone_tiles = [t for t in ZONAS[zona] if t[0] < 10 and t[1] < 10]
            best = None; bd = 999
            for tx, ty in zone_tiles:
                t = tiles[ty][tx] if (0 <= ty < len(tiles) and 0 <= tx < len(tiles[ty])) else None
                if t is None and seeds > 0 and n_wheat < PARAMS["wheat_target"]:
                    d = self._manhattan(pos, (tx, ty))
                    if d < bd: bd = d; best = (tx, ty)
            if best is not None:
                m = self._move(pos, best)
                cmds[hi+1] = [m] if m else ["PASS"]

        # ---- market ----
        market = []
        n_hands = len(hands_pos)

        # BUY_SEED WHEAT
        if n_wheat < PARAMS["wheat_target"] and seeds < 12 and money > 60 and len(market) < 10:
            q = 12 if day == 0 else 8
            market.append(["BUY_SEED", "WHEAT", min(q, PARAMS["wheat_target"] - n_wheat)])

        # BUY_LAND NE d1, SW d5
        if PARAMS["buy_land"]:
            if "NE" not in unlocked and "NE" not in st["land"] and day == 1 and money > 1200 and len(market) < 10:
                market.append(["BUY_LAND"]); st["land"].add("NE")
            elif "SW" not in unlocked and "SW" not in st["land"] and day == 5 and money > 2500 and len(market) < 10:
                market.append(["BUY_LAND"]); st["land"].add("SW")

        # HIRE (até hands_target)
        if n_hands < PARAMS["hands_target"] and day < 14 and money > 150 and len(market) < 10:
            need = min(PARAMS["hands_target"] - n_hands, 10 - len(market))
            market += [["HIRE"]] * need

        # SELL WHEAT excedente
        shed_w = int(private.get("shed", {}).get("WHEAT", 0) or 0)
        if day >= PARAMS["sell_wheat_from"] and shed_w > PARAMS["wheat_reserve"] and len(market) < 10:
            market.append(["SELL", "WHEAT", shed_w - PARAMS["wheat_reserve"]])

        return {
            "farmer": ["PASS"],
            "hands": [cmds[i + 1] for i in range(len(hands_pos))],
            "market": market[:10],
        }


_BRAIN = ZCCore()


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
