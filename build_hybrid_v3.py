"""Build do HÍBRIDO V3: hybrid_v2 + overlay _sheep_balance (lição dos top10).

V3 = hybrid_v2 (Moon + mature_opp_front_run + sell_first + glut_guard) + overlay
_sheep_balance: limita o nº de cows (~COW_CAP) e prioriza SHEEP até SHEEP_TARGET.

Motivação (replays dos top 10, ep 98403998 seed 647390248):
  - Arman (reward 117178): C5 S8 M15 (segura melons) → late WOOL $244.
  - Nós (reward 107960):     C8 S4 (despeja melons no d10) → pouco WOOL late.
  - Cluster A fraco (79-97k): C11 S4 — over-cows crasha o próprio MILK.
Receita dos top-10 fortes: C5-6 S8-10 + segurar premium.

Output: submissions/hybrid_v3/main.py
Uso:    python build_hybrid_v3.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
V2_OUT = ROOT / "submissions" / "hybrid_v2" / "main.py"
OUT = ROOT / "submissions" / "hybrid_v3" / "main.py"

_SHEEP_OVERLAY = '''

# ---------------------------------------------------------------------------
# V3: _sheep_balance — composição de animais alinhada aos top-10 fortes.
# Limita cows (COW_CAP) e prioriza SHEEP até SHEEP_TARGET, para maximizar
# WOOL no late ($244) em vez de saturar MILK (crash pós d13).
# ---------------------------------------------------------------------------
_COW_CAP = 6
_SHEEP_TARGET = 8


def _farm_counts(obs):
    cows = sheep = geese = 0
    for row in obs.get("farms", [{}])[0].get("tiles", []):
        for t in row:
            if not isinstance(t, dict):
                continue
            a = t.get("animal")
            if a == "COW":
                cows += 1
            elif a == "SHEEP":
                sheep += 1
            elif a == "GOOSE":
                geese += 1
    return cows, sheep, geese


def _sheep_balance(action, obs, step):
    cows, sheep, geese = _farm_counts(obs)
    if sheep >= _SHEEP_TARGET:
        return action
    if cows < _COW_CAP:
        return action
    # já temos cows suficientes -> converte compras de COW em SHEEP
    market = list(action.get("market", []) or [])
    new_market = []
    for o in market:
        if isinstance(o, list) and len(o) >= 2 and o[0] == "BUY_ANIMAL" and o[1] == "COW":
            n = int(o[2]) if len(o) > 2 else 1
            need = _SHEEP_TARGET - sheep
            if need > 0:
                take = min(n, need)
                new_market.append(["BUY_ANIMAL", "SHEEP", take])
                n -= take
                sheep += take
            if n > 0:
                new_market.append(["BUY_ANIMAL", "COW", n])
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
    action = _sheep_balance(action, obs, step)
    return action
'''


def build() -> None:
    v2 = V2_OUT.read_text(encoding="utf-8")
    # remove a função agent do V2 e injeta a versão V3 (que chama _sheep_balance)
    idx = v2.find("\ndef agent(obs, config=None):")
    if idx < 0:
        raise RuntimeError("não achei def agent no hybrid_v2")
    header = v2[:idx]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(header + _SHEEP_OVERLAY, encoding="utf-8")
    print(f"OK -> {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
