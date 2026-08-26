"""Build do bundle single-file do HÍBRIDO V11: Moon V56 + overlays do mix +
glut-guard + overlay ADAPTATIVO price-trend (tendência de preço dia-a-dia).

V11 = hybrid_v6 + _price_trend:
  - Mantém memória do preço de cada item no início do dia (por seat, resetado
    no step 0 do episódio).
  - Quando o dia muda, calcula a variação % dia-a-dia de cada item.
  - SATURAÇÃO (preço caiu >=15%): dump TOTAL de MELON/STRAWB/MILK/WOOL
    (vender todo o shed antes do colapso) — reage a padrões reais, não a
    thresholds fixos por step (v7/v10 já provaram que fixo não funciona).
  - ALTA (preço subiu >=10%): segurar MAIS WHEAT/CARROT/TOMATO (vender só 25%)
    para aproveitar a subida.
  - Estável: comportamento do v6.

Diff qualitativo: usa DERIVADA de preço observada (informação nova), não nível
fixo nem step. Resto idêntico ao v6.

Output: submissions/hybrid_v11/main.py
Usage:   python build_hybrid_v11.py
"""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "submissions" / "hybrid_v11" / "main.py"

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
# V11: _price_trend — reage a padrões de preço reais (tendência dia-a-dia).
# Memória por seat, resetada no step 0 do episódio.
# ---------------------------------------------------------------------------
_PT_STATE = {0: {"prev": {}, "day": -1}, 1: {"prev": {}, "day": -1}}
_PT_DUMP_DROP = -0.15      # saturação: preço caiu >=15% -> dump total
_PT_HOLD_RISE = 0.10       # alta: preço subiu >=10% -> segurar grisers mais
_PT_HOLD_KEEP = 0.25       # fração a vender quando em alta


def _price_trend(action, obs, step):
    if step == 0:
        _PT_STATE[0] = {"prev": {}, "day": -1}
        _PT_STATE[1] = {"prev": {}, "day": -1}
    farms = obs.get("farms", [])
    if len(farms) < 2:
        return action
    seat = 1 if int(obs.get("player", 0) or 0) == 1 else 0
    day = int(obs.get("day", 0) or 0)
    prices = ((obs.get("market") or {}).get("prices") or {})
    st = _PT_STATE[seat]

    trend = {}
    if st["day"] >= 0 and day != st["day"] and st["prev"]:
        for item, prev in st["prev"].items():
            cur = prices.get(item)
            if isinstance(cur, (int, float)) and prev and cur:
                trend[item] = (cur - prev) / prev
    st["day"] = day
    if prices:
        st["prev"] = dict(prices)

    if not trend:
        return action

    market = list(action.get("market") or [])
    shed = ((obs.get("private") or {}).get("shed") or {})
    new_market = []
    for o in market:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] in trend:
            item = o[1]
            t = trend[item]
            qty = int(o[2] or 0)
            if item in ("MELON", "STRAWBERRY", "MILK", "WOOL") and t <= _PT_DUMP_DROP:
                avail = int(shed.get(item, 0) or 0)
                if avail > 0:
                    new_market.append(["SELL", item, max(qty, avail)])
                else:
                    new_market.append(o)
            elif item in ("WHEAT", "CARROT", "TOMATO") and t >= _PT_HOLD_RISE:
                keep = max(1, int(qty * _PT_HOLD_KEEP))
                new_market.append(["SELL", item, keep])
            else:
                new_market.append(o)
        else:
            new_market.append(o)
    action["market"] = new_market[:10]
    return action


def agent(obs, config=None):
    step = int(obs.get("step", 0) or 0)
    action = moon.agent(obs)
    _mature_opp_front_run(action, obs, step)
    action = _sell_first(action, obs, step)
    action = _glut_guard(action, obs, step)
    action = _price_trend(action, obs, step)
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

    header = f'''"""hybrid_v11 - single-file Kaggle submission bundle.

Moon V56 + overlays do mix (maturity front-run + order-slot sell-first) +
glut-guard + overlay ADAPTATIVO price-trend (tendência dia-a-dia: dump total
em saturação >=15%, segurar grisers em alta >=10%).

Built by build_hybrid_v11.py. Self-contained: embute moon_agent_main.py
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
