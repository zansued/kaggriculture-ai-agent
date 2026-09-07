"""Lista episódios e baixa replays dos top-N times do Kaggriculture.

Lê data/leaderboard/latest.json (produzido por leaderboard.py) e, para cada
time do top-N, consulta os episódios públicos da submissão em tracking e baixa
os M episódios mais recentes ainda não baixados. Grava um manifest.json no
diretório de saída para evitar re-baixar.

Uso:
    python tools/collect/episodes.py [--top 10] [--max-episodes 1] [--replay-dir data/replays]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, '..', '..'))
_LATEST = os.path.join(_REPO, 'data', 'leaderboard', 'latest.json')


def _run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def list_episodes(submission_id: str):
    r = _run(['kaggle', 'competitions', 'episodes', str(submission_id)])
    ids = re.findall(r'^\s*(\d{6,})\s', r.stdout, re.M)
    return ids


def download_replay(episode_id: str, replay_dir: str):
    os.makedirs(replay_dir, exist_ok=True)
    r = _run(['kaggle', 'competitions', 'replay', episode_id, '-p', replay_dir])
    if r.returncode != 0:
        raise RuntimeError(f'replay {episode_id} falhou: {r.stderr[:300]}')
    # acha o arquivo baixado
    for f in os.listdir(replay_dir):
        if f.startswith(f'episode-{episode_id}'):
            return os.path.join(replay_dir, f)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=10)
    ap.add_argument('--max-episodes', type=int, default=1)
    ap.add_argument('--replay-dir', default=os.path.join(_REPO, 'data', 'replays'))
    args = ap.parse_args()

    latest = json.load(open(_LATEST, encoding='utf-8'))
    rows = latest['rows'][:args.top]

    manifest_path = os.path.join(args.replay_dir, 'manifest.json')
    manifest = {}
    if os.path.exists(manifest_path):
        manifest = json.load(open(manifest_path, encoding='utf-8'))

    os.makedirs(args.replay_dir, exist_ok=True)
    log = []
    for row in rows:
        team = (row.get('teamName') or '?')[:40]
        sub_id = row.get('submissionId')
        if not sub_id:
            continue
        eps = list_episodes(sub_id)
        if not eps:
            print(f'[skip] rank {row["rank"]} {team}: sem episódios públicos (sub {sub_id})', flush=True)
            continue
        new = 0
        for ep in eps[:args.max_episodes]:
            if str(ep) in manifest:
                continue
            print(f'[dl]   rank {row["rank"]} {team} sub={sub_id} ep={ep} ...', flush=True)
            path = download_replay(str(ep), args.replay_dir)
            if path:
                manifest[str(ep)] = {
                    'episode_id': ep, 'submission_id': sub_id, 'team_id': row.get('teamId'),
                    'team_name': team, 'rank': row.get('rank'), 'replay_path': path,
                    'downloaded_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                }
                new += 1
            else:
                print(f'[erro] ep {ep}: arquivo não encontrado após download', flush=True)
        log.append({'rank': row['rank'], 'team': team, 'new': new, 'total_eps': len(eps)})

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print('\nResumo:')
    for l in log:
        print(f"  rank {l['rank']:>3} {l['team'][:38]:<38} novos={l['new']} (total_eps={l['total_eps']})")
    print(f'Manifesto: {manifest_path}')


if __name__ == '__main__':
    sys.exit(main())
