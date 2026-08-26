"""wheat_farm — FarmBrain com economia WHEAT-HEAVY (Fase 3, iteração 2).

Lição da iteração 1: fertilizar wheat num coordenador genérico NÃO ajuda —
strawberry usa melhor o fert (cada fert no strawberry ~+$240 vs wheat ~+$80),
e o fert é limitado (1/animal/dia). Por isso wheat_farm perdeu 2-10.

Iteração 2: tornar a economia ESTRUTURALMENTE wheat-heavy:
  - remove STRAWBERRY do crop selection (todo o fert vai para o WHEAT)
  - aumenta wheat_target (mais tiles de wheat)
  - cap melon (crasha rápido)
  - fertilização do wheat jovem (idade 0-2) ativa SEMPRE

Referência: docs/WHEAT_BASE_DESIGN.md.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kaggriculture_real as fb

WHEAT_FERT_AGES = (0, 2)


class WheatHeavyFarm(fb.FarmBrain):
    def __init__(self, **kw):
        defaults = dict(
            crops=["WHEAT", "MELON", "CARROT"],   # sem STRAWBERRY
            fert_strawberry=False,                 # fert vai para o WHEAT
            max_melon_plants=8,
            max_wheat_plants=30,
            melon_plant_gate=230,
            livestock_hands=8,
        )
        defaults.update(kw)
        super().__init__(**defaults)
        self.fert_wheat = True

    def _find_fert_targets(self, obs, farm, day, size):
        """WHEAT jovem não fertilizado (idade 0-2, cobre o window de WATER d2-4)."""
        tiles = farm.get("tiles", [])
        lo, hi = WHEAT_FERT_AGES
        out = []
        for y in range(size):
            for x in range(size):
                t = tiles[y][x]
                if not (isinstance(t, dict) and t.get("kind") == fb.KIND_PLANT and t.get("crop") == "WHEAT"):
                    continue
                age = day - int(t.get("planted_day", day))
                if lo <= age <= hi and int(t.get("fertilized_until_day", -1) or -1) < day:
                    out.append((x, y))
        return out

    def _plan_fert_tasks(self, obs, farm, private, day, size):
        """Idêntico ao pai, mas ignora self.fert_strawberry (fert_wheat sempre ativo)."""
        shed_fert = private.get("shed", {}).get("FERTILIZER", 0)
        targets = self._find_fert_targets(obs, farm, day, size)
        if not targets:
            return []
        n_carry = sum(1 for inv in private.get("inventories", []) if inv.get("FERTILIZER", 0) > 0)
        tasks = []
        if n_carry > 0:
            for xy in targets:
                tasks.append((-0.4, xy, [fb.FERTILIZE], "FERT", False))
        elif shed_fert > 0:
            n_free = sum(
                1 for inv in private.get("inventories", [])
                if inv.get("FERTILIZER", 0) <= 0 and not any(a in inv for a in fb.ANIMALS)
            )
            for _ in range(min(n_free, len(targets), 3)):
                tasks.append((-0.5, fb._shed_tile(farm), [fb.PICKUP, "FERTILIZER", 1], "!FERT", True))
        return tasks


_BRAIN = WheatHeavyFarm()


def agent(obs, config=None):
    return _BRAIN.decide(obs)
