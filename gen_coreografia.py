"""gen_coreografia — Gerador de coreografia para hands extras (Fase D, Passo 3).

Adiciona hands extras dedicados a ZONAS de colheita, fechando o gap de 523
tile-dias de atraso de colheita (docs/COBERTURA_ANALISE.md).

Abordagem (conceito testável):
  - A base (v18) segue a fita Moon + overlays para farmer/hands base.
  - HANDS EXTRAS (por índice, além dos da fita) são controlados por um
    coordenador de ZONA:
      * Na zona: se PLANT maduro (age>=2, yield>0) -> HARVEST; se não regado -> WATER;
        senão move para o próximo tile da zona.
      * Fora da zona: move em direção à zona.
  - Market: HIRE na rampa (6 -> 10 -> 13 -> 12).

O coordenador de zona é REATIVO (decide por estado). Se validar, a fita pode ser
gravada (Passo 4) para o bundle final.

Uso (teste do conceito):
    python -c "import gen_coreografia; gen_coreografia.test_vs_v18()"
"""
from __future__ import annotations

import importlib.util
import os

REPO = os.path.dirname(os.path.abspath(__file__))

# carrega o v18 (base)
spec18 = importlib.util.spec_from_file_location("v18", os.path.join(REPO, "submissions", "hybrid_v18", "main.py"))
mod18 = importlib.util.module_from_spec(spec18)
spec18.loader.exec_module(mod18)

# ---------------------------------------------------------------------------
# Zonas (docs/COREOGRAFIA_ZONAS.md)
# ---------------------------------------------------------------------------
# Por quadrante: NW(0-4,0-4) NE(5-9,0-4) SW(0-4,5-9) SE(5-9,5-9)
ZONAS = {
    "A": {"hand": 13, "tiles": [(x, y) for x in range(1, 4) for y in range(1, 4)]},        # NW centro (strawberry)
    "B": {"hand": 14, "tiles": [(x, y) for x in range(0, 5) for y in range(0, 5)
                                 if not (1 <= x <= 3 and 1 <= y <= 3)]},                     # NW bordas
    "C": {"hand": 15, "tiles": [(x, y) for x in range(5, 10) for y in range(0, 5)]},        # NE
    "D": {"hand": 16, "tiles": [(x, y) for x in range(0, 5) for y in range(5, 10)]},        # SW
    "E": {"hand": 17, "tiles": [(x, y) for x in range(5, 10) for y in range(5, 10)]},       # SE
}

# Rampa de HIRE (dia -> hands totais alvo) — máximo 18 (hands da fita + extras 13-17)
RAMP = {
    0: 6, 1: 6, 2: 6, 3: 6,
    4: 10, 5: 10, 6: 10, 7: 10, 8: 10,
    9: 14, 10: 14, 11: 14, 12: 14, 13: 14, 14: 14, 15: 14, 16: 14, 17: 14, 18: 14, 19: 14, 20: 14,
    21: 14, 22: 14, 23: 14, 24: 14, 25: 14, 26: 14, 27: 14, 28: 14, 29: 14,
}
DEFAULT_HANDS = 14


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _move_toward(pos, target):
    if pos == target:
        return None
    dx, dy = target[0] - pos[0], target[1] - pos[1]
    if abs(dx) >= abs(dy):
        return "EAST" if dx > 0 else "WEST"
    return "SOUTH" if dy > 0 else "NORTH"


def _zone_cmd(pos, zone_tiles, tiles, day, seeds):
    """Decide a ação de um hand extra na sua zona (foco: colheita + rega)."""
    x, y = pos
    # se na zona
    if (x, y) in zone_tiles:
        tile = tiles[y][x] if (0 <= y < len(tiles) and 0 <= x < len(tiles[y])) else None
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            crop = tile.get("crop")
            age = day - int(tile.get("planted_day", day))
            yield_u = int(tile.get("yield_units", 0) or 0)
            # primeiro: colher maduro
            if yield_u > 0:
                first_yd = {"WHEAT": 2, "CARROT": 2, "MELON": 10, "STRAWBERRY": 10, "TOMATO": 8}.get(crop, 2)
                if age >= first_yd:
                    return ["HARVEST"]
            # depois: regar se não regado
            if not tile.get("watered_today", False):
                return ["WATER"]
        # senão: mover para o próximo tile da zona com PLANT maduro
        best = None
        bd = 999
        for tx, ty in zone_tiles:
            t = tiles[ty][tx] if (0 <= ty < len(tiles) and 0 <= tx < len(tiles[ty])) else None
            if isinstance(t, dict) and t.get("kind") == "PLANT":
                d = _manhattan((x, y), (tx, ty))
                if d < bd and d > 0:
                    bd = d
                    best = (tx, ty)
        if best is None:
            # tudo colhido/regado: fica parado
            return ["PASS"]
        m = _move_toward((x, y), best)
        return [m] if m else ["PASS"]
    # fora da zona: move para o tile da zona mais próximo
    best = min(zone_tiles, key=lambda p: _manhattan((x, y), p))
    m = _move_toward((x, y), best)
    return [m] if m else ["PASS"]


def hybrid_agent(obs, config=None):
    """v18 base + hands extras de zona + HIRE na rampa."""
    step = int((obs or {}).get("step", 0) or 0)
    day = step // 24
    action = mod18.agent(obs, config)
    seat = int((obs or {}).get("index", 0) or 0)
    farms = obs.get("farms") or []
    if seat >= len(farms):
        return action
    farm = farms[seat]
    tiles = farm.get("tiles") or []
    hands = farm.get("hands") or []
    private = obs.get("private", {}) or {}
    seeds = int((private.get("seeds") or {}).get("WHEAT", 0) or 0)
    money = float(farm.get("money", 0) or 0)

    # 1. market: HIRE na rampa
    target_hands = RAMP.get(day, DEFAULT_HANDS)
    n_hands = len(hands)
    mkt = list(action.get("market") or [])
    if n_hands < target_hands and day < 27 and money > 150 and len(mkt) < 10:
        need = min(target_hands - n_hands, 10 - len(mkt))
        mkt += [["HIRE"]] * need
        action["market"] = mkt[:10]

    # 2. hands extras (índice >= 8) -> coordenador de zona
    base_hands = list(action.get("hands") or [])
    positions = [list(h) for h in hands]
    new_hands = list(base_hands)
    for zona in ZONAS.values():
        hi = zona["hand"] - 1  # índice na lista de hands (0-based)
        if hi >= len(new_hands):
            continue
        if hi >= len(positions):
            continue
        pos = positions[hi]
        new_hands[hi] = _zone_cmd(tuple(pos), zona["tiles"], tiles, day, seeds)
    action["hands"] = new_hands
    return action


def test_vs_v18(seeds=range(1, 13), n_games=24):
    """h2h hybrid vs v18 (2 lados)."""
    import statistics
    from kaggle_environments import make
    wins = loss = ties = 0
    margins = []
    for seed in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([hybrid_agent, mod18.agent])
        r0 = env.steps[-1][0]["reward"]; r1 = env.steps[-1][1]["reward"]
        if r0 > r1: wins += 1
        elif r1 > r0: loss += 1
        else: ties += 1
        margins.append(r0 - r1)
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([mod18.agent, hybrid_agent])
        r0 = env.steps[-1][0]["reward"]; r1 = env.steps[-1][1]["reward"]
        if r1 > r0: wins += 1
        elif r0 > r1: loss += 1
        else: ties += 1
        margins.append(r1 - r0)
    print(f"=== hybrid(extras) vs v18: {wins}-{loss} ties={ties} n={len(margins)} mean_d={statistics.mean(margins):+.0f}")
    return wins, loss, ties


if __name__ == "__main__":
    test_vs_v18()
