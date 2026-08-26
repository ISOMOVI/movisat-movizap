# 04 — Contrato da IA

O que a IA do MoviZap faz, o que ela **nunca** faz, e como se prova que ela continua fazendo certo.

Motor herdado do MoviChat e **migrado em 2026-08-26**: vive em `movizap/llm/` + `movizap/ia.py`. **Não se reescreve o motor — herda-se** — mas o que se herda são as DECISÕES, não a biblioteca; ver a seção do passo 8, no fim.

---

## Papel

**Triagem inicial no canal de atendimento.** Ela é o primeiro a responder, entende o que a pessoa quer, busca o que dá para buscar, resolve o que é simples e **entrega para o humano com contexto** o que não é.

Ela **não** é uma árvore de menu com linguagem natural por cima. Não existe "digite 1".

```
Objetivo:     cliente resolvido sem espera, e humano recebendo contexto pronto
Hoje:         = o objetivo na Fase 1, só no canal de atendimento
Por quê:      menu numerado não sobrevive a pergunta fora do script, e a maioria é
Reavaliar se: taxa de transferência ficar tão alta que a triagem não esteja poupando ninguém
```

---

## Ferramentas que ela pode chamar

| Ferramenta | O que faz |
|---|---|
| `identificar_contato(telefone)` | quem é, pelo telefone normalizado |
| `dados_cliente(cliente_id)` | razão social, documento, situação |
| `listar_veiculos(cliente_id)` | placas e equipamentos |
| `posicao_veiculo(placa)` | **ao vivo, nunca do cache** |
| `consultar_faturas(cliente_id)` | em aberto e vencidas |
| `historico_conversas(contato_id)` | o que já foi falado |
| `transferir(time, motivo)` | manda para a fila humana |
| `encerrar(motivo)` | fecha quando resolveu |

⚠️ **Toda ferramenta é somente leitura na Fase 1**, com exceção de `transferir` e `encerrar`. A IA não escreve em cadastro, não abre OS, não altera nada.

---

## O que ela nunca faz

1. **Prometer prazo.** Nem "amanhã", nem "em breve", nem "logo".
2. **Dar desconto, isentar, negociar valor.**
3. **Confirmar pagamento.** Ela informa o que o sistema mostra; quem confirma baixa é o financeiro.
4. **Cancelar, suspender ou alterar contrato.**
5. **Expor o mecanismo.** Não fala de API, cache, Harmonit, WESO, "meu sistema", "não consegui consultar". O cliente não precisa saber como a salsicha é feita.
6. **Inventar.** Se não sabe, transfere.
7. **Responder em grupo.** (Grupos são Fase 3, e mesmo lá: nunca.)
8. **Repetir dado sensível sem necessidade** — não recita CPF/CNPJ inteiro na conversa.

🚨 O item 6 é o que custou caro no MoviChat em 02/07, 15/07 e 28/07: a IA **negava o que ela mesma já tinha no banco**. A regressão de 168 perguntas nasceu disso.

---

## Caminho de "não sei"

```
não tenho a informação  →  transfere, com o resumo do que já foi apurado
tenho, mas é ambígua    →  pergunta UMA vez, depois transfere
o cliente pediu humano  →  transfere na hora, sem insistir
```

**Nunca:** "não consegui acessar", "estou com problema técnico", "tente novamente". Isso é expor mecanismo — e é o item 5.

## Handoff

- Ao transferir, a IA escreve uma **nota interna** (não vai para o cliente) com: quem é, o que quer, o que já foi consultado, o que falta.
- Quando um humano assume, **a IA cala imediatamente** — sem despedida, sem "vou transferir você". O cliente não deve perceber a troca.
- O humano pode **devolver ao bot** depois de resolver.

## Agrupamento de entrada

O cliente manda três mensagens seguidas. A IA espera **~5 segundos de silêncio** e trata as três como **uma**. Responder cada uma isoladamente é a coisa que mais denuncia um robô.

## Saída

- Teto de tamanho por mensagem.
- Atraso proporcional ao texto, com "digitando…".
- **Nunca mais de 2 balões seguidos.**

---

## Versionamento

**O prompt não é editado por cima.** Cada alteração cria uma linha em `prompt_versao`, e cada conversa grava `prompt_versao_id`.

Sem isso, "por que a IA respondeu isso em julho?" não tem resposta — o prompt de julho não existe mais.

Publicar versão nova exige **passar no teste de aceite** abaixo.

---

## Teste de aceite

Reaproveita o insumo que já existe: **as 168 perguntas reais** da regressão do MoviChat, mais as **17 negativas** (perguntas que a IA deve recusar ou transferir, não responder).

| Critério | Meta |
|---|---|
| Respondem sem exceção | 168/168 |
| Negativas corretas | ≥ 16/17 |
| Nenhuma resposta expõe mecanismo | 100% |
| Nenhuma resposta promete prazo ou valor | 100% |
| Custo médio por mensagem | acompanhado, não travado |

🚨 **A asserção precisa detectar valor constante, não só `NULL`.** Um campo devolvendo `0` em 100% das linhas passa batido num teste de nulidade — foi assim que `bateria = 0` sobreviveu.

⚠️ Teste que roda só contra mock não conta. O aceite final é conversa real no chip de teste.

---


---

## 🚨 O interruptor — ela nasce desligada

**Decisão do usuário em 2026-08-06.** A IA tem um interruptor **por canal**, e
ele nasce em `false`. Ninguém liga por acidente; ligar é um ato.

```
Objetivo:     a IA só fala quando alguém decidiu que ela devia falar
Hoje:         = o objetivo. canal.ia_ligada, false por padrão (migração 007)
Por quê:      pedido do usuário -- a ordem é validar conexão, depois o bot, e
              só então ligar. Um sistema que já nasce respondendo ao cliente
              não tem ensaio: o primeiro erro dele é em público
Reavaliar se: -- fechado
```

### Por que por canal e não global

| | |
|---|---|
| **Global** | obriga alguém a lembrar de desligar antes de cada disparo do informativo. **"Lembrar" é exatamente o que falha.** |
| **Por canal** | o informativo não tem como ligar. Não é disciplina, é a coluna |

**Somente o canal `atendimento` tem IA.** O `informativo` não recebe mensagem
como conversa — o que chegar nele é gravado em `webhook_evento` e marcado como
processado, sem virar conversa e sem acionar a IA.

⚠️ E vai chegar mensagem nele: **gente responde boleto.** Fingir que não chega
faria a resposta do cliente sumir sem rastro. Guardar sem atender é o meio
termo honesto.

### A sequência de ativação

```
1. parear o chip                     CFG_1.1
2. confirmar que mensagem chega      conferir webhook_evento
3. validar o bot respondendo         em conversa de teste
4. LIGAR O INTERRUPTOR               ato deliberado, na CFG_1.1
```

O banco registra `ia_ligada_em` e `ia_ligada_por`. Não é burocracia: quando
alguém perguntar *"desde quando a IA está respondendo os clientes?"*, a
resposta não pode ser um encolher de ombros.

---

## Os dados que ela pode consultar

**Só leitura, e só o que está no banco do MoviZap.** A IA não fala com o
Harmonit nem com a WESO: fala com o cadastro que o sync já trouxe. Isso não é
economia de código — é o que impede uma pergunta em linguagem natural de virar
carga na API de terceiro, e o que garante que ela vê o mesmo dado que o
atendente vê na ficha.

| Tabela | O que ela enxerga | O que ela NUNCA enxerga |
|---|---|---|
| `cliente` | nome, fantasia, documento, situação | — |
| `contato` | nome, relação, e-mail | — |
| `contato_telefone` | E.164, `tem_whatsapp` | o `bruto`, que não acrescenta nada a ela |
| `contato_papel` | papéis | — |
| `conversa`, `mensagem` | **só a conversa em andamento** | conversa de outro contato |
| FPSL | veículos, contratos, faturas | qualquer escrita |

🚨 **Ela nunca enxerga `config`, `atendente`, `prompt_versao` nem
`webhook_evento`.** Não é só privacidade: uma IA que lê a própria configuração
é uma IA que pode ser convencida a descrevê-la para quem estiver do outro lado.

🚨 **Nunca escreve no cadastro.** Se a conversa revelar que o cadastro está
errado — telefone de outra empresa, nome trocado — ela **registra na conversa**
e não corrige nada. Correção de cadastro é ato de gente, com rastro.

### O caso do número compartilhado

44 números da base estavam em mais de um cliente (`08_Identidade.md`). Os
duvidosos ficaram **sem dono**, então `identificar_contato` vai devolver
**vazio** para eles — e isso é o comportamento certo.

Quando isso acontecer, a IA **pergunta**: *"você está falando em nome de qual
empresa?"*, e registra a resposta na conversa para um humano confirmar.

🚨 **É a única fonte que sabe a verdade — a pessoa do outro lado.** Nenhuma
regra automática resolve isso, e chutar produziria ficha errada na tela do
atendente, que é pior que ficha nenhuma.
## Chave e custo

- Chave lida do `.env` por **um único gateway**. Nenhum outro módulo sabe que ela existe.
- Montagem usa a chave atual; a chave própria do MoviZap entra depois — **é uma linha no `.env`, sem tocar em código**.
- Chave separada por projeto dá **custo discriminado** e permite revogar uma sem derrubar as outras.
- Em tela de configuração, mostra-se `sk-...a3f9`. Nunca o valor.
- 🚨 `httpx` / `httpcore` / `hpack` silenciados desde a primeira linha — é por ali que a chave da WESO vazou para um log.

---

# 🟢 O PASSO 8 ENTROU EM 2026-08-26 — o que foi construído, e o que não

Tudo acima continua sendo o contrato. Esta seção diz **o que dele existe em
código hoje**, e o que ficou de fora com o motivo. Ela é o estado; o resto do
documento é o desenho.

## Onde o motor mora

| Peça | Arquivo | O que faz |
|---|---|---|
| Adaptadores de modelo | `movizap/llm/provedores.py` | DeepSeek e Groq, pelo REST compatível com OpenAI |
| Parâmetros | `movizap/llm/params.py` | `temperature`, `max_tokens=900` — herdados do MoviChat, medidos lá |
| O laço de ferramentas | `movizap/llm/gateway.py` | genérico: recebe catálogo e executor por parâmetro |
| A IA do atendimento | `movizap/ia.py` | contexto, catálogo, conduta, envio, transferência |
| A trava de repetição | migração `035` (`conversa.ia_atendeu_ate`) | não responder duas vezes |

🚨 **O `movizap/llm/` é o ÚNICO lugar que lê a chave**, e há um teste que
mede isso — varrendo o `settings.deepseek_api_key` **fora de comentário e
docstring**, porque trava que mede palavra já reprovou código correto oito
vezes neste projeto.

## Herdado do MoviChat — e o que NÃO foi herdado

O contrato dizia *"não se reescreve o motor — herda-se"*, e as decisões foram
herdadas inteiras: o modelo (`deepseek-v4-flash`, porque `deepseek-chat` foi
desativado em 24/07), o `thinking` desligado, o teto de 45 s abaixo do da
borda, 1 retry, a estratégia `single`/`fallback`, o teto de rodadas, **a última
rodada sem `tools`** e **a conduta diante da falha vinda de nós**.

⚠️ **O que não foi herdado é o SDK `openai`.** O adaptador fala por `httpx`
síncrono. Motivo, e é um só: o caminho que chama a IA no MoviZap é síncrono de
ponta a ponta — `conversas.processar_pendentes` é `def`, e roda em
`asyncio.to_thread` justamente porque `async def` ali **não executa nada**.
Trazer o SDK arrastaria um mundo `async` e uma cadeia de dependência para
dentro de um laço que é `def`, por **um POST**.

⚠️ **`gateway.py`, `schema_map.py` e `query_catalog.py` do MoviChat NÃO foram
copiados.** São de frota: mapa da base do MoviChat, recorte por placa, frescor
de posição, catálogo de SQL de telemetria. Nada disso existe aqui. O que se
herdou foi o **desenho** do laço, não o conteúdo dele.

## As ferramentas — 5 de 8, e por quê

| Ferramenta do contrato | Estado |
|---|---|
| `identificar_contato` | ✅ **sem argumento**, olha só a conversa em curso |
| `dados_cliente` | ✅ **sem argumento**, a empresa desta conversa |
| `historico_conversas` | ✅ os 5 atendimentos anteriores do mesmo contato |
| `transferir(time, resumo, despedida)` | ✅ escreve nota interna e usa `conversas.transferir` com `motivo='ia_triagem'` |
| `encerrar(motivo, despedida)` | ✅ marca `resolvida_pela_ia` |
| `listar_veiculos` | ❌ **não existe fonte** |
| `posicao_veiculo` | ❌ **não existe fonte** |
| `consultar_faturas` | ❌ **não existe fonte** |

🚨 **AS TRÊS QUE FALTAM NÃO SÃO ESQUECIMENTO, SÃO CONTRADIÇÃO DO PRÓPRIO
DOCUMENTO.** A seção "Os dados que ela pode consultar" decide que *"a IA não
fala com o Harmonit nem com a WESO: fala com o cadastro que o sync já
trouxe"* — e o banco do MoviZap **não tem tabela de veículo, contrato nem
fatura** (medido em 26/08: 35 tabelas, nenhuma delas). As três só existem
levantando dado de outro sistema, que é justamente o que está proibido.

⚠️ **A saída não foi fingir que dá.** O prompt de sistema diz, em voz alta, que
ela **não consegue** consultar veículo, posição, contrato e fatura, e que nesses
casos **transfira** — sem dizer que não encontrou e sem falar de acesso. É a
correção da CLASSE de erro que reincidiu três vezes no MoviChat (02/07, 15/07,
28/07): *a IA não distingue "não achei" de "não consigo ler", e reporta ausência
como fato*.

🔵 **Decisão que fica com você:** se essas três ferramentas devem existir, elas
exigem uma ponte para o FPSL (que já tem `FPSL_BASE_URL` no `.env`) ou para o
espelho do Harmonit. Isso **é escopo novo**, não é dívida deste passo.

⚠️ **`identificar_contato` e `dados_cliente` perderam o parâmetro de propósito.**
O contrato os descrevia como `identificar_contato(telefone)` e
`dados_cliente(cliente_id)`. Parâmetro livre é um caminho para convencer a IA a
ler a ficha de outra pessoa, e a tabela deste mesmo documento já diz que ela
nunca enxerga "conversa de outro contato". **Um parâmetro que só aceita um
valor não é um parâmetro.**

## As três travas — e uma quarta que faltava

| # | Trava | Onde |
|---|---|---|
| 1 | `canal.ia_ligada` | por canal. O informativo não tem como ligar |
| 2 | `relacao_automacao.ia_ligada` | por tipo de contato — o filtro de desgaste de 25/08 |
| 3 | `conversa.ia_atendeu_ate` | por mensagem — não responder duas vezes |
| 4 | **`canal.ia_ligada_em`** | **por hora — não responder o passado** |

🚨 **A QUARTA NÃO ESTAVA NO CONTRATO E FOI ACHADA ESCREVENDO O TESTE.** A base
tinha **357 conversas abertas** quando o motor entrou. Sem ela, ligar o
interruptor faria a IA responder a todas de uma vez — mensagens de dias atrás,
no meio de conversas que já seguiram sem ela. É a mesma lição que a saudação
automática deu na auditoria de 25/08, cometida de novo em outro lugar.
A coluna já existia, para registrar *quem e quando*; agora ela **decide**.

## Como se prova que ele funciona

**A suíte não prova.** `tests/teste_ia.py` (38 verificações) troca o provedor
por um duplo e nunca sai da máquina — ela prova as travas, o laço e o que é
gravado. Quem prova que o modelo responde é:

| Ferramenta | O que faz | Custa |
|---|---|---|
| `scripts/exercitar_ia.py` | 4 casos contra o modelo real, sem tocar em conversa nenhuma | centavos |
| **Sala de ensaio** (CFG_2.1) | roda o motor contra uma **conversa de verdade** e mostra o que ela TERIA feito — sem enviar, sem gravar, sem transferir | centavos |

🚨 **A SALA DE ENSAIO É O PASSO 3 DA SEQUÊNCIA DE ATIVAÇÃO**, que até 25/08 não
tinha como ser cumprido. Sem ela, o primeiro erro da IA acontece em público —
que é exatamente o que a decisão de 06/08 existe para evitar.

### O que o primeiro ensaio contra conversa real achou (26/08)

Duas coisas, nenhuma delas visível em teste:

1. **Markdown.** O modelo devolveu `**Fulano**`, e no WhatsApp os asteriscos
   aparecem literalmente. Corrigido em `ia.para_whatsapp()` — **instrução em
   prompt é pedido, não regra**, então a conversão é código.
2. 🚨 **Anunciou uma transferência que não fez.** Escreveu *"vou te passar
   para o time de manutenção"* e **não chamou a ferramenta**: o cliente
   ficaria esperando alguém que nunca viria, sem ninguém saber. Corrigido
   endurecendo a `CONDUTA` — e reconferido contra a mesma conversa, que passou
   a chamar `transferir` com nota interna útil e despedida sem citar o time.

⚠️ **A `CONDUTA` fica em CÓDIGO, não no texto versionado da tela.** O prompt é
editável, e o que ela **nunca** pode fazer não pode depender de alguém lembrar
de reescrever "não prometa prazo" na versão seguinte.

## O que continua faltando, e é honesto dizer

| Item | Estado |
|---|---|
| **Teste de aceite** (168 perguntas + 17 negativas) | ❌ o insumo está no MoviChat e é de FROTA, não de atendimento. Reaproveitá-lo exigiria reescrever as perguntas |
| **"digitando…" e atraso proporcional** | ❌ não implementado. A resposta sai num balão só |
| **Nunca mais de 2 balões** | ✅ por construção: é sempre um |
| **Devolver a conversa ao bot** depois do humano | ❌ não há caminho. Hoje, transferiu, acabou |
| **Reação do cliente** (`reactionMessage`) | ❌ segue no ramo de "tipo ainda não tratado" |

⚠️ **Nada disso impede ligar.** São lacunas declaradas, não defeitos escondidos
— e a diferença é a razão desta tabela existir.
