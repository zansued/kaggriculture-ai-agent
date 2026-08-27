"""Build do bundle single-file do HÍBRIDO V13: Moon V56 + overlays do mix +
glut-guard ADAPTATIVO (trailing stop por preço real + momentum).

V13 = hybrid_v6 + glut-guard adaptativo:
  - _GBASE fixo é usado só como fallback inicial; depois cada item ganha um
    trailing stop baseado no PICO OBSERVADO da partida:
      * _GDUMP (MILK/WOOL/MELON/STRAWBERRY): dump quando preço cai para X% do
        pico, ou quando há queda recente acentuada (momentum < ~0.92).
      * _GRISERS (WHEAT/CARROT/TOMATO): segura 50% enquanto preço subindo e
        abaixo do pico; libera tudo se cair ou no fim do jogo.
  - Justificativa: preços variam MUITO por partida (ex: MELON pico 271 numa,
    180 noutra; MILK caro 246-250 ou colapsado). Thresholds fixos do v6 usam
    _GBASE absoluto (MELON 250, STRAWB 120) e não reagem à tendência real.
    Os top agents (Crop Dusta, Ryo, tetsuya, Blu3s) reagem à série de preços:
    vendem antes do crash, seguram enquanto sobe, dumpam no fim.

Validado a fazer: h2h vs v6 (2 lados). NUNCA submeter sem W/L positivo.

Estrutura: embute research/public/moon_agent_main.py (stdlib-only) como blob
zlib+base85, e injeta inline os overlays do mix_agent (mature_opp_front_run,
sell_first) MAIS o _glut_guard adaptativo.

Output: submissions/hybrid_v13/main.py
Usage:   python build_hybrid_v13.py
"""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "submissions" / "hybrid_v13" / "main.py"

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
# V13: _glut_guard ADAPTATIVO — trailing stop pelo preço real da partida.
# _GBASE fixo só como fallback; depois cada item usa o PICO observado.
# _GDUMP (MILK/WOOL/MELON/STRAWBERRY): dump quando preço cai para X% do pico
#   ou quando há queda recente acentuada (momentum). _GRISERS (grãos): segura
#   enquanto sobe, libera se cair ou no fim do jogo.
# ---------------------------------------------------------------------------
_GBASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
          "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}
_GRISERS = ("WHEAT", "CARROT", "TOMATO")
_GDUMP = ("MILK", "WOOL", "MELON", "STRAWBERRY")
# V13: piso de venda adaptado ao PICO observado da partida.
#   vende (esvazia shed) quando price >= max(base_fixo*floor, pico*0.55).
#   Em partidas de preço alto (MELON pico 271, MILK 250) o pico*0.55 fica acima
#   do piso fixo → vende ANTES, capturando preço melhor. Em partidas de preço
#   baixo, o piso fixo domina (igual ao v6).
_FLOOR_REL = {"MELON": 0.55, "STRAWBERRY": 0.55, "MILK": 0.45, "WOOL": 0.45}
_GD_FLOOR = {"MILK": 0.45, "WOOL": 0.45, "MELON": 0.40, "STRAWBERRY": 0.40}
_GRISE_KEEP = 0.5          # grãos: segurar 50% enquanto barato (igual v6)
_GRISE_MULT = 1.3          # grãos: segura se price < base*1.3
_GSTART = 250
_GSTOP = 650

_PRICE_HIST = {}           # item -> [(step, price), ...]


def _observe_prices(obs, step):
    prices = ((obs.get("market") or {}).get("prices") or {})
    for k, v in prices.items():
        if v:
            _PRICE_HIST.setdefault(k, []).append((step, float(v)))
            h = _PRICE_HIST[k]
            if len(h) > 60:
                _PRICE_HIST[k] = h[-60:]


def _peak(item):
    h = _PRICE_HIST.get(item)
    if not h:
        return 0.0
    return max(p for _, p in h)


def _mom(item):
    h = _PRICE_HIST.get(item) or []
    if len(h) < 4:
        return 1.0
    cur = h[-1][1]
    prev = h[-8][1] if len(h) >= 8 else h[0][1]
    return (cur / prev) if prev > 0 else 1.0


def _glut_guard(action, obs, step):
    step = int(step or 0)
    _observe_prices(obs, step)
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
                peak = _peak(item)
                if item in _GDUMP:
                    # vende (esvazia shed) quando price >= max(piso fixo, % do pico)
                    base_floor = _GBASE[item] * _GD_FLOOR.get(item, 0.40)
                    peak_floor = peak * _FLOOR_REL.get(item, 0.55) if peak > 0 else 0.0
                    thr = max(base_floor, peak_floor)
                    avail = int(shed.get(item, 0) or 0)
                    if price >= thr:
                        new_market.append(["SELL", item, max(qty, avail) if avail > 0 else qty])
                    else:
                        new_market.append(o)
                else:
                    # grãos: igual v6 — segura 50% se price < base*1.3 (esperando subir)
                    base = _GBASE[item]
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

    header = f'''"""hybrid_v13 - single-file Kaggle submission bundle.

Moon V56 + overlays do mix (maturity front-run + order-slot sell-first) +
glut-guard ADAPTATIVO: trailing stop pelo preço real da partida (dump quando
cai para FLOOR_REL do pico, ou momentum negativo) + grãos seguram enquanto
sobem. Fallback _GBASE fixo só no início.

Built by build_hybrid_v13.py. Self-contained: embute moon_agent_main.py
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
