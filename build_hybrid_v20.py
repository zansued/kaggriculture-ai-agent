"""Build do bundle single-file do HÍBRIDO V20 (TOMATO tardio, sobre o V17):
Moon V56 (com _v35 GOOSE expandido + _v17_feed_guard) + overlays do mix +
glut-guard v17 (inalterado) + _tomato_late (planta TOMATO d10-d16).

V17 = campeão. Análise empírica (29/08): o v17 já planta CARROT tardio
(d22-27), mas NÃO planta NADA de TOMATO. Os tops (tetsuya/Blu3s) plantam
TOMATO d11-12 e vendem d21-24; o preço do TOMATO sobe 60 -> 147 no fim.

Mecânica: TOMATO seed=50, first_yield d8, colheita contínua (interval 1d),
max_yield=4, ongoing. Plantado d10-16 -> matura d18-24 -> colhe até o d29
com o preço subindo.

Implementação (segura para a coordenação do Moon):
- _tomato_late TROCA até _TOM_MAX ordens PLANT WHEAT por PLANT TOMATO nos
  dias 10-16, mantendo a MESMA unidade/tile — não desloca hands nem quebra
  o plano de movimento (o hand vai ao mesmo tile e planta TOMATO).
- Garante BUY_SEED TOMATO no market (custo 50) quando vai trocar.
- Limite de 4 tiles de TOMATO p/ não comprometer o FEED dos animais (o Moon
  mantém ~40+ tiles de wheat; 4 a menos é ~10%).

Validado (a preencher): v20 vs v17, h2h 2 lados, seeds 1-36.
Output: submissions/hybrid_v20/main.py
Usage:   python build_hybrid_v20.py
"""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "submissions" / "hybrid_v20" / "main.py"

_MIX_OVERPRELUDE = '''\
# ---------------------------------------------------------------------------
# Overlays do mix_agent (validados) — injetados sobre a base Moon.
# _mature_opp_front_run (vende quando produção do oponente está madura) e
# _sell_first (order-slot: premium sells antes, piorando o preço do oponente).
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
# V5 glut-guard (ótimo local do v17) — INALTERADO.
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
# V20: _tomato_late — planta TOMATO d10-d16 trocando alguns PLANT WHEAT do
# próprio Moon (mesma unidade/tile, sem deslocar coordenação). Garante seed.
# ---------------------------------------------------------------------------
_TOM_DAY_LO = 10
_TOM_DAY_HI = 16
_TOM_MAX = 4          # máx tiles de TOMATO no total (protege FEED do wheat)
_TOM_SEED_MIN = 1


def _tomato_late(action, obs, step):
    day = int(obs.get("day", 0) or 0)
    if not (_TOM_DAY_LO <= day <= _TOM_DAY_HI):
        return action
    farm = obs.get("farms", [{}])[0]
    tiles = farm.get("tiles", []) or []
    n_tom = sum(1 for row in tiles for t in row
                if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == "TOMATO")
    if n_tom >= _TOM_MAX:
        return action

    # troca PLANT WHEAT -> PLANT TOMATO (nas ordens farmer + hands)
    farmer = list(action.get("farmer") or ["PASS"])
    hands = [list(h or ["PASS"]) for h in (action.get("hands") or [])]
    changed = False
    for order in [farmer, *hands]:
        if n_tom >= _TOM_MAX:
            break
        if isinstance(order, list) and len(order) >= 2 and order[0] == "PLANT" and order[1] == "WHEAT":
            order[1] = "TOMATO"
            n_tom += 1
            changed = True
    if changed:
        action["farmer"] = farmer
        action["hands"] = hands

    # garante pelo menos 1 seed de TOMATO no mercado
    seeds = ((obs.get("private") or {}).get("seeds") or {})
    if int(seeds.get("TOMATO", 0) or 0) < _TOM_SEED_MIN:
        market = list(action.get("market") or [])
        has = any(isinstance(m, list) and len(m) >= 2 and m[0] == "BUY_SEED" and m[1] == "TOMATO"
                  for m in market)
        if not has and len(market) < 10:
            market.append(["BUY_SEED", "TOMATO", 1])
            action["market"] = market[:10]
    return action


def agent(obs, config=None):
    step = int(obs.get("step", 0) or 0)
    action = moon.agent(obs)
    _mature_opp_front_run(action, obs, step)
    action = _sell_first(action, obs, step)
    action = _glut_guard(action, obs, step)
    action = _tomato_late(action, obs, step)
    return action
'''


def _blob(path: Path) -> str:
    src = path.read_text(encoding="utf-8")
    idx = src.find("if __name__")
    if idx > 0:
        src = src[:idx]
    return base64.b85encode(zlib.compress(src.encode("utf-8"))).decode("utf-8")


def build() -> None:
    moon_src = ROOT / "research" / "public" / "moon_v17_goose.py"
    moon_b = _blob(moon_src)

    header = f'''"""hybrid_v20 - single-file Kaggle submission bundle.

Moon V56 (com _v35 GOOSE expandido + _v17_feed_guard) + overlays do mix +
glut-guard v17 (inalterado) + _tomato_late (planta TOMATO d10-d16 trocando
4 PLANT WHEAT do próprio Moon). Captura a valorização do TOMATO no fim.

Built by build_hybrid_v20.py. Self-contained: embute moon_v17_goose.py
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
