# Mapa do Moon V56 — fitas kawa + overlays (27/08/2026)

Objetivo: mapear a arquitetura do `research/public/moon_agent_main.py` para
planejar a evolução estrutural (GOOSE/HIRE).

## 1. Arquitetura: fita base + cascata de overlays

```
agent(obs):
  actions = _kawa_actions(obs)          # seleciona a fita por _kawa_route_label
  action = actions[step]                # ação pré-computada da fita (719 steps)
  overlays em cascata modificam action:
    _weed_repair_action                 # DIG em weeds
    _v17_feed_guard                     # protege FEED dos animais
    _v17_room_evac
    _repay_shift / _preempt_shift       # ajuste de dívida/preempt
    _rank_sell_slots                    # ordena slots de venda
    _v17_r5_counter / _v17_md_counter   # contadores de família r5/md
    _v38_farm_pair_tomatoes             # TOMATO no fim
    _v35_egg_late_pair                  # GOOSE/EGG condicional (d11)
    _v17_room_guard
    _terminal_liquidation               # liquidação no fim (step>=708 usa _v20)
  _align_hands                          # ajusta nº de hands
```

O bundle hybrid_v6 adiciona POR CIMA: `_mature_opp_front_run`,
`_sell_first`, `_glut_guard`.

## 2. Fitas kawa (rotas pré-computadas)

Cada rota é um JSON de **719 dicts** `{"farmer": [...], "hands": [...], "market": [...]}`,
compactado como blob zlib+base85. Nome = mix de animais + nº de quadrantes:

| Rota | Mix | Notas |
|---|---|---|
| `10c4s_3q` | 10 COW + 4 SHEEP | 3 quadrantes |
| **`8c6s_3q` (default)** | 8 COW + 6 SHEEP | `_ACTIONS = _ACTIONS_8C6S_3Q` |
| `6c8s_3q` | 6 COW + 8 SHEEP | |
| `6c12s_4q_first/second_yarn` | 6 COW + 12 SHEEP | 4 quadrantes, 2 variações |
| `LEGACY_*` | mesmas | usadas se `_kawa_use_legacy_layout` |

Fita default `8c6s_3q` (contagem):
- **277 HIRE**, 8 BUY_ANIMAL (5 COW + 3 SHEEP = 8c6s), 101 BUY_SEED,
  72 BUY_PRODUCT (WHEAT p/ FEED), 482 SELL, 2 BUY_LAND.
- Compra animais escalonado: d0 (2 COW+2 SHEEP), d3, d5, d7 (2+2), d9, d11.
- NÃO compra GOOSE na fita base.

## 3. GOOSE/EGG: JÁ EXISTE condicionalmente (_v35_egg_late_pair)

O Moon V56 já tem um "gatilho de EGG":
- `_V35_EGG_SHOPS = {"BAKERY", "BRUNCH_SPOT"}`
- No **step 264 (d11)**, olha as 3 primeiras lojas (`town.unlocked_shops[:3]`).
- Se `egg_shops >= 2` (2+ BAKERY/BRUNCH_SPOT) E sem YARN_STORE E sem oponente
  com GOOSE → **converte o par de animais do d11 em GOOSE**:
  - `BUILD_PASTURE` → `BUILD_COOP`
  - `COW/SHEEP` → `GOOSE` em `PICKUP`/`PLACE`
  - `BUY_ANIMAL COW/SHEEP` → `BUY_ANIMAL GOOSE`
- Escopo: só o par do d11 (2 gansos). Ativo nos steps 264-275.

Implicação: o v6 JÁ usa GOOSE em jogos com regime de lojas favorável a EGG.
A lacuna vs Crop Dusta (que usa GOOSE d6-d12, 3-4+ gansos) é: **mais cedo e
mais gansos**, e talvez **mais regimes**.

## 4. HIRE e BUY_PRODUCT já existem na fita

A premissa antiga ("Moon não usa HIRE") é FALSA para o V56: a fita 8c6s usa
277 HIRE e 72 BUY_PRODUCT WHEAT. A descoberta de 25/08 sobre "HIRE quebra o
Moon" referia-se a overlay de HIRE sobre uma versão sem fita de HIRE.

## 5. Implicações para a evolução

- **NÃO é preciso reescrever a fita inteira** para GOOSE: expandir `_v35`
  (converter mais pares / mais regimes) é a alavanca localizada.
- A cascata de overlays já cobre FEED, weeds, terminal, TOMATO, EGG.
- Validação: qualquer mudança via h2h_bench (2 lados) vs v6.
- O bundle embute o moon como blob → para testar mudança no moon, criar cópia
  modificada do `moon_agent_main.py` e buildar novo bundle (ex: v17).

## Próximo passo sugerido (Fase 2 revisada)

Expandir `_v35_egg_late_pair` para ativar GOOSE em mais cenários:
1. Converter também o par do d9 (step 216) em GOOSE quando regime forte.
2. Ampliar `_V35_EGG_SHOPS` ou reduzir o limiar (`egg_shops >= 1` em regimes
   sem YARN_STORE).
3. Garantir venda de EGG (já coberta pelo glut-guard `_GBASE["EGG"]=50`?).
Testar incrementalmente via h2h.
