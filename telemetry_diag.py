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

# Parametros animais do engine (first_yield_day, interval, max_held, custo fixo).
ANIM = {
    "GOOSE": {"first": 4, "interval": 1, "cap": 4, "cost": 300},
    "COW":   {"first": 8, "interval": 2, "cap": 6, "cost": 400},
    "SHEEP": {"first": 6, "interval": 3, "cap": 6, "cost": 500},
}


def _fib(n):
    """fib indexado como no engine: _fib(0)=1, _fib(1)=1, _fib(2)=2, _fib(3)=3..."""
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


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

        # --- instrumentacao hires (HIRE order != hand pago) ---
        self.hire_orders = 0        # ordens ["HIRE"] emitidas no market do act
        self.successful_hires = 0   # incremento REAL de len(farm.hands) intra-dia
        self.hire_cost = 0          # custo fibonacci reconstruido (mult=1)
        self.prev_n_hands = 0
        self.hired_hand_turns = 0   # soma de hands presentes por turno (sem farmer)

        # --- instrumentacao CARE realizacao / clipping por transicao de dia ---
        self._last_day = None
        self._last_pastures = {}
        self.prod_nights = 0         # noites em que algum animal produziu
        self.prod_nights_fed = 0     # noites produtivas em que o animal estava fed
        self.base_units = 0          # unidades base (sem bonus) que entraram
        self.care_consumed = 0       # pending usado em noite produtiva COM feed
        self.care_realized = 0       # do pending, qto virou yield (nao clipado)
        self.care_clipped = 0        # do pending, qto foi perdido por max_held
        self.care_lost_no_feed = 0   # pending ZERADO por produzir sem feed (l.815 engine)
        self.prod_clipped_total = 0  # unidades totais clipadas por max_held (base+bonus)

        # --- logistica WHEAT ---
        self.wheat_pickups = 0       # comandos PICKUP WHEAT
        self.wheat_units = 0         # unidades pedidas em PICKUP WHEAT n

        # --- slack de expansao diario ---
        self.daily = {}              # day -> registro (caixa, rebanho, precos, hires, buys)

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

    def _snapshot_pastures(self, farm):
        """Estado dos pastos com animal no obs atual (pre-acao)."""
        snap = {}
        tiles = farm.get("tiles") or []
        for yy, row in enumerate(tiles):
            for xx, cell in enumerate(row):
                if isinstance(cell, dict) and cell.get("animal"):
                    snap[(xx, yy)] = {
                        "animal": cell["animal"],
                        "placed": int(cell.get("placed_day", 0) or 0),
                        "yield": int(cell.get("yield_units", 0) or 0),
                        "pend": int(cell.get("pending_care_bonus", 0) or 0),
                        "fed": bool(cell.get("fed_today")),
                        "cared": bool(cell.get("cared_today")),
                    }
        return snap

    def _transit_pastures(self, prev_snap, farm, new_day):
        """Analisa a producao da virada de dia (engine _daily_refresh_animals).

        prev_snap: estado do ULTIMO turno do dia anterior (flags do dia que
        terminou). farm/obs atual: ja pos-producao (primeiro turno do novo dia).
        So mede quando a producao acontece (dia produtivo do animal).
        """
        tiles = farm.get("tiles") or []
        for (xx, yy), p in prev_snap.items():
            cell = None
            if 0 <= yy < len(tiles):
                row = tiles[yy]
                if 0 <= xx < len(row) and isinstance(row[xx], dict) and row[xx].get("animal"):
                    cell = row[xx]
            if cell is None:
                continue  # animal fugiu / tile mudou
            a = ANIM.get(p["animal"])
            if not a:
                continue
            dias = new_day - p["placed"] - a["first"]
            if dias < 0 or dias % a["interval"] != 0:
                continue  # noite nao produtiva para este animal
            cap = a["cap"]
            self.prod_nights += 1
            base = 1
            y_exp = p["yield"] + base
            if p["fed"]:
                self.prod_nights_fed += 1
                bonus = p["pend"]
                y_exp += bonus
                if bonus > 0:
                    self.care_consumed += bonus
                    entered = max(0, min(cap, y_exp) - (p["yield"] + base))
                    self.care_realized += entered
                    self.care_clipped += max(0, bonus - entered)
            else:
                # produziu sem feed: pending e zerado no engine (linha 815)
                self.care_lost_no_feed += p["pend"]
            self.prod_clipped_total += max(0, y_exp - cap)
            self.base_units += max(0, min(cap, p["yield"] + base) - p["yield"])

    def _note_daily(self, obs, farm, day):
        """Registra caixa/rebanho/precos/hires do dia (slack de expansao)."""
        d = self.daily.setdefault(day, {
            "money_open": None, "money_close": None,
            "cows": 0, "sheep": 0, "goose": 0,
            "pastures_total": 0, "pastures_empty": 0,
            "cow_price_open": None, "cow_price": None,
            "sheep_price_open": None, "sheep_price": None,
            "goose_price_open": None, "goose_price": None,
            "hires_day": 0, "hire_cost_day": 0,
            "cow_buys": 0, "sheep_buys": 0, "goose_buys": 0,
        })
        money = int(farm.get("money", 0) or 0)
        if d["money_open"] is None:
            d["money_open"] = money
        d["money_close"] = money
        cows = sheep = goose = ptotal = pempty = 0
        for row in farm.get("tiles") or []:
            for cell in row:
                if not isinstance(cell, dict):
                    continue
                a = cell.get("animal")
                if a:
                    # tile ocupado por animal (kind = PASTURE/COOP + key "animal")
                    if a == "COW":
                        cows += 1
                    elif a == "SHEEP":
                        sheep += 1
                    elif a == "GOOSE":
                        goose += 1
                elif cell.get("kind") in ("PASTURE", "COOP"):
                    pempty += 1
        ptotal = cows + sheep + goose + pempty
        d["cows"] = cows
        d["sheep"] = sheep
        d["goose"] = goose
        d["pastures_total"] = ptotal
        d["pastures_empty"] = pempty
        # precos de animal sao FIXOS no engine (ANIMALS[item]["cost"]); nao vem do market
        for item, key in (("COW", "cow_price"), ("SHEEP", "sheep_price"), ("GOOSE", "goose_price")):
            cost = ANIM[item]["cost"]
            if d[key + "_open"] is None:
                d[key + "_open"] = cost
            d[key] = cost
        return d

    def daily_report(self):
        """Linhas dia a dia: caixa de abertura, rebanho, preco COW, quantos COW
        'cabiam' no caixa (money_open // cow_price), compras e hires do dia."""
        rows = []
        for day in sorted(self.daily):
            d = self.daily[day]
            mopen = d["money_open"] if d["money_open"] is not None else 0
            cprice = d["cow_price_open"] or d["cow_price"] or 0
            afford = int(mopen // cprice) if cprice > 0 else 0
            rows.append({
                "day": day, "money_open": mopen, "money_close": d["money_close"],
                "cows": d["cows"], "sheep": d["sheep"], "goose": d["goose"],
                "pastures_total": d["pastures_total"], "pastures_empty": d["pastures_empty"],
                "cow_price": cprice, "afford_cow": afford,
                "cow_buys": d["cow_buys"],
                "hires_day": d["hires_day"], "hire_cost_day": d["hire_cost_day"],
            })
        return rows

    def record(self, obs, act):
        self.turns += 1
        farm = obs["farms"][obs["player"]]
        n_hands = len(farm.get("hands") or [])
        self.hand_turns += 1 + n_hands
        self._note_cells(farm)

        # --- hires: ordem != hand pago (engine zera hands/hires_today no fim do dia) ---
        day = int(obs.get("day", 0) or 0)
        self._note_daily(obs, farm, day)
        if self._last_day is None:
            # primeiro turno do jogo (hands comecam zerados no dia 0)
            self.prev_n_hands = n_hands
        elif day > self._last_day:
            # virada de dia: mede a producao animal da noite que passou
            self._transit_pastures(self._last_pastures, farm, day)
            # hands foram resetados para [] no end_of_day
            self.prev_n_hands = n_hands
        else:
            if n_hands > self.prev_n_hands:
                diff = n_hands - self.prev_n_hands
                self.successful_hires += diff
                for k in range(self.prev_n_hands, n_hands):
                    c = _fib(k)
                    self.hire_cost += c
                    self.daily[day]["hire_cost_day"] += c
            self.prev_n_hands = n_hands
        self.hired_hand_turns += n_hands
        self._last_pastures = self._snapshot_pastures(farm)
        self._last_day = day

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
            if t == "HIRE":
                self.hire_orders += 1
                self.daily[day]["hires_day"] += 1
            if t == "SELL" and len(o) >= 3:
                self.sells[o[1]] += o[2]
            elif t in ("BUY_PRODUCT", "BUY_ANIMAL", "BUY_SEED") and len(o) >= 3:
                self.buys[o[1]] += o[2]
                if t == "BUY_ANIMAL":
                    dd = self.daily[day]
                    if o[1] == "COW":
                        dd["cow_buys"] += o[2]
                    elif o[1] == "SHEEP":
                        dd["sheep_buys"] += o[2]
                    elif o[1] == "GOOSE":
                        dd["goose_buys"] += o[2]

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
            item = action[1] if len(action) > 1 else None
            if item == "WHEAT":
                self.wheat_pickups += 1
                try:
                    self.wheat_units += int(action[2]) if len(action) > 2 else 1
                except (TypeError, ValueError):
                    self.wheat_units += 1
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
            "hire_orders": self.hire_orders,
            "successful_hires": self.successful_hires,
            "hire_cost": self.hire_cost,
            "hired_hand_turns": self.hired_hand_turns,
            "prod_nights": self.prod_nights,
            "prod_nights_fed": self.prod_nights_fed,
            "base_units": self.base_units,
            "care_consumed": self.care_consumed,
            "care_realized": self.care_realized,
            "care_clipped": self.care_clipped,
            "care_lost_no_feed": self.care_lost_no_feed,
            "prod_clipped_total": self.prod_clipped_total,
            "wheat_pickups": self.wheat_pickups,
            "wheat_units": self.wheat_units,
            "feeds_per_pickup": round(self.feeds / max(1, self.wheat_pickups), 2),
            "care_realization": round(self.care_realized / max(1, self.care), 3),
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
    ap.add_argument("--daily", action="store_true",
                    help="imprime tabela dia a dia do slack de expansao")
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
                      "animal_days", "near_cap_turns", "hire_orders", "successful_hires",
                      "hire_cost", "hired_hand_turns", "prod_nights", "prod_nights_fed",
                      "base_units", "care_consumed", "care_realized", "care_clipped",
                      "care_lost_no_feed", "prod_clipped_total", "wheat_pickups", "wheat_units"):
                agg[k] += s[k]
            for k in ("moves/prod", "pass_share_actions", "feeds_per_pickup", "care_realization"):
                agg[k] = None  # recomputa depois
            for k in ("sells", "shed_end"):
                for item, v in s[k].items():
                    agg["%s:%s" % (k, item)] += v
            print(f"  [{cand} seed {seed}] reward={r0} "
                  f"moves/prod={s['moves/prod']} pass_share={s['pass_share_actions']} "
                  f"h2p={s['harvest_to_plant']} care={s['care']}(cap{s['care_at_cap']}) "
                  f"feeds={s['feeds']} pickup={s['pickup']} sells={s['sells']} "
                  f"hires={s['successful_hires']}/{s['hire_orders']} cost={s['hire_cost']}")
            if args.daily:
                print("    -- slack diario: d | money_open | cows sheep goose | past(empty) | cow_price | afford | cow_buys | hires(cost)")  # noqa: E501
                for r in tele.daily_report():
                    print(f"    d{r['day']:>2} | {r['money_open']:>7} | {r['cows']} {r['sheep']} {r['goose']} "
                          f"| {r['pastures_total']}({r['pastures_empty']}) | {r['cow_price']:>4} "
                          f"| {r['afford_cow']:>2} | {r['cow_buys']} | {r['hires_day']}({r['hire_cost_day']})")
        n = len(seeds)
        sell_keys = [k for k in agg if k.startswith("sells:")]
        sell_str = " ".join(f"{k[6:]}={agg[k]/n:.0f}" for k in sell_keys if agg[k] > 0)
        shed_keys = [k for k in agg if k.startswith("shed_end:")]
        shed_str = " ".join(f"{k[9:]}={agg[k]/n:.0f}" for k in shed_keys if agg[k] > 0)
        care_r = agg["care_realized"] / max(1, agg["care"])
        fpp = agg["feeds"] / max(1, agg["wheat_pickups"])
        print(f"== {cand}: mean_reward={agg['reward']/n:.0f} | "
              f"hand_turns={agg['hand_turns']:.0f} prod={agg['prod']:.0f} "
              f"moves={agg['moves']:.0f} PASS={agg['PASS']:.0f} noact={agg['no_action']:.0f} "
              f"| moves/prod={agg['moves']/max(1,agg['prod']):.2f} "
              f"pass_share={agg['PASS']/max(1,agg['actions']):.3f} "
              f"care={agg['care']:.0f}(cap {agg['care_at_cap']:.0f}) feeds={agg['feeds']:.0f} "
              f"animal_days={agg['animal_days']:.0f} near_cap={agg['near_cap_turns']:.0f}\n"
              f"    HIRE orders={agg['hire_orders']:.0f} success={agg['successful_hires']:.0f} "
              f"cost={agg['hire_cost']:.0f} hired_hand_turns={agg['hired_hand_turns']:.0f}\n"
              f"    CARE issued={agg['care']:.0f} consumed={agg['care_consumed']:.0f} "
              f"realized={agg['care_realized']:.0f} clipped={agg['care_clipped']:.0f} "
              f"lost_nofeed={agg['care_lost_no_feed']:.0f} | realization={care_r:.2f}\n"
              f"    PROD nights={agg['prod_nights']:.0f} fed={agg['prod_nights_fed']:.0f} "
              f"base_units={agg['base_units']:.0f} clip_total={agg['prod_clipped_total']:.0f}\n"
              f"    WHEAT pickups={agg['wheat_pickups']:.0f} units={agg['wheat_units']:.0f} "
              f"feeds_per_pickup={fpp:.2f}\n"
              f"    sells_med: {sell_str}\n"
              f"    shed_end_med: {shed_str}")


if __name__ == "__main__":
    main()
