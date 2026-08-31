"""Build do bundle single-file do HÍBRIDO V19 (BUY_PRODUCT WHEAT cedo, sobre o V17):
Moon V56 (com _v35 GOOSE expandido + _v17_feed_guard) + overlays do mix +
glut-guard v17 (inalterado) + compra de WHEAT barato nos primeiros 12 dias.

V17 = campeão (57W-37L vs v6). V19 = V17 + _buy_wheat_early CONSERVADOR.

Contexto:
- v15 (BUY_PRODUCT WHEAT cedo sobre o v6, SEM feed_guard) foi REFUTADO: 1-7,
  média -11.348. A compra gastava o cash do ramp-up do Moon.
- O V17 adicionou o _v17_feed_guard, que usa WHEAT do shed para alimentar
  animais (FEED). Hipótese v19: comprar WHEAT barato d0-d12 abastece o
  feed_guard, evitando animais famintos/mortos — benefício que o v15 não tinha.
- Parâmetros MAIS conservadores que o v15: money mínimo 1500 (vs 800), qty 3
  (vs 5), reserva alvo < 10 (vs 15). Compra só quando há folga real de caixa.

Validado (a preencher): v19 vs v17, h2h 2 lados, seeds 1-36.
Output: submissions/hybrid_v19/main.py
Usage:   python build_hybrid_v19.py
"""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "submissions" / "hybrid_v19" / "main.py"

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
# V19: _buy_wheat_early — compra WHEAT barato nos primeiros 12 dias para
# abastecer o feed_guard do v17. Parâmetros conservadores (money alto, qty
# pequena, reserva baixa) para NÃO quebrar o cash do ramp-up (lição do v15).
# ---------------------------------------------------------------------------
_BUY_LAST_STEP = 300   # até ~d12
_BUY_MAX_PRICE = 32    # wheat barato
_BUY_MIN_MONEY = 1500  # folga real de caixa (v15 usava 800 e quebrava ramp-up)
_BUY_QTY = 3
_BUY_SHED_CAP = 10     # reserva de WHEAT no shed abaixo da qual compra


def _buy_wheat_early(action, obs, step):
    step = int(step or 0)
    if step >= _BUY_LAST_STEP:
        return action
    prices = ((obs.get("market") or {}).get("prices") or {})
    wp = float(prices.get("WHEAT", 0) or 0)
    if wp <= 0 or wp >= _BUY_MAX_PRICE:
        return action
    farms = obs.get("farms") or []
    money = None
    if farms:
        money = farms[0].get("money")
    if money is None or money < _BUY_MIN_MONEY:
        return action
    shed = ((obs.get("private") or {}).get("shed") or {})
    if int(shed.get("WHEAT", 0) or 0) > _BUY_SHED_CAP:
        return action
    market = list(action.get("market", []) or [])
    for o in market:
        if isinstance(o, list) and len(o) >= 2 and o[0] == "BUY_PRODUCT" and o[1] == "WHEAT":
            return action
    if len(market) >= 10:
        return action
    market.append(["BUY_PRODUCT", "WHEAT", _BUY_QTY])
    action["market"] = market[:10]
    return action


def agent(obs, config=None):
    step = int(obs.get("step", 0) or 0)
    action = moon.agent(obs)
    _mature_opp_front_run(action, obs, step)
    action = _sell_first(action, obs, step)
    action = _glut_guard(action, obs, step)
    action = _buy_wheat_early(action, obs, step)
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

    header = f'''"""hybrid_v19 - single-file Kaggle submission bundle.

Moon V56 (com _v35 GOOSE expandido + _v17_feed_guard) + overlays do mix +
glut-guard v17 (inalterado) + _buy_wheat_early (compra WHEAT barato d0-d12
para abastecer o feed_guard). V17 + compra conservadora de WHEAT.

Built by build_hybrid_v19.py. Self-contained: embute moon_v17_goose.py
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
