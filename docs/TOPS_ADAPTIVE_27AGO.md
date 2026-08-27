# Análise adaptativa dos Top Agents — 27/08/2026

Baixados replays reais dos ranks 1-5 (Kaggle Kaggriculture, competição id 147734):
- Crop Dusta (#1, 3113.2) — partida vs Subramanya N (#3), seed 2084502533, reward 69076
- Ryo Hasegawa (#2, 2979.1) — seed 867560714, reward 81853
- tetsuya (#4, 2880.0) e Blu3s (#5, 2879.0) — mesma partida, seed 2022269475, rewards 81457 / 76812

Ferramenta: `kaggriculture/analyze_adaptive.py` (percorre replay e extrai por dia: preços,
shed, ações de mercado, plantio). Saídas em `kaggriculture/replays_top10/analise_*.txt`.

## 1. Padrões comuns aos 4 tops

| Padrão | Evidência |
|---|---|
| **Front-run MELON** | Todos vendem MELON ~d10-d16 ANTES do crash. Preço MELON pico d9 (~271), colapsa d21 (~7). Ninguém segura até o piso. |
| **Front-run STRAWBERRY** | Todos vendem STRAWBERRY durante o declínio (d13-d24), antes do piso (~1-7). Timing varia: Crop Dusta d13-21, Ryo d14-24, tetsuya/Blu3s d15-29. |
| **Rebanho COW é o motor** | Todos têm 10-12 COW e vendem MILK o jogo todo quando o preço permite. tetsuya/Blu3s lucraram com MILK caro (246→250). |
| **Compra de WHEAT no mercado** | Todos compram PROD:WHEAT (5-20/dia) nos dias 0-13 → FEED dos animais + reserva. Permite rebanho maior sem plantar tanto WHEAT. |
| **HIRE agressivo** | 10-15 hands/dia (HIRE 591-602 por partida). MUITO acima dos ~12 hands automáticos. |
| **FERTILIZER dump cedo** | Vendem FERT enquanto preço alto (~100→30), em lotes pequenos constantes. |
| **Vendas fracionadas** | SELL 10-40×/dia em lotes de 3-16 unidades (não dump em bloco). |
| **CARROT tardio** | Plantam CARROT d15-d26 para vender no fim (preço sobe 35→56). |
| **TOMATO no fim (tetsuya)** | Planta TOMATO d11-12, vende d21-24 (preço sobe 60→147). |

## 2. Comportamento adaptativo (reagem à partida)

Os preços variam MUITO entre partidas (dependem do oponente):
- Partida 100939868: **WOOL colapsa** (206→24→recupera), MILK colapsa (169→1→recupera).
- Partida 100969498: **MILK fica caro** (169→250), **WOOL colapsa** (206→1).

Respostas observadas:
- **MILK caro → foca COW e vende leite o jogo todo** (tetsuya/Blu3s).
- **WOOL colapsa → vende WOOL cedo (d7-d12) e para** (tetsuya).
- **WHEAT sobe no fim → dump de WHEAT no d29** (Blu3s: 93 vendas).
- Crop Dusta usa **GOOSE para EGG** (vende EGG ~50-66 o jogo todo) — fonte extra estável.

## 3. O que o hybrid_v6 (Moon+overlays) tem

Overlays atuais do v6 (em `submissions/hybrid_v6/main.py`):
- `_mature_opp_front_run`: vende MELON/STRAWB/MILK/WOOL quando a produção do oponente
  está madura (age >= max_day-2). Thresholds fixos: STRAWB 4, MELON 2, MILK 4, WOOL 3.
- `_sell_first`: order-slot — premium sells primeiro (piora o preço do oponente).
- `_glut_guard`: segura grãos (WHEAT/CARROT/TOMATO) se preço < 1.3×base; dumpa
  MILK/WOOL/MELON/STRAWB se preço >= base×floor (0.45/0.40), janela steps 250-650.

Base Moon (embutida): planta WHEAT/CARROT staples + MELON/STRAWB cedo; rebanho
COW+SHEEP; SEM GOOSE, SEM HIRE, SEM BUY_PRODUCT.

## 4. Lacunas vs tops (priorizadas)

1. **Sem compra de WHEAT no mercado (BUY_PRODUCT)** — todos os tops compram WHEAT
   d0-d13 para FEED. Overlay leve: injetar BUY_PRODUCT WHEAT quando money alto e
   preço baixo. Menos invasivo (só ordem de mercado).
2. **Sem GOOSE/EGG** — Crop Dusta usa GOOSE como terceira fonte animal. Risco médio:
   exige colocar GOOSE em tile e coletar EGG (mexe no planejamento do Moon).
3. **Sem CARROT/TOMATO tardio** — tops plantam CARROT d15+ e TOMATO d21+ para vender
   no fim. Risco médio: compete por tiles/hands com o plano do Moon.
4. **Thresholds fixos (não adaptativos)** — glut-guard usa _GBASE fixo; tops reagem à
   série de preços real. Overlay leve: tornar _GD_FLOOR/_GRISE dinâmicos (ex: base =
   média recente; momentum de preço decide manter/dump).
5. **HIRE agressivo** — tops usam 10-15 hands/dia, MAS overlay de HIRE quebra o Moon
   (reward cai 143k→6.5k, medido 25/08). NÃO tentar via overlay; exigiria mudar a base.

## 5. Insight sobre rewards

Tops: 69-82k de reward final nas partidas amostradas. Nosso v6: ~100-150k em h2h local.
Produzimos MAIS dinheiro absoluto, mas o ladder é **ELO (W/L)**, não reward absoluto —
o preço depende dos DOIS jogadores. **Adaptatividade = extrair mais valor que o oponente
dadas as mesmas condições de preço.** Imitar a produção dos tops (wheat-heavy, HIRE) não
basta (já medido: perde localmente); o gap é comportamento reativo ao preço da partida.

## 6. Próximos passos sugeridos

- Validar via `h2h_bench.py` (2 lados) qualquer overlay novo vs v6 — NUNCA submeter sem
  W/L positivo. Série de 25/08: 9 variações reprovaram vs v6 (ótimo local apertado).
- Candidato de menor risco: **overlay adaptativo de preço no glut-guard** (base dinâmica
  + momentum) e **BUY_PRODUCT WHEAT cedo**.
- Candidato de maior ganho potencial (se a base Moon for trocável): rebanho GOOSE+EGG e
  CARROT/TOMATO tardio — exigem mudança estrutural, não overlay.
