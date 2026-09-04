"""Monitor de ELO do hybrid_v19 (teste anti-resubmit).

Lê a submissão mais recente de hybrid_v19 (COMPLETE), registra (ts, sub_date, elo)
num CSV e imprime a trajetória. NUNCA submete. Fins: verificar se o ELO de uma
submissão DEIXADA EM PAZ sobe sozinho (convergência) ou se a rotina de resubmit
estava resetando o rating.

Uso:
    python elo_track.py            # registra + imprime resumo
"""
from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
CSV_PATH = _HERE / "results" / "elo_track_v19.csv"


def fetch_latest_v19():
    import os as _os
    token = Path.home() / ".kaggle" / "access_token"
    _os.environ["KAGGLE_API_TOKEN"] = token.read_text().strip()
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    subs = api.competition_submissions("kaggriculture")
    v19 = [s for s in subs if s.file_name == "hybrid_v19.tar.gz" and s.status.name == "COMPLETE"]
    if not v19:
        return None
    s = max(v19, key=lambda x: x.date)
    return {"sub_date": s.date.strftime("%Y-%m-%d %H:%M"), "elo": s.public_score}


def main():
    cur = fetch_latest_v19()
    if cur is None:
        print("SEM_SUBMISSAO_V19_COMPLETE")
        return
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if CSV_PATH.exists():
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    prev = rows[-1] if rows else None
    baseline = rows[0] if rows else None

    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not rows:
            w.writerow(["ts", "sub_date", "elo"])
        w.writerow([now, cur["sub_date"], cur["elo"]])

    print(f"TRACK ts={now} sub_date={cur['sub_date']} elo={cur['elo']}")
    delta_base = None
    if baseline:
        delta_base = round(float(cur["elo"]) - float(baseline["elo"]), 1)
        print(f"BASELINE elo={baseline['elo']} (sub {baseline['sub_date']}) delta={delta_base:+.1f}")
    if prev:
        d_prev = round(float(cur["elo"]) - float(prev["elo"]), 1)
        print(f"PREV elo={prev['elo']} delta={d_prev:+.1f}")
    if baseline and baseline["sub_date"] != cur["sub_date"]:
        print("NEW_SUBMISSION")
    print(f"REGISTROS={len(rows)+1}")


if __name__ == "__main__":
    main()
