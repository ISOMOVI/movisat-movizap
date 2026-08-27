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

## O que mudou em 27/08 — a rodada dos ajustes

Todos vieram de frases dele, e a frase fica junto do item: é o que separa
demanda de invenção minha quando alguém ler isto daqui a três meses.

### `ATD_1.1` / `ATD_1.2` — Caixa de entrada

**O desenho da conversa** passou a ser o da opção *"Familiar"*, escolhida por
ele entre cinco mockups vistos lado a lado. A razão é de uso, não de gosto:
quem atende passa o dia no WhatsApp, e uma tela parecida com o que a pessoa já
sabe usar custa quase nada de treinamento. Papel com textura, balão branco na
entrada e verde na saída com bico, nota interna centrada e sem bico, hora à
direita, e **o tique no lugar da palavra** — `enviada / entregue / lida` é
vocabulário do CHECK do banco; ✓ e ✓✓ se leem sem pensar. `pendente` e
`falhou` continuam por extenso, que são os dois casos em que é preciso parar
e ler.

🚨 **O escopo foi dito duas vezes por ele: só o interior desta tela.** Menu
lateral, paleta da casa e as outras telas não mudaram — o padrão visual dos
quatro painéis (05/08) continua de pé.

🚨 **O balão tinha escapado do sistema**, e é a peça mais vista do painel:
usava `var(--raio, 12px)` — token que **nunca existiu**, então caía no valor
de emergência, em silêncio — e três `rgba()` escritos à mão. Agora tudo é
token (`--conversa-*`), e `teste_estilo_conversa.py` impede a volta.

**A busca da conversa abre por botão** — *"pode abrir de um botão, pois ocupa
muito espaço"*. Era uma faixa fixa na altura mais disputada da tela, e altura
ali é conversa visível. ⚠️ **Fechar limpa o termo**: com ele guardado, os
balões continuariam marcados e o contador sumiria junto com o campo — um
filtro ativo sem nada dizendo que existe.

**A ficha mostra o tipo mesmo sem cadastro** — *"lista para selecionar o tipo
ainda não aparece na Ficha do contato"*. Medido: `relacao` é coluna de
CONTATO, e **63% das conversas abertas não têm contato** (234 de 374). A ficha
ficava muda no caso mais comum. Agora mostra "Sem cadastro", que é o tipo que
a automação e a IA de fato usam, e diz que trocar exige vincular.
🚨 **"Sem cadastro" não entra no seletor**: `contato.relacao` tem 8 valores no
CHECK e este não é um deles — ele é chave da `relacao_automacao`. Oferecê-lo
faria a tela propor um valor que o banco recusa.

**Menção `@` em grupo** — ver `docs/02`. Só em grupo: fora dele o WhatsApp
ignora `mentioned`.

### `ATD_6.1` — Chat interno

**A barra alta de distinção** — *"design replicado de caixa de entrada do zap,
porém com barra alta evidente para distinção"*. O pedido é de desenho e a
razão é de **risco**: quanto mais esta tela se parecer com a caixa de entrada,
mais fácil escrever para o colega achando que é o cliente. Primeira coisa da
tela, largura toda, não rola junto, faixa grossa à esquerda.
⚠️ **Âmbar, não vermelho**: vermelho é erro, e aqui não há erro, há contexto.
Vermelho para o que é normal treina a equipe a ignorar vermelho.
⚠️ E o aviso **saiu do cabeçalho**: ele já esteve em três lugares ao mesmo
tempo, e três avisos iguais viram decoração que o olho pula.

**Excluir conversa** esconde para mim e não apaga para o outro — ver `docs/02`,
migração 038.

### `EML_1.1` — E-mail

**As 12 estrelas coloridas do Gmail somem da lista** — *"o tip 'YELLOW_STAR'
ajustar para 'Com estrela' como no gmail"*. A saída não foi traduzir:
`YELLOW_STAR`, `RED_STAR`, `BLUE_INFO` e as outras nove apontam para a **mesma
lista** que o `STARRED` já mostra como "Com estrela". Dois itens com o mesmo
nome seriam pior que um id feio.

**Tirar a estrela sai da lista** — *"tirar estrela não removeu ele da lista"*.
⚠️ **Só dentro de "Com estrela"**: na caixa de entrada, tirar a estrela não
muda nada sobre estar na caixa, e remover ali faria a mensagem sumir por um
motivo que não tem a ver com o lugar onde ela está.

**A assinatura por imagem voltou à tela** — *"assinatura por upload de imagem
oculto? onde foi parar"*. 🚨 **O backend estava inteiro desde a migração 017**:
rota de subir, de tirar, pasta por atendente, e o envio já embutia por CID.
Faltava só o controle na tela — o recurso existia e ninguém podia usar.
⚠️ Mostra o **nome** do arquivo, não a imagem: não há rota que devolva o
arquivo, e criar uma só para a prévia seria escopo que ninguém pediu.

**A leitura pagina, e o `puxar_desde` passou a valer** — *"pagine o gmail, o
puxar_desde tem que valer"*. 🚨 A listagem parava na primeira página e o Gmail
devolve os mais recentes primeiro: o cron relia os mesmos 40 a cada 2 minutos
e contava o resto como "repetidas", **com log de sucesso**. Faltavam 111
mensagens. A correção é a distinção entre **listar** (uma chamada por 500 ids)
e **baixar** (uma chamada por mensagem): o teto por execução foi para os
downloads, onde ele precisa estar.
⚠️ **Um número meu que a medição derrubou:** afirmei que o sistema "nunca
alcançou janeiro" olhando `recebido_em` — que é `now()`, a data em que o
painel importou. A data do e-mail é `enviado_em`, ia de 02/01 desde sempre, e
a lista já ordenava por ela.

### As 13 telas com cabeçalho — o ícone de ajuda

Ver `docs/03_Registro_Telas.md`, seção do `bi-question-circle`.

---

## CFG_0.1 — Configurações

**A casca com abas.** Criada em 27/08, a pedido do usuário: *"precisamos ter
uma aba para as configurações e os acionadores dos interruptores devem ficar
lá"*.

As seis telas `CFG_*` viraram abas dela — `IA`, `Canais`, `Automação`,
`Classificações`, `Sincronização`, `Telas` — e o grupo "Configuração" do menu,
que tinha seis linhas, passou a ter uma.

🚨 **NENHUMA DAS SEIS FOI REESCRITA.** Cada uma continua no seu arquivo, com
seu código, sua rota e sua permissão. As sete rotas montam a mesma casca, que
lê `meta.codigo` e abre na aba certa — é isso que faz **link antigo, favorito
e histórico do navegador continuarem funcionando**.

### A escada da IA — o motivo de tudo isto

Em 26/08 o usuário disse: *"não tem botão nenhum ali, nem por canal, nem por
prompt e nem por tipo"*. Os três botões existiam, **em três telas diferentes**,
e o journal mostrou que ele estava com o bundle certo — não era cache. O que
havia era um padrão:

| Onde | O que acontecia |
|---|---|
| `CFG_1.1` | "Ligar IA" era o **quarto botão de contorno** de uma fileira cinza |
| `CFG_5.1` | botão sempre `:disabled`, sem dizer o que o destravaria |
| `CFG_2.1` | a sala de ensaio **sumia inteira** quando faltava prompt — a tela escondia o caminho que levava ao prompt |

🚨 **A REGRA NOVA, E VALE PARA TODO DEGRAU: nada some.** Degrau travado fica
cinza, **com o motivo escrito** e o link para o degrau que o destrava. Botão
que desaparece não ensina nada; botão cinza que diz "precisa de prompt
publicado" ensina.

Os quatro passos, na ordem de uso:

| # | Degrau | Trava quando |
|---|---|---|
| 1 | **Prompt publicado** | nunca — é ele que destrava o resto |
| 2 | **Ensaio** | não há prompt publicado (o motivo vem do motor, não da tela) |
| 3 | **Tipos de contato** | o motor não está disponível. Mostra quantas pessoas os tipos ligados alcançam |
| 4 | **Canal de atendimento** | falta prompt, ou nenhum tipo ligado. **Desligar nunca trava** |

⚠️ **O passo 3 e o passo 4 são travas separadas de propósito.** Ligar um sem o
outro não põe a IA para responder ninguém, e a tela diz isso.

⚠️ **"Ligar IA" SAIU DA `CFG_1.1`.** O ato deliberado do `docs/04` continua
sendo um ato — a confirmação diz o que vai acontecer com o cliente do outro
lado, e o que **não** vai (a IA não responde nada que já esteja na caixa). Ele
só mudou de lugar. O chip **"IA no ar"** ficou em Canais: é estado, não
interruptor.

⚠️ **`aba_de` É APRESENTAÇÃO, NÃO PERMISSÃO.** As telas-aba continuam vindo em
`sessao.telas`, porque é essa lista que a guarda de rota usa. Quem não desenha
item de menu para elas é o `MenuLateral`.

🚨 **As provas montam o componente de verdade** (`src/configuracoes.teste.js`,
10 verificações). Três placares verdes deste projeto já não viram tela
quebrada: 677 com o painel derrubado, 1.322 com a trava só no comentário, 1.568
com o menu lateral morto. Teste que lê `.vue` como texto entraria na mesma
lista.

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

---

# Revisão das telas — 2026-08-25

> Escrito a partir dos pedidos do usuário em 25/08, com o estado de cada tela
> **medido no código e no banco antes de propor**. Substitui o
> `16_Repaginacao_das_Telas.md`, que era doc paralelo sobre este mesmo assunto
> e foi apagado: uma fonte só.

**Medido em 25/08:** 332 conversas (326 diretas, 6 grupos) · **211 sem cadastro
(64%)** · maior conversa com **776 mensagens** de um teto de 1.000 · 1.750 de
1.754 contatos como `cliente` · 5 atendentes ativos, nenhum com teto de
conversas · 7 times, todos com membro · 1 caixa de e-mail com 336 mensagens ·
Evolution **2.3.7** · escopo Google `gmail.modify` + `gmail.send`.

---

## INI_1.1 — no ar em 25/08

### A tela mostra desfecho, não só pendência

```
Objetivo:     a tela inicial responder "o que espera alguém" E "o que eu já
              concluí" -- o mini-CRM de atendimento que o usuário pediu
Hoje:         = o objetivo. Três faixas: o seu dia (esperando você,
              acompanhando, concluídos por você com período) · a operação (em
              aberto, sem dono, adiadas vencidas) · owner
Por quê:      decisão do usuário em 25/08. A régua anterior ("aqui não entra
              número, isso é relatório") era MINHA, e vale para VOLUME --
              mensagens processadas continua fora. Desfecho é o outro lado do
              que está aberto
Reavaliar se: a REL_1.1 nascer. Aí o que é análise sai daqui e fica lá; o que
              fica é o número do dia, com rota
```

### Canais só para owner, travado no servidor

```
Objetivo:     dado de owner não sair pela porta da frente
Hoje:         = o objetivo. `inicio.resumo()` não monta as chaves `canais`,
              `saude` e `alcance` quando quem pede não é owner
Por quê:      a CFG_1.1 é tela de owner desde sempre, e esta rota entregava a
              mesma informação para qualquer perfil. Esconder no `v-if` deixa
              a rota respondendo a quem souber pedir
Reavaliar se: — fechado
```

⚠️ No lugar, quem não é owner recebe **"Como você está configurado"**: perfil,
estado, jornada de hoje, times, filas que enxerga e se recebe transferência,
tudo só-leitura. Existe porque quem não é owner não abre CAD_2.1 nem CAD_2.2 e
não tinha **nenhum** lugar onde descobrir por que não vê uma tela ou uma fila —
a conclusão natural era "o painel está quebrado".

---

## ATD_1.1 / ATD_1.2 — caixa de entrada

### Concluir atendimento (no ar em 25/08)

Rótulo, comportamento e a coluna `resolvida_por` estão no `02_Modelo_Dados.md`.
O que é da tela: o botão diz **"Concluir atendimento"**, o modal avisa que a
conversa volta para "sem dono", e quando há gente acompanhando ele diz quantas
pessoas serão tiradas.

### A ordem da aba "Sem dono"

```
Objetivo:     "Sem dono" responder "o que ninguém assumiu ainda", em ordem de
              quem espera há mais tempo por resposta
Hoje:         ordena só por `ultima_atividade_em` -- e concluir não toca nesse
              campo, então a conversa concluída logo após a última mensagem
              FICA NO TOPO, acima de quem espera
Por quê:      o usuário descreveu o comportamento esperado em 25/08: a
              concluída "volta a ficar sem dono, mas vai para o fim da fila".
              Isso é ordenação explícita, não efeito colateral da data
Reavaliar se: — a construir no bloco 1: `ORDER BY (estado = 'resolvida'),
              ultima_atividade_em DESC`
```

### O botão `+` — falar primeiro com quem ainda não é cadastro

🚨 **Hoje não existe caminho de saída**: conversa só nasce quando CHEGA
mensagem (`garantir_conversa` roda no webhook). Não há tela para falar antes.

Spec, conforme o usuário em 25/08 (*"o foco do botão + seria enviar mensagem
para um número que ainda não temos salvo"*):

1. `+` logo depois da aba **Minhas**;
2. campo de número **ou** busca no cadastro;
3. 🚨 **valida se tem WhatsApp antes de enviar** — `/chat/whatsappNumbers`, que
   hoje só existe dentro de `scripts/verificar_whatsapp.py` e sobe para
   `evolution.py` como função. Cópia que diverge é defeito que esta base já
   pagou uma vez (ver `_condicao_busca`);
4. número que **não** tem WhatsApp não envia, e a tela diz isso — metodologia
   §4 proíbe enviar para `tem_whatsapp = false`;
5. envia a mensagem e abre a conversa já com dono (quem clicou);
6. **depois de enviar**, tenta identificar: casou com exatamente um cadastro,
   vincula; casou com vários, fica como sugestão, exatamente como a gaveta já
   faz hoje; não casou, nasce contato com `origem = movizap`;
7. **cadastrar cliente novo pela tela também entra** (resposta do usuário:
   "ambos").

⚠️ Um destinatário por vez neste caminho — não por regra de disparo, que caiu
(ver abaixo), mas porque este botão responde "falar com esta pessoa".

### Encaminhar entra, e a regra de "não é caixa de disparo" cai

```
Objetivo:     poder repassar o que já foi dito, de qualquer tipo
Hoje:         não existe. `enviar_texto` e `enviar_midia` são as duas únicas
              rotas do Evolution que o painel usa
Por quê:      decisão do usuário em 25/08: "pode sim, para todo tipo de
              mensagem, a regra que não é caixa de disparo pode cair já que
              voltamos ao projeto"
Reavaliar se: aparecer uso de encaminhar como disparo em massa. Aí o que
              falta é a ferramenta certa (lista, template, ritmo), não uma
              trava no encaminhar
```

⚠️ **Encaminhar não é disparo em massa.** Encaminhar leva uma mensagem
existente a destinatários escolhidos, com confirmação mostrando quais. Disparo
com lista, template e ritmo continua sendo outra construção — e quando for
pedida, o §4 da metodologia (ritmo, não rajada; teto por hora em código) vale
inteiro.

### Rolagem

```
Objetivo:     ninguém perder mensagem antiga, e a busca dentro da conversa
              nunca dizer "não achei" sobre algo que existe
Hoje:         1.000 carregadas de uma vez; a maior conversa tem 776
Por quê:      60 iniciais + 200 por vez, decisão do usuário em 25/08. A
              recomendação contrária do `05_Frontend.md` ("a saída é rolagem
              virtual, não baixar o teto") é justificativa escrita por MIM, e
              rolagem virtual está na lista de fechado como demanda que eu
              inventei
Reavaliar se: o navegador travar com 260 balões -- aí o problema é render, e
              aí sim a conversa é sobre virtualizar
```

🚨 **A busca dentro da conversa vai para o servidor no mesmo bloco.** Ela roda
hoje no navegador sobre o que foi carregado; paginar sem mover a busca faz ela
deixar de achar o que existe — e o usuário registrou em 25/08 que essa busca
"está ótima". É um item só, não dois.

### Margem lateral, e o que ela NÃO carrega

Faixa de 4px na borda esquerda do item, com **um significado só: conversa
direta × grupo**. É o fichário que o usuário pediu. "Não identificado" e
"concluída" continuam como chip — duas leituras na mesma faixa é a faixa não
querer dizer nada.

### Filtro por tipo de cadastro

Chips de `relacao` acima da lista, combináveis com Todas / Sem dono / Minhas,
entrando como mais uma condição no `listar()`. A busca de hoje já varre nome do
WhatsApp, nome do contato, nome do cliente, telefone inteiro e em pedaço, e o
texto das mensagens inclusive notas — nada disso muda.

### Ver ficha

Botão de contorno com o nome dentro (*"Ficha · Pastelaria Velasco"*) ou, sem
cadastro, *"Sem ficha — vincular"* em âmbar. Com 64% das conversas sem
cadastro, o segundo é o estado mais comum e é o convite para resolver.

---

## O que o WhatsApp tem e nós não temos — medido em 25/08

🚨 **Medido contra a instância real (Evolution 2.3.7)**, probando cada rota com
corpo vazio: 400 significa que a rota existe e recusou o corpo, nunca um envio.
Antes disso eu havia afirmado suporte de memória, que é o `M5`.

| Recurso | Rota | Estado |
|---|---|---|
| Reagir com emoji | `POST /message/sendReaction` | existe |
| Enviar áudio | `POST /message/sendWhatsAppAudio` | existe |
| Apagar mensagem enviada | `DELETE /chat/deleteMessageForEveryone` | existe |
| Marcar lida no WhatsApp | `POST /chat/markMessageAsRead` | existe |
| Enviar contato / localização | `sendContact` / `sendLocation` | existem |
| Digitando | `POST /chat/sendPresence` | existe |
| Arquivar conversa | `POST /chat/archiveChat` | existe |
| Responder citando | campo `quoted` do `sendText` | **parâmetro, não rota — só se prova enviando** |

Do nosso lado, faltam ainda: emoji no compositor, colar print (Ctrl+V), mídia
em tela cheia, rascunho por conversa, respostas rápidas (`/atalhos`), galeria
da conversa, fixar, silenciar grupo e info do grupo.

---

## EML_1.1 — e-mail

### Estrela, seleção e leitura

O escopo concedido é `gmail.modify` + `gmail.send` — o comentário no topo do
`gmail.py` diz `readonly` e **está errado**. Estrelar, marcar não lida e
arquivar não pedem consentimento novo.

Spec: ícone de estrela clicável na linha e no cabeçalho · caixa de seleção por
linha com barra de ações (lida · não lida · estrela · arquivar) · selecionar
tudo com contagem. *"Botão de leitura"* é **marcar como lida/não lida**,
confirmado pelo usuário em 25/08 — não é painel de leitura.

⚠️ Arquivar no painel arquiva **no Gmail também**, senão as duas caixas
divergem em uma semana e ninguém sabe qual é a verdade.

### Assinatura com imagem

`atendente.assinatura_imagem` existe desde a migração 017, guarda o **caminho**
(nunca os bytes) e `enviar._assinatura()` já a embute por **CID**. Falta rota de
upload e interface: duas abas, `HTML` e `Imagem`, com pré-visualização
renderizada; a ativa é a que sai no e-mail.

### Mais de uma caixa — cada um vê a que conectou

```
Objetivo:     um atendente poder ter a caixa dele e uma caixa compartilhada
              (sac@) lado a lado, sem login novo no painel
Hoje:         `email_conta` já é tabela de N contas e `ler()` já lê todas as
              ativas -- mas a listagem NÃO filtra por conta e
              `POST /api/email/enviar` faz `SELECT ... WHERE ativa LIMIT 1`.
              Com a segunda caixa, todo e-mail sairia pela primeira, calado
Por quê:      decisão do usuário em 25/08: "cada um vê a que logou no seu
              acesso... a Erika poderia logar o sac@movisat na caixa dela
              também, na outra aba"
Reavaliar se: alguém precisar ver caixa que não conectou -- aí quem concede é
              o owner, pela tabela de acesso, e não se duplica a caixa
```

🚨 **UMA caixa, N acessos — não N cópias da caixa.** `email_conta.endereco` é
UNIQUE e continua sendo: a caixa é sincronizada uma vez só. Quem vê é uma
tabela de ligação `email_conta_acesso (conta_id, atendente_id)`. Sem isso, o
dia em que a Karla também precisar do `sac@` esbarra no UNIQUE — e a saída
errada seria duplicar a conta, o que duplicaria a leitura e as mensagens.

Na tela: abas no topo, estilo pasta de planilha, com o endereço inteiro visível
na ativa e faixa de cor por caixa; o compositor herda a aba e mostra "De:" em
campo fixo; `conta_id` obrigatório na listagem e no envio — sem ele, erro,
nunca "escolhe a primeira".

### Design da tela

Três painéis fixos (pastas 240px recolhível · lista 380px · mensagem no resto).
Linha com remetente, assunto e trecho; não lida com barra de 3px à esquerda.
**Chip do cliente vinculado na linha** — é o que faz esta caixa valer mais que
o Gmail, e hoje o vínculo só aparece dentro da mensagem. Corpo com
`max-width: 68ch` pelo token `--largura-texto`, que existe e não é usado.
Compositor em gaveta lateral, não modal. Agrupamento por fio — `thread_externa`
é coluna e não é usada. Atalhos `j` `k` `e` `r` `s`.

---

## ATD_6.1 — chat interno

Estado hoje: pessoas e grupos misturados numa coluna, uma **fileira de botões
com o nome de cada atendente** embaixo, balões sem separador de dia, sem foto,
sem estado, `Ctrl+Enter` para enviar, sem busca, sem anexo, e o aviso "não
chega ao cliente" repetido **três vezes** na mesma tela.

Spec: seções **Pessoas** e **Grupos** com busca no topo (a fileira de botões
sai) · avatar com iniciais e cor derivada do nome — a função já existe pronta
na tela de e-mail · **ponto de estado no avatar**, de `atendente.estado`, que é
coluna e nenhuma tela usa · separador de dia e agrupamento de mensagens
seguidas · **Enter envia, Shift+Enter quebra linha** · um aviso de "interno",
não três · busca · linha divisória "novas" · anexo · menção `@nome`.

⚠️ **Continua sendo 1-a-1 mais grupos**, não canais por assunto — decisão do
usuário em 25/08: *"podemos criar grupos com os temas"*.

⚠️ **`Ctrl+Enter` fica na caixa de entrada.** Lá a mensagem vai para o cliente
e não volta; aqui é conversa de equipe, e a fricção não se paga.

### Emoji

Não existe biblioteca nenhuma no projeto (as dependências são Vue, vue-router,
bootstrap-icons e Vite/Vitest). **Grade própria, ~150 emojis curados, ~4 KB,
zero dependência**, servindo os dois compositores. Emoji é caractere de texto —
biblioteca só serve para *procurar*. Se faltar busca por nome, troca-se pelo
`emoji-picker-element` (40 KB) sem mexer no resto.

---

## CAD_1.1 / CAD_1.2 — clientes e contatos

🚨 **Cliente é EMPRESA, contato é PESSOA.** Cliente tem documento e **não tem
telefone**; contato tem os telefones (tabela própria, N por pessoa) e pode
existir sem empresa. **A conversa liga no contato, nunca na empresa** — um
número identifica quem fala, não a empresa do assunto; a empresa vem por
tabela, via `contato.cliente_id`. É por isso que existe a gaveta "Empresas
vinculadas": a mesma pessoa responde por várias.

Spec: mestre-detalhe lado a lado (hoje o detalhe abre embaixo da tabela e some
da vista) · ficha de cliente com contatos, telefones, se tem WhatsApp, últimas
conversas, últimos e-mails e **botão "Abrir conversa" por telefone** — hoje a
ficha não leva a lugar nenhum · filtro por relação e por "tem WhatsApp / não
verificado / não tem" (`tem_whatsapp` distingue NULL de false e isso não
aparece em tela nenhuma) · **marcação de relação em lote**, que é o que
destrava a automação por tipo · selo de origem · lista de duplicados por
documento ou telefone.

⚠️ Os papéis (assinar · central 24h · financeiro) continuam gravando e não
acionando nada. O aviso na tela fica.

---

## CAD_2.1 — atendentes, como controle de RH

### O teto de conversas simultâneas sai da tela

```
Objetivo:     a tela não prometer comportamento que não existe
Hoje:         `atendente.max_conversas` é gravado e LIDO POR NADA -- nenhuma
              fila, distribuição ou transferência consulta a coluna, e os 5
              atendentes estão com NULL
Por quê:      decisão do usuário em 25/08: "essa função não precisa"
Reavaliar se: existir distribuição automática. Aí o campo volta com o
              comportamento junto, não antes
```

A coluna fica no banco: removê-la exige migração para ganhar zero.

### Exclusão é desligamento, e desligamento solta as conversas

🚨 **Não existe apagar, e não deve existir**: `conversa`, `transferencia`,
`mensagem` e `chat_mensagem` apontam para o atendente, e apagar a linha faria o
histórico mentir sobre quem atendeu.

⚠️ **O que falta é o que o desligamento NÃO faz hoje.** Ele só grava
`ativo = false`: as conversas da pessoa continuam com ela, os times continuam,
a senha continua. Quem sai da empresa com conversas abertas deixa dono que
nunca mais entra. Spec: ação nomeada **"Desligar atendente"**, com confirmação
dizendo o que acontece, devolvendo as conversas dele à fila e informando
quantas, tirando dos times e revogando a senha no mesmo ato; lista com filtro
Ativos / Desligados.

### Jornada com interruptor

```
Objetivo:     poder montar a escala sem que ela passe a valer antes da hora
Hoje:         a jornada existe em tabela, não bloqueia nada, e nenhuma tela
              mostra se a pessoa está no horário
Por quê:      decisão do usuário em 25/08: "pode colocar interruptor na
              configuração do owner de usar jornada ou não, daí pode montar
              ela mas deixando desligado"
Reavaliar se: — o interruptor É a condição de reavaliar. Ligar é decisão do
              owner, na tela dele
```

Spec: grade semanal com blocos e total de horas · coluna "está no horário
agora?" usando `atendente.fuso`, que existe e não é usado · interruptor
`jornada_ativa` na configuração do owner, **nascendo desligado** · e enquanto
desligado, nada na fila muda de comportamento.

⚠️ Mesmo ligada, a jornada **avisa, não bloqueia** — bloquear faria o atendente
fechar a conversa para se livrar dela, e aí o cliente some do radar de vez.

Mais na ficha: acesso (último login, tem senha, entra por Google ou senha,
convite pendente — `convite_token` existe e não aparece), assinatura de e-mail,
e `transferivel` (migração 013), que é o "não me mandem conversa" e não está em
tela nenhuma.

---

## CAD_2.2 — times

Cartões em vez de tabela: nome, descrição (que é entrada da IA), membros como
avatares, transbordo como seta. **Cadeia de transbordo desenhada** — hoje é uma
célula com um nome e a cadeia inteira ninguém enxerga. Contagem de fila por
time no cartão. **Quem enxerga a fila deste time**
(`atendente_time_permissao` é eixo diferente de `atendente_time` e não aparece
em nenhuma tela; sem linha = vê a fila inteira, que é o padrão permissivo).

⚠️ Medido em 25/08: **os 7 times têm de 2 a 4 membros, nenhum vazio.** A
anotação de "3 times sem ninguém" é do **Chatwoot**, não daqui, e o bloqueio
que ela representava para a triagem por IA caiu.

---

## ATD_5.1 e ATD_3.1 — não mexer

Histórico e Informativos ficam como estão, por decisão do usuário em 25/08.

### ✅ Validado em 25/08 — o `+` e o filtro por tipo

Comportamento **real confirmado**, não spec:

| O quê | Confirmado |
|---|---|
| Número sem WhatsApp | recusa e **não cria conversa nenhuma** — nada é gravado antes de saber que dá para falar |
| Evolution mudo sobre o número | recusa também: `None` é "não sei", nunca "não tem" |
| Número já com conversa aberta | **abre a que existe**, não cria outra |
| Conversa nova | nasce com dono (quem clicou) e estado `humano` |
| Identificação | acontece **depois** do envio; um cadastro vincula, vários ficam como sugestão |
| Filtro medido | `sem_cadastro` 214 · `cliente` 126 · `tecnico` 0 · `sem_identificacao` 0 · sem filtro 343 |

`tests/teste_conversa_nova.py`, 18 testes, com envio e consulta ao WhatsApp
mockados por fixture `autouse` — depender de alguém lembrar de mockar é o
mesmo que não ter.

🚨 **A regra "o painel não é caixa de disparo" saiu dos docstrings** (decisão
do usuário em 25/08: *"elimine a regra e foco no escopo atual"*). O que fica no
lugar é a descrição do que cada função faz: `responder` responde uma conversa
que já existe; `iniciar_conversa` fala com quem ainda não escreveu.

⚠️ **Uma lição do próprio teste:** o mock de envio devolvia sempre o mesmo
`id_externo`, e a segunda mensagem sumia. Não era defeito do código — é a
trava de idempotência (`UNIQUE` em `mensagem.id_externo`) funcionando, porque
o Evolution reentrega. Mock que repete id acusa o código por defeito do teste.

### ✅ Validado em 25/08 — rolagem e busca dentro da conversa

O teto de 1.000 mensagens **saiu**. `TETO_MENSAGENS_NA_TELA` não existe mais, e
com ele saiu o aviso de "truncada" — ele existia porque não havia como buscar o
resto, e agora há.

| O quê | Confirmado na conversa 766, a maior (776 mensagens) |
|---|---|
| Abrir | 60 mensagens, `tem_anteriores: true` |
| Carregar anteriores | 200 por vez, e diz se ainda há mais |
| Busca | roda no servidor e alcança a conversa inteira |

**Paginação por cursor, não por `OFFSET`.** O cursor é o par
`(criada_em, id)` da mensagem mais antiga que a tela tem. Com offset, uma
mensagem nova chegando entre dois cliques empurra tudo e a pessoa vê a mesma
linha duas vezes, ou pula uma. E o par, não só a data: duas mensagens podem ter
o mesmo `criada_em` — o WhatsApp entrega em lote — e cortar pela data perderia
uma delas em silêncio.

🚨 **O acerto pode estar acima do que está carregado.** A busca vê a conversa
inteira; a tela, não. Sem tratar isso, o contador diria "3/7" e nada se
mexeria — pior do que não achar. `rolarAteAchado` carrega para trás até o balão
existir, com limite de voltas para nunca virar laço infinito.

⚠️ **O scroll é preservado ao carregar anteriores.** Guarda-se a altura antes
de prepender e recompõe-se depois; sem isso o conteúdo novo entra por cima e a
pessoa perde o lugar onde estava lendo.

### 🚨 O teto que quase se repetiu

A busca no servidor devolvia **exatamente 200** acertos numa conversa longa — o
próprio limite dela, calado. É a **mesma mentira por omissão** do teto de
1.000: quem procura conclui que achou tudo. Corrigido no mesmo bloco:
`TETO_ACHADOS_NA_CONVERSA` é declarado, a rota devolve `limitado`, e a tela
diz *"mostrando os primeiros 200 acertos"*.

Fica registrado porque o padrão é o que importa: **todo teto tem de aparecer na
resposta.** Um teto que ninguém vê não é limite, é dado sumindo.

---

# ✅ Validado em 2026-08-25 — o resto dos onze blocos

> ⚠️ **ESTA SEÇÃO EXISTE PORQUE EU PULEI A ETAPA 4 DO CICLO.** O `+`, a rolagem
> e a busca ganharam o "validado" no mesmo dia; os outros sete blocos foram
> entregues, testados e commitados **sem** o comportamento confirmado voltar
> para cá. Doc que descreve só metade do que existe manda quem lê procurar no
> código — e o código não conta por que uma coisa é assim.

---

## CAD_1.2 — classificar em lote

| O quê | Confirmado |
|---|---|
| Marcação em lote | teto de **500 por vez** |
| A resposta | diz **quantos mudaram**, não "ok" |
| Id repetido | conta uma vez |
| Id inexistente | não derruba o lote |
| Filtro por tipo | combina com a busca |

⚠️ **O teto não é medo do banco:** lote sem teto aceita "marcar a base inteira"
num clique, e não existe desfazer.

⚠️ **Pedir 40 e mudar 37** quer dizer que 3 já estavam assim — silêncio aqui
vira "marquei e não pegou".

🚨 **`cadastro.RELACOES` tinha ficado para trás da migração 029:** a rota
recusava, com "relação inválida", um valor que o banco aceita. Espelho que não
se atualiza junto vira mentira, e agora há teste lendo o CHECK do próprio banco.

---

## CFG_5.1 — Automação por tipo de contato

A tela que o registro de telas ganhou em 25/08. **Só owner.**

```
Objetivo:     a mensagem que chega ser filtrada antes de gastar atendimento
Hoje:         boas-vindas por tipo de contato, acionando de verdade e nascendo
              desligada. O interruptor de IA aparece TRAVADO, com o motivo
Por quê:      pedido do usuário em 25/08. `docs/09` item 4: configuração não
              afirma o que o código não faz -- e `canal.ia_ligada` é lido em
              quatro lugares sem que nenhum aja sobre ele
Reavaliar se: o `services/llm/` migrar. Aí o interruptor destrava num lugar só
```

| O quê | Confirmado |
|---|---|
| Ligar sem texto | **recusado** — mandaria mensagem em branco ao cliente |
| Grupo | nunca recebe saudação |
| Conversa em andamento | não recebe: só na **primeira mensagem de entrada** |
| Reentrega de webhook | não repete: a trava é `UPDATE ... WHERE boas_vindas_em IS NULL` |
| Autor da mensagem | `sistema`, não um atendente |
| Tempo de primeira resposta | **não** conta a saudação |

🚨 **CADA LINHA MOSTRA QUANTOS CONTATOS ALCANÇA.** Ligar "Cliente" hoje atinge
**1.750 pessoas** — o número precisa estar à vista na hora de ligar, e não
depois.

🚨 **`sem_cadastro` é linha da automação e NÃO é valor de `contato.relacao`.**
64% das conversas chegam de número sem contato nenhum: é o caso majoritário, e
sem essa linha ele não teria como ser configurado.

---

## EML_1.1 — o que entrou no e-mail

### Estrela, não lida, arquivar e lote

🚨 **NADA DISSO PEDIU CONSENTIMENTO NOVO.** O escopo é `gmail.modify` +
`gmail.send`; o cabeçalho do `gmail.py` dizia `readonly` e **estava errado**.
Foi a frase, não a permissão, que atrasou o recurso.

- `_mexer_rotulo` é **uma função, não três cópias**: estrela, não-lida e
  arquivar são a mesma chamada com rótulos diferentes
- **arquivar arquiva no Gmail também** — só aqui, as duas caixas divergem em
  uma semana e ninguém sabe qual é a verdade
- no lote, **um erro não derruba os outros**, e a dona da caixa é conferida
  **item a item**: um id alheio no meio de ids meus passaria despercebido
- `email_mensagem.estrela` é reflexo local do `STARRED`; quem manda é o Google

### Assinatura com imagem

Metade já existia desde a migração 017 e ninguém podia usar: a coluna estava
lá e `enviar._assinatura()` já embutia por **CID**. Faltava só a rota de
upload. O nome do arquivo **nunca vira caminho** — o diretório é nosso, por
atendente.

### Multi-caixa

```
Objetivo:     ter a caixa própria e uma compartilhada lado a lado, sem login
              novo no painel
Hoje:         = o objetivo. Abas por caixa, `conta_id` obrigatório na listagem
              e no envio, e cada atendente vê só o que conectou
Por quê:      decisão do usuário em 25/08. A migração 030 foi ANTECIPADA
              porque nenhuma rota filtrava por conta: o próximo login abriria
              a caixa do owner inteira -- 336 mensagens. Não dava erro
Reavaliar se: alguém precisar ver caixa que não conectou
```

🚨 **`POST /api/email/enviar` fazia `SELECT ... ativa LIMIT 1`.** Com uma caixa
acertava sempre; com a segunda, **todo e-mail sairia pela primeira**, calado, e
o destinatário responderia para o endereço errado.

⚠️ Caixa alheia responde **404, não 403**: dizer "existe, mas não é sua" já
entrega que aquele endereço está conectado por alguém.

### O fio, o cabeçalho e os atalhos

`thread_externa` era coluna desde a 014 e **nunca foi usada** — uma troca de
seis e-mails virava seis linhas idênticas. O maior fio da base tem 8 mensagens.
Cabeçalho fixo na leitura (rolar fazia sumir de quem a mensagem é) e atalhos
`j` `k` `r` `e` `u` `s`, **nunca dentro de campo de texto**.

---

## ATD_6.1 — chat interno

| Antes | Agora |
|---|---|
| pessoas e grupos misturados | duas seções, com busca |
| fileira de botões com o nome de cada atendente | some: buscar acha conversa E começa uma nova |
| sem estado | **ponto de estado no avatar** (`atendente.estado`, coluna que nenhuma tela usava) |
| balões sem separador | separador de dia e agrupamento de mensagens seguidas |
| `Ctrl+Enter` | **Enter envia, Shift+Enter quebra linha** |
| aviso "não chega ao cliente" **três vezes** | uma |

⚠️ **`Ctrl+Enter` fica na caixa de entrada**, onde a mensagem vai para o cliente
e não volta. Aqui é conversa de equipe: a fricção aparecia em toda mensagem.

**Emoji: grade própria, ~150 curados, ~4 KB, zero dependência.** Emoji é
caractere de texto — biblioteca só serve para *procurar*. `emoji-picker-element`
custa 40 KB e `vue3-emoji-picker` 90 KB, num bundle de 300 KB, para inserir um
caractere.

---

## ATD_1.2 — mídia do WhatsApp

Os cinco aprovados em 12/08, nunca começados até 25/08, mais o encaminhar.

| Recurso | Como ficou |
|---|---|
| **Reagir** | seis emojis, os mesmos do WhatsApp. **Emoji vazio TIRA a reação** — é assim que o WhatsApp desfaz |
| **Citar** | `quoted` é **campo do `sendText`, não rota**. Citar de outra conversa é recusado |
| **Áudio** | `sendWhatsAppAudio`, **não `sendMedia`** |
| **Tela cheia** | clique na imagem; a foto abria do tamanho do balão |
| **Colar print** | `Ctrl+V`, com nome carimbado pela hora |
| **Encaminhar** | até **5 por vez** (limite do próprio WhatsApp), chega como mensagem nova marcada |

🚨 **ÁUDIO PELA ROTA DE VOZ MUDA O QUE O CLIENTE VÊ.** Por `sendMedia` o mesmo
arquivo chega como anexo para baixar; por `sendWhatsAppAudio`, como mensagem de
voz com onda e tocar-seguido. A diferença é o recurso inteiro.

🚨 **A CHAVE DO WHATSAPP É RECONSTRUÍDA, NÃO GUARDADA.** Reagir e citar precisam
do trio `{remoteJid, fromMe, id}`; ele sai de `id_externo` + `direcao` + o
destino da conversa. Guardar o trio seria copiar o que já está lá.

⚠️ **Nota interna não reage nem é citada:** nunca foi ao WhatsApp, então não há
chave para apontar.

✅ **Encaminhar arquivo ENTROU em 26/08.** O arquivo é relido do disco e vai
junto com a legenda. O que esta nota dizia — mandar só a legenda seria pior que
recusar — continua valendo e virou regra: arquivo que sumiu do disco é
**recusado com o motivo**, nunca enviado só como legenda.

⚠️ **Reação do cliente ainda não é tratada:** chega como `reactionMessage` e cai
no ramo de "tipo ainda não tratado".

---

## CAD_1.1 · CAD_2.1 · CAD_2.2 — cadastro e operação

**Clientes:** a ficha mostrava dados e **acabava ali**. Agora traz últimas
conversas e e-mails com o id que abre a tela certa, botão **"Conversar"** por
telefone (**só onde há WhatsApp** — oferecer onde não há é oferecer erro), e o
alcance no topo, onde `tem_whatsapp` distingue NULL de false.

**Atendentes como RH:** em aberto, concluídas na semana, "está no horário
agora?" e total de horas.

```
Objetivo:     montar a escala sem que ela passe a valer antes da hora
Hoje:         interruptor `config.jornada_ativa`, nascendo DESLIGADO
Por quê:      decisão do usuário em 25/08
Reavaliar se: — o interruptor É a condição. Ligar é decisão do owner
```

🚨 **"SEM JORNADA" E "FORA DO HORÁRIO" SÃO ESTADOS DIFERENTES.** Sem a
distinção, quem nunca cadastrou escala aparece como fora do expediente — e isso
lê como defeito. Medido: nenhum dos 5 tem jornada.

🚨 **DESLIGAR SOLTA AS CONVERSAS.** O que faltava não era o botão, era o efeito:
desativar gravava `ativo = false` e nada mais, e quem saía com 12 conversas
abertas deixava dono que nunca mais entra — **invisíveis**, porque não aparecem
em "sem dono" (elas *têm* dono). Agora voltam para a fila, os times são
desfeitos e senha e `google_sub` são revogados. O histórico continua com o nome.

⚠️ **O teto de conversas saiu da tela**: era gravado e lido por nada. A coluna
fica no banco — removê-la exige migração para ganhar zero.

**Times em cartões:** fila por time, cadeia de transbordo desenhada em dois
elos, e **quem enxerga a fila** (`atendente_time_permissao`, eixo diferente de
`atendente_time`, que não aparecia em tela nenhuma). Lista vazia ali significa
que **todo mundo vê** — padrão permissivo da 001.

---

## O redesenho — e por que ele não é bloco separado

⚠️ **EU TINHA POSTO DESIGN COMO ITEM 13 DE 13.** O usuário corrigiu em 25/08,
olhando um filtro que eu tinha entregue como fileira de chips: *"ficou horrível
assim, onde foram parar as demandas de design e UX/UI?"*. Design deixou de ser
bloco e virou **condição de entrega** — nenhum bloco fecha com a tela em estado
pior do que começou.

O que mudou de fundo nas duas telas do dia a dia:

- **filtro dentro do campo de busca**, não numa fileira de chips: buscar e
  filtrar são a mesma pergunta, e separá-las enchia a coluna de botões
- caixa de entrada: **4 chips do mesmo peso viraram 2 números com hierarquia**;
  abas como controle segmentado; avatar com cor **derivada** do nome (a lista
  recarrega a cada 8 s — cor sorteada destruiria o reconhecimento); prévia
  truncada em uma linha (altura variável impede varrer); **separador de dia**
- e-mail: linha única virou **duas alturas de informação**; não lida com barra
  de 3px (negrito muda a largura das palavras e faz a lista tremer); estrela
  clicável fora do que abre; **chip do cliente na lista**, que é o que esta
  caixa tem e o Gmail não

---

## 🚨 A auditoria do mesmo dia — seis defeitos meus

Nenhum quebrava nada. Todos faziam a coisa errada em silêncio, com a suíte
inteira passando. Ficam aqui porque o padrão é o que importa.

| # | Defeito | Por que passou |
|---|---|---|
| 1 | **Encaminhar tornava quem clicou dono de até 5 conversas** | `responder` tem "quem responde assume", e encaminhar o reusava sem pensar. Há 336 conversas sem dono |
| 2 | **Encaminhar não exigia estar na conversa de origem** | era o único caminho de escrita sem `_exige_estar_na_conversa` |
| 3 | **A saudação dispararia em conversa em andamento** | a trava era só `boas_vindas_em IS NULL`, e as 332 conversas existentes têm o campo nulo |
| 4 | **A fila da automação era lista de módulo** | `processar_pendentes` roda no laço E na rota; o `clear()` de um apagava o do outro |
| 5 | **O microfone não era solto ao sair da tela** | tratei o `onstop` e esqueci a saída pela porta |
| 6 | **A citação não era limpa ao trocar de conversa** | o backend recusa, mas a tela mentia até a pessoa tentar |

⚠️ **O teste da automação passava porque a fixture criava conversa SEM MENSAGEM
NENHUMA** — um estado que não existe na vida real. Teste que monta cena
impossível aprova regra frouxa.

🚨 **A REGRA QUE FICOU:** *todo teto tem de aparecer na resposta.* A busca
devolvia 200 acertos calada — a mesma mentira por omissão do teto de 1.000
mensagens. Vale para qualquer limite novo.

---

# 2026-08-26 — o que mudou nas telas

⚠️ **ESTA SEÇÃO EXISTE PORQUE O DOC TINHA ATRASADO.** Ele perguntou, em 26/08,
se a documentação das telas estava em dia. Estava para o **registro** (as 20
telas do `movizap/telas.py` aparecem todas no `docs/03`), e **não estava para o
conteúdo**: este arquivo ainda dizia *"encaminhar arquivo ainda não"* depois de
o encaminhar arquivo existir. Ficou a trava
`tests/teste_telas_documentadas.py`, que reprova tela sem seção aqui.

## CFG_2.1 — a sala de ensaio

O `docs/04` sempre teve uma sequência de ativação de quatro passos: parear o
chip, conferir que a mensagem chega, **validar o bot respondendo**, ligar o
interruptor. O passo 3 não tinha como ser cumprido — não havia motor.

| O quê | Onde |
|---|---|
| Campo com o **número da conversa** e uma pergunta opcional | fim da CFG_2.1 |
| Devolve o texto, as **ferramentas** que ela usou e a **ação** que teria tomado | balão, no formato de mensagem |

🚨 **ENSAIAR NÃO É OPERAR.** Roda o motor inteiro — prompt publicado, catálogo
de ferramentas, modelo — e **não envia, não grava, não transfere e não liga
nada**. Ele mostra o que ela *teria* feito. Se ensaiar operasse, não seria
ensaio, e o primeiro erro da IA aconteceria em público.

⚠️ **A seção só aparece com o motor disponível.** Sem chave ou sem versão de
prompt publicada, no lugar dela fica o motivo escrito.

## CFG_5.1 — o interruptor de IA destravou

Até 25/08 o botão de IA aparecia **cinza com o motivo**, porque não havia
motor. Ele agora liga e desliga de verdade — e continua cinza, com o motivo,
sempre que o motor estiver indisponível. **A tela não decide:** `ia_disponivel`
vem do próprio motor.

🚨 **LIGAR AQUI NÃO PÕE A IA NO AR, E A TELA DIZ ISSO.** São duas travas
separadas de propósito: aqui é o **filtro por tipo de contato**; quem coloca no
ar é o interruptor do **canal**, na CFG_1.1. Sem esse aviso, alguém liga
"Cliente", sai da tela achando que a IA está atendendo, e nada acontece — o
pior tipo de silêncio.

⚠️ **O alcance aparece na hora de ligar:** *"ligar a IA aqui a coloca para
conversar com 1.750 pessoas"*. É o mesmo número que a saudação já mostrava, na
mesma lógica.

## CFG_1.1 — "Ligar IA", o ato

Botão novo no cartão do canal, e um selo **"IA no ar"** antes do estado da
conexão — é a informação mais consequente da tela.

🚨 **A CONFIRMAÇÃO DIZ O QUE VAI ACONTECER, E O QUE NÃO VAI:** que ela passa a
responder sozinha, e que **não responde nada que já esteja na caixa** — só o
que chegar depois do clique. Sem essa segunda frase, ligar responderia às 363
conversas abertas.

⚠️ **Só no canal de atendimento.** O informativo é disparo; a rota recusa e a
tela nem oferece.

## ATD_1.2 — reação do cliente

| Antes (até 25/08) | Agora |
|---|---|
| a reação virava **uma mensagem** `[reactionMessage — tipo ainda não tratado]` no meio da conversa | ela fica **pendurada no balão reagido**, como no WhatsApp |
| um emoji só, o nosso | **lista agrupada por emoji, com a contagem** a partir de 2 |
| — | a **nossa** fica com a borda de acento, no balão e no seletor |

🚨 **Eram 161 mensagens falsas em conversas reais.** 159 foram recuperadas para
o lugar certo e as falsas apagadas; **2 ficaram**, porque reagiam a mensagens
anteriores ao painel.

⚠️ **A conta só aparece a partir de dois.** Num grupo, "👍 3" é informação; numa
conversa direta, "👍 1" seria ruído em todo balão.

## ATD_1.2 — encaminhar arquivo

**O arquivo vai junto, com a legenda.** O aviso no modal diz isso antes do
clique, junto com o teto de 25 MB.

⚠️ **A falha agora diz o MOTIVO, não só o número.** "1 não deu" manda o
atendente adivinhar; com arquivo o motivo costuma ser o teto, e é isso que ele
precisa ler para não achar que o número está errado.

🚨 **Arquivo que sumiu do disco é RECUSADO.** Mandar só a legenda deixaria o
outro lado sem o anexo — e o balão diria "encaminhada".

## ATD_1.2 — a ficha ganhou o TIPO da pessoa

**Apontado por ele em 26/08:** a faixa mostrava empresa, CNPJ e e-mail, e não
mostrava nem deixava escolher o tipo — cliente, técnico, fornecedor, lead.

🚨 **ISSO DEIXOU DE SER ETIQUETA DE CADASTRO EM 25/08.** O tipo decide se a
**saudação automática** dispara e, desde 26/08, se a **IA atende**. Quem fala
com a pessoa é quem sabe o que ela é; mandá-lo a outra tela para marcar isso é
o caminho que ninguém faz.

⚠️ **Quem não tem `CAD_1.2` vê o tipo, mas não troca.** A rota exige essa
permissão, e oferecer um seletor que responde 403 é pior que mostrar o valor —
o frontend desenha, não decide.

## ATD_1.2 — o alinhamento do fio com o compositor

**Apontado por ele em 26/08**, e os dois defeitos eram reais:

| Sintoma | Causa | Correção |
|---|---|---|
| o campo de escrever parecia **mais estreito** que as mensagens | o fio usava `--e-3` de margem lateral e o compositor vive em `.cartao__corpo`, que usa `--e-4` — 4px de cada lado | o fio passou a usar o **mesmo token**, não um ajuste a olho |
| o fio rolava numa **janelinha** com metade da tela vazia embaixo | `max-height: 52vh` fixo | a coluna virou pilha com altura, e o fio **ocupa o que sobra** |

⚠️ **`max-height`, não `height`:** conversa curta continua sendo um cartão
curto, sem vão cinza embaixo. **Altura fixa em `vh` é chute sobre o monitor de
quem usa.**

⚠️ **A ficha também passou a saber encolher.** Com a coluna tendo altura, uma
ficha de pessoa com muitas empresas empurraria o fio e o compositor para fora
do cartão — e `.coluna { overflow: hidden }` cortaria **em silêncio**, sem
barra para rolar.
