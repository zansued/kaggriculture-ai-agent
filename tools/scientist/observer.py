"""Observer — detecta drift no leaderboard a partir dos snapshots.

Compara os 2 snapshots mais recentes em leaderboard_snapshots e reporta:
  - horários dos snapshots e gap
  - trajetória do top-10 atual (score atual, anterior, delta, rank)
  - maiores subidas/descidas de score no top-100
  - times que mudaram de submission_id entre snapshots (sinal de novo envio)

Grava um registro em agent_runs (run_type='observer') como checkpoint.

Uso:
    python observer.py [--top 10] [--window 100]
"""
from __future__ import annotations

import argparse
import json
import sys

from db import get_conn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=10)
    ap.add_argument('--window', type=int, default=100)
    args = ap.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    # 2 snapshots mais recentes
    cur.execute("SELECT DISTINCT captured_at FROM leaderboard_snapshots ORDER BY captured_at DESC LIMIT 2")
    times = [r[0] for r in cur.fetchall()]
    if len(times) < 2:
        print('Observer: menos de 2 snapshots no banco; colete mais antes de comparar.')
        cur.close(); conn.close()
        return 1
    t_latest, t_prev = times[0], times[1]
    gap_min = round((t_latest - t_prev).total_seconds() / 60, 1)

    def load(t):
        cur.execute("""
            SELECT rank, team_id, team_name, score, submission_id FROM leaderboard_snapshots
            WHERE captured_at = %s ORDER BY rank LIMIT %s
        """, (t, args.window))
        return {r[1]: {'team_id': r[1], 'rank': r[0], 'name': r[2],
                       'score': float(r[3]) if r[3] else None, 'sub': r[4]} for r in cur.fetchall()}

    latest = load(t_latest)
    prev = load(t_prev)

    print(f'=== OBSERVER: snapshots {t_prev:%H:%MZ} -> {t_latest:%H:%MZ} (gap {gap_min} min) ===')

    print(f'\nTop {args.top} (trajetoria):')
    print(f"{'rank':>4} {'agora':>8} {'antes':>8} {'delta':>8}  time")
    rows = sorted(latest.values(), key=lambda x: x['rank'])[:args.top]
    for r in rows:
        p = prev.get(r['team_id'])
        before = p['score'] if p else None
        delta = (r['score'] - before) if (r['score'] is not None and before is not None) else None
        d = f'{delta:+.1f}' if delta is not None else '-'
        b = f'{before:.1f}' if before is not None else '-'
        a = f'{r["score"]:.1f}' if r['score'] is not None else '-'
        sub_change = ' [NOVA SUB]' if (p and p.get('sub') and r.get('sub') and p['sub'] != r['sub']) else ''
        print(f'{r["rank"]:>4} {a:>8} {b:>8} {d:>8}  {(r["name"] or "?")[:34]}{sub_change}')

    # maiores movimentacoes de score no window
    movers = []
    for tid, r in latest.items():
        p = prev.get(tid)
        if p and r['score'] is not None and p['score'] is not None:
            movers.append((r['score'] - p['score'], r['name'], p['rank'], r['rank']))
    movers.sort(reverse=True)
    print(f'\nMaiores SUBIDAS de score (top-{args.window}):')
    for delta, name, pr, nr in movers[:5]:
        print(f'  {delta:+.1f}  {name[:40]} (rank {pr}->{nr})')
    print('Maiores QUEDAS de score:')
    for delta, name, pr, nr in movers[-5:]:
        print(f'  {delta:+.1f}  {name[:40]} (rank {pr}->{nr})')

    # persiste checkpoint em agent_runs
    payload = {
        'gap_min': gap_min, 't_latest': str(t_latest), 't_prev': str(t_prev),
        'top': [{ 'rank': r['rank'], 'team': r['name'], 'score': r['score'],
                  'delta': (r['score'] - prev[tid]['score']) if tid in prev and prev[tid]['score'] and r['score'] else None }
                for tid, r in sorted(latest.items(), key=lambda x: x[1]['rank'])[:args.top]],
        'n_snapshots_pairs': 1,
    }
    cur.execute("INSERT INTO agent_runs (run_type, status, payload) VALUES ('observer','done',%s)",
                (json.dumps(payload, ensure_ascii=False),))
    conn.commit()
    cur.close(); conn.close()
    print('\nagent_runs: observer gravado.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
