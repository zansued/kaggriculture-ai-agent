"""Shadow interpreter (Fase telemetria DEEP3) — classifica os comandos do Moon
sem alterar política, replicando as regras de no-op do engine.

Para cada worker/step do champion, decide se o comando (nao-MOVE) é
USEFUL (muta estado), NOOP (silent no-op — capacidade desperdicada), ou
UNCLASSIFIED (verbos nao modelados, tratados como possivelmente uteis).
Classifica também:
  - NOOP/PASS sobre tile produtivo (planta ou animal) = folga escondida
  - WATER redundante, HARVEST sem yield, FEED/CARE/COLLECT_FERTILIZER impossíveis
  - PLANT bloqueado/ocupado/sem seed
  - plant_without_water_eod (plantado hoje e nao regado ate hour 23 -> WEED)
  - day-slip: tile de crop colhido que segue VAZIO ao fim do dia (replant so
    no dia seguinte)

Uso:
    python shadow_telemetry.py --seeds 1-6 --json results/shadow_telemetry.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
sys.path.insert(0, os.path.join(_HERE, "src"))

from kaggle_environments import make  # noqa: E402
import purearch_opponent  # noqa: E402
from clock_utils import logical_step  # noqa: E402

MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}
CROPS = {
    "WHEAT": {"first_yield_day": 2, "max_yield_day": 4, "ongoing": False},
    "CARROT": {"first_yield_day": 2, "max_yield_day": 3, "ongoing": False},
    "TOMATO": {"first_yield_day": 8, "max_yield_day": 8, "ongoing": True},
    "STRAWBERRY": {"first_yield_day": 10, "max_yield_day": 10, "ongoing": True},
    "MELON": {"first_yield_day": 10, "max_yield_day": 12, "ongoing": False},
}


def new_counters():
    return {
        "steps": 0, "units": 0,
        "move": 0, "pass": 0,
        "useful": 0, "noop": 0, "unclassified": 0,
        "noop_water": 0, "noop_harvest": 0, "noop_feed": 0, "noop_care": 0,
        "noop_fert": 0, "noop_plant": 0, "noop_dig": 0,
        "noop_on_productive": 0, "pass_on_productive": 0,
        "useful_on_productive": 0,
        # dia
        "plant_without_water_eod": 0, "plant_watered_same_day": 0,
        "eod_empty_crop_tile_days": 0, "harvest_events": 0,
        "harvest_replant_same_day": 0,
        "mature_unharvested_units": 0,
    }


def _is_plant(t):
    return isinstance(t, dict) and t.get("kind") == "PLANT"


def _is_animal(t):
    return isinstance(t, dict) and "animal" in t


def classify(obs, action, C):
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if player >= len(farms):
        return
    farm = farms[player] or {}
    private = obs.get("private") or {}
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)

    tiles = farm.get("tiles") or []
    # shadow do grid (shallow copy por celula)
    sh = [[(dict(t) if isinstance(t, dict) else t) for t in row] for row in tiles]
    invs = [dict(inv) for inv in (private.get("inventories") or [])]
    seeds = dict((private.get("seeds") or {}))

    pos = [list(farm.get("farmer") or [0, 0])]
    pos += [list(p) for p in (farm.get("hands") or [])]
    ua = [list(action.get("farmer") or ["PASS"])]
    ua += [list(h or ["PASS"]) for h in (action.get("hands") or [])]

    C["steps"] += 1
    C["units"] += len(pos)

    # atomicidade de PLANT por crop no turno
    demand = {}
    for a in ua:
        if isinstance(a, list) and len(a) >= 2 and a[0] == "PLANT":
            demand[a[1]] = demand.get(a[1], 0) + 1
    blocked = {c for c, n in demand.items() if n > seeds.get(c, 0)}
    # plantios já feitos no turno (para não estourar seeds no shadow)
    planted_this = {}

    def tile_productive(t):
        return _is_plant(t) or _is_animal(t)

    harvest_this_turn = set()

    for i, p in enumerate(pos):
        if i >= len(ua):
            break
        a = ua[i] or ["PASS"]
        verb = a[0] if a else "PASS"
        if verb in MOVES:
            C["move"] += 1
            continue
        if verb == "PASS":
            C["pass"] += 1
            try:
                x, y = int(p[0]), int(p[1])
                t = sh[y][x]
                if tile_productive(t):
                    C["pass_on_productive"] += 1
            except Exception:
                pass
            continue
        # comando de tile: precisa posicao valida
        try:
            x, y = int(p[0]), int(p[1])
            t = sh[y][x]
        except Exception:
            C["unclassified"] += 1
            continue

        noop = False
        productive = tile_productive(t)
        useful = True

        if verb == "WATER":
            if _is_plant(t) and not t.get("watered_today", False):
                t["watered_today"] = True
            else:
                noop = True
                C["noop_water"] += 1
        elif verb == "HARVEST":
            ok = False
            if _is_plant(t) and int(t.get("yield_units", 0) or 0) > 0:
                cd = CROPS.get(t.get("crop"))
                if cd and (day - int(t.get("planted_day", day) or 0)) >= cd["first_yield_day"]:
                    ok = True
                    if not cd["ongoing"]:
                        sh[y][x] = None
                    else:
                        t["yield_units"] = 0
            elif _is_animal(t) and int(t.get("yield_units", 0) or 0) > 0:
                ok = True
                t["yield_units"] = 0
            if not ok:
                noop = True
                C["noop_harvest"] += 1
            else:
                C["harvest_events"] += 1
                harvest_this_turn.add((x, y))
        elif verb == "FEED":
            if _is_animal(t) and not t.get("fed_today", False):
                inv = invs[i] if i < len(invs) else {}
                if int(inv.get("WHEAT", 0) or 0) > 0:
                    inv["WHEAT"] = inv.get("WHEAT", 0) - 1
                    t["fed_today"] = True
                else:
                    noop = True
                    C["noop_feed"] += 1
            else:
                noop = True
                C["noop_feed"] += 1
        elif verb == "CARE":
            if _is_animal(t) and not t.get("cared_today", False):
                t["cared_today"] = True
            else:
                noop = True
                C["noop_care"] += 1
        elif verb == "COLLECT_FERTILIZER":
            if _is_animal(t) and t.get("fertilizer_available", False):
                t["fertilizer_available"] = False
                inv = invs[i] if i < len(invs) else {}
                inv["FERTILIZER"] = inv.get("FERTILIZER", 0) + 1
            else:
                noop = True
                C["noop_fert"] += 1
        elif verb == "PLANT" and len(a) >= 2:
            crop = a[1]
            if t is not None or crop in blocked:
                noop = True
                C["noop_plant"] += 1
            else:
                have = seeds.get(crop, 0) - planted_this.get(crop, 0)
                if have <= 0:
                    noop = True
                    C["noop_plant"] += 1
                else:
                    planted_this[crop] = planted_this.get(crop, 0) + 1
                    sh[y][x] = {"kind": "PLANT", "crop": crop, "planted_day": day,
                                "watered_today": False, "consecutive_unwatered": 1,
                                "yield_units": 0 if CROPS[crop]["ongoing"] else 1}
        elif verb == "DIG":
            if isinstance(t, dict) and t.get("kind") == "WEED":
                sh[y][x] = None
            else:
                noop = True
                C["noop_dig"] += 1
        else:
            # verbos nao modelados (PICKUP/PLACE/DROP/BUILD_*/FERTILIZE)
            useful = True  # nao sabemos; nao marcar como noop
            C["unclassified"] += 1

        if verb not in ("WATER", "HARVEST", "FEED", "CARE", "COLLECT_FERTILIZER", "PLANT", "DIG"):
            # já contado como unclassified
            continue

        if noop:
            C["noop"] += 1
            if productive:
                C["noop_on_productive"] += 1
        else:
            C["useful"] += 1
            if productive:
                C["useful_on_productive"] += 1

    # ---- métricas de fim de dia / janela ----
    # plants plantadas hoje e o estado de water (usando shadow final do turno)
    for y, row in enumerate(sh):
        for x, t in enumerate(row):
            if _is_plant(t) and int(t.get("planted_day", -1) or -1) == day:
                if hour == 23:
                    if t.get("watered_today", False):
                        C["plant_watered_same_day"] += 1
                    else:
                        C["plant_without_water_eod"] += 1
    # replant same-day: harvest ocorreu neste turno; tile ja replantado neste turno?
    for (x, y) in harvest_this_turn:
        if _is_plant(sh[y][x]):
            C["harvest_replant_same_day"] += 1
    # maduros nao colhidos (informacional): planta com yield>0 madura que nao foi colhida agora
    for row in tiles:
        for t in row:
            if _is_plant(t) and int(t.get("yield_units", 0) or 0) > 0:
                cd = CROPS.get(t.get("crop"))
                if cd and (day - int(t.get("planted_day", day) or 0)) >= cd["first_yield_day"]:
                    C["mature_unharvested_units"] += 1


def parse_seeds(spec):
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",") if x]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="submissions/hybrid_v19/main.py")
    ap.add_argument("--seeds", default="1-6")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    spec = importlib.util.spec_from_file_location(
        "shadow_champ", os.path.join(_HERE, args.agent))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    champ = m.agent

    agg = {"P0": new_counters(), "P1": new_counters()}
    per_seed = {}

    def wrap(fn, champ_seat, C):
        def _a(obs, cfg=None):
            obs = dict(obs)
            obs["step"] = logical_step(obs)
            act = fn(obs, cfg)
            seat = 1 if int(obs.get("player", 0) or 0) == 1 else 0
            if seat == champ_seat:
                classify(obs, act, C)
            return act
        return _a

    for seed in parse_seeds(args.seeds):
        for label in ("P0", "P1"):
            cseat = 0 if label == "P0" else 1
            agents = ([champ, purearch_opponent.agent] if label == "P0"
                      else [purearch_opponent.agent, champ])
            C = new_counters()
            a0 = wrap(agents[0], cseat, C)
            a1 = wrap(agents[1], cseat, C)
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
            env.run([a0, a1])
            for k in agg[label]:
                agg[label][k] += C[k]
            per_seed[f"{seed}_{label}"] = dict(C)
            print(f"seed {seed} {label}: noop={C['noop']} useful={C['useful']} "
                  f"noop_on_prod={C['noop_on_productive']} pass_on_prod={C['pass_on_productive']}",
                  flush=True)

    print("\n=== SHADOW INTERPRETER (champion v19) ===")
    for label in ("P0", "P1"):
        C = agg[label]
        nonmove = C["useful"] + C["noop"] + C["unclassified"]
        print(f"[{label}] steps={C['steps']} units={C['units']} "
              f"move={C['move']} pass={C['pass']} nonmove={nonmove}")
        print(f"   useful={C['useful']} noop={C['noop']} unclassified={C['unclassified']} "
              f"(noop% do nao-move={100.0*C['noop']/max(1,nonmove):.1f})")
        print(f"   noop: water={C['noop_water']} harvest={C['noop_harvest']} feed={C['noop_feed']} "
              f"care={C['noop_care']} fert={C['noop_fert']} plant={C['noop_plant']} dig={C['noop_dig']}")
        print(f"   sobre tile produtivo: noop={C['noop_on_productive']} pass={C['pass_on_productive']} "
              f"useful={C['useful_on_productive']}")
        print(f"   dia: plant_sem_water_eod={C['plant_without_water_eod']} "
              f"plant_water_same_day={C['plant_watered_same_day']} harvest={C['harvest_events']} "
              f"replant_same_day={C['harvest_replant_same_day']} mature_nao_colhido={C['mature_unharvested_units']}")

    if args.json:
        json.dump({"agg": agg, "per_seed": per_seed},
                  open(os.path.join(_HERE, args.json), "w"), indent=1)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
