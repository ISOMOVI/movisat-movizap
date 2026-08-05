# 02 — Modelo de dados

**Versão 2 — 2026-08-05.** A v1 (04/08) nunca chegou a virar banco. Esta
incorpora as decisões da conversa de 05/08: avaliação no encerramento, notas
internas, jornada do atendente, repasse por inatividade, histórico de
transferência, métricas de fechamento e permissão por time.

Banco `movizap`, no **Postgres 16 do host** (não no container — aquele é do
Evolution). Banco próprio, não schema dentro de outro: backup e restauração
independentes.

> **Este é o documento que fica caro de mudar depois.** É o que mais merece
> revisão antes de existir código.

🛑 **Aguardando aprovação.** Nada de DDL antes disso.

---

## Princípios

1. **Evento referencia, nunca copia.** A mensagem aponta para o contato; não
   guarda o nome dele. Foi copiar que quebrou o `HBG 8442` no Harmonit — uma
   instalação de 2024 fotografou um cadastro vazio e nunca mais foi corrigível.
2. **Estado derivado, não escrito à mão.** "Conversa aberta" é consulta, não
   flag mantida por gatilho.
3. **Duas origens no mesmo lugar, com fronteira dura.** `origem` diz quem
   manda em cada linha.
4. **Telefone é identidade no WhatsApp**, e por isso é tabela, não coluna.
5. **Nada se apaga.** Inativa-se.
6. **🆕 O que a operação vai perguntar depois, grava-se agora.** Tempo de
   atendimento, quem transferiu, por que a conversa parou: derivar isso de
   `mensagem` funciona uma vez e fica caro toda vez. Colunas preenchidas no
   fechamento custam bytes e economizam a pergunta.

---

## Cadastro

### `cliente`
| Campo | Tipo | Nota |
|---|---|---|
| `id` | bigserial PK | |
| `nome` | text | razão social ou nome |
| `nome_fantasia` | text NULL | 🆕 vem do Harmonit |
| `documento` | text | CNPJ/CPF, só dígitos. **Aceita alfanumérico** (o novo CNPJ já existe na base) |
| `tipo_pessoa` | smallint NULL | 🆕 do Harmonit |
| `email` | text NULL | 🆕 78,8% preenchido no Harmonit |
| `origem` | enum(`harmonit`,`movizap`) | fronteira do sync |
| `harmonit_id` | text NULL | UNIQUE quando não nulo |
| `ativo` | bool | |
| `criado_em` / `atualizado_em` | timestamptz | |

### `contato`
| Campo | Tipo | Nota |
|---|---|---|
| `id` | bigserial PK | |
| `cliente_id` | FK NULL | lead e fornecedor podem não ter cliente |
| `nome` | text | |
| `relacao` | enum(`cliente`,`fornecedor`,`parceiro`,`tecnico`,`lead`) | **o que a pessoa é para a Movisat**. 🆕 `parceiro` entrou |
| `email` | text NULL | 🆕 |
| `origem` / `harmonit_id` / `ativo` | | igual acima |
| `criado_em` / `atualizado_em` | timestamptz | |

🆕 **A cor da etiqueta não é coluna.** É constante no código, mapeada de
`relacao`: cliente 🔵 · fornecedor 🔴 · parceiro 🟡 · técnico 🟣 · lead ⚪.
Vira tabela **só** se você quiser trocar cor pela tela — o que não é Fase 1.

### `contato_papel`
Papel **dentro do cliente** — eixo diferente de `relacao`.

| Campo | Nota |
|---|---|
| `contato_id` | FK |
| `papel` | enum(`assinar`,`central_24h`,`financeiro`) |

⚠️ **`relacao` e `papel` não são a mesma coisa.** Um técnico não é "papel de
contato de cliente". Colapsar os dois num campo só custa faxina depois.
⚠️ Na Fase 1 o papel **é gravado e não aciona nada**.

### `contato_telefone`
| Campo | Tipo | Nota |
|---|---|---|
| `id` | bigserial PK | |
| `contato_id` | FK | |
| `e164` | text | **normalizado — é por aqui que se busca.** INDEX |
| `bruto` | text | como veio. Nunca se perde |
| `origem_campo` | text NULL | 🆕 `telefone`, `telefone2`, `celular` — de qual campo do Harmonit veio |
| `tem_whatsapp` | bool NULL | `NULL` = não verificado ≠ `false` = verificado e não tem |
| `verificado_em` | timestamptz NULL | |
| `principal` | bool | |

🚨 A busca **nunca** usa `bruto`. O nono dígito faz `+551899811xxxx` e
`+55189811xxxx` serem a mesma pessoa — o normalizador resolve nos dois sentidos.

🚨 **Nunca deduzir `tem_whatsapp` do formato do número.** Fixo de 10 dígitos e
0800 **têm** WhatsApp (verificação por chamada de voz), e a Movisat tem
clientes assim. O único que sabe é o Evolution, e a resposta dele vira
`tem_whatsapp` + `verificado_em`.

**Medido em 05/08, amostra de 400 clientes do Harmonit:** 84,2% têm algum
telefone — `telefone` 79,5%, `celular` 25,8%, `telefone2` 16,8%. 464 números
distintos em 488 preenchidos, ou seja, são telefones reais e não um número
padrão da empresa.

⚠️ **O `import_harmonit_clientes.py` de hoje descarta os três campos.** O sync
do MoviZap tem que ler `contatoPrincipal.telefone`, `.telefone2` e `.celular`
— cada um com `ddd`/`ddi`/`phone` — e gerar uma linha por número.

---

## Canal e conversa

### `canal`
| Campo | Nota |
|---|---|
| `id` | |
| `tipo` | enum(`atendimento`,`informativo`) |
| `gateway` | 🆕 enum(`evolution`,`email`) — a aba de e-mail da Fase 2 cabe sem migração |
| `instancia` | nome da instância no Evolution |
| `modo` | enum(`baileys`,`cloud_api`) — a porta para a API oficial já fica aberta |
| `ativo` | |

### 🆕 `canal_evento`
Histórico de conexão. `id · canal_id · estado · motivo NULL · em`

🚨 **É o que responde "desde quando parou de chegar mensagem?"** Sem histórico
essa pergunta não se responde, só se chuta. Alimenta a `CFG_1.1`: pareado em,
conectado há, reconexões nas últimas 24h.

### `conversa`
| Campo | Nota |
|---|---|
| `id` | |
| `canal_id` | FK |
| `contato_id` | FK **NULL** — desconhecido até identificar |
| `telefone_e164` | text — a identidade antes de haver contato |
| `estado` | enum(`nova`,`bot`,`fila`,`humano`,`resolvida`,`adiada`) |
| `time_id` | FK NULL |
| `atendente_id` | FK NULL — quem é o dono agora |
| `prompt_versao_id` | FK NULL — **qual versão da IA atendeu esta conversa** |
| `classificacao_id` | FK NULL — preenchida no fechamento |
| ⚠️ `classificacao_texto` | **acrescentado na implementação.** A v2 exige comentário quando a classificação é `Outro`, mas não disse onde ele fica. É aqui |
| `adiada_ate` | timestamptz NULL |
| `criada_em` / `atualizada_em` | timestamptz |
| 🆕 `ultima_atividade_em` | timestamptz — **base do repasse por inatividade** |
| 🆕 `primeira_resposta_em` | timestamptz NULL — humano ou IA respondeu |
| 🆕 `resolvida_em` | timestamptz NULL |
| 🆕 `segundos_ate_resposta` | int NULL — congelado no fechamento |
| 🆕 `segundos_total` | int NULL — idem |
| 🆕 `qtd_transferencias` | int default 0 |
| 🆕 `resolvida_pela_ia` | bool default false — fechou sem humano nenhum |
| 🆕 `avaliacao` | smallint NULL — **1 a 5** |
| 🆕 `avaliacao_pedida_em` | timestamptz NULL |
| 🆕 `avaliacao_comentario` | text NULL |

**Constraint que evita conversa duplicada:**
```
UNIQUE (canal_id, telefone_e164) WHERE estado <> 'resolvida'
```
Uma conversa aberta por telefone, por canal. É isso que faz o cliente que
volta **reabrir** em vez de criar outra.

### 🆕 A máquina de estados, como ficou

```
nova ──> bot ──> fila ──> humano ──> resolvida
                  ↑          │
                  └──────────┘  repasse (manual ou por inatividade)
                             │
                          adiada ──> volta para fila no prazo
```

🚨 **Não existe "devolver à fila" como ação do atendente.** Decisão de 05/08.
Uma vez que a conversa tem dono, ela sai dele por **repasse** (para outra
pessoa ou time), por **repasse automático por inatividade**, ou por
**encerramento**. Isso é diferente de v1 e muda a tela: some o botão
"Devolver ao bot".

⚠️ **Fila é o que NÃO tem dono.** Conversa em `bot` não está na fila — a IA
está atendendo. Confundir os dois esconde o número que a operação precisa:
quanto está realmente parado esperando gente.

### 🆕 `transferencia`
`id · conversa_id · de_atendente_id NULL · para_atendente_id NULL ·
para_time_id NULL · motivo enum(manual, inatividade, ia_triagem, sem_time) ·
resumo text NULL · em timestamptz`

🚨 **`mensagem.tipo='sistema'` mostra a transferência na linha do tempo, mas
não responde "quantas vezes o Financeiro empurrou para o Suporte no mês".**
Texto em balão não é dado consultável.

O `resumo` é o que a IA apurou, para o humano não pedir tudo de novo.

### `mensagem`
| Campo | Nota |
|---|---|
| `id` | |
| `conversa_id` | FK |
| `id_externo` | text **UNIQUE** — 🚨 é a idempotência do webhook. Sem isso, reentrega duplica |
| `direcao` | enum(`entrada`,`saida`,🆕`interna`) |
| `autor` | enum(`cliente`,`ia`,`atendente`,`sistema`) |
| `tipo` | enum(`texto`,`imagem`,`audio`,`video`,`documento`,`figurinha`,`localizacao`,`contato`,`sistema`,🆕`nota`) |
| `conteudo` | text |
| `midia_id` | FK NULL |
| `citada_id` | FK NULL — resposta citando outra mensagem |
| `atendente_id` | FK NULL |
| `entrega` | enum(`pendente`,`enviada`,`entregue`,`lida`,`falhou`) |
| `criada_em` | timestamptz — **do provedor**, é por ela que a tela ordena |
| `recebida_em` | timestamptz — nossa. Webhook chega fora de ordem |

**`tipo = 'sistema'`** é o que põe "Karla assumiu" e "transferido para
Financeiro" na mesma linha do tempo dos balões. Sem isso o histórico fica
ilegível — é o `activity` do Chatwoot, e vale a cópia.

🆕 **`tipo = 'nota'` + `direcao = 'interna'` é a nota interna.** Aparece na
conversa para o atendente, **nunca sai para o cliente**.

🚨 **A trava é de código, não de disciplina:** o envio filtra
`direcao = 'saida'`. Nota interna não tem como escapar porque nunca entra na
consulta que envia. Sem isso, um dia alguém manda "cliente chato" para o
cliente.

### `midia`
`id · conversa_id · mime · tamanho · caminho · nome_original · hash · baixada_em`

Arquivo em disco, não no banco. `hash` evita guardar duas vezes o mesmo áudio.

---

## Operação

### `atendente`
| Campo | Nota |
|---|---|
| `id` | |
| `login` | 🆕 UNIQUE, **comparado ignorando maiúscula** |
| `nome` | 🆕 nome de exibição — é o que o cliente vê |
| `email` | |
| `senha_hash` NULL / `google_sub` NULL | login local na Fase 1; as colunas do Google já nascem para a Fase 2 não exigir migração |
| `ativo` | |
| ⚠️ `owner` | **acrescentado na implementação, não estava na v2 aprovada.** O `auth.py` já trata owner como conceito (enxerga todas as telas, independente do que estiver gravado). Sem a coluna, esse conceito viveria só no `.env` e não sobreviveria ao `CAD_2.1` |
| `convite_token` / `convite_expira_em` | NULL |
| 🆕 `estado` | enum(`disponivel`,`ausente`,`nao_perturbe`) |
| 🆕 `fuso` | text default `America/Sao_Paulo` |
| 🆕 `max_conversas` | int NULL — teto de simultâneas; NULL = sem teto |

### 🆕 `atendente_jornada`
`id · atendente_id · dia_semana (0-6) · inicio time · fim time`

Uma linha por faixa — cobre almoço e escala partida sem gambiarra.

🚨 **Serve para evitar transferência fantasma**, não para bloquear.
Transferir para quem está fora da jornada **avisa e sugere o time**; nunca
recusa. Bloquear faz o atendente encerrar a conversa para se livrar dela, e
aí o cliente some do radar de vez.

### 🆕 Repasse por inatividade
Não é tabela: é `conversa.ultima_atividade_em` + um prazo em `config`.

```
humano + ultima_atividade_em > prazo  ->  volta para fila
                                          grava transferencia(motivo=inatividade)
```

⚠️ Prazo configurável, não constante no código. Ninguém acerta esse número de
primeira.

### `time` · `atendente_time`
n:n. O time rege a transferência.

`time`: `id · nome · descricao · ativo · time_transbordo_id NULL`

🚨 **A `descricao` é entrada da IA, não enfeite.** É por ela que a IA escolhe
o destino. Time sem descrição = IA chutando.

Os 7 do Chatwoot: Contratual · Comercial · Financeiro · Suporte · Geral ·
Pós Venda · agendamento. ⚠️ Numeração nova — os ids 3 e 8 lá são buracos de
times apagados.

### 🆕 `atendente_time_permissao` — quem vê o quê na fila
A fila mostra **todas** as conversas sem dono, **exceto** para quem tem
visão restrita a certos times.

```
sem linha em atendente_time_permissao  ->  vê a fila inteira
com linha(s)                           ->  vê só os times listados
```

🚨 **Isto é permissão de DADO, não de tela.** O `telas.py` responde "pode
abrir a `ATD_1.3`?"; isto responde "quais conversas aparecem lá dentro". São
perguntas diferentes e não podem viver no mesmo lugar.

⚠️ Continua valendo: a barreira é o backend. A consulta já sai filtrada — o
frontend não recebe e esconde.

### `classificacao`
`id · nome · ativo` — motivo de fechamento. Obrigatória ao resolver.

🆕 Se `nome = 'Outro'`, **comentário obrigatório**. Sem isso `Outro` vira o
vale-tudo onde metade das conversas acaba, e o analytics morre.

### 🆕 O encerramento, na ordem
```
1. atendente escolhe a classificação        (obrigatória)
2. sistema congela as métricas na conversa
3. envia agradecimento + pede nota de 1 a 5
4. cliente responde -> grava avaliacao
5. agradece e informa que é só chamar
```

⚠️ **A avaliação não pode travar o encerramento.** A conversa fecha no passo
2; os passos 3-5 acontecem depois. Cliente que não responde deixa
`avaliacao = NULL`, e isso é normal — não é pendência.

### `prompt_versao`
`id · versao · conteudo · autor_id · criado_em · ativo`

**Prompt não é editado por cima.** Cada alteração é uma versão nova, e a
conversa grava qual atendeu. É o que permite responder "por que a IA disse
isso" três semanas depois.

### `sync_execucao`
`id · iniciado_em · terminado_em · origem(cron|manual) · atendente_id NULL ·
lidos · criados · atualizados · inativados · vazios · erros · mensagem_erro`

🆕 `vazios` é coluna própria. 🚨 **`ok` / `vazio` / `erro` são três estados.**
Não separar foi o que fez um painel acusar **76% de falha num sistema
saudável** — a numeração do Harmonit tem buracos, e resposta vazia não é erro.

### 🆕 `config`
`chave · valor · atualizado_em` — prazo de inatividade, horário geral de
atendimento, tempo de adiamento padrão.

---

## 🚨 A regra dura do sync

```
O sync SÓ toca linhas com origem = 'harmonit'.
Linha com origem = 'movizap' é intocável — nem update, nem delete, nunca.
```

- Upsert por `harmonit_id`. **Jamais "apaga tudo e reinsere"** — seria perder
  na primeira madrugada todo contato cadastrado à mão.
- Sumiu do Harmonit → `ativo = false`. Não se apaga cadastro.
- O Harmonit responde **`list` quando acha** e **`dict` quando não acha**, e o
  `dict` é *truthy*. O sync checa o **tipo**, não a veracidade.
- 🆕 O envelope de `/ObterClientes` é `{sumario, lista}` — **não** `data`.
  Medido em 05/08.

### 🆕 Este sync passa a ser O cache do Harmonit

Hoje o cadastro do Harmonit existe em dois lugares com idades diferentes:
`fpsl.db/harmonit_clientes` (943 linhas, **parado em 16/07**) e nada mais. O
`weso_cache` é outra coisa — equipamento, não cadastro, e só o FPSL consome.

O sync de 12h do MoviZap vira a **única** cópia do cadastro do Harmonit, e o
FPSL passa a ler dela. Sem isso viram três bases com três idades.

---

## Índices que não são opcionais

| Índice | Por quê |
|---|---|
| `mensagem.id_externo` UNIQUE | idempotência do webhook |
| `contato_telefone.e164` | é o lookup de toda mensagem que chega |
| `conversa (canal_id, telefone_e164)` parcial | uma conversa aberta por telefone |
| `conversa (estado, time_id)` | a fila é a tela mais aberta do dia |
| `mensagem (conversa_id, criada_em)` | rolagem do histórico |
| 🆕 `conversa (estado, ultima_atividade_em)` | varredura do repasse por inatividade |
| 🆕 `conversa (resolvida_em)` | relatório e a tela de Histórico |
| 🆕 `cliente.harmonit_id` / `contato.harmonit_id` UNIQUE parcial | upsert do sync |

### 🚨 Postgres NÃO indexa chave estrangeira sozinho

Só PK e UNIQUE ganham índice automático. É engano comum supor que FK também
ganha. A auditoria de 05/08 achou **16 FKs sem índice** logo depois da
migração 001.

A **002** indexou cinco — as que têm padrão de leitura real:

| Índice | A consulta que ele serve |
|---|---|
| `conversa.atendente_id` | "minhas conversas", o dia inteiro |
| `midia.conversa_id` | abrir conversa carrega as mídias |
| `atendente_time.time_id` | quem é do time X |
| `atendente_time_permissao.time_id` | filtro da fila |
| `transferencia.para_time_id` | relatório por time |

⚠️ **As outras 11 ficaram de fora de propósito.** Índice pesa em todo INSERT,
e `mensagem` é a tabela que mais cresce — três índices a mais ali seriam
pagos em toda entrega de webhook, para junções que quase não acontecem.

O outro motivo clássico para indexar FK — DELETE no pai varrendo a filha
inteira — **não se aplica**: o princípio do modelo é *nada se apaga,
inativa-se*.

---

## O que este modelo deliberadamente não tem ainda

`contrato` · `veiculo` · `os` · `fatura` — **na Fase 1 esses dados são
consultados no FPSL, não copiados para cá.**

Quando o ERP existir, eles nascem aqui como entidades próprias e a ficha deixa
de ser consulta externa. O modelo acima já está desenhado para isso: `cliente`
e `contato` são as mesmas tabelas que o ERP vai usar.

🆕 **Também não tem:** respostas prontas, busca no histórico, férias e
afastamento, plantão 24h, escala de quem cobre quem. Jornada resolve o dia
comum; ausência planejada é outro assunto e fica para a Fase 2.

---

## Decisões desta versão

### Métricas congeladas na conversa, não derivadas (05/08)
```
Objetivo:     responder "quanto tempo levou" sem varrer mensagem
Hoje:         = o objetivo. Colunas preenchidas no fechamento
Por quê:      derivar de `mensagem` funciona uma vez e fica caro toda vez --
              e a tela de Histórico é relatório, não consulta pontual
Reavaliar se: precisar de métrica que não foi congelada. Aí ou entra coluna
              nova, ou aceita-se varrer para aquele caso
```

### Nota interna é `mensagem`, não tabela separada (05/08)
```
Objetivo:     recado entre atendentes na mesma linha do tempo
Hoje:         = o objetivo. tipo='nota', direcao='interna'
Por quê:      tabela separada exigiria intercalar duas fontes por data toda
              vez que a conversa abre; e a trava contra vazar é a MESMA
              consulta de envio filtrar direcao='saida'
Reavaliar se: nota precisar de campo que mensagem não tem
```

### Permissão por time separada da permissão por tela (05/08)
```
Objetivo:     perfil que só enxerga os times dele na fila
Hoje:         = o objetivo. atendente_time_permissao; sem linha = vê tudo
Por quê:      telas.py responde "pode abrir a tela?"; isto responde "quais
              conversas aparecem lá dentro" -- misturar faria o registro de
              telas carregar regra de dado
Reavaliar se: — fechado. O padrão permissivo é proposital: time novo não
              deixa ninguém cego sem querer
```

### Repasse por inatividade com prazo em `config` (05/08)
```
Objetivo:     conversa não dormir com dono ausente
Hoje:         = o objetivo, prazo configurável
Por quê:      ninguém acerta esse número de primeira, e constante no código
              vira deploy toda vez que a operação quiser ajustar
Reavaliar se: — fechado
```

### O sync do MoviZap vira o único cache do Harmonit (05/08)
```
Objetivo:     um cadastro do Harmonit, com uma idade só
Hoje:         contorno -- existe em fpsl.db/harmonit_clientes, parado em 16/07
Por quê:      duas cópias com idades diferentes é pior que nenhuma: ninguém
              sabe qual está certa e as duas são consultadas
Reavaliar se: cai quando o FPSL passar a ler do banco movizap
```
