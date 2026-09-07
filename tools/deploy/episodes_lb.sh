#!/bin/bash
# Job cron: baixa episódios recentes dos top-10 (replays crus ~30MB) + manifest.
# Guarda anti-duplicidade.
set -e
exec 9>/opt/kaggriculture/logs/episodes.lock
flock -n 9 || { echo "episodes ja em execucao; skip $(date -u +%FT%TZ)" >> /opt/kaggriculture/logs/ep.log; exit 0; }
export HOME=/root
export PATH=/usr/local/bin:/usr/bin:/bin:$PATH
mkdir -p /opt/kaggriculture/logs /opt/kaggriculture/replays
cd /opt/kaggriculture-ai-agent
/opt/kaggriculture/venv/bin/python tools/collect/episodes.py --top 10 --max-episodes 1 --replay-dir /opt/kaggriculture/replays >> /opt/kaggriculture/logs/ep.log 2>&1
echo "episodes done $(date -u +%FT%TZ)" >> /opt/kaggriculture/logs/ep.log
