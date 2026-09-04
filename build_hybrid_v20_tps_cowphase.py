"""Build do v20_tps_cowphase sobre o champion hybrid_v19 (por-item).

Estratégia (PESQUISA_DEEP3_04SET): NÃO trocar o Moon. Preservar a fita como
routing e transformar action slots estacionários/semanticamente-noop em
micro-transações completas, com posição preservada e zero HIRE.

O que o v20 adiciona AO v19 (que permanece intacto, incluindo market overlays):
  1) CLOCK-0: obs['step'] = day*24 + hour (fonte canônica p/ P0 e P1; o stock
     1.32.7 não propaga 'step' ao seat 1 -> Moon indexaria actions[0] sempre).
  2) Cow Phase-Locked CARE: em worker parado (PASS) sobre COW já alimentada
     (fed_today=True) e ainda não cuidada (cared_today=False), troca por CARE.
     O engine só faz bank de +1 pending_care_bonus no EOD se fed&care -> adiciona
     +1 MILK no próximo tick produtivo. Custo: zero (não move, não gasta item).
  3) TPS-crop replant same-day: detecta tile de WHEAT que o Moon colheu hoje
     (memória: estava com PLANT WHEAT na obs anterior e agora está vazio). Se 2+
     workers co-localizados no tile com comando PASS, o de menor índice vira
     PLANT WHEAT e o de maior índice vira WATER (mesmo turno -> water garantido
     antes do EOD, planta não vira WEED). Fecha o day-slip sem MOVE.

Build lê submissions/hybrid_v19/main.py (champion já construído) e anexa o
overlay, emitindo submissions/hybrid_v20_tps_cowphase/main.py.

Uso:
    python build_hybrid_v20_tps_cowphase.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "submissions" / "hybrid_v19" / "main.py"
OUT = ROOT / "submissions" / "hybrid_v20_tps_cowphase" / "main.py"

_OVERLAY = '''\
# ---------------------------------------------------------------------------
# v20_tps_cowphase — overlays posicionais sobre o champion v19.
# Adicionados APÓS o v19; o agente final redefine agent() e delega ao base.
# ---------------------------------------------------------------------------
_MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}
_V20_MAX_STEP = 700          # não intervir na liquidação terminal do Moon
_V20_MAX_REPLANT = 8         # teto de replants por dia (segurança)

_MEM = {}  # seat -> {"last": {(x,y): crop}, "harv": {(x,y): day}, "day": int}


def _v20_step(obs):
    return int(obs.get("day", 0) or 0) * 24 + int(obs.get("hour", 0) or 0)


def _v20_seat(obs):
    return 1 if int(obs.get("player", 0) or 0) == 1 else 0


def _v20_farm(obs):
    farms = list(obs.get("farms", []) or [])
    s = _v20_seat(obs)
    return farms[s] if s < len(farms) else {}


def _v20_tile(farm, x, y):
    try:
        return (farm.get("tiles") or [])[y][x]
    except Exception:
        return "LOCKED"


def _v20_plant_map(farm):
    out = {}
    for y, row in enumerate(farm.get("tiles") or []):
        for x, t in enumerate(row):
            if isinstance(t, dict) and t.get("kind") == "PLANT":
                out[(x, y)] = t.get("crop")
    return out


def _v20_worker_overlay(obs, action):
    step = _v20_step(obs)
    if step == 0:
        _MEM.clear()
    if not (20 <= step < _V20_MAX_STEP):
        return action
    seat = _v20_seat(obs)
    farm = _v20_farm(obs)
    if not farm:
        return action
    day = int(obs.get("day", 0) or 0)

    tiles = farm.get("tiles") or []
    farmer = list(farm.get("farmer") or [0, 0])
    hands = [list(p) for p in (farm.get("hands") or [])]
    pos = [farmer, *hands]

    ua = [list(action.get("farmer") or ["PASS"])]
    ua += [list(h or ["PASS"]) for h in (action.get("hands") or [])]
    if len(ua) < len(pos):
        ua += [["PASS"]] * (len(pos) - len(ua))
    ua = ua[:len(pos)]

    private = obs.get("private") or {}
    seeds = private.get("seeds", {}) if hasattr(private, "get") else {}
    if seeds is None or not hasattr(seeds, "get"):
        seeds = {}

    mem = _MEM.setdefault(seat, {"last": {}, "harv": {}, "day": -1})
    cur = _v20_plant_map(farm)
    # detecta colheitas de WHEAT ocorridas desde a obs anterior (mesmo dia)
    if mem.get("day") == day and mem.get("last"):
        for (x, y), c in mem["last"].items():
            if c == "WHEAT" and (x, y) not in cur and mem["harv"].get((x, y)) != day:
                # tile saiu de PLANT WHEAT -> colhido/decaiu hoje
                if _v20_tile(farm, x, y) is None:
                    mem["harv"][(x, y)] = day
    # limpa harv antigos
    for k in [k for k, d in mem["harv"].items() if d != day]:
        del mem["harv"][k]
    mem["last"] = cur
    mem["day"] = day

    # ---- TPS-crop: replant same-day de WHEAT recém-colhido ----
    demand = sum(
        1 for a in ua if isinstance(a, list) and len(a) >= 2 and a[0] == "PLANT" and a[1] == "WHEAT"
    )
    seed_ok = int(seeds.get("WHEAT", 0) or 0) > demand
    by_tile = {}
    for i, p in enumerate(pos):
        try:
            k = (int(p[0]), int(p[1]))
        except Exception:
            continue
        by_tile.setdefault(k, []).append(i)
    did_replant = 0
    for (x, y), idxs in by_tile.items():
        if did_replant >= _V20_MAX_REPLANT:
            break
        if (x, y) not in mem["harv"] or mem["harv"][(x, y)] != day:
            continue
        if _v20_tile(farm, x, y) is not None:
            continue
        if not seed_ok:
            continue
        passers = [i for i in idxs if ua[i] and ua[i][0] == "PASS"]
        if len(passers) < 2:
            continue
        planter = min(passers)
        water_cands = [i for i in passers if i > planter]
        if not water_cands:
            continue
        waterer = min(water_cands)
        ua[planter] = ["PLANT", "WHEAT"]
        ua[waterer] = ["WATER"]
        demand += 1
        seed_ok = int(seeds.get("WHEAT", 0) or 0) > demand
        did_replant += 1
        # tile já foi replantado hoje; remove para não repetir
        del mem["harv"][(x, y)]

    # ---- Cow Phase-Locked CARE (slots PASS sobre COW alimentada) ----
    for i, p in enumerate(pos):
        if i >= len(ua):
            break
        cmd = ua[i] or ["PASS"]
        verb = cmd[0] if cmd else "PASS"
        if verb in _MOVES or verb != "PASS":
            continue
        try:
            x, y = int(p[0]), int(p[1])
            t = tiles[y][x]
        except Exception:
            continue
        if not (isinstance(t, dict) and t.get("animal") == "COW"):
            continue
        # CARE é inócuo (não move, não gasta item) e só ajuda: se a vaca estiver
        # alimentada no EOD, o CARE banqueia +1 pending para o próximo tick;
        # se não estiver, não há custo. Garante nunca perder noite produtiva.
        if not t.get("cared_today", False):
            ua[i] = ["CARE"]

    action["farmer"] = ua[0]
    action["hands"] = ua[1:]
    return action


_BASE_AGENT_V20 = agent


def agent(obs, config=None):
    # CLOCK-0: fonte canônica de tempo para Moon e todos os overlays (P0 e P1).
    obs["step"] = int(obs.get("day", 0) or 0) * 24 + int(obs.get("hour", 0) or 0)
    action = _BASE_AGENT_V20(obs, config)
    try:
        action = _v20_worker_overlay(obs, action)
    except Exception:
        pass  # overlay nunca deve derrubar o agente
    return action
'''


def build() -> None:
    if not SRC.exists():
        raise SystemExit(f"base v19 não encontrado: {SRC}")
    src = SRC.read_text(encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(src.rstrip() + "\n" + _OVERLAY, encoding="utf-8")
    print(f"OK -> {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
