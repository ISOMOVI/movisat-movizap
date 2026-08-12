# 06 — Conteúdo das telas

**Proposta, 2026-08-05.** Responde às perguntas do usuário sobre o que vai
dentro de cada tela do registro. Nada aqui está implementado.

⚠️ **Depende de `02_Modelo_Dados` aprovado.** As telas de cadastro não nascem
antes do banco, e o banco não nasce antes da sua aprovação.

---

## 0. Antes de tudo: a chave da IA

🚨 A chave DeepSeek de `IA_agente_Movichat/.env` é **a que vazou no GitHub em
04/08** e ainda não foi rotacionada. O MoviZap pode usá-la — mas então nasce
sobre credencial queimada, e quem tiver o commit `2e2e877` fala com a IA por
nossa conta.

```
Rotacionar -> colocar a nova no .env -> LLM_PROVIDER=deepseek
```

O código de LLM vem pronto do MoviChat: `services/llm/` (706 linhas, gateway +
providers deepseek/groq + tool-calling). Não se reescreve nada.

⚠️ O `PROJETO.md` do MoviChat diz *"DeepSeek dormente — aguarda saldo"*. Isso é
retrato antigo: hoje `LLM_PROVIDER=deepseek` e o custo medido é
**~US$ 0,0027/mensagem**. Confirmar saldo antes de ligar a triagem.

---

## ATD_1.1 — Caixa de entrada

> ⚠️ **Reescrita em 12/08.** A versão anterior desenhava uma tela que nunca
> foi construída: abas por canal, botões *Adiar* e *IA*, foto do contato,
> etiqueta de papel colorida e coluna de time na linha. Nada disso existe, e
> faltava tudo que existe. Desenho que promete botão inexistente faz quem lê
> procurar na tela o que não está lá.

### Layout de hoje — duas colunas, não três

```
┌──────────────────────┬──────────────────────────────────────┐
│ LISTA                │ CONVERSA (ATD_1.2)                   │
│ [Todas][Sem dono]    │  cabeçalho · nome · telefone · estado │
│ [Minhas]             │  [Assumir] ou [Reabrir e assumir]     │
│ 🔍 Buscar conversa   │  ─────────────────────────────────    │
│ ──────────────────   │  🔍 Buscar na conversa      3/17 ↑↓   │
│ Iago Do Ó       2min │  ─────────────────────────────────    │
│ …boleto vence hoje   │  balões                               │
│ [não identificado]   │  ▸ gaveta do contato (abre por botão) │
│              [Assumir]│  ─────────────────────────────────   │
│ …                    │  [⇄][+][↩][⇤]            [Encerrar]  │
│                      │  [Responder][Nota interna]            │
│                      │  [ campo de texto                  ]  │
└──────────────────────┴──────────────────────────────────────┘
```

**A ficha do cliente com dados do FPSL (veículos, contratos, faturas) é a
`ATD_2.1` e ainda não existe.** O que existe é a *gaveta*, componente da
`ATD_1.2`, que mostra o que o Harmonit e o Bitrix sabem do número.

### Cada linha da lista

nome · há quanto tempo · prévia · selos · **[Assumir]** quando cabe.

- **O nome** sai de `nome_whatsapp || contato_nome || telefone`, nessa ordem.
  O apelido do WhatsApp vem primeiro porque 65% das conversas não têm vínculo
  com o cadastro — com o nome do cadastro na frente, a tela mostrava número
  cru quase sempre.
- **A prévia** é a última mensagem — **ou o trecho achado**, quando a conversa
  entrou na lista por causa do texto de uma mensagem e não do nome. Ver busca,
  abaixo.
- **Selos:** `não identificado` (fala do cadastro, não do nome) · nome do
  cliente · quem atende, ou `sem dono` · `encerrada`.
- **[Assumir]** aparece em conversa sem dono; em conversa encerrada ele vira
  **[Reabrir]**, e abre a conversa antes de perguntar.

### 🔍 Buscar conversa

Um campo só, e ele procura em **tudo que identifica a conversa**:

| Onde | Exemplo |
|---|---|
| apelido do WhatsApp | `ago` acha Iago, Thiago, Tiago, Yago |
| nome do contato e do **cliente** | `keeva` |
| telefone, **em pedaço** | `6168`, `998116168` (sem DDD), `(18) 99811-6168` |
| texto das mensagens, **inclusive notas internas** | `rastreador`, `boleto` |

🚨 **É `OR` em tudo, não escolha por formato.** Até 12/08 o código decidia
entre telefone *ou* nome pelo que tinha sido digitado: `998116168` não
normalizava (falta DDD), caía no ramo de nome e devolvia **vazio, sem dizer
por quê**. Escolher o campo pelo formato do que a pessoa digitou é adivinhar.

⚠️ **A nota interna entra na busca** — decisão do usuário em 12/08: *"a nota,
uma vez dentro da conversa, faz parte da conversa"*.

⚠️ **O girando só aparece depois de 3 s.** O normal é responder entre 5 e 30
ms; piscar indicador a cada tecla cansa mais do que espera nenhuma. Passando
de 3 s o silêncio é que engana, e a pessoa acha que travou.

---

## ATD_1.2 — Conversa

Vive **dentro** da `ATD_1.1`, na coluna direita — não é tela separada, embora
tenha rota própria (`/atendimento/{id}`) para dar link direto e para o log de
auditoria saber distinguir. As 16 rotas de API do atendimento exigem esta tela.

### A barra de ações

Quatro são **só ícone**, com `title` e `aria-label`; *Encerrar* mantém o texto,
por ser o fim do atendimento e o único que não deve depender de reconhecer
desenho.

| | Ação | O que faz | Confirma? |
|---|---|---|---|
| ⇄ | **Transferir** | manda para um time; **tira o dono** | modal com time + resumo |
| + | **Convidar** | chama atendentes; **vários de uma vez**, por caixa de seleção | modal |
| ↩ | **Devolver à fila** | larga sem fechar; fica sem dono | **sim** |
| ⇤ | **Sair da conversa** | some da sua lista; se você era o dono, a posse passa | **sim** |
| | **Encerrar** | vai para o Histórico; classificar é **opcional**, e fica no fim | **sim** |

🚨 **Convidar NÃO dá acesso.** Qualquer atendente com `ATD_1.2` já abre
qualquer conversa — **não existe isolamento por conversa**. O convite faz a
conversa **aparecer na lista** de quem foi chamado. Quem responde por ela
continua sendo o dono.

🚨 **O dono que sai passa a posse** a quem está acompanhando há mais tempo; sem
ninguém, a conversa volta para a fila. Fica gravado com motivo
`saida_do_dono` — não `manual`, que faria o histórico dizer que uma pessoa
transferiu à mão.

### Reabrir

Conversa encerrada mostra **[Reabrir e assumir]**. Até 12/08 encerrar era porta
só de ida: `responder` recusa conversa resolvida e a tela escondia a barra
inteira, então só o cliente escrevendo de novo trazia a conversa de volta.

🚨 **Reabrir esbarra no `ux_conversa_aberta`** — único em
`(canal_id, telefone_e164)` para conversa não resolvida, que é o que faz o
cliente que volta reabrir em vez de duplicar. Se ele já escreveu depois do
encerramento, existe outra conversa aberta: o sistema **não força**, avisa qual
é a conversa viva e manda falar nela.

⚠️ Reabrir limpa `resolvida_em` e `segundos_total`, que são métricas congeladas
no fechamento. Deixá-las preenchidas faria a `ATD_5.1` listar como encerrada
uma conversa que voltou a andar.

### Os balões

- **Nota interna** é amarela, centralizada, e diz **quem escreveu**. O nome
  sempre veio da API; a tela é que não o imprimia — meses depois, *"cliente
  pediu desconto"* não dizia de quem era.
- **Resposta enviada pelo painel** mostra o nome de quem respondeu no rodapé.
  O eco do WhatsApp (mensagem mandada pelo celular ou pelo sistema antigo)
  chega **sem atendente**, e aí não há nome a mostrar — não é defeito.
- **Mídia** aparece no próprio balão; ela vem no webhook em base64, não por
  download. Documento não é pré-carregado.

### 🔍 Buscar na conversa

Pergunta diferente da busca da lista: lá é *"com quem eu falei"*, aqui é
*"onde ele disse isso"*. Destaca as ocorrências, conta `3/17` e navega com ↑↓,
dando a volta nas duas pontas.

⚠️ **Roda no navegador**, sem rota nova: as mensagens já estão carregadas.

🚨 **Só acha o que foi carregado.** O teto é de 1.000 mensagens
(`conversas.TETO_MENSAGENS_NA_TELA`) e a conversa avisa quando está truncada —
*"não encontrado"* numa conversa cortada seria mentira. Nenhuma passou do teto
ainda: a maior tem 130.

⚠️ **A marcação é feita em pedaços, nunca com `v-html`.** O texto é o que o
cliente escreveu; montar `<mark>` numa string e injetar entregaria a tela a
quem manda a mensagem.

### Envio

⚠️ **Envio de arquivo fica visível e desabilitado**, com o motivo: *"Envio de
mídia entra na Fase 2. Recebimento já funciona."* O cliente **manda** áudio,
foto e vídeo e nós vemos — só não devolvemos arquivo.

🚨 **O destinatário não é parâmetro: sai da conversa.** Não existe caminho para
escolher para quem enviar, e é isso que impede o painel de virar ferramenta de
disparo — que é a `ATD_3.1`, com decisão própria.

---

## ATD_1.3 — Fila

**O que é:** conversas **sem dono**, esperando alguém assumir.

Chegam aqui por três caminhos:
1. a IA concluiu a triagem e transferiu para um time;
2. um atendente devolveu para a fila;
3. uma conversa adiada venceu o prazo e voltou.

**Não é** a caixa de entrada filtrada: a caixa mostra o que é seu; a fila
mostra o que **não é de ninguém** — e é responsabilidade coletiva.

```
Time         Esperando   Mais antiga   Ação
Suporte          3         12 min      [Assumir]
Financeiro       1          2 min      [Assumir]
Contratual       0            —
```

**Ordenação por espera, não por chegada** — quem esperou mais aparece primeiro.

🚨 **Assumir é atômico.** Dois atendentes clicando ao mesmo tempo: um ganha, o
outro recebe *"a conversa já foi assumida por Erika"*. Sem isso, dois humanos
respondem o mesmo cliente e ele vê a bagunça.

---

## CAD_1.1 — Clientes

### A base ainda NÃO existe. Nenhuma delas serve como está.

| Fonte | O que tem | Por que não basta |
|---|---|---|
| **Harmonit** | o cadastro comercial de verdade | é de terceiro, e a API mente no código de retorno |
| **Cache WESO** | 1.964 veículos, 3.748 rastreadores | **não tem vínculo veículo↔cliente** |
| **MoviChat** `Client` | empresas que usam o MoviChat | outro conceito — é quem contrata o chat |
| **FPSL** | consulta o Harmonit ao vivo | não guarda base própria |

**A base do MoviZap nasce vazia e é preenchida pelo sync do Harmonit.** É a
decisão de 03/08: *"o cadastro do MoviZap é o cadastro do ERP nascendo"*.

### A tela

Busca no topo (nome, CNPJ/CPF, telefone, placa) → lista → ficha.

🚨 **Busca por telefone usa o normalizado, nunca o que foi digitado.** O nono
dígito faz a mesma pessoa ter dois números.

Cada linha traz a **origem**: `harmonit` (cinza) ou `movizap` (azul). O sync
só toca linha `harmonit`; linha `movizap` é intocável.

---

## CAD_1.2 — Contatos

**As duas coisas, e é isso que dá trabalho:**

| Origem | Como nasce |
|---|---|
| `harmonit` | pelo sync de 12h |
| `movizap` | **automaticamente, na primeira mensagem de um número desconhecido** |

Quando um número novo escreve, o contato **já nasce** com o telefone, o nome
do perfil do WhatsApp e `origem = movizap`. O atendente completa depois.

🚨 **Não esperar o atendente cadastrar.** Se o contato só nascesse por
cadastro manual, toda conversa começaria órfã e o histórico se perderia.

### Papéis, e a sua ideia das cores

Um contato tem **papéis** (vários ao mesmo tempo):

| Papel | Cor sugerida |
|---|---|
| Cliente | 🔵 azul |
| Fornecedor | 🔴 vermelho |
| Parceiro | 🟡 amarelo |
| Técnico | 🟣 roxo |
| Lead | ⚪ cinza |

⚠️ **Isto não é "classificação" — ver `CFG_4.1`.** São duas coisas
diferentes com nomes parecidos, e confundi-las estraga o analytics:

```
ETIQUETA DE PAPEL  = o que a PESSOA é.      Dura para sempre. Automática.
CLASSIFICAÇÃO      = o que a CONVERSA foi.  Vale para uma conversa. Manual.
```

A cor do papel **é automática**, sim: sai do cadastro, ninguém marca à mão.

---

## CAD_2.1 — Atendentes

Do Chatwoot vêm 4: **Administrador, Karla Financeiro, Suporte Erika,
Comercial Claudia**.

### O que falta e você pediu

| Campo | Para quê |
|---|---|
| **Nome de exibição** | é o que o cliente vê. Hoje só existe login |
| **Jornada** (dias + horários) | 🚨 evita transferência fantasma |
| **Fuso** | fixo `America/Sao_Paulo`, mas explícito |
| **Estado** | Disponível · Ausente · Não perturbe |
| **Times** | a quais pertence |
| **Teto de conversas simultâneas** | evita empilhar tudo em quem é rápido |

### 🚨 Transferência fantasma

**O problema:** transferir para alguém que saiu às 18h e a conversa dormir a
noite inteira sem ninguém saber.

**A regra proposta:**

```
Transferir PARA PESSOA fora da jornada  -> avisa e sugere o time
Transferir PARA TIME sem ninguém on-line -> aceita, MAS marca "fora do
                                            horário" e a fila mostra em
                                            vermelho
Nenhum time disponível                   -> IA responde o horário de
                                            atendimento e registra retorno
```

⚠️ **Nunca bloquear a transferência.** Bloquear faz o atendente fechar a
conversa para se livrar dela — e aí o cliente some do radar de vez. Deixa
transferir, mas **deixa visível**.

### Ainda falta decidir

- **férias/afastamento** — jornada não cobre;
- **quem cobre quem** fora do horário;
- **plantão** (a Movisat tem central 24h? o papel existe no modelo);
- **o que acontece com conversa aberta quando a jornada acaba**.

---

## CAD_2.2 — Times

**Copiar os 7 do Chatwoot**, como você pediu:

| Time | Observação |
|---|---|
| Contratual | |
| Comercial | |
| Financeiro | |
| Suporte | |
| Geral | provável destino padrão da IA quando não souber |
| Pós Venda | |
| agendamento | descrição: *"Agendamento de instalacao/manutencao"* |

⚠️ Os ids 3 e 8 não existem — times apagados no Chatwoot. **Numeração nova
aqui**, sem herdar buraco.

Cada time ganha: **descrição** (a IA lê para decidir o destino), membros,
horário de funcionamento e destino de transbordo.

🚨 **A descrição do time é entrada da IA, não enfeite.** É por ela que a IA
escolhe para onde mandar. Time sem descrição = IA chutando.

---

## CFG_1.1 — Canais

Sim: é onde o QR aparece e onde se vê o que está conectado.

```
┌─────────────────────────────────────────────────────┐
│ ATENDIMENTO            ● conectado                  │
│ +55 18 9xxxx-xxxx  ·  Baileys/QR                    │
│                                                     │
│ Pareado em      05/08/2026 14:32                    │
│ Conectado há    2 d 04 h                            │
│ Última mensagem 05/08/2026 16:41                    │
│ Reconexões(24h) 0                                   │
│ Versão WA Web   2.3xxx                              │
│                                                     │
│ [ Reconectar ]  [ Desconectar ]  [ Ver QR ]         │
└─────────────────────────────────────────────────────┘
```

**Estados:** `desconectado` · `aguardando QR` · `pareando` · `conectado` ·
`caiu`.

**O QR expira** (~60 s no Baileys): a tela **conta o tempo e renova sozinha**,
sem pedir F5.

### Registro que fica

Toda mudança de estado vira linha: quando, estado, e o motivo quando houver.
🚨 **É isso que responde "desde quando parou de chegar mensagem?"** — pergunta
que sem histórico não se responde, só se chuta.

**Settings aplicadas no pareamento:** `groupsIgnore: true`,
`syncFullHistory: false`, `readMessages: false`.

---

## CFG_2.1 — IA, prompt

### As camadas do prompt

```
1. QUEM SOMOS       Movisat, rastreamento de frotas. Tom, tratamento.
2. O QUE PODE FAZER consultar cliente/veículo/contrato/fatura (tool-calling)
3. O QUE NÃO PODE   prometer prazo, dar desconto, cancelar, falar de valor
                    que não leu, inventar protocolo
4. COMO TRIAR       identificar quem é -> entender o que quer -> resolver
                    se der -> transferir com resumo
5. PARA ONDE MANDAR a descrição de cada time (vem do CAD_2.2)
6. QUANDO CALAR     🚨 humano assumiu = IA muda e não volta sozinha
7. LIMITES DO CANAL "envio de arquivo ainda não disponível" — a IA avisa em
                    vez de prometer e falhar
```

**Sem menu numerado.** Está no escopo e é o ponto do projeto.

### Receptivo, com as camadas do bot

O MoviBot tinha fluxo fixo. Aqui a IA faz o mesmo trabalho conversando, mas as
**etapas continuam existindo** — só não aparecem para o cliente:

```
identificar -> entender -> consultar -> resolver ou transferir -> registrar
```

🚨 **Prompt versionado, e a conversa grava qual versão a atendeu.** Sem isso,
"a IA respondeu errado semana passada" é irrespondível.

### O que a tela mostra

Versão ativa · editor · **rascunho testável antes de publicar** · histórico
com data e autor · botão de voltar para a versão anterior.

⚠️ **Testar antes de publicar não é luxo:** prompt ruim em produção responde
errado para cliente de verdade, e não tem `Ctrl+Z`.

---

## CFG_3.1 — Sincronização

### O ponto dela

Responder **"o cadastro está atualizado?"** sem ter que confiar.

```
Última execução   05/08/2026 12:00   ✅
Lidos 1.964 · Criados 3 · Atualizados 41 · Sem mudança 1.920 · Erros 0
Duração 42 s                        [ Sincronizar agora ]
```

### Log de erro: sim, e ele separa três coisas

🚨 **`ok` / `vazio` / `erro` são estados diferentes.** Foi por não separar que
um painel acusou **76% de falha num sistema saudável** — a numeração do
Harmonit tem buracos, e resposta vazia **não é falha**.

| Estado | Significa | Aparece como |
|---|---|---|
| `ok` | veio dado | contagem |
| `vazio` | id não existe no Harmonit | contagem, **não é erro** |
| `erro` | timeout, 500, formato inesperado | **linha no log, com o id** |

🚨 O Harmonit responde *"encontrado"* como `list` e *"não encontrado"* como
`dict` — e o `dict` é *truthy*. **Checar o tipo, não a veracidade.**

Cada execução guarda: quando, origem (cron ou botão), as contagens, duração e
os erros com id. **Sync que só diz "ok" não serve para nada.**

---

## CFG_4.1 — Classificações

**Isto é o motivo do FECHAMENTO da conversa — não o papel do contato.**

| | Etiqueta de papel (CAD_1.2) | Classificação (aqui) |
|---|---|---|
| descreve | a **pessoa** | a **conversa** |
| dura | para sempre | uma conversa |
| quem põe | automático, do cadastro | o atendente, ao encerrar |
| serve para | achar e colorir | analytics: *no que gastamos atendimento* |

Sugestão inicial: `Dúvida de fatura` · `Solicitação de instalação` ·
`Manutenção` · `Rastreador sem sinal` · `Segunda via` · `Cancelamento` ·
`Comercial` · `Outro`.

⚠️ **`Outro` precisa de campo de texto obrigatório.** Sem isso vira o vale-tudo
onde metade das conversas acaba, e o analytics morre.

**Obrigatória no fechamento** — item 11 do escopo.

---

## CFG_9.1 — Registro de telas

Já implementada. **Regra que passa a valer:**

🚨 **Mudou rota, título, ícone ou permissão de uma tela? Atualiza
`movizap/telas.py` no MESMO commit.** O registro serve navegação, permissão e
auditoria: se ele mentir, o menu leva ao lugar errado e o log de auditoria
aponta para uma tela que já não é aquela. **Código nunca é reaproveitado** —
reusar faz o log antigo mentir.

---

## O que falta, e você não perguntou

| # | O que | Por quê |
|---|---|---|
| 1 | **Perfil do próprio usuário** | trocar a própria senha. Hoje o usuário vem do `.env` |
| 2 | **Notas internas na conversa** | recado entre atendentes que o cliente não vê. Sem isso vira grupo de WhatsApp paralelo |
| 3 | **Respostas prontas** | as 10 frases repetidas 50x/dia |
| 4 | **Busca no histórico** | *"o que esse cliente falou mês passado?"* |
| 5 | **Mensagem fora do horário** | resposta automática dizendo quando volta |
| 6 | **Transferência com resumo** | a IA escreve 2 linhas do que já apurou. Sem isso o cliente repete tudo e a triagem não valeu nada |
| 7 | **Auditoria de quem viu o quê** | ficha tem dado de cliente; quem abriu precisa ficar registrado |
| 8 | **Sinal de digitando / lida** | o cliente sabe que tem alguém do outro lado |

**Recomendo para a Fase 1:** os itens **2** e **6**. O 6 principalmente — sem
resumo na transferência, a triagem por IA não entrega o que promete.

Os outros cabem na Fase 2 sem prejuízo.
