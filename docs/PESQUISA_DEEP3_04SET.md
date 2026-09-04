# Kaggriculture: a nova rota para romper o platô do Moon

## 🛑 Conclusão executiva

A pesquisa muda a prioridade do projeto em dois pontos importantes.

**Primeiro: antes de tentar qualquer nova arquitetura de produção, há um problema de infraestrutura que precisa ser tratado como P0.** O `kaggle-environments` **1.32.7 continua sendo a versão publicada mais recente em 4 de setembro de 2026**, e o código atual de Kaggriculture propaga `farms`, `market`, `town`, `day` e `hour` para o seat 1, mas **não propaga `step`**. citeturn10search0 fileciteturn27file0L11-L58 Isso é especialmente grave para o Moon porque o próprio `moon_v17_goose.py` calcula diretamente:

```python
step = min(max(0, int(_get(obs, "step", 0) or 0)), len(actions) - 1)
...
action = _copy_action(actions[step])
```

ou seja, sua fita inteira depende desse campo. fileciteturn38file0L2-L2 O `build_hybrid_v19.py` repete a mesma dependência no wrapper dos overlays. fileciteturn30file0L2-L2 Há também uma reprodução pública recente exatamente desse defeito no fórum da competição: no ambiente oficial local, o seat 0 recebe `0,1,2...`, enquanto o seat 1 permanece sem `step`. citeturn9search3

Mais preocupante ainda: a **liga de arquétipos atual do repositório não corrige isso**. `league_game.py` chama diretamente `env.run([a,b])`, e `league_bench.py` troca o campeão entre P0 e P1 para “espelhar” os lados. fileciteturn48file0L2-L2 fileciteturn49file0L2-L2 Portanto, **se esses benchmarks estão rodando no stock 1.32.7, o lado P1 dos agentes step-indexed não está executando a mesma política que o lado P0**. Isso coloca uma interrogação sobre parte das conclusões locais recentes — inclusive sobre o diagnóstico de que “mirror não prediz ladder”. Não significa que as ~57 refutações sejam todas falsas; significa que resultados executados sob essa configuração precisam ser classificados por versão do engine e revalidados após um relógio robusto.

**Segundo: a melhor nova implementação não é outro coordenador global, nem outro overlay de HIRE.** A alternativa que emerge da semântica do engine e das falhas anteriores é um **Tape-Preserving Transaction Scheduler**: aproveitar slots de ação do próprio Moon para executar pequenos **bundles completos e position-invariant**, sem alterar a trajetória espacial esperada pela fita. A primeira aplicação deve ser **HARVEST→PLANT→WATER transacional** em crops e **FEED→CARE phase-locked** em COWs. O ponto central é que os experimentos anteriores alteravam uma ação; a nova proposta altera a **transação inteira**, preservando as invariantes da fita.

Minha ordem de prioridade, portanto, mudou para:

| Prioridade | Trabalho | Razão |
|---|---|---|
| **P0** | Corrigir relógio `step` em ambos os seats + revalidar harness | Sem isso, não há benchmark confiável |
| **P1** | Medir **semantic no-ops** e **day-slip**, não só PASS/MOVE | Revela capacidade escondida dentro da fita |
| **P2** | **Tape-Preserving H→P→W** em 2–4 microcélulas | Testa compressão sem quebrar routing |
| **P3** | **Phase-Locked Cow Service**: FEED+CARE na paridade correta | Pode gerar MILK adicional e até economizar FEED |
| **P4** | Auditoria `successful_hires / usable_hand_turns` | Corrige a leitura dos “591 HIRE” |
| **P5** | Só depois: crop token, fertilizer high-throughput e scheduler maior | São complementos, não fundação |

Essa direção também é consistente com a evidência pública: um participante que estudou o engine relata que seu maior ganho operacional veio de **terminar o trabalho no tile antes de voltar a caminhar**, e que walking — não simplesmente custo de HIRE — dominava a ineficiência. citeturn11search2 E Rishi Gottumukkala, aparecendo como primeiro colocado nas discussões recentes, afirmou que suas submissões competitivas eram essencialmente heurísticas; RL end-to-end ficou muito abaixo, enquanto opponent modeling foi a área em que viu mais utilidade. citeturn9search2turn11search7

## ⚠️ O benchmark atual tem dois problemas mais sérios do que parecia

### O bug de relógio precisa ser tratado como uma falha experimental, não como detalhe

O código oficial inicializa `day` e `hour` para os outros jogadores, mas o `step` não aparece nessa sincronização. No interpreter, a cada turno, a sincronização do seat 1 novamente copia apenas `farms`, `market`, `town`, `day` e `hour`. fileciteturn26file0L2-L2 fileciteturn27file0L11-L58

O Moon atual, porém, seleciona literalmente `actions[step]`. fileciteturn38file0L2-L2 Portanto, a correção não deve ser um guard localizado no `v19`; deve existir **uma única fonte canônica de tempo** para Moon, overlays, telemetria e harness:

```python
def logical_step(obs, config=None):
    turns_per_day = int(
        getattr(config, "turnsPerDay", 24)
        if config is not None
        else 24
    )
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    return day * turns_per_day + hour
```

O ideal é reconstruir `step` a partir de `day/hour` **sempre**, mesmo quando `obs["step"]` existe, para que P0 e P1 tenham exatamente a mesma semântica. A discussão pública que identificou o problema recomenda precisamente `day * turnsPerDay + hour` como workaround, porque esses dois campos são sincronizados. citeturn9search3

Há uma consequência importante: `sweep_v18_refinado.py`, por exemplo, executa primeiro `[candidate, v18]` e depois `[v18, candidate]`, mas o candidato calcula o passo com `obs.get("step",0)`, e o `v18` subjacente é Moon-derived. fileciteturn51file0L2-L2 Isso não permite concluir automaticamente que o histórico v18/v19 está errado — é preciso saber exatamente qual versão local executou cada sweep —, mas **qualquer resultado produzido atualmente com 1.32.7 stock deve ser marcado como “clock-unverified”**.

Eu criaria imediatamente um teste de CI muito simples:

```text
seat 0 logical_step: 0 1 2 3 ... 719
seat 1 logical_step: 0 1 2 3 ... 719

Moon tape index P0 == logical_step
Moon tape index P1 == logical_step
```

Só depois desse teste passar eu voltaria a usar `league_bench.py` como gate.

### Mesmo seed não significa exatamente a mesma partida estrutural

Há ainda um segundo confounder mais sutil. No `_end_of_day`, o engine cria um RNG a partir de `seed` e `day`; em seguida usa **esse mesmo RNG** para tentar gerar weeds nos tiles vazios de cada fazenda e, depois, para sortear a nova loja. fileciteturn25file0L161-L340 Como `_spawn_weeds` chama `rng.random()` apenas para tiles vazios, duas estratégias que alteram o número ou a posição temporal de tiles vazios podem consumir uma quantidade diferente de números aleatórios antes do `rng.choice` que escolhe a loja. fileciteturn25file0L161-L340

Isso significa:

> **para mudanças estruturais, “mesmo seed” não garante “mesma sequência de shops”.**

Esse detalhe importa muito agora, porque justamente uma variante H→P→W muda quanto tempo tiles permanecem vazios. Um ganho ou perda de vários milhares em uma única seed pode vir parcialmente de uma trajetória de lojas diferente, e não da produção.

Por isso eu faria dois tipos de benchmark:

**Benchmark mecanístico:** harness experimental com sequência de shops congelada ou RNG de shops desacoplado, exclusivamente para medir `crop_units`, `day-slip`, CARE realizado e eficiência de ações.

**Benchmark competitivo:** engine oficial, sem modificação, duas posições e liga de arquétipos, porque é essa distribuição real que interessa no final.

O primeiro responde “a engenharia produz mais?”. O segundo responde “essa produção ganha jogos?”.

Essa distinção também ajuda a explicar por que um candidato pode melhorar reward local sem melhorar o ladder. O mercado é compartilhado e pair-dependent; além disso, o objetivo da competição é W/L, e a avaliação final usará um único torneio Bradley–Terry após a janela pós-deadline, conforme esclarecimento oficial da Kaggle. citeturn11search10 Ryo Hasegawa também vem recomendando empiricamente avaliar win-rate contra a população relevante, em vez de usar coin total como único objetivo. citeturn11search8

## 🧠 A telemetria estava medindo a latência certa na unidade errada

O dado de **18–33 turns entre HARVEST e replant** é útil, mas o engine revela que a métrica economicamente decisiva não é exatamente “turns”.

O crescimento de crops é indexado por **dia**. Uma planta guarda `planted_day`, e os testes de maturação usam `day - planted_day`; não usam o número exato do turno dentro daquele dia. fileciteturn26file0L191-L357

Isso produz uma diferença enorme entre estes casos:

```text
HARVEST h00 → PLANT h22 do mesmo dia
latência = 22 turns
day-slip = 0

HARVEST h23 → PLANT h00 do dia seguinte
latência = 1 turn
day-slip = 1
```

Apesar de a primeira latência ser vinte e duas vezes maior em turns, **a segunda é muito pior para a próxima maturação**, porque mudou `planted_day`.

Portanto eu substituiria a métrica central:

```text
harvest_to_replant_turns
```

por:

```text
harvest_day
plant_day
replant_day_slip = plant_day - harvest_day

plant_hour
first_water_hour
water_before_eod = yes/no
```

Esse ajuste pode revelar que parte dos “592 tile-days” já estava sendo contada corretamente, mas que a média de 18–33 turnos mistura atrasos irrelevantes dentro do mesmo dia com atrasos caríssimos que cruzam a meia-noite.

### O detalhe que explica por que PASS→PLANT pôde falhar tão violentamente

Aqui está, na minha avaliação, a descoberta mecânica mais importante para reinterpretar uma das suas refutações.

Quando `PLANT` cria uma planta, o engine a inicializa assim:

```python
"watered_today": False,
"consecutive_unwatered": 1
```

O **dia do plantio já conta como um dia sem água**. fileciteturn26file0L2-L2

No refresh noturno, se a planta ainda não foi regada, o engine incrementa esse contador. Ao atingir `2`, a planta é transformada em `WEED`. fileciteturn25file0L161-L340

Logo:

> **qualquer replantio que não garanta WATER antes do fim daquele mesmo dia cria uma dependência fatal.**

Isso altera a interpretação do experimento anterior **PASS→PLANT = 1–8**. Ele não testou realmente a hipótese “replantio imediato é ruim”; ele testou algo mais próximo de:

> “inserir PLANT isoladamente dentro de uma fita que não prometeu atender a nova obrigação de WATER”.

Essas são hipóteses diferentes.

O engine trata ações inválidas ou impossíveis como **silent no-ops**. fileciteturn26file0L2-L2 Portanto, uma fita pode conter muito mais capacidade desperdiçada do que o `PASS = 8,2%` sugere. Exemplos são WATER em planta já regada, HARVEST sem yield disponível, FEED em animal já alimentado, CARE duplicado, PLANT sem seed ou sobre tile ocupado. Todas essas ações aparecem na fita como “trabalho”, mas economicamente podem produzir **zero mutação útil de estado**. fileciteturn26file0L191-L357

🛑 Isso sugere uma nova telemetria antes de escrever um scheduler:

```text
TEXTUAL_PASS
MOVE

EFFECTIVE_NOOP
USEFUL_STATE_MUTATION

USEFUL_WATER_YIELD
SURVIVAL_ONLY_WATER
REDUNDANT_WATER

HARVEST_REAL
HARVEST_NOOP
FEED_REAL
FEED_NOOP
CARE_REAL
CARE_NOOP
```

A pergunta deixa de ser “onde há PASS?” e passa a ser:

> **onde a fita já reserva um turno de unidade, mantém a posição correta, mas o comando daquele turno não cria valor?**

Esses são os slots onde podemos colocar produção nova sem pagar mais HIRE e sem destruir o routing.

## 🎯 A nova arquitetura: Tape-Preserving Transaction Scheduler

As tentativas anteriores parecem compartilhar um padrão de falha: o Moon é uma fita com **estado implícito de posição**. Quando um overlay substitui um movimento, adiciona um hand ou mantém um worker parado onde a fita esperava que ele andasse, o erro não termina naquele turno. A fita seguinte assume que o trabalhador está em outro lugar; daí surgem ações sobre tiles errados, inventários errados e cascatas de no-op.

A re-coreografia de zonas tentou resolver isso globalmente, mas o custo e a coordenação da nova frota derrubaram o agente; o próprio relatório termina com extras 8–12 em 0–24 e extras 13+ também 0–24, com reward fortemente negativo. fileciteturn41file0L2-L2

Minha proposta é atacar exatamente essa propriedade, e não lutar contra ela.

### O princípio: nunca mudar a posição que a fita espera

Para cada ação original do Moon, classifique:

```text
MOVE        -> proibido tocar no protótipo
NON_MOVE    -> candidato
PASS/NOOP   -> candidato ideal
```

O novo executor só pode substituir uma ação do Moon quando:

1. o worker já está no tile relevante;
2. a ação original **não moveria** o worker;
3. a ação substituta também **não move** o worker;
4. inventário/seeds necessários estão garantidos;
5. a transação inteira tem deadline atendível;
6. a ação retirada do Moon tem valor marginal inferior à ação inserida.

Assim:

```text
posição antes:  (x,y)
Moon original:  PASS / WATER redundante / HARVEST no-op
novo comando:   HARVEST / PLANT / WATER / CARE
posição depois: (x,y)
```

O próximo frame da fita continua recebendo **o worker exatamente na coordenada que esperava**.

É essencialmente uma cirurgia local que preserva a coluna vertebral do Moon.

Eu chamaria a primeira versão de:

> **TPS-v0 — Zero-Displacement Splicer**

Ela não decide a economia da fazenda. Não decide quantas vacas comprar. Não cria terra. Não escolhe automaticamente tomate. Ela apenas encontra capacidade perdida no executor existente.

### H→P→W realmente pode ser feito no mesmo turno

O interpreter constrói `[farmer, *hands]`, faz uma validação prévia de sementes e então aplica **farmer primeiro e cada hand sequencialmente sobre o mesmo estado mutável**. fileciteturn27file0L11-L58

Portanto, se três workers estão no mesmo tile e seus índices de execução são adequados:

```text
actor A: HARVEST
         tile one-shot vira None

actor B: PLANT WHEAT
         vê o tile agora vazio e cria a nova planta

actor C: WATER
         vê a planta recém-criada e a rega
```

é mecanicamente válido. fileciteturn26file0L191-L357

Há duas restrições cruciais que o scheduler deve saber.

A primeira é **ordem de actor**. O harvester precisa ser processado antes do planter, e o planter antes do waterer. Como farmer vem primeiro e hands seguem índice crescente, não basta ter três trabalhadores na célula; o TPS precisa atribuir os papéis segundo a ordem real de execução. fileciteturn27file0L11-L58

A segunda é a validação atômica de PLANT: se, num turno, a demanda total por uma seed exceder o estoque, **todas as PLANT daquele crop viram PASS** antes da execução. fileciteturn27file0L11-L58 Então o scheduler precisa reservar seeds antes de emitir o bundle. Um erro de uma única unidade pode derrubar simultaneamente vários replants.

O protótipo deveria ser deliberadamente pequeno:

```text
2–4 tiles WHEAT
sem HIRE novo
sem novo crop
sem alteração de market
sem fertilizer

somente:
HARVEST + PLANT + WATER
quando pode preservar posições
```

Isso isola a pergunta certa:

> **é possível capturar day-slip sem destruir o estado implícito da fita?**

Se sim, você não precisa trocar o Moon inteiro ainda.

### Há um segundo modo, ainda mais fácil: splice temporal de um único worker

Nem sempre serão encontrados três workers no mesmo tile. O mesmo conceito pode operar por pequena reserva temporal:

```text
turn t:   HARVEST
turn t+1: PLANT
turn t+2: WATER
```

mas **somente** se a posição prevista pelo Moon para aquele actor continuar a mesma durante a janela, ou se as ações originais nesses turns também fossem stationary. O worker recebe um `reservation_lock` de 2–3 turns e depois devolve o controle à fita sem qualquer desvio de coordenada.

Aqui o deadline é obrigatório: se `PLANT` ocorrer perto da noite, WATER precisa acontecer antes do refresh; em `hour=23`, só se deve plantar quando o WATER puder ocorrer **no mesmo turno com outro worker**. A mecânica da planta recém-criada torna isso uma constraint, não uma heurística. fileciteturn26file0L2-L2 fileciteturn25file0L161-L340

Essa é a diferença fundamental para o antigo `PASS→PLANT`: **não fazemos uma substituição de verbo; fazemos commit de uma transação com todas as dependências garantidas.**

## 🐄 A alavanca animal mais promissora é mais específica que “CARE esparso”

O código de animais revela uma estratégia particularmente elegante para COW que não aparece como tal nas abordagens anteriores: **Phase-Locked Cow Service**.

Uma COW tem `first_yield_day=8`, intervalo de produção `2` e `max_held=6`. fileciteturn47file0L2-L2 No refresh:

1. dois dias consecutivos sem feed fazem o animal escapar;
2. numa noite produtiva, o bônus de CARE **já acumulado** é consumido somente se a vaca estiver fed;
3. a produção `base + bonus` entra no tile;
4. **depois** disso, o CARE do dia atual, se combinado com feed, é armazenado para uma produção futura. fileciteturn25file0L161-L340

Essa ordem produz uma propriedade surpreendentemente útil.

### Para COW, feed a cada dois dias pode alinhar perfeitamente sobrevivência e produção

Considere uma vaca colocada no dia `p`.

O primeiro refresh produtivo é aquele que avança o jogo para `p+8`, ou seja, no fim do dia `p+7`; depois, produção ocorre a cada dois dias. Isso decorre diretamente de:

```python
days_since_first =
    next_day - placed_day - first_yield_day
```

e do teste `% interval == 0`. fileciteturn25file0L161-L340

Agora alimente e cuide da COW somente nos dias:

```text
p+1
p+3
p+5
p+7   <- primeira noite produtiva
p+9
p+11
...
```

Isso produz quatro efeitos simultâneos:

**A vaca não foge.** Há no máximo uma noite não alimentada entre feeds; o escape exige duas consecutivas. fileciteturn25file0L161-L340

**Todas as noites produtivas são fed.** A paridade do serviço coincide com a paridade de produção.

**CAREs anteriores ao primeiro yield acumulam.** CARE em `p+1`, `p+3` e `p+5` cria três créditos antes da primeira produção. Na primeira noite produtiva, isso pode resultar em `1 base + 3 bonus = 4 MILK`, ainda abaixo do `max_held=6`. fileciteturn25file0L161-L340 fileciteturn47file0L2-L2

**O CARE feito na própria noite produtiva não melhora aquela produção; ele fica banked para a próxima.** Assim, depois do primeiro ciclo, o regime tende para **2 MILK por tick em vez de 1**, com apenas um CARE por intervalo produtivo, desde que o produto seja colhido com frequência suficiente para não bater no cap. fileciteturn25file0L161-L340

Esse ponto refina bastante a hipótese anterior de “CARE esparso”.

🛑 A estratégia não deveria ser simplesmente:

```text
CARE uma vez a cada dois dias
```

mas:

```text
CARE + FEED na paridade exata da produção da COW
```

Eu chamaria isso de **production-phase locking**.

Para dez vacas, uma unidade marginal adicional em vários ciclos já chega à ordem de grandeza material em MILK, cujo preço-base atual é $160; mas o valor monetário realizado será menor e dependerá de glut, vendas do oponente, clipping e timing. fileciteturn47file0L2-L2 O importante é que isso oferece uma rota para obter CARE sem tentar o regime caro de CARE diário que matou o Shadow Crew.

### Melhor ainda: isso pode liberar trabalho em vez de adicionar trabalho

Se a telemetria mostrar que o Moon está alimentando determinadas COWs **todos os dias**, existe potencial para uma troca interessante:

```text
antes:
FEED d0
FEED d1
FEED d2
FEED d3
...

depois:
FEED + CARE somente na fase correta
skip
FEED + CARE
skip
...
```

O número de FEED pode cair aproximadamente pela metade para uma COW em regime estável, enquanto o CARE passa a gerar bônus. Essa é uma hipótese de implementação; ela precisa ser validada contra o cronograma real da fita e a fase de cada animal. A condição de segurança vem diretamente do contador de dois dias sem feed. fileciteturn25file0L161-L340

Isso é muito diferente de “adicionar um hand para CARE”.

É potencialmente:

> **substituir manutenção redundante por manutenção produtiva.**

Eu instrumentaria imediatamente:

```text
cow_id / tile
placed_day
production_phase

feed_days
feed_on_production_day
care_days

pending_care_before_tick
care_bonus_consumed
milk_added
milk_clipped_by_maxheld

consecutive_unfed
```

e procuraria a oportunidade:

```text
existing Moon FEED
+ worker stationary/co-located
→ CARE splice sem MOVE
```

O `TPS` e o `Phase-Locked Cow Service` são complementares: o primeiro fornece o mecanismo de intervenção segura; o segundo fornece um job animal de alto ROI.

### CARE deve vencer COLLECT_FERTILIZER por valor marginal, não por regra fixa

Todo animal sobrevivente recebe `fertilizer_available=True` no refresh; como o flag é booleano, fertilizer não acumula no tile. fileciteturn25file0L161-L340 Portanto, em algumas visitas uma COW pode oferecer simultaneamente:

```text
FEED
CARE
HARVEST
COLLECT_FERTILIZER
```

Não tente fazer tudo automaticamente.

O scheduler deveria atribuir um **shadow value** ao slot estacionário. CARE compra uma unidade futura de MILK se o bônus puder ser realizado; fertilizer gera uma unidade cujo mercado não recebe consumo do Town Center e cuja curva atual tem base $100. fileciteturn47file0L2-L2 Como seu próprio Moon já mostrou que fertilizer vendido cedo pode valer mais que fertilizer mal utilizado, o desempate deve ser econômico:

```text
CARE_value =
    P(realização)
    × expected_future_milk_price
    × P(no_clipping)

FERT_collect_value =
    expected_fert_sale_price
    - inventory / market externality

escolher maior valor marginal
```

Isso também explica por que “fert farm” global falhou sem refutar fertilizer em regime high-throughput. Para crops ongoing, o refresh adiciona 2 unidades em vez de 1 quando há água + fertilizer, mas continua limitado por `max_yield`. fileciteturn25file0L161-L340 Sem harvest frequente, o bônus fertilizado bate no cap e desaparece economicamente.

## 💰 A auditoria de HIRE precisa medir capacidade útil, e há uma correção importante

A conclusão de `PESQUISA_DEEP2.md` de que **HIRE command count ≠ successful hires** está correta. O código oficial calcula o custo Fibonacci, testa o dinheiro e simplesmente retorna se não houver saldo; somente uma contratação bem-sucedida incrementa `hires_today` e adiciona um hand. fileciteturn25file0L1-L160 O próprio relatório já propõe `HIRE_ORDERS`, `SUCCESSFUL_HIRES`, `HAND_TURNS` e `PAID_LABOR_COST`, que são métricas muito superiores ao bruto 591–602. fileciteturn43file0L2-L2

Há, porém, mais uma métrica que eu acrescentaria:

> **USABLE_HAND_TURNS_PER_HIRE**

Isso ocorre porque a ordem do interpreter é:

```text
aplica ações do farmer/hands existentes
→ processa market, incluindo HIRE
→ ...
→ se for fim do dia, apaga todos os hands
```

fileciteturn27file0L11-L58 fileciteturn25file0L161-L340

Logo, um hand contratado no turno atual **não pode trabalhar naquele mesmo turno**. E todos os hands são resetados no fim do dia. Portanto, num dia de 24 horas:

| Hora do HIRE | Máximo de ações úteis restantes daquele hand |
|---:|---:|
| 0 | 23 |
| 6 | 17 |
| 12 | 11 |
| 18 | 5 |
| 22 | 1 |
| **23** | **0** |

Isso corrige uma pequena imprecisão de análises anteriores que tratavam um hire no início do dia como até 24 ações. O máximo é **23**, porque ele só entra depois da fase de ações do turno de contratação. fileciteturn27file0L11-L58

E existe um caso particularmente absurdo:

> **um HIRE bem-sucedido em hour 23 cobra dinheiro e o hand é apagado no refresh antes de executar qualquer ação.**

Isso precisa aparecer na auditoria dos tops e do Moon.

A sequência marginal continua sendo `1,1,2,3,5,8,13,21,34,55,89,144...`. fileciteturn25file0L1-L160 Assim, o décimo hand marginal custa $55. Se contratado em h0, isso representa cerca de **$2,39 por ação potencial**; em h12, **$5 por ação**; em h18, **$11 por ação**; em h22, **$55 por uma única ação potencial**.

Portanto, eu substituiria:

```text
top HIRE = 591
Moon HIRE = 277
```

por uma tabela diária:

```text
hire_orders
successful_hires
hire_hour_histogram
paid_labor_cost

available_hand_turns
usable_hand_turns_after_hire
productive_hand_turns

moves
effective_noops
useful_work
```

e calcularia:

\[
\textbf{Labor Utilization}
=
\frac{\text{useful state-mutating actions}}
{\text{usable farmer + hand turns}}
\]

e:

\[
\textbf{Labor ROI}
=
\frac{\text{marginal physical production value}}
{\text{paid labor cost}}
\]

Isso provavelmente responderá melhor à pergunta “como os tops conseguem 10–15 hands?” do que simplesmente contar HIRE.

Há evidência externa compatível com esse raciocínio. Um participante relatou que dez hands custam $143, mas que sua primeira implementação gastava 83% dos unit-turns andando; mudar o executor para terminar o trabalho no tile antes de caminhar reduziu drasticamente essa fração e aumentou fortemente o resultado. citeturn11search2 Isso não prova que os tops usam exatamente o TPS proposto aqui, mas reforça a tese de que **mão de obra barata só é barata quando não é convertida em caminhada**.

## 🔬 O experimento que eu executaria agora

Eu não implementaria ainda o “Moon chassis + executor novo” inteiro. Há uma ponte muito menos arriscada entre fita pura e scheduler global.

### Fase de saneamento experimental

Antes de mexer em produção:

```text
CLOCK-0
- logical_step = day*24 + hour
- injetar o mesmo clock no Moon e em TODOS os overlays
- corrigir league_game / sweep harness
- logar engine version + engine SHA
- assert P0/P1 clock progression
```

O pacote publicado continua em 1.32.7 no momento desta pesquisa. citeturn10search0

Depois eu reexecutaria **somente alguns canários**, não as 57 ideias:

```text
v19 vs v18
immediate replant
Shadow CARE
HIRE overlay
fertilise
```

O objetivo não é reabrir tudo; é medir quanto o bug de seat contaminou as conclusões históricas. Se os resultados permanecerem essencialmente iguais, ótimo: as refutações ganham muito mais confiança.

### Fase de telemetria sem alterar a política

Adicionar um “shadow interpreter” que classifique o comando Moon antes de executá-lo:

```text
MOVE
PASS
SILENT_NOOP
USEFUL_NONMOVE
```

E medir:

```text
same_tile_stationary_windows length >= 2
same_tile_worker_count >= 2/3

harvest_replant_same_day
harvest_replant_next_day
plant_water_same_day
plant_without_water_eod

crop_tile_days_empty
productive_crop_tile_days
```

A variável que eu mais quero ver é:

> **quantos stationary/no-op action slots existem exatamente sobre tiles produtivos?**

Se forem poucos, TPS não tem área de atuação e podemos matar a hipótese barato.

Se forem muitos, finalmente encontramos “mão de obra escondida” que não exige HIRE.

### Fase TPS-crop

Variante A:

```text
v19-clockfix
```

Variante B:

```text
v19-clockfix
+ transactional HARVEST→PLANT
+ WATER garantido antes de EOD
+ somente WHEAT
+ máximo 2 tiles
+ zero HIRE
```

Variante C:

```text
igual B
+ até 4 tiles
```

Nenhuma delas deve trocar crop, comprar terra ou fertilizar.

Critérios mecanísticos antes de olhar reward:

```text
replant_day_slip ↓
plant_without_water_eod = 0
new_weeds_from_transaction = 0
worker_position_drift = 0
seed_atomic_failures = 0
```

Só depois comparar produção.

### Fase TPS-cow

Separadamente:

```text
v19-clockfix
+ COW phase detector
+ FEED/CARE na phase correta
+ no new HIRE
+ CARE somente via stationary splice
```

O critério não é inicialmente reward. É:

\[
\text{CARE realization rate}
=
\frac{\text{extra MILK realmente criado}}
{\text{CARE actions executados}}
\]

e:

```text
cow escapes = 0
care lost on unfed production = 0
milk clipped by max_held ≈ 0
```

Depois testar a versão que reduz FEED redundante, caso a telemetria prove que o Moon alimenta COW acima do necessário.

### Fase combinada

Somente se crop e cow funcionarem isoladamente:

```text
v19-tps
├── Moon macro/tape
├── v19 market overlays
├── robust clock
│
└── Transaction Splicer
    ├── position-invariant only
    ├── H→P→W crop bundles
    ├── phase-locked COW service
    ├── semantic-noop reclamation
    └── no HIRE by default
```

O HIRE entra **depois**, como resposta a um backlog de transações já economicamente comprovadas:

```text
hire only if
expected_value(backlog executable before EOD)
>
marginal_hire_cost
```

e nunca:

```text
hire because top has more hands
```

### Gate competitivo corrigido

Depois do ganho físico:

```text
MECHANISM LAB
→ frozen shop schedule
→ mesmas condições estruturais
→ produção física

OFFICIAL ENGINE
→ 2 seats
→ robust clock
→ seeds de referência

ARCHETYPE LEAGUE
→ v19
→ v18
→ cow-heavy
→ crop-heavy
→ goose/egg
→ market-aggressive
→ top-like/public strong

LARGE VALIDATION
→ somente candidatos sobreviventes
```

Como shops podem divergir estruturalmente mesmo no mesmo seed, eu registraria explicitamente o vetor:

```text
shops = [...]
```

em cada jogo e separaria:

```text
Δreward total
Δreward conditional on same shop path
```

Isso reduzirá bastante a chance de uma “melhoria” ser simplesmente uma mudança de RNG.

## 🎯 Veredito estratégico

Depois de cruzar o código atual do engine, o Moon, os harnesses do repositório, os relatórios estruturais e as discussões recentes da competição, eu **não começaria pela Alavanca 8, o executor DAG completo**.

Eu faria uma etapa intermediária que ainda não foi realmente testada:

> 🛑 **preservar a fita como sistema de routing, mas transformar seus action slots estacionários ou semanticamente inúteis em microtransações completas.**

Essa abordagem resolve diretamente a razão pela qual os patches anteriores quebravam:

```text
OLD OVERLAY
ação isolada
→ cria dependência nova
→ fita não sabe dela
→ worker desvia
→ estado futuro diverge
→ cascata de falhas
```

contra:

```text
TRANSACTION SPLICE
detecta capacidade local
→ garante dependências
→ executa bundle
→ não muda posição
→ satisfaz deadline EOD
→ devolve exatamente o worker à fita
```

O **HARVEST→PLANT→WATER** é especialmente promissor porque a mecânica mostra que PLANT isolado é perigoso: a planta nasce já com `consecutive_unwatered=1`, de modo que a antiga tentativa de replantio não avaliou a transação completa. fileciteturn26file0L2-L2 fileciteturn25file0L161-L340 E o **Phase-Locked Cow Service** é ainda mais interessante porque a COW combina intervalo produtivo de dois dias com tolerância de exatamente uma noite sem feed; isso permite sincronizar FEED e CARE com os ticks úteis em vez de manter um Shadow Crew diário. fileciteturn47file0L2-L2 fileciteturn25file0L161-L340

Minha aposta de pesquisa ficaria assim:

| Hipótese | Confiança | Impacto potencial | Custo de testar |
|---|---:|---:|---:|
| **Clock P1 está contaminando benchmark stock 1.32.7** | **Muito alta localmente** | **Enorme** | Muito baixo |
| **Raw turn latency deve virar day-slip** | **Muito alta** | Alto para diagnóstico | Baixo |
| **Semantic no-ops escondem capacidade livre** | Alta | Alto | Baixo |
| **Transactional H→P→W supera PASS→PLANT** | **Alta** | Alto | Médio |
| **COW phase-lock produz melhor CARE/ação** | **Alta mecanicamente** | Alto | Médio |
| Successful HIRE ≪ HIRE orders dos tops | Média | Médio | Baixo |
| Fertilizer passa a valer após high-throughput | Média-alta | Médio | Médio |
| Adaptive crop token é o próximo grande salto | Média | Situacional | Médio |
| Novo scheduler global agora | Baixa como próximo passo | Potencial alto | **Muito alto** |
| RL end-to-end | Baixa | Baixo no estado atual | Muito alto |

A atualização 1.32.7 reforça ainda que **CARROT/TOMATO/EGG foram deliberadamente tornados situacionais, não universalmente superiores**; a própria Kaggle declarou essa intenção, estimando oportunidades sem produção em cerca de 50% das partidas para tomato, 26% para carrot e 22% para egg. citeturn9search1 Isso é mais uma razão para não gastar o próximo ciclo reconstruindo a economia inteira em torno de crop choice.

O salto que falta, portanto, provavelmente não é “descobrir outro produto mágico”. É fazer o Moon deixar de pensar em **ações** e começar, gradualmente, a pensar em **transações com deadline**, sem abandonar o routing que já levou anos-homem de busca implícita para funcionar.

**A implementação nova que eu escolheria é `v20_tps_cowphase`: clock robusto + semantic-noop detector + position-preserving transaction splices + COW phase-lock, zero HIRE adicional no primeiro experimento.** Ela ataca simultaneamente os três gargalos que sobreviveram às ~57 refutações — **coordenação, produtividade por ação e temporalidade** — sem repetir a estratégia que mais vezes falhou: adicionar capacidade a uma fita que não sabe utilizá-la.