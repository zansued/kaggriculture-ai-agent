"""Test debt-tracked front-run for the mix (fresh process).

Moon V56 / C45 technique: when we front-run a premium sale (sell the shed
stock before the trace's planned sell), record a DEBT and REDUCE the original
later sell by the shifted quantity — selling the SAME total, just earlier.
This avoids over-flooding the shared market (our current front-run ADDS a
sell on top of the trace's planned sells).

Usage: python mix_debt_test.py [variant]
  variant: baseline | debt
Runs vs purearch on seeds 1-12.
"""
import sys
import statistics

sys.path.insert(0, ".")
sys.path.insert(0, "reference/opponents")

import mix_agent  # noqa: E402
import purearch_opponent as pa  # noqa: E402
from kaggle_environments import make  # noqa: E402

seeds = list(range(1, 13))

# Debt state: item -> {due_step: qty}
_debt = {}


def _front_run_debt(action, obs, step):
    """Front-run like the mix, but record a debt and repay the later sell."""
    global _debt
    if mix_agent.c27_agent._CLONE_CONFIDENCE < 2:
        return action
    orders = list(action.get("market", []) or [])
    if len(orders) >= 10:
        return action
    already = {}
    for o in orders:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
            already[o[1]] = already.get(o[1], 0) + max(0, int(o[2] or 0))
    planned = {}
    end = min(len(pa._MARKET_TRACE), step + 3)
    for fs in range(step + 1, end):
        for o in pa._MARKET_TRACE[fs]:
            if not (isinstance(o, list) and len(o) >= 3 and o[0] == "SELL"
                    and o[1] in ("MELON", "STRAWBERRY", "MILK", "WOOL")):
                continue
            item = o[1]
            qty = max(0, int(o[2] or 0))
            if item not in planned:
                planned[item] = [fs, qty]
            else:
                planned[item][1] += qty
    shed = (obs.get("private") or {}).get("shed") or {}
    prices = ((obs.get("market") or {}).get("prices") or {})
    choices = []
    for item, (due_step, qty) in planned.items():
        avail = max(0, int(shed.get(item, 0) or 0) - already.get(item, 0))
        qty = min(avail, qty)
        if qty <= 0:
            continue
        price = float(prices.get(item, mix_agent._BASE_PRICE[item]) or 0)
        prio = (price * qty * mix_agent._GLUT_WEIGHT[item]
                + (2 + 1 - (due_step - step)) * mix_agent._BASE_PRICE[item])
        choices.append((prio, item, qty, due_step))
    if choices:
        choices.sort(reverse=True)
        _, item, qty, due_step = choices[0]
        orders.append(["SELL", item, qty])
        # record the debt: repay at the trace's due step.
        _debt.setdefault(item, {})
        _debt[item][due_step] = _debt[item].get(due_step, 0) + qty
        action["market"] = orders[:10]
    return action


def _repay_debt(action, obs, step):
    """Reduce the trace's later SELL by the recorded debt."""
    global _debt
    if not _debt:
        return action
    market = list(action.get("market", []) or [])
    for i, o in enumerate(market):
        if not (isinstance(o, list) and len(o) >= 3 and o[0] == "SELL"):
            continue
        item = o[1]
        due = _debt.get(item, {}).get(step, 0)
        if due > 0:
            reduce = min(int(o[2] or 0), due)
            o[2] = int(o[2] or 0) - reduce
            _debt[item][step] -= reduce
            if o[2] <= 0:
                market[i] = None
    action["market"] = [o for o in market if o is not None][:10]
    return action


def agent(obs, config=None):
    global _debt
    step = int(obs.get("step", 0) or 0)
    if step == 0:
        _debt = {}
    action = mix_agent.agent(obs, config)
    action = _front_run_debt(action, obs, step)
    action = _repay_debt(action, obs, step)
    action = mix_agent._sell_first(action, obs, step)
    return action


def h2h(a, b, seeds):
    ms = []
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([a, b])
        last = env.steps[-1]
        ms.append(last[0]["reward"] - last[1]["reward"])
    return ms


if __name__ == "__main__":
    variant = sys.argv[1] if len(sys.argv) > 1 else "debt"
    if variant == "baseline":
        ms = h2h(mix_agent.agent, pa.agent, seeds)
    else:
        ms = h2h(agent, pa.agent, seeds)
    print(f"{variant}: mean={statistics.mean(ms):+.0f} "
          f"({sum(1 for m in ms if m > 0)}-{sum(1 for m in ms if m < 0)}) per={[int(m) for m in ms]}")
