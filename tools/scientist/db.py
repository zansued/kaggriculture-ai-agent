"""Conexão com o kaggle-meta-db (Postgres na VPS).

Resolução de credenciais, em ordem:
1. env vars: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
2. layout VPS: /opt/kaggriculture/app.env + /opt/kaggriculture/db.env
"""
from __future__ import annotations

import os


def _load_env_file(path: str) -> dict:
    d = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                d[k] = v
    return d


def connection_params() -> dict:
    cfg = {k: os.environ.get(k) for k in ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD')}
    if not cfg['DB_HOST']:
        app = _load_env_file('/opt/kaggriculture/app.env')
        db = _load_env_file('/opt/kaggriculture/db.env')
        cfg = dict(
            DB_HOST=app.get('DB_HOST', '127.0.0.1'),
            DB_PORT=app.get('DB_PORT', '5433'),
            DB_NAME=app.get('DB_NAME', 'kaggriculture'),
            DB_USER=app.get('DB_USER', 'postgres'),
            DB_PASSWORD=db.get('POSTGRES_PASSWORD', ''),
        )
    return cfg


def get_conn():
    import psycopg2
    c = connection_params()
    return psycopg2.connect(
        host=c['DB_HOST'], port=int(c['DB_PORT']), dbname=c['DB_NAME'],
        user=c['DB_USER'], password=c['DB_PASSWORD'])


def current_git_sha() -> str:
    try:
        import subprocess
        return subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True,
                              text=True, timeout=10).stdout.strip() or 'unknown'
    except Exception:
        return 'unknown'
