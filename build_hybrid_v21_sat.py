"""Build do candidato v21_sat — "saturação do inventory global" (Scientist).

Hipótese (mecânica de preço 29/08, durável): preço = f(inventory_global) com
equilibrium I0=10000. Quando o inventory global CRUZA para cima de 10000
(oversupply estrutural), o preço de itens com shape acima do equilibrium colapsa
(MELON ~d12, STRAWBERRY ~d24-26). O v19 só usa floor RELATIVO (dyn_base) e
vende fracionado (lotes <=16), então "dribla" a queda. O v21 adiciona um gatilho
ABSOLUTO: se inventory_global[item] >= 10000 + trig, faz DUMP TOTAL do shed
daquele item agora (independente do momentum/dyn_base).

Escopo: MELON e STRAWBERRY (crash, sem recuperação). Exclui WOOL (dip + retoma
tarde) e MILK (não cruza/colapsa).

Output: submissions/hybrid_v21_sat/main.py  (reusa o champion v19 + overlay)
Usage:   python build_hybrid_v21_sat.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "submissions" / "hybrid_v19" / "main.py"
OUT = ROOT / "submissions" / "hybrid_v21_sat" / "main.py"

_OVERLAY = '''

# ---------------------------------------------------------------------------
# v21_sat — overlay "saturação do inventory global".
# Re-define agent() no fim do arquivo (base = v19). Só intervém quando um item
# alvo está em oversupply estrutural (inventory_global >= 10000 + trig) e força
# o esvaziamento do shed naquele item (dump total), em vez de driblar.
# ---------------------------------------------------------------------------
_BASE_AGENT_V21 = agent

_SAT_ITEMS = ("MELON", "STRAWBERRY")
_SAT_TRIG = {"MELON": 40, "STRAWBERRY": 40}   # unidades acima de 10000
_SAT_EQUILIBRIUM = 10000
_SAT_START = 120
_SAT_STOP = 708


def _sat_seat(obs):
    return 1 if int(obs.get("player", 0) or 0) == 1 else 0


def _sat_guard(action, obs, step):
    if not (_SAT_START <= step < _SAT_STOP):
        return action
    try:
        inv = dict(((obs.get("market") or {}).get("inventory") or {}) or {})
        shed = dict(((obs.get("private") or {}).get("shed") or {}) or {})
        if not inv or not shed:
            return action
        mk = list(action.get("market") or [])
        if not mk:
            return action
        changed = False
        for item in _SAT_ITEMS:
            I = int(inv.get(item, 0) or 0)
            if I < _SAT_EQUILIBRIUM + _SAT_TRIG[item]:
                continue
            avail = int(shed.get(item, 0) or 0)
            if avail <= 0:
                continue
            found = False
            for o in mk:
                if (isinstance(o, list) and len(o) >= 3
                        and o[0] == "SELL" and o[1] == item):
                    o[2] = avail
                    found = True
                    changed = True
                    break
            if not found and len(mk) < 10:
                mk.append(["SELL", item, avail])
                changed = True
        if changed:
            action["market"] = mk[:10]
    except Exception:
        pass
    return action


def agent(obs, config=None):
    step = obs.get("step")
    step = int(step) if step is not None else -1
    if step < 0:
        step = int(obs.get("day", 0) or 0) * 24 + int(obs.get("hour", 0) or 0)
    action = _BASE_AGENT_V21(obs, config)
    try:
        action = _sat_guard(action, obs, step)
    except Exception:
        pass
    return action
'''


def build() -> None:
    if not SRC.exists():
        raise SystemExit(f"base v19 nao encontrado: {SRC}")
    src = SRC.read_text(encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(src.rstrip() + "\n" + _OVERLAY, encoding="utf-8")
    print(f"OK -> {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
