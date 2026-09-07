"""Leitura robusta de JSONs h2h (h2h_bench.py e merges).

Aceita tanto o formato cru do h2h_bench (games/wins_a/wins_b/ties, sem mean_d)
quanto o formato normalizado (com mean_d/n). Em ambos, 'a' é o agente de
referência (P0). Para 2 lados, passar os dois arquivos já normalizados com o
mesmo 'a'.
"""
from __future__ import annotations

import json


def file_stats(path: str):
    d = json.load(open(path, encoding='utf-8'))
    games = d.get('games')
    if games is not None and isinstance(games, list) and games:
        r0 = [g.get('r0') for g in games]
        r1 = [g.get('r1') for g in games]
        # ignora jogos BAD (r0/r1 None)
        pairs = [(a, b) for a, b in zip(r0, r1) if a is not None and b is not None]
        wa = sum(1 for a, b in pairs if a > b)
        wb = sum(1 for a, b in pairs if b > a)
        ties = sum(1 for a, b in pairs if a == b)
        n = len(pairs)
        md = round(sum(a - b for a, b in pairs) / n, 1) if n else 0.0
    else:
        wa = d.get('wins_a', 0)
        wb = d.get('wins_b', 0)
        ties = d.get('ties', 0)
        n = d.get('n') or (wa + wb + ties)
        md = float(d.get('mean_d') or 0.0)
    return wa, wb, ties, md, n


def combine_stats(paths):
    wa = wb = ties = 0
    weighted = 0.0
    n = 0
    for p in paths:
        a, b, t, md, nn = file_stats(p)
        wa += a
        wb += b
        ties += t
        weighted += md * nn
        n += nn
    mean_d = round(weighted / n, 1) if n else 0.0
    return wa, wb, ties, mean_d, n, len(paths)
