"""episode_profile.py — perfil estrutural de um player a partir de replay Kaggle.

Decoder por ESTADO (obs), não por contagem ingênua de ações:
  - tiles com kind=PLANT  -> crops de pé (WHEAT/CARROT/...)
  - tiles com kind=PASTURE/COOP com campo 'animal' -> animais VIVOS (COW/SHEEP/GOOSE)
  - farms.hands (len)     -> mão de obra do dia
  - farms.hires_today     -> hires ativos no dia
  - farms.money, farms.unlocked_quadrants, farms.tiles
  - private.shed/inventories -> estoque

Ações também são somadas para PLANT/BUY_ANIMAL/HIRE/BUILD/SELL (cross-check).

Uso:
    python episode_profile.py <replay.json> <player> [--json out.json]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

CROPS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON']
ANIMALS = ['COW', 'SHEEP', 'GOOSE']


def farm_of(frame, player):
    obs = frame.get('observation') or {}
    farms = obs.get('farms') or []
    return farms[player] if player < len(farms) else {}


def iter_tiles(f0):
    for row in (f0.get('tiles') or []):
        if isinstance(row, list):
            for t in row:
                if isinstance(t, dict):
                    yield t


def decode(path, player, verbose=False):
    data = json.load(open(path, encoding='utf-8'))
    steps = data.get('steps') or []
    names = (data.get('info') or {}).get('TeamNames') or ['?', '?']
    rewards = data.get('rewards') or []
    n_days = len(steps) // 24

    # contadores de ações (cross-check)
    plant = collections.Counter()
    buy_animal = collections.Counter()
    seed = collections.Counter()
    sell = collections.Counter()
    hire = 0
    build = collections.Counter()
    feed = 0
    care = 0

    eod = []          # snapshots por dia
    for i, frame in enumerate(steps):
        act = frame[player].get('action') or {}
        for o in (act.get('farmer') or []) + (act.get('hands') or []):
            if not isinstance(o, list) or not o:
                continue
            op = o[0]
            item = o[1] if len(o) > 1 else None
            if op == 'PLANT' and item in CROPS:
                plant[item] += 1
            elif op in ('BUILD_PASTURE', 'BUILD_COOP'):
                build[op.replace('BUILD_', '')] += 1
            elif op == 'FEED':
                feed += 1
            elif op == 'CARE':
                care += 1
        for o in (act.get('market') or []):
            if not isinstance(o, list) or not o:
                continue
            op = o[0]
            item = o[1] if len(o) > 1 else None
            qty = int(o[2]) if len(o) > 2 and str(o[2]).lstrip('-').isdigit() else 1
            if op == 'BUY_ANIMAL' and item in ANIMALS:
                buy_animal[item] += 1
            elif op == 'BUY_SEED' and item in CROPS:
                seed[item] += qty
            elif op == 'SELL' and item:
                sell[item] += qty
            elif op == 'HIRE':
                hire += 1
            elif op in ('BUILD_PASTURE', 'BUILD_COOP'):
                build[op.replace('BUILD_', '')] += 1

        if i % 24 == 23:
            f0 = farm_of(frame[player], player)
            obs = frame[player].get('observation') or {}
            priv = obs.get('private') or {}
            standing = collections.Counter()
            animals = collections.Counter()
            for t in iter_tiles(f0):
                kind = t.get('kind')
                if kind == 'PLANT' and t.get('crop'):
                    standing[t['crop']] += 1
                elif kind in ('PASTURE', 'COOP') and t.get('animal'):
                    animals[t['animal']] += 1
            eod.append({
                'day': i // 24 + 1,
                'money': f0.get('money'),
                'hands': len(f0.get('hands') or []),
                'hires_today': f0.get('hires_today'),
                'unlocks': len(f0.get('unlocked_quadrants') or []),
                'tiles_active': sum(1 for _ in iter_tiles(f0)),
                'standing_crops': dict(standing),
                'animals': dict(animals),
                'shed': {k: v for k, v in (priv.get('shed') or {}).items() if v},
            })

    profile = {
        'replay': os.path.basename(path),
        'player': player,
        'team': names[player] if player < len(names) else '?',
        'reward': rewards[player] if player < len(rewards) else None,
        'steps': len(steps),
        'days': n_days,
        'tot_plant': dict(plant),
        'tot_buy_animal': dict(buy_animal),
        'tot_buy_seed': dict(seed),
        'tot_sell': dict(sell),
        'tot_hire': hire,
        'tot_build': dict(build),
        'tot_feed': feed,
        'tot_care': care,
        'eod': eod,
        'final_eod': eod[-1] if eod else None,
        'hands_max': max((x['hands'] or 0) for x in eod) if eod else 0,
    }
    return profile


def print_profile(p):
    n = p['days']
    print(f"== {p['team']}  (reward={p['reward']}, steps={p['steps']}, {n} dias) ==")
    print(f"   PLANT totais: " + ", ".join(f"{k}={v}" for k, v in sorted(p['tot_plant'].items())))
    print(f"   Animais comprados: " + ", ".join(f"{k}={v}" for k, v in sorted(p['tot_buy_animal'].items())) or 'nenhum')
    print(f"   HIRE={p['tot_hire']}  BUILD={p['tot_build'] or {}}  FEED={p['tot_feed']}  CARE={p['tot_care']}")
    print(f"   hands_max={p['hands_max']}  SELL=" + ", ".join(f"{k}={v}" for k, v in sorted(p['tot_sell'].items(), key=lambda x: -x[1])[:4]))
    fe = p['final_eod']
    if fe:
        print(f"   EOD final d{fe['day']}: money={fe['money']} hands={fe['hands']} unlocks={fe['unlocks']} "
              f"crops_de_pe={fe['standing_crops'] or {}} animais_vivos={fe['animals'] or {}}")
        print(f"   shed final: {fe['shed'] or {}}")
    # linha por dia (amostra d1,d5,d10,d15,d20,d25,d30)
    print("   dias (money/hands/unlocks | crops_de_pe | animais):")
    for x in p['eod']:
        if x['day'] in (1, 5, 10, 15, 20, 25, 30) or x['day'] == n:
            sc = "/".join(f"{k[:3]}={v}" for k, v in sorted(x['standing_crops'].items(), key=lambda z: -z[1])[:3]) or '-'
            an = "/".join(f"{k}={v}" for k, v in sorted(x['animals'].items())) or '-'
            print(f"    d{x['day']:>2} money={x['money']:>8} hands={x['hands']:>2} un={x['unlocks']} | {sc:<24} | {an}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('replay')
    ap.add_argument('player', type=int)
    ap.add_argument('--json', default=None)
    args = ap.parse_args()
    p = decode(args.replay, args.player)
    print_profile(p)
    if args.json:
        json.dump(p, open(args.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'wrote {args.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
