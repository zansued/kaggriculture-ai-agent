# Kaggriculture: o gargalo não é o shed — é a eficiência marginal da mão de obra

## Tese executiva

🛑 **Minha conclusão muda uma parte importante da hipótese atual:** o v19 provavelmente não está perdendo ~15k porque “os tops conseguem pagar o dobro de HIRE”. O gargalo mais plausível é **valor produzido por ação efetivamente paga**, e há três mecanismos que ainda parecem subexplorados no Moon: **CARE seletivo e sincronizado**, **logística de WHEAT em lote** e **continuação de trabalho no mesmo tile sem movimento intermediário**. A evidência pública independente converge nessa direção. citeturn15view0turn20search3

Mais importante: eu **não reconstruiria o agente do zero** e não tentaria outro “coordenador geral”. Minha aposta principal seria uma arquitetura que vou chamar de **Shadow Crew / Microfactory**: manter o Moon v19 intacto como controlador macro e criar **um ou dois hands adicionais, anexados ao final da lista, cuja única responsabilidade é executar bundles de alto ROI em animais**, começando com COW. Isso evita exatamente o problema que matou suas abordagens anteriores: mexer na coreografia que já produz 77–88k.

A primeira versão que eu testaria é ainda mais específica:

> **v20-shadow-cow:** um ou dois hands extras somente quando há trabalho CARE economicamente justificável; `PICKUP WHEAT n` em lote; rota fixa entre cows; `FEED → CARE` no mesmo animal em turnos consecutivos; CARE inicialmente **somente uma vez por intervalo produtivo da COW**, não diariamente; colheita antecipada apenas quando necessária para evitar clipping em `max_held=6`.

Há uma razão matemática forte para começar aí: cada CARE realizado e posteriormente consumido com sucesso equivale essencialmente a **comprar uma unidade futura adicional do produto animal com uma ação**, enquanto o sistema público do jogo permite carregar várias unidades de WHEAT com um único `PICKUP`. Para COW, essa unidade marginal é MILK, cujo preço-base é 160. citeturn20search1turn21search0

E existe uma segunda descoberta que eu colocaria **antes de qualquer novo experimento**:

> ⚠️ **591 HIRE dos tops versus 277 do Moon não prova 591 contratações pagas.**

O engine permite que `HIRE` falhe silenciosamente quando não há dinheiro suficiente para o próximo custo Fibonacci. Portanto, contar comandos `HIRE` em replay não é igual a contar **hands realmente criados** nem a medir **hand-turns efetivamente disponíveis**. O código oficial incrementa `hires_today` e adiciona o hand apenas quando o pagamento consegue ser realizado. citeturn21search0

Isso pode alterar bastante a interpretação causal dos seus dados.

## O que o engine revela sobre o verdadeiro desperdício

Sua investigação do shed parece correta: se o overflow só aparece no fechamento do d29, ele não explica a diferença estrutural de 12–15k durante a temporada. O problema a procurar passa a ser outro: **desperdício de ações**, isto é, turnos pagos que não geram aumento marginal de produção ou que gastam movimento desnecessário.

O engine atual é particularmente revelador nesse ponto. O PyPI mostra que a versão mais recente de `kaggle-environments` é **1.32.7, publicada em 15 de agosto de 2026**, enquanto muitos notebooks e agentes públicos ainda documentam 1.32.4, lançada em 4 de agosto. Como houve várias releases 1.32.x em poucos dias, qualquer análise séria deve registrar versão e, idealmente, hash do ambiente local usado no harness. citeturn19search0turn19search2

### CARE não é exatamente “um multiplicador”; é uma unidade futura por ação

O comportamento do engine é mais útil quando pensado marginalmente.

Em cada fim de dia:

1. se o animal estava **fed + cared**, `pending_care_bonus` aumenta em 1;
2. em uma noite de produção, se ele estiver alimentado, o bônus acumulado é adicionado à produção-base;
3. depois disso o banco de CARE é zerado;
4. o total armazenado no animal é limitado por `max_held`;
5. se a produção ocorrer sem feed, a produção-base ainda acontece, mas o bônus de CARE não é realizado. citeturn20search1turn20search0

Portanto, para fins de planejamento:

\[
V(\text{CARE agora})
\approx
P(\text{bônus realizado})
\times
P_{\text{venda futura}}
-
C_{\text{ação}}
-
C_{\text{logística}}
-
C_{\text{impacto de mercado}}
\]

Isto é muito mais útil do que codificar “CARE sempre”.

Para uma COW em regime estável, o intervalo de produção é dois dias e `max_held=6`. Cuidá-la todos os dias permite acumular aproximadamente dois bônus entre produções, produzindo tipicamente **3 MILK por tick em vez de 1**, desde que o animal seja alimentado na noite produtiva e o estoque no tile não esteja bloqueando a produção. Essa mecânica é também a interpretação usada por um projeto público que reconstruiu sua economia em torno de COW/SHEEP + CARE. citeturn21search0turn15view0

Mas daqui vem a descoberta que considero mais interessante para o v19:

### Você não precisa começar com CARE diário

Para COW, pode-se adotar um regime intermediário:

| Regime estável aproximado | FEED/CARE no intervalo | MILK por tick | Ações de manutenção por 2 dias |
|---|---:|---:|---:|
| Sem CARE, feed suficiente | feed na noite necessária | 1 | baixo |
| **CARE esparso** | 1 CARE entre produções + feed de realização | **2** | intermediário |
| CARE completo | care/feed em ambos os dias | **3** | alto |

Os números exatos no primeiro ciclo dependem da data de placement e do bônus acumulado antes da primeira produção, mas o princípio vem diretamente da ordem das atualizações do engine. Cada CARE adicional realizado antes da próxima produção adiciona uma unidade, até o limite de armazenamento. citeturn20search1

Isso é crucial porque o problema do Moon não é “CARE não vale dinheiro”; é **não haver ações suficientes para CARE diário em todo o rebanho sem desmontar o resto da fazenda**.

Então não comece tentando capturar 100% do potencial.

Comece tentando capturar **50% do bônus CARE da COW com uma fração da perturbação estrutural**.

### O `max_held` transforma harvest em parte do custo de CARE

COW e SHEEP comportam no máximo seis unidades não colhidas. Se o animal já contém cinco MILK e a próxima produção tentaria adicionar três, apenas uma unidade efetivamente cabe. O resto do potencial desaparece no `min(max_held, ...)`. citeturn20search0turn20search1

Isso fornece uma possível explicação para abordagens de CARE que parecem caras demais:

> **CARE isolado não basta. CARE precisa ser acompanhado por capacidade de realização.**

A métrica correta não é:

```text
care_count
```

mas algo como:

```text
care_issued
care_banked
care_consumed
care_units_potential
care_units_realized
care_units_clipped_by_maxheld
care_units_unsold_terminal
```

Por exemplo, SHEEP é especialmente sensível. Com CARE diário e intervalo de três dias, a produção potencial por tick cresce muito, mas `max_held` continua em seis; perder uma janela de harvest rapidamente transforma CARE anterior em ação desperdiçada. COW é logisticamente mais tolerante porque o intervalo é de dois dias e três unidades por produção cabem em exatamente duas produções antes do teto seis. citeturn20search0turn21search0

Por isso eu **começaria COW-only**, não `CARE all animals`.

### O planting day e as ações “sem valor marginal”

Há outro vazamento possível. Uma planta nasce com `consecutive_unwatered = 1`; precisa ser regada a tempo para não morrer. Porém, após uma rega bem-sucedida, uma planta tolera um dia sem água antes da segunda ausência consecutiva matá-la. Nos crops one-shot, WATER aumenta yield somente dentro da janela de bônus; fora dela, pode estar servindo apenas à sobrevivência. citeturn17search2turn20search4

Isso sugere uma instrumentação que ainda vale mais que outra tentativa de “fert farm”:

```text
WATER_SURVIVAL_REQUIRED
WATER_ADDED_YIELD
WATER_BOTH
WATER_ZERO_MARGINAL
```

🛑 Ou seja: **o próximo “overflow” a investigar não é overflow do shed; é overflow da agenda de trabalho.**

Quantos dos 719 × unidades são ações que poderiam ser eliminadas ou consolidadas sem alterar o estado produtivo?

Um projeto público que chegou a ~94k após abandonar uma economia baseada em melon/geese descobriu exatamente esse tipo de problema: a passagem “standing-on-work” reduziu sua proporção de movimento de **59,7% para 46,1%** e bateu a versão anterior por 40–0 em seus testes. Ele também passou de ~57k para ~94k ao reconstruir a economia em torno de cows/sheep + CARE. Esses números são resultados daquele projeto, não garantias para o Moon, mas são evidência independente muito relevante. citeturn15view0

## A nova arquitetura que eu testaria: Shadow Crew

🎯 A melhor característica dessa ideia é que ela **não exige substituir a fita Moon**.

O erro estrutural das tentativas anteriores parece ter sido este:

```text
Moon coordena bem
→ overlay tenta criar produção extra
→ produção extra exige ações extras
→ overlay rouba ações/movimentos previstos pela fita
→ unidades deixam de estar onde a fita esperava
→ erro de coordenação se propaga
→ ganho econômico não chega a existir
```

Minha proposta é alterar para:

```text
MOON CORE
├── farmer original
├── hands originais
├── fita original
├── market overlays v19
│
└── SHADOW CREW
    ├── somente hands adicionais
    ├── índices após os hands Moon
    ├── nenhuma ação prevista pela fita
    └── microtarefas independentes de alto ROI
```

A propriedade fundamental é **append-only**: o Shadow Crew não toma o hand 3 que o Moon esperava encontrar em `(x,y)`. Ele cria hand 10/11, por exemplo, que a fita antiga nunca controlou.

Isso é substancialmente diferente de “HIRE escalável”, que você já testou e perdeu. Lá, pelo que seu contexto descreve, aumentou-se mão de obra dentro de uma coreografia incapaz de aproveitá-la. Aqui, **a contratação existe somente porque um job previamente avaliado já paga pelo hand**.

### A unidade de planejamento deve ser um bundle, não uma task

Eu evitaria outro scheduler greedy de tarefas individuais.

Para uma COW, o bundle natural seria:

```text
COW_SERVICE
  target = (x, y)
  needs_feed = ...
  care_value = ...
  harvest_value = ...
  expected_milk = ...
  distance = ...
```

E o hand, ao chegar lá, ganha uma pequena **reservation lock**:

```text
turn t:     FEED
turn t+1:   CARE
turn t+2:   move para próxima cow
```

Ele não volta ao coordenador global entre FEED e CARE.

Isto explora exatamente a ideia de **standing on work**: fazer outra ação no tile onde o trabalhador já está custa uma ação de trabalho, mas **zero ações de movimento**. O agente público `lonespear/kaggriculture` relata que dar precedência explícita ao trabalho já sob os pés e depois fazer matching global produziu sua maior melhoria de coordenação. citeturn20search3turn15view0

No Moon, eu iria um passo além: em vez de solver global para toda a fazenda, faria matching **somente entre Shadow Hands e Animal Bundles**.

Algo conceitualmente assim:

```python
bundle_value =
    expected_extra_product_value
    - expected_market_externality
    - seed_or_feed_cost
    - terminal_risk
    - clipping_risk

assignment_score =
    bundle_value
    - MOVE_PENALTY * manhattan_distance
    - SWITCH_PENALTY * abandons_current_bundle
```

Isso tem uma vantagem enorme sobre sua tentativa de `coordenador greedy`: a fita continua sendo responsável pelos 90% do jogo que já funcionam.

### A logística de WHEAT deve ser em lote

O engine aceita `PICKUP <item> <n>`, e o item inteiro pode ser retirado do shed em uma única ação. Não existe razão operacional para cada ida ao shed significar carregar uma única unidade de feed. citeturn20search8turn21search0

Há uma pista externa extremamente específica aqui. O projeto público de lonespear mediu que farms fortes sustentavam aproximadamente **3,7 FEEDs por viagem ao shed**, enquanto sua própria implementação fazia cerca de **1,45**; o autor deixou isso explicitamente registrado como uma hipótese aberta de logística. citeturn15view0

Isso é possivelmente a peça que falta entre:

> “CARE é lucrativo matematicamente”

e

> “CARE custa ações demais no Moon”.

Uma rota deve parecer mais com um carteiro entregando correspondência do que com dez pessoas voltando ao depósito depois de cada envelope:

```text
Shed
  ↓ PICKUP WHEAT 5
COW A: FEED → CARE
  ↓
COW B: FEED → CARE
  ↓
COW C: FEED → CARE
  ↓
...
```

Para dez cows, uma pickup em lote em vez de várias pickups e retornos pode remover uma quantidade relevante de overhead logístico.

A ordem de placement dos animais também passa a importar. **Um cluster de cows contíguas é infraestrutura logística.** Um tile animal não vale só por sua produção; vale também pela distância incremental que ele adiciona à rota de FEED/CARE/HARVEST.

### Fase produtiva pode substituir parte da mão de obra

Existe ainda uma ideia que eu não encontrei entre suas ~57 refutações: **engenharia de fase do rebanho**.

Se dez cows forem colocadas no mesmo dia, seus ticks de produção tendem a sincronizar-se. Isso cria dias com grande backlog de:

```text
FEED obrigatório
CARE a realizar
HARVEST para liberar max_held
retorno ao shed
```

Se as cows forem divididas em duas coortes temporais, por exemplo cinco em uma fase e cinco na fase oposta do ciclo de dois dias, o volume médio de trabalho é parecido, mas o **pico diário de trabalho cai**.

Isso importa porque os hands expiram diariamente e o custo de contratação é Fibonacci. O engine usa custos 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144… e zera `hires_today` a cada novo dia. citeturn21search0turn20search4

Assim:

| Hands contratados no dia | Custo acumulado |
|---:|---:|
| 8 | 54 |
| 9 | 88 |
| 10 | 143 |
| 11 | 232 |
| 12 | 376 |
| 13 | 609 |
| 14 | 986 |

O problema econômico não é apenas “quantas ações a temporada exige”; é **quantas ações simultâneas o pior dia exige**.

Uma coreografia que reduz o pico de 13 para 11 hands pode economizar muito mais que uma pequena redução na quantidade total de trabalho, justamente por causa da convexidade Fibonacci. citeturn21search0

É por isso que eu pesquisaria:

```text
cow_phase = placed_day % 2
sheep_phase = placed_day % 3
crop_phase = planted_day % cycle
```

e mediria o histograma diário de jobs.

Pode ser que parte da superioridade dos tops que parece “591 HIRE” seja, na verdade, **produção melhor faseada + hands mais ocupados**, e não simplesmente uma frota muito maior.

## A descoberta que pode invalidar a leitura atual dos 591 HIRE

⚠️ Este ponto merece um experimento separado porque pode evitar uma semana inteira na direção errada.

No código oficial, `HIRE` faz:

```text
calcula custo Fibonacci
se money < cost:
    retorna
senão:
    subtrai dinheiro
    incrementa hires_today
    adiciona hand
```

Ações inválidas ou inviáveis são silenciosamente ignoradas. citeturn21search0

Portanto:

> **HIRE command count ≠ successful hires ≠ paid labor ≠ effective hand-turns.**

Se `TOPS_ADAPTIVE_27AGO.md` está contando comandos observados no action stream, o número 591–602 precisa ser reinterpretado.

Eu substituiria imediatamente a métrica por estas quatro:

| Métrica | O que realmente mede |
|---|---|
| `HIRE_ORDERS` | quantas vezes o bot pediu HIRE |
| `SUCCESSFUL_HIRES` | aumento efetivo de `len(hands)` |
| `HAND_TURNS` | soma de hands disponíveis ao longo dos 720 steps |
| `PAID_LABOR_COST` | Fibonacci reconstruído por dia |

E acrescentaria:

\[
\text{productive efficiency}
=
\frac{
FEED + CARE + WATER_{\text{value}} + HARVEST + PLANT + FERTILIZE_{\text{value}}
}{
farmer\_turns + hand\_turns
}
\]

Um projeto público que comparou sua fazenda com agentes superiores encontrou algo revelador: seus números de **CARE/FEED eram 347/348 contra 312/320 nos tops**, ou seja, ele fazia até mais manutenção animal; a diferença restante estava em crop throughput, com tops fazendo aproximadamente 890 WATER e 340 HARVEST contra 582 e 210. O próprio autor concluiu que seu manejo animal já se aproximava dos fortes, enquanto a diferença continuava na área agrícola que a economia conseguia sustentar. citeturn15view0

Isso não prova que v19 tenha a mesma distribuição, mas refuta a proposição simplista:

> “top = muito mais HIRE = muito mais CARE”.

Uma explicação melhor é:

> **top = cada unidade paga sustenta mais trabalho útil; esse trabalho cria cash flow; o cash flow permite ampliar a produção; só então mais hands tornam-se rentáveis.**

Essa formulação combina muito melhor com o fato de o clone público de uma fazenda top com **44 strawberries, três quadrantes e 14 hands ter perdido 0–40**, apesar de executar 1.068 WATER e 311 HARVEST: o custo adicional de contratação ficou em cerca de 22,6k e a produção não sustentou a expansão. citeturn15view0

Isso é quase uma replicação independente do que vocês já descobriram no Moon.

## O experimento que eu faria agora

🎯 Eu abandonaria temporariamente “produzir 2× por tile” como meta direta. O próximo objetivo experimental deveria ser muito menor:

> **Conseguir +1 MILK por ciclo de COW com mínimo custo incremental de coordenação.**

Essa pequena meta pode ser suficientemente grande economicamente.

Com dez cows e cerca de dez oportunidades posteriores de produção por cow ao longo da parte produtiva da temporada, **uma única unidade adicional de MILK por ciclo representa ordem de grandeza de ~100 MILK adicionais**. Ao preço-base de 160, isso tem valor bruto teórico de cerca de **16k**, antes de descontar feed, contratação, movimento, clipping e impacto no mercado. Os valores de intervalo, `max_held` e preço-base vêm do engine oficial. citeturn21search0

Não estou prevendo que o bot ganhará 16k — MILK tem curva de glut agressiva e o preço depende também do oponente — mas a ordem de grandeza é exatamente a do gap que você está tentando fechar. O cálculo mostra que **não é necessário capturar CARE diário completo para o experimento ser material**. citeturn21search0

### Protótipo mínimo

Eu faria quatro variantes, todas sobre **v19 puro**, sem qualquer outra modificação.

**Control:** `v19`.

**A — Cow CARE opportunistic:** somente quando um hand Moon já estiver parado sobre uma cow e CARE tiver valor futuro positivo. Nada de HIRE extra. Serve para medir o valor “grátis” de `standing-on-work`.

**B — Shadow hand:** no máximo **um hand adicional**, exclusivo para cows. Ele usa `PICKUP WHEAT n`, rota entre animals e executa FEED/CARE. Nenhuma mudança em crops.

**C — Shadow hand + CARE sparse:** como B, mas cada cow recebe no máximo **um CARE por intervalo de produção**, priorizando a próxima produção que realmente pode realizar o bônus.

**D — Shadow hand + value gate:** como C, mas CARE só é autorizado quando:

```python
expected_extra_milk_value > marginal_hand_cost_share + action_shadow_price
```

e:

```python
held + predicted_next_production <= max_held
```

ou existe HARVEST programado antes do tick.

A versão D começa a ser a **adaptatividade de produção** que os overlays de PLANT que vocês tentaram nunca conseguiram implementar: ela não escolhe “plante tomato porque preço atual é alto”; ela escolhe **comprar ou não uma unidade futura de produção usando uma ação escassa**.

Esse é, na minha avaliação, o nível certo de adaptatividade.

### Instrumentação obrigatória

Não julgaria a ideia somente pelo reward. Para cada partida, gravaria:

```text
successful_hires/day
hand_turns/day
hire_cost/day

moves
productive_actions
zero_marginal_actions

wheat_pickups
wheat_units_picked_up
feeds_per_pickup

cow_feed
cow_care
cow_care_realized
cow_care_clipped

milk_harvest_units
milk_sold_units
milk_avg_sale_price

distance_per_shadow_hand
jobs_completed_per_shadow_hand
```

A métrica que eu mais gostaria de ver é:

\[
\text{CARE realization rate}
=
\frac{\text{extra animal units efetivamente produzidos}}
{\text{CARE actions}}
\]

Idealmente próxima de 1 antes de considerar impacto de preço.

A segunda:

\[
\text{feeds per shed pickup}
\]

Eu tentaria sair do regime próximo de 1 para **3+**. O valor de ~3,7 observado em fazendas fortes por outro pesquisador público torna isso uma meta experimental plausível, embora não deva ser tratado como número universal. citeturn15view0

A terceira:

\[
\text{shadow contribution}
=
\Delta reward
-
\text{cost of additional hires}
\]

Assim você saberá exatamente se o hand extra “se paga”, em vez de inferir pelo resultado final.

## Por que o H2H local pode estar enganando o ladder

Sua primeira pergunta aberta também tem agora uma resposta bem sustentada.

Um v19 que vence v18 em 62% dos mirrors demonstra:

> **v19 é um bom best-response à distribuição induzida por v18.**

Não demonstra:

> **v19 vence 62% da população relevante.**

Isso é especialmente problemático em Kaggriculture porque as políticas dos dois jogadores alteram o mesmo mercado. Um parâmetro excelente contra outro vendedor de MILK pode ser ruim contra um strawberry-heavy; um guard excelente contra outro dumper pode perder dinheiro contra alguém que deixa o produto escasso. Um projeto público independente explicitamente abandonou validação exclusivamente mirror por esse motivo e passou a exigir **mirror + league sem regressão por arquétipo**. citeturn15view0

Há evidência recente do próprio fórum no mesmo sentido. Um participante descreveu PPO selecionando estratégias públicas e observou que melhorar contra alguns oponentes piorava contra outros; a discussão atribuiu parte do problema à **não-transitividade** e à necessidade de diversidade na pool local. citeturn13search14

Além disso, o rating ao vivo não é o objetivo final. A Kaggle confirmou oficialmente que, depois do deadline, as partidas continuam por aproximadamente duas semanas e então um **único torneio Bradley–Terry** sobre esses episódios determina o leaderboard final. citeturn13search7

Ryo Hasegawa publicou uma análise empírica do rating ao vivo segundo a qual submissões novas começam em 600, grande parte da convergência ocorre nas primeiras dezenas de partidas, diferenças pequenas permanecem bastante ruidosas e o matchmaking se concentra em adversários próximos do rating atual. Ele recomenda explicitamente otimizar W/L contra o campo relevante em vez de coin total médio. Esses detalhes do rating ao vivo são análise empírica dele, não especificação oficial, mas a parte sobre o Bradley–Terry final é corroborada pela Kaggle. citeturn13search4turn13search7

Por isso eu mudaria seu gate de:

```text
24–36 seeds vs v19
→ se >50%
→ 144 mirror
```

para:

```text
STAGE A — regression
12–16 seeds × 2 seats vs v19

STAGE B — archetype league
v19
v18
crop-heavy
high-cow/milk
goose/egg
strong public / top-like

STAGE C — paired race
mesmos seeds e mesmos adversários
eliminar candidatos claramente piores cedo

STAGE D — grande validação
somente sobreviventes
```

A utilização dos mesmos seeds por candidato é particularmente importante. O projeto lonespear relata que **common random numbers** reduziram dramaticamente suas barras de erro e permitiram resolver diferenças menores com menos partidas; novamente, o número exato é específico de seu harness, mas o método é diretamente aplicável. citeturn15view0

E aqui há outro ponto estratégico vindo do topo atual: Rishi Gottumukkala, listado como **1º na competição** quando comentou há dois dias, disse não ter conseguido fazer RL end-to-end funcionar competitivamente; seu PPO/Transformer chegou aproximadamente a 40k. Ele relatou sucesso moderado com **heurística + RL** e disse que a maior parte de seu trabalho de RL foi em **opponent modeling**. citeturn13search1

Isso reforça minha recomendação: **não resolva o gargalo operacional com RL**. Resolva FEED/CARE/rotation deterministicamente. Se usar aprendizado, use-o depois para escolher thresholds, market regimes ou opponent archetypes.

## Prioridade final

🛑 A ordem que eu seguiria agora seria esta:

| Prioridade | Experimento | Por que é novo/relevante | Risco |
|---|---|---|---|
| **Máxima** | Recontar **successful hires / hand-turns**, não comandos HIRE | Pode invalidar a premissa 591 vs 277 | Muito baixo |
| **Máxima** | Instrumentar `CARE realized / clipped` | Descobre se o gargalo é CARE ou realização | Muito baixo |
| **Máxima** | **Shadow Crew COW-only + batch WHEAT** | Não toca a fita Moon | Médio |
| **Alta** | CARE **sparse**, 1 bônus/ciclo antes de CARE full | Alvo ~100 MILK extras, não 3× imediato | Médio |
| **Alta** | `standing-on-work` / reservation lock | Converte movimento em produção | Baixo |
| **Alta** | `feeds_per_pickup` e rota de serviço | Evidência externa aponta ~3,7 em farms fortes | Baixo |
| **Média** | Fasear cows em 2 coortes | Reduz pico diário e custo Fibonacci | Médio/alto |
| **Depois** | Bundle HARVEST→PLANT→WATER em crops | Grande potencial, mas mexe no core Moon | Alto |
| **Depois** | Fertilizante phase-aware | Só depois de liberar ações | Alto |
| **Evitaria agora** | Coordenador total / RL end-to-end | Já há evidência local e pública contrária | Muito alto |

A ideia mais importante é que **você não precisa resolver toda a coreografia top para encontrar os 15k**.

O engine permite uma trajetória incremental muito mais segura:

```text
v19
  ↓
medir hand-turns reais
  ↓
achar ações sem valor marginal
  ↓
adicionar 1 shadow hand
  ↓
batchar WHEAT
  ↓
CARE 1× por ciclo de COW
  ↓
garantir harvest antes de max_held
  ↓
market-gate o CARE
  ↓
só depois tentar CARE full
```

A matemática torna esse caminho particularmente atraente. Com 10 COWs, **uma única unidade adicional de MILK por ciclo produtivo já está na mesma ordem de grandeza do gap inteiro** antes dos custos e da reação do mercado. Não é necessário saltar de “Moon sem CARE” para “top com CARE diário em tudo”; basta criar uma máquina que converta **uma ação incremental em uma unidade incremental vendável com alta taxa de realização**. citeturn21search0turn20search1

E a pista pública mais forte é quase uma frase-resumo do problema: outro agente conseguiu melhorar dramaticamente com CARE e coordenação, mas quando simplesmente copiou **mais terra + mais crops + 14 hands**, perdeu 0–40 porque o custo dos hands explodiu. O mesmo projeto obteve grande ganho quando parou de mandar trabalhadores atravessarem a fazenda e passou a executar primeiro o trabalho que já estava debaixo dos pés. citeturn15view0

**Isso sugere que o próximo salto do KAWA não é “mais mãos”. É fazer cada mão parar de andar para poder produzir.**