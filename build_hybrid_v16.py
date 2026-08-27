"""Build do bundle single-file do HÍBRIDO V16: Moon V56 + overlays do mix +
glut-guard v6 + GOOSE/EGG overlay.

V16 = hybrid_v6 + _goose_overlay + _egg_sell:
  - Evidência de W/L (27/08): Crop Dusta (rank 1) usa GOOSE→EGG e venceu
    Subramanya (rank 3) na mesma partida por ~8k. EGG (~50-66) é renda estável
    que não crasha. O Moon conhece GOOSE→COOP mas as fitas kawa só usam
    COW+SHEEP.
  - _goose_overlay: compra 1 GOOSE (BUY_ANIMAL) nos dias 3-10 quando money >
    900 e ainda não há 3 GOOSE na farm. O Moon deve posicionar em COOP.
  - _egg_sell: vende EGG do shed quando preço >= 40.

Validado a fazer: h2h vs v6 (2 lados). NUNCA submeter sem W/L positivo.

Output: submissions/hybrid_v16/main.py
Usage:   python build_hybrid_v16.py
"""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "submissions" / "hybrid_v16" / "main.py"

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


# V5 glut-guard (inalterado)
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
# V16: GOOSE/EGG overlay.
# ---------------------------------------------------------------------------
_GOOSE_DAYS = (3, 10)
_GOOSE_MIN_MONEY = 900
_GOOSE_MAX = 3


def _count_goose(obs):
    farms = obs.get("farms", []) or []
    if not farms:
        return 0
    n = 0
    for row in (farms[0].get("tiles") or []):
        for t in row or []:
            if isinstance(t, dict) and t.get("animal") == "GOOSE":
                n += 1
    return n


def _goose_overlay(action, obs, step):
    day = int(obs.get("day", 0) or 0)
    if not (_GOOSE_DAYS[0] <= day <= _GOOSE_DAYS[1]):
        return action
    farms = obs.get("farms", []) or []
    if not farms:
        return action
    money = float(farms[0].get("money", 0) or 0)
    if money < _GOOSE_MIN_MONEY:
        return action
    if _count_goose(obs) >= _GOOSE_MAX:
        return action
    market = list(action.get("market", []) or [])
    for o in market:
        if isinstance(o, list) and len(o) >= 2 and o[0] == "BUY_ANIMAL" and o[1] == "GOOSE":
            return action
    if len(market) >= 10:
        return action
    market.append(["BUY_ANIMAL", "GOOSE", 1])
    action["market"] = market[:10]
    return action


def _egg_sell(action, obs, step):
    shed = ((obs.get("private") or {}).get("shed") or {})
    egg = int(shed.get("EGG", 0) or 0)
    if egg <= 0:
        return action
    prices = ((obs.get("market") or {}).get("prices") or {})
    ep = float(prices.get("EGG", 0) or 0)
    if ep < 40:
        return action
    market = list(action.get("market", []) or [])
    for o in market:
        if isinstance(o, list) and len(o) >= 2 and o[0] == "SELL" and o[1] == "EGG":
            return action
    if len(market) >= 10:
        return action
    market.append(["SELL", "EGG", egg])
    action["market"] = market[:10]
    return action


def agent(obs, config=None):
    step = int(obs.get("step", 0) or 0)
    action = moon.agent(obs)
    _mature_opp_front_run(action, obs, step)
    action = _sell_first(action, obs, step)
    action = _glut_guard(action, obs, step)
    action = _goose_overlay(action, obs, step)
    action = _egg_sell(action, obs, step)
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

    header = f'''"""hybrid_v16 - single-file Kaggle submission bundle.

Moon V56 + overlays do mix (maturity front-run + order-slot sell-first) +
glut-guard v6 (inalterado) + GOOSE/EGG overlay (compra GOOSE d3-d10, vende
EGG). Evidência de W/L: Crop Dusta usa GOOSE/EGG e venceu Subramanya ~8k.

Built by build_hybrid_v16.py. Self-contained: embute moon_agent_main.py
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
