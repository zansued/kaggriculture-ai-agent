#!/bin/bash
# Job cron: observer (drift leaderboard) - roda apos cada snapshot de 6h.
# Guarda anti-duplicidade.
set -e
exec 9>/opt/kaggriculture/logs/observer.lock
flock -n 9 || { echo "observer ja em execucao; skip $(date -u +%FT%TZ)" >> /opt/kaggriculture/logs/observer.log; exit 0; }
export HOME=/root
export PATH=/usr/local/bin:/usr/bin:/bin:$PATH
mkdir -p /opt/kaggriculture/logs
cd /opt/kaggriculture-ai-agent
/opt/kaggriculture/venv/bin/python tools/scientist/observer.py >> /opt/kaggriculture/logs/observer.log 2>&1 || true
echo "observer done $(date -u +%FT%TZ)" >> /opt/kaggriculture/logs/observer.log
