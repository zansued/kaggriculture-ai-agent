"""Build do bundle single-file do HÍBRIDO V9: Moon V56 + overlays do mix +
glut-guard + overlay de HIRE e coordenação de hands ociosos.

V9 = hybrid_v6 + _hire_and_work:
  1. HIRE: adiciona ordens ["HIRE"] ao market até um teto (18 hands/dia),
     max 2 por turno, respeitando o limite de 10 ordens do market. O custo é
     fibonacci por hand (1,1,2,3,5...); hands resetam a cada dia.
  2. COORDENAÇÃO: para cada hand com ação ["PASS"] (ocioso), atribui tarefa
     útil no tile onde o hand está:
       - tile PLANT (crop) e não regado  -> ["WATER"]
       - tile PASTURE com animal          -> ["CARE"]
     Sem trabalho útil no local -> mantém PASS (seguro).

Motivação (medição 25/08): o Moon NÃO emite HIRE (0 ações) — joga com ~12
hands automáticos do jogo. Tops emitem ~280 HIRE (~10 hands/dia re-contratados).
O Moon tem ~4 hands ociosos por step em média. Hipótese: contratar hands extras
e usá-los em trabalho útil (regar/cuidar) aumenta volume/receita.

Primeira iteração (conservadora): só WATER/CARE no tile atual; sem plantio novo
(complexo, exige sementes/tiles). Iterar se passar.

Output: submissions/hybrid_v9/main.py
Usage:   python build_hybrid_v9.py
"""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "submissions" / "hybrid_v9" / "main.py"

_MIX_OVERPRELUDE = '''\
# ---------------------------------------------------------------------------
# Overlays do mix_agent (validados) — injetados sobre a base Moon.
# ---------------------------------------------------------------------------
_OPP_THRESH = {"STRAWBERRY": 4, "MELON": 2, "MILK": 4, "WOOL": 3}
_OPP_MAX_DAY = {"STRAWBERRY": 10, "MELON": 12}
_FRONT_FIRST_ITEMS = ("MELON", "STRAWBERRY", "MILK", "WOOL")


def _mature_opp_front_run(action, obs, step):
    farms = obs.get("farms", [])
    if len(farms) < 2:
        return
    tiles = farms[1].get("tiles", []) or []
    day = int(obs.get("day", 0) or 0)
    prod = {"STRAWBERRY": 0, "MELON": 0, "MILK": 0, "WOOL": 0}
    for row in tiles:
        for t in row:
            if not isinstance(t, dict):
                continue
            if t.get("kind") == "PLANT":
                c = t.get("crop")
                if c in ("STRAWBERRY", "MELON"):
                    age = day - int(t.get("planted_day", day))
                    if age >= _OPP_MAX_DAY[c] - 2 and int(t.get("yield_units", 0) or 0) > 0:
                        prod[c] += 1
            elif t.get("animal"):
                p = {"COW": "MILK", "SHEEP": "WOOL"}.get(t["animal"])
                if p and int(t.get("yield_units", 0) or 0) > 0:
                    prod[p] += 1
    orders = list(action.get("market", []) or [])
    if len(orders) >= 10:
        return
    already = set()
    for o in orders:
        if isinstance(o, list) and len(o) >= 2 and o[0] == "SELL":
            already.add(o[1])
    shed = (obs.get("private") or {}).get("shed") or {}
    for item, thresh in _OPP_THRESH.items():
        if prod.get(item, 0) >= thresh and item not in already and int(shed.get(item, 0) or 0) > 0 and len(orders) < 10:
            orders.append(["SELL", item, int(shed.get(item, 0) or 0)])
            already.add(item)
    action["market"] = orders[:10]


def _sell_first(action, obs, step):
    market = list(action.get("market", []) or [])
    sells = []
    others = []
    for o in market:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
            sells.append(o)
        else:
            others.append(o)
    sells.sort(key=lambda o: (o[1] not in _FRONT_FIRST_ITEMS, -(o[2] or 0)))
    action["market"] = (sells + others)[:10]
    return action


# ---------------------------------------------------------------------------
# V5/V6: _glut_guard — timing de venda adaptativo à saturação do mercado.
# ---------------------------------------------------------------------------
_GBASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
          "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}
_GRISERS = ("WHEAT", "CARROT", "TOMATO")
_GHOLD = 0.5
_GRISE_MULT = 1.3
_GDUMP = ("MILK", "WOOL", "MELON", "STRAWBERRY")
_GD_FLOOR = {"MILK": 0.45, "WOOL": 0.45, "MELON": 0.40, "STRAWBERRY": 0.40}
_GSTART = 250
_GSTOP = 650


def _floor_of(item):
    return _GD_FLOOR.get(item, 0.45) if isinstance(_GD_FLOOR, dict) else _GD_FLOOR


def _glut_guard(action, obs, step):
    if not (_GSTART <= step < _GSTOP):
        return action
    market = list(action.get("market", []) or [])
    if not market:
        return action
    prices = ((obs.get("market") or {}).get("prices") or {})
    shed = ((obs.get("private") or {}).get("shed") or {})
    new_market = []
    for o in market:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] in _GBASE:
            item = o[1]
            qty = int(o[2] or 0)
            if qty <= 0:
                continue
            price = float(prices.get(item, 0) or 0)
            base = _GBASE[item]
            if item in _GRISERS and price > 0 and price < base * _GRISE_MULT:
                keep = max(1, int(qty * _GHOLD))
                new_market.append(["SELL", item, keep])
            elif item in _GDUMP and price >= base * _floor_of(item):
                avail = int(shed.get(item, 0) or 0)
                if avail > 0:
                    new_market.append(["SELL", item, max(qty, avail)])
                else:
                    new_market.append(o)
            else:
                new_market.append(o)
        else:
            new_market.append(o)
    action["market"] = new_market[:10]
    return action


# ---------------------------------------------------------------------------
# V9: _hire_and_work — contratar hands extras (HIRE no market) e dar trabalho
# aos hands ociosos (tarefas no tile atual).
# ---------------------------------------------------------------------------
_HIRE_MAX = 18           # teto de hands por dia
_HIRE_MAX_PER_TURN = 2   # max ordens HIRE por turno
_HIRE_LAST_DAY = 24      # para de contratar no dia 24+ (custo alto, retorno baixo)


def _task_for_tile(tile):
    if not isinstance(tile, dict):
        return None
    kind = tile.get("kind")
    if kind == "PLANT" and not tile.get("watered"):
        return ["WATER"]
    if tile.get("animal"):
        return ["CARE"]
    return None


def _hire_and_work(action, obs, step):
    action = dict(action)
    farms = obs.get("farms", [])
    if len(farms) < 2:
        return action
    seat = 1 if int(obs.get("player", 0) or 0) == 1 else 0
    farm = farms[seat] if seat < len(farms) else {}
    day = int(obs.get("day", 0) or 0)
    hands = farm.get("hands") or []
    n_hands = len(hands)
    hires_today = int(farm.get("hires_today", 0) or 0)

    # 1) HIRE via market orders
    if day <= _HIRE_LAST_DAY and n_hands < _HIRE_MAX and hires_today < _HIRE_MAX:
        market = list(action.get("market") or [])
        slots = 10 - len(market)
        to_hire = min(_HIRE_MAX_PER_TURN, _HIRE_MAX - n_hands,
                      _HIRE_MAX - hires_today, slots)
        for _ in range(max(0, to_hire)):
            market.append(["HIRE"])
        action["market"] = market[:10]

    # 2) Coordenar hands ociosos
    hand_cmds = list(action.get("hands") or [])
    if hand_cmds and n_hands > 0:
        tiles = farm.get("tiles") or []
        for i in range(min(len(hand_cmds), n_hands)):
            cmd = hand_cmds[i]
            is_pass = (cmd is None or (isinstance(cmd, list) and cmd and cmd[0] == "PASS"))
            if not is_pass:
                continue
            pos = hands[i] if i < len(hands) else None
            if not pos or not tiles:
                continue
            try:
                tile = tiles[pos[0]][pos[1]]
            except Exception:
                continue
            task = _task_for_tile(tile)
            if task:
                hand_cmds[i] = task
        action["hands"] = hand_cmds
    return action


def agent(obs, config=None):
    step = int(obs.get("step", 0) or 0)
    action = moon.agent(obs)
    _mature_opp_front_run(action, obs, step)
    action = _sell_first(action, obs, step)
    action = _glut_guard(action, obs, step)
    action = _hire_and_work(action, obs, step)
    return action
'''


def _blob(path: Path) -> str:
    src = path.read_text(encoding="utf-8")
    idx = src.find("if __name__")
    if idx > 0:
        src = src[:idx]
    return base64.b85encode(zlib.compress(src.encode("utf-8"))).decode("utf-8")


def build() -> None:
    moon_src = ROOT / "research" / "public" / "moon_agent_main.py"
    moon_b = _blob(moon_src)

    header = f'''"""hybrid_v9 - single-file Kaggle submission bundle.

Moon V56 + overlays do mix + glut-guard + HIRE e coordenação de hands ociosos
(WATER/CARE). Tetos: _HIRE_MAX=18, max 2 HIRE/turno.

Built by build_hybrid_v9.py. Self-contained: embute moon_agent_main.py
(zlib+base85) e injeta os overlays inline.
"""
from __future__ import annotations

import base64
import types
import zlib

_MOON_B85 = {moon_b!r}


def _load(blob, modname):
    code = zlib.decompress(base64.b85decode(blob)).decode("utf-8")
    ns = types.ModuleType(modname)
    ns.__file__ = modname + ".py"
    exec(compile(code, modname + ".py", "exec"), ns.__dict__)
    return ns


moon = _load(_MOON_B85, "moon_agent_main")
'''

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(header + _MIX_OVERPRELUDE, encoding="utf-8")
    print(f"OK -> {OUT} ({OUT.stat().st_size} bytes)")
    print(f"    moon blob: {len(moon_b)} chars")


if __name__ == "__main__":
    build()
