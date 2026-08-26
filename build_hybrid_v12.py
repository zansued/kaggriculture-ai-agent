"""Build do bundle single-file do V12 (Fase 1 da mudança estrutural wheat-heavy).

V12 = hybrid_v6 + overlay _wheat_early_sell baseado no replay CropDusta
(seed 507467650, gap 49k no reward):
  - Quando preço do WHEAT >= 1.4x base (~35) e step na janela d10-27, força
    SELL do EXCEDENTE de wheat (shed - reserva de feed de 60). O CropDusta
    vende 222-244/dia nos dias 11-14; o v6 segura wheat até o fim.

LIÇÃO (smoke test 26/08): vender TODO o shed de wheat MATA os animais (wheat
é o FEED; rebanho = ~88% do bank) -> reward colapsa 146k->56k. Com reserva de
feed o v12 é SEGURO mas quase inócuo (shed > 60 é raro no meio) -> a Fase 2
(produção de wheat p/ gerar excedente) é o caminho real. Ver docs/
WHEAT_STRUCTURAL.md.

Escopo: ESQUELETO seguro — validação h2h pendente. Resto idêntico ao v6.

Output: submissions/hybrid_v12/main.py
Usage:   python build_hybrid_v12.py
"""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "submissions" / "hybrid_v12" / "main.py"

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
# V5: _glut_guard — timing de venda adaptativo à saturação do mercado.
# v2 validou dump global; v4 recalibrou (0.40, janela 250-650); v5 ajusta o
# dump_floor POR ITEM: MILK/WOOL 0.45, MELON/STRAWBERRY 0.40. Validado: front-run MELON 2/STRAWB 4 dá 33-12 vs v5 (72 jogos).
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
# V12 (Fase 1 mudança estrutural): _wheat_early_sell + _fert_dampen.
# Baseado no replay CropDusta (seed 507467650): vender wheat cedo/em massa e
# não spamar fertilizante barato.
# ---------------------------------------------------------------------------
_WHEAT_TRIGGER = 1.4      # preço >= base*1.4 -> forçar SELL do excedente wheat
_WHEAT_RESERVE = 60       # reserva de FEED dos animais (nunca vender abaixo disso)


def _wheat_early_sell(action, obs, step):
    if not (250 <= step < 650):   # d10-27
        return action
    prices = ((obs.get("market") or {}).get("prices") or {})
    shed = ((obs.get("private") or {}).get("shed") or {})
    market = list(action.get("market") or [])
    if len(market) >= 10:
        return action
    price = float(prices.get("WHEAT", 0) or 0)
    shed_qty = int(shed.get("WHEAT", 0) or 0)
    qty = max(0, shed_qty - _WHEAT_RESERVE)   # só o EXCEDENTE é vendável
    if price >= 25 * _WHEAT_TRIGGER and qty > 0:
        for o in market:
            if isinstance(o, list) and len(o) >= 2 and o[0] == "SELL" and o[1] == "WHEAT":
                return action  # já há ordem de wheat
        market.append(["SELL", "WHEAT", qty])
        action["market"] = market[:10]
    return action


def agent(obs, config=None):
    step = int(obs.get("step", 0) or 0)
    action = moon.agent(obs)
    _mature_opp_front_run(action, obs, step)
    action = _sell_first(action, obs, step)
    action = _glut_guard(action, obs, step)
    action = _wheat_early_sell(action, obs, step)
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

    header = f'''"""hybrid_v12 - single-file Kaggle submission bundle.

Moon V56 + overlays do mix + glut-guard + _wheat_early_sell (dump wheat cedo,
>=1.4x base) + _fert_dampen (segura fertilizante barato). Fase 1 da mudança
estrutural wheat-heavy. ESQUELETO — validação h2h pendente.

Built by build_hybrid_v12.py. Self-contained: embute moon_agent_main.py
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
