"""Probe TPS/cow — telemetria de oportunidade no agente v19 champion.

Roda partidas reais (engine oficial local) com o agente num dos seats (e o
outro também, para espelhar), injeta o relógio canônico e conta, por step:

  - comandos MOVE vs PASS vs non-move úteis (por worker)
  - workers parados (cmd PASS/non-move) sobre tile WHEAT maduro (yield>0) e
    sobre tile vazio com sementes de WHEAT  (oportunidade TPS-crop)
  - co-localização: quantos workers sobre o MESMO tile (janelas p/ transação)
  - ritmo das COWs por dia: fed_today / cared_today / pending_care_bonus /
    productive_eve / yield, e quantos workers parados sobre a COW (slots p/
    FEED/CARE splice)

Uso:
    python probe_tps.py --agent submissions/hybrid_v19/main.py --seeds 1-2 --json results/probe_tps.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
sys.path.insert(0, os.path.join(_HERE, "src"))

from kaggle_environments import make  # noqa: E402
import purearch_opponent  # noqa: E402
from clock_utils import logical_step  # noqa: E402

MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}
STATE = {"tot": 0, "unit_turns": 0, "move": 0, "pass": 0, "nonmove": 0,
         "ripe_wheat_any": 0, "ripe_wheat_wasted": 0,
         "empty_wheat_any": 0, "empty_wheat_wasted": 0,
         "empty_wheat_seeds0": 0,
         "groups_same_tile": 0, "max_group": 0,
         # cow
         "cow_days": 0, "cow_fed": 0, "cow_cared": 0, "cow_fedprod": 0,
         "cow_prod_eve_any": 0, "cow_prod_eve_unfed": 0, "cow_prod_eve_uncared": 0,
         "cow_pass_slots": 0, "cow_feed_slots": 0, "cow_care_slots": 0,
         "cow_unfed_risk_days": 0}


def _is_plant(t):
    return isinstance(t, dict) and t.get("kind") == "PLANT"


def _is_animal(t):
    return isinstance(t, dict) and "animal" in t


def _wrap(agent_fn, state: dict):
    def _a(obs, cfg=None):
        obs = dict(obs)
        obs["step"] = logical_step(obs)
        action = agent_fn(obs, cfg)
        _scan(obs, action, state)
        return action
    return _a


def _scan(obs, action, S):
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if player >= len(farms):
        return
    farm = farms[player] or {}
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    step = logical_step(obs)

    private = obs.get("private") or {}
    seeds = (private.get("seeds") or {}) if hasattr(private, "get") else {}
    pos_list = [list(farm.get("farmer") or [0, 0])]
    pos_list += [list(p) for p in (farm.get("hands") or [])]
    tiles = farm.get("tiles") or []

    fcmd = (action.get("farmer") or ["PASS"]) if isinstance(action, dict) else ["PASS"]
    hcmds = (action.get("hands") or []) if isinstance(action, dict) else []
    unit_cmds = [fcmd, *hcmds]

    S["tot"] += 1
    from collections import Counter
    tile_occupancy = Counter()

    # ---- crops + generic stats ----
    for i, pos in enumerate(pos_list):
        if i >= len(unit_cmds):
            break
        cmd = unit_cmds[i] or ["PASS"]
        verb = cmd[0] if isinstance(cmd, list) and cmd else "PASS"
        S["unit_turns"] += 1
        if verb in MOVES:
            S["move"] += 1
            continue
        if verb == "PASS":
            S["pass"] += 1
        else:
            S["nonmove"] += 1
        try:
            x, y = int(pos[0]), int(pos[1])
            t = tiles[y][x]
        except Exception:
            continue
        tile_occupancy[(x, y)] += 1
        if _is_plant(t) and t.get("crop") == "WHEAT" and int(t.get("yield_units", 0) or 0) > 0:
            S["ripe_wheat_any"] += 1
            if verb != "HARVEST":
                S["ripe_wheat_wasted"] += 1
        if t is None:
            has_seed = int(seeds.get("WHEAT", 0) or 0) > 0 if hasattr(seeds, "get") else False
            if has_seed:
                S["empty_wheat_any"] += 1
                if verb != "PLANT":
                    S["empty_wheat_wasted"] += 1
            else:
                S["empty_wheat_seeds0"] += 1

    # co-localização (mesmo tile com >=2 workers) — janelas de transação
    for (x, y), c in tile_occupancy.items():
        if c >= 2:
            S["groups_same_tile"] += 1
            S["max_group"] = max(S["max_group"], c)

    # ---- cows ----
    # inventory do worker para FEED (WHEAT em mãos)
    invs = (private.get("inventories") or []) if hasattr(private, "get") else []
    for i, pos in enumerate(pos_list):
        if i >= len(unit_cmds):
            break
        cmd = unit_cmds[i] or ["PASS"]
        verb = cmd[0] if isinstance(cmd, list) and cmd else "PASS"
        if verb in MOVES:
            continue
        try:
            x, y = int(pos[0]), int(pos[1])
            t = tiles[y][x]
        except Exception:
            continue
        if not _is_animal(t) or t.get("animal") != "COW":
            continue
        placed = int(t.get("placed_day", 0) or 0)
        fed = bool(t.get("fed_today", False))
        cared = bool(t.get("cared_today", False))
        pcb = int(t.get("pending_care_bonus", 0) or 0)
        unfed = int(t.get("consecutive_unfed", 0) or 0)
        prod_eve = ((day + 1) - placed - 8) >= 0 and ((day + 1) - placed - 8) % 2 == 0
        if verb == "PASS":
            S["cow_pass_slots"] += 1
        elif verb == "FEED":
            S["cow_feed_slots"] += 1
        elif verb == "CARE":
            S["cow_care_slots"] += 1
        if hour == 23:
            S["cow_days"] += 1
            if fed:
                S["cow_fed"] += 1
            if cared:
                S["cow_cared"] += 1
            if prod_eve:
                S["cow_prod_eve_any"] += 1
                if fed:
                    S["cow_fedprod"] += 1
                else:
                    S["cow_prod_eve_unfed"] += 1
                if not cared:
                    S["cow_prod_eve_uncared"] += 1
            if unfed >= 1:
                S["cow_unfed_risk_days"] += 1


def _load(path):
    base = os.path.basename(path).replace(".py", "")
    base = re.sub(r"[^A-Za-z0-9_]", "_", base)
    spec = importlib.util.spec_from_file_location("ag_" + base, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = mod.agent
    try:
        n = len([p for p in __import__("inspect").signature(fn).parameters.values()])
    except Exception:
        n = 2
    if n < 2:
        f0 = fn
        def fn(obs, cfg=None):  # noqa: F811
            return f0(obs)
    return fn


def parse_seeds(spec):
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",") if x]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="submissions/hybrid_v19/main.py")
    ap.add_argument("--seeds", default="1-2")
    ap.add_argument("--json", default=None)
    ap.add_argument("--opp", default="purearch")
    args = ap.parse_args()

    champion = _load(os.path.join(_HERE, args.agent))
    opp = purearch_opponent.agent if args.opp == "purearch" else _load(os.path.join(_HERE, args.opp))

    agg = {"P0": dict(STATE), "P1": dict(STATE)}
    per_seed = {}
    for seed in parse_seeds(args.seeds):
        for label, agents in (("P0", [champion, opp]), ("P1", [opp, champion])):
            st = dict(STATE)
            a0 = _wrap(agents[0], st)
            a1 = _wrap(agents[1], dict(STATE))  # opp recording descartado
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
            env.run([a0, a1])
            last = env.steps[-1]
            r_c = last[0]["reward"] if label == "P0" else last[1]["reward"]
            for k in st:
                agg[label][k] += st[k]
            per_seed[f"{seed}_{label}"] = {"champ_reward": r_c, **st}
            print(f"seed {seed} {label}: champ_reward={r_c}  ripe_wasted={st['ripe_wheat_wasted']} "
                  f"empty_wasted={st['empty_wheat_wasted']} groups={st['groups_same_tile']} "
                  f"cow_pass_slots={st['cow_pass_slots']}", flush=True)

    print("\n=== AGREGADO (champion por seat) ===")
    for label in ("P0", "P1"):
        S = agg[label]
        print(f"[{label}] unit_turns={S['unit_turns']} move={S['move']} pass={S['pass']} nonmove={S['nonmove']}")
        print(f"   ripe_wheat: any={S['ripe_wheat_any']} wasted(nao-HARVEST)={S['ripe_wheat_wasted']}")
        print(f"   empty_wheat(seeds ok): any={S['empty_wheat_any']} wasted(nao-PLANT)={S['empty_wheat_wasted']} seeds0={S['empty_wheat_seeds0']}")
        print(f"   co-locacao: grupos same-tile>=2 = {S['groups_same_tile']} max={S['max_group']}")
        print(f"   cows: dias={S['cow_days']} fed={S['cow_fed']} cared={S['cow_cared']} "
              f"prod_eve={S['cow_prod_eve_any']} fedprod={S['cow_fedprod']} unfed_prod={S['cow_prod_eve_unfed']} "
              f"uncared_prod={S['cow_prod_eve_uncared']} unfed_risk_days={S['cow_unfed_risk_days']}")
        print(f"   slots cow: pass={S['cow_pass_slots']} feed={S['cow_feed_slots']} care={S['cow_care_slots']}")

    if args.json:
        json.dump({"agg": agg, "per_seed": per_seed}, open(os.path.join(_HERE, args.json), "w"), indent=1)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
