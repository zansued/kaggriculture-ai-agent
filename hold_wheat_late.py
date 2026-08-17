"""purearch production + HOLD WHEAT LATE sell overlay.

From the research report: top agents "não vendem trigo até o preço subir
muito no final" — they sell a little wheat early (8-38/day) and DUMP late
(120-149/day d19-29), because wheat price rises $27->$46. purearch sells
wheat throughout (including a big d12 dump of 204).

This overlay caps early WHEAT sells (d0-18) at a small rate and dumps big in
the late game, keeping ALL other purearch behavior (fert sell-all, other
products aggressive). Tests the report's specific claim.

Usage: python hold_wheat_late.py (demo); h2h via h2h_bench.py
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
import purearch_opponent as pa  # noqa: E402

EARLY_WHEAT_CAP = 15  # per-turn cap d0-18
DUMP_DAY = 19         # from here, dump everything


def agent(obs, config=None):
    trace = pa.agent(obs, config)
    day = int(obs.get("day", 0) or 0)
    market = []
    wheat_dumped_early = False
    for o in trace.get("market", []):
        if o and o[0] == "SELL" and len(o) >= 3 and o[1] == "WHEAT" and day < DUMP_DAY:
            # Cap early wheat sells; accumulate the rest for the late dump.
            qty = min(o[2], EARLY_WHEAT_CAP)
            if qty > 0:
                market.append(["SELL", "WHEAT", qty])
            wheat_dumped_early = True
        else:
            market.append(o)
    return {"farmer": trace.get("farmer", ["PASS"]), "hands": trace.get("hands", []), "market": market[:10]}


if __name__ == "__main__":
    from kaggle_environments import make
    for s in (1, 2):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "starter"])
        print(f"seed {s} vs starter:", env.steps[-1][0]["reward"])
