"""Snapshot do leaderboard do Kaggriculture (competition 147734).

Grava o top-N completo (com submissionId, score, data) em data/leaderboard/
com timestamp UTC e mantém um data/leaderboard/latest.json.

Uso:
    python tools/collect/leaderboard.py [--n 100]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

COMPETITION_ID = 147734
TOKEN_PATH = os.path.expanduser('~/.kaggle/access_token')
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, '..', '..'))
_OUT_DIR = os.path.join(_REPO, 'data', 'leaderboard')


def get_leaderboard():
    import requests
    s = requests.Session()
    s.get('https://www.kaggle.com')
    xsrf = s.cookies.get('XSRF-TOKEN') or s.cookies.get('CSRF-TOKEN')
    token = open(TOKEN_PATH).read().strip()
    url = 'https://www.kaggle.com/api/i/competitions.LeaderboardService/GetLeaderboard'
    body = json.dumps({'competitionId': COMPETITION_ID,
                       'leaderboardMode': 'LEADERBOARD_MODE_DEFAULT'})
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-XSRF-TOKEN': xsrf or '',
        'X-Kaggle-Build-Version': '0.0.1',
        'User-Agent': 'Mozilla/5.0',
        'Origin': 'https://www.kaggle.com',
        'Referer': 'https://www.kaggle.com/competitions/kaggriculture/leaderboard',
    }
    r = s.post(url, data=body, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f'GetLeaderboard falhou: {r.status_code} {r.text[:200]}')
    return r.json()


def normalize(entry):
    """Extrai os campos que nos interessam de uma entrada do publicLeaderboard."""
    return {
        'rank': entry.get('rank'),
        'teamId': entry.get('teamId'),
        'teamName': entry.get('teamName') or entry.get('teamNameNullable'),
        'score': entry.get('score') or entry.get('scoreNullable') or entry.get('displayScore'),
        'submissionId': entry.get('submissionId'),
        'submissionDate': entry.get('submissionDate'),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=100)
    args = ap.parse_args()

    data = get_leaderboard()
    lb = data.get('publicLeaderboard', [])
    teams = data.get('teams', [])
    by_id = {t.get('teamId'): (t.get('teamName') or t.get('name')) for t in teams}

    rows = []
    for e in lb[:args.n]:
        row = normalize(e)
        row['teamName'] = row['teamName'] or by_id.get(row['teamId'])
        rows.append(row)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H%M%SZ')
    os.makedirs(_OUT_DIR, exist_ok=True)
    path = os.path.join(_OUT_DIR, f'leaderboard_{ts}.json')
    snap = {'capturedAt': ts, 'n': len(rows), 'rows': rows}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    with open(os.path.join(_OUT_DIR, 'latest.json'), 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)

    print(f'Snapshot gravado: {path}  ({len(rows)} times)')
    print(f'{"rank":>4}  {"score":>8}  team')
    for r in rows[:10]:
        print(f'{str(r["rank"]):>4}  {str(r["score"]):>8}  {(r["teamName"] or "?")[:40]}')
    return rows


if __name__ == '__main__':
    main()  # não usar sys.exit(main()): main retorna lista -> exit code 1
