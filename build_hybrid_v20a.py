"""Build do candidato estrutural v20a — componente "-STRAWBERRY tardia".

Scientist loop, hipotese crop/estrutura. Observacao (finding id2 conf 0.35):
Moon planta STRAWBERRY ~34-42; o preco do morango CRASHA pos-d21. A coorte de
morango plantada a partir do dia ~12.5 (step>=300) tem a 1a colheita ~dia 22.5+
(no crash). Este candidato REMOVE essa coorte tardia (PLANT->PASS) e reduz a
compra de sementes correspondente (teste "gratis", mecanicamente seguro: as
visitas futuras de WATER/HARVEST naqueles tiles viram no-op, sem crash).

NAO implementa o "+CARROT/+WHEAT" (exigiria re-coreografia posicional com HARVEST
no tile ~d+3; tape nao tem coords). Testa apenas o componente -STRAWBERRY tarde.

Output: submissions/hybrid_v20a/main.py  (reusa o blob+overlays do v19)
Usage:   python build_hybrid_v20a.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "submissions" / "hybrid_v19" / "main.py"
OUT = ROOT / "submissions" / "hybrid_v20a" / "main.py"

# step minimo (dia ~12.5); morangos plantados a partir daqui colhem no crash.
_MIN_STEP = 300

_PATCH = '''

# ---------------------------------------------------------------------------
# v20a: candidato estrutural "-STRAWBERRY tardia" (Scientist, axis=estrutura).
# Remove a coorte de morango plantada em step>=%d (1a colheita cai no crash
# pos-d21) e reduz a ultima compra de sementes de STRAWBERRY correspondente.
# Mecanicamente seguro: WATER/HARVEST futuros nos tiles viram no-op.
# ---------------------------------------------------------------------------
_V20A_MIN_STEP = %d


def _v20a_trim(tape, min_step):
    removed = 0
    for step in range(min_step, len(tape)):
        ac = tape[step]
        orders = []
        if isinstance(ac.get("farmer"), list):
            orders.append(ac["farmer"])
        for h in ac.get("hands") or []:
            if isinstance(h, list):
                orders.append(h)
        for order in orders:
            if (isinstance(order, list) and len(order) >= 2
                    and order[0] == "PLANT" and order[1] == "STRAWBERRY"):
                order[:] = ["PASS"]
                removed += 1
    # reduz a ultima compra de semente de STRAWBERRY antes de min_step
    if removed:
        for step in range(min_step - 1, -1, -1):
            ac = tape[step]
            changed = False
            for o in ac.get("market") or []:
                if (isinstance(o, list) and len(o) >= 3
                        and o[0] == "BUY_SEED" and o[1] == "STRAWBERRY"):
                    o[2] = max(0, int(o[2] or 0) - removed)
                    removed = 0
                    changed = True
                    break
            if changed and removed == 0:
                break
    return removed


def _v20a_patch_tapes(moon):
    names = [n for n in dir(moon)
             if n.startswith("_ACTIONS_") or n.startswith("_LEGACY_ACTIONS_")]
    total = 0
    for name in names:
        tape = getattr(moon, name, None)
        if tape:
            total += _v20a_trim(tape, _V20A_MIN_STEP)
    return moon


moon = _v20a_patch_tapes(moon)
''' % (_MIN_STEP, _MIN_STEP)


def build() -> None:
    src = SRC.read_text(encoding="utf-8")
    anchor = 'moon = _load(_MOON_B85, "moon_agent_main")\n'
    if anchor not in src:
        raise SystemExit("anchor nao encontrado no v19 main.py")
    patched = src.replace(anchor, anchor + _PATCH, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(patched, encoding="utf-8")
    print(f"OK -> {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
