"""Build do candidato estrutural v20b — "+SHEEP cedo / +SHEEP no lugar de COW".

Scientist loop, hipotese id=1 (axis=estrutura), finding id2 (conf 0.35):
tops compram mais SHEEP (2-11) que o Moon nas rotas leite/neutra.

Operacionalizacao CLEAN (mantem coreografia): as rotas 10C4S e 8C6S compartilham
o MESMO esqueleto fisico (mesmos moves/water/harvest/pastagens) e so diferem no
mix de animais comprados. Este candidato troca o lote de 2 COW comprado no dia
~9 (step 216) por 2 SHEEP na MESMA janela de pickup/place -> mesma estrutura,
mesmo nº de animais, producao muda de MILK para WOOL.

Rotas alteradas: _ACTIONS_10C4S_3Q, _ACTIONS_8C6S_3Q (+ versoes _LEGACY_).
Rotas yarn (ja sheep-heavy) e _6C8S_3Q nao sao tocadas.

Output: submissions/hybrid_v20b/main.py  (reusa o blob+overlays do v19)
Usage:   python build_hybrid_v20b.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "submissions" / "hybrid_v19" / "main.py"
OUT = ROOT / "submissions" / "hybrid_v20b" / "main.py"

_PATCH = '''

# ---------------------------------------------------------------------------
# v20b: candidato estrutural "+SHEEP cedo" (Scientist, axis=estrutura).
# Troca o lote de 2 COW do dia ~9 (step 216) por 2 SHEEP nas rotas 10C4S e 8C6S
# (+legacy). Mesma coreografia (pickup/place na mesma janela de steps); muda a
# producao: -MILK +WOOL. Nao toca nas rotas yarn (ja sheep-heavy).
# ---------------------------------------------------------------------------
def _v20b_swap_cow_lot_to_sheep(tape, buy_step, qty=2):
    ac = tape[buy_step]
    changed = 0
    for o in ac.get("market") or []:
        if (isinstance(o, list) and len(o) >= 2 and o[0] == "BUY_ANIMAL"
                and o[1] == "COW" and changed < qty):
            o[1] = "SHEEP"
            changed += 1
    pk = plc = 0
    for step in range(buy_step + 1, min(buy_step + 96, len(tape))):
        if pk >= qty and plc >= qty:
            break
        a2 = tape[step]
        orders = []
        if isinstance(a2.get("farmer"), list):
            orders.append(a2["farmer"])
        for h in a2.get("hands") or []:
            if isinstance(h, list):
                orders.append(h)
        for order in orders:
            if not (isinstance(order, list) and len(order) >= 2
                    and order[1] == "COW" and order[0] in ("PICKUP", "PLACE")):
                continue
            if order[0] == "PICKUP" and pk < qty:
                order[1] = "SHEEP"
                pk += 1
            elif order[0] == "PLACE" and plc < qty:
                order[1] = "SHEEP"
                plc += 1
    return tape


def _v20b_patch_tapes(moon):
    names = ("_ACTIONS_10C4S_3Q", "_ACTIONS_8C6S_3Q",
             "_LEGACY_ACTIONS_10C4S_3Q", "_LEGACY_ACTIONS_8C6S_3Q")
    for name in names:
        tape = getattr(moon, name, None)
        if tape:
            _v20b_swap_cow_lot_to_sheep(tape, 216, qty=2)
    return moon


moon = _v20b_patch_tapes(moon)
'''


def build() -> None:
    src = SRC.read_text(encoding="utf-8")
    anchor = 'moon = _load(_MOON_B85, "moon_agent_main")\n'
    if anchor not in src:
        raise SystemExit("anchor nao encontrado no v19 main.py")
    # mantem o load original e insere o patch logo depois (o patch religa moon)
    patched = src.replace(anchor, anchor + _PATCH, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(patched, encoding="utf-8")
    print(f"OK -> {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
