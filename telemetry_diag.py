"""Telemetria de producao: instrumenta um agente e compara perfis v19/v18/v17
contra um oponente fixo (v18), para localizar onde o reward se perde.

Uso:
    python telemetry_diag.py --cands v19,v18,v17 --opp v18 --seeds 1-3 [--steps 720]
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))

MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}
PROD = {"PLANT", "WATER", "HARVEST", "FEED", "CARE", "FERTILIZE",
        "COLLECT_FERTILIZER", "PLACE", "BUILD_PASTURE", "DIG", "DROP", "PICKUP", "BUY_ANIMAL"}
CAP = 6  # max_held animal (engine)


def load(name: str):
    folder = name if name.startswith("hybrid_") else "hybrid_" + name
    modname = "subm_" + folder.replace("/", "_")
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_HERE, "submissions", folder, "main.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent


def cell_at(farm, pos):
    try:
        x, y = int(pos[0]), int(pos[1])
        row = farm["tiles"][y]
        if 0 <= x < len(row):
            return row[x]
    except Exception:
        pass
    return None


class Tele:
    def __init__(self):
        self.cmd = Counter()
        self.hand_turns = 0          # farmer + hands presentes, somado por turno
        self.actions_emitted = 0     # farmer+hands com comando explicito
        self.turns = 0
        self.moves = 0
        self.pass_explicit = 0
        self.no_action = 0           # hand presente sem acao no act
        self.prod = 0
        self._harvest_at = {}        # (x,y) -> turno do ultimo HARVEST de crop
        self.replant_lat = []        # latencias harvest->replant (turnos)
        self.care = 0
        self.care_at_cap = 0         # CARE num pasture com yield>=CAP
        self.care_pending_gt1 = 0    # CARE num pasture com pending_care_bonus>1
        self.feeds = 0
        self.pickup = Counter()
        self.near_cap_turns = 0      # turns em que algum pasture tem yield>=CAP
        self.animal_days = 0         # pastures vistos por turno (proxy rebanho)
        self.shed = Counter()        # shed final
        self.shed_max = Counter()
        self.sells = Counter()       # unidades vendidas por item
        self.market_orders = Counter()  # tipo de ordem de mercado
        self.buys = Counter()
        self.final = None

    def _is_pasture(self, cell):
        return isinstance(cell, dict) and cell.get("kind") == "PASTURE" and cell.get("animal")

    def _note_cells(self, farm):
        # pastos perto do cap (proxy de clipping de producao animal)
        for row in farm["tiles"]:
            for cell in row:
                if not isinstance(cell, dict):
                    continue
                if cell.get("kind") == "PASTURE" and cell.get("animal"):
                    self.animal_days += 1
                    y = int(cell.get("yield_units", 0) or 0)
                    if y >= CAP:
                        self.near_cap_turns += 1

    def record(self, obs, act):
        self.turns += 1
        farm = obs["farms"][obs["player"]]
        n_hands = len(farm.get("hands") or [])
        self.hand_turns += 1 + n_hands
        self._note_cells(farm)

        # shed
        shed = obs.get("private", {}).get("shed", {})
        for k, v in shed.items():
            self.shed[k] = v
            if v > self.shed_max[k]:
                self.shed_max[k] = v

        # ordens de mercado
        mkt = act.get("market") if isinstance(act, dict) else []
        for o in mkt or []:
            if not isinstance(o, (list, tuple)) or not o:
                continue
            t = o[0]
            self.market_orders[t] += 1
            if t == "SELL" and len(o) >= 3:
                self.sells[o[1]] += o[2]
            elif t in ("BUY_PRODUCT", "BUY_ANIMAL", "BUY_SEED") and len(o) >= 3:
                self.buys[o[1]] += o[2]

        # farmer action
        fa = act.get("farmer") if isinstance(act, dict) else None
        hands_a = act.get("hands") if isinstance(act, dict) else []
        hand_poses = farm.get("hands") or []

        # farmer age na posicao do farmer
        if fa:
            self._on_action(fa, farm.get("farmer"), is_farmer=True)
        # hands (alinhados por indice)
        for i in range(n_hands):
            a = hands_a[i] if i < len(hands_a) else None
            pos = hand_poses[i] if i < len(hand_poses) else None
            if a is None:
                self.no_action += 1
                continue
            self._on_action(a, pos, is_farmer=False)

    def _on_action(self, action, pos, is_farmer):
        if not isinstance(action, (list, tuple)) or not action:
            self.no_action += 1
            return
        cmd = action[0]
        self.cmd[cmd] += 1
        self.actions_emitted += 1
        cell = None
        if pos is not None:
            # a farm precisa estar disponivel; passamos via record para _on_action? simplifica:
            pass
        if cmd in MOVES:
            self.moves += 1
            return
        if cmd == "PASS":
            self.pass_explicit += 1
            return
        if cmd not in PROD:
            return
        self.prod += 1
        if cmd == "PICKUP":
            self.pickup[action[1] if len(action) > 1 else "?"] += 1
        # estado da celula onde a acao age (posicao atual do worker)
        # pos e preenchida fora via _cell_state

    def record_cell_state(self, action, pos, farm):
        """Associa acao com a celula onde ocorre (para CARE/HARVEST/PLANT)."""
        if not isinstance(action, (list, tuple)) or not action:
            return
        cmd = action[0]
        cell = cell_at(farm, pos) if pos is not None else None
        turn = self.turns - 1  # turno do obs atual (ja incrementado)

        if cmd == "CARE":
            self.care += 1
            if self._is_pasture(cell):
                y = int(cell.get("yield_units", 0) or 0)
                pend = int(cell.get("pending_care_bonus", 0) or 0)
                if y >= CAP:
                    self.care_at_cap += 1
                if pend > 1:
                    self.care_pending_gt1 += 1
        elif cmd == "FEED":
            self.feeds += 1
        elif cmd == "HARVEST":
            # crop harvest deixa a celula vazia -> marca para latencia
            if isinstance(cell, dict) and cell.get("kind") == "PLANT":
                self._harvest_at[(pos[0], pos[1])] = turn
        elif cmd == "PLANT":
            key = (pos[0], pos[1])
            if key in self._harvest_at:
                lat = turn - self._harvest_at.pop(key)
                self.replant_lat.append(lat)
            else:
                self._harvest_at.pop(key, None)

    def summary(self):
        prod = self.prod or 1
        n_harvest_plant = len(self.replant_lat)
        return {
            "reward": None,
            "turns": self.turns,
            "hand_turns": self.hand_turns,
            "actions": self.actions_emitted,
            "moves": self.moves,
            "PASS": self.pass_explicit,
            "no_action": self.no_action,
            "prod": self.prod,
            "moves/prod": round(self.moves / prod, 2),
            "pass_share_actions": round(self.pass_explicit / max(1, self.actions_emitted), 3),
            "harvest_to_plant": f"{n_harvest_plant} lat_med=" + (f"{sum(self.replant_lat)/n_harvest_plant:.1f}" if n_harvest_plant else "n/a"),
            "care": self.care,
            "care_at_cap": self.care_at_cap,
            "care_pending>1": self.care_pending_gt1,
            "feeds": self.feeds,
            "pickup": dict(self.pickup),
            "animal_days": self.animal_days,
            "near_cap_turns": self.near_cap_turns,
            "shed_end": dict(self.shed),
            "sells": dict(self.sells),
            "market_orders": dict(self.market_orders),
        }


def run_one(agent, opp_agent, seed, steps):
    from kaggle_environments import make
    tele = Tele()
    # precisa do farm dentro de record_cell_state; empacotamos obs
    state = {}

    def wrap(agent_fn, tele, side):
        def ag(obs, cfg=None):
            act = agent_fn(obs, cfg)
            farm = obs["farms"][obs["player"]]
            tele.record(obs, act)
            # associa acoes as celulas
            if isinstance(act, dict):
                if act.get("farmer"):
                    tele.record_cell_state(act["farmer"], farm.get("farmer"), farm)
                for i, a in enumerate(act.get("hands") or []):
                    poses = farm.get("hands") or []
                    tele.record_cell_state(a, poses[i] if i < len(poses) else None, farm)
            return act
        return ag

    env = make("kaggriculture", configuration={"episodeSteps": steps, "seed": seed})
    env.run([wrap(agent, tele, 0), opp_agent])
    last = env.steps[-1]
    tele.final = last
    r0 = last[0]["reward"] if last[0] else None
    return tele, r0


def parse_seeds(s):
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",") if x]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cands", default="v19,v18,v17")
    ap.add_argument("--opp", default="v18")
    ap.add_argument("--seeds", default="1-3")
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    opp = load(args.opp)
    cands = [c.strip() for c in args.cands.split(",") if c.strip()]
    seeds = parse_seeds(args.seeds)
    agents = {c: load(c) for c in cands}

    print(f"# Telemetria candidatos={cands} vs oponente={args.opp} seeds={seeds}")
    for cand in cands:
        agg = defaultdict(float)
        rewards = []
        for seed in seeds:
            tele, r0 = run_one(agents[cand], opp, seed, args.steps)
            s = tele.summary()
            rewards.append(r0)
            agg["reward"] += (r0 or 0)
            for k in ("hand_turns", "actions", "moves", "PASS", "no_action", "prod",
                      "care", "care_at_cap", "care_pending>1", "feeds",
                      "animal_days", "near_cap_turns"):
                agg[k] += s[k]
            for k in ("moves/prod", "pass_share_actions"):
                agg[k] = None  # recomputa depois
            for k in ("sells", "shed_end"):
                for item, v in s[k].items():
                    agg["%s:%s" % (k, item)] += v
            print(f"  [{cand} seed {seed}] reward={r0} "
                  f"moves/prod={s['moves/prod']} pass_share={s['pass_share_actions']} "
                  f"h2p={s['harvest_to_plant']} care={s['care']}(cap{s['care_at_cap']}) "
                  f"feeds={s['feeds']} pickup={s['pickup']} sells={s['sells']}")
        n = len(seeds)
        sell_keys = [k for k in agg if k.startswith("sells:")]
        sell_str = " ".join(f"{k[6:]}={agg[k]/n:.0f}" for k in sell_keys if agg[k] > 0)
        shed_keys = [k for k in agg if k.startswith("shed_end:")]
        shed_str = " ".join(f"{k[9:]}={agg[k]/n:.0f}" for k in shed_keys if agg[k] > 0)
        print(f"== {cand}: mean_reward={agg['reward']/n:.0f} | "
              f"hand_turns={agg['hand_turns']:.0f} prod={agg['prod']:.0f} "
              f"moves={agg['moves']:.0f} PASS={agg['PASS']:.0f} noact={agg['no_action']:.0f} "
              f"| moves/prod={agg['moves']/max(1,agg['prod']):.2f} "
              f"pass_share={agg['PASS']/max(1,agg['actions']):.3f} "
              f"care={agg['care']:.0f}(cap {agg['care_at_cap']:.0f}) feeds={agg['feeds']:.0f} "
              f"animal_days={agg['animal_days']:.0f} near_cap={agg['near_cap_turns']:.0f}\n"
              f"    sells_med: {sell_str}\n"
              f"    shed_end_med: {shed_str}")


if __name__ == "__main__":
    main()
