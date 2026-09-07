#!/bin/bash
# Job cron: snapshot leaderboard top-100 -> JSON + ingest Postgres (kaggle-meta-db)
# Guarda anti-duplicidade (2 daemons cron podem existir no host).
set -e
exec 9>/opt/kaggriculture/logs/snapshot.lock
flock -n 9 || { echo "snapshot ja em execucao; skip $(date -u +%FT%TZ)" >> /opt/kaggriculture/logs/lb.log; exit 0; }
export HOME=/root
export PATH=/usr/local/bin:/usr/bin:/bin:$PATH
mkdir -p /opt/kaggriculture/logs
cd /opt/kaggriculture-ai-agent
/opt/kaggriculture/venv/bin/python tools/collect/leaderboard.py --n 100 >> /opt/kaggriculture/logs/lb.log 2>&1
cp data/leaderboard/latest.json /opt/kaggriculture/latest_lb.json
/opt/kaggriculture/venv/bin/python /opt/kaggriculture/db_ingest_lb.py >> /opt/kaggriculture/logs/lb.log 2>&1
echo "snapshot_lb done $(date -u +%FT%TZ)" >> /opt/kaggriculture/logs/lb.log
