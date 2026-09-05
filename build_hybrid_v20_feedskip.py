"""Build do v20_feedskip sobre o champion hybrid_v19 (por-item).

Objetivo (P3 do PESQUISA_DEEP3_04SET): reduzir o FEED diário REDUNDANTE das COWs.

Medição (probe_cow_feed, seeds 1-3): o Moon alimenta COW ~0.98x/dia; ~49% dos
feeds caem em dias de diff PAR (fora da fase de produção) e ~90%+ dos feeds
fazem parte de runs diários triplos. A mecânica tolera 1 noite sem feed (escape
só com 2 consecutivas) e a produção da COW é a cada 2 dias em diff ÍMPAR
(prod-eve = (day+1)-placed-8 par). Logo dá para cortar os feeds em diff par sem
risco de fuga nem perda de produção/bônus.

Overlay (clockfix + feedskip):
  - CLOCK-0: injeta obs['step'] = day*24+hour (fonte canônica P0/P1).
  - Para cada worker cujo comando é FEED sobre uma COW:
      diff = day - placed_day
      pula (vira PASS) sse diff é PAR **e** a vaca foi alimentada ONTEM
      (last_feed == day-1). Assim nunca pulamos 2 feeds seguidos
      (consecutive_unfed max = 1) e mantemos todos os feeds em fase (diff ímpar,
      que inclui as noites produtivas).
  - WHEAT poupado fica no inventário do worker e é dropado ao shed no EOD
    (vira venda extra no terminal).

Build lê submissions/hybrid_v19/main.py e emite
submissions/hybrid_v20_feedskip/main.py.

Uso:
    python build_hybrid_v20_feedskip.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "submissions" / "hybrid_v19" / "main.py"
OUT = ROOT / "submissions" / "hybrid_v20_feedskip" / "main.py"

_OVERLAY = '''\
# ---------------------------------------------------------------------------
# v20_feedskip — skip de FEED diario redundante de COW + CLOCK-0.
# Adicionado APOS o champion v19; redefine agent() delegando ao base.
# ---------------------------------------------------------------------------
_FS_MEM = {}          # seat -> {(x,y,placed): last_feed_day}
_FS_MAX_STEP = 700    # nao intervir na liquidacao terminal


def _fs_step(obs):
    return int(obs.get("day", 0) or 0) * 24 + int(obs.get("hour", 0) or 0)


def _fs_seat(obs):
    return 1 if int(obs.get("player", 0) or 0) == 1 else 0


def _fs_farm(obs):
    farms = list(obs.get("farms", []) or [])
    s = _fs_seat(obs)
    return farms[s] if s < len(farms) else {}


def _fs_overlay(obs, action):
    step = _fs_step(obs)
    if step == 0:
        _FS_MEM.clear()
    if not (0 <= step < _FS_MAX_STEP):
        return action
    seat = _fs_seat(obs)
    farm = _fs_farm(obs)
    if not farm:
        return action
    day = int(obs.get("day", 0) or 0)
    tiles = farm.get("tiles") or []
    farmer = list(farm.get("farmer") or [0, 0])
    hands = [list(p) for p in (farm.get("hands") or [])]
    pos = [farmer, *hands]

    ua = [list(action.get("farmer") or ["PASS"])]
    ua += [list(h or ["PASS"]) for h in (action.get("hands") or [])]
    if len(ua) < len(pos):
        ua += [["PASS"]] * (len(pos) - len(ua))
    ua = ua[:len(pos)]

    mem = _FS_MEM.setdefault(seat, {})

    for i, p in enumerate(pos):
        if i >= len(ua):
            break
        cmd = ua[i] or ["PASS"]
        if not cmd or cmd[0] != "FEED":
            continue
        try:
            x, y = int(p[0]), int(p[1])
            t = tiles[y][x]
        except Exception:
            continue
        if not (isinstance(t, dict) and t.get("animal") == "COW"):
            continue
        placed = int(t.get("placed_day", day) or 0)
        diff = day - placed
        if diff % 2 != 0:
            # em fase (inclui noite produtiva): alimenta e registra
            mem[(x, y, placed)] = day
            continue
        # fora de fase (diff par): pula sse alimentada ontem
        if mem.get((x, y, placed)) == day - 1:
            ua[i] = ["PASS"]
        else:
            mem[(x, y, placed)] = day

    action["farmer"] = ua[0]
    action["hands"] = ua[1:]
    return action


_BASE_AGENT_FS = agent


def agent(obs, config=None):
    # CLOCK-0: fonte canonica de tempo (Moon e overlays) para P0 e P1.
    obs["step"] = int(obs.get("day", 0) or 0) * 24 + int(obs.get("hour", 0) or 0)
    action = _BASE_AGENT_FS(obs, config)
    try:
        action = _fs_overlay(obs, action)
    except Exception:
        pass  # overlay nunca deve derrubar o agente
    return action
'''


def build() -> None:
    if not SRC.exists():
        raise SystemExit(f"base v19 não encontrado: {SRC}")
    src = SRC.read_text(encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(src.rstrip() + "\n" + _OVERLAY, encoding="utf-8")
    print(f"OK -> {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
