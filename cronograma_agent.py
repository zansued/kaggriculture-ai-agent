"""Agente cronograma v1 — escala via zonas fixas + rega absoluta.

Inspirado no c27 (que escala 75 tiles): cada hand tem uma ZONA fixa
(quadrante) e é responsável por regar/colher/cavar/plantar DENTRO dela.
O farmer cuida do shed, dos animais e do quadrante NW.

Prioridade de tarefas (maior urgência primeiro):
  - salvar planta em risco (1 dia sem água)  -> regar
  - animal: coletar fertilizante / produto     -> coletar
  - planta precisa água                        -> regar
  - planta pronta                              -> colher
  - weed                                       -> cavar
  - vazio com semente e capacidade             -> plantar

Regra de capacidade: nunca plantar além do que as hands conseguem regar.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'src'))

from kaggriculture_real import (  # noqa: E402
    CROPS, ANIMALS, SEASON_DAYS, MAX_MARKET_ORDERS,
    PASS, NORTH, SOUTH, EAST, WEST, MOVES,
    WATER, HARVEST, DIG, PLANT, BUILD_PASTURE,
    FEED, CARE, COLLECT_FERTILIZER, PICKUP, PLACE,
    BUY_SEED, BUY_ANIMAL, BUY_PRODUCT, SELL, HIRE, BUY_LAND,
    KIND_PLANT, KIND_WEED, KIND_PASTURE,
    build_action, my_farm, farmer_xy, _shed_tile, _fib, SHED_TILES,
)

KIND_COOP = "COOP"


def _quadrant(x: int, y: int) -> str:
    if x < 5 and y < 5:
        return "NW"
    if x >= 5 and y < 5:
        return "NE"
    if x < 5 and y >= 5:
        return "SW"
    return "SE"


class CronogramaAgent:
    def __init__(
        self,
        animal_plan=(("COW", 8), ("SHEEP", 6)),
        buy_land_day=11,
        max_hands=10,
        wheat_cap_per_hand=7,
        premium_cap_per_hand=3,
        animal_days=None,
    ):
        self.animal_plan = list(animal_plan)
        self.buy_land_day = buy_land_day
        self.max_hands = max_hands
        self.wheat_cap_per_hand = wheat_cap_per_hand
        self.premium_cap_per_hand = premium_cap_per_hand
        # cronograma de compra de animais: dias em que compramos (1-based).
        # DEFAULT OFF (vazio): hoje os animais são NET-NEGATIVE no cronograma
        # (medido: crop-only 25-29k > animals-on 16-17k) porque a economia de
        # produção ainda não sustenta a colocação + alimentação de 14 animais.
        # Ative quando a produção escalar (via CronogramaAgent(animal_days={...})).
        self.animal_days = animal_days or {}
        self._n_animals_owned = {a: 0 for a, _ in animal_plan}

    # ---- entry ---------------------------------------------------------- #
    def decide(self, obs):
        farm = my_farm(obs)
        private = obs.get("private", {})
        day = int(obs.get("day", 0))
        hour = int(obs.get("hour", 0))

        market = self._market(obs, farm, private, day, hour)
        cmds = self._units(obs, farm, private, day)
        farmer_cmd = cmds[0] if cmds else [PASS]
        hands_cmds = cmds[1:] if len(cmds) > 1 else []
        return build_action(farmer_cmd, hands_cmds, market)

    # ---- 1. mercado ------------------------------------------------------ #
    def _market(self, obs, farm, private, day, hour):
        ops = []
        shed = private.get("shed", {})
        seeds = private.get("seeds", {})
        money = float(farm.get("money", 0.0))
        prices = obs.get("market", {}).get("prices", {})
        invs = private.get("inventories", [])
        n_hands = len(farm.get("hands", []))

        # 1) Vender tudo do shed (em massa, priorizando valor). Mas RESERVA
        #    wheat para alimentar animais — se vendermos tudo, eles passam fome
        #    e fogem (investimento jogado fora). Reserva ~4/dia por animal.
        n_animals = self._count_animal(farm, "COW") + self._count_animal(farm, "SHEEP") \
            + int(shed.get("COW", 0) or 0) + int(shed.get("SHEEP", 0) or 0)
        feed_need = n_animals * 2  # 2 wheat/animal/dia
        for item, qty in shed.items():
            q = int(qty)
            if q <= 0 or item in ANIMALS:
                continue
            if item == "WHEAT" and day < SEASON_DAYS - 2:
                keep = max(0, feed_need - 10)
                q = max(0, q - keep)
            if q <= 0:
                continue
            ops.append([SELL, item, q])
            money += q * prices.get(item, 0)
            if len(ops) >= MAX_MARKET_ORDERS:
                return ops[:MAX_MARKET_ORDERS]

        # 2) Sementes em BURSTS (estilo purearch) — PRIORIDADE sobre animais:
        #    o motor de colheita é quem financia o resto. Só no início do dia.
        if hour == 0:
            n_plants = self._count_plants(farm)
            cap = self._capacity(farm)
            room = max(0, cap - n_plants)
            # melon: burst dias 0-3 (até 12 plantas)
            if day <= 3 and room > 0:
                n_melon = self._count_crop(farm, "MELON")
                to_buy = min(5, room, max(0, 12 - n_melon))
                if to_buy > 0 and money >= CROPS["MELON"]["seed"] * to_buy:
                    ops.append([BUY_SEED, "MELON", to_buy])
                    money -= CROPS["MELON"]["seed"] * to_buy
            # strawberry: burst dias 5-12 (até o cap de premium)
            if 5 <= day <= 12 and room > 0:
                n_straw = self._count_crop(farm, "STRAWBERRY")
                target = self.premium_cap_per_hand * max(1, self.max_hands)
                have_s = seeds.get("STRAWBERRY", 0)
                to_buy = min(5, room, max(0, target - n_straw - have_s))
                if to_buy > 0 and money >= CROPS["STRAWBERRY"]["seed"] * to_buy:
                    ops.append([BUY_SEED, "STRAWBERRY", to_buy])
                    money -= CROPS["STRAWBERRY"]["seed"] * to_buy
            # wheat: preenche o resto (até 8/turno)
            if room > 0:
                n_wheat = self._count_crop(farm, "WHEAT")
                have_w = seeds.get("WHEAT", 0)
                to_buy = min(8, room, max(0, 30 - n_wheat - have_w))
                if to_buy > 0 and money >= CROPS["WHEAT"]["seed"] * to_buy:
                    ops.append([BUY_SEED, "WHEAT", to_buy])
                    money -= CROPS["WHEAT"]["seed"] * to_buy
            if len(ops) >= MAX_MARKET_ORDERS:
                return ops[:MAX_MARKET_ORDERS]

        # 3) Hands (até max_hands, custo fib). Limitado a 2/turno para espalhar
        #    o custo; funciona em qualquer hora do dia (hands resetam diário).
        if n_hands < self.max_hands:
            n_hired = int(farm.get("hires_today", 0))
            for _ in range(min(2, self.max_hands - n_hands)):
                cost = _fib(n_hired)
                if money < cost:
                    break
                ops.append([HIRE])
                money -= cost
                n_hired += 1
            if len(ops) >= MAX_MARKET_ORDERS:
                return ops[:MAX_MARKET_ORDERS]

        # 4) Animais no cronograma (comprar a cada dia conforme plano).
        #    Só se houver folga de caixa (money > 3x o custo do animal).
        day_qty = self.animal_days.get(day, 0)
        if hour == 0 and day_qty > 0:
            remaining = day_qty
            for animal, target in self.animal_plan:
                if remaining <= 0:
                    break
                a = ANIMALS[animal]
                placed = self._count_animal(farm, animal)
                owned = placed + int(shed.get(animal, 0) or 0)
                to_buy = min(remaining, max(0, target - owned))
                if to_buy > 0 and money >= a["cost"] * to_buy * 3:
                    ops.append([BUY_ANIMAL, animal, to_buy])
                    money -= a["cost"] * to_buy
                    remaining -= to_buy
            if len(ops) >= MAX_MARKET_ORDERS:
                return ops[:MAX_MARKET_ORDERS]

        # 5) Terra no dia programado (só no início do dia, com folga).
        n_unlocked = len(farm.get("unlocked_quadrants", []))
        if hour == 0 and self.buy_land_day and day >= self.buy_land_day and n_unlocked < 3:
            next_cost = (1000, 2000, 4000)[n_unlocked - 1]
            if money >= next_cost + 1500:
                ops.append([BUY_LAND])
                money -= next_cost

        return ops[:MAX_MARKET_ORDERS]

    # ---- 2. unidades ----------------------------------------------------- #
    def _units(self, obs, farm, private, day):
        tiles = farm.get("tiles", [])
        size = len(tiles)
        seeds = private.get("seeds", {})
        sheds = set(SHED_TILES)
        positions = [tuple(farm["farmer"])] + [tuple(h) for h in farm.get("hands", [])]
        assigned = set()  # alvos já escolhidos por outra unidade
        cmds = []
        # O farmer é a unidade 0; as hands têm zonas.
        for i, pos in enumerate(positions):
            x, y = pos
            cmd, target = self._unit_action(
                obs, farm, private, day, i, x, y, tiles, size, seeds, sheds, assigned
            )
            if target is not None:
                assigned.add(target)
            cmds.append(cmd)
        return cmds

    def _unit_action(self, obs, farm, private, day, i, x, y, tiles, size, seeds, sheds, assigned):
        inv = self._inv(obs, i)
        tile = tiles[y][x] if 0 <= y < size and 0 <= x < size else None
        shed = private.get("shed", {})

        # Carregando animal? NUNCA deixe o bloco de depósito engolir a unidade
        # (era o livelock: load>0 com apenas COW/SHEEP no inv -> movia pro shed
        #  eternamente, sem nunca chegar ao PLACE).
        carrying_animal = any(int(inv.get(a, 0) or 0) > 0 for a in ("COW", "SHEEP"))
        shed_has_animal = any(int(shed.get(a, 0) or 0) > 0 for a in ("COW", "SHEEP"))

        # A0) depositar produtos no shed (SÓ não-animais) ----------------------
        load = sum(max(0, int(v or 0)) for v in inv.values())
        if load > 0 and not carrying_animal:
            _prod = [k for k, v in inv.items() if int(v or 0) > 0 and k not in ANIMALS]
            _prod.sort(key=lambda k: -int(inv[k] or 0))
            if _prod and (x, y) in sheds:
                return ([PLACE, _prod[0], int(inv[_prod[0]])], None)
            if _prod:
                t = min(sheds, key=lambda q: abs(q[0] - x) + abs(q[1] - y))
                return (self._move(x, y, t[0], t[1], tiles), t)

        # A0b) colocar animais comprados (cadeia PICKUP -> BUILD -> PLACE) ----
        # SÓ o farmer (i==0) coloca animais — se as hands ajudam, a colocação
        # preempta as colheitas e a fazenda não escala (medido: animals-on 11-14k
        # vs animals-off 24-30k). Farmer dedicado = padrão kawashigi.
        if (shed_has_animal or carrying_animal) and i == 0:
            animal = "COW" if (int(shed.get("COW", 0) or 0) > 0 or int(inv.get("COW", 0) or 0) > 0) else "SHEEP"
            a = ANIMALS[animal]
            pasture_xy = self._find_empty_pasture(farm, animal, size)
            if pasture_xy is None:
                build_xy = self._first_empty_tile(farm, size)
                if build_xy is not None:
                    if (x, y) == build_xy:
                        return ([BUILD_PASTURE], None)
                    return (self._move(x, y, build_xy[0], build_xy[1], tiles), build_xy)
                return ([PASS], None)
            if int(inv.get(animal, 0) or 0) <= 0:
                st = min(sheds, key=lambda q: abs(q[0] - x) + abs(q[1] - y))
                if (x, y) == st:
                    return ([PICKUP, animal, 1], None)
                return (self._move(x, y, st[0], st[1], tiles), st)
            if (x, y) == pasture_xy:
                return ([PLACE, animal, 1], None)
            return (self._move(x, y, pasture_xy[0], pasture_xy[1], tiles), pasture_xy)

        # A) tarefa imediata no tile atual ----------------------------------
        if isinstance(tile, dict):
            kind = tile.get("kind")
            if kind == KIND_PLANT:
                crop = tile.get("crop")
                cd = CROPS.get(crop)
                needs_water = not tile.get("watered_today", False)
                y_units = int(tile.get("yield_units", 0) or 0)
                age = day - int(tile.get("planted_day", day))
                if cd:
                    if cd["ongoing"]:
                        if y_units >= cd["max_yield"]:
                            return ([HARVEST], None)
                        if y_units > 0 and needs_water:
                            return ([WATER], None)
                        if needs_water:
                            return ([WATER], None)
                        # colhe só no max_yield; yield parcial continua crescendo
                    else:
                        at_cap = y_units >= cd["max_yield"]
                        if (age >= cd["max_yield_day"] or (at_cap and y_units > 0)) and y_units > 0:
                            return ([HARVEST], None)
                        if needs_water:
                            return ([WATER], None)
            elif kind == KIND_PASTURE or kind == KIND_COOP:
                if tile.get("fertilizer_available", False):
                    return ([COLLECT_FERTILIZER], None)
                if int(tile.get("yield_units", 0) or 0) > 0:
                    return ([HARVEST], None)
                if not tile.get("fed_today", False) and inv.get("WHEAT", 0) > 0:
                    return ([FEED], None)
                if not tile.get("cared_today", False):
                    return ([CARE], None)
            elif kind == KIND_WEED:
                return ([DIG], None)
        elif tile is None and i == 0:
            crop = self._choose_plant(farm, private, day, seeds)
            if crop and self._capacity(farm) > self._count_plants(farm):
                return ([PLANT, crop], None)

        # C) mover para a tarefa mais urgente --------------------------------
        target, task, act = self._best_task(farm, obs, day, x, y, tiles, size, seeds, private, i, assigned)
        if target is None:
            return ([PASS], None)
        # Feed choreography: FEED precisa wheat no inventário. Se não tem,
        # desvia pro shed pegar wheat primeiro (senão chega e não alimenta).
        if act == [FEED] and int(inv.get("WHEAT", 0) or 0) <= 0:
            st = min(sheds, key=lambda q: abs(q[0] - x) + abs(q[1] - y))
            if (x, y) == st:
                return ([PICKUP, "WHEAT", 1], None)
            return (self._move(x, y, st[0], st[1], tiles), st)
        if (x, y) == target:
            return (act, target)
        return (self._move(x, y, target[0], target[1], tiles), target)

    def _best_task(self, farm, obs, day, x, y, tiles, size, seeds, private, unit_i, assigned=None):
        """Retorna (target_xy, descricao, acao) da tarefa de maior urgência."""
        zone = _quadrant(x, y)
        # para o farmer (0), zona = NW + animais; para hands, zona fixa.
        # mapa de zonas: hand i -> quadrante (rotaciona conforme unlocked)
        unlocked = farm.get("unlocked_quadrants", ["NW"])
        zone_order = ["NW", "NE", "SW"]
        # unidade i cuida de zone_order[i % len(zone_order)]
        if unit_i == 0:
            my_zone = "NW"
        else:
            idx = unit_i % 3
            my_zone = zone_order[idx] if zone_order[idx] in unlocked else "NW"

        best = None
        best_key = None
        assigned = assigned or set()

        for yy in range(size):
            for xx in range(size):
                if _quadrant(xx, yy) != my_zone:
                    continue
                if (xx, yy) in assigned:
                    continue
                if tiles[yy][xx] is None:
                    # plantio em tile vazio: prioridade 20 (abaixo de regar 28,
                    # acima de weed 15) — plantio não pode ser o último recurso.
                    crop = self._choose_plant(farm, private, day, seeds)
                    if crop and self._capacity(farm) > self._count_plants(farm):
                        d = abs(xx - x) + abs(yy - y)
                        score = 20 * 100 - d
                        if best_key is None or score > best_key:
                            best_key = score
                            best = ((xx, yy), [PLANT, crop])
                    continue
                t = tiles[yy][xx]
                if not isinstance(t, dict):
                    continue
                kind = t.get("kind")
                key = None
                act = None
                if kind == KIND_PLANT:
                    crop = t.get("crop")
                    cd = CROPS.get(crop)
                    needs_water = not t.get("watered_today", False)
                    risk = int(t.get("consecutive_unwatered", 0) or 0) >= 1
                    y_units = int(t.get("yield_units", 0) or 0)
                    age = day - int(t.get("planted_day", day))
                    if cd and cd["ongoing"]:
                        if y_units >= cd["max_yield"]:
                            key, act = 38, [HARVEST]
                        elif y_units > 0 and needs_water:
                            key, act = 25, [WATER]  # rega antes de perder
                        elif risk:
                            key, act = 45, [WATER]
                        elif needs_water:
                            key, act = 28, [WATER]
                        # NÃO colher ongoing com yield parcial: espera max_yield
                        # (colher cedo = 1-3 units em vez de 4).
                    elif cd:
                        at_cap = y_units >= cd["max_yield"]
                        if (age >= cd["max_yield_day"] or at_cap) and y_units > 0:
                            key, act = 38, [HARVEST]
                        elif risk:
                            key, act = 45, [WATER]
                        elif needs_water:
                            key, act = 28, [WATER]
                elif kind == KIND_WEED:
                    key, act = 15, [DIG]
                elif kind == KIND_PASTURE or kind == KIND_COOP:
                    if not t.get("animal"):
                        continue  # pasto vazio: nada a fazer
                    risk = int(t.get("consecutive_unfed", 0) or 0) >= 1
                    if risk or not t.get("fed_today", False):
                        # SOBREVIVÊNCIA primeiro: alimentar (30) antes de coletar
                        # fertilizante (20) — animal faminto foge e perde tudo.
                        key, act = 30, [FEED]
                    elif t.get("fertilizer_available", False):
                        key, act = 20, [COLLECT_FERTILIZER]
                    elif int(t.get("yield_units", 0) or 0) > 0:
                        key, act = 35, [HARVEST]
                    elif not t.get("cared_today", False):
                        key, act = 12, [CARE]

                if key is not None:
                    dist = abs(xx - x) + abs(yy - y)
                    # urgência - custo de movimento
                    score = key * 100 - dist
                    if best_key is None or score > best_key:
                        best_key = score
                        best = ((xx, yy), act)
        return (best[0], None, best[1]) if best else (None, None, [PASS])

    def _choose_plant(self, farm, private, day, seeds):
        n_w = self._count_crop(farm, "WHEAT")
        n_s = self._count_crop(farm, "STRAWBERRY")
        n_m = self._count_crop(farm, "MELON")
        if day <= 5 and n_m < 9 and seeds.get("MELON", 0) > 0:
            return "MELON"
        if 5 <= day <= 16 and n_s < self.premium_cap_per_hand * max(1, self.max_hands) and seeds.get("STRAWBERRY", 0) > 0:
            return "STRAWBERRY"
        if seeds.get("WHEAT", 0) > 0:
            return "WHEAT"
        return None

    # ---- helpers ----------------------------------------------------------- #
    def _inv(self, obs, i):
        invs = obs.get("private", {}).get("inventories", [])
        return invs[i] if i < len(invs) else {}

    def _count_animal(self, farm, animal):
        tiles = farm.get("tiles", [])
        return sum(
            1 for y in range(len(tiles)) for x in range(len(tiles[y]))
            if isinstance(tiles[y][x], dict) and tiles[y][x].get("animal") == animal
        )

    def _count_plants(self, farm):
        tiles = farm.get("tiles", [])
        return sum(
            1 for y in range(len(tiles)) for x in range(len(tiles[y]))
            if isinstance(tiles[y][x], dict) and tiles[y][x].get("kind") == KIND_PLANT
        )

    def _count_crop(self, farm, crop):
        tiles = farm.get("tiles", [])
        return sum(
            1 for y in range(len(tiles)) for x in range(len(tiles[y]))
            if isinstance(tiles[y][x], dict)
            and tiles[y][x].get("kind") == KIND_PLANT
            and tiles[y][x].get("crop") == crop
        )

    def _capacity(self, farm):
        # IMPORTANTE: no hour 0 (quando compramos sementes) as hands JÁ
        # resetaram (len=0), então usar n_hands atual trava a capacidade em ~10.
        # Usamos max_hands planejado para a fazenda poder escalar.
        n_hands = self.max_hands
        return self.wheat_cap_per_hand * max(1, n_hands) + \
            self.premium_cap_per_hand * max(1, n_hands)

    def _move(self, x, y, tx, ty, tiles):
        if tx < x:
            op, nx, ny = WEST, x - 1, y
        elif tx > x:
            op, nx, ny = EAST, x + 1, y
        elif ty < y:
            op, nx, ny = NORTH, x, y - 1
        elif ty > y:
            op, nx, ny = SOUTH, x, y + 1
        else:
            return [PASS]
        if 0 <= nx < len(tiles) and 0 <= ny < len(tiles) and tiles[ny][nx] != "LOCKED":
            return [op]
        return [PASS]

    def _find_empty_pasture(self, farm, animal, size):
        """Pasture vazio (sem animal) ou com o mesmo animal com slot livre."""
        a = ANIMALS[animal]
        tiles = farm.get("tiles", [])
        best = None
        best_d = 10 ** 9
        for y in range(size):
            for x in range(size):
                t = tiles[y][x]
                if not (isinstance(t, dict) and t.get("kind") == KIND_PASTURE):
                    continue
                cur = t.get("animal")
                if cur is None:
                    d = abs(x - 4) + abs(y - 4)
                    if d < best_d:
                        best_d = d
                        best = (x, y)
                elif cur == animal and int(t.get("held_count", 1) or 1) < a["max_held"]:
                    d = abs(x - 4) + abs(y - 4)
                    if d < best_d:
                        best_d = d
                        best = (x, y)
        return best

    def _first_empty_tile(self, farm, size):
        tiles = farm.get("tiles", [])
        best = None
        best_d = 10 ** 9
        for y in range(size):
            for x in range(size):
                if (x, y) in SHED_TILES:
                    continue
                if tiles[y][x] is None:
                    d = abs(x - 4) + abs(y - 4)
                    if d < best_d:
                        best_d = d
                        best = (x, y)
        return best


_agent = CronogramaAgent()


def agent(obs, config=None):
    return _agent.decide(obs)
