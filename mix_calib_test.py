"""Clean calibration test for mix_agent front-run variants (fresh process).

Usage: python mix_calib_test.py [variant]
  variant in: baseline | fullshed | horizon3 | both
Runs mix vs purearch on seeds 1-8 for the given variant. Each run is a fresh
process so module state can't leak between variants.
"""
import sys
import statistics

sys.path.insert(0, ".")
sys.path.insert(0, "reference/opponents")

import mix_agent  # noqa: E402
import purearch_opponent as pa  # noqa: E402
from kaggle_environments import make  # noqa: E402

seeds = [1, 2, 3, 4, 5, 6, 7, 8]


def h2h(a, b):
    ms = []
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([a, b])
        last = env.steps[-1]
        ms.append(last[0]["reward"] - last[1]["reward"])
    return ms


def main():
    variant = sys.argv[1] if len(sys.argv) > 1 else "baseline"

    if variant == "fullshed":
        # Clone front-run sells FULL shed quantity (not capped by planned).
        orig = mix_agent._front_run_purearch
        def _full(action, obs, step):
            if mix_agent.c27_agent._CLONE_CONFIDENCE < 2:
                return
            orders = list(action.get("market", []) or [])
            if len(orders) >= 10:
                return
            already = set()
            for o in orders:
                if isinstance(o, list) and len(o) >= 2 and o[0] == "SELL":
                    already.add(o[1])
            shed = (obs.get("private") or {}).get("shed") or {}
            # sell the premium product the trace is about to dump, FULL shed qty
            # find planned items from purearch's near-future sells
            planned = set()
            step_i = min(int(obs.get("step", 0) or 0), len(pa._MARKET_TRACE) - 1)
            for fs in range(step_i + 1, min(len(pa._MARKET_TRACE), step_i + 3)):
                for o in pa._MARKET_TRACE[fs]:
                    if (isinstance(o, list) and len(o) >= 3 and o[0] == "SELL"
                            and o[1] in ("MELON", "STRAWBERRY", "MILK", "WOOL")):
                        planned.add(o[1])
            for item in sorted(planned):
                qty = int(shed.get(item, 0) or 0)
                if qty > 0 and item not in already and len(orders) < 10:
                    orders.append(["SELL", item, qty])
                    already.add(item)
            action["market"] = orders[:10]
        mix_agent._front_run_purearch = _full

    elif variant == "horizon3":
        mix_agent._FRONT_RUN_HORIZON = 3

    elif variant == "both":
        mix_agent._FRONT_RUN_HORIZON = 3
        orig = mix_agent._front_run_purearch
        def _full3(action, obs, step):
            if mix_agent.c27_agent._CLONE_CONFIDENCE < 2:
                return
            orders = list(action.get("market", []) or [])
            if len(orders) >= 10:
                return
            already = set()
            for o in orders:
                if isinstance(o, list) and len(o) >= 2 and o[0] == "SELL":
                    already.add(o[1])
            shed = (obs.get("private") or {}).get("shed") or {}
            planned = set()
            step_i = min(int(obs.get("step", 0) or 0), len(pa._MARKET_TRACE) - 1)
            for fs in range(step_i + 1, min(len(pa._MARKET_TRACE), step_i + 4)):
                for o in pa._MARKET_TRACE[fs]:
                    if (isinstance(o, list) and len(o) >= 3 and o[0] == "SELL"
                            and o[1] in ("MELON", "STRAWBERRY", "MILK", "WOOL")):
                        planned.add(o[1])
            for item in sorted(planned):
                qty = int(shed.get(item, 0) or 0)
                if qty > 0 and item not in already and len(orders) < 10:
                    orders.append(["SELL", item, qty])
                    already.add(item)
            action["market"] = orders[:10]
        mix_agent._front_run_purearch = _full3

    elif variant == "top2":
        # Clone front-run sells the TOP-2 planned glut products.
        orig = mix_agent._front_run_purearch
        def _top2(action, obs, step):
            if mix_agent.c27_agent._CLONE_CONFIDENCE < 2:
                return
            orders = list(action.get("market", []) or [])
            if len(orders) >= 10:
                return
            already = {}
            for o in orders:
                if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
                    already[o[1]] = already.get(o[1], 0) + max(0, int(o[2] or 0))
            planned = {}
            step_i = min(int(obs.get("step", 0) or 0), len(pa._MARKET_TRACE) - 1)
            for fs in range(step_i + 1, min(len(pa._MARKET_TRACE), step_i + 3)):
                d = fs - step_i
                for o in pa._MARKET_TRACE[fs]:
                    if not (isinstance(o, list) and len(o) >= 3 and o[0] == "SELL"
                            and o[1] in ("MELON", "STRAWBERRY", "MILK", "WOOL")):
                        continue
                    item, qty = o[1], max(0, int(o[2] or 0))
                    if item not in planned:
                        planned[item] = [d, qty]
                    else:
                        planned[item][1] += qty
            shed = (obs.get("private") or {}).get("shed") or {}
            prices = ((obs.get("market") or {}).get("prices") or {})
            choices = []
            for item, (d, qty) in planned.items():
                avail = max(0, int(shed.get(item, 0) or 0) - already.get(item, 0))
                qty = min(avail, qty)
                if qty <= 0:
                    continue
                price = float(prices.get(item, mix_agent._BASE_PRICE[item]) or 0)
                prio = (price * qty * mix_agent._GLUT_WEIGHT[item]
                        + (2 + 1 - d) * mix_agent._BASE_PRICE[item])
                choices.append((prio, item, qty))
            if choices:
                choices.sort(reverse=True)
                for _, item, qty in choices[:2]:
                    if len(orders) >= 10:
                        break
                    orders.append(["SELL", item, qty])
                action["market"] = orders[:10]
        mix_agent._front_run_purearch = _top2

    ms = h2h(mix_agent.agent, pa.agent)
    print(f"{variant}: mean={statistics.mean(ms):+.0f} "
          f"({sum(1 for m in ms if m > 0)}-{sum(1 for m in ms if m < 0)}) per={[int(m) for m in ms]}")


if __name__ == "__main__":
    main()
