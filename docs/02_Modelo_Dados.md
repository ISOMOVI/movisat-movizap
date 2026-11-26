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
| `relacao` | enum(`cliente`,`fornecedor`,`parceiro`,`tecnico`,`lead`,`colaborador`,`teste`,`sem_identificacao`) | **o que a pessoa é para a Movisat**. `colaborador` e `teste` entraram na migração 023; `sem_identificacao` na 029, por decisão do usuário em 25/08 |
| `email` | text NULL | 🆕 |
| `origem` / `harmonit_id` / `ativo` | | igual acima |
| `criado_em` / `atualizado_em` | timestamptz | |

🆕 **A cor da etiqueta não é coluna.** Se existir, é constante no código,
mapeada de `relacao`. Vira tabela **só** se alguém quiser trocar cor pela tela
— o que não é Fase 1.

🚨 **NÃO HÁ PALETA DECIDIDA, E ESTE PARÁGRAFO JÁ AFIRMOU QUE HAVIA.** Até 25/08
ele listava cliente 🔵 · fornecedor 🔴 · parceiro 🟡 · técnico 🟣 · lead ⚪ como
se fosse decisão. Corrigido depois de o usuário perguntar de onde tinha saído a
cor de `sem_identificacao`: a **ideia** das cores é dele (o `docs/06` diz "a sua
ideia das cores"), a **paleta** é sugestão minha, a coluna do `06` se chama
"Cor sugerida", e **nada disso foi construído** — os chips têm só acento, ok,
aviso e erro, e roxo e cinza nem existem como token.

⚠️ E há **três eixos de cor** escritos em documentos diferentes, que se
contradizem no símbolo: relação (aqui e no `06`), prova de identidade (`docs/11`:
verde vinculado, azul confirmado por você, amarelo aparece no Bitrix, branco
desconhecido) e tipo de conversa (a margem da lista). Azul quer dizer "é
cliente" num e "você confirmou" no outro; amarelo e branco também colidem.
**Cor nova só entra numa proposta que resolva os três de uma vez.**

⚠️ **O valor gravado hoje não mede a realidade.** Medido em 25/08: 1.750 dos
1.754 contatos estão como `cliente`, porque `sync._gravar_contato` grava essa
palavra **literal** para todo mundo que vem do Harmonit. O número mede uma
constante no código. Quem classifica é gente, na CAD_1.2 — e é por isso que a
marcação em lote vem antes de qualquer automação por tipo.

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
| `atendente_id` | FK NULL — quem é o dono agora. 🚨 **Volta a NULL ao concluir** (25/08): conversa concluída não tem dono |
| ⚠️ `resolvida_por` | FK NULL — **quem concluiu o atendimento** (migração 029). Gravada ANTES de soltar `atendente_id`, na mesma instrução. NULL nas conversas fechadas antes de 25/08: a informação nunca foi gravada, e preencher com o dono de então seria chute |
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
`id · conversa_id · sala_id · mime · tamanho · caminho · nome_original · hash · baixada_em`

Arquivo em disco, não no banco. `hash` evita guardar duas vezes o mesmo áudio.

🆕 **DOIS DONOS POSSÍVEIS, UM DE CADA VEZ** (migração 047, 22/09). `conversa_id`
é a conversa com o cliente; `sala_id` é a sala do chat interno, que passou a
aceitar anexo. `CHECK ((conversa_id IS NULL) <> (sala_id IS NULL))` garante que
toda linha pertence a exatamente um — nunca aos dois, nunca a nenhum.

🚨 **A COLUNA DO DONO É A REGRA DE PERMISSÃO.** `/api/midia/{id}` decide quem
pode ver lendo daí: mídia de conversa segue a tela `ATD_1.2`, como sempre;
mídia de sala exige **ser membro da sala**. Antes da 047 a rota exigia só a
tela e não conferia participação — numa caixa compartilhada isso passa, num
chat de duas pessoas não, porque o `midia_id` é sequencial e trocar o número no
link entregaria o anexo alheio. Linha órfã viraria "mídia de ninguém", e "não
sei de quem é" acaba virando "deixa ver": por isso o `CHECK`.

⚠️ **O DEDUPE É POR DONO, NÃO GLOBAL.** O mesmo print mandado na conversa do
cliente e no chat interno são **duas linhas** apontando para **um arquivo** no
disco — o nome do arquivo é o SHA256. Unificar as linhas daria a quem vê uma
delas o direito de ver a outra.

⚠️ **A PASTA `/home/claude/movizap_midia` TEM BACKUP DESDE 22/09** e não tinha
antes: o `backup_projetos.sh` empacota diretórios nominais e ela fica fora do
projeto, e o `pg_dump` guarda o caminho, não o arquivo. Pior, o
`expurgar_base64.py` moveu as mídias do banco para o disco — antes dele o
conteúdo viajava no dump. Agora `scripts/backup_midia.sh` faz instantâneo
datado com hardlink às 02:50, retenção 14 dias.

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
| 🆕 `estado` | enum(`disponivel`,`ausente`,`offline`) — o `offline` entrou na **044**; o `nao_perturbe` **saiu na 068** (19/10), por decisão dele: não barrava receber conversa, só a tela dizia que barrava. 🚨 O `CHECK` mora no `pg_constraint`, não no `information_schema.columns` |
| 🆕 `fuso` | text default `America/Sao_Paulo` |
| ~~`max_conversas`~~ | **saiu na 056 (25/09)**: *"não deve haver máximo de conversas"*. Estava vazia em 11 de 11 e nada a lia |

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


---

## 🆕 Migrações 006 e 007 (2026-08-06)

### `cliente` — três colunas novas

| Coluna | Para quê |
|---|---|
| `cadastrado_em` | `dataCadastro` do Harmonit. **NULL em 29% da base** |
| `revisar` | cadastro que precisa de olho humano. Não esconde nem apaga |
| `motivo_revisao` | por quê. Hoje: nome marcado `[NÃO USAR]` / `(INATIVADO)` |

🚨 **Por que `cadastrado_em` existe, se já há `harmonit_id`.** Ordenar por data
dá resultado **diferente** de ordenar por id em **665 de 747** clientes. O id
*parece* ordem de cadastro e não é — e a regra do número compartilhado depende
de saber quem é o mais antigo.

🚨 **E por que ele é NULL-ável.** O Harmonit manda o campo vazio em 291
clientes e manda `0001-01-01T00:00:00` — **o vazio do .NET** — em outros 12.
Esse sentinela **parseia sem erro e vira o ano 1**: gravado como data, o
registro *sem* data ganharia toda disputa de antiguidade, e a regra ficaria
exatamente invertida sem nada acusar. O sync converte para NULL, e NULL aqui
significa *"o Harmonit não sabe"* — quem não sabe perde o desempate.

Depois de gravar: **747 com data, 303 sem, e a mais antiga é 12/08/1967**.

### `canal` — o interruptor da IA

| Coluna | Para quê |
|---|---|
| `ia_ligada` | **nasce `false`**. Por canal, nunca global |
| `ia_ligada_em` · `ia_ligada_por` | desde quando, e por quem |

Por canal e não global porque global obrigaria alguém a lembrar de desligar
antes de cada disparo do informativo — e "lembrar" é o que falha. Ver
`04_Contrato_IA.md`.

O canal `informativo` entrou aqui (a migração 003 o deixou de fora de
propósito). 🚨 **Disparo em massa continua fora da Fase 1**: conectar e receber
não é disparar, e este canal existir não cria rota de envio em lote.

### 🆕 `webhook_evento` — o corpo cru, antes de interpretar

| Coluna | |
|---|---|
| `payload` | **jsonb com o corpo inteiro**, como chegou |
| `instancia` · `evento` · `id_externo` · `de_mim` · `telefone` | extraídos, para consultar |
| `processado` · `processado_em` · `erro` | o que já foi tratado, e por que algo foi ignorado |

🚨 **Por que guardar o corpo inteiro.** Todo parser deste projeto foi escrito
contra a **documentação** do Evolution 2.3.7, não contra o que ele manda.
Guardar antes de interpretar permite conferir o formato real com **uma**
mensagem — em vez de descobrir a divergência com catorze telas construídas em
cima da suposição. É a mitigação escrita do risco de parear o chip por último.

🚨 **`ux_webhook_externo (instancia, id_externo)` é a trava da reentrega.** O
Evolution reenvia e não garante ordem: a idempotência é **do banco, não da
disciplina**. Reentrega é conflito esperado — ignora e responde 200. **Nunca
deduplicar por conteúdo ou timestamp**: o cliente manda "ok" duas vezes de
propósito, e isso é legítimo.

O índice é **parcial** porque nem todo evento tem id — os de conexão não têm, e
não se deduplica por um NULL.

⚠️ Mensagem em canal **informativo** e mensagem de **grupo** são gravadas e
marcadas como processadas, com o motivo em `erro`. Não viram conversa e não
acionam IA. Grupo é Fase 3; informativo não atende. Mas as duas **chegam**, e
descartar sem registro faria a resposta de um cliente sumir sem rastro.

### `contato_telefone` — o que a regra de identidade mudou

O sync deixou de gravar telefone durante a leitura. Decidir de quem é um número
compartilhado exige ver **todos** os clientes antes — gravar durante a varredura
faria a decisão depender da ordem das páginas.

🚨 **E o sync passou a REMOVER.** Ele só inseria, então os vínculos duvidosos
gravados antes da regra de 06/08 continuavam no banco: a regra nova valia só
para o que entrava. `_limpar_em_revisao` fecha isso — **1.248 → 1.152**
telefones, exatamente os 96 que a lista de revisão previu.

🚨 **Mas nunca apaga telefone com `tem_whatsapp` verificado.** O vínculo se
reconstrói relendo o Harmonit; a verificação, não — ela é do Evolution e custa
uma chamada. Se houver algum, ele fica e vai para o log.
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

---

## O CHECK do banco é contrato — e eu quebrei dois num dia (2026-08-07)

### `transferencia.motivo` é vocabulário fechado, não texto livre

```sql
CHECK (motivo IN ('manual', 'inatividade', 'ia_triagem', 'sem_time'))
```

Gravar a frase que o atendente escreveu ali levanta `CheckViolation`. O texto
livre vai no **`transferencia.resumo`** — que é onde o
`06_Conteudo_das_Telas.md` manda o resumo da transferência ficar, de qualquer
forma.

O `motivo` existe para o analytics conseguir separar *o que* transferiu: a IA
na triagem, um humano, inatividade, ou time sem gente. Frase livre não agrupa.

### 🚨 `information_schema.table_constraints` NÃO enxerga índice único

Consultei as constraints da tabela `atendente`, não vi unicidade em `login`, e
**quase criei um índice que já existia**. O `ux_atendente_login` estava lá o
tempo todo — como **índice**, não como constraint, e por isso invisível
naquela consulta.

Para ver os dois mundos:

```sql
-- constraints (PK, FK, UNIQUE declarada, CHECK)
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
 WHERE conrelid = 'atendente'::regclass;

-- índices (inclusive UNIQUE criado por CREATE INDEX, e os parciais)
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'atendente';
```

⚠️ Vale para os índices **parciais** também, que este projeto usa bastante:
`ux_conversa_aberta`, `ux_prompt_ativo`, `ux_atendente_origem`.

### Os índices parciais que carregam regra de negócio

Não são otimização — são a regra, aplicada pelo banco:

| Índice | O que impede |
|---|---|
| `ux_conversa_aberta (canal_id, telefone_e164) WHERE estado <> 'resolvida'` | duas conversas abertas para a mesma pessoa. Sem ele, a fala dela apareceria partida em duas telas |
| `ux_mensagem_id_externo (id_externo) WHERE NOT NULL` | mensagem duplicada na reentrega do webhook — **e o eco da própria mensagem enviada** |
| `ux_prompt_ativo (ativo) WHERE ativo` | duas versões de prompt ativas ao mesmo tempo |
| `ux_atendente_login (lower(login))` | dois logins que diferem só por maiúscula |
| `ux_atendente_origem (origem) WHERE NOT NULL` | reimportar o Chatwoot duplicar os atendentes |

🚨 **`ux_conversa_aberta` é parcial de propósito:** depois de encerrada, a
mesma pessoa voltar a falar abre conversa **nova**. Se fosse único absoluto, o
histórico juntaria dois assuntos diferentes na mesma conversa.

🚨 **`ux_mensagem_id_externo` é o que evita a mensagem em dobro no envio.** O
Evolution devolve pelo webhook a nossa própria mensagem, com `fromMe: true` e
o mesmo `key.id`. `conversas.responder` grava esse id no envio; quando o eco
chega, o índice transforma em conflito ignorado. Sem isso, tudo que o
atendente mandasse apareceria duas vezes na tela dele.

### `mensagem`: o CHECK que impede nota interna de vazar

```sql
CHECK ((tipo = 'nota') = (direcao = 'interna'))
```

Amarra os dois campos: não existe nota que não seja interna, nem mensagem
interna que não seja nota. É o banco impedindo que uma anotação do atendente
saia para o cliente por erro de código.


---

## `conversa_participante` — quem acompanha (2026-08-11, migrações 021/022)

Decisão do usuário em 11/08: dá para **convidar** outro atendente para uma
conversa; o convidado responde à vontade; sair é do próprio ou o dono remove;
e **quando o dono sai, a posse passa para quem ficou**.

### 🚨 Convidar não dá acesso — o acesso já existia

A auditoria de 11/08 mediu: **não há isolamento por conversa**. As 13 rotas de
atendimento exigem a tela `ATD_1.2` e **nenhuma pergunta quem é o dono**.
Qualquer atendente já abria, lia, respondia e vinculava qualquer conversa.

Então esta tabela responde outra pergunta: **quem está acompanhando**. Ela faz a
conversa **aparecer na lista** de quem foi chamado, e a tela mostrar quem mais
está ali. Chamar isso de "permissão" seria mentir sobre o que o sistema faz.

⚠️ Se o isolamento por conversa passar a existir um dia, esta tabela vira a
lista de quem tem acesso além do dono — e aí **muda de significado**. Está dito
para ninguém supor que já é isso.

### A estrutura

```sql
conversa_participante (
    conversa_id, atendente_id,          -- PK composta
    convidado_por,                      -- NULL = entrou por conta própria
    entrou_em, saiu_em,
    CHECK (saiu_em IS NULL OR saiu_em >= entrou_em)
)
```

**`saiu_em` em vez de apagar a linha:** quem entrou leu o que estava escrito na
conversa. Apagar faria o sistema esquecer que aquela pessoa viu — e *"quem teve
acesso a esta conversa"* é a pergunta que se faz **depois**, não antes.

⚠️ **A PK composta tem uma consequência assumida:** reconvidar quem saiu
**reabre a mesma linha**, em vez de criar outra. Perde-se o histórico de idas e
vindas. É a troca escolhida — para auditoria importa se a pessoa esteve, não
quantas vezes, e uma PK serial deixaria a porta aberta para duas participações
ativas da mesma pessoa, que é o defeito pior.

### 🚨 `entrou_em` é a fila de herança — e um `ON CONFLICT` quase a quebrou

Quando o dono sai, herda **o participante ativo mais antigo por `entrou_em`**.
Isso faz de `entrou_em` uma coluna com regra de negócio, não um carimbo.

A primeira versão do `convidar` fazia `ON CONFLICT ... SET entrou_em = now()`
**sempre**. Reconvidar alguém que **nunca saiu** reiniciava a antiguidade dele e
**reordenava a fila de herança** — a posse ia para a pessoa errada, sem nada ter
acontecido de verdade. O teste pegou isso antes de virar tela.

A correção é a mesma lição da metodologia §1: **reentrega é conflito esperado, e
conflito esperado se IGNORA**. Só quem tinha `saiu_em` preenchido recomeça a
contar.

### Os índices parciais

```sql
ix_participante_atendente (atendente_id) WHERE saiu_em IS NULL
ix_participante_conversa  (conversa_id)  WHERE saiu_em IS NULL
```

O primeiro é o que a **caixa de entrada** usa a cada carregamento; o segundo, o
cabeçalho da conversa. Parciais porque quem saiu não entra em lista nenhuma —
o índice não carrega o que nunca será consultado. ⚠️ Postgres **não** indexa FK
sozinho: é a mesma lição da migração 002.

### `transferencia.motivo` ganhou `saida_do_dono` (migração 022)

Herdar posse é troca de dono, e toda troca de dono é registrada. Mas o CHECK só
conhecia `manual | inatividade | ia_triagem | sem_time`.

🚨 **Gravar como `manual` seria mentir no dado**: o relatório diria que alguém
transferiu à mão, quando quem passou a posse foi **o sistema**, porque o dono
saiu. É a mesma lição da migração 009, que separou `motivo_ignorado` de `erro`.

### Sair, nos dois casos

| Quem sai | O que acontece |
|---|---|
| participante | marca `saiu_em`, e nada mais muda |
| **dono**, com participante | o mais antigo vira dono e **deixa de ser participante** |
| **dono**, sem ninguém | volta para a fila (`estado = 'fila'`) |

🚨 **Tudo num cursor só, com `SELECT ... FOR UPDATE` na conversa.** Entre
escolher o herdeiro e gravá-lo, o herdeiro pode ter saído — e a conversa
acabaria com um dono que não está mais lá. É a mesma serialização que o
`WHERE atendente_id IS NULL` dá ao `assumir`.

### O que a listagem passou a fazer

`listar(atendente_id=X)` deixou de significar *"sou o dono"* e passou a
significar *"sou o dono **ou** estou acompanhando"*. Cada linha ganhou o campo
**`acompanho`**, para a tela separar uma coisa da outra — sem ele a caixa de
entrada misturaria "minha" com "fui chamado", e o atendente não saberia por
qual ele responde.

⚠️ Esse foi o ponto de regressão do trabalho: mexe no `WHERE` da tela que a
operação usa todo dia. `tests/teste_listagem.py` foi escrito **antes** da
mudança e fixa o comportamento anterior — 7 testes de regressão mais 7 do
comportamento novo.

---

## Concluir atendimento — migração 029 (2026-08-25)

Pedido do usuário: *"ao 'encerrar' conversa que vamos mudar para 'concluir
atendimento', a conversa deve voltar para a coluna de 'sem dono'"*, e *"concluir
a conversa mesmo que tenham outras pessoas, ainda é uma conclusão; sair da
conversa que deixa ela somente com quem estiver nela"*.

### Concluir solta o dono, e por isso `resolvida_por` existe

```
Objetivo:     conversa concluída não continuar contando como trabalho de
              ninguém, e ainda assim saber quem atendeu
Hoje:         = o objetivo. `encerrar()` grava `resolvida_por` e zera
              `atendente_id` na MESMA instrução; os participantes recebem
              `saiu_em`; o Histórico lê COALESCE(resolvida_por, atendente_id)
Por quê:      decisão do usuário em 25/08. `resolvida_por` não é extra: era
              `atendente_id` o único lugar que dizia quem atendeu, e soltá-lo
              sem gravar antes apagaria o desfecho -- que é justamente o que a
              INI_1.1 passou a contar
Reavaliar se: aparecer necessidade de saber quem era o dono NO MOMENTO do
              fechamento, separado de quem clicou em concluir. Hoje os dois
              são a mesma pessoa em todo caso observado
```

🚨 **Reabrir limpa `resolvida_por` junto com `resolvida_em`.** Conversa
reaberta que guardasse o autor do fechamento seria contada como desfecho sem
ter desfecho, e o número da tela inicial subiria sozinho a cada
reabrir/concluir do mesmo atendimento.

⚠️ **A ordem da aba "Sem dono" precisa mudar junto.** A lista ordena por
`ultima_atividade_em`, e concluir não toca nesse campo -- então a conversa
concluída logo após a última mensagem do cliente **fica no topo**, acima de
quem espera. O usuário descreveu o comportamento esperado em 25/08: *"vai para
o fim da fila"*. Isso é ordenação explícita, não efeito colateral.

### `sem_identificacao` entra no vocabulário

```
Objetivo:     poder dizer "não sei o que esta pessoa é" sem confundir com lead
Hoje:         = o objetivo. Oitavo valor do CHECK, migração 029
Por quê:      decisão do usuário em 25/08, para o interruptor de automação por
              tipo de contato. `lead` é quem ainda não comprou -- é uma
              afirmação; `sem_identificacao` é a ausência de afirmação
Reavaliar se: a marcação em lote mostrar que ninguém usa o valor, o que
              significaria que `lead` já bastava
```

🚨 **Não confundir com a conversa sem cadastro.** São 211 conversas com
`contato_id IS NULL` (64% do total, medido em 25/08) -- essas não têm linha em
`contato` para receber marcação nenhuma, e o interruptor de automação as trata
por uma linha própria. `sem_identificacao` é para o contato que **existe** na
base e ninguém sabe o que é.

### `relacao` é flag da ficha — migração 031 (2026-08-25)

```
Objetivo:     o campo dizer o que uma PESSOA marcou, e nada além disso
Hoje:         = o objetivo. O sync não escreve nem atualiza `relacao`; o
              DEFAULT é `sem_identificacao`; quem marca é gente, na CAD_1.2
Por quê:      decisão do usuário em 25/08 -- "o sync não usará esse campo, o
              sync usa o número; o que pedi foi um flag de tipo no cadastro,
              somente será usado para regra de automação boas vindas".
              O `INSERT` de `sync._gravar_contato` tinha `'cliente'` LITERAL
              desde 06/08: não era regra, era constante. É de lá que vinham os
              1.750 de 1.754 contatos "cliente" que ninguém classificou
Reavaliar se: aparecer origem externa que saiba de verdade o que a pessoa é.
              Aí ela escreve o flag -- mas dizendo de onde veio, não como
              padrão silencioso
```

⚠️ **Os 1.754 que já existem não foram tocados.** Reclassificar cadastro é
mexer em dado, e não foi pedido. A consequência fica registrada aqui para quem
for ligar a automação: **enquanto 1.750 disserem "cliente", ligar boas-vindas
para `cliente` alcança quase a base inteira.** É por isso que a marcação em
lote vem ANTES do interruptor por tipo, e não depois.

⚠️ O `DEFAULT` era `'lead'` desde a 001. `lead` é uma afirmação — "ainda não
comprou" —, e contato recém-nascido não sustenta afirmação nenhuma.

---

## O que entrou em 2026-08-25 — migrações 030 a 034

⚠️ **Esta seção existe porque eu quase a esqueci.** As migrações 029 e 031
foram documentadas na hora; as outras quatro ficaram só no arquivo `.sql` até
o fim do dia. Modelo de dados que não está aqui é modelo que ninguém acha —
e é a mesma dívida que o `docs/03` prende com teste e este doc não prende.

### `email_conta.atendente_id` — a caixa tem dono (030)

```
Objetivo:     cada atendente ver as caixas que ELE conectou, e só elas
Hoje:         = o objetivo. `atendente_id NOT NULL`, e UNIQUE (atendente_id,
              endereco) no lugar do UNIQUE(endereco)
Por quê:      decisão do usuário em 25/08 -- "cada um vê a que logou no seu
              acesso... a Erika poderia logar o sac@ na caixa dela também, na
              outra aba". Antecipada do bloco 6 porque outra pessoa entraria
              no painel e NENHUMA rota de e-mail filtrava por conta: o
              próximo login abriria a caixa do owner inteira. Não dava erro
Reavaliar se: alguém precisar ver caixa que não conectou -- aí quem concede é
              o owner, por tabela de acesso, e não se duplica a caixa
```

🚨 **O UNIQUE de `endereco` SAIU, e o custo está declarado:** duas pessoas com
o mesmo endereço são duas contas sincronizadas, e a mesma mensagem fica
guardada duas vezes (`email_mensagem` é UNIQUE por `(conta_id, id_externo)`, e
continua certo assim). É o preço de "cada um vê a que logou".

### `relacao_automacao` e `conversa.boas_vindas_em` (032)

| Campo | Nota |
|---|---|
| `relacao` | PK. Os oito valores de `contato.relacao` **mais `sem_cadastro`** |
| `boas_vindas_ligado` | aciona de verdade. Nasce **false** |
| `boas_vindas_texto` | sem texto não se liga: ligado e vazio mandaria mensagem em branco |
| `ia_ligada` | **aciona de verdade desde 26/08** — é a 2ª das três travas da IA (canal, tipo, `ia_atendeu_ate`). Nasce **false** |

🚨 **`sem_cadastro` É LINHA AQUI E NÃO É VALOR DE `contato.relacao`.** 64% das
conversas chegam de número sem contato nenhum (211 de 332, medido em 25/08) —
é o caso majoritário, e sem esta linha ele não teria como ser configurado.

🚨 **`conversa.boas_vindas_em` é a trava de "uma vez só", e é do BANCO.** O
`UPDATE ... WHERE boas_vindas_em IS NULL` só passa uma vez mesmo com dois
processos entrando juntos — e o Evolution reentrega webhook por desenho. Trava
em `if` perderia a corrida e o cliente receberia a saudação duas vezes.

⚠️ **Marca ANTES de enviar.** Falha depois da marca custa uma saudação; na
ordem inversa, uma falha entre enviar e marcar dispararia outra saudação na
próxima mensagem, e mais outra.

### `email_mensagem.estrela` (033)

Reflexo local do marcador `STARRED`. O marcador continua sendo a verdade do
Google; a coluna existe porque a lista lê `email_mensagem` direto, e um
`EXISTS` por linha custaria uma subconsulta por mensagem numa tela que carrega
60 de uma vez.

🚨 **A tela desenhava a estrela a partir de um campo que o `SELECT` não
trazia.** Toda estrela aparecia vazia, em qualquer estado, com a rota
respondendo 200 e a lista completa em tudo o mais. Achado exercitando, não por
teste. Ficou a regra, com teste que a prende: **campo que a tela desenha tem de
estar na consulta que a tela pede.**

### `email_mensagem.na_lixeira_desde` e `email_mensagem.sumida_do_gmail_em` (046)

🔵 **Pedido dele em 17/09:** *"não temos lixeira também no movizap? não
deveria se espelhado o uso?"* — e resolve de quebra outra lacuna que a mesma
pergunta descobriu: `arquivada` existe desde a **014** e **nunca teve tela
própria**. Uma vez arquivada, a mensagem só desaparecia — sem lugar para ver
de novo.

🚨 **MEDIDO EM 17/09, CONTRA O GMAIL AO VIVO:** das 575 mensagens que o painel
mostrava, **190 (33%) já estavam na lixeira** do Gmail e **72 (13%) tinham
sido apagadas de vez** — **46% da caixa desatualizada**, e o painel não tinha
como saber. O `ler()` só baixa mensagem **nunca vista**; uma vez importada,
nunca é reconferida. Depois de rodar a varredura de verdade: **191 e 72** —
bateu com a medição manual.

| Campo | Nota |
|---|---|
| `na_lixeira_desde` | quando a varredura viu esta mensagem na lixeira do Gmail. NULL = não está lá. Volta a NULL se a pessoa restaurar — no Gmail **ou** no painel |
| `sumida_do_gmail_em` | quando a varredura deixou de achar a mensagem em **qualquer lugar** do Gmail. NULL = ainda existe, de algum jeito |

### 🚨 Em qual aba cada estado aparece — e o filtro que decide isso (22/10)

A tabela acima diz o que cada coluna **significa**. Faltava o que custou um
defeito em 22/10: **em qual aba cada estado cai.** São três estados e três
abas, e o filtro tem de conhecer os três.

| estado | `na_lixeira_desde` | `sumida_do_gmail_em` | aba |
|---|---|---|---|
| ativa no Gmail | NULL | NULL | **Entrada** (ou Arquivadas, se `arquivada`) |
| na lixeira / spam | preenchido | NULL | **Lixeira** |
| sumiu da lixeira | preenchido | preenchido | **Lixeira** |
| **sumiu sem passar pela lixeira** | **NULL** | preenchido | **Lixeira** (🔵 decisão dele, 22/10) |

🚨 **A ÚLTIMA LINHA É A QUE ENGANA, e enganou.** "Sumida" **não** é "na
lixeira": a mensagem pode ir de ativa a inexistente **entre duas varreduras**
(apagada de vez, ou purgada pelos 30 dias do Gmail) e nunca ser vista na
lixeira. Até 22/10 a aba Entrada só excluía `na_lixeira_desde` e a aba Lixeira
só olhava essa mesma flag — então **73 mensagens que já não existiam no Gmail
ficaram presas na Entrada**, e o selo do menu contava 56 delas como não lidas
(dizia 61 onde a verdade eram 5).

🚨 **O FILTRO MORA NUM LUGAR SÓ**, em `movizap/main.py`: `FILTRO_ENTRADA`,
`FILTRO_ARQUIVADAS`, `FILTRO_LIXEIRA` e `filtro_da_caixa()`. Ele estava
**copiado à mão** na rota da lista e no contador do selo, e foi a cópia que
divergiu. Quem precisar do filtro **lê a constante** — há teste que reprova
quem escrever as condições de novo (`tests/teste_filtro_sumida.py`,
`TestOFiltroEUmSo`).

⚠️ **E a mensagem sumida não aceita escrita no Gmail:** `messages/{id}/modify`
devolve 404. A tela esconde "marcar não lida", "Arquivar", "Excluir" e
"Restaurar" para ela, e deixa só "Responder" (que compõe mensagem nova e não
toca na original) — ver `semEscritaNoGmail` no `Email.vue`.

🚨 **NUNCA PERDEMOS O CONTEÚDO**, e é a diferença para o caso análogo do
WhatsApp (045): texto, HTML e anexos já foram baixados na importação.
"Sumida do Gmail" não apaga nada nosso — só registra que **lá** não existe
mais.

🚨 **A VARREDURA, NÃO `history.list`.** Medido ao vivo: listar 539 ids (com e
sem lixeira) custou **2 chamadas** — 500 por página, a mesma lição do `ler()`
("listar é barato, baixar é caro"). `history.list` resolveria só daqui para
frente; a varredura resolve o **passado acumulado** (as 262 já divergentes) e
o futuro com o mesmo código, e se autocorrige se o histórico do Google
expirar. Roda a cada 15 minutos (`scripts/sincronizar_lixeira.py`), separada
do `ler_caixa.py` de 2 em 2 — ninguém precisa saber em 2 minutos que um
e-mail sumiu.

🚨 **`excluir()` E `restaurar()` REUSAM O `_mexer_rotulo()`**, o mesmo
mecanismo de estrela/lida/arquivar — testado ao vivo em 17/09, não é rota
nova.

⚠️ **O `untrash` SOZINHO NÃO DEVOLVE O `INBOX`.** Testado ao vivo: depois do
`untrash` puro, os rótulos ficam `SENT, UNREAD` — sem `TRASH` e sem `INBOX`.
A mensagem "existe" mas não aparece em lugar nenhum da tela do Gmail. Por
isso `restaurar()` faz `poe=["INBOX"], tira=["TRASH"]` explícito, e devolve
para a **Caixa** (decisão dele) — não para Arquivadas.

⚠️ **ARQUIVADA + NA LIXEIRA SÓ CONTA COMO LIXEIRA.** Se o Gmail mandou para a
lixeira algo que também estava arquivado, a mensagem aparece na aba Lixeira,
não nas duas. Testado.

⚠️ **RESTAURAÇÃO FEITA DIRETO NO GMAIL CHEGA AO PAINEL** — não só a que passa
pelo botão daqui. A varredura lê as duas listas a cada rodada; se o id
reaparece na lista sem lixeira, os dois campos voltam a NULL. Testado
mockando as duas listagens.

### `mensagem.reacao` e `mensagem.encaminhada_de` (034)

| Campo | Nota |
|---|---|
| `reacao` | ⚠️ **REMOVIDA na 036.** A razão escrita aqui — *"do nosso lado só há um participante"* — caiu quando o cliente passou a reagir. Ver `mensagem_reacao`, no fim |
| `encaminhada_de` | FK para `mensagem`, `ON DELETE SET NULL`. NULL = escrita aqui |

✅ **A reação do CLIENTE passou a ser tratada em 26/08** (migração 036). O que
esta nota descrevia — cair no ramo de "tipo ainda não tratado" — produziu **161
mensagens falsas** antes de ser consertado.

🚨 **E O RAMO INTEIRO CAIU EM 27/08.** A reação foi o caso mais caro, não o
único: qualquer chave fora das conhecidas virava `[<chave> — tipo ainda não
tratado]` gravado em `mensagem.conteudo`, que é o que aparece no balão e no
resumo da lista, com a mesma cara de uma fala do cliente. Medido no dia: **84
linhas falsas em 28 conversas**, de 8 tipos, e **crescendo** — duas entraram
durante a própria medição, às 09:13 e às 09:59.

Hoje o parser tem três destinos, e nenhum deles é o nome cru da chave:

| Destino | Quem vai | Onde |
|---|---|---|
| **descarte** | `pollUpdateMessage` (voto criptografado), `albumMessage` (cabeçalho — as imagens chegam à parte), `placeholderMessage`, `messageHistoryNotice`, e **todo tipo ainda não tratado** | `conversas.DESCARTADOS`, e o motivo vai para `webhook_evento.motivo_ignorado` |
| **texto legível** | `templateMessage`, `pollCreationMessage*`, `listMessage`, `listResponseMessage` | extratores em `conversas.py` |
| **aviso** | `secretEncryptedMessage` **sem** `targetMessageKey` — chega criptografado e não temos a chave; o atendente precisa saber que veio algo. **Com** alvo e `secretEncType` 2 é edição e não vira linha (06/10) | `conversas.AVISOS` |

🚨 **O RÓTULO DO AVISO MENTIU DE 27/08 A 17/09.** A razão escrita acima sempre
esteve certa, mas o texto que ia para a tela dizia **"[mensagem de visualização
única]"** — que é OUTRO recurso do WhatsApp, a foto que some depois de aberta.
Ninguém decidiu chamar assim: o rótulo não seguiu a razão escrita ao lado dele,
e o nome do teste que o prendia (`test_visualizacao_unica_...`) carimbou o
engano. **Custo medido: 92 linhas em 60 conversas**, de 07/08 a 17/09.
Hoje é **"[mensagem cifrada que o painel não consegue abrir]"**, as 92 linhas
foram corrigidas (`scripts/corrigir_rotulo_cifrado.py`) e o
`teste_rotulo_cifrado.py` prende a **promessa**, não a frase: o aviso não pode
afirmar tipo que não sabemos, e tem de dizer que veio algo e que não abre.
⚠️ **Ainda não sabemos o que é.** Em 17/09 um destes apareceu no lugar exato de
uma edição de mensagem, e nem isso dá para afirmar — o conteúdo é cifrado.

⚠️ **O DESCARTE ACONTECE ANTES DE `garantir_conversa`**, no mesmo ponto da
reação. Depois dela, um voto de enquete abriria conversa a partir de ruído.

⚠️ **NADA SE PERDE.** O `webhook_evento` guarda o payload cru de tudo — foi ele
que permitiu recuperar 57 mídias, 30 nomes e 32 citações em 10/08. O que sai é
a **exibição**, e o nome da chave sobrevive no motivo. Contar por
`motivo_ignorado` custou **0,035 s**; varrer o payload custa **1,10 s por
chave**.

🚨 **`listMessage` E `listResponseMessage` NÃO ESTAVAM NO LEVANTAMENTO** — nem
podiam estar, porque nunca chegaram a virar mensagem: eles se perdem antes, num
defeito separado (ver a nota do 0800 abaixo). Apareceram só quando o parser foi
exercitado contra os 14.209 eventos reais, por `scripts/exercitar_parser.py`.
O segundo é **a pessoa respondendo a um menu** (`{"title": "Outros Assuntos"}`):
descartá-lo teria apagado o que ela escolheu. **Fixture verde não substitui o
mundo real** — é o quarto jeito, e se pagou na primeira rodada.

⚠️ **PENDENTE, NÃO CORRIGIDO: número 0800 não vira conversa.** Medido em 27/08:
**1.341 eventos `messages.upsert` com `telefone` nulo**, entre eles todo o menu
interativo de fornecedor (`558008871599@s.whatsapp.net`, um 0800 de 12 dígitos).
O `remoteJid` é normal; quem recusa é a extração do telefone. É defeito
separado, mais antigo, e **não foi tocado nesta rodada**.

🚨 **A chave do WhatsApp (`{remoteJid, fromMe, id}`) NÃO é guardada.** Reagir e
citar a reconstroem de `id_externo` + `direcao` + o destino da conversa —
guardar o trio seria copiar o que já está aqui, contra o princípio 1 deste
documento.

### `chat_mensagem.midia_id` — anexo no chat interno (047 e 048)

🔵 Pedido dele em 22/09: *"sobre envio de anexos no chat interno, igual no
aberto"*. Teto de **25 MB** e **voz gravada junto**, decididos por ele no mesmo
dia. A mídia vai para a tabela `midia`, com `sala_id` no lugar de
`conversa_id` — ver a nota daquela tabela.

🚨 **NADA SAI PARA O CLIENTE, e a garantia é de import.** O módulo `chat` não
importa o `evolution` nem o `conversas`: não existe caminho de código pelo qual
um anexo interno alcance um número de WhatsApp. É o mesmo contrato da nota
interna, que é de 12/08.

🚨 **A MENSAGEM PODE SER SÓ O ANEXO** (048). O `CHECK` original, de 026, era
`length(btrim(texto)) > 0` — certo para o mundo onde anexo não existia. Virou
`length(btrim(texto)) > 0 OR midia_id IS NOT NULL`: continua proibida a
mensagem vazia, mas quem manda um print não precisa inventar legenda. **A 047
esqueceu esta metade e quem achou foi o teste**: eu li que `texto` é `NOT NULL`
no `information_schema.columns` e concluí que vazio passaria — `CHECK` mora em
`pg_constraint`, que é outra consulta. É o `M15`.

### Até 10 anexos por envio, sem migração (25/09, item C)

🔵 Demanda dele: até 10 anexos por envio, texto só na primeira mensagem, 25 MB
cada — na Caixa e no Chat interno.

🟡 **SÓ FRONTEND.** O backend já era stateless por chamada: cada
`POST .../arquivo` (tanto `/api/conversas/{id}/arquivo` quanto
`/api/chat/salas/{id}/arquivo`) sempre tratou 1 arquivo por requisição,
criando 1 balão independente — não havia trava de "1 anexo por mensagem"
para tirar. A tela passou a aceitar `multiple` no `<input type=file>` e
manda um laço sequencial de `POST`, legenda só na primeira chamada.

⚠️ **SE UM ARQUIVO DO MEIO FALHAR, O LAÇO PARA** — decisão de engenharia
(28/09, documentada no plano de execução): não desfaz o que já chegou ao
cliente, nem segue tentando os que faltam sem avisar. A tela mostra quantos
de quantos foram, e o que falhou.

### `chat_membro.oculta_ate_id` — esconder uma conversa interna (038)

Pedido dele em 27/08: *"Canal interno -> botão de excluir conversa"*.

🚨 **ESCONDE PARA MIM, NÃO APAGA PARA O OUTRO.** É o que "excluir conversa" faz
no WhatsApp — a referência que ele escolheu para esta tela — e é a única versão
segura: apagar a sala levaria junto o histórico da OUTRA pessoa, que não pediu
nada e não tem como desfazer. **Conversa interna é prova de combinado**: quem
disse o quê sobre um atendimento.

⚠️ **E VOLTA SOZINHA** quando chega mensagem nova, também como no WhatsApp.
Esconder não pode virar um jeito de deixar de receber recado da equipe — esse
seria o defeito silencioso: a pessoa some da conversa e ninguém sabe.

🚨 **GUARDA ATÉ QUE MENSAGEM FOI ESCONDIDA, não um booleano.** Com um booleano,
ou a conversa some para sempre, ou é preciso um segundo lugar para saber quando
ela volta — e dois lugares para o mesmo estado dessincronizam.

⚠️ **`COALESCE(u.id, 0)` NA COMPARAÇÃO.** Sala escondida sem nenhuma mensagem
teria `id` NULL, e `NULL > n` não é falso: é NULL, que não é o que se quer
dizer. Com o zero a comparação é explícita, e há teste para esse caso.

⚠️ **Abrir a conversa desfaz o esconder.** Quem voltou pelo endereço está
dizendo que quer a conversa de volta; deixá-la oculta faria ela sumir de novo
no próximo carregamento, sem explicação.

**Nenhuma linha de `chat_mensagem` é tocada** — a conversa reaparece inteira,
do começo.

### `chat_reacao` — reagir a mensagem no chat interno (066)

Pedido do usuário em 16/10: *"verifique recursos de reagir a mensagens
internas, como do externo"* → *"pode fazer tudo"*.

| Coluna | Nota |
|---|---|
| `mensagem_id` | FK para `chat_mensagem`, **`ON DELETE CASCADE`** |
| `atendente_id` | FK para `atendente`, **`ON DELETE CASCADE`** — mesma forma da `chat_mencao`, para a limpeza dos testes não travar em chave estrangeira |
| `emoji` | um dos **seis da Caixa** (`chat.REACOES`), conferido no backend |
| `em` | quando reagiu (ou trocou) |

**PK `(mensagem_id, atendente_id)`** — uma reação por pessoa por mensagem:
trocar o emoji substitui (`ON CONFLICT ... DO UPDATE`), reagir com vazio apaga
a linha. É o contrato da `mensagem_reacao` (034/036) sem o eco do WhatsApp, e
por isso a chave é o `atendente_id`, não o texto `quem`.

🚨 **LISTA FECHADA DE EMOJIS, IGUAL NAS TRÊS PONTAS.** Sem ela a rota aceitaria
qualquer texto e viraria um segundo campo de mensagem. `teste_chat_reacao_busca.py`
confere que `chat.REACOES`, a `REACOES` da `CaixaDeEntrada.vue` e a do
`ChatInterno.vue` são idênticas, por codepoint (o coração é U+2764 + U+FE0F).

⚠️ **Reação não é mensagem:** não mexe em `lido_ate`, não acende não lida, não
sobe a sala na lista. Reagir à própria mensagem pode, como no WhatsApp.

⚠️ **Apagada não recebe reação, e a que já tinha some junto com o conteúdo**
para quem não é owner — mesma régua do texto (05/10).

### `chat_mencao` — quem foi chamado por `@` no chat interno (037)

Pedido do usuário em 27/08: *"interessante e pode ser, tanto no interno quanto
no do whatsa"*.

| Coluna | Nota |
|---|---|
| `mensagem_id` | FK para `chat_mensagem`, **`ON DELETE CASCADE`** — menção sem mensagem não significa nada |
| `atendente_id` | FK para `atendente`, **`ON DELETE CASCADE`** — pessoa removida não deixa linha órfã |
| `criada_em` | quando |

**PK `(mensagem_id, atendente_id)`** — chamar a mesma pessoa duas vezes na
mesma mensagem é uma menção só.

🚨 **TABELA, E NÃO COLUNA COM A LISTA — é a lição da 034→036 aplicada ANTES de
doer.** A reação nasceu como coluna, com a razão escrita, e a razão caiu quando
o cliente entrou: numa conversa com várias pessoas, uma coluna guarda a última
e **apaga as outras em silêncio**. Menção tem a mesma forma: uma mensagem pode
chamar três pessoas, e um grupo do chat interno tem até cinco.

🚨 **QUEM RESOLVE O `@` É QUEM ESCREVE, na hora de escolher na lista.** O
compositor manda os IDS; o backend só **confere** que cada um é membro da sala.
Um regex lendo o texto teria de adivinhar onde o nome termina (*"Suporte
Erika"* tem espaço no meio), casar apelido e desempatar homônimo — e erraria em
silêncio nos três casos.

🚨 **CHAMAR QUEM NÃO ESTÁ NA SALA É RECUSA, NÃO REMENDO**, e a recusa diz o
nome de quem não está. Aceitar e ignorar faria a pessoa achar que avisou alguém
que nunca vai ver a mensagem — é o "parâmetro aceito e ignorado", que este
projeto cataloga como o pior defeito. A mensagem inteira é recusada: meia
gravação seria pior que nenhuma.

⚠️ **O TEXTO NÃO GANHA MARCAÇÃO EMBUTIDA.** Guardar `@[12:Erika]` tornaria o
histórico ilegível fora da tela, e o texto do chat é lido em log e em busca. O
destaque no balão vem de `chat_mencao`, nunca de procurar `@` no texto —
procurar acenderia `suporte@movisat.com.br` como se fosse gente.

⚠️ **Menção não lida usa o MESMO `lido_ate` do resto** (`chat_membro`). Não há
segundo marcador para dessincronizar. A conta é separada porque 40 mensagens
não lidas num grupo é rotina, e **uma** em que alguém te chamou pelo nome não
é.

🔵 **`TETO_MENCOES = 20` é número MEU**, rotulado como meu em `chat.py`: não há
decisão do usuário sobre isso, e 20 é maior que a equipe inteira (5 hoje).
**Limite é decisão dele** se um dia apertar.

### `config.jornada_ativa` — sem migração, e de propósito

O interruptor da jornada é **um valor para o sistema inteiro**, e a tabela
`config` existe exatamente para isso desde a 001. Nasce desligado: monta-se a
escala com calma, e ligar é ato separado (decisão do usuário em 25/08).

### `conversa.ia_atendeu_ate` (035) — a trava de não responder duas vezes

| Campo | Nota |
|---|---|
| `ia_atendeu_ate` | Id da última mensagem de **entrada** que a IA já atendeu. NULL = nenhuma |

🚨 **É A MESMA LIÇÃO DE `boas_vindas_em`, EM OUTRO LUGAR.** A trava é do
BANCO: `UPDATE ... WHERE ia_atendeu_ate IS NULL OR ia_atendeu_ate < %s` só
passa uma vez, mesmo com duas execuções simultâneas — e há duas, porque
`processar_pendentes` roda no laço de 5 s **e** na rota
`/api/conversas/processar`. Um `if` no Python perde a corrida, e o cliente
recebe duas respostas da IA para a mesma pergunta.

⚠️ **GUARDA O ID DA MENSAGEM, NÃO UM `timestamp` NEM UM `bool`.**

| Alternativa | Por que não |
|---|---|
| `bool` | serviria uma vez: a IA responderia a primeira mensagem da conversa e mais nenhuma |
| `timestamp` | compararia com `criada_em`, que é a hora **do provedor** e chega fora de ordem por desenho — mensagem atrasada pareceria já respondida |

O id é monotônico e é nosso. `ia_atendeu_ate < <id da última entrada>` é a
pergunta exata: *existe entrada que a IA ainda não viu?*

🚨 **A MARCA VEM ANTES DA CHAMADA AO MODELO.** Falha depois da marca custa uma
resposta; na ordem inversa, uma falha entre responder e marcar faria a próxima
passada responder de novo. **Repetir é pior do que faltar** — a mesma regra da
saudação automática.

### `canal.ia_ligada_em` deixou de ser só registro (035)

A coluna existe desde a 007 para responder *"desde quando a IA está
respondendo os clientes?"*. Desde 26/08 ela também **decide**: a varredura da
IA só olha mensagem com `criada_em > canal.ia_ligada_em`.

🚨 **SEM ISSO, LIGAR O INTERRUPTOR RESPONDERIA A BASE INTEIRA DE UMA VEZ.**
Havia **357 conversas abertas** quando o motor entrou. A IA sairia respondendo
a todas, a mensagens de dias atrás, no meio de conversas que já seguiram sem
ela — exatamente o que a auditoria de 25/08 achou na saudação automática, que
mandaria "seja bem-vindo" para gente no meio de uma conversa em andamento.
Achado ao escrever o teste da varredura, não pelo placar.

⚠️ **Ligado sem hora não atende nada.** Pelo caminho oficial isso não
acontece (a rota grava as duas coisas juntas), mas quem editar a coluna na mão
não pode com isso fazer a IA varrer o passado inteiro.

### `mensagem_reacao` (036) — a reação do cliente, e o fim da coluna única

| Campo | Nota |
|---|---|
| `mensagem_id` | FK, `ON DELETE CASCADE`. Apagou a mensagem, some a reação |
| `quem` | `'nos'` se saiu do painel; senão o **JID de quem reagiu** |
| `quem_nome` | o `pushName` de quem reagiu. Só existe em grupo, e é apelido |
| `emoji` | `CHECK (emoji <> '')` — vazio não é reação, é a remoção dela |

`UNIQUE (mensagem_id, quem)` — **reagir de novo TROCA** (upsert), reagir com
nada **APAGA** a linha. É assim que o WhatsApp funciona: não existe "remover
reação", existe reagir com nada.

🚨 **O QUE ISTO CONSERTOU, MEDIDO EM 26/08: 161 mensagens falsas.** Cada vez
que alguém reagia com um emoji, o painel gravava no meio da conversa uma linha
`[reactionMessage — tipo ainda não tratado]`, para o atendente ler. O defeito
não era a reação faltar — era ela virar **lixo visível** em conversa real.
`scripts/migrar_reacoes.py` recuperou **159** delas para o lugar certo e só
então apagou as falsas; **2 ficaram** porque reagiam a mensagens anteriores ao
painel, e o que não pôde ser recuperado não foi apagado.

🚨 **`mensagem.reacao` SAIU, E A RAZÃO DA 034 CAIU COM O CLIENTE ENTRANDO.**
Aquela migração escolheu coluna e escreveu o porquê: *"do nosso lado só existe
um participante (o painel)"*. Estava certo enquanto só nós reagíamos. Das 161
medidas, **64 são em GRUPO** (40%): num grupo de quinze, uma coluna guarda o
último que reagiu e **apaga os outros em silêncio**. Duas colunas resolveriam a
conversa direta e continuariam erradas no grupo.

⚠️ **Sair não custou dado: zero linhas usavam a coluna** (a 034 é de 25/08 e
ninguém reagiu pelo painel desde então). Mantê-la seria manter **duas verdades
sobre a mesma coisa**, que é o que o princípio 1 deste documento proíbe.

🚨 **QUEM REAGIU VEM DO `key` DE FORA, NÃO DO DE DENTRO.** O
`reactionMessage.key` aponta para a mensagem **reagida**: usar o `fromMe` dele
diria de quem é a mensagem, não de quem é a reação — e toda reação nossa a uma
mensagem do cliente ficaria marcada como dele. Tem teste que prende isso.

⚠️ **A tela lê `reacoes` agrupado por emoji**, com `n` e `nosso`, por
subconsulta e não por `JOIN`: com `LEFT JOIN` a mesma mensagem viria repetida
uma vez por reação, e o `LIMIT` de 60 passaria a contar reação como mensagem.

### `preferencia_atendente` — o gosto de cada pessoa (040)

Pedido dele em 28/08: *"crie nas configurações tela de atalhos e interruptor
desligado para eles e permita edição por lá também"*.

```sql
preferencia_atendente (
    atendente_id  BIGINT REFERENCES atendente(id) ON DELETE CASCADE,
    chave         TEXT,
    valor         TEXT,
    atualizado_em TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (atendente_id, chave)
)
```

🚨 **POR QUE NÃO NA `config`.** A `config` é do **sistema** — repasse por
inatividade, horário de atendimento, avaliação ligada. Atalho de teclado é a
**mão de quem usa**, e ele já tinha fixado isso em 27/08: *"quais teclas é
decisão sua — atalho é regra de uso"*. Guardar em `config` faria a tecla de uma
pessoa mudar a de todas, com nove em teste ao mesmo tempo.

🚨 **SEM LINHA = PADRÃO DO CÓDIGO, e o padrão dos atalhos é DESLIGADO.** Ele
pediu o interruptor desligado, e a ausência tem de significar isso: se
significasse "ligado", quem nunca abriu a tela teria o teclado agindo — que é
exatamente o risco que o pedido veio fechar.

⚠️ **GENÉRICA DE PROPÓSITO** (`chave`/`valor`), e não uma coluna `atalhos` no
`atendente`. Hoje guarda `atalhos_ligados` (bool como texto) e `atalhos_teclas`
(JSON). A próxima preferência — tema, densidade, ordenação padrão — entra sem
migração. Coluna por preferência faz a tabela crescer de lado a cada gosto novo.

⚠️ **`ON DELETE CASCADE` aqui é seguro**, ao contrário do resto do painel:
preferência não é histórico. Atendente não é apagado (é desativado), mas se um
dia sumisse, o gosto dele não faz falta a ninguém — diferente de `conversa` e
`transferencia`, que apontam para ele e fariam o histórico mentir.

⚠️ **O JSON de teclas é lido com desconfiança:** só ação conhecida sobrescreve
o padrão, e JSON ilegível cai no padrão sem estourar. Versão antiga pode ter
gravado ação que não existe mais, e ela não pode virar atalho fantasma.


### `foto_perfil` — a foto do WhatsApp, por telefone (041)

🟢 Pedido da Erika em 15/09: *"permitir exibir as fotos de perfil de cada
contato"*.

```sql
foto_perfil (
    e164        TEXT PRIMARY KEY,
    arquivo     TEXT,
    sem_foto    BOOLEAN NOT NULL DEFAULT false,
    buscada_em  TIMESTAMPTZ NOT NULL DEFAULT now()
)
```

🚨 **POR TELEFONE, NÃO POR CONTATO.** A foto é de quem está no WhatsApp, e
**61% das conversas não têm cadastro** (medido em 28/08) — pendurar no
`contato` deixaria justamente a maioria sem foto. O telefone é o que sempre
existe.

🚨 **O ARQUIVO FICA EM DISCO; A URL NÃO SERVE.** Medido em 15/09 no payload
real: a URL que o WhatsApp devolve traz `oe=` no fim — ela **expira**.
Guardar o link daria uma foto que funciona hoje e vira quadrado quebrado
semana que vem, sem nada no log dizendo por quê. É a mesma decisão que já vale
para a mídia das mensagens.

⚠️ **`sem_foto` distingue "perguntei e não tem" de "nunca perguntei"** (que é
a ausência da linha). Sem esse campo, todo número sem foto viraria uma
pergunta repetida ao Evolution para sempre.

⚠️ **`buscada_em` segura a renovação em uma vez por dia por número.** Quem
troca de foto não troca de hora em hora, e cada consulta é uma ida à rede.

⚠️ **Nunca no caminho da mensagem.** A busca roda quando a TELA pede, ao abrir
uma conversa — nunca ao gravar mensagem, que é onde este projeto mais paga
caro por lentidão.


### `conversa_leitura` — até onde cada pessoa leu (042)

🟢 Pedido da Erika em 15/09: *"aparecer a bolinha de quantidade de novas
mensagens como no bitrix e whatsapp"*.

```sql
conversa_leitura (
    conversa_id   BIGINT REFERENCES conversa(id)  ON DELETE CASCADE,
    atendente_id  BIGINT REFERENCES atendente(id) ON DELETE CASCADE,
    lido_ate      BIGINT NOT NULL DEFAULT 0,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (conversa_id, atendente_id)
)
```

🚨 **ISTO NÃO EXISTIA PARA O WHATSAPP.** O chat **interno** tem
`chat_membro.lido_ate` desde sempre, e é dele que sai o selo do menu; a
conversa de cliente não tinha nada equivalente — **nenhuma coluna, em nenhuma
tabela**, dizia o que alguém já tinha lido. Esta tabela copia o modelo que já
funciona ao lado, em vez de inventar um segundo jeito de responder à mesma
pergunta.

🚨 **POR PESSOA, e é o ponto.** A mesma conversa está lida para quem acabou de
atender e não lida para quem vai pegar o plantão. Uma marca única na
`conversa` diria que está lida para todos assim que UM abrisse.

⚠️ **Conta só `direcao = 'entrada'`**: o que nós mesmos mandamos nunca é
"não lido".

⚠️ **Abrir a conversa é o que marca** — o mesmo gesto do WhatsApp. A marcação
vai até a última mensagem que existe NAQUELE instante: se outra chegar entre a
leitura e a gravação, ela fica por ler, que é o certo.

🚨 **MARCO ZERO EM 15/09.** A tabela nasceu vazia e ausência de linha significa
"tudo por ler" — o que é certo para conversa nova e absurdo para a base
inteira: medido antes de ligar, a Erika via **536 não lidas** numa conversa de
agosto que ela já tinha atendido. O passado entrou como lido (4.500 linhas,
9 atendentes × as conversas existentes) e a contagem vale daqui para a frente.
Reverter é `DELETE FROM conversa_leitura`; nenhuma mensagem é tocada.

### `mensagem.editada_em` e `mensagem.conteudo_original` (043)

| Campo | Nota |
|---|---|
| `editada_em` | quando a **última** edição chegou. NULL = nunca editada, que é o caso de praticamente todas as 26.559 de hoje |
| `conteudo_original` | o texto como chegou da **primeira** vez. Não se sobrescreve nas edições seguintes (`COALESCE(conteudo_original, conteudo)`) |

🚨 **A EDIÇÃO JÁ CHEGAVA E ERA JOGADA FORA.** Medido em 17/09 nos **54.544
eventos crus** recebidos desde 18/08: `editedMessage` apareceu **5 vezes**, e
as 5 casam com uma mensagem nossa pelo `keyId` — 5 de 5. Elas entram por
`messages.update`, o **mesmo evento do tique de entrega**, e o
`_atualizar_entrega` só olhava `data.status`: o texto novo ia para o lixo, e o
atendente seguia lendo a versão velha para sempre. Casos reais desta base:
*"Bom dia"* virou *"Boa tarde"*, *"ponstuais"* virou *"pontuais"*, e um comando
SMS de rastreador ganhou *"para ativar ign virtual"* que ninguém do atendimento
chegou a ver.

🚨 **O TEXTO NOVO MORA EM DOIS LUGARES**, e ler só um esvaziaria quase metade
das edições — pior que não tratar, porque apagaria o que estava certo:

| Formato | Quantos dos 5 casos reais | Quando o WhatsApp usa |
|---|---|---|
| `editedMessage.message.conversation` | 2 | texto simples |
| `editedMessage.message.extendedTextMessage.text` | 3 | texto com citação, menção ou prévia de link |

🚨 **A EDIÇÃO NÃO TOCA EM `entrega`, de propósito.** O `status` que vem junto é
o ack da **edição** (`SERVER_ACK` → "enviada"), não o da mensagem. Gravá-lo
rebaixaria para "enviada" um tique que já estava **lida** — o ✓✓ azul
desapareceria porque o cliente corrigiu uma vírgula. É o que o teste
`test_nao_rebaixa_o_tique_de_leitura` prende.

⚠️ **ALVO QUE NÃO TEMOS NÃO VIRA NADA**, mesma regra da reação (036): a edição
pode ser de mensagem anterior ao painel, e inventar linha para ela poria na
conversa um texto sem contexto nenhum.

⚠️ **O ORIGINAL FICA PORQUE O ATENDENTE AGIU SOBRE O QUE LEU.** Se o cliente
edita depois, o que foi lido não pode sumir do registro — é a mesma razão de
*"esconder conversa é para mim, não para o outro"* (27/08). Na tela, o balão
mostra a palavra **editada** ao lado da hora (palavra visível, não `title` —
M10) e clicar nela abre o texto anterior.

⚠️ **AS 5 EDIÇÕES ANTIGAS NÃO FORAM APLICADAS.** O tratamento vale de 17/09 em
diante; os 5 eventos continuam em `webhook_evento`, já marcados como
processados. Reaplicá-los é decisão do usuário — o ensaio com `ROLLBACK`
provou que funcionaria nos 5.


### `mensagem.apagada_em` (045)

| Campo | Nota |
|---|---|
| `apagada_em` | quando o WhatsApp avisou que foi apagada **para todos**. NULL = nunca apagada. O `conteudo` **não** é destruído |

🚨 **PROVADO CONTRA O MUNDO REAL EM 17/09, e só depois de três medições que
diziam o contrário.** O `messages.delete` nunca tinha chegado em **54.544
eventos** (18/08 a 17/09), por **dois motivos somados**:

1. **`MESSAGES_DELETE` não estava assinado** no webhook do Evolution — a lista
   tinha 5 eventos e este não era um deles;
2. **mesmo depois de assinar, o que NÓS apagamos não volta.** Exercitado duas
   vezes contra o número de teste: o Evolution executa o REVOKE (a resposta
   traz `protocolMessage` com `type: REVOKE`, e ele confirmou que a mensagem
   aparece apagada no celular) e o webhook **não recebe nada**.

**O que destravou foi o teste dele:** três *"Oi"* do próprio celular para o
número do painel, e o terceiro apagado para todos. O evento chegou **6
segundos depois**, e aponta certo para a mensagem.

🚨 **O ID DO ALVO VEM EM `data.id`, E ESTE É O TERCEIRO LUGAR** do mesmo
provedor, para a mesma coisa:

| Evento | Onde está o id da mensagem |
|---|---|
| `messages.upsert` | `data.key.id` |
| `messages.update` | `data.keyId` |
| **`messages.delete`** | **`data.id`** |

Quem escrever o handler olhando só o que já conhecia erra o alvo **e não
acusa nada**: `UPDATE` que não casa linha nenhuma não é erro. O handler aceita
os três, e há teste preso nisso.

⚠️ **O TEXTO NÃO É DESTRUÍDO**, e é a mesma razão da 043: o atendente **agiu
sobre o que leu**. Apagar o registro faria a conversa mentir sobre o que foi
dito. O que muda é a **exibição** — o balão diz *"mensagem apagada"* e o texto
fica atrás de *"ver o que dizia"*.

🟡 **A ESCOLHA DA EXIBIÇÃO É REVERSÍVEL, E É DELE.** As três saídas eram:
esconder de vez (o atendente nunca mais lê), não esconder nada (só um aviso no
balão) ou o meio — marcar e esconder atrás de um clique. Escolhi o meio porque
não perde informação e respeita a intenção de quem apagou. **Mudar é trocar um
`v-if`.**

⚠️ **REENTREGA NÃO REMARCA.** O `UPDATE` tem `AND apagada_em IS NULL`: sem
isso, uma reentrega do Evolution moveria a hora do apagamento para a hora da
reentrega.

### Nota interna editável/apagável, sem migração nova (28/09)

🔵 Demanda dele, 25/09: nota interna editável/apagável por quem escreveu, com
"editada por X, em ..." e ícone da versão anterior.

🟡 **REAPROVEITA AS MESMAS COLUNAS DA 043/045**, em vez de criar a tabela
`mensagem_versao` que o plano original previa. A nota é uma linha de
`mensagem` (`tipo='nota'`), e `editada_em`/`conteudo_original`/`apagada_em`
já existem ali, genéricas — não são específicas de WhatsApp. Editar/apagar
nota vira `UPDATE` local, sem chamar o `evolution` (que a função nem
importa).

**Diferença de regra em relação à mensagem para o cliente:** SEM janela de
tempo — decisão dele (28/09), porque é registro interno, nunca sai daqui.
`conversas.editar_nota`/`apagar_nota` conferem só que `atendente_id` é quem
escreveu, nunca a idade da mensagem.

Rotas: `POST /api/conversas/{id}/nota/editar` e `.../nota/apagar`, corpo
igual ao de editar/apagar mensagem enviada (`EdicaoEntrada`/`MensagemAlvo`).

### `chat_mensagem.editada_em`, `.conteudo_original`, `.apagada_em` (061)

🔵 Demanda dele, 25/09 (Plano 4, item B): "Chat interno: editar (15 min) e
apagar (48 h) a própria mensagem, como na Caixa".

Mesmo padrão da 043/045, agora em `chat_mensagem`. Sem chamada ao
`evolution` — é mensagem interna, nunca vai ao WhatsApp. Funções em
`chat.py`: `editar_propria`/`apagar_propria`, mesmas janelas
(`JANELA_EDITAR_MIN=15`, `JANELA_APAGAR_HORAS=48`) e mesmo formato de
`UPDATE` (`conteudo_original = COALESCE(conteudo_original, texto)`).

Rotas: `POST /api/chat/salas/{sala_id}/mensagens/{mensagem_id}/editar` e
`.../apagar`.

**Apagada, só o owner vê** (🔵 05/10 — *"apagar mesmo e não deixar registrado o
que dizia, somente ao owner deixar para ver"*). O texto fica no banco; quem
esconde é a LEITURA, por `chat._eh_owner`. Todas as portas por onde o conteúdo
sai precisam da mesma guarda:

| Porta | Guarda | Desde |
|---|---|---|
| `chat.mensagens` (texto, histórico, mídia) | zera para quem não é owner | 05/10 |
| `chat.salas` (prévia da última) | `ultima_mensagem` NULL | 05/10 |
| citação (`citada_texto`, `citada_midia_*`) | `q.apagada_em AS citada_apagada_em` e zera | 07/10 |
| `/api/midia/{id}` e `/ver` | `chat.midia_escondida()` → 404 | 07/10 |

🚨 **As duas últimas vazaram de 05/10 a 07/10.** A citação levava o texto da
apagada para todos; o link do anexo só conferia a sala, e o `midia_id` é
sequencial. Porta nova que devolver conteúdo de `chat_mensagem` entra nesta
tabela. A tela não cita owner (pedido dele, 07/10): diz `mensagem excluída`.

### Item G (25/09): tique de leitura no Chat interno, sem coluna nova

🔵 Demanda dele: *"ajustar o painel interno visualmente igual ao do externo
e as confirmações de envio e leitura tbm"*.

🟡 **NÃO PRECISOU DE MIGRAÇÃO.** O dado já existia em `chat_membro.lido_ate`
(watermark por sala/membro, da 026). `chat.mensagens()` ganhou uma coluna
calculada `lida`, comparando o `id` da mensagem com o `lido_ate` de quem
não é o autor:

- sala `direta` (2 pessoas): `lida` = o outro membro já leu até este id;
- sala `grupo`: por decisão dele (28/09), `lida` só quando **TODOS** os
  outros membros já leram — `MIN(COALESCE(lido_ate, 0))` entre eles.

Só 2 estados no tique (`enviada`/`lida`, `TIQUE_CHAT` no Vue) — não existe
"entregue" aqui, é tudo local, sem gateway externo que confirme entrega.

⚠️ **NÃO ENTROU:** a Caixa só marca como lida com a aba visível
(`document.hidden`); o Chat interno continua marcando sempre que a sala é
aberta. Achado da exploração, não pedido — registrado como pendência
separada, não implementado sozinho.

⚠️ **O visual (cor, bico) passou a usar os tokens `--conversa-*`**, os
mesmos da Caixa. Isto reverte uma decisão de 22/09 que evitava de propósito
a cor do WhatsApp no chat interno (*"o chat interno não é WhatsApp"*) — a
demanda de 25/09 é posterior e explícita, e prevalece.

### O achado paralelo: a edição em conversa direta chega cifrada

✅ **RESOLVIDO EM 06/10 (marca, não texto).** Era a edição, e dá para provar sem
a chave: o `secretEncryptedMessage` traz `secretEncType` **2** (MESSAGE_EDIT no
protocolo do WhatsApp) e **`targetMessageKey.id`** = a mensagem editada. Medido
em 06/10: **94 de 94** eventos assim, todos com o original no banco. Hoje
`conversas._marcar_edicao_cifrada` grava `editada_em` no original e **não cria
linha**; `conteudo` fica como estava e **`conteudo_original` fica NULL — esse
NULL é o sinal** para a tela dizer só *"editada"* (e, no clique, que o texto
exibido é o de antes da edição). 🔵 **07/10, decisão dele: só a ação** — saiu o
"(texto novo ilegível)"; exclusão passou de "mensagem apagada"/"apagada pelo
cliente" para *"mensagem excluída"*/*"excluída"*. Decifrar foi descartado: a
Evolution 2.4 só existe como rc, não sobe o Baileys e não corrige; o patch do
Baileys (#2743) segue sem merge. Reavaliar só se o #2743 entrar. Sem alvo
ou com outro `secretEncType`, continua o aviso. Backfill feito só no número de
teste (3 linhas, `scripts/backfill_edicao_cifrada.py`); restam **152** linhas-lixo,
e só **91** ainda têm o evento bruto que aponta o alvo (de 08/09 em diante): as
61 mais antigas perderam o evento no expurgo de 30 dias e não dá para saber
qual mensagem editaram. Esperam decisão. ⚠️ O evento `MESSAGES_EDITED` da Evolution chega como
**`messages.edited`** e, nesta base, só trouxe ruído interno
(`GROUP_MEMBER_LABEL_CHANGE`, `PEER_DATA_OPERATION...`).

O registro abaixo é o de 17/09, mantido como histórico.

⚠️ **NO MESMO TESTE, A EDIÇÃO DO SEGUNDO *"Oi"* NÃO CHEGOU COMO
`editedMessage`.** O que chegou 6 segundos depois dos três *"Oi"* foi um
`secretEncryptedMessage` — id novo, conteúdo cifrado, ilegível para nós. É o
único candidato pelo horário, mas **não dá para provar que é a edição**, porque
não temos a chave.

🔴 **E ELE VIROU UMA LINHA FALSA NA CONVERSA.** O `AVISOS` traduz
`secretEncryptedMessage` para **"[mensagem de visualização única]"**, que é
outro recurso do WhatsApp — o atendente lê que chegou uma foto que some, e o
que houve foi outra coisa. **Rótulo errado, e é do mesmo tipo dos que já
custaram caro aqui.** Fica registrado como pendência, separado desta entrega.

⚠️ **As 5 edições que FUNCIONAM não vieram todas de grupo** — 2 de `@lid`
(conversa direta) e 3 de `@g.us`. Então não é "grupo sim, direto não": alguma
outra coisa decide se a edição vem legível ou cifrada, e ainda não sei o quê.


---

## 23/09 — bloqueio pelo painel, e o resumo da transferência que ninguém lia

### `numero_bloqueado` — o que o painel bloqueou (050)

🔵 Pedido dele em 23/09: *"permitir ler e só bloquear se existir pelo painel
tbm"*.

```sql
numero_bloqueado (
    id               BIGSERIAL PRIMARY KEY,
    canal_id         BIGINT NOT NULL REFERENCES canal(id),
    telefone_e164    TEXT   NOT NULL,
    bloqueado_por    BIGINT REFERENCES atendente(id) ON DELETE SET NULL,
    bloqueado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    desbloqueado_por BIGINT REFERENCES atendente(id) ON DELETE SET NULL,
    desbloqueado_em  TIMESTAMPTZ,
    CHECK (desbloqueado_em IS NULL OR desbloqueado_em >= bloqueado_em)
)
-- UM bloqueio ativo por número e canal:
UNIQUE (canal_id, telefone_e164) WHERE desbloqueado_em IS NULL
```

🚨 **O PAINEL GUARDA O PRÓPRIO REGISTRO PORQUE O WHATSAPP NÃO CONTA.** Medido
na instância real (Evolution 2.3.7) em 23/09: bloquear existe
(`POST /chat/updateBlockStatus`), mas **não existe rota que liste os
bloqueados** — cinco nomes testados, todos 404 — e **nenhum evento de
bloqueio** chega pelo webhook (57 mil eventos: só mensagens, conexão e QR).
Bloqueio feito **no celular** é invisível para o painel.

⚠️ **HISTÓRICO, NÃO ESTADO.** Desbloquear preenche `desbloqueado_em`; a linha
fica. **Anota depois de o WhatsApp aceitar** — anotar antes deixaria o painel
dizendo "bloqueado" para um número que o WhatsApp não bloqueou.

**Efeitos na tela e nas rotas:** a conversa bloqueada sai das abas (menos na
**busca**, onde aparece marcada) e vai para o filtro "Bloqueados"; as rotas de
envio ao cliente (`responder`, `arquivo` não interno, `audio`) recusam 409;
**nota interna continua valendo**. Grupo não se bloqueia.

### O resumo da transferência vira nota interna (049)

🔵 Pergunta dele: *"o campo 'Resumo' tem uso real? ou apenas front?"* —
**era só frente**: o texto ia para `transferencia.resumo` e nenhuma consulta o
lia de volta. Desde 23/09 `conversas.transferir` grava, na mesma transação,
uma `mensagem` `tipo = 'nota'`, `direcao = 'interna'`:
*"Transferida para {pessoa | o time X}. Resumo: …"*. A 049 fez o mesmo para
o que já estava gravado — **só `motivo = 'manual'`**: das 22 linhas com
resumo, 21 eram texto automático da saída do dono. Entrou 1 (conversa 12853).

### Colunas que a lista e a conversa passaram a devolver (sem migração)

- `atendente_estado` (de `atendente.estado`) na lista e na conversa — a
  bolinha de quem responde;
- `bloqueado` na lista e `bloqueio` na conversa;
- `mensagem.atendente_id` na leitura das mensagens — a tela só oferece
  editar e apagar na mensagem de quem está olhando.

### Editar e apagar o que NÓS mandamos (sem migração)

Reusam `editada_em`, `conteudo_original` (o `COALESCE` guarda a primeira
versão) e `apagada_em` — as mesmas colunas da edição e exclusão feitas pelo
**cliente**. 🚨 **O que nós apagamos não volta pelo webhook** (provado em
17/09): a rota marca `apagada_em` ela mesma.

## 24/09 — perfil admin, status por tempo, afastamento, fim de expediente

### `atendente.perfil` volta a aceitar `admin` (051)

🔵 Decisão dele: o admin enxerga atendimento + Times + Atendentes + Minha
conta. Só o `CHECK` mudou; o alcance mora em `telas.PERFIS` (permissão nova
`equipe`). O owner continua único.

### Presença do atendente (052)

| Coluna | Para quê |
|---|---|
| `atendente.ultima_acao_em` | última AÇÃO DE ATENDIMENTO (enviar, nota, assumir, entrar, transferir, concluir...). Ler não conta: a tela relê a conversa a cada 8 s. NULL = sem ponto de partida, e a regra não derruba quem está NULL |
| `atendente.estado_automatico` | `true` = o estado foi posto pela regra de tempo, e a próxima ação o desfaz (volta a disponível). Estado escolhido à mão nunca volta sozinho |
| `atendente.painel_visto_em` (**067**, 19/10) | quando o painel desta pessoa falou com o servidor pela última vez — carimbada pela **lista da Caixa** e pelo **pedido de notificações**, que roda em toda tela (uma escrita por minuto, no máximo). 🚨 Prova que a **aba está aberta**, não que alguém a esteja olhando, e **não é ação**: não devolve ninguém a disponível nem zera `ultima_acao_em`. ⚠️ **Mudou de trabalho no mesmo dia:** de manhã segurava o offline dentro da jornada; à tarde, com a regra fechada (*"dentro da jornada cadastrada, impossível ficar fora do expediente"*), saiu da régua de estado e passou a decidir **quem sai da FILA** (`presenca.painel_aberto_agora`, `distribuicao._pode_receber_da_fila`). `NULL` conta como fechado |
| `atendente.sempre_online` | exclusivo do owner (`ck_sempre_online_so_owner`): dentro da jornada dele, a regra não o toca |
| `atendente.afastamento_motivo`, `atendente.afastado_ate` | férias, licença... Com motivo preenchido, a pessoa está offline e não recebe. Desde a 055, `afastado_ate` é o **dia da volta** e vale: nesse dia o laço encerra sozinho |
| `conversa.fora_expediente_em` | trava de "uma vez a cada 12 h" da mensagem de fim de expediente, no mesmo desenho de `boas_vindas_em` |

As regras ficam em `config` (sem migração): `presenca_regra_ligada`,
`presenca_minutos_ausente` (15), `presenca_minutos_offline` (60),
`fora_expediente_ligada`, `fora_expediente_texto`. Nascem desligadas.

### `ux_atendente_email` — e-mail de atendente é único (053)

Achado da auditoria de 24/09: a entrada pelo Google casa por `google_sub` ou
e-mail, e o e-mail não era único. Com o admin criando contas, dois cadastros
com o mesmo e-mail deixavam a entrada ambígua e podiam derrubar a do dono.
Índice único em `lower(email)`, ignorando nulos; nenhum repetido existia.

### `atendente.notificacao_ativa` (054) — o owner liga e desliga a notificação de cada um

🔵 *"a opção da notificação estar ativada por usuario ou não, só aparece ao
Owner"*. Coluna, e não `preferencia_atendente`: aquela tabela é o GOSTO da
pessoa (tom e volume moram lá, chaves `notificacao_tom` e
`notificacao_volume`); isto é decisão do owner SOBRE ela. Nasce ligada.
Desligada, não toca nem pisca; o contador das abas continua.

## 25/09 — interruptor Ativo/Inativo, afastamento com datas, sem teto

### Afastamento marcado (055)

🔵 *"ao definir o motivo, um calendário já indica a saída e a volta, daí
volta"*; as conversas passam ao substituto *"no dia da saída"*.

| Coluna | Para quê |
|---|---|
| `atendente.afastado_de` | o dia em que o afastamento EM CURSO começou (só para mostrar) |
| `atendente.afasta_em` | dia da saída de um afastamento MARCADO |
| `atendente.afasta_ate` | dia da volta do marcado (`ck_afasta_volta_depois`: depois da saída) |
| `atendente.afasta_motivo` | o motivo do marcado |
| `atendente.afasta_substituto_id` | quem recebe as conversas abertas no dia da saída (FK, `ON DELETE SET NULL`) |

🚨 **POR QUE COLUNAS PRÓPRIAS PARA O MARCADO.** `afastamento_motivo`
preenchido quer dizer "afastado AGORA" em seis lugares (`pode_receber`,
`transferir`, a lista de quem recebe...). Gravar ali um afastamento da semana
que vem afastaria a pessoa hoje. `ck_afasta_completo`: tudo ou nada.

O laço de 60 s de `presenca` (`aplicar_afastamentos`) roda **sempre**, antes
da regra de status: começa o marcado no dia da saída (transfere; se o
substituto não puder receber, a conversa vai para a fila com nota do
sistema) e encerra o em curso no dia da volta, deixando a pessoa **offline**.
"Hoje" é no fuso da pessoa (`atendente.fuso`), nunca `date.today()` do
servidor, que está em UTC.

### `max_conversas` sai (056)

🔵 *"não deve haver máximo de conversas para a pessoa ou para receber
conversas"*. Medido em 25/09: 0 de 11 com valor, e nenhuma consulta a lia.
Aplicada **depois** do backend novo no ar: o antigo a selecionava.

### Ativo/Inativo, sem migração

O antigo "desligar" apagava `senha_hash`, `google_sub` e os times, e não
tinha volta (o e-mail único da 053 impedia até recadastrar). Agora
`atendente.ativo` é um interruptor nos dois sentidos, por rota própria
(`PUT /api/atendentes/{id}/ativo`); a edição comum não grava mais `ativo`.
Inativo não entra (`auth` recusa a cada chamada) e a conta fica inteira.
Nunca menos de um owner ativo.

### `mensagem_rapida` — mensagens rápidas (057, Plano 3)

🔵 Três tipos, cada um uma aba da CFG_12.1: **Padrões** (owner e admin),
**Minhas notas** (cada um as suas), **Formulários** (*"serão links"*; owner e
admin). *"Apelido curto ... e ele quem aparecerá na lista da conversa"*.

```sql
mensagem_rapida (
    id, tipo ('padrao'|'nota'|'formulario'), apelido (1-60), conteudo (1-4000),
    atendente_id  -- só a nota tem dono (ck_mensagem_rapida_dono)
    ativo, ordem, criada_em, atualizada_em
)
```

- `ux_mensagem_rapida_apelido`: apelido único por tipo e dono, sem diferenciar
  maiúscula: é por ele que se escolhe na conversa.
- As variáveis (`{cliente}`, `{contato}`, `{saudacao}`) ficam no texto como
  escritas e são preenchidas **na tela**, ao inserir, com os dados da conversa
  aberta; nada disso passa pelo banco.
- Apagar é seguro: o que já foi enviado é texto na conversa, sem vínculo.

### Ligações do MicroSIP (059, Plano 5)

🔵 *"inicialmente o backup das ligações na VPS de uma forma bem inteligente"*.
Cada operador usa o MicroSIP (central Intelbras WideVoice); um agente no PC
(`movizap-ligacoes.ps1`) sobe o histórico e as gravações 2x por dia.

| Tabela / coluna | Para quê |
|---|---|
| `atendente.ramal` | o ramal da central (único) |
| `agente_ligacao` | a chave do agente de cada ramal (**só o hash**, `chave_sha256`), `ultimo_contato_em`, `ultimo_pc`, `ultima_versao`, `ultimo_erro`, `pendentes`, `revogado_em`. Gerar chave nova revoga a anterior do ramal. **Migração 060 (25/09, mTLS):** `cert_sha256` e `cert_validade` (o certificado do mesmo agente, conferido junto da chave na porta própria), `ultimo_ip` e `ultimo_aviso` (o que o alerta de PC mudo e de certificado vencendo já mostrou, para não repetir) |
| `ligacao` | uma linha por ligação do histórico, com ou sem gravação: `agente_id`, `atendente_id`, `ramal`, `call_id`, `numero_bruto`, `telefone_e164`, `sentido` (feita/recebida/perdida), `situacao`, `inicio`, `duracao_s`, `pc`, `recebida_em`. Única por `(ramal, call_id)` |
| `ligacao_gravacao` | as gravações de cada ligação: `ligacao_id`, `nome_original`, `arquivo_sha256` (único), `arquivo_bytes`, `caminho`, `inicio`, `recebida_em` |
| `alistamento_queimado` | **migração 063 (15/10)**: a janela de senha de alistamento já GASTA — `ramal`, `janela` (epoch/600), `usado_em`, `pc`, `ip`, `agente_id`, com `UNIQUE (ramal, janela)`. 🚨 A senha NUNCA é guardada: ela é derivada por HMAC de `MOVIZAP_LIGACOES_SENHA_SEGREDO` sobre (ramal, janela de 10 min), e é este `UNIQUE` que a faz servir **uma vez só** |
| `ligacao_exportacao` | **migração 063 (15/10)**: o rastro de cada CSV exportado da aba Ligações — `atendente_id`, `quando`, `filtros` (jsonb) e `linhas`. Não guarda o conteúdo exportado, só quem levou o quê e quando: exportar ligação é número de telefone e áudio de conversa saindo do sistema |

- **Uma ligação pode ter várias gravações:** quando a gravação recomeça, o
  MicroSIP abre outro arquivo (medido em 10/08 13:27 e 18/09 17:34). Por isso
  a gravação tem tabela própria, e não colunas em `ligacao`.
- **Índices da 063 (15/10), nascidos junto das consultas que os usam:**
  `ligacao (inicio DESC)` para o grid, `(atendente_id, inicio DESC)` e
  `(ramal, inicio DESC)` para os filtros, e a FK `(agente_id)`. O de
  `(telefone_e164, inicio DESC)` vem da 059 e é o que serve o modal da ficha.
  Índice sem consulta é palpite -- por isso não nasceram antes.
- **O arquivo mora em disco**, em `/home/claude/movizap_ligacoes/AAAA/MM/<sha256>.mp3`
  (0640), fora da pasta de mídia do WhatsApp, para entrar sozinho no backup
  noturno (`empacotar movizap_ligacoes`).
- **Idempotente pelo banco:** o agente reenvia sem duplicar. A resposta
  devolve o SHA-256 relido do disco, e o agente só marca como salvo quando ele
  bate com o do PC.
- **Agente de importação (15/10):** uma linha de `agente_ligacao` pode nascer
  **já revogada**, com `ultima_versao = 'import'` — é o dono que o import
  retroativo (`scripts/importar_ligacoes.py`) usa quando o ramal nunca teve
  agente. Ela existe para a ligação ter de quem ser, e **não** serve para
  enviar: a chave é aleatória e ninguém a vê. O import **nunca** revoga o
  agente vivo de um ramal.
- **Alerta:** `ligacoes.agentes_mudos()` lista quem está sem contato há mais
  de 24 h (ou nunca falou); `scripts/agentes_mudos.py` roda no gancho
  `SessionStart` do Claude Code dele e não imprime nada quando está tudo em dia.

### `mensagem.evento` — o log de ações da conversa (migração 064, 15/10)

🔵 *"log dentro da conversa interno apenas sobre ações de transfernecia,
inserir pessoas, etc, pode ser em Nota interna do Movizap"*.

| Campo | O quê |
|---|---|
| `mensagem.evento` | `text`, nulo em mensagem comum. Lista fechada no CHECK `ck_evento_conhecido`: `assumiu`, `entrou`, `convidou`, `saiu`, `removeu`, `devolveu`, `transferiu`, `encerrou`, `vinculou`, `desvinculou`, `mudou_tipo`, `bloqueou`, `desbloqueou` |

- 🚨 **É COLUNA, E NÃO UM `tipo` NOVO.** O CHECK `ck_nota_e_interna` amarra
  `tipo = 'nota'` a `direcao = 'interna'` **nos dois sentidos**: um
  `tipo = 'sistema'` interna seria recusado, e afrouxar esse CHECK abriria a
  porta para uma nota vazar como mensagem de saída. O evento **é** nota
  interna, com uma marca a mais — e `ck_evento_e_nota_interna` garante isso no
  banco, não na confiança do código.
- 🚨 **`autor = 'sistema'`**, nunca `'atendente'`: a frase foi escrita pelo
  sistema, em nome de quem agiu. Quem agiu vai em `atendente_id`.
- 🚨 **Evento não se edita nem se apaga.** A recusa mora em
  `conversas._minha_nota`, o único caminho de editar e apagar nota. Ela é
  obrigatória porque o `atendente_id` do evento é de quem agiu — sem a recusa
  explícita, essa pessoa passaria no teste "só quem escreveu pode editar".
- ⚠️ **Nada retroativo**, decisão declarada: transferência, encerramento e
  convite dariam para reconstituir, mas **vínculo e tipo não têm histórico**, e
  log pela metade com data inventada engana mais do que log que começa hoje.
- ⚠️ **Não conta como não lida**: só `direcao = 'entrada'` conta, e nota nunca
  contou.
- Índice parcial `ix_mensagem_evento (conversa_id, id) WHERE evento IS NOT NULL`,
  para quem quiser só o log de um atendimento.

🚨 **A armadilha que isto custou, medida em 15/10 com `faulthandler`:** gravar o
evento pedindo uma **conexão nova** dentro de um `with banco.cursor()` ainda
aberto **trava para sempre**. A `INSERT INTO mensagem` tem FK para `conversa` e
precisa de trava na linha da conversa, que a transação do chamador já segura:
uma sessão espera a outra, que espera a primeira, e o Postgres não vê deadlock
porque só há **um** esperando. Não é o pool (`max_size=8`, `timeout=10`: falta
de conexão daria erro em 10 s). Por isso `registrar_evento` aceita `cur`, e
quem chama de dentro de uma transação **tem de passar**. Com `cur`, um erro no
log abortaria a transação da ação inteira — daí o **SAVEPOINT**: falha de log
desfaz só o log.

### `nota_leitura` — "visto por" na nota interna (migração 065, 15/10)

🔵 *"confirmação de leitura das notas dentro da conversa ... um icone que ao
clicar mostra que ja leu aquela nota, junto ao carimbo de data e hora, bem
pequeno mesmo"*.

| Tabela | O quê |
|---|---|
| `nota_leitura` | `mensagem_id`, `atendente_id`, `visto_em`. PK `(mensagem_id, atendente_id)`, que é o que faz o carimbo ser o da PRIMEIRA vez |

- 🚨 **O rótulo é "visto por", nunca "leu".** O sistema sabe que a nota esteve
  na tela de alguém; não sabe que a pessoa leu. Dizer "leu" vira prova de algo
  que não se mediu.
- 🚨 **Marca quando a nota APARECE na tela** (`IntersectionObserver`), não
  quando a conversa abre: abrir uma conversa de 200 mensagens e não rolar até o
  fim não é ver a nota de lá atrás.
- 🚨 **Nota anterior a `conversas.LEITURA_DE_NOTA_DESDE` (15/10) não é
  carimbada**, e a consulta devolve `leitura_rastreada = False` por nota. É o
  que permite à tela dizer *"sem registro"* em vez de *"ninguém viu"* — que
  seria uma afirmação falsa sobre o passado.
- ⚠️ A conversa é **coletiva** e não tinha nenhuma noção de leitura por
  mensagem. Quem tem marcador é o chat interno, e lá é marca d'água por sala
  (`chat_membro.lido_ate`), não por mensagem.
- Índice `ix_nota_leitura_atendente (atendente_id, visto_em DESC)` para o
  caminho oposto ("o que esta pessoa já viu"), que ainda não tem tela.

🚨 **O EVENTO NÃO É "A ÚLTIMA MENSAGEM" DA CONVERSA**, e isso vale para duas
consultas de `listar()`: a prévia da lista (`u.conteudo`) e a regra de **sem
dono** (02/10: "a última mensagem tem de ser de `entrada`"). Sem
`m.evento IS NULL` nas duas, convidar alguém numa conversa órfã a **tirava da
fila**, e toda conversa passaria a mostrar "assumiu a conversa" no lugar da
última fala do cliente. Achado pela suíte inteira, não por leitura.
⚠️ A exclusão é do **evento**, não da nota: nota é coisa que uma pessoa
escreveu, e vê-la na prévia informa.

---

### Agendamento de serviço e orçamento (migração 069, 21/10)

🔵 Decisão 7 dele (19/10): **o MoviZap é o dono do agendamento**; a escrita no
Harmonit é 2º passo. 🚨 Medido antes de escrever: **a OS não tem campo de data
agendada em lugar nenhum** — `data_previsao` é a previsão do Harmonit, e o
resto é texto livre no checklist. Por isso o compromisso tem casa própria.

**`agendamento`** — o compromisso.

| Coluna | O que é |
|---|---|
| `conversa_id` | a conversa de **origem** (a do técnico) |
| `tecnico_contato_id` | o técnico, `contato(id)` |
| `cliente_harmonit_id` | 🚨 **text**, e não int: é o tipo de `cliente.harmonit_id` deste lado, e é a **chave da ponte** com a OS do FPSL |
| `cliente_nome` | retrato, para a tela não depender do Harmonit no ar |
| `inicio` / `fim` | `timestamptz` |
| `endereco` | 🔵 decisão 11: o operador **digita**, sugerido com o último usado |
| `responsavel_cliente` | quem acompanha o técnico; nulo até o cliente confirmar |
| `estado` | CHECK: `rascunho`, `aguardando`, `confirmado`, `cancelado` |
| `orcamento_id` | o documento que foi junto, se houve |
| `criado_por`, `criado_em`, `confirmado_em`, `cancelado_em`, `motivo_cancelamento` | o rastro |

**`agendamento_os`** — N OS por compromisso: `agendamento_id`, `numero_os`,
`placa`, PK composta, cascata. ⚠️ A placa vem do `oficinas_json` da OS e é
**nula com frequência** (só 236 das 572 OS têm oficina) — a tela diz "sem
placa registrada" em vez de desenhar vazio.

🚨 **"Uma OS não entra em dois compromissos ativos" NÃO É CONSTRAINT.** A
tabela não carrega estado, e duplicar o estado nas duas criaria duas versões
do mesmo fato. A regra mora em `agendamento.criar`, com `FOR UPDATE` na mesma
transação da inserção, e tem teste. ⚠️ E não dá para usar `DISTINCT` junto do
`FOR UPDATE`: o Postgres recusa — achado por teste, não por leitura.

**`orcamento`** — `numero` (**UNIQUE**), `tecnico_contato_id`, `conversa_id`,
`total_centavos`, `midia_id` (o PDF, reaproveitando a mídia da conversa),
`criado_por`, `criado_em`.

**`orcamento_item`** — `orcamento_id`, `ordem`, `servico`,
`preco_unit_centavos`, `quantidade` (numeric), `unidade` (CHECK `un`/`km`),
`valor_centavos`.

🚨 **Dinheiro em centavos, inteiro**, do começo ao fim: documento com valor não
usa float. 🔵 Decisão 13 dele: deslocamento é **por km** — a `unidade` é dado
da linha, e é ela que faz o PDF imprimir "77,7 km" em vez de "77.7 un".

**A numeração** mora no `config`, chave `orcamento_proximo_numero`, com aba
própria no `/config` (`CFG_13.1`, só owner). 🚨 **O número só se gasta quando o
PDF existe** — reservar antes deixaria buraco na sequência toda vez que alguém
fechasse o modal.

### O agendamento no Harmonit, e as OS do orçamento (migração 070, 21/10)

🔵 *"pode deixar ligado e seguir com o plano"*, depois do relatório do teste na
OS 16991. É o **2º passo** da decisão 7 dele.

**`agendamento`** ganhou o rastro da escrita: `harmonit_agendamento_id` (o
`agendamentoId` do lado de lá), `harmonit_em` (quando deu certo) e
`harmonit_erro` (a recusa, em texto cru — a rota é crua, e a única forma de
descobrir um motivo novo é lê-lo).

🚨 **A escrita nunca derruba o compromisso.** O MoviZap é o dono: se o Harmonit
recusar, o agendamento continua valendo aqui e o motivo fica gravado na linha.
Falha silenciosa viraria "achei que tinha ido".

**O que o teste na OS 16991 mediu, e desenha tudo isto:**

| Medido | Consequência |
|---|---|
| `id: 0` **cria** (nasceu o agendamento 944767, conferido relendo a OS) | é assim que a rota é chamada |
| com o `id` de um compromisso existente, **recusa** (`TecnicoJaAgendado`) | não se reagenda por cima |
| `agendado` continua `false` depois de agendar | o campo **não** quer dizer "tem compromisso" |
| a OS traz os técnicos na chave **`tecnico`**, no singular | chutar o nome fez o primeiro script relatar "sem técnico" numa OS com três |
| o corpo da OS **não traz `clienteId`** | ele sai da `os_historico` |

⚠️ **O elo técnico ↔ usuário do Harmonit é o NOME**, e não existe tabela
ligando os dois: o MoviZap conhece o técnico como contato de WhatsApp. Por isso
a ponte **recusa e lista os nomes** quando não casa, em vez de escolher
sozinha — agendar no técnico errado é pior que não agendar.

**`orcamento.ordens_os`** (`bigint[]`) — os números de OS impressos no
documento. 🚨 Não estavam sendo guardados: o PDF imprime "Ordem(ns) de
serviço(s)", e sem a coluna um **reenvio produziria papel diferente com o mesmo
número**. Achado no primeiro uso real dele, em 21/10.

**O interruptor** é a chave `agendamento_escreve_harmonit` no `config`, com
caixa na `CFG_7.1` (Geral) — e **nasceu ligada por decisão dele**, que é a
exceção, não a régua desta casa.

### O contato técnico ligado ao cadastro do Harmonit (migração 071, 21/10)

🔵 Pedido dele: *"podemos pensar em um vínculo de dados técnicos dentro do
cadastro do tipo 'técnico', assim já traz sugerido pelo número dele... para
técnicos novos ou ainda sem o tipo 'técnico' no nome"*.

**`contato`** ganhou quatro colunas — mesmo desenho do `cliente.harmonit_id`,
que já era o precedente da casa:

| Coluna | O que é |
|---|---|
| `harmonit_tecnico_id` | o `tecnico_id` do cadastro (tabela `tecnicos` do FPSL, sincronizada 1×/dia por `sync_tecnicos`) |
| `harmonit_tecnico_nome` | retrato do nome — 🚨 **é o que o orçamento imprime** |
| `harmonit_vinculo_origem` | CHECK `automatico` / `manual` |
| `harmonit_vinculo_em` | quando foi gravado |

🚨 **A chave é o TELEFONE**, porque o e-mail do técnico no Harmonit **é o
telefone dele** (`Franck` → `997394026@movisat.com.br`, contato
`+5519997394026`). 🔵 Decisão dele: tenta **9 dígitos, depois 8** (número
antigo sem o nono), e **só vincula com candidato único**. Medido na primeira
passada: **186 vínculos** (179 pelos nove + 7 pelos oito), zero ambíguos, 117
contatos de técnico sem cadastro correspondente.

🚨 **`manual` nunca é tocado pela varredura.** É o que sustenta a exceção dele
(o `6168` aponta para o Iago, `tecnico_id` 7493): pelo telefone aquele número
jamais casaria, porque `iago@movisat.com.br` não é numérico e está marcado
como **usuário do sistema**, não técnico de campo.

🚨 **A varredura nunca muda o `relacao` do contato.** Trocar para `tecnico`
esconde empresas na ficha e muda regra de negócio — continua sendo clique de
gente. O contato que casa e ainda não é do tipo vira **sugestão**, não ação.

⚠️ **Na escrita no Harmonit, o vínculo gravado ganha do telefone**, porque é
identidade e não semelhança: o `usuarioId` de cada técnico da OS **é o
`tecnico_id` do cadastro** (medido: Iago 7493, Franck 14262, iguais dos dois
lados).

**O interruptor** é `tecnico_vinculo_ligado` no `config` e **nasceu ligado por
decisão dele** — exceção consciente à régua da casa, porque a varredura só
grava o que a trava do agendamento já calcula ao vivo.

## Migração 072 — `agendamento_os.tipo_nome`, o tipo da OS no compromisso

🔵 Ponta 1 do plano de Agendamentos (§7.4): o cabeçalho da mensagem imprimia
a palavra `(SERVIÇO)` literal, onde o plano pede o **tipo da OS**. 🚨 É a
única das quatro pontas que **sai para o cliente**.

| Coluna | Tipo | Nulo? |
|---|---|---|
| `agendamento_os.tipo_nome` | `text` | **sim**, e é o caso comum |

🚨 **RETRATO, COMO A PLACA DO LADO.** O nome do tipo é gravado no momento do
agendamento, não consultado quando a mensagem é montada. Três razões, todas
medidas: a mensagem sai de uma tela que o operador está olhando; a
`agendamento_os` já guarda a placa pelo mesmo motivo desde a 069; e a OS pode
ser reclassificada depois — a mensagem que saiu falava do tipo de então.

🚨 **NULO É RESPOSTA, NÃO FALHA.** A lista de tipos do Harmonit
(`/TipoOrdemServico/ObterListaTipoOrdemServico`) tem **5 tipos**, que cobrem
**374 das 547** OS não excluídas. As outras **173** estão em **nove** ids fora
da lista (57, 76, 73, 72, 55, 77, 75, 576, 814) — tipos que o Harmonit removeu
ou renomeou; o FPSL já registrava o caso do 55 desde 14/08
(`os_router._resolver_cabecalho_por_nome`: *"id fixo em código apodrece em
silêncio"*). Medido em 21/10, antes de escrever.

⚠️ Para essas, o cabeçalho **omite o segmento inteiro** — parênteses e barra
incluídos — em vez de imprimir número ou rótulo inventado. `(tipo 57)` não diz
nada ao cliente.

**A fonte do nome é do lado do FPSL**, na tabela `tipos_os` (`tipo_id`, `nome`,
`codigo`, `atualizado_em`), preenchida pela rotina **`sync_tipos_os`**, 1×/dia,
e devolvida pela ponte em `tipo_nome`. ⚠️ Ela é **dicionário, não autoridade**
sobre que tipos existem: quem pergunta por um tipo fora dela recebe ausência,
e nunca apaga o que já sabia quando a rota do Harmonit responde vazio.

## Migração 073 — o endereço do compromisso em campos separados

🔵 Pedido dele, 21/10, depois de exercitar o fluxo no navegador: *"a tela 3
precisa ter o campo com os dados de endereço separados, para enviar sem erros
no harmonit... sem os campos, podem inserir de qqer jeito"*.

| Coluna | Tipo | Observação |
|---|---|---|
| `agendamento.cep` | `varchar(8)` | 8 dígitos, **sem máscara** |
| `agendamento.logradouro` | `varchar(80)` | a rua — no Harmonit chama-se `endereco` |
| `agendamento.numero` | `varchar(10)` | |
| `agendamento.bairro` | `varchar(60)` | |
| `agendamento.cidade` | `varchar(50)` | no Harmonit vem de `cidade`; no ViaCEP, de `localidade` |
| `agendamento.uf` | `varchar(2)` | |
| `agendamento.complemento` | `varchar(40)` | |
| `agendamento.endereco_os_em` | `timestamptz` | quando o endereço foi gravado na OS |
| `agendamento.endereco_os_erro` | `text` | por que não foi |

🚨 **OS CAMPOS SÃO OS DO HARMONIT, UM A UM.** A OS guarda o endereço nesses
sete campos (medido na OS 16991 em 21/10), e a rota de escrita espera esses
mesmos nomes. Inventar um formato aqui obrigaria uma tradução no caminho, e
tradução é onde o endereço se perde. ⚠️ A **única** diferença de nome é
`logradouro`: `agendamento.endereco` já existia desde a 069 e é a **linha
montada** que sai na mensagem do cliente.

🚨 **`endereco` CONTINUA SENDO A FONTE DA MENSAGEM**, e passou a ser *montada*
dos campos quando eles existem. Trocar a mensagem para ler os sete campos faria
os compromissos criados antes desta migração saírem sem endereço — e eles são o
único histórico que existe.

⚠️ **Nada é obrigatório:** em 30 OS amostradas no Harmonit em 21/10, **7 têm os
oito campos em branco**. Exigir endereço estruturado impediria de agendar
justamente onde o cadastro está pior.

🚨 **Os tamanhos são escolha nossa, e o teto do Harmonit não é documentado.** O
que se mediu nas 30 OS é o **piso** — logradouro 41, bairro 54, cidade 21,
número 4, complemento 9 —, e piso prova que cabe, não prova o limite.

### A escrita do endereço na OS, e por que ela relê 39 campos

🚨 **NÃO EXISTE "ATUALIZAR SÓ O ENDEREÇO" NO HARMONIT.** A única rota é
`POST /OrdemServico/SalvarOrdemServico`, que a doc deles chama de *"criar/
atualizar OS completa"*: manda-se a OS inteira, e o que não for mandado se
perde. Por isso a rota `POST /api/os/endereco` do FPSL **lê a OS, remonta campo
a campo, grava, relê e compara** — e devolve `fora_do_endereco` quando tocou
algo que não devia.

🚨 **OS NOMES DE LEITURA E DE ESCRITA NÃO BATEM**, e é a armadilha central:

| leitura | escrita |
|---|---|
| `tipo` | `tipoId` |
| `localServico` | `localServicoId` |
| `prioridade` | `prioridadeId` |
| `problema` | `problemaId` |
| `produtoId` | `produtoServicoId` |
| `descricao` | `descricaoDetalhada` |
| `dataPrevisao` (`dd/mm/aaaa HH:MM:SS`) | `dataPrevisaoEntrega` (ISO) |
| `parceiro` | `clienteId` |

⚠️ **`parceiro` É O `clienteId`** (998063 na 16991, igual ao `cliente_id` da
`os_historico`) — a nossa própria nota dizia que a OS não traz o cliente.
Medido em **uma** OS, então a `os_historico` segue como fonte e o `parceiro` é
o reforço.

🚨 **O ENSAIO A SECO E A ESCRITA NO-OP SALVARAM O REMAPEAMENTO.** Com
`conferir: true` a rota monta tudo e não grava; depois, gravar o **mesmo**
endereço de volta provou o mapa. E pegou um erro meu: `solucaoTecnica` saía
como `""` onde a OS tinha `null`, por causa de um `or ""`. A comparação acusou,
`ok` voltou `False`, e a causa foi corrigida. Sem o no-op, isso teria ido para
produção invisível.

## Migração 074 — os formulários próprios, e eles são DADO

🔵 22/10, decisão dele: *"nenhuma possibilidade irá usar o bitrix, esse
projeto é movizap"*. Cinco tabelas novas.

**`formulario`** — um por formulário: `codigo`, `slug` (o que aparece em
`/f/<slug>`), `titulo`, `setor`, `botao`, `descricao`, `ativo`, `ordem`,
`gera_os`, `problema_id`, `tipo_os_id`, `prioridade_id`, `bitrix_id`,
`bitrix_sec`, `criado_em`, `atualizado_em`.
🚨 `ativo` **nasce falso**: enquanto for, o link público responde 404. Quem
liga é o owner, pela tela.
🚨 `bitrix_id`/`bitrix_sec` são **procedência**, não destino — dizem de onde a
definição foi lida em 22/10 (`dados/formularios_bitrix/mapa_bruto.json`).
Nada neste projeto escreve no Bitrix.

**`formulario_campo`** — `formulario_id`, `nome` (o nome de ORIGEM, ilegível
de propósito: `DEAL_UF_CRM_DEAL_1649449139431` é campo personalizado do
Bitrix, e o número é o timestamp em que alguém o criou), **`nosso_nome`** (o
nome legível, derivado do rótulo e único por formulário), `rotulo`, `tipo`,
`obrigatorio`, `multiplo`, `visivel`, `ordem`, `opcoes` (jsonb, com o `value`
numérico do Bitrix — é ele que as regras comparam), `ajuda`.
O CHECK de `tipo` tem os **15 tipos** medidos nos 239 campos: tipo
desconhecido para na CARGA, não na tela do cliente.

**`formulario_regra`** — `formulario_id`, `ordem`, `logica`, `lista` (jsonb,
a estrutura do Bitrix como veio: `condition` → `action`, `show`/`hide`).
🚨 Fica em UMA forma porque os DOIS lados a avaliam: o servidor
(`movizap/formularios.py:visiveis`, que é a autoridade) e o navegador
(`frontend/src/util/regras_formulario.js`). As duas suítes leem o mesmo
arquivo de casos, `tests/casos_regras_formulario.json`.

**`formulario_solicitacao`** — `formulario_id`, `criada_em`, `ip`, `valores`
(jsonb, pela chave de ORIGEM), `estado` (`nova`/`em_andamento`/`concluida`),
`lida_por`, `lida_em`, e já anuláveis para a Etapa 2/3: `conversa_id`,
`contato_id`, `cliente_id`, `os_id`, `numero_ordem`.
🚨 **É RETRATO**: não se reescreve quando a definição muda, e campo escondido
por regra **não entra, nem vazio**.
⚠️ A FK para `formulario` **não** é `ON DELETE CASCADE`, de propósito: apagar
um formulário com solicitação recebida é recusado pelo banco. Campo e regra,
que são definição, saem em cascata.

**`formulario_arquivo`** — `solicitacao_id`, `campo`, `nome_original`,
`caminho`, `bytes`, `mime`, `criado_em`.
🚨 O arquivo fica **fora do projeto**, em
`/home/claude/movizap_formularios_anexos`, como o anexo de e-mail: dentro, ele
entraria no git e no `dist` — e o `dist` é servido. `nome_original` é texto
para ler, **nunca** caminho.

## Migração 075 — a que painel cada formulário pertence

🔵 O mapa é dele (plano, §2.1): **Operação** (Suporte · Demonstração · Teste
gratuito · Credenciamento), **Pós venda** (NPS · CES), **Contratual** (Ficha
cadastral · Aditivo · Substituição · Rescisão), **Financeiro** (Financeiras ·
Pagamento de técnicos · Administrativas · Fornecedores) e **sem painel**
(Contato).

`formulario.painel` — `varchar(20)`, **anulável**, com CHECK em
`operacao | pos_venda | contratual | financeiro`.
🚨 **É coluna, não lista no código**, pelo mesmo motivo que a definição do
formulário é dado: mover "Administrativas" de Financeiro para Contratual não
pode exigir deploy.
🚨 **O mapa vive em UM lugar** — a tabela `NOSSOS` do
`scripts/carregar_formularios.py` — e é **reescrito a cada carga**
(`painel = EXCLUDED.painel`). ⚠️ `ativo` **não** entra nessa lista: recarregar
não publica formulário nenhum.
⚠️ **Nulo é um valor legítimo**, e tem nome: *"SEM PAINEL — Contato"*.

## Migração 076 — a situação da OS, guardada na solicitação

Para o painel da Operação (opção A) ter colunas, a solicitação precisa saber
em que situação está a OS dela.

`formulario_solicitacao.situacao_id` · `situacao_em` · `situacao_erro`.
🚨 **É CACHE, e o nome diz:** a verdade da situação é do Harmonit; aqui fica a
última lida, **com a hora**. Sem a hora, a tela afirmaria a situação sem prazo.
🚨 **Três estados distinguíveis, não dois:** `os_id` nulo (não virou OS) ·
`os_id` com `situacao_id` nulo (tem OS e **nunca foi lida**) ·
`situacao_id = 0` (lida, e o Harmonit respondeu zero — **127 das 574 OS** estão
assim, medido em 22/10). Os três caem na mesma coluna da tela e continuam
separados no banco.
⚠️ `situacao_erro` segue a régua do `agendamento.endereco_os_erro` (073): nulo
com `situacao_em` nulo = não tentou; nulo com data = deu certo.

## Migração 079 — o formato novo do formulário público

🔵 Pedido dele, 29/10, sobre o Suporte: *"ajuste ele no novo formato 'etapas,
logo, cor, placas, etc'"*. O desenho é o de 23/10 (blocos 1, 3, 5 e 6 do
plano, em `Desktop\Formularios_Movisat_Design.md`).

`formulario.formato` — `varchar(10)`, **não anulável**, CHECK em
`classico | novo`, padrão **`classico`**.
🚨 **Nasce `classico` nos 15**, e ligar é decisão dele: o formato novo muda a
tela que a internet vê, e ele valida formulário por formulário no navegador.
Hoje só o **SUPORTE** está em `novo`.

`formulario.etapas` — `jsonb`, **anulável**:
`[{"titulo": ..., "campos": [nosso_nome, ...]}]`. Nulo = rolo único, que é o
caso dos outros 14.
🚨 **Os campos são citados pelo `nosso_nome`**, não pelo nome do Bitrix — é o
único dos dois que uma pessoa revisa. Quem traduz para o nome de origem é a
rota pública (`main._etapas_publicas`), porque `nosso_nome` **não sai** para a
internet.
🚨 **A carga recusa etapa errada dos dois lados:** campo citado que não existe
**e** pergunta que ficou fora de toda etapa. O segundo é o perigoso — a
pergunta simplesmente não apareceria, e o formulário seguiria aceitando envio
com uma pergunta a menos.
⚠️ Onde o formulário tiver `page` (15 delas nos outros), **é ela que manda**: o
Suporte não tem nenhuma, e por isso as 4 etapas dele são agrupamento nosso.

`formulario_campo.validacao` — `varchar(16)`, **anulável**, CHECK em
`cpf | cnpj | placa | telefone | email | cep`.
🚨 **Existe porque o tipo do Bitrix não diz o bastante:** 30 dos 239 campos são
`double` e são CNPJ, CPF, RG e quantidade. Sem esta coluna não há máscara nem
dígito verificador.
🚨 **NÃO é barreira.** Quem recusa o envio é `formularios.validar`; esta coluna
diz à tela qual máscara pôr e qual frase mostrar.
🚨 **O QUE VAI GRAVADO É A FORMA CANÔNICA — sem pontuação, em maiúscula — e
a `validacao` manda mais que o `tipo`.** O campo CNPJ é `double` no Bitrix, e a
regra do `double` é `float()`: ela recusava **`WQ0P6GLD000108`**, que é um CNPJ
**válido** da nossa própria base (Pastelaria Velasco).
🚨 **O CNPJ É ALFANUMÉRICO desde 2026:** 12 posições com letra ou dígito + 2
dígitos de verificação, e o valor de cada caractere na conta do DV é o **ASCII
menos 48** (`0`–`9` dão o próprio número, `A` dá 17) — então o CNPJ antigo é um
caso particular da mesma conta.
🔵 **Decisão dele, 29/10:** *"deve permitir todos os formatos para CNPJ bem como
alfanuméricos"* e *"podem colar somente numero ou . e - e / tbm"*. Colar
`WQ0P6GLD000108`, `WQ.0P6.GLD/0001-08` ou só dígitos dá o mesmo valor gravado.
⚠️ **`placa` NÃO é canonizada**, de propósito: o campo do Suporte é *"Veículo e
Placa — um por linha"*, e `SAVEIRO ABC1234` é resposta certa. Lá a regra é só
mensagem na tela, que **procura** a placa dentro do texto.
⚠️ O servidor garante o **formato** (quantos caracteres); o **dígito
verificador** é frase na tela. Mudar isso é régua, e régua é decisão dele.
As provas estão em `tests/teste_formato_novo.py`.
🚨 **As três são reescritas a cada carga** (como `painel`, ao contrário de
`ativo`): o mapa vive no `scripts/carregar_formularios.py`.
⚠️ **Ninguém escreve nestas colunas ainda** — a leitura e a escrita de
`situacaoId` são da volta seguinte, e dependem de decisão dele.

## Migração 077 — o KM do técnico: memória, retrato e cache da rota

🔵 *"na parte de agendamento do tecnico: proponha no deslocamento uma
calculadora km técnico (...) o endereço do tecnico sempre fica preenchido
conforme o ultimo (...) se for alterado, permanece alterado"*, e *"o km é o
calculo a ser feito (...) Hoje é feita na mão via 'rotas' do google"*.

🚨 **São três coisas porque têm TRÊS TEMPOS DE VIDA diferentes.**

**`tecnico_origem`** (tabela nova) — a **memória**, e vale *agora*. Uma linha
por técnico (`tecnico_contato_id` é a PK, referência a `contato`), com os
**mesmos sete campos e os mesmos limites** do endereço de destino da 073 —
duas réguas para o mesmo endereço é uma delas mentindo. **Sobrescrita**, que é
a frase dele ao pé da letra: *"se for alterado, permanece alterado"*.
⚠️ **Não é cadastro:** ninguém digita isto num formulário — a linha é escrita
pelo **uso** da calculadora. Cadastro é coisa que alguém tem de manter, e o
projeto já tem **117 contatos de técnico sem cadastro no Harmonit** para
provar o que acontece quando ninguém mantém.

**`agendamento.origem_endereco` e `agendamento.km`** — o **retrato**, e valem
*naquele dia*. Se o técnico mudar de endereço, a memória muda e o compromisso
antigo continua dizendo de onde se cobrou. Mesmo desenho do `tipo_nome` da
072 (*"retrato do momento do agendamento"*).
⚠️ Aqui é a **linha de texto**, não sete colunas: a origem estruturada vive na
memória, e sete colunas aqui seriam a **terceira** cópia do mesmo endereço.
⚠️ `km numeric(12,3)` igual ao `orcamento_item.quantidade` — o km vai para lá
como quantidade, e arredondar diferente nos dois lados faria o compromisso e o
orçamento discordarem do mesmo deslocamento.

**`rota_cache`** (tabela nova) — cache de **consulta paga**, e vale por um
prazo. Chave: o **par de endereços normalizados** (minúsculas, sem acento, sem
pontuação), porque "Rua X, 123" e "rua x 123" são a mesma consulta e pagar
duas vezes por isso é desperdício que ninguém vê na fatura.

🚨 **E o cache em TABELA contraria um princípio escrito da casa, então a
objeção se responde aqui.** O `movizap/cep.py` diz: *"Não vira tabela porque
cache que sobrevive a deploy é cache que guarda erro para sempre"*. Vale para o
CEP, que é grátis. Aqui muda o que importa: cada consulta **custa**, e o mesmo
técnico vai ao mesmo cliente muitas vezes — cache de processo pagaria de novo a
cada deploy. E as duas condições que respondem ao medo do `cep.py`: **só
resultado bom entra** (falha nunca é gravada) e **`consultado_em` fica à
vista**, com prazo de 90 dias aplicado por quem lê — a mesma razão pela qual a
076 guardou a situação **com a hora**.

⚠️ **Ninguém escreve nestas três ainda.** A calculadora e a rota são da mesma
volta; as colunas nascem agora porque acrescentá-las depois obrigaria a mexer
em quem lê. E o cache **continua vazio enquanto não houver chave da API** —
sem chave, `rotas.disponivel()` é `False` e a tela cai no campo manual dizendo
por quê.

## Migração 078 — onde o agente procura a gravação, e o canal de volta

🔵 *"veja se da para atualizar do lado de ca para os computadores o local de
coleta das ligações gravadas"*, e o desenho dele: *"que permita inserir mais
endereços por aqui ou buscar pelo nome da pasta, pedindo permissão ao
instalar"*.

🚨 **O ponto de partida, medido em 26/10:** a pasta era **100% derivada** do
`MicroSIP.ini` e, com `recordingPath` vazio, o agente **chutava**
`Desktop\Recordings` — palpite que o próprio código marcava como *"HIPOTESE a
medir no PC da Claudia"*, porque **com OneDrive a Área de Trabalho muda de
lugar**. E **não existia canal VPS → agente**: o batimento devolvia
`{ok, ramal, servidor_em}` e o agente **descartava a resposta**.

### Três colunas de diagnóstico

`agente_ligacao.pasta` · `pasta_origem` · `auto_gravacao`.

**`pasta`** é o caminho que o agente realmente observa. 🚨 Sem ele, o aviso
*"pasta de gravacoes ainda nao existe"* não dizia **qual** pasta — e era por
isso que ninguém via, pelo painel, que o caminho calculado estava errado. Aviso
que não diz onde procurou não é diagnóstico.

**`pasta_origem`** é **COMO** a pasta foi decidida, com `CHECK` de lista
fechada: `vps` · `escolhida` · `ini` · `relativa` · `busca` · `palpite`. ⚠️
Fechada porque a tela explica cada caso em texto — frase livre viraria seis
variações do mesmo recado. `palpite` é o comportamento de até o agente 0.6 e
**sai no 0.7**.

**`auto_gravacao`** é a gravação automática do MicroSIP, dita pelo PC. 🚨 Até
aqui, *"REC ligado"* era **deduzido da ausência** de um aviso de texto —
dedução que inverte se a frase do agente mudar, e que "desliga" o REC sozinho se
chegar aviso novo sobre outra coisa. ⚠️ **Nulo é o terceiro estado:** em quem
**já falou**, significa **agente velho**, não "desligado" — e aí vale a dedução
de antes, que é o melhor que existe para ele.

### Uma coluna de instrução

**`pastas_extra text[]`** — os caminhos que a VPS manda o agente tentar, em
ordem. Vazio = **não interfiro**, que é o estado de todos os 7 PCs hoje.

🚨 **É INSTRUÇÃO QUE SAI DAQUI E VIRA LEITURA DE DISCO ALHEIO.** O que impede
estrago mora **no PC** — caminho só dentro do perfil do usuário ou de uma raiz
de OneDrive, unidade de rede recusada, travessia (`..`) recusada, e só
`.mp3`/`.wav` sobem. É o **oposto** do padrão da casa (*"quem barra é o
backend"*), e tem de ser: o backend do risco, neste caso, é o agente. Um agente
que confia na VPS para dizer o que é seguro é um agente que obedece a VPS
invadida.

⚠️ E a escrita é **só do owner** (`PUT /api/ligacoes/agentes/{id}/pastas`),
embora a aba `LIG_1.1` seja `atendimento`: *"todo atendente vê a aba"* não pode
virar *"todo atendente aponta o agente do colega para onde quiser"*.

### ⚠️ Nada disto vale nos PCs antes do agente 0.7

Os 7 rodam o `0.4`, e o agente **não se atualiza sozinho**. As colunas nascem
agora porque o lado da VPS (rota, tela, teste) é o que dá para fazer sem tocar
em máquina nenhuma — e porque acrescentá-las depois obrigaria a mexer em quem
lê. Em 26/10 as três de diagnóstico estão **nulas nos 7**, e `pastas_extra`
vazio em todos.

## Migração 080 — os ajustes NOSSOS em cima da definição do Bitrix

🔵 Pedidos dele, 29/10, no formulário de Suporte: uma caixa só para o nome · o
modelo esmaecido no telefone · as opções novas de *Tipo de solicitação* · sai o
*Assunto* · *Detalhe a ocorrência* mais alto · as placas ativas no campo de
veículo.

🚨 **POR QUE ISTO É COLUNA, E NÃO UMA EDIÇÃO NO BANCO:** `gravar_definicao`
**apaga e reescreve** campos e regras a cada carga, a partir do
`dados/formularios_bitrix/mapa_bruto.json`. Opção editada à mão no banco
funciona hoje e **desaparece na próxima carga, sem erro e sem aviso**. O ajuste
vive na tabela `AJUSTES` do `scripts/carregar_formularios.py` e é reaplicado
toda vez.

`formulario_campo.fantasma` — `varchar(60)`, anulável. O modelo de
preenchimento esmaecido **dentro** do campo (`placeholder`). 🚨 É modelo, não
valor: não é enviado e some ao digitar.

`formulario_campo.linhas` — `smallint`, anulável, CHECK entre 2 e 20. Altura em
linhas. ⚠️ *Detalhe a ocorrência* é `string` no Bitrix — sem isto seria **uma
linha só**, o que diz a quem preenche *"escreva pouco"*.

`formulario_campo.fonte` — `varchar(20)`, anulável, CHECK em `weso_placas`. De
onde a tela puxa **sugestão** para o campo.
🚨 **É A REGRA, NÃO SUGESTÃO.** 🔵 Dele, 29/10: *"só é possível abrir chamados
para placas ativas na weso. o match é basicamente de 100% mesmo. essa é a
regra"*. Placa informada é conferida contra a WESO na rota de envio, e placa sem
rastreador ativo é **recusada**.
⚠️ **O botão *"Meu veículo não está na lista"* continua**, com outro papel: a
placa que está ativa na WESO mas **não aparece na lista do cliente** — as **30**
(medido em 29/10) que a WESO tem e o Harmonit não, e que por isso não têm
`clienteId` para cruzar.
🚨 **A conta certa do casamento, medida em 29/10 normalizando os dois lados:**
das 1.998 linhas da WESO, **50 não são placa** (a coluna tem chassi e número de
série) e **30 são placa que o Harmonit não tem** — entre as que *são* placa,
**1.918 de 1.948 = 98,5%**. Os 80 restantes são dado sujo de um lado, não
cliente de fora. (A conta anterior, de 95%, não separava isso.)

⚠️ **TIRAR CAMPO NÃO PRECISOU DE COLUNA:** o campo simplesmente não é inserido
(`fora`, na tabela de ajustes). Trocar rótulo e opção também não — `rotulo` e
`opcoes` já existiam.
🚨 **E o `nosso_nome` continua saindo do rótulo ORIGINAL.** Ele é *derivado* do
rótulo: aplicar o rótulo novo antes do cálculo renomearia o campo
(`primeiro-nome` → `nome-completo`) e as tabelas `ETAPAS` e `VALIDACOES`
passariam a citar campo inexistente. Tem teste próprio.

## Migração 081 — o rastro da regra da placa

🔵 **Regra dele, 29/10:** *"só é possível abrir chamados para placas ativas na
weso. o match é basicamente de 100% mesmo. essa é a regra"*. A regra é cobrada
na rota de envio: placa informada que não está ativa na WESO é **recusada**.

`formulario_solicitacao.placas_conferidas` — `boolean`, anulável.

🚨 **A conferência depende de outro serviço** (a ponte do FPSL, que é quem tem a
base da WESO), e **indisponibilidade nossa não pode barrar o chamado do
cliente**. Quando a ponte não responde, o envio **passa** — e é esta coluna que
registra que passou sem conferir, para quem atende saber.

⚠️ **Os três valores têm significado diferente:**
- `true` — as placas foram conferidas e estão ativas;
- `false` — **não deu para conferir** (ponte fora do ar), e **não** "placa
  inativa": placa inativa nunca é gravada, porque a rota recusa antes;
- `NULO` — a solicitação não informou placa, ou o formulário não tem campo de
  placa.

## Migração 082 — a OS do chamado

🔵 **Duas decisões dele, de 29/10, que juntas obrigam uma tabela:**
- **D4** — *"todo chamado de suporte abrirá uma OS"*: automático no envio, não
  por botão (o que **inverteu** a decisão 3.6 de 23/10);
- **D3** — **uma OS por placa**, e não uma por envio (o que inverteu a 3.5).

`solicitacao_os` — tabela nova. Cada linha é **um par solicitação ↔ placa**, e
a OS de análise que o par gerou no Harmonit.

| coluna | tipo | o que é |
|---|---|---|
| `solicitacao_id` | `integer NOT NULL` | FK para `formulario_solicitacao`, `ON DELETE CASCADE` |
| `placa` | `varchar(10)` | a placa do chamado, na forma canônica. **Nula** = o chamado não informou nenhuma |
| `criada_em` | `timestamptz` | quando a linha nasceu — **não** quando a OS nasceu |
| `os_id` | `integer` | o `id` da OS no Harmonit. Nulo até a escrita voltar |
| `numero_ordem` | `integer` | o `numeroOrdem` da OS |
| `erro` | `text` | por que a OS não nasceu, nas palavras de quem recusou |
| `tentativas` | `integer NOT NULL DEFAULT 0` | quantas vezes se tentou |
| `tentada_em` | `timestamptz` | a última tentativa |

🚨 **POR QUE UMA TABELA, E NÃO MAIS UMA COLUNA:**
`formulario_solicitacao.os_id` é **uma** OS, e a partir da D3 um envio com 4
placas abre 4. Enfiar quatro números numa coluna (ou criar `os_id_2`) é o
caminho que não tem fim.

⚠️ **`formulario_solicitacao.os_id` CONTINUA EXISTINDO** e passa a significar
**a primeira OS desta solicitação** — não "a OS". Quem precisa de todas lê a
tabela nova. Não foi removida porque o painel de hoje a lê, e trocar as duas
coisas na mesma volta esconderia qual delas quebrou.

🚨 **A LINHA NASCE ANTES DA OS EXISTIR**, com `os_id` e `erro` nulos, e isso é o
ponto do Bloco A: *"a falha tem de ser visível — chamado gravado e OS não
criada é o pior caso: o cliente recebe 'recebemos' e ninguém abre OS"*. Então a
ordem é **chamado primeiro, OS depois**: o envio grava, as linhas nascem vazias,
e cada falha fica **escrita na linha** e contada no painel (`fora_do_quadro.
os_falhou`). A alternativa — criar a OS antes e só então gravar — perderia o
chamado inteiro quando o ERP estivesse fora do ar, que é justamente quando o
cliente mais precisa ser ouvido.

⚠️ **OS TRÊS ESTADOS DE UMA LINHA, e o terceiro não é sucesso:**
- `os_id` preenchido, `erro` nulo — a OS nasceu;
- `os_id` nulo, `erro` preenchido — a OS **não** nasceu, e o motivo está dito;
- `os_id` nulo **e** `erro` nulo — a tentativa **nunca aconteceu**.

🚨 **O ÍNDICE ÚNICO É A TRAVA DA DUPLICATA, não a boa intenção de quem chama:**
`idx_solicitacao_os_unica` em `(solicitacao_id, coalesce(placa, ''))`. Sem ele,
dois cliques no mesmo envio abrem duas OS para a mesma placa. O `coalesce`
existe porque **em SQL dois nulos não são iguais** — sem ele a solicitação sem
placa poderia ganhar duas linhas.

🚨 **E O CASO QUE NÃO SE PODE MASCARAR — o `erro` que começa com 🚨:** quando o
Harmonit aceita a escrita e **não diz o número da OS**, pode haver OS criada no
ERP que ninguém sabe que existe. A linha guarda o aviso e **a retentativa não
acontece** (a linha já existe, e `ON CONFLICT DO NOTHING` não devolve nada).
Dizer "falhou" ali faria quem chama tentar de novo e abrir a **segunda**.
⚠️ **Timeout da ponte cai nesse mesmo caso**, e foi um erro que quase ficou no
código: *"não respondeu no tempo"* **não** quer dizer *"não gravou"* — a escrita
pode ter chegado e a resposta ter se perdido na volta.

## Migração 083 — a passagem de etapa

🔵 **Decisão dele, 29/10, em uma frase:** *"deve ter o log de quem faz o que
SEMPRE"*.

`os_passagem` — tabela nova. Uma linha por tentativa de mover um card de etapa.

| coluna | tipo | o que é |
|---|---|---|
| `numero_os` | `integer NOT NULL` | a OS no Harmonit |
| `os_id` | `integer` | o id interno da OS, quando conhecido |
| `de_situacao` | `integer` | de onde o card saiu. **Nula** = o ERP tinha a situação como `NULL` |
| `para_situacao` | `integer NOT NULL` | para onde |
| `atendente_id` | `integer` | **quem** moveu (`ON DELETE SET NULL`) |
| `em` | `timestamptz` | quando |
| `ok` | `boolean NOT NULL` | a escrita foi **confirmada pela releitura** |
| `erro` | `text` | o que o ERP respondeu, quando recusou |
| `fora_da_situacao` | `jsonb` | o que a releitura acusou **fora** da situação |

🚨 **POR QUE ESTA TABELA É A CONDIÇÃO DO BLOCO D, e não um extra:** o Harmonit
**não registra a situação na linha do tempo** — só o `status`, conferido em 3 OS
em 29/10. Então, movido o card, **não há como saber quem moveu, de onde e
quando**, nem aqui nem lá. Sem ela, mover é uma escrita **anônima e
irreversível** no ERP.

🚨 **A TENTATIVA RECUSADA TAMBÉM É GRAVADA**, e foi o que a prova de ponta a
ponta mostrou: duas linhas com `ok = false` e o motivo, antes das duas que
deram certo. Escrita negada sem rastro é a mesma família do `criada: null` da
criação de OS — ninguém descobre depois.

⚠️ **O CONFLITO DE CONCORRÊNCIA NÃO VIRA LINHA.** Quando a situação do ERP já é
outra, nada é tentado — e registrar uma passagem que não aconteceu encheria a
linha do tempo da OS de ruído. A recusa volta na resposta e a tela recarrega.

⚠️ **`de_situacao` NULA NÃO É ZERO.** `0` é um valor que o Harmonit grava em
**129** OS; `NULL` é "a varredura não leu". Confundir os dois já custou uma
coluna inteira do painel em 22/10.

⚠️ **ESTA TABELA NÃO É O BLOCO C.** O C quer *"quanto tempo em cada etapa"*, com
os dois tempos no card. Aqui é o **registro da passagem** — e é ele que faz o C
sair barato depois, porque o dado passa a ser colhido desde já.

🟡 **E é o que faz o "Voltar" ser honesto:** sabendo de onde o card veio, voltar
é uma **nova passagem**, nunca um "desfazer" — o ERP não desfaz nada, e dizer
"desfazer" afirmaria que a primeira escrita não aconteceu.

**Os três índices:** por OS (a linha do tempo que o Bloco E vai ler), por
atendente (*"o log de quem faz o que"* respondido sem varrer a tabela) e um
parcial sobre as recusadas (`WHERE NOT ok`).

## Migração 084 — a observação do painel

🔵 **Pedido dele no plano:** *"observação do painel, com autor e hora, **no
MoviZap**. Não vai para a `solucaoTecnica` — aquele campo é da operação, e o
fluxo que está lá vai ser apagado"* (a decisão **D10**).

`os_observacao` — tabela nova. Uma linha por recado do painel sobre uma OS.

| coluna | tipo | o que é |
|---|---|---|
| `numero_os` | `integer NOT NULL` | a OS no Harmonit |
| `texto` | `text NOT NULL` | o recado. CHECK impede texto em branco |
| `atendente_id` | `integer` | **quem** escreveu (`ON DELETE SET NULL`) |
| `em` | `timestamptz` | quando |

🚨 **POR QUE ELA NÃO VAI PARA O ERP, e é o ponto:** a `solucaoTecnica` é da
operação técnica, **o cliente pode lê-la num relatório**, e escrever nela
**grava a OS inteira** (`SalvarOrdemServico`) a cada recado — risco sem ganho.

🚨 **NÃO SE APAGA E NÃO SE EDITA, e não há coluna para isso.** Reescrever recado
é reescrever a história que a operação leu. É a mesma régua do 🔵 *"deve ter o
log de quem faz o que SEMPRE"*.

⚠️ **A CHAVE É O `numero_os` E NÃO A SOLICITAÇÃO:** desde a **D8** o card é a OS
de qualquer origem, e a maioria **não tem solicitação** — amarrar na solicitação
deixaria 10 dos 11 cards sem onde escrever.

⚠️ **A troca de prioridade entra aqui como linha do sistema** (`[sistema]
prioridade: Normal → Alta`), em vez de ganhar tabela própria: uma tabela de log
por campo escrito seria tabela por campo.

**Os dois índices:** por OS (o que o card aberto lê) e por atendente (*"o log de
quem faz o que"* respondido sem varrer a tabela).

⚠️ **O card fechado mostra só o NÚMERO de recados**, nunca um trecho: trecho na
coluna faria o card crescer sem limite.

## Migração 085 — a ficha do técnico, os serviços e o preço de cada um

🔵 04/11, pedido dele: *"nessa aba ter uma ficha de cada 1. como no formulario
de credenciamento (...) Dentro vamos colocar uma tabela de preço por serviços
que ele oferece, padrão a todos (...) Dai o cadastro do tecnico e validação dele
passará por essa tela."*

🚨 **ESTA MIGRAÇÃO CONTRARIA, DE PROPÓSITO, O AVISO DA 077**, que diz da
`tecnico_origem`: *"⚠️ NÃO É CADASTRO (...) o projeto já tem 117 contatos de
técnico sem cadastro no Harmonit para provar o que acontece quando ninguém
mantém."* O aviso continua verdadeiro — é por isso que a 077 não inventou
cadastro sozinha. O que mudou é que **ele pediu o cadastro e disse quem
mantém**: a validação do técnico passa pela `TEC_1.1`.

⚠️ **A FICHA NÃO CRIA ENTIDADE NOVA.** A chave é o `contato` — o mesmo
`contato_id` que `agendamento.tecnico_contato_id` e
`orcamento.tecnico_contato_id` já apontam. Técnico virar uma segunda identidade
faria o orçamento emitido e a ficha falarem de dois sujeitos diferentes.

Medido antes de escrever: **303** contatos com `relacao = 'tecnico'`,
`tecnico_origem` com **0 linhas**, formulário `CREDENCIAMENTO` **ativo** com
**0 solicitações**.

### `servico_tecnico` — o catálogo, igual para todos

| coluna | tipo | o que é |
|---|---|---|
| `id` | bigserial | PK |
| `nome` | varchar(60) UNIQUE | Instalação, Retirada, Manutenção Local, Manutenção Troca, Substituição Retirada, Substituição Instalação, Socorro, Laudo Técnico, Treinamento, Acompanhamento |
| `ordem` | integer | a ordem na ficha; a dele |
| `ativo` | boolean | desativa-se, **não se apaga** — `tecnico_preco` aponta para cá |
| `criado_em` | timestamptz | |

### `tecnico_ficha` — o cadastro do prestador

Uma linha por técnico, PK `contato_id` → `contato(id)` `ON DELETE CASCADE`.
**Contato sem linha é técnico sem ficha, e isso é estado válido.**

| bloco | colunas |
|---|---|
| validação | `estado` (CHECK `candidato`/`credenciado`/`recusado`, default `candidato`), `estado_em`, `estado_por` → `atendente(id)`, `estado_nota` |
| empresa | `nome_fantasia`, `razao_social`, `cnpj`, `telefone_fixo`, `email_geral` |
| responsável | `responsavel_nome`, `responsavel_sobrenome`, `cpf`, `responsavel_celular`, `responsavel_email` |
| endereço fixo | `cep`, `logradouro`, `numero`, `bairro`, `cidade`, `uf`, `complemento` |
| banco | `banco`, `agencia`, `conta`, `titular_tipo` (CHECK `F`/`J`) |
| deslocamento | `ponto_fixo`, `vai_ao_cliente`, `area_cobertura`, `cobra_deslocamento`, `km_valor_centavos` |
| resto | `observacao`, `solicitacao_id` → `formulario_solicitacao(id)`, `criado_em`, `atualizado_em` |

🚨 **OS SETE DO ENDEREÇO SÃO OS MESMOS DA 073 E DA 077, NOS MESMOS LIMITES** —
duas réguas para o mesmo endereço é uma delas mentindo. E é **este** endereço
que a calculadora de KM abre preenchida, desde 04/11.

⚠️ `solicitacao_id` **NULL = ficha feita à mão** (D3: o formulário alimenta a
tela, sem exclusividade).

⚠️ Os três booleanos aceitam **NULL**, e isso é o ponto: *"não respondeu se tem
ponto fixo"* e *"disse que não tem"* são fatos diferentes.

### `tecnico_preco` — o que ele cobra de nós, por serviço

| coluna | tipo | o que é |
|---|---|---|
| `contato_id` | bigint | PK composta, → `contato(id)` CASCADE |
| `servico_id` | bigint | PK composta, → `servico_tecnico(id)` |
| `custo_centavos` | integer | **CUSTO** (D2), em centavos. Nulo = não oferece |
| `atualizado_em` | timestamptz | |

🚨 **LINHA AUSENTE E VALOR NULO SIGNIFICAM A MESMA COISA:** ele não oferece
aquele serviço. Não existe booleano "oferece" ao lado de propósito — dois
campos para o mesmo fato acabam discordando. **Zero é zero**, e continua
diferente de ausente.

### E a memória da 077

A migração copia `tecnico_origem` → `tecnico_ficha` (como **candidato**:
endereço escrito pelo uso é exatamente o que ninguém conferiu), e **hoje isso
move 0 linhas**. O `DROP TABLE tecnico_origem` fica numa migração separada,
depois de ele validar a tela: `movizap/rotas.py` deixou de ler a tabela na
mesma entrega, mas derrubá-la aqui deixaria a calculadora em erro entre a
migração e o deploy.

## Migração 086 — os dados de PAGAMENTO do técnico

🔵 04/11, segunda volta da tela: *"Banco ajuste para dados de pagamento, pode
ser TED, PIX, ou boleto, oopção por lista e campo com os dados"*. E sobre o
formulário de credenciamento, que perguntava os quatro campos bancários:
*"ajuste no formulario tbm, o mesmo formato. ai amarra eles"*.

| coluna | tipo | o que é |
|---|---|---|
| `pagamento_forma` | varchar(10), CHECK `ted`/`pix`/`boleto` | como se paga este técnico |
| `pagamento_dados` | text | para onde vai o dinheiro, como ele informou |

**Saíram** `banco`, `agencia`, `conta` e `titular_tipo`, que a 085 havia criado.

🚨 **POR QUE REMOVER FOI SEGURO**, medido antes: `tecnico_ficha` com **0
linhas**, fichas com qualquer dado bancário **0**, solicitações do
`CREDENCIAMENTO` **0**. Não havia dado a migrar porque não havia dado. Com
conteúdo, a migração copiaria antes — e o que fazer com o conteúdo seria
pergunta para ele, não decisão minha.

⚠️ **DUAS COLUNAS, NÃO UMA POR FORMA.** PIX e TED não pedem tabelas diferentes:
pedem a mesma pergunta ("para onde vai o dinheiro?") com conteúdo diferente. Uma
coluna por forma criaria três sempre vazias menos uma, e a primeira consulta de
"quem está sem dados de pagamento" teria de conhecer as três.

⚠️ **`pagamento_dados` É TEXTO LIVRE, de propósito.** Chave PIX é CPF, CNPJ,
telefone, e-mail ou chave aleatória; conta é banco + agência + conta + titular.
Validar formato aqui recusaria o que o técnico mandou do jeito que ele tem — e
quem confere é quem credencia.

🚨 **OS TRÊS VALORES SÃO OS MESMOS DO FORMULÁRIO**, e é isso que "amarra eles":
`tecnico_ficha.FORMAS_DE_PAGAMENTO` e as `opcoes` do campo do formulário têm de
coincidir, e há um teste que compara os dois lados
(`test_a_forma_do_formulario_bate_com_a_da_ficha`).

## Migração 087 — sai a `tecnico_origem`

🔵 04/11, decisão dele em duas partes: *"o cadastro alimenta alimenta a memória,
pode tirá-la"* e, à proposta do fechamento, **"1 ok"**.

A tabela da 077 — memória do último endereço de origem, escrita pelo uso da
calculadora de KM — **não existe mais**. O que a substituiu é o endereço FIXO de
`tecnico_ficha` (085), que é cadastro e tem quem mantenha: a tela `TEC_1.1`.

🚨 **AS DUAS MEDIDAS FORAM REFEITAS NA HORA**, não copiadas da sessão da manhã:
`select count(*) from tecnico_origem` → **0**, e `grep` por `tecnico_origem` em
`movizap/*.py` e `frontend/src/` → **nenhuma ocorrência em código** (só
comentários que contam a história). Há um teste que reprova se
`rotas.lembrar_origem` ou `rotas.origem_do_tecnico` voltarem a existir.

⚠️ **NÃO FORAM TOCADAS:** `rota_cache` (nasceu na mesma 077 e continua válida —
é cache de consulta paga, não tem a ver com de quem é a origem) e
`agendamento.origem_endereco` / `agendamento.km`, que são o **retrato** do que
se cobrou em cada compromisso.

⚠️ **Desfazer recria a tabela VAZIA, e isso não basta:** quem escrevia nela eram
as duas funções que saíram do código. Desfazer de verdade é desfazer a decisão.

## Migração 088 — a marca `preenche_os`

🔵 04/11, no fechamento: *"crie um campo de flag, junto com os do deslocamento
chamado 'Preenche OS'"*.

`tecnico_ficha.preenche_os boolean`, anulável e **sem DEFAULT**.

🚨 **TRÊS ESTADOS, como as outras três perguntas do bloco:** sim, não e **não
respondido**. Nascer `false` diria, das 287 fichas que existem, que nenhum
técnico preenche OS — afirmação que ninguém fez. É a régua do `ponto_fixo`, do
`vai_ao_cliente` e do `cobra_deslocamento`, e a mesma lição do `0` ≠ `NULL` da
situação da OS (076).

⚠️ **Mora no bloco do deslocamento porque ele pediu ali**, não porque preencher
OS seja deslocamento — anotado para ninguém "arrumar" de lugar depois achando
que foi descuido.

⚠️ **NÃO CONDICIONA NADA HOJE.** A tela grava e mostra. Fazer a criação de OS
depender desta marca seria regra nova sobre o fluxo do Harmonit, e regra é
decisão dele — quando quiser, o dado já está gravado e medível.

## 04/11 — as 287 fichas com cidade e UF, derivadas do nome

🔵 Decisão dele, à proposta P4: **"4 preencha e mantenha o nome"**.

**Medido:** **287 dos 303** `contato.nome` de técnico (95%) trazem
`Nome | Cidade - UF`; **286** terminam em ` - UF` e o resto usa barra
(*"TÉC. Rogerio Marques | Araxá/MG"*). Os **16** que não têm o padrão são razões
sociais sem cidade no nome (*"CIA DO RADIO"*, *"AUTOTECH RASTREADORES"*).

Feito por `scripts/cidade_do_nome_do_tecnico.py`, que **por padrão só relata**;
`--um` faz o primeiro e `--aplicar` faz o lote. Resultado: **287 fichas** com
cidade e UF, todas em estado `candidato`.

🚨 **ISTO É DERIVAÇÃO, NÃO CADASTRO CONFERIDO**, e o script diz isso de três
maneiras: a ficha nasce **candidata**, a `observacao` registra a procedência
(*"Cidade e UF derivadas do nome do cadastro do Harmonit (04/11). Confira antes
de credenciar."*) e **nada já preenchido é sobrescrito** — rodar duas vezes não
muda nada (provado: a segunda rodada diz "a preencher: 0").

🚨 **O NOME NÃO FOI TOCADO**, e o script prova isso ao fim de cada rodada: os
técnicos **sem** o ` | ` no nome continuam **16**, antes e depois.

⚠️ **SÓ CIDADE E UF.** Rua, número, bairro e CEP seguem vazios — e credenciar
continua exigindo **rua e cidade**, então nenhuma das 287 fica "pronta" por
causa disto.

## Migração 089 — a unidade de cada serviço do técnico

🔵 04/11, parte da ligação entre a ficha e o orçamento. A premissa que
destravou é dele: *"o orçamento não vai ao cliente, somente ao técnico."*

`servico_tecnico.unidade varchar(4) NOT NULL DEFAULT 'un' CHECK (unidade IN
('un','km'))`. Os 10 nascem `un`.

🚨 **POR QUE UMA COLUNA, e não "assume `un` no código":** o botão da calculadora
de KM no modal aparece por **`l.unidade === 'km'`**, não pelo nome do serviço —
e isso está escrito no `ModalAgendar.vue` de propósito, *"para um serviço novo
por km ganhar a calculadora sozinho"*. Assumir no código faria essa regra
passar a depender de nome, que é exatamente o que ela evita.

⚠️ **O MESMO PAR DE VALORES DO OUTRO LADO:** `orcamento_item.unidade` tem
`CHECK (unidade IN ('un','km'))` desde a 069. Duas listas de unidade que não
batem seriam uma delas recusando no `INSERT` o que a outra ofereceu na tela.

⚠️ **Deslocamento não é um dos dez** — é `KM DESLOCAMENTO`, do catálogo fixo do
orçamento, e o valor por km do técnico vive em `tecnico_ficha.km_valor_centavos`.

## Migração 090 — o checklist de cada etapa do painel da Operação

🔵 04/11, com um print do Bitrix como referência: *"são itens que vão ficar em
um botão dentro do card, como mapa para o operador saber o que fazer"*, e
**"Modelo fixo + o operador pode acrescentar"**.

**`checklist_modelo`** — a lista da etapa: `id`, `situacao_id`, `texto`
varchar(200), `ordem`, `ativo`, `criado_em`.
**`checklist_item`** — o card: `id`, `numero_os`, `situacao_id`, `texto`,
`ordem`, `de_modelo_id` → `checklist_modelo`, `feito`, `feito_por`, `feito_em`,
`criado_por`, `criado_em`, e `UNIQUE (numero_os, situacao_id, de_modelo_id)`.

🚨 **NÃO É O CHECKLIST DO HARMONIT.** O ERP tem o seu
(`ObterCheckListOrdemServico`), que o app do técnico em campo mostra. Os itens
daqui são de **escritório** — *"Verificar DataScope"*, *"Nota Fiscal (emitir e
enviar)"* — e lá só fariam ruído. Decisão dele: nem um nem outro.

🚨 **O ITEM DO CARD É CÓPIA, NÃO REFERÊNCIA.** O texto é gravado quando o card
abre a etapa pela primeira vez; **editar o modelo depois não reescreve** o que
já está marcado. O card é registro do que foi feito, não espelho da
configuração — o mesmo desenho do `tipo_nome` (072) e do `origem_endereco`
(077). Há teste prendendo os dois lados: o card antigo não muda, o card novo
nasce com o texto novo.

🚨 **O `UNIQUE` É O QUE TORNA A CÓPIA IDEMPOTENTE.** Com `ON CONFLICT DO
NOTHING`, abrir o card dez vezes — ou dois atendentes ao mesmo tempo — dá o
mesmo resultado. ⚠️ Ele **não** alcança item avulso (`de_modelo_id` nulo, e
`NULL` não conflita com `NULL` em `UNIQUE`), e é o certo: o operador pode
escrever dois avulsos iguais se quiser.

⚠️ **`situacao_id` sem chave estrangeira**, de propósito: as 17 situações vivem
em `movizap/paineis.py`, não em tabela. Criar uma tabela de situações aqui seria
uma segunda fonte para a mesma lista.

⚠️ **Desmarcar não apaga**: vira `feito = false` com `feito_em` novo. Quem
marcou e desmarcou fez duas coisas, e as duas são informação.

**Seed**: 251 → 3 itens · 16488 → 4 · 677 → 2, as três listas que ele escreveu.
As outras seis etapas que ele citou ficaram **sem itens** — ele não os escreveu,
e etapa sem modelo simplesmente não mostra o botão.

## Migração 091 — anexo na observação do card

🔵 04/11: *"Card OBS anexos, texto, format conve -- exibir em modal"*.

`os_observacao_arquivo (id, observacao_id → os_observacao CASCADE,
nome_original, caminho, bytes, mime, criado_em)`.

🚨 **POR QUE NÃO A TABELA `midia`: o banco proíbe.** O
`CHECK midia_tem_um_dono` (047) é `((conversa_id IS NULL) <> (sala_id IS NULL))`
— ou-exclusivo, exatamente um dono. Observação de card não é conversa nem sala,
então **não existe linha possível** ali. ⚠️ E o CHECK **não foi afrouxado**: ele
é o que impede mídia órfã, e órfã é mídia que ninguém acha para apagar.

O molde é o `formulario_arquivo` (074): pasta própria
(`/home/claude/movizap_observacao_anexos`), caminho no banco, nome original só
para exibir, arquivo gravado em pasta sorteada (`uuid4().hex`), **lista branca**
de extensão no código e teto de 10 MB.

🚨 **ESTA PASTA NÃO TEM BACKUP**, como as outras duas de anexo: o
`scripts/backup_db.py` leva o **banco**, então a linha sobrevive e o arquivo
não. Por isso `GET /api/paineis/operacao/anexo/{id}` devolve **410** (não 500)
quando o arquivo sumiu — e **a tela diz isso a quem anexa**, antes de anexar.

⚠️ Recusa **antes** de escrever no disco: extensão, tamanho e vazio são
conferidos primeiro, para não deixar arquivo solto sem linha no banco.

## Migrações 092 e 093 — as etapas NOSSAS, e a coluna `Chamados`

🔵 05/11: *"vamos criar uma coluna nova antes de 'Nova solicitação', chamada
'Chamados', aqui vão ser gerados os cards que virão do forms de suporte, não
mais em OS e nessa coluna não são OS ainda, somente o CARD mesmo, com OBS,
etc"*. E a razão de negócio, na frase dele: *"O chamado é o cliente dizendo
algo, como: 'rastreador parou de pegar'. O chamado é para analisar e decidir se
realmente será aberta OS."*

🚨 **A descoberta que desenhou o modelo:** a coluna `Chamados` e as pipelines de
Pós-venda que ele pediu no mesmo dia (*"a aba 'Operação' do Movizap é a mesma
lógica para os demais"*) **são a mesma coisa** — colunas que **não existem no
Harmonit**. Mover numa coluna da Operação escreve `situacaoId` no ERP; mover
numa destas escreve **só aqui**. Um motor serve os dois casos, e fazer a coluna
Chamados sozinha seria fazer duas vezes.

### As quatro tabelas

```
painel_aba        (id, painel, codigo_tela, titulo, ordem, ativo)
pipeline_etapa    (id, aba_id → painel_aba CASCADE, titulo, ordem, ativo, final)
pipeline_card     (id, aba_id, etapa_id, solicitacao_id NULL, cliente_id NULL,
                   criado_em, criado_por,
                   desfecho NULL CHECK (desfecho IN ('resolvido','virou_os')),
                   desfecho_em, desfecho_por)
pipeline_passagem (id, card_id → pipeline_card CASCADE,
                   de_etapa, para_etapa, de_titulo, para_titulo, quem, em)
```

⚠️ **A aba tem `codigo_tela`** porque a permissão é **por aba** — decisão dele:
*"será por abas. então terá mais de uma pipeline, mas todas dentro de
'Pós-Venda'"* e *"a Karla terá permissão para ver o 'Financeiro' e todas as
abas. A Erika, apenas a aba 3 do financeiro"*. `permissao` é campo da entrada no
`telas.py`, então cada aba precisa da própria entrada. A aba da Operação reusa a
`PNL_1.1`, porque a coluna `Chamados` **é parte do quadro da Operação**, não uma
tela nova.

🚨 **A `Chamados` NÃO entra na tupla `SITUACOES`** do `movizap/paineis.py`, e
isso é deliberado: duas travas dependem de ela ter 17, e
`checklist._etapa_conhecida` recusa situação fora dessas 17. A coluna é de outra
natureza — etapa nossa, `situacao_id` nulo — e não uma 18ª situação do ERP. O
quadro da Operação passou a responder **18 colunas**, com a `Chamados` na
frente e chave `"chamados"` (e não `s<id>`, justamente para a tela não poder
confundi-la com situação).

### 🚨 A passagem é um RETRATO (migração 093)

A `092` amarrava `de_etapa`/`para_etapa` por chave estrangeira em
`pipeline_etapa`, **sem `ON DELETE`** — e isso tornava **impossível apagar uma
aba**. As duas saídas óbvias eram ruins: `CASCADE` apagaria o histórico junto, e
`SET NULL` deixaria a passagem sem dizer para onde o card foi.

A `093` tira as duas chaves e grava **o título de então** (`de_titulo`,
`para_titulo NOT NULL`). Renomear a etapa amanhã não reescreve o que a passagem
dizia, e apagar a aba não leva o log. É o molde do `orcamento_item.servico`, que
guarda o nome do serviço no item em vez de apontar para o catálogo.

### A observação do card, com dois donos possíveis

```sql
ALTER TABLE os_observacao
  ADD COLUMN solicitacao_id integer NULL
      REFERENCES formulario_solicitacao(id) ON DELETE CASCADE,
  ALTER COLUMN numero_os DROP NOT NULL,
  ADD CONSTRAINT os_observacao_tem_um_dono
      CHECK (numero_os IS NOT NULL OR solicitacao_id IS NOT NULL);
CREATE INDEX idx_observacao_solicitacao ON os_observacao (solicitacao_id, em DESC);
```

🚨 **O CHECK é o ponto:** a observação tem um dono — OS **ou** chamado, nunca
nenhum. É o molde do `midia_tem_um_dono` (047), com uma diferença medida: lá é
ou-exclusivo (`<>`), aqui é `OR`, porque um chamado que vira OS pode querer os
dois.

⚠️ **O índice velho não serve**: `idx_observacao_os` é `(numero_os, em DESC)`, e
buscar por `solicitacao_id` passaria por varredura. Daí o novo.

✅ **O anexo vem de graça:** `os_observacao_arquivo` é chaveado por
`observacao_id`, então a observação de chamado anexa pelo mesmo caminho da de
OS, com a mesma pasta e o mesmo 410 de arquivo sumido.

### ⚠️ O desfecho não mexe no `estado` da solicitação

`formulario_solicitacao_estado_check` aceita só `nova`/`em_andamento`/
`concluida`, e `formularios.py` conta `estado = 'nova'` em dois lugares.
`estado` é **ciclo de vida**; desfecho é **como terminou**. Misturar faria todo
código que testa `'concluida'` passar a errar.

🚨 **E "Virou OS" SÓ MARCA** — decisão dele: *"só marca; a OS é pelo Operação"*.
Nenhuma das rotas de chamado fala com o Harmonit, e é isso que torna
`Finalizar Chamado` reversível por `Reabrir`.

## `tela_concedida` — a permissão que não é por perfil (migração 095, 06/11)

```
tela_concedida
  id             bigserial PK
  atendente_id   bigint NOT NULL -> atendente(id) ON DELETE CASCADE
  codigo_tela    varchar(16) NOT NULL        -- código do `movizap/telas.py`
  concedida_por  bigint -> atendente(id) ON DELETE SET NULL
  concedida_em   timestamptz NOT NULL DEFAULT now()
  UNIQUE (atendente_id, codigo_tela)
```

🔵 Nasceu do pedido dele de 06/11: *"em configuração, crie uma aba de permissão
para os paineis, ali vou definir quem pode ver o que e por aba tbm"*.

🚨 **É A LISTA DE EXCEÇÕES NOMEADAS DA PERMISSÃO.** Até 06/11 quem decidia
acesso era só `atendente.perfil` → `telas.PERFIS`. Cada linha aqui diz *"esta
pessoa alcança esta tela"*, e `telas.pode_acessar` a honra **antes** de recusar
tela `owner`. ⚠️ A tela continua `owner` no registro — isto não a rebaixa.

🚨 **SEM FK EM `codigo_tela`, de propósito:** o catálogo de telas é o CÓDIGO
(`movizap/telas.py`), não uma tabela — a mesma razão de `painel_aba.codigo_tela`
não ter. Quem limita o que pode ser gravado é a rota, que só aceita código do
grupo "Painéis".

🚨 **A UNIQUE É A TRAVA DA TELA.** Sem ela, conceder duas vezes daria duas
linhas e revogar apagaria uma só: a pessoa continuaria vendo o painel e a tela
de permissão diria "não concedido" — `M12`, e sobre quem vê o quê.

⚠️ **AS DUAS FK SÃO DIFERENTES DE PROPÓSITO.** `atendente_id` cai em **CASCADE**
(a concessão não tem sentido sem quem a recebeu); `concedida_por` cai em **SET
NULL** (apagar quem concedeu não tira o acesso de quem recebeu, só o autor).

⚠️ **LIDA A CADA REQUISIÇÃO** por `auth.buscar_usuario`, e **não** guardada no
token: revogar vale no próximo clique da pessoa, não no próximo login dela. A
leitura degrada para vazio se a tabela não responder — a pessoa perde o painel
concedido e continua entrando, que é o lado certo de falhar.

**Hoje:** 0 linhas. Quem concede é ele, na aba `CFG_15.1`. A migração não
concede nada a ninguém.

## Os quatro painéis em `painel_aba` (migrações 092 · 094 · 096 · 097)

| painel | `codigo_tela` | título da aba | etapas | migração |
|---|---|---|---|---|
| `operacao` | `PNL_1.1` | Operação | **1** (`Chamados`) | 092 |
| `pos_venda` | `PNL_1.2` | Treinamentos | 4 | 094 |
| `pos_venda` | `PNL_1.3` | Pós-venda | 4 | 094 |
| `financeiro` | `PNL_1.4` | Financeiro | **10** | 096 |
| `contratual` | `PNL_1.5` | Contratual | **6** | 097 |

🚨 **`painel_aba.painel` TEM VOCABULÁRIO FECHADO** (`painel_aba_painel_conhecido`):
`operacao`, `pos_venda`, `contratual`, `financeiro`. Painel novo — "Cobrança", por
exemplo, que a anotação dele sobre INADIMPLENTES menciona — precisa de migração
que **amplie o CHECK** antes de qualquer aba. É a armadilha que a casa já
catalogou em `contato.relacao`: código recusando valor que o banco aceita, ou o
contrário.

⚠️ **A `PNL_1.1` tem UMA etapa só**, e não dezessete: as 17 colunas da Operação
são **situações da OS do Harmonit**, calculadas em `paineis.quadro()`. A única
etapa nossa dela é a `Chamados`. As dos outros três são **todas** nossas, e
vivem aqui.

⚠️ **Etapa é única DENTRO da aba, não no sistema:** "Solicitação" aparece nas
duas abas do Pós-venda, e "Assinado" (contratual) e "Contratos assinados"
(financeiro) são colunas diferentes de painéis diferentes.

**Cards hoje: 1 no total** (um chamado na `Chamados` da Operação). Os quatro
painéis novos estão **vazios por decisão dele** — a origem dos cards segue em
aberto (*"as regras de criação de cards (...) ainda ficam em branco mesmo"*).

---

## `os_campo_da_etapa` — o campo de texto que a etapa pede (migração 099, 11/11)

🔵 Pedido dele, duas vezes com a mesma forma: *"Enviar por correio - Abaixo de
'Observações', criar um campo de texto chamado 'Rastreamento' que é onde a
operadora irá colocar o código de rastreamento que será enviado ao cliente"* e
*"Aguardando devolução - Abaixo de 'Observações', criar um campo de texto
chamado 'Devolução' (...) Apenas para consulta interna da operadora"*.

```sql
os_campo_da_etapa (id, numero_os, chave, valor,
                   atendente_id → atendente SET NULL, em)
```

🚨 **NÃO EXISTIA NENHUM CAMPO LIVRE POR ETAPA ANTES DISTO.** O que havia era o
item de checklist *"Inserir código de rastreio"* (etapa 677, migração 090), que
**só marca que alguém inseriu** — `checklist_item` tem `texto`, `feito`,
`feito_por` e `feito_em`, e nenhum lugar para o código. Marcar o item continua
valendo; agora há onde escrever.

### Uma tabela para os dois campos, e não duas colunas na OS

O terceiro campo por etapa vai aparecer — ele já pediu dois no mesmo bloco —, e
coluna por pedido é como nasce tabela larga que ninguém sabe ler. A chave é
texto, com **vocabulário fechado** no `CHECK os_campo_chave_check`
(`rastreio`, `devolucao`), e o que cada chave significa mora em
`movizap/campo_etapa.py`, onde dá para ler a regra junto do código.

⚠️ **Chave nova exige migração** que amplie o CHECK — a mesma armadilha de
`painel_aba.painel` e de `contato.relacao`. A trava
`teste_campo_etapa.py::test_as_chaves_do_codigo_sao_as_do_CHECK_do_banco`
compara o dicionário do código com o CHECK do banco, para que ninguém mexa só
num dos dois.

### As duas chaves, e por que não são o mesmo campo

| chave | etapa | rótulo | vai ao cliente? |
|---|---|---|---|
| `rastreio` | **677** Enviar por correio/transportadora | Rastreamento | **sim** — é o código que a mensagem da etapa seguinte vai levar |
| `devolucao` | **15696** Aguardando devolução de equipamento | Devolução | **não** — *"Apenas para consulta interna da operadora"* |

🚨 **A diferença é dado, não comentário** (`campo_etapa.CAMPOS[...]["ao_cliente"]`),
e é o que impede o primeiro disparo automático de mandar o código de devolução
para o cliente.

### Nunca se dá `UPDATE`: cada gravação é uma linha

O valor de agora é o **mais recente** (`DISTINCT ON (chave) ... ORDER BY em DESC`,
o molde do `passagem.etapa_desde`), e o anterior fica.
🚨 **A razão é concreta:** a operadora que troca o código de rastreio não pode
apagar o anterior, que **pode já ter ido para o cliente** — saber o que foi
mandado antes é o que permite dizer "mandei o errado".
O índice `idx_campo_etapa_atual (numero_os, chave, em DESC, id DESC)` serve
exatamente essa leitura.

### A chave é `numero_os`, como na `os_observacao`

E **não** a solicitação: amarrar na solicitação deixaria sem onde escrever toda
OS que nasceu no ERP, que é a maioria.
⚠️ **Sem FK para a OS**, pelo mesmo motivo da `os_observacao` e da
`os_passagem`: não existe tabela de OS nossa — a OS vive no Harmonit e o cache
é do FPSL, outro banco.

### Gravar gera observação, e gravar não escreve no Harmonit

🔵 *"O mesmo para os dados de 'Rastreamento' (...) o mesmo para o campo de
'Devolução'"* — gerar OBS. Cada gravação escreve
`[sistema] Rastreamento: AA123456789BR` na `os_observacao`, com autor e hora.

⚠️ **A OBS sai na GRAVAÇÃO, e não ao sair da etapa** — ao contrário do
checklist. Para o checklist o que vale registrar é o placar final; aqui o que
vale é *qual código foi posto e por quem*, e esperar a saída da etapa perderia a
troca feita no meio.
⚠️ **A OBS falhar não desfaz a gravação:** o código é o dado, a OBS é o rastro.

🚨 **`movizap/campo_etapa.py` NÃO IMPORTA A PONTE**, e há trava estrutural
provando. Escrever o código na OS exigiria `SalvarOrdemServico` — a **OS
inteira** —, que é a armadilha do endereço e da situação. A tela **diz** isso a
quem escreve: *"Fica registrado aqui e vira observação no card. Não vai para a
OS do Harmonit."*

### Teto de 120 caracteres

`CHECK os_campo_valor_tamanho`. É código de rastreio, não recado — quem precisa
escrever um parágrafo tem a observação, que aceita 4000.

---

## `os_observacao.apagada_em` / `.apagada_por` — apagar o recado (migração 101, 11/11)

🔵 Pedido dele: *"Permitir excluir OBS's, porém manter os logs e somente owner
pode visualizar o exlcuido, com botão, como no chat interno, sem que vejam essa
informação. Se excluírem, aparecerá como 'Observação excluida' e log's."*
E as três respostas do mesmo dia: apaga **todos que têm acesso à visualização do
painel**; **sem janela de tempo** (*"pode ser apagada conforme disponivel
mesmo"*); e **a autoria fica visível** — *"é um dos objetivos,
rastreabilidade"*.

```sql
os_observacao (… , apagada_em TIMESTAMPTZ,
                   apagada_por INTEGER → atendente SET NULL)
```

🚨 **ISTO INVERTEU UMA DECISÃO ESCRITA, e o texto velho morreu junto.** A
migração 084 afirmava, no comentário da coluna `texto`, que *"nao ha coluna de
'apagada' nem de 'editada', de proposito"*, e a tela repetia isso em palavras
(*"e não se apagam"*). Os dois foram atualizados na mesma entrega — senão o
sistema mente sobre si mesmo (`M12`). **Editar continua não existindo.**

### Três diferenças deliberadas em relação ao chat interno

| | chat interno (061) | aqui (101) |
|---|---|---|
| quem apaga | **só o autor** | **qualquer pessoa com a `PNL_1.1`** |
| janela | **48 h** | **nenhuma** |
| `apagada_por` | **não existe** | **existe** |

🚨 **A terceira é consequência da primeira.** No chat, "quem apagou" é dedutível
— só o autor pode —, então a coluna seria redundante. Aqui qualquer pessoa apaga
o recado de qualquer um, e sem a coluna a pergunta *"quem apagou?"* não teria
resposta. Rastreabilidade é o objetivo que ele nomeou.

### O texto não é destruído; quem esconde é a leitura

Molde exato do `chat.py:421-444`. `passagem._esconder_apagados` zera `texto` e
`anexos` para quem **não** é owner, e o banco continua com tudo — é o que permite
ao owner ver o que dizia e o que torna a decisão reversível.

⚠️ **A autoria NÃO é escondida**: quem escreveu, quando, quem apagou e quando
continuam na tela para todos. Some **só o que o recado dizia**.

⚠️ **O anexo some da lista junto com o texto.** Deixar
`comprovante-pix-joao.pdf` ao lado de *"Observação excluída"* devolveria pela
legenda o que o apagar tirou — é o vazamento que o chat interno fechou em 07/10,
na mensagem citada.

🚨 **E a rota de download barra também** (`passagem.anexo_e_de_apagada`, molde do
`chat._eh_de_apagada`): a lista esconder não basta, porque a rota aceita um id, e
esse id esteve na tela de quem viu o recado antes de alguém apagar. Responde
**404, não 403** — 403 confirmaria que o arquivo existe, que é metade do que o
apagar esconde.

### `eu` nasce nulo, e nulo não é owner

`passagem.observacoes(numero_os, eu=None)` devolve a versão **fechada** quando
não lhe dizem quem está lendo. ⚠️ Falha no lado seguro, e isso importa porque
**cinco pontos** de `main.py` chamam essa leitura: é o elo *quem devolve → quem
grava → quem lê* que a casa já catalogou, e um ponto esquecido daria ao owner a
tela de todo mundo, em silêncio.

### Os dois donos possíveis

`observacoes_da_solicitacao` nasceu nesta entrega movendo para o módulo a
consulta que vivia dentro da rota do chamado. ⚠️ **Regra que mora na rota é
regra que o segundo caminho esquece**, e com o apagar a regra de esconder passou
a ser obrigatória nos dois.

### O recado do SISTEMA não se apaga

Não é regra de banco: é a tela não oferecer o botão. Aquele texto é o **log**
(checklist da etapa, troca de prioridade, código de rastreio), e apagar log é
apagar a prova.


---

## `etapa_mensagem` — o disparo de cada etapa (migração 102, 11/11)

🔵 Pedido dele: *"Em configurações tela nova de 'Disparos Operação' -> Deixar o
campo de menagens que são enviadas em cada etapa do fluxo com interruptor de
'ligado e desligado'"*, com quatro respostas no mesmo dia: *"nasce em branco e
com interruptor desligado ainda, na tela de config exclusiva owner"* · *"por hora
só whatsapp"* · *"por enquanto somente cliente deixe no painel de disparos uma
nota que nenhuma vai ao tecnico"* · *"ao ligar o interruptor, sairá
automaticamente como na regra"*.

```sql
etapa_mensagem (id, situacao_id UNIQUE, canal, texto, ativo,
                atualizado_em, atualizado_por → atendente SET NULL)
```

🚨 **ATÉ AQUI NADA NO PAINEL FALAVA COM O CLIENTE SEM ALGUÉM CLICAR.** Isto
afrouxa, por decisão dele, a régua da ÁREA F de 04/11 (*"confirmação antes de
enviar, sempre"*). O que ficou no lugar da confirmação:

| guarda | onde |
|---|---|
| nasce **vazia e desligada**, nas 17 | o `INSERT` da própria 102 |
| **não dá para ligar vazia** | `CHECK etapa_mensagem_ligada_tem_texto` |
| **só whatsapp** | `CHECK etapa_mensagem_canal_conhecido` |
| **só ao cliente** | o destinatário é DERIVADO da OS, não escolhido |
| **falhar não desfaz o mover** | `enviar_da_etapa` não levanta, e o `mover` ainda embrulha em `try` |
| **só dispara se o ERP aceitou** | o bloco está dentro do `if resposta.get("ok")` |

### Uma linha por etapa, e as 17 já nascem

Criar a linha só quando ele escrevesse faria a tela ter **dois estados** ("não
existe" e "existe vazia") para a mesma coisa.
⚠️ A coluna `Chamados` **não entra**: não é situação do ERP.

### O canal: atendimento, nunca informativo

🚨 O informativo é de campanha (`informativos.py`), e usá-lo mostraria ao
cliente **o número errado**.
⚠️ E `estado` **não é coluna** do `canal` — é derivado do Evolution a cada
leitura. Conferir conexão no SQL custaria uma ida ao gateway dentro do clique de
mover; se o canal estiver fora do ar, o envio falha e **o motivo vira observação
do sistema no card**.

### O envio passa pela conversa

`conversas.iniciar_conversa`, nunca o `evolution` cru: ele confere se o número
tem WhatsApp, reusa a conversa aberta e **grava a mensagem**. Enviar por fora
deixaria o cliente com uma mensagem que a operação não vê.
⚠️ A trava disso mede `__code__.co_names`, e **não** o texto da função: o
docstring fala do evolution de propósito, e varredura de texto reprovava por
causa do comentário que explica a regra.

### As três variáveis são as PALAVRAS DELE

`{{Contato: Primeiro nome}}` · `{{Nome}}` (o número da OS) ·
`{{Código de envio/acompanhamento transporte}}` (o código gravado na etapa 677).
🚨 A grafia não se "melhora": ele escreve o texto copiando estes nomes, e
divergência deixa a variável sem resolver -- **saindo crua ao cliente**.
⚠️ Variável desconhecida é **removida** do texto final, nunca enviada crua. Sem
nome, o primeiro nome cai em *"tudo bem"*.

### Nenhum texto foi semeado, e é fato, não esquecimento

O texto que ele passou em 04/11 **não sobreviveu em documento nenhum** — do bloco
daquele dia restaram só os três nomes de variável. Semear um texto inventado
seria pôr palavra dele na boca do sistema. Ele disse *"depois colo"*.

---

## `pipeline_card.numero_os` e `pipeline_etapa.depois_da_situacao` — a etapa `Serviço Realizado` (migração 105, 11/11)

🔵 Decisão dele: *"Criar nova etapa de 'Serviço Realizado'"*, **nossa, fora do
Harmonit**, e o fluxo nas palavras dele: *"a coluna nova é para evitar
reverificação de item esquecido, então moverão para la e depois auditarão o card
e por fim, atendimento finalizado"*.

```sql
pipeline_card  (… , numero_os INTEGER)          -- sem FK
pipeline_etapa (… , depois_da_situacao INTEGER) -- onde a etapa nossa entra
```

### 🚨 Até aqui, card nosso era card SEM OS

A coluna `Chamados` (092) é de chamados que **ainda não viraram OS**, e
`pipeline_card` só sabia apontar para `solicitacao_id`. A `Serviço Realizado` é o
**primeiro caso de card COM OS numa etapa nossa**: a OS fica parada em **1316**
no Harmonit enquanto o card está aqui, e só sai de 1316 quando alguém move para
`Atendimento finalizado`.

⚠️ **Isso é consequência da decisão dele, e está dita:** enquanto o card estiver
nesta etapa, o Harmonit **não reflete** que a auditoria está em curso. Em troca, a
operação ganha o passo de conferir antes de finalizar — que é o que ele pediu.

**Sem FK em `numero_os`**, pela mesma razão da `os_observacao` e da `os_passagem`:
não existe tabela de OS nossa — a OS vive no Harmonit e o cache é do FPSL, outro
banco.

### Uma OS não pode estar em duas etapas nossas

`idx_pipeline_card_os_unica (aba_id, numero_os) WHERE numero_os IS NOT NULL AND
desfecho IS NULL`.
⚠️ Sem ele, um clique duplo no arrasto deixaria **a mesma OS em duas colunas**, e
o quadro a mostraria duas vezes.

### "Entre a 1316 e a 15694" não se diz com um número solto

🚨 As colunas da Operação são as **17 situações do ERP, calculadas no código**; as
nossas vivem no banco. A `Chamados` ia na frente de todas e `ordem = 0` bastava.
A `Serviço Realizado` tem de entrar **no meio** — então a etapa nossa diz **depois
de quem** ela vem (`depois_da_situacao`), e nulo = na frente de tudo.

⚠️ **Renumerar as 17 no banco** seria copiar para cá uma lista que vive no código
e que o ERP manda.
⚠️ **Âncora que não existe mais** (situação renomeada ou fora das 17) põe a coluna
no **fim**, e não a esconde: coluna sumida leva card com ela.

### O quadro passou a ter 19 colunas

17 do ERP + `Chamados` + `Serviço Realizado`.
🚨 **`len(SITUACOES)` continua 17**, e é essa separação que mantém verdadeira a
frase dele de 29/10 (*"qualquer aba fora dessas não deve estar no painel"*) sobre
as colunas **do ERP**, que eram as únicas de que aquela frase falava.

⚠️ **E "do ERP" deixou de ser "tudo menos chamados":** com duas etapas nossas, o
que as separa é o **`situacao_id` nulo**, não o nome de uma delas. Duas travas
antigas filtravam pelo nome e passaram a contar errado — uma delas estourou com
`None < int`.

### Entrar não escreve no ERP; sair escreve

| gesto | rota | escreve no Harmonit? |
|---|---|---|
| pôr a OS na etapa nossa | `POST /api/paineis/operacao/etapa-nossa` | **não** |
| tirar (mover para coluna do ERP) | `POST /api/paineis/operacao/mover` | **sim** |

🚨 **Duas rotas, de propósito:** a `/mover` grava `situacaoId` no ERP, e a outra
não toca no Harmonit. Uma rota só, decidindo por dentro, seria o caminho errado
esperando acontecer.

🚨 **A ORDEM NA SAÍDA IMPORTA:** solta DEPOIS de a escrita no ERP dar certo.
Soltar antes deixaria o card fora da etapa nossa **e ainda na situação velha** se
o Harmonit recusasse — ou seja, o card sumiria das duas colunas.

### Sair FINALIZA o card, não o apaga

`desfecho = 'resolvido'`. 🚨 O histórico de passagens é o registro de que a
auditoria aconteceu, e apagar a linha levaria isso junto
(`pipeline_passagem` tem `ON DELETE CASCADE` no card).

### A exceção no arrasto é NOMEADA

A guarda dos dois mundos continua recusando card de OS na `Chamados`. O que
mudou é uma exceção **nomeada** para a etapa nossa que aceita OS — não um
afrouxamento da regra.

---

## `pipeline_etapa.recebe_situacao` e `formulario.etapa_destino_id` — as filas da Operação em relação aos outros painéis (migração 106, 11/11)

🔵 **Duas frases dele, e as duas são a mesma ideia:**

- *"não é nesse financeiro que deve nascer, como foi dito essas etapas finais do
  OP devem ser excluídas e deveria ter nascido no painel Financeiro, na etapa
  correta 'Nova solicitação'"*;
- *"fiz teste com form de aditivo e não abriu card no contratual como foi
  pedido"*.

### 📏 O que a medição achou antes de escrever uma linha

| achado | número |
|---|---|
| a OS **17119** (ressarcimento, termo 8947) nasceu na situação **15746** e apareceu na coluna *Financeiro* da **Operação** | — |
| passagens para 15746 / 15695 / 16492 no `os_passagem`, desde que o log existe | **zero** |
| o envio de aditivo dele gerou a solicitação **3437** com cards | **nenhum** |
| slugs no `chamado_os.PROBLEMA_POR_FORMULARIO`, que era o portão do card | **1** (`suporte`) |

🚨 **Ninguém moveu a 17119: ela nasceu ali.** O log não tem uma única passagem
para aquelas três situações — e eu era o suspeito.

### As duas colunas, e por que são duas e não uma

```sql
pipeline_etapa.recebe_situacao  -- "OS nesta situação do ERP mora NESTA etapa"
formulario.etapa_destino_id     -- "o card deste formulário nasce NESTA etapa"
```

🚨 **São dois caminhos diferentes, e misturá-los era o defeito:** a primeira é um
card que **o ERP cria** e nós apenas colocamos no lugar; a segunda é um card que
**nasce aqui**, sem OS, como os chamados do Suporte desde 29/10. O portão antigo
exigia estar no mapa de **problema do Harmonit** para criar um **card** — duas
coisas sem relação.

### 🚨 Por que o destino é DADO e não código

As 17 situações vivem em código porque **o ERP as manda**. O destino é o
contrário: é decisão dele, muda por painel e por formulário, e mudar não pode
exigir deploy — a mesma razão de `formulario.painel` ser coluna.

### As três que saíram, e para onde foram

| situação | ia para | agora nasce em |
|---|---|---|
| 15746 Financeiro | coluna da Operação | **PNL_1.4 › Nova solicitação** |
| 15695 Pós venda | coluna da Operação | **PNL_1.3 › Nova solicitação** |
| 16492 Contratual | coluna da Operação | 🔴 **PNL_1.5 › Elaborar contrato** |

🔴 **A terceira espera ele:** o Contratual **não tem** "Nova solicitação" — as
seis colunas que ele escreveu começam em *Elaborar contrato*. Inventar uma
coluna ali seria mexer numa lista dele. Mudar é **uma linha**, e há trava que
muda de alvo junto.

⚠️ **Tirar sem dar destino faria a OS sumir de TODAS as telas.** É o `M12` na
forma mais cara, e nenhuma suíte reclamaria — o card simplesmente não estaria
lá. Por isso a trava `test_toda_situacao_reenderecada_tem_etapa_que_a_recebe`
existe, e por isso as duas metades vieram no mesmo passo.

### O card é MATERIALIZADO, não calculado na hora

`pipeline.semear_os(os_do_erp)` cria a linha em `pipeline_card`.

🚨 **A escolha é deliberada:** se o quadro daquele painel fosse montado lendo a
ponte, ficaria **vazio** quando o FPSL ou o Harmonit caíssem — e o
`quadro_da_aba` existe com a promessa oposta (*"este quadro não pode ficar vazio
porque um terceiro caiu"*). Materializado, a queda de um terceiro impede card
**novo** de aparecer, e nunca apaga o que já está na tela.

🚨 **Idempotente pelo índice, não por consulta:** o
`idx_pipeline_card_os_unica` (migração 105) é quem garante. Conferir antes com
um `SELECT` deixaria uma janela entre a conferência e a escrita — e duas pessoas
abrindo o painel ao mesmo tempo é o caso comum, não o raro.
⚠️ **Mas card FINALIZADO não renasce:** o índice único só vale para
`desfecho IS NULL`, então uma OS já tratada voltaria a nascer a cada leitura.
A guarda extra olha também o card com desfecho.

### Quem semeia, e por que os DOIS

| quem | quando | por quê |
|---|---|---|
| `quadro("operacao")` | a cada abertura do painel | é o único lugar que **já** lia a ponte |
| `quadro_da_aba(...)` | se a aba tem etapa que recebe situação | ⚠️ sem isto, o card da OS financeira só nasceria quando alguém abrisse a **Operação** — um acoplamento invisível entre duas telas |

Os dois dentro de `try`: semear é efeito colateral e não pode tirar o quadro do
ar.

### Dois defeitos que só a medição no estado real mostrou

1. **O card não mostrava a OS.** `_card_do_chamado` põe `numero_ordem: None` de
   propósito — é esse nulo que mantém o card não-arrastável. Entrou uma chave
   **nova**, `numero_os`, só de exibição. ⚠️ Reusar o `numero_ordem` ligaria o
   arrasto para o ERP numa aba cujo mover escreve só no nosso banco.
   O card dizia *"Card 912"* — um número **nosso**, que não serve para procurar
   nada no Harmonit.
2. **A Operação dizia que as duas OS estavam "fora do quadro".** Não estão:
   estão em outro painel, por decisão dele. `fora_do_quadro` avisa *"há OS que
   nenhuma coluna mostra"* — usá-lo para OS **reendereçada** é a tela mentindo
   (`M12`). Entrou a conta `noutro_painel`, separada.

### O empate que a regra derivada errou

O destino de cada formulário é **derivado** do `painel` dele (a primeira etapa
daquele painel), e não escrito à mão em 16 linhas. A derivação acertou três
painéis e **errou um**: o Pós-venda tem **duas abas**, e *"a primeira por
ordem"* entregou **CES e NPS** na fila de **Treinamentos**. Pesquisa não é
treinamento.

⚠️ **Derivar é certo; derivação com empate precisa de desempate NOMEADO**, e não
do acaso da `ordem`. A exceção está no arquivo da migração, para quem
reconstruir a base chegar no mesmo lugar.

### A rolagem chegou às outras abas (item 1 dele)

`grep -c rolo PainelAba.vue` dava **0**; a Operação tinha os dois controles
desde 06/11. 🚨 **O `ref` não pode se chamar `quadro`:** naquela tela `quadro`
já é o ref do JSON do painel, e reusar o nome poria o elemento do DOM onde a
tela espera os dados — uma colisão que o Vue não reclama e que deixaria o quadro
sem desenhar.

⚠️ **A trava olha a ESTRUTURA, não o gesto:** o jsdom não faz layout, então
`scrollWidth` é sempre 0 e "arrastar e ver rolar" não prova nada. O que prova é
que os dois controles estão na árvore **ligados ao mesmo elemento que rola** —
e o defeito forjado (controle na árvore, `prop` nula) deixa exatamente essas
duas travas vermelhas.

---

## `formulario_convite` — o link do formulário pré-preenchido (migração 107)

🔵 **Pedido dele, 11/11:** formulários *"pré-preenchidos quando abertos pelo
botão dentro do chat"*.

Uma linha é **um convite**: um formulário + os valores que a Movisat sugere +
quem convidou e de onde.

| coluna | o que guarda |
|---|---|
| `bilhete` | 🚨 **o que viaja na URL**: opaco, `secrets.token_urlsafe(16)`, `UNIQUE`. Não deriva do `id` nem da data, então não se adivinha a partir de um convite conhecido |
| `slug` | o formulário. ⚠️ **Slug e não `formulario_id`**: é o slug que monta o link e é por ele que a página pública pede a definição |
| `valores` | `JSONB`, pelo **nome** do campo. 🚨 **Sugestão, nunca verdade** |
| `conversa_id`, `cliente_id` | de onde o convite saiu, para o rastro. Os dois podem ser nulos |
| `criado_por`, `criado_em` | quem e quando |
| `expira_em` | 🚨 **o convite vence** — 7 dias |
| `aberto_em`, `aberturas` | marca da primeira abertura e a contagem. ⚠️ **Marca, não trava** |
| `usado_em`, `solicitacao_id` | o convite virou solicitação. ⚠️ **Não invalida nada** |

### 🚨 Por que uma tabela, e não os valores na URL

O caminho curto seria `/f/suporte?cnpj=...&telefone=...`. **Isso põe dado de
cliente no endereço**, e endereço não é lugar de dado: ele entra no **log de
acesso do nginx** (que guarda a linha de requisição inteira, com a query
string), no **histórico do navegador** de quem abriu, no `Referer` de qualquer
recurso que a página carregue, e em **qualquer repasse do link** por WhatsApp ou
e-mail. ⚠️ **Base64 não resolve nada disso** — esconde do olho, não do log.

Então o bilhete viaja e os valores ficam aqui. Quem tem o bilhete lê os valores
**daquele** convite, por uma rota pública que devolve só `{slug, valores}`.

### As quatro decisões que a tabela carrega

1. 🚨 **Vence.** Link pré-preenchido é um ponteiro para dado de cliente: sem
   prazo, um link repassado no ano que vem ainda abriria a ficha de alguém.
2. ⚠️ **Abrir não gasta.** A pessoa recarrega a página, perde a aba, volta no
   dia seguinte — gastar no primeiro `GET` viraria *"o link não funciona
   mais"*, que é o pior jeito de proteger.
3. ⚠️ **Enviar não apaga.** O rastro de quem convidou quem fica; apagar
   deixaria a solicitação sem origem.
4. 🚨 **Os valores são sugestão, nunca verdade.** O envio continua validando
   tudo pelo `formularios.validar`. Se fossem verdade, um convite velho com CNPJ
   antigo gravaria o CNPJ antigo sem ninguém olhar.

### 🚨 A sugestão é por RÓTULO, não por tipo de campo

Medido nas 16 definições, e é o achado que desenhou o `SUGESTAO_POR_ROTULO`:

| armadilha | formulário |
|---|---|
| **dois** campos `phone` e **dois** `email`, e os segundos são *"... do novo titular"* | `rescisao` |
| **dois** `phone` (da empresa e pessoal) | `ficha-cadastral` |
| `double` é **CNPJ, CPF, RG e "Quantidade de veículos"** | quatro formulários |

⚠️ **Sugerir o telefone de quem está rescindindo no campo do novo titular não é
defeito de tela: é a pessoa errada escrita num termo.** Por isso o mapa é lista
fechada de rótulos, casa **exato** (sem acento, sem caixa) e só o **primeiro**
campo de cada rótulo recebe.

**Efeito medido e desejado:** a `ficha-cadastral` **não** recebe nome, porque
pede *"Nome completo do responsável em assinar o contrato"*, que não bate exato
com *"Nome completo"* — e quem fala no WhatsApp não é necessariamente quem
assina.

### Dois fatos do modelo que o código teve de obedecer

1. 🚨 **`conversa` não tem `cliente_id`** — só `contato_id`. O cliente vem por
   `contato.cliente_id`.
2. 🚨 **`cliente.tipo_pessoa` é INTEIRO** (`cadastro.TIPO_PESSOA`: `0` indefinido,
   `1` Jurídica, `2` Física, `3` Estrangeiro). ⚠️ **É ele quem decide se o
   documento vai no campo de CNPJ ou no de CPF, nunca o comprimento do texto** —
   cadastro com documento pela metade existe, e adivinhar pelo tamanho poria
   CNPJ no campo de CPF. `0` e `3` não sugerem documento nenhum.

### O índice

`idx_convite_da_conversa (conversa_id, criado_em DESC) WHERE conversa_id IS NOT
NULL` — a pergunta da tela do chat: *"quais convites desta conversa?"*. A busca
pelo bilhete usa o `UNIQUE`.


---

## 🆕 109 — o login do dia, a hora do estado e a memória do agente (13/11)

🔵 Três pedidos dele no mesmo dia: *"a regra precisa verificar se está logada de
fato"*, *"status a x minutos"* no chat interno, e *"coletar IP e quando eles
atualizarem ou mudar a pasta não perdermos de vista"*.

### `atendente.logou_em` — o login vira fato gravado

🚨 **Até 13/11 o sistema não sabia quem tinha logado.** O token é JWT e morre na
virada do dia; não existe tabela de sessão. O único sinal de presença era o
`painel_visto_em` (migração 067), que prova **aba aberta, não pessoa** — medido
no dia: o carimbo de quem estava **afastada** era de um minuto antes, com a
máquina ligada e ninguém na frente.

Quem carimba é `presenca.registrar_login`, nos **dois** caminhos de entrada
(senha e Google). Dentro da jornada o login põe `disponivel`; **fora do turno
só carimba a hora** — decisão dele: *"logar fora do turno não disponibiliza
status e nem conversas"*.

⚠️ **Nulo quer dizer "não logou desde a migração"**, e a fila lê isso como "não
logou hoje". Quem já estava dentro no dia da migração foi carimbado uma vez a
partir de `painel_visto_em` — um painel que falou hoje só pode estar usando um
token de hoje.

**Quem lê:** `presenca.logaram_hoje` (a trava da fila, no lugar de "o painel
está aberto") e a borda de início da jornada, que deixou de acordar quem não
logou.

### `atendente.estado_em` — a hora em que o estado mudou

Alimenta o *"ausente há 30min"* do chat interno (`chat.minutos_no_estado`).

🚨 **Por que coluna nova e não `atualizado_em`:** aquela é carimbada por nome,
foto, times e afastamento — usá-la faria a tela dizer "online há 2min" porque
alguém salvou o cadastro da pessoa. Carimbam-na todos os caminhos que escrevem
`estado`: borda da jornada, régua de inatividade, curativo, escolha manual,
afastamento e retorno, e o login.

⚠️ **Só muda quando o estado muda.** Em `registrar_acao` e no retorno de
afastamento a hora é condicional (`IS DISTINCT FROM`), senão cada mensagem
enviada reiniciaria o relógio de quem já estava disponível.

### `config.distribuicao_ordem` — a fila vira cadeia

A ordem como lista (`"28581,123,124"` = Ludmila, Erika, Claudia), no lugar dos
dois campos. 🚨 **`distribuicao_primeiro` e `distribuicao_reserva` continuam
existindo e continuam sendo escritos pela tela de hoje**: a lista nasce deles
quando está vazia, e `definir_config` **preserva a cauda** ao salvar — sem isso,
salvar na tela antiga apagaria o terceiro nome em silêncio.

### `config.ligacoes_senha_fixa` — o atalho do alistamento

A senha padrão (hoje `Movisat!@`, 🔵 trocada por ele em 23/11; efetiva
`MOVISAT`, porque `senha_fixa()` passa a `_limpar()`) aceita **além** da
derivada por HMAC, que continua
valendo. ⚠️ **Não queima janela**, senão o primeiro PC a usá-la trancaria os
outros. 🚨 Custo declarado por ele: quem souber a senha e um ramal alista um PC
naquele ramal; limite de tentativas por IP e certificado do PC continuam de pé.

### `agente_ligacao_evento` — o que mudou no PC do ramal

`agente_id` · `criado_em` · `campo` (`versao`, `pasta`, `ip`, `pc`) ·
`valor_antes` · `valor_depois`.

🚨 **Só mudança, nunca batimento.** A linha do agente guarda apenas o último
valor de cada coisa: trocar a pasta de gravação apagava o caminho antigo e, com
ele, a chance de achar as gravações que ficaram lá. São 8 agentes falando 2× por
dia — gravar cada passada seria ruído escondendo as poucas linhas que importam.

⚠️ **`None` não é mudança:** o agente 0.4 não manda pasta nem versão nova, e o
`COALESCE` do batimento preserva o que havia; anotar aqui criaria uma "mudança
para vazio" que nunca aconteceu. 📏 Em 13/11, **7 dos 8 agentes estavam na 0.4**.

---

## 🆕 17/11 — migração 110: os serviços do técnico com os nomes dele

🔵 Dele: a lista em dez linhas (`INSTALAÇÃO SIMPLES`, `COM BLOQUEIO`, `COM
LEITOR RFID`, `COM LEITOR BUTTON`, `CÂMERA`, `RETIRADA SIMPLES`, `RETIRADA COM
ACESSORIO`, `MANUTENÇÃO COM TROCA`, `MANUTENÇÃO SEM TROCA`, `SUBSTITUIÇÃO
VEÍCULO PARA OUTRO`), *"e tirar as redundantes"*, com as *"mesmas regras das
demais sobre o valor zero"*. Perguntado sobre os três pontos abertos, ele
decidiu: os quatro sem equivalente **ficam**; a substituição **mantém as duas
pernas**; as cinco variantes de instalação **entram**. **São 15.**

🚨 **RENOMEOU, NÃO RECRIOU, e é o que preservou o dinheiro:** `tecnico_preco`
aponta para `servico_tecnico(id)`, então o preço mora no **id**, não no nome.
Apagar e inserir de novo teria perdido os seis preços gravados. A migração põe o
nome antigo no `WHERE` de cada `UPDATE` e tem um bloco `DO` que **derruba a
transação** se faltar nome, sobrar nome velho ou o número de preços cair.

| id | era | passou a ser |
|---|---|---|
| 1 | Instalação | `INSTALAÇÃO SIMPLES` |
| 2 | Retirada | `RETIRADA SIMPLES` |
| 3 | Manutenção Local | `MANUTENÇÃO SEM TROCA` |
| 4 | Manutenção Troca | `MANUTENÇÃO COM TROCA` |
| 5 | Substituição Retirada | `SUBSTITUIÇÃO VEÍCULO PARA OUTRO - RETIRADA` |
| 6 | Substituição Instalação | `SUBSTITUIÇÃO VEÍCULO PARA OUTRO - INSTALAÇÃO` |
| 7–10 | Socorro, Laudo Técnico, Treinamento, Acompanhamento | **inalterados** |
| novos | — | `INSTALAÇÃO COM BLOQUEIO`, `COM LEITOR RFID`, `COM LEITOR BUTTON`, `CÂMERA`, `RETIRADA COM ACESSORIO` |

📏 **Medido antes e depois:** 6 preços, todos de um técnico (contato 91041), e
**6 depois** — os mesmos valores, agora sob os nomes novos. Ensaiado com
`ROLLBACK` sobre o dado real antes de aplicar.

⚠️ **As regras de valor zero não mudaram, e os novos entram nelas sem nada a
mais:** linha ausente ≡ nulo ≡ *"não oferece"*; **zero ≡ cobra zero**, que é
cortesia e é um fato; negativo recusado pelo CHECK de 085; `precos_para_orcamento`
leva só o que tem valor, e **zero entra**. Serviço novo nasce **sem linha** em
`tecnico_preco`, que é exatamente *"não oferece"* — ninguém ganhou preço.

⚠️ **Caixa mista de propósito:** a grafia dos onze é a dele, em maiúsculas; os
quatro que ficaram continuam como nasceram. Normalizar os quatro é decisão dele.

⚠️ **Não existe tela para o catálogo** (as rotas `POST`/`PUT
/api/tecnicos/servicos` existem e nenhum `.vue` as chama): mudar a lista é
migração.

---

## 🆕 17/11 — migração 111: a decisão do disparo mora na passagem

🔵 Dele: a caixa *"Deseja enviar aviso ao cliente?"* ao mover o card, e o "Não"
**registra no card**.

🚨 **A DECISÃO MORA NA `os_passagem`, e não numa tabela nova:** ela já é **uma
linha por movimento**, e o disparo é consequência de um movimento — um para um.
Tabela separada criaria duas versões do mesmo fato, e *"este movimento avisou o
cliente?"* passaria a ter dois lugares para discordar.

| coluna | o que guarda |
|---|---|
| `disparo_em` | quando o aviso foi enviado. Nulo = não foi |
| `disparo_recusado_em` | quando o operador respondeu **Não** |
| `disparo_texto` | o texto que **SAIU**, já editado e resolvido — não o molde |
| `disparo_por` | quem decidiu, enviar ou não enviar |

🚨 **CHECK `os_passagem_disparo_uma_decisao`:** enviado **ou** recusado, nunca
os dois. Sem ele, uma corrida entre dois cliques deixaria a linha afirmando as
duas coisas, e nenhuma seria confiável.

🚨 **É ESTA LINHA QUE É A TRAVA DE REENVIO.** Mover duas vezes para a mesma
etapa são **duas** passagens e podem ser dois avisos (movimento novo, fato
novo); a **mesma** passagem decide **uma vez só**. O `decidir_disparo` é um
`UPDATE` atômico que exige as duas colunas nulas — de dois cliques no mesmo
instante, um só passa. Quem envia **reserva antes**: marcar depois do envio
deixaria os dois cliques enviarem antes de qualquer um marcar.

⚠️ **E solta a reserva quando o envio falha** (`soltar_disparo`), para o
operador poder tentar de novo — mas **só enquanto `disparo_texto` é nulo**: com
texto gravado, o aviso aconteceu e não se desfaz.


---

## Migração 112 — o rastro do compromisso no Harmonit, **por OS**

🔵 Demanda dele, 18/11: reagendar e cancelar o compromisso também no Harmonit.

| coluna de `agendamento_os` | tipo | para quê |
|---|---|---|
| `harmonit_agendamento_id` | `bigint` | o `agendamentoId` **daquela OS** |
| `harmonit_vinculo_id` | `bigint` | o `ordemServicoxTecnicoId` daquela OS |
| `vinculo_criado` | `boolean` | **nós** criamos a linha do técnico? |
| `harmonit_em` | `timestamptz` | quando o rastro foi colhido |

🚨 **POR QUE EM `agendamento_os` E NÃO EM `agendamento`.** Um compromisso do
MoviZap cobre **N OS**, e no Harmonit **cada OS tem a sua linha de técnico e o
seu compromisso** — não existe "agendar as três de uma vez". A
`agendamento.harmonit_agendamento_id` (migração 070) guarda só o **primeiro**
id que voltou: serve para o selo *"foi para o Harmonit?"*, e **não serve para
apagar**, porque apagar com o id da OS errada arrancaria a linha errada.

⚠️ A coluna de 070 **fica onde está**. Ela não mente — responde outra pergunta,
e é a que o selo já no ar lê.

🚨 **`vinculo_criado` É O CAMPO QUE DECIDE SE CANCELAR PODE EXISTIR**, e isso
vem de medição, não de preferência. Na Velasco (OS 17105, 18/11), com vínculo e
compromisso descartáveis:

| hipótese | resultado |
|---|---|
| `AgendarTecnico` com o `id` do compromisso e data nova | 🔴 recusou: *"Erro ao alterar Evento: TecnicoJaAgendado"*; a data não mudou |
| a mesma rota mexendo em `statusCompromisso`/`motivoCancelamento` | 🔴 recusou igual |
| `DELETE(osId, id, agendaId)` | ✅ funcionou — **e levou o compromisso E a linha do técnico**; a OS ficou com zero linhas |

Ou seja: **não existe alteração de compromisso no ERP, e não existe cancelar o
compromisso deixando a linha.** Cancelar é apagar a linha. 🔵 Logo, a regra
dele: *"apaga, só se a linha for nossa"* — porque quando reusamos a linha de um
técnico que já estava na OS (🔵 *"usa a linha existente"*), apagá-la levaria o
vínculo e o compromisso de outra pessoa.

🚨 **`vinculo_criado` NULO é "não sei", e não é o mesmo que `false`.** As linhas
anteriores a esta migração nasceram sem o rastro: para elas não se sabe quem
criou o vínculo. Na prática não se apaga, igual a `false` — mas a tela pode
dizer a verdade (*"não sei de quem é esta linha"*) em vez de afirmar que é de
outro.

⚠️ **E reagendar cria o novo ANTES de apagar o antigo.** Apagando primeiro, uma
criação que falhasse deixaria a OS com **zero** compromisso: o técnico perde a
visita da agenda e ninguém percebe. Na ordem que está no código, a falha deixa
**dois** — visível, corrigível, e a frase diz qual sobrou. Errar para o lado do
excesso é recuperável; para o lado da falta, não.

🚨 **O caso que a medição obrigou e que não estava no desenho:** se o
compromisso novo nascer na **mesma linha** do antigo, não se apaga nada — o
`DELETE` levaria junto o compromisso que acabamos de criar.


---

## Migrações 113, 114 e 115 — a auditoria da OS e a fila das passagens

🔵 Desenho dele, 18/11: *"uma pode verificar e levantar, indicar os erros, e
disparar por outro que só vai reescrever, daí guardar os logs juntos para evitar
perca e depois devolve ao primeiro para validar e passar verde"* · *"assim op
não para de trabalhar e seguimos no background com a OS"*.

### 🚨 O fato que originou as três, e vale ler antes das tabelas

Na OS **17133**, em 18/11, a mesma rota do Harmonit, na mesma OS, **sem nenhuma
escrita entre as duas leituras**:

```
11:42:47  devolveu 251    -> o painel recusou a passagem como "alguem mudou no meio"
11:43:18  devolveu 16488  -> a passagem seguinte funcionou
```

Das 11:17 às 11:42 ela respondeu **o valor que escrevemos às 09:42**, ignorando
o de 09:49: um atraso de ≈1h54 que se resolveu sozinho. Foram **7 recusas,
todas falsas**, e o operador clicando porque nada acontecia.

🚨 **A pergunta que separa tudo o que vem abaixo:** o valor que o ERP mostra é
um valor que **nós** já escrevemos nesta OS?

| o ERP mostra | significa | o que se faz |
|---|---|---|
| valor **nosso**, escrita recente (< 1h) | a leitura dele atrasou | nada; espera |
| valor **nosso**, escrita antiga (> 1h) | a escrita se perdeu | reescreve |
| valor que **nunca escrevemos** | alguém mexeu no ERP | **nada** — o ERP está certo |

### `auditoria_os` (migração 113)

Uma linha por divergência. 🚨 **Uma tabela, não duas**, e é a parte do pedido
dele que mais importa: *"guardar os logs juntos para evitar perca"*. O auditor
levanta e fecha; o escritor anota as tentativas **na mesma linha**.

| coluna | para quê |
|---|---|
| `numero_os`, `coluna_nossa`, `situacao_do_erp` | os dois lados |
| `lido_em`, `cache_de` | a idade de cada leitura — divergência entre um dado de agora e um de ontem é dado velho, não divergência |
| `veredito` | ver abaixo |
| `tentativas`, `grupos`, `ultimo_erro`, `escrito_em` | o log do escritor |
| `fechada_em`, `fechada_como` | o fechamento, que é **sempre** do auditor relendo |

Índice único parcial `auditoria_os_uma_aberta`: **uma linha aberta por OS**, para
uma OS parada não criar uma linha por noite e a red flag não contar o mesmo
problema várias vezes.

### 🚨 Os vereditos (migração 114, e ela nasceu de um furo meu)

A 113 saiu com `veredito` em `aberta`/`atraso`/`nao_confirmada`/`resolvida`/
`desistiu`, e **toda divergência confirmada ia para o escritor**. O ensaio a
seco contra a produção — rodado antes de ligar a escrita — mostrou o problema:

```
OS 17054: o painel diz 251   e o Harmonit diz 16490
OS 17114: o painel diz 15696 e o Harmonit diz 16490
```

E o histórico de passagens diz o que elas são: escrevemos 251 em 29/10 e 15696
em 12/11, e **16490 nunca foi escrito por nós**. Alguém avançou essas OS dentro
do Harmonit. ⚠️ **O escritor iria reescrever a nossa coluna por cima** — puxando
a 17054 de *"Analise de Equipamentos Retornados"* de volta para *"Configurar
equipamentos e Sistemas"*, numa OS de cliente, desfazendo o trabalho de quem
fez a coisa certa.

A 114 separou:

| veredito | o que é | vai ao escritor? |
|---|---|---|
| `aberta` | em avaliação na rodada | — |
| `atraso` | valor nosso, escrita de menos de 1h | **não** |
| `escrita_perdida` | valor nosso, escrita de mais de 1h | **sim** — a única |
| `mudou_no_erp` | valor que nunca escrevemos | **não**, vira aviso |
| `nao_confirmada` | as duas leituras discordaram | **não** |
| `resolvida` | o auditor releu e fechou verde | — |
| `desistiu` | 3 grupos estouraram ou recusa de negócio | vira red flag |

### `os_passagem`, colunas da fila (migração 115)

| coluna | para quê |
|---|---|
| `pendente_desde` | 🚨 **nulo = não está na fila.** Enquanto preenchido, a coluna do card sai **daqui**, não do cache do FPSL |
| `tentativas`, `pendente_erro` | quantas vezes e o último retorno, em frase |
| `resolvida_em` | quando saiu da fila, **para qualquer lado** |
| `avisada_em` | para a mesma pendência não ser avisada em toda rodada do cron |

🚨 **A fila são linhas, não memória**: reinício não pode perder escrita. E mora
na própria `os_passagem`, que já é o registro de *"quem faz o que SEMPRE"* —
tabela nova seria um segundo lugar para a mesma verdade.

🚨 **Índice único parcial `os_passagem_uma_pendente_por_os`:** duas pendentes na
mesma OS seriam duas verdades sobre em que coluna o card está, e a tela teria de
escolher uma sem critério. A segunda passagem **atualiza** o destino — o
operador acabou de dizer para onde quer o card.

⚠️ **`ok` continua FALSO numa pendente**, e isso é de propósito: a OS não mudou.
O card anda, mas quem lê a linha não pode concluir que o ERP gravou. `ok` só
vira `true` quando a fila consegue escrever **e** a releitura confirma.

### Os números, todos dele (18/11)

| número | onde |
|---|---|
| **60s** entre passagens da mesma OS | `passagem.SEGUNDOS_ENTRE_PASSAGENS` |
| **3 grupos de 3** tentativas | `auditoria_os.GRUPOS`, `TENTATIVAS_POR_GRUPO` |
| **5 min** entre os grupos | `auditoria_os.SEGUNDOS_ENTRE_GRUPOS` |
| **1 hora** para atraso virar escrita perdida | `auditoria_os.HORAS_DE_ESPERA_DO_ATRASO` |
| **1 hora** para a pendência virar red flag | `passagem.HORAS_PARA_A_RED_FLAG` |
| **03:00** para o auditor rodar | o cron, quando ele mandar |

⚠️ Limite, filtro e teto são decisão dele: nenhum destes se muda sem a palavra
dele.

### Migração 116 — `auditoria_os.avisada_em`: o aviso sai uma vez

🚨 **Defeito meu, achado em 18/11 ao conferir o que a rodada SEGUINTE diria.** As
duas linhas que o ensaio a seco abriu —

```
OS 17054  mudou_no_erp  nossa=251    erp=16490  fechada=None
OS 17114  mudou_no_erp  nossa=15696  erp=16490  fechada=None
```

— ficavam com `fechada_em` nulo para sempre, e a red flag as pegava por
`veredito = 'mudou_no_erp' AND fechada_em IS NULL`. **As mesmas duas OS sairiam
na mensagem todas as noites, indefinidamente.**

⚠️ **E o problema é mais fundo que a coluna que faltava.** `coluna_nossa` é a
nossa última passagem confirmada, e ela **nunca** vai voltar a bater com um valor
que nós não escrevemos. A divergência é permanente por construção — avisar dela
sem parar é avisar de um fato que não tem conserto, e treina a pessoa a ignorar
o vigia. 🔵 Contra a regra dele que o resto do desenho respeita: *"aviso que
aparece todo dia vira aviso que ninguém lê"*.

| coluna | para quê |
|---|---|
| `avisada_em` | nulo = ainda não avisada. **Marcada depois de o envio dar certo** — marcar antes perderia o aviso se o WhatsApp falhasse |

A regra que isto fecha: **mudança feita no ERP é aceita, e aceitar é lembrar.**
`mudou_no_erp` **fecha a linha na hora** (não há o que fazer: o card já segue o
ERP, que vem do cache), avisa uma vez, e só volta a falar se o ERP for para um
**terceiro** valor que também não é nosso.

## Migração 118 — quem procura cliente na nossa base, e o documento do parceiro

🔵 Ele, 23/11: *"formulario de pagamento de parceiros esta errado, ele nao
precisa de cpf e cnpj, obviamente pois nao puxa de base alguma, devem ser
somente preencheiveis"*. E, sobre o botão: **tirar onde não há base**.

`formulario.busca_cliente` — `boolean`, **não anulável**, padrão **`false`**.
É quem decide se o CNPJ daquele formulário ganha o botão *Buscar*.

🚨 **O DEFEITO QUE A COLUNA FECHA, medido em 23/11.** O botão não era decisão
de ninguém: a tela o desenhava por `ehNovo && campo.validacao === 'cnpj'`, e
`FORMATO_NOVO = None` (desde 11/11) põe os 16 em `novo` — então **todo**
formulário com campo CNPJ ganhou o botão. O `cliente_por_documento` varre a
tabela `cliente`, que são os clientes **nossos**: parceiro técnico, fornecedor
ou interessado em teste gratuito nunca está lá. O botão aparecia, a pessoa
clicava, e a resposta correta era sempre *"não achou"* — comportamento certo
numa tela que não devia ter oferecido a busca.

🚨 **Fica ligada em SEIS**, e são exatamente os que têm a etapa "Contrato" com
CPF/CNPJ **escondidos** atrás da pergunta PF/PJ, cujo CNPJ identifica quem já
tem contrato: `SUPORTE`, `ADITIVO`, `ADMINISTRATIVO`, `FINANCEIRO`, `RESCISAO`,
`SUBSTITUICAO`.
⚠️ A `FICHA_CADASTRAL` fica **fora** de propósito: é a ficha de clientes
**novos** — quem preenche, por definição, ainda não está na base.

⚠️ **POR QUE COLUNA, E NÃO UMA LISTA NO `.vue`:** a mesma razão do `painel` e
do `formato`. Quem procura cliente é decisão dele, formulário por formulário;
em coluna, mudar de ideia é uma linha na carga — sem migração e sem build. A
fonte é o `BUSCA_CLIENTE` do `scripts/carregar_formularios.py`, e a coluna é
**reescrita a cada carga**, como o `painel`. Duas travas comparam banco ×
script (`tests/teste_etapas_dos_formularios.py`), porque foi a divergência
entre as duas verdades que quase apagou 55 validações em 11/11.

🚨 **E o documento do parceiro deixou de ser obrigatório — isto é dado, não
coluna.** Nos dois formulários de parceiro técnico (`PAGAMENTO_TECNICOS` e
`CREDENCIAMENTO`) o CPF e o CNPJ estavam **visíveis e os dois obrigatórios**,
sem nenhuma regra PF/PJ: pessoa física tinha de inventar um CNPJ para o botão
Enviar funcionar, e jurídica, um CPF. No `CREDENCIAMENTO` isso fechava a porta
de entrada do parceiro. Agora `obrigatorio = false` nos quatro campos, pelo
`AJUSTES` da carga.
⚠️ **Os campos FICAM, e a validação de formato também** — é o pedido dele ao pé
da letra (*"somente preencheiveis"*): ela só fala quando a pessoa escreve algo.
Campo vazio passa; CPF pela metade, não. Tirar as duas coisas juntas seria
passar a aceitar documento quebrado, que é outra decisão.
⚠️ Os de **cliente** (`TESTE_GRATUITO`, `FICHA_CADASTRAL`, `FORNECEDORES`)
**não entraram**: lá o documento é o próprio assunto do formulário, e afrouxar
seria mudança de régua. Decisão dele nesta rodada.

## Migração 119 — o comprovante de pagamento em arquivo (aba 2, `PNL_1.6`)

🔵 18/11: *"haverá campo para que em cada 1 dos artefatos de pagamento seja
inserido anexo que comprove o pagamento. Após o envio do anexo, abre o campo que
pede o valor inserido no documento."* 🔵 24/11: o anexo é **do MoviZap, no padrão
da observação da Operação**, e é **anexo completo — não só PDF**.

`pagamento_comprovante_arquivo (id, artefato_id, nome_original, caminho, bytes,
mime, criado_em, por)`, com índice por `artefato_id`.

🚨 **`artefato_id` NÃO É CHAVE ESTRANGEIRA, E ISSO É DESENHO.** O artefato de
pagamento vive no **SQLite do FPSL** (`pagamento_artefato`, no `fpsl.db`) e esta
tabela é **Postgres**: não existe FK possível entre os dois bancos. Quem confere
a existência é a rota, **pelo quadro da ponte** — `_artefato_no_quadro` em
`main.py` devolve **404 "não está no quadro"** antes de gravar, e **502** quando
o FPSL não respondeu (dizer "não está no quadro" sem ter lido o quadro mandaria
o operador procurar defeito no lugar errado). Pôr `REFERENCES` aqui seria mentir
sobre uma garantia que o banco não dá.

🚨 **A REFERÊNCIA NO FPSL É TEXTO, E NENHUM BYTE ATRAVESSA A PONTE.** O FPSL
guarda `anexo:<id>` no `comprovante_arquivo TEXT` que **já existe**, pelo
`guardar_comprovante` que **já existe** — sem migração daquele lado. A ponte é
JSON servidor-a-servidor (`X-Ponte-Key`), e caminho de disco atravessando-a
faria o FPSL guardar algo que só este servidor sabe ler. Quem põe nome e tamanho
no quadro é este lado, numa consulta só para o quadro inteiro
(`_anexar_comprovantes_no_quadro`) — por card seria N+1.

O molde é o `os_observacao_arquivo` (091): pasta própria
(`/home/claude/movizap_pagamento_comprovantes`), um diretório sorteado
(`uuid4().hex`) por arquivo, nome original só para exibir e para o download,
**lista branca** de extensão — a **mesma** `EXTENSOES_DA_OBS`, importada e não
recopiada, porque lista duplicada divergiria no dia em que alguém acrescentasse
um formato num dos dois lugares — e teto de 10 MB. ⚠️ **Recusa antes de escrever
no disco** (extensão, teto, vazio), para não deixar arquivo solto quando a linha
não vai existir.

🚨 **ESTA PASTA NÃO TEM BACKUP**, como as outras três de anexo: o backup leva o
**banco**, então a linha sobrevive e o arquivo não. Por isso
`GET /api/paineis/servico-dos-tecnicos/anexo/{id}` devolve **410** (não 500)
quando o arquivo sumiu do disco, com a frase.

---

## Migração 120 — o termo posto à mão no card (Contratual, `PNL_1.5`)

🔵 Ele, 25/11: *"os cards fechados na aba contratual devem ter o numero do termo
antes do nome do cliente: TERMO: '12345 - PASTELARIA VELASCO'"*; e sobre de onde
vem o número: *"o operador coloca a mão no card, pois só depois de assinado que
ele será gerado oficialmente"*.

Três colunas novas no **`pipeline_card`**: `termo` (text), `termo_por` (integer,
FK para `atendente` com `ON DELETE SET NULL`) e `termo_em` (timestamptz).

📏 **A medição que obrigou a migração.** O quadro do Contratual tem **6 cards e
nenhum com termo**, porque os seis são **solicitações sem OS** ("Aditivo
contratual", "Substituição de veículos") — e o termo **não é campo da OS** no
Harmonit: ele é extraído de dentro do corpo dela (`fpsl_weso/termo_da_os.py`).
As respostas dos formulários foram abertas uma por uma: há CNPJ, placas,
endereço e responsável, e **nenhum campo de termo ou contrato**. Entre assinar e
gerar a OS, o número não existe em lugar nenhum do sistema.

🚨 **O TERMO DA OS CONTINUA GANHANDO.** Quando a OS existe, o número dela é o
oficial e é ele que a tela mostra; `pipeline_card.termo` preenche só o vazio. O
card devolve **`termo_a_mao`** para a tela saber a origem — tela que mostra
número digitado com cara de oficial é tela mentindo (`M12`). E o campo de digitar
**só aparece em card sem OS**, senão a tela prometeria uma escrita que a regra do
servidor ignora.

🚨 **NÃO SE GRAVA `pipeline_passagem` AO PÔR O TERMO.** Medido: o `etapa_desde`
do card sai de `max(pipeline_passagem.em)`, então uma passagem a cada digitação
zeraria o contador de *"parado nesta etapa desde"* — justamente o que mostra card
esquecido. Quem conta a história deste campo são as colunas `termo_por` e
`termo_em`.

⚠️ **`CHECK pipeline_card_termo_tem_data`**: `(termo IS NULL) = (termo_em IS
NULL)`, a mesma régua que o `desfecho` já usa nesta tabela — data sem valor (ou
valor sem data) seria estado que a tela não sabe desenhar. Por isso **vazio
limpa os dois**.

⚠️ **Sem máscara no número**, e é decisão declarada: medi apenas **dois** termos
reais no Financeiro (8953 e 8958), e inventar formato a partir de dois exemplos
barraria dado verdadeiro. A coluna é `text`, a rota apara e limita a **20**
caracteres, e o `<input>` tem o mesmo teto.

🚨 **E o campo de digitar entrou no MESMO passo da coluna**, de propósito: medido
no mesmo dia, as quatro chaves `procfy_*` vivem no `/config` e **nenhuma rota as
escreve** — ninguém consegue preenchê-las, nem o owner. Coluna sem tela é dado
inalcançável, e esse defeito já existe nesta casa.

**Quem lê:** `pipeline.cards_da_aba` (as três colunas mais `qt.nome AS
termo_por_nome`) e `paineis._card_do_chamado` (a precedência e o `termo_a_mao`).
**Quem grava:** `pipeline.gravar_termo`, pela rota
`POST /api/paineis/operacao/chamado/{card_id}/termo`, com a permissão **da aba do
próprio card** — a mesma régua do `finalizar` e do `reabrir`.
**Travas:** `tests/teste_termo_posto_a_mao.py` (11) e
`src/contratual_termo_a_mao_2511.teste.js` (6).
