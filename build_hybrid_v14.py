"""Build do bundle single-file do HÍBRIDO V14: Moon V56 + overlays do mix +
glut-guard com VENDA FRACIONADA para perecíveis.

V14 = hybrid_v6 + fracionamento de venda no _GDUMP:
  - O v6, quando price >= piso, esvazia TODO o shed de uma vez
    (max(qty, avail)). Isso derruba o preço na mesma ordem e captura um único
    preço. Os top agents (Crop Dusta, Ryo, tetsuya, Blu3s) vendem em LOTES
    PEQUENOS e FREQUENTES (MELON:6, MELON:12, 10-40 ordens/dia) — capturam
    preço médio melhor na descida e espalham o impacto de mercado.
  - V14 vende a quantidade que o Moon pediu (qty), limitada ao shed, quando o
    preço está acima do piso — o resto fica para as próximas janelas. Se o
    preço crashar, o _mature_opp_front_run e o próprio Moon continuam tentando
    vender.

Validado a fazer: h2h vs v6 (2 lados). NUNCA submeter sem W/L positivo.

Estrutura: embute research/public/moon_agent_main.py (stdlib-only) como blob
zlib+base85, e injeta inline os overlays do mix_agent (mature_opp_front_run,
sell_first) MAIS o _glut_guard com venda fracionada.

Output: submissions/hybrid_v14/main.py
Usage:   python build_hybrid_v14.py
"""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "submissions" / "hybrid_v14" / "main.py"

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
# V14: _glut_guard — dump_floor por item + VENDA FRACIONADA.
# Quando price >= piso (base*floor), vende a qtd pedida pelo Moon limitada ao
# shed (fraciona em vez de esvaziar tudo). Grãos continuam segurando 50% se
# baratos (igual v6).
# ---------------------------------------------------------------------------
_GBASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
          "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}
_GRISERS = ("WHEAT", "CARROT", "TOMATO")
_GDUMP = ("MILK", "WOOL", "MELON", "STRAWBERRY")
_GD_FLOOR = {"MILK": 0.45, "WOOL": 0.45, "MELON": 0.40, "STRAWBERRY": 0.40}
_GRISE_KEEP = 0.5          # grãos: segurar 50% enquanto barato
_GRISE_MULT = 1.3          # grãos: segura se price < base*1.3
# fração do shed vendida por janela para perecíveis (<= 0 => usa qty do Moon)
_GFRAC = 0.55
_GSTART = 250
_GSTOP = 650


def _glut_guard(action, obs, step):
    step = int(step or 0)
    if not (_GSTART <= step < _GSTOP):
        return action
    market = list(action.get("market", []) or [])
    if not market:
        return action
    prices = ((obs.get("market") or {}).get("prices") or {})
    shed = ((obs.get("private") or {}).get("shed") or {})
    new_market = []
    for o in market:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
            item = o[1]
            qty = int(o[2] or 0)
            if qty <= 0:
                continue
            if item in _GRISERS or item in _GDUMP:
                price = float(prices.get(item, 0) or 0)
                if price <= 0:
                    new_market.append(o)
                    continue
                base = _GBASE[item]
                if item in _GDUMP:
                    if price >= base * _GD_FLOOR.get(item, 0.40):
                        avail = int(shed.get(item, 0) or 0)
                        if avail > 0:
                            # venda fracionada: vende fração do shed por janela
                            sell = int(avail * _GFRAC) if _GFRAC > 0 else qty
                            sell = max(min(sell, avail), 1)
                            new_market.append(["SELL", item, sell])
                        else:
                            new_market.append(o)
                    else:
                        new_market.append(o)
                else:
                    # grãos: igual v6
                    if price < base * _GRISE_MULT:
                        keep = max(1, int(qty * _GRISE_KEEP))
                        new_market.append(["SELL", item, keep])
                    else:
                        new_market.append(o)
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

    header = f'''"""hybrid_v14 - single-file Kaggle submission bundle.

Moon V56 + overlays do mix (maturity front-run + order-slot sell-first) +
glut-guard com VENDA FRACIONADA (perecíveis vendem em frações do shed por
janela, capturando preço médio melhor, em vez de esvaziar tudo de uma vez).

Built by build_hybrid_v14.py. Self-contained: embute moon_agent_main.py
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
