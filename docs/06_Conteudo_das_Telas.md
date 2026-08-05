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

### Abas por canal: sim, mas com uma só populada

```
┌ Todos (12) ┬ WhatsApp (12) ┬ E-mail (—) ┐
```

- **WhatsApp** é o único canal da Fase 1;
- **E-mail** aparece **desabilitada, com o motivo à vista** ("Fase 2"). Mesma
  regra do "Esqueci minha senha": aba que existe e diz por que não funciona é
  honesta; aba que some e volta depois muda a tela debaixo do usuário.

🚨 A consequência real não é visual: **`conversa.canal` precisa existir no
banco desde o dia 1**. Acrescentar coluna de canal depois de ter conversa
gravada é migração; nascer com ela é grátis.

### Layout

```
┌──────────────┬─────────────────────────┬──────────────┐
│ LISTA        │ CONVERSA                │ FICHA        │
│              │                         │              │
│ filtros:     │ balões                  │ cliente      │
│  · minhas    │ ...                     │ veículos     │
│  · sem dono  │                         │ contratos    │
│  · time      │ [ Encerrar Transferir   │ faturas      │
│  · estado    │   Adiar  Devolver IA ]  │              │
│              │ [ campo de texto      ] │ (do FPSL)    │
└──────────────┴─────────────────────────┴──────────────┘
```

**Cada linha da lista mostra:** foto/inicial · nome (ou telefone, se não
cadastrado) · última mensagem · há quanto tempo · **quem está atendendo** ·
etiqueta de papel (cor) · time.

⚠️ **Envio de arquivo fica visível e desabilitado**, com o motivo: *"Envio de
mídia entra na Fase 2. Recebimento já funciona."* O cliente **manda** áudio,
foto e vídeo e nós vemos — só não devolvemos arquivo.

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
