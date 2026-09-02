# Kaggriculture Top 10: o que provavelmente está separando o v19 da elite

Pesquisa consolidada em **2 de setembro de 2026**, combinando o contexto experimental que você forneceu, o **engine atual do `kaggle-environments`**, discussões recentes da competição, esclarecimentos oficiais da equipe Kaggle, código público e relatos dos competidores mais fortes.

## 🛑 Conclusão executiva

A minha conclusão principal é esta:

> **O gap do v19 não parece ser primariamente “qual crop escolher” nem “quantos hands contratar”. Ele está na compressão temporal da execução: quanto trabalho útil cada tile recebe por unidade de tempo e quanta latência existe entre colher, replantar, regar, alimentar, cuidar, fertilizar e colher novamente.**

O engine contém uma propriedade especialmente importante que muda a leitura do problema: **farmer e hands são processados sequencialmente, no mesmo estado mutável, e vários workers podem ocupar o mesmo tile**. Portanto, em um único turno é legal fazer, por exemplo, **HARVEST → PLANT → WATER no mesmo tile com três workers diferentes**. Em animais, um pequeno “micro-time” no mesmo tile pode encadear **FEED, CARE, HARVEST e COLLECT_FERTILIZER**. Isso cria uma explicação mecânica muito mais forte para a produtividade observada nos tops do que simplesmente “eles contratam 600 vezes”. citeturn18view1turn19view2

Há seis descobertas que, em ordem prática, eu trataria como prioritárias:

1. **⚠️ Existe neste momento um bug público grave no `obs["step"]` para o seat 1 no `kaggle-environments==1.32.7`.** O seat 0 recebe `step=0,1,2...`; o seat 1 recebe `None` permanentemente. Como o Moon é uma fita indexada por turno, qualquer dependência direta de `obs.step` pode fazer metade dos jogos repetir a lógica do turno zero. Antes de mexer em estratégia, isso precisa ser auditado. A alternativa robusta é `step = day * turnsPerDay + hour`. citeturn26search2
2. **O scheduler dos tops provavelmente captura complementaridades que overlays não capturam.** `PASS→PLANT`, “mais HIRE”, fertilização isolada etc. fracassam porque uma ação tem valor apenas quando as ações dependentes estão coordenadas espacial e temporalmente.
3. **Plantio adaptativo deve olhar o mercado futuro, não o preço atual.** A composição das lojas é pública, persistente e gera demanda previsível; desde a versão **1.32.7**, carrot, tomato e egg foram explicitamente alterados pela Kaggle para serem oportunidades situacionais quando a demanda das lojas cria escassez. citeturn26search5turn26search0
4. **Fertilizer e mão de obra são complementares.** Em um executor lento, vender fertilizante pode realmente ser melhor. Em um executor que colhe rápido e evita cap de yield, fertilizer pode gerar produção adicional que o Moon simplesmente não consegue converter em dinheiro.
5. **Opponent modeling é provavelmente a próxima fronteira de market timing.** Rishi Gottumukkala, então mostrado como primeiro colocado em uma discussão recente, relatou que RL end-to-end ficou por volta de 40k e que sua parte mais bem-sucedida de RL estava em **opponent modeling**, não em substituir o agente inteiro. citeturn12search0
6. **O h2h v19×v18 não mede o que o ladder mede.** Ele prova domínio sobre um ancestral específico. Não prova domínio sobre a distribuição atual de estratégias; além disso, seeds não são controles perfeitos porque a própria sequência de lojas pode ser afetada pelo comportamento das fazendas através do RNG compartilhado. citeturn26search0turn8search10

Há ainda uma correção importante de calendário: **23 de setembro de 2026 é o Entry/Team Merger Deadline; o Final Submission Deadline é 30 de setembro de 2026**. Depois disso, os episódios continuam aproximadamente por duas semanas antes do Bradley–Terry final. citeturn16search0turn26search6

E o esclarecimento oficial mais importante sobre esse Bradley–Terry é ainda melhor para planejamento: **o ajuste final usa episódios de toda a competição entre agentes que continuem ativos no momento do torneio final**; se qualquer um dos dois agentes daquele episódio tiver sido desativado, o episódio não conta. citeturn26search1turn26search9

## O que o engine revela sobre o verdadeiro gap de produção

### A descoberta central: o engine permite “pipelines” dentro do mesmo turno

O processamento não é simultâneo no sentido usual. Para cada jogador, o engine aplica primeiro a ação do farmer e depois as ações dos hands, **sequencialmente**, alterando o estado entre uma ação e outra. Também não há uma regra de exclusão espacial impedindo diversos workers de estarem na mesma coordenada. citeturn18view1turn19view2

Isso permite uma coreografia que uma fita tradicional tende a enxergar como três eventos separados:

```text
Mesmo tile, mesmo turno:

Worker 0: HARVEST WHEAT
                  ↓ tile vira vazio
Worker 1: PLANT WHEAT
                  ↓ tile vira PLANT
Worker 2: WATER
```

O resultado é que a latência **colheita → novo plantio → primeira rega** pode ser reduzida praticamente a zero. Isso é especialmente poderoso para culturas one-shot de ciclo curto.

Para um crop ongoing, pode existir:

```text
HARVEST
   ↓
FERTILIZE
   ↓
WATER
   ↓
produção agendada no fim do dia
```

E, para um animal:

```text
FEED ─┐
CARE ─┼─> animal já preparado para o refresh
HARVEST ┤
COLLECT_FERTILIZER ┘
```

Isso é uma **inferência da semântica do engine**, não evidência de que Crop Dusta ou Ryo necessariamente programaram exatamente essas quatro sequências. Mas mecanicamente é uma explicação forte para a combinação que você observou nos tops: mais HIRE, mais rotação, mais fertilizer convertido em valor e mais produção por tile. citeturn18view1turn19view2turn24view0

### Por que “mais HIRE” isoladamente dá 0–12

Os custos Fibonacci atuais tornam uma força de trabalho razoavelmente grande surpreendentemente barata enquanto os workers estiverem efetivamente ocupados:

| Hands contratados no dia | Custo cumulativo |
|---:|---:|
| 6 | $20 |
| 8 | $54 |
| 10 | $143 |
| 12 | $376 |
| 13 | $609 |
| 14 | $986 |
| 15 | $1.596 |

Isso deriva da sequência marginal `1,1,2,3,5,8,13,21,34,55,89,144...`, que o engine usa para cada novo hire diário. citeturn17search1

Um décimo hand contratado cedo no dia custa marginalmente $55 e pode, no máximo, realizar cerca de 24 ações naquele dia: **$2,29 por ação potencial**. O décimo segundo custa $144, ou até **$6 por ação potencial**. Portanto, 10–12 hands não são economicamente absurdos; tornam-se absurdos quando passam metade do tempo em `MOVE`, `PASS`, trajetos redundantes ou esperando dependências.

Isso coincide com análise pública recente da competição: um participante que mediu utilização encontrou grande parte dos turnos gasta em movimento, e outro relatou que reorganizar a execução para **terminar o trabalho de um tile antes de mover** reduziu dramaticamente caminhada e multiplicou o banco final do agente. O ponto não é o número específico de cada bot; é a conclusão operacional: **routing é uma variável econômica**. citeturn20search0

Há ainda um detalhe importante para sua análise de replay: **contar comandos `HIRE` não equivale a contar hires bem-sucedidos**. O engine simplesmente transforma um HIRE inviável por falta de dinheiro em no-op. Assim, seus “591–602 HIRE” dos tops devem ser reanalisados como:

> `HIRE attempted` ≠ `HIRE committed` ≠ `peak hands alive`.

O número que interessa é **quantos hands efetivamente existiam em cada turno** e quanto trabalho útil eles produziram. citeturn18view3

### A métrica que eu passaria a perseguir

Em vez de perguntar somente “reward por seed”, eu adicionaria:

| Métrica | O que revela |
|---|---|
| `harvest_to_replant_latency` | Quantos turns um tile produtivo fica vazio |
| `work_action_share` | % das ações em trabalho, excluindo MOVE/PASS |
| `productive_actions / hand-day` | Eficiência econômica real do HIRE |
| `moves / productive_action` | Qualidade de routing |
| `crop_units / tile-day` | O gap físico que você quer fechar |
| `ongoing_cap_events` | Produção desperdiçada por crop cheio |
| `fert_collected / animal-days` | Quanto valor diário está sendo abandonado |
| `care_coverage / useful_animal-days` | Quanto bônus animal está sendo perdido |
| `successful_hires/day` | Corrige o falso sinal de contar comandos |
| `shed_overflow_units` | Produção criada e depois literalmente descartada |

🛑 **Minha hipótese forte é que os tops não têm simplesmente “uma rotação duas vezes mais rápida”: eles comprimem várias fases da rotação no mesmo turno e diminuem brutalmente o tempo não produtivo do tile.**

## Fertilizer, animais e a economia que o Moon provavelmente não está capturando

O funcionamento atual do animal é particularmente relevante. Ao fim do dia, **todo animal sobrevivente recebe `fertilizer_available=True`**. Essa disponibilidade é booleana: fertilizer não acumula indefinidamente no tile. Se você não coletar, perde a oportunidade de transformar aquele animal-day em uma unidade adicional de fertilizer. citeturn24view0turn24view1

Isso muda a economia de COW. Uma vaca não é apenas:

> `COW → MILK`

Ela é aproximadamente:

> `COW → MILK + fluxo diário potencial de FERTILIZER + bônus futuro de CARE`.

O fertilizer não recebe demanda de nenhuma loja nem do Town Center; portanto, ele não tem um “buraco de demanda” natural como milk, strawberry ou carrot. Sua venda tende a caminhar pelo lado glut da curva. citeturn26search0turn18view3

Isso explica por que **dump cedo** faz sentido em algumas fitas: o preço começa perto de $100, ninguém consome fertilizer do mercado, e guardar produção excessiva só degrada sua própria saída futura.

Mas daí não segue que “fertilizer deve sempre ser vendido”.

### O valor do fertilizer depende do throughput

O fertilizer aumenta produção quando coincide com as janelas corretas; para ongoing crops, o engine pode produzir **duas unidades em vez de uma** em um tick fertilizado e regado. Porém o armazenamento da planta continua limitado ao seu `max_yield`. Se o crop já está cheio, parte dessa produção extra simplesmente não tem valor. citeturn24view0

Assim:

\[
V_{\text{fert usado}}
=
\Delta q_{\text{realmente colhido}}
\times
P_{\text{futuro}}
-
C_{\text{labor}}
\]

e não

\[
V_{\text{fert usado}}
=
\Delta q_{\text{teórico}}
\times
P
\]

Esse detalhe provavelmente resolve o aparente paradoxo **“no Moon vender fert é melhor; no CropDusta usar fert parece melhor”**.

No Moon:

- harvests mais espaçados;
- mais risco de crop já estar no cap;
- fertilizer exige transporte e uma ação;
- a produção adicional pode nunca chegar à venda.

Em uma arquitetura high-throughput:

- harvest antes de saturar;
- fertilizer aplicado no timing exato;
- output novo é liberado continuamente;
- mãos extras reduzem o custo marginal de serviço.

Ou seja: **fertilizer tem complementaridade superlinear com mão de obra e frequência de harvest**.

### Nem toda crop merece fertilizer

Um caso especialmente revelador é **MELON**. Pela implementação atual, ele começa a ser colhível em torno do dia 10 e atinge maturidade máxima no dia 12. A janela de aumento por watering começa suficientemente cedo para que um melon perfeitamente regado consiga chegar ao máximo de seis unidades já quando se torna colhível. Nesse cenário, fertilizer não aumenta o yield final: ele apenas chega mais depressa a um cap ao qual a planta já chegaria. citeturn17search1turn19view2

Portanto:

**MELON saudável + water perfeito + harvest no primeiro momento útil → fertilizer tende a ter valor incremental zero.**

Fertilizar melon só começa a fazer sentido quando há, por exemplo, regas perdidas ou alguma consideração específica de timing.

WHEAT e CARROT têm espaço incremental menor; TOMATO é muito mais interessante porque sua frequência alta permite que um scheduler rápido converta repetidamente fertilização em unidades adicionais, em vez de deixá-las morrer no cap. STRAWBERRY também tem complementaridade, embora com intervalo maior. citeturn17search1turn24view0

🎯 **Teste que eu faria:** não “fert farm” global. Escolha dois tiles ongoing, fixe workers próximos e compare:

```text
controle:
HARVEST → WATER

tratamento:
HARVEST → FERTILIZE → WATER
```

registrando **unidades adicionais realmente vendidas**, e não simplesmente fertilizações executadas.

## Plantio adaptativo: por que as tentativas anteriores estavam mirando a variável errada

A atualização **1.32.7** é uma pista quase explícita dos designers. A Kaggle alterou carrot, tomato e egg para que seus preços possam disparar quando existe **grande demanda das lojas e pouca produção**. A equipe afirmou que a intenção era torná-los “viáveis em algumas situações, não universalmente”; nas condições sem produção, estimou que a oportunidade relevante surgiria em aproximadamente 50% das partidas para tomato, 26% para carrot e 22% para egg. citeturn26search5

No source atual, CARROT, TOMATO e EGG usam uma função de escassez com **hinge**: abaixo do ponto de joelho, o comportamento é controlado; passada a capacidade `T`, entra um termo quadrático forte. Para carrot, além disso, o `below_target` foi elevado, aumentando bastante seu potencial em regimes de escassez. citeturn26search0turn6file0

Isso significa que a decisão não deve ser:

```python
if price["CARROT"] > threshold:
    plant("CARROT")
```

Quando você observa o preço alto, frequentemente já está tarde demais.

A decisão correta é aproximadamente:

\[
EV(c,t)=
\sum_h
\hat q(c,h)
\cdot
\hat P(c,h)
-
seed(c)
-
labor(c)
-
fert\_opportunity(c)
-
market\_impact(c)
\]

onde o preço deve ser previsto no **momento em que a produção chegará ao mercado**.

### A composição das lojas é um sinal antecipado

A análise pública do próprio `SHOPS` e dos intervalos de consumo produz uma expectativa aproximada de demanda total da cidade durante a temporada:

| Produto | Consumo esperado da cidade |
|---|---:|
| WHEAT | 525 |
| STRAWBERRY | 426 |
| CARROT | 327 |
| MILK | 327 |
| TOMATO | 228 |
| EGG | 228 |
| WOOL | 228 |
| MELON | 30 |
| FERTILIZER | 0 |

Esses números foram derivados independentemente a partir da frequência das lojas e do Town Center e conferidos por participantes recentes. Como as lojas são sorteadas com reposição, a partida real pode divergir fortemente da média. citeturn26search0

Isso deixa claro por que **MELON é um timing game brutal**: nenhuma loja especializada consome melon; praticamente todo o sink natural vem do Town Center. Strawberry, milk e wool possuem muito mais demanda estrutural. citeturn26search0

Mas a média não é uma política. A política deveria utilizar o **shop genome da partida atual**.

Um plant forecaster poderia calcular:

```text
market_inventory_at_harvest
=
inventory_now
- known_town_demand_until_harvest
+ expected_our_supply
+ expected_opponent_supply
```

e então aplicar a própria `market_price()` do engine sobre essa projeção.

Por exemplo, no momento do replantio:

```python
score_carrot = expected_carrot_price_at_day_3
score_wheat  = expected_wheat_price_at_day_4
score_tomato = stream_value_from_day_8
```

O ponto crucial é **tomar essa decisão somente em slots estruturalmente seguros**, quando o tile acaba de ficar vazio e o scheduler já tem um `PLANT` válido. Isso é diferente de um overlay `PASS → PLANT` que interrompe uma coreografia pré-computada.

🧠 Eu chamaria isso de **adaptive crop token**:

> Moon continua dizendo “este tile deve ser replantado agora”; o módulo adaptativo escolhe **qual crop ocupa o token de replantio**.

Assim você desacopla **quando agir**, onde Moon é forte, de **o que plantar**, onde o estado real da partida contém informação que a fita não conhecia.

### Existe também um timing de mercado que seu guard pode estar ignorando

A ordem interna do turno é aproximadamente:

1. ações dos workers;
2. mercado;
3. consumo da cidade;
4. refresh/decay/end-of-day conforme aplicável.

Portanto, quando uma loja consome determinado item no turno `s`, uma venda sua no próprio `s` acontece **antes** do consumo; uma venda em `s+1` pode receber o preço já elevado pelo buraco criado pela loja. citeturn18view3

Isso cria um dilema explícito:

> **esperar a demanda da cidade elevar o preço** versus **vender antes de o oponente despejar supply**.

É exatamente um problema de opponent modeling.

### “Vendas fracionadas” precisam ser interpretadas com cuidado

O `_process_market` trabalha os pedidos dos dois jogadores em lockstep por posição da fila e processa quantidade unidade a unidade. Para unidades simultâneas equivalentes, os dois jogadores recebem a cotação a partir do mesmo inventário pré-commit. Isso significa que não existe simplesmente um “player 0 vende primeiro e leva todo o preço melhor” em cada unidade concorrente. citeturn18view2

Isso muda a interpretação do seu `sell_first`.

A vantagem real de front-run está principalmente em:

- **vender um turno antes**;
- escolher melhor a posição relativa dentro da fila de market orders;
- antecipar o dump futuro do rival;
- aproveitar demanda da cidade em momento diferente;
- controlar financiamento para operações que aparecem depois na fila.

Também implica que partir `SELL MELON 20` em muitos pedaços **dentro do mesmo turno**, sem mudar a interleaving relevante, não cria magicamente um preço melhor: o engine já executa as unidades incrementalmente. O grande valor da fragmentação está em **fragmentar através do tempo e reobservar o mercado**, e não apenas transformar um número grande em dez números pequenos. citeturn18view2

Isso talvez explique por que seu v14 “venda fracionada extra” piorou: você pode ter aumentado complexidade sem acrescentar informação nova.

## Opponent modeling: a camada que eu colocaria acima do v19

A evidência externa mais interessante vem do topo. Rishi Gottumukkala relatou recentemente que sua tentativa de RL end-to-end não substituiu com sucesso o sistema heurístico — PPO/Transformer ficou na faixa de 40k — enquanto obteve resultados mais promissores usando aprendizado em **opponent modeling**. citeturn12search0

Isso combina de forma quase perfeita com a estrutura informacional do Kaggriculture.

Você não vê o shed privado do adversário, mas vê:

- fazenda adversária;
- plantas e animais;
- yield visível nos tiles;
- dinheiro público;
- mercado compartilhado;
- lojas;
- mudanças de preço;
- mudanças do market inventory.

Para produtos que o adversário **não pode comprar** do mercado — carrot, tomato, strawberry, melon, egg, milk e wool — a mudança do market inventory contém um sinal quase direto do volume líquido vendido.

Se:

\[
I_t = I_{t-1}
+ sell_{ours}
+ sell_{opp}
- town\_drain
\]

então:

\[
\widehat{sell}_{opp}
=
I_t-I_{t-1}
-sell_{ours}
+town\_drain
\]

com ressalvas como vendas ao preço floor, que o engine trata de maneira especial. Para WHEAT e FERTILIZER a inferência é menos limpa porque o rival também pode usar `BUY_PRODUCT`. citeturn18view2turn18view3

Esse estimador transforma algo aparentemente oculto — **“quando o top costuma vender?”** — em uma variável parcialmente observável.

Eu manteria para cada item:

```text
estimated_opponent_hidden_stock
estimated_next_sale_size
P(sell within 1 turn)
P(sell within 2 turns)
P(sell within 4 turns)
```

e alimentaria o guard com features como:

```text
current_price / recent_price
opponent_visible_mature_units
opponent_recent_harvest
estimated_hidden_stock
turn_mod_4
town_demand_next_turn
our_inventory
market_inventory_delta
opponent_historical_sale_delay
```

Uma política simples já poderia decidir:

```text
se hazard de dump adversário é alto:
    front-run mais agressivamente
elif shop demand acontece agora:
    esperar consumo
else:
    seguir guard v19
```

Isso é superior a média+momentum porque distingue duas situações com o mesmo gráfico de preços:

> “preço está subindo e rival não tem supply”  
> versus  
> “preço está subindo, mas rival acabou de colher 40 unidades”.

Código público recente já mostra agentes rastreando estado anterior do mercado, lojas, próprias ações, preços e grau de similaridade com o adversário para decidir timing; portanto, essa classe de controlador não é apenas uma abstração teórica — ela já aparece no ecossistema competitivo público. citeturn22search6turn10search6

🎯 **Minha prioridade de RL seria exatamente a mesma sugerida pelo relato do #1:** não treinar o fazendeiro inteiro. Treinar um pequeno modelo de **sale hazard / opponent type** e colocá-lo em volta de uma execução determinística confiável.

## Por que o h2h local não está traduzindo em ELO

Aqui há vários problemas sobrepostos.

### O bug do seat 1 é o primeiro suspeito

O relato reproduzível publicado há três dias no fórum usa `kaggle-environments==1.32.7` e mostra:

```text
seat 0: step = 0,1,2,3...
seat 1: step = None,None,None...
```

O próprio autor aponta explicitamente o impacto em agentes indexados por step. citeturn26search2

Para uma arquitetura cuja essência é uma fita de **719 ações**, isso é crítico.

O primeiro teste que eu executaria no v19 seria:

```python
def canonical_step(obs, config):
    turns_per_day = int(config.get("turnsPerDay", 24))
    return int(obs.get("day", 0)) * turns_per_day + int(obs.get("hour", 0))
```

e eliminaria `obs["step"]` como fonte temporal em todos os caminhos.

Depois:

```text
v19 original seat0 vs v19 original seat1
v19 fixed seat0    vs v19 fixed seat1
```

com logs do índice real da fita.

Se o seu bundle já deriva `step` de `day/hour`, ótimo: o item está descartado. Mas, dada a arquitetura Moon, **não vale assumir**. O custo de auditoria é mínimo e o upside potencial é enorme. citeturn26search2

### 62% contra v18 é bem menos conclusivo do que parece

Pelos números que você forneceu:

\[
57/(57+35) = 61,96\%
\]

O intervalo de Wilson de 95% é aproximadamente:

\[
51,7\% \text{ a } 71,2\%
\]

Ou seja, o resultado provavelmente mostra uma melhoria real **contra v18**, mas a precisão ainda é baixa. Mais importante: o adversário é um ancestral altamente correlacionado com o próprio v19.

Isso testa:

> “o novo guard explora melhor os regimes criados pelo v18?”

e não:

> “o v19 vence a população que determina meu rating?”

Ryo Hasegawa, em sua análise pública de submission strategy, chegou exatamente ao ponto operacional: avaliar por adversário, usar bastante volume local, testar as mesmas seeds e lembrar que o campo muda. Ele também estimou que ratings live ainda carregam dezenas de pontos de ruído mesmo depois de muitos episódios. citeturn26search4

Há uma segunda inconsistência a corrigir na telemetria interna: você registra v17 como **57W–37L em 144 jogos**, mas `57+37=94`. Se os 50 restantes foram draws, invalids ou outra classe, isso precisa aparecer explicitamente no harness; do contrário, a taxa de vitória usada para promoção pode estar sendo calculada sobre denominadores diferentes.

### O seed não é um controle perfeito entre arquiteturas diferentes

Um achado público particularmente relevante é que o sorteio das lojas compartilha fluxo de aleatoriedade com processos ligados ao estado das fazendas. Participantes demonstraram que **o mesmo seed pode acabar com uma sequência de lojas diferente quando bots estruturalmente diferentes alteram o número/estado de tiles envolvidos nas chamadas anteriores de RNG**. citeturn26search0turn8search10

Isso significa:

> `seed 123, bot A vs X` e `seed 123, bot B vs X`

não são necessariamente a mesma economia externa.

Para pequenas alterações no v18→v19, muitas vezes o shop draw continuará igual; quando você testar um scheduler estrutural, ele pode mudar. Portanto, seu atual controle por seed perde força exatamente quando começar a testar as mudanças mais importantes.

Eu passaria a registrar uma assinatura como:

```text
shop_genome = (
  shop_at_day_3,
  shop_at_day_6,
  shop_at_day_9,
  ...
)
```

e compararia resultados também por **regime realizado**, não apenas por seed original.

### O ladder e o torneio final têm uma população própria

O esclarecimento oficial atual é que o Bradley–Terry final usa **todos os episódios da competição entre agentes que ainda estiverem ativos**, e os dois lados do episódio precisam continuar ativos. citeturn26search1

Isso tem uma consequência estratégica importante: suas duas submissões finais são também uma escolha de **dataset efetivo**.

Um agente pode:

- ganhar de v18 em 62%;
- ganhar de Moon em 70%;
- perder de Barnyard-style em 40%;
- perder de opponent-aware em 35%;

e ainda apresentar h2h interno espetacular.

A unidade correta de validação é portanto:

\[
W/L(opponent\ family,\ seat,\ shop\ regime)
\]

e não apenas:

\[
W/L(\text{v19}, \text{v18})
\]

### Seu gate de 24–36 seeds é bom para regressão, não para detectar +3pp

Como regra prática, 48–72 resultados são ótimos para matar cedo mudanças que produzem 30%, 40% ou 70% de win rate. São muito fracos para provar melhorias de 52–55%.

Aproximadamente, detectar uma taxa real de **55% contra 50%** com poder estatístico convencional exige centenas de partidas — da ordem de **600–800**, dependendo de teste unilateral/bilateral e desenho experimental. Uma taxa de 60–62% é detectável bem antes.

Portanto eu manteria seu processo, mas mudaria a interpretação:

```text
48–72 jogos:
    filtro de catástrofe / sinal grande

144 jogos:
    filtro intermediário

painel amplo + paired analysis:
    promoção estratégica
```

E sempre com **seat swap**.

## Arquitetura que eu tentaria agora: Moon chassis, executor novo

Eu não substituiria o Moon por um FarmBrain global. Seus ~52 experimentos já são evidência suficiente de que essa direção destrói dependências úteis.

Também há evidência pública recente na mesma direção. O notebook público **[STRONG] Barnyard Economist** apareceu com score público acima de 3000 e se descreve em torno de “queue-aware farming”, preservação de rota e camadas de controle, em vez de uma reconstrução total do agente. citeturn22search0

🛑 Eu construiria o próximo ramo como:

> **Moon macro-plan + Pipeline Scheduler + Demand Forecaster + Opponent Flow Model**

não como “v20 = mais um overlay”.

### A camada de execução

O Moon continua responsável por decisões cuja coreografia já provou valor:

```text
opening
land unlock
animal layout
macro route
baseline economy
```

O novo scheduler só assume **slots de produção explicitamente autorizados**.

Para cada tile ele constrói um pequeno DAG:

```text
WHEAT one-shot
HARVEST
   ↓
PLANT
   ↓
WATER
```

```text
TOMATO ongoing
HARVEST ──────────┐
                  ↓
            FERTILIZE?
                  ↓
                WATER
```

```text
COW
FEED ───────────────┐
CARE ───────────────┤
HARVEST ────────────┤
COLLECT_FERT ───────┘
```

Então atribui workers por:

\[
score(unit,task)
=
value(task)
-
\lambda \cdot distance
-
\mu \cdot reassignment
+
stickiness
\]

A chave é **stickiness**. Um worker não sai atravessando o mapa atrás do próximo score marginalmente maior; ele termina um bundle local antes de mudar de zona.

### O controller de HIRE

Não use:

```python
if money > X:
    HIRE
```

Use:

\[
hire\ if\ 
\text{valor das tarefas que o novo hand consegue liberar}
>
fib_{next}
+
buffer
\]

O backlog precisa considerar dependências. Um terceiro worker vale muito quando transforma:

```text
turn t: HARVEST
turn t+1: PLANT
turn t+2: WATER
```

em:

```text
turn t: HARVEST → PLANT → WATER
```

Ele vale muito menos se só reduzir uma caminhada de dois tiles.

### O plant controller

Quando chega a ação `PLANT`, escolha crop por forecast de harvest-time:

```python
candidate_score = {
    crop: forecast_crop_ev(crop, tile, now, shops, opponent)
    for crop in feasible_crops
}
```

Mas comece com apenas **2–4 adaptive slots**, não a fazenda inteira.

A versão 1.32.7 justifica explicitamente revisitar seus resultados negativos de `CARROT/TOMATO tardio`: aqueles experimentos podem ter falhado não porque carrot/tomato são ruins, mas porque eram **overlays por dia/preço**, e não respostas a uma escassez futura causada por uma composição específica de lojas. A própria Kaggle fez a alteração para estimular exatamente decisões situacionais de endgame. citeturn26search5

### O market controller

Preserve o v19 primeiro.

Em cima dele adicione somente dois sinais novos:

```text
town_demand_phase
opponent_sale_hazard
```

Não reabra simultaneamente thresholds, chunk size, buy wheat, fertilizer dump e order sorting. Seus próprios resultados mostram que mudar muitas dessas dimensões juntas mata o agente rapidamente.

### A sequência experimental que eu considero de maior EV

| Prioridade | Experimento | Por que agora |
|---|---|---|
| **P0** | `step` hardening seat 1 | Pode existir falha catastrófica independente da estratégia |
| **P0** | telemetria de throughput | Descobre exatamente onde os 12–15k estão morrendo |
| **P1** | pipeline H→P→W em 2–4 tiles WHEAT | Teste puro da hipótese de compressão temporal |
| **P1** | bundle de serviço em 2 COW | Testa labor + milk + care + fertilizer juntos |
| **P2** | harvest-before-cap em TOMATO | Necessário para fazer fertilizer gerar output real |
| **P2** | adaptive planting em 2–4 slots | Explora lojas sem quebrar a fita |
| **P3** | opponent-flow inference | Melhora front-run sem reconstruir market layer |
| **P4** | scale 8→10→12 hands via backlog | Hands entram como consequência de tarefas reais |

O critério de sucesso do primeiro pipeline não seria inicialmente “ganhou do v19?”. Seria:

```text
+ crop_units/tile-day
- harvest_to_replant_latency
- moves/productive_action
+ final reward
sem degradar survival e shed overflow
```

Só depois ele entra no h2h.

Isso evita repetir o erro clássico das suas 52 abordagens: uma ideia boa em isolamento aparece como ruim porque a infraestrutura necessária para capturar seu valor não estava presente.

## 🎯 Respostas diretas às perguntas abertas e caminho para Top 10

**Por que o h2h local não traduz em ELO?** Porque v19×v18 é um matchup estreito contra um ancestral correlacionado, a amostra de 92 decisões ainda tem intervalo amplo, a composição do field mudou, o RNG das lojas pode mudar junto com alterações estruturais e há agora um possível **bug de seat 1** especialmente perigoso para agentes indexados por step. Além disso, a avaliação final depende dos episódios entre os agentes que permanecerem ativos, não de uma média abstrata contra sua própria família. citeturn26search1turn26search2turn26search4

**Como os tops conseguem mais produção por tile?** A hipótese mecanicamente mais forte é **latência comprimida + routing eficiente + workers coordenados por dependência**. O engine permite vários agentes no mesmo tile e aplica suas ações sequencialmente, tornando possível colher, replantar e regar no mesmo turno. Isso transforma HIRE de “mais movimentos disponíveis” em “mais estágios de uma pipeline disponíveis simultaneamente”. citeturn18view1turn19view2

**Qual adaptatividade de plantio provavelmente falta?** Não `if price high → plant`. É **forecast de preço no harvest**, usando lojas já reveladas, demanda determinística até a maturação, supply próprio previsto e supply adversário inferido. A atualização 1.32.7 praticamente declara essa oportunidade para carrot, tomato e egg. citeturn26search5turn26search0

**Quando fertilizer vale a pena?** Quando o scheduler consegue converter o aumento teórico de produção em **unidades realmente colhidas antes do cap** e o valor dessas unidades supera o preço de venda do fertilizer mais o custo de serviço. Isso favorece especialmente ongoing crops bem servidas. No Moon lento, vender fertilizer pode racionalmente dominar; numa fazenda high-throughput, a desigualdade pode inverter. citeturn24view0turn24view1

**Como escalar mão de obra sem quebrar coordenação?** Não por overlay de HIRE. Por **task DAG + zone assignment + worker stickiness + bundles locais**, contratando o próximo hand somente quando houver backlog de tarefas que paga o próximo Fibonacci. Os primeiros 10 hands somam apenas $143/dia; o gargalo é utilização, não o preço nominal. citeturn17search1turn20search0

**Existe outra economia capaz de 92k+?** Provavelmente não é necessário abandonar a economia Moon. Seu próprio diagnóstico de cows, buy-wheat e premium timing está alinhado com a estrutura do engine. A mudança mais promissora é transformar o Moon de **fita que executa produção** em **chassis que fornece macroestrutura a um executor de produção**. Agentes públicos recentes de score muito alto também enfatizam routing, queue awareness e preservação de estrutura em vez de RL end-to-end; e o relato do líder aponta opponent modeling como uma área mais frutífera que substituir toda a estratégia. citeturn22search0turn12search0

Minha ordem de ataque ao gap de **~12–15k** seria, portanto:

> **seat correctness → telemetria física → same-turn pipeline → animal service bundles → fertilizer-throughput synergy → shop-aware planting → opponent-flow timing → escala de hands.**

O ponto mais importante é que isso também explica por que tantos testes anteriores “logicamente corretos” deram negativo. **Fertilizer, replantio imediato, mais hands e crops tardias não são features independentes.** São componentes de um mesmo sistema de execução. Adicionar uma delas por overlay sobre uma fita que não reposicionou workers, não preservou dependências e não antecipou demanda pode reduzir reward mesmo quando a política completa seria superior.

⚠️ Há duas coisas que esta pesquisa externa não consegue provar sem executar o seu repositório: **se o v19 realmente sofre com o bug de `obs.step`** e **se os tops usam literalmente o pipeline H→P→W descrito acima**. O primeiro é auditável diretamente no bundle; o segundo é uma inferência forte derivada do engine e dos padrões observados, não uma reconstrução vazada de código privado. Também não encontrei evidência confiável de código privado publicado por Crop Dusta/Ryo que permita afirmar a coreografia exata deles. O material público mais sólido aponta antes para **queue-aware execution, route preservation, opponent modeling e adaptação a demanda**. citeturn26search2turn12search0turn22search0

**A aposta de maior valor, hoje, não seria v20 com mais um guard. Seria um ramo experimental “Moon Pipeline”: só 2–4 tiles e 2 cows sob um scheduler de dependências, todo o resto ainda v19.** Se esse microcosmo aumentar `units/tile-day` e reward sem quebrar o resto da fita, você terá finalmente isolado o mecanismo que pode explicar a diferença entre **~80k e 92k+** — e, pela primeira vez, uma mudança estrutural poderá ser escalada em vez de injetada como overlay.