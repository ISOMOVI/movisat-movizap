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

Um campo só, e o **filtro ao lado dele decide onde procurar** (30/09). No
padrão ele procura em quem a conversa é:

| Onde | Exemplo | No padrão |
|---|---|---|
| apelido do WhatsApp | `ago` acha Iago, Thiago, Tiago, Yago | sim |
| **nome do grupo** | `Tecnofrota`, `x3tech` | sim |
| nome do contato e do **cliente** | `keeva` | sim |
| telefone, **em pedaço** | `6168`, `998116168` (sem DDD), `(18) 99811-6168` | sim |
| texto das mensagens, **inclusive notas internas** | `rastreador`, `boleto` | **não — precisa ligar** |

🚨 **É `OR` em tudo, não escolha por formato.** Até 12/08 o código decidia
entre telefone *ou* nome pelo que tinha sido digitado: `998116168` não
normalizava (falta DDD), caía no ramo de nome e devolvia **vazio, sem dizer
por quê**. Escolher o campo pelo formato do que a pessoa digitou é adivinhar.

⚠️ **A nota interna continua na busca** — decisão do usuário em 12/08: *"a
nota, uma vez dentro da conversa, faz parte da conversa"*. O que mudou em 30/09
é que ela entra com o interruptor **"O que foi dito na conversa"** ligado, não
por padrão. A capacidade não saiu; o padrão saiu.

#### 🚨 Os dois defeitos achados em 30/09

**1. `grupo_nome` não estava na busca, e nenhum grupo era encontrável pelo
próprio nome.** Medido: das 15 conversas de grupo, **14 têm `grupo_nome` e
ZERO têm `nome_whatsapp`** — e só `nome_whatsapp` era olhado. Buscar
`Tecnofrota` devolvia **0** existindo dois grupos com esse nome. É a mesma
família do defeito do `assumir`, corrigido no mesmo dia: coluna de grupo
esquecida em código escrito para conversa direta.

**2. Um dígito solto no meio de letras arrastava a base inteira.** `x3tech`
tem o `3`, e o código montava `telefone_e164 LIKE '%3%'` — que casa com quase
todo telefone. A busca devolvia **100 conversas**, o teto da lista, e parecia
não fazer nada: ela respondia com a base cortada no limite, não com o que se
procurou. Era **isto** que o usuário estava vendo ao relatar *"quando busco por
x3tech, por exemplo, não muda muita coisa"*.

A regra nova: pedaço de telefone só quando o termo **não tem letra** (telefone
não tem) e traz ao menos 3 dígitos. `6168` continua achando o celular.

Efeito medido antes e depois:

| termo | antes | depois |
|---|---|---|
| `x3tech` | 100 (o teto) | **2** — os dois grupos |
| `Tecnofrota` | 0 | **2** |
| `weso` | 10, sendo 6 só menções | **4** — os grupos |
| `6168` | achava | achava |

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
`(canal_id, COALESCE(grupo_jid, telefone_e164))` para conversa não resolvida,
que é o que faz o cliente que volta reabrir em vez de duplicar. Se ele já
escreveu depois do encerramento, existe outra conversa aberta: o sistema **não
força**, avisa qual é a conversa viva e manda falar nela.

🚨 **ESTA LINHA DIZIA `(canal_id, telefone_e164)`, SEM O `COALESCE`, E ESTAVA
ERRADA — e foi essa descrição que guiou o defeito.** Até 30/09 a guarda do
`assumir` comparava só `telefone_e164`, que é **NULL em conversa de grupo**:
`telefone_e164 = NULL` nunca é verdade em SQL, a trava passava batido, o
`UPDATE` seguia e estourava o índice com **500 Internal Server Error** na cara
do atendente. **4 conversas de grupo** estavam nesse estado. O código seguiu o
comentário em vez do índice, e o comentário era este.

🔵 **E a ação oferecida ainda não é a certa.** Observação dele em 30/09: *"Se o
grupo já está aberto e com alguém, não deve ter reabrir e assumir, deveria
entrar pelo botão de entrar pois está em andamento"*. O mecanismo existe —
`conversa_participante`, migração 021, o "acompanhar" — e funciona: em 30/09
10:24:32 ele entrou na #55760 como participante e o dono (Thiago) continuou.
Mas **a tela só oferece "assumir"**, que em conversa com dono responde *"já foi
assumida por X"*: beco sem saída quando o caminho certo existe. 🔴 Pendente.

⚠️ **E a lista mostra várias linhas do mesmo grupo sem dizer qual é a viva.**
*"porque parece que tem duas conversas então?"* — porque `conversa` é **uma
linha por atendimento**, não por contato. O grupo "Suporte Movisat -> Weso" tem
3 encerradas e 1 aberta, nome idêntico nas quatro. 🔴 Pendente.

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

**Reagir e buscar, "como do externo" (16/10)** — *"verifique recursos de
reagir a mensagens internas, como do externo e pesquisar conteudo dentro das
conversar tbm"*.

- **Reagir:** botão de carinha nas ações do balão, os **mesmos seis** da Caixa,
  o meu marcado no seletor (clicar nele de novo tira). A reação fica pendurada
  no canto do balão; a conta aparece de **dois para cima**, e **passar o mouse
  diz quem reagiu** — diferença deliberada da Caixa: lá quem reage é o cliente
  e um "nós" coletivo, aqui são colegas. Apagada não oferece reagir.
- **Buscar:** lupa no cabeçalho da sala, mesmo gesto da Caixa (contador `3/7`,
  setas, `Enter` vai ao próximo, `Esc` fecha e **fechar limpa o termo**). Roda
  **no servidor** (`/api/chat/salas/{id}/buscar`), teto de 200 declarado.
  🚨 **A sala carrega as 500 mais recentes e não pagina**: acerto mais antigo
  que isso é achado e **dito** ("1 acerto é mais antigo que as mensagens
  mostradas aqui"), não rola para o nada nem vira "0" calado. Paginar o chat é
  outro trabalho — hoje a maior sala tem 330.
- **Busca da Caixa, junto (16/10):** passou a procurar também nas **conversas
  irmãs** (`_ids_do_historico`) — desde 07/10 a tela mostrava o fio inteiro e a
  busca olhava só a conversa aberta.

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

### Filtro: onde buscar, contato ou grupo, e tipo

Chips de `relacao` combináveis com Todas / Sem dono / Minhas / Time /
Bloqueados, entrando como mais uma condição no `listar()`.

🔵 **30/09 — três seções no painel do filtro**, pedido dele: *"no botão filtro
pode ter abas de opção como Contato; Grupos // Se é na conversa ou nome // e os
tipos em um grupo de 'Tipos' no filtro mesmo"*.

| Seção | O que oferece | Padrão |
|---|---|---|
| **Buscar em** | `Nome, telefone e empresa` · `O que foi dito na conversa` | só o primeiro |
| **Onde** | `Tudo` · `Contatos` · `Grupos` | Tudo |
| **Tipos** | os chips de `relacao` que já existiam | nenhum |

🚨 **"Onde" é FILTRO, NÃO ABA, de propósito.** A migração 027 criou uma aba
separada de grupo e a **028 desfez** — a decisão registrada é *"grupo e
conversa direta na mesma lista, como no WhatsApp"*. Um chip estreita quando se
pede; uma aba dividiria a lista por padrão e reabriria aquilo.

🚨 **Os dois interruptores de "Buscar em" não podem ficar desligados.**
Condição de busca vazia quer dizer "sem filtro", e a lista voltaria **inteira**
para quem digitou um termo — o pior resultado possível, e calado. A tela religa
o outro ao desmarcar o último; o backend, por garantia, cai no nome.

⚠️ **O padrão de `_condicao_busca` continua com mensagens LIGADAS**, porque a
função é compartilhada com o **Histórico** e mudar o padrão dela mudaria aquela
tela em silêncio. Quem nasce com mensagens desligado é a Caixa, em `listar`.

⚠️ **O placeholder do campo mudou junto**: era *"nome, telefone ou o que foi
dito"* e virou *"nome, telefone ou empresa"*. Com o conteúdo desligado por
padrão, o texto antigo prometia o que a tela deixou de fazer — o M12 outra vez.

🟡 **O que NÃO entrou, por decisão dele:** o selo de "por que esta linha casou"
(`no nome` / `na mensagem` / `no telefone`) e a contagem por escopo no topo do
resultado. Ficaram para depois.

### Ver ficha

Botão de contorno com o nome dentro (*"Ficha · Pastelaria Velasco"*) ou, sem
cadastro, *"Ficha · vincular"* em âmbar. Medido em 28/08: **231 das 381
conversas (61%) não têm cadastro**, então esse é o estado mais comum e é o
convite para resolver.

🚨 **O RÓTULO MUDOU EM 28/08, E POR UM DEFEITO MEU.** Ele estava escrito
*"Sem ficha — vincular"* desde 25/08 (`48bdfd4`), e ele disse: *"não vejo
mais a ficha nas conversas"*. A ficha estava lá o tempo todo — o botão é que
anunciava uma AUSÊNCIA em 61% das conversas, no lugar de anunciar uma porta.
A palavra "Ficha" agora abre os três casos; **o que distingue é o contorno
âmbar e o ícone, não a palavra**. Cor diz estado, palavra diz que coisa é.

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

🔵 **REPAGINADA EM 24/09, com as regras dele sobre os campos:**

| Campo | Owner | Admin | Atendimento/cadastro (Minha conta) |
|---|---|---|---|
| Nome de exibição | edita | edita | edita o próprio (*"pode ser alterado por todos os tipos"*) |
| E-mail | vê e edita | vê e edita | não vê (*"somente para admin e owner"*) |
| Login | vê e edita | não vê | não vê (*"oculto a todos menos owner, pois usamos o auth google"*) |
| Perfil | admin/atendimento/cadastro | atendimento/cadastro | só lê |

- **O Editar abre um modal** (`componentes/ModalEdicao.vue`): clique fora ou
  Esc, com mudança, pergunta *"Descartar"* / *"Continuar editando"*; no fim,
  *"Salvar"* / *"Cancelar alterações"*. Sem mudança, fecha direto. Arrastar
  uma seleção de dentro para fora não conta como clique fora.
- **Conta nova criada pelo admin nasce com login = e-mail**: o banco exige
  login e ele não vê o campo. Para ele, o e-mail é obrigatório na criação.
- **`owner` saiu do seletor de todos**: não se promove ninguém a owner, e a
  opção só dava erro ao salvar.
- 🚨 **"SEM SENHA" DEIXOU DE SER AVISO.** A entrada pelo Google casa pelo
  e-mail, sem senha (`google_auth.py`). A tela dizia *"conta sem senha existe
  mas não entra no painel"* -- falso para quem tem e-mail (os 11, medido em
  24/09; 2 deles sem senha). A coluna virou **"Entra por"**: Google, senha ou
  *não entra*.
- 🚨 **`offline` NÃO SE SALVAVA AQUI.** A Minha conta oferece quatro estados e
  o CHECK da 044 aceita quatro, mas `operacao.ESTADOS` tinha três: quem se
  marcasse *fora do expediente* não podia mais ser editado. Corrigido, e os
  rótulos agora são os mesmos da Minha conta.
- ⚠️ **PEDIDO DELE QUE NÃO ENTROU:** *"do Admin permite tem todos menos
  owner"* -- o admin deveria poder dar admin. A trava `_so_owner_da_admin`
  (🟡 minha) continua: removê-la foi barrado pelo classificador de permissões
  da sessão, e **ele decidiu mantê-la** (*"1 mantem, admin não vira owner"*).
- Resumo no topo (ativos, em aberto, concluídas 7d, sem como entrar), avatar
  com foto quando existe, times em chips.

🔵 **OS TIMES AQUI SÃO SÓ LEITURA DESDE 24/09** (mesma decisão, ver CAD_2.2):
chips com os times da pessoa e um link para Times. Desde a mesma data o
**admin** entra nesta tela, e duas travas 🟡 minhas o seguram: não edita a
conta do owner (o botão Editar nem aparece na linha dele) e não cria, promove
nem rebaixa admin — o seletor não oferece `owner` nem `admin` a ele. Para o
admin, o chip "Jornada" é só leitura: Configurações › Geral é do owner.

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

🟡 **REPAGINADA EM 24/09**: a edição abre no mesmo modal da CAD_2.1, com os
atendentes em cartões marcáveis; o cartão do time ganhou cabeçalho, contador
da fila em pílula, avatares sobrepostos e sombra ao passar o mouse. O texto
*"Três dos sete estão assim"* saiu do cabeçalho do arquivo: era do Chatwoot,
não daqui (corrigido na doc em 25/08, não no código).

🔵 **QUEM ESTÁ NO TIME SE DECIDE AQUI DESDE 24/09.** Decisão dele: *"vamos deixar a tela de times vincular os atendentes e no cadastro do atendentes pode ter os times dos quais são vinculados, mas só visualizar"*. O formulário do time ganhou **"Atendentes neste time"** (caixinhas dos ativos), e grava por
`PUT /api/times/{id}/membros`. Troca só o vínculo dos **ativos**: um inativo
que não aparece na lista não perde o vínculo por isso. A rota antiga
`PUT /api/atendentes/{id}/times` **saiu** — duas portas gravando o mesmo
vínculo, uma delas sem tela, é como uma some sem ninguém ver.
Desde a mesma data, a tela é permissão `equipe`: owner e **admin**.

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

---

# ✅ Validado em 2026-08-28 — a ficha, o modal de vínculo e os rótulos

> 🚨 **AS TRÊS COISAS DESTA RODADA SÃO O MESMO DEFEITO**, e nenhuma delas era
> função quebrada: em todas, o mecanismo respondia e a **palavra que levava
> até ele** tinha sumido da tela. Ele achou as três usando; eu não achei
> nenhuma com suíte verde e build limpo.
>
> ⚠️ **A trava nova:** antes de mexer em rótulo de botão que já existe, rodar
> `git log -S"<o texto atual>"`. Se a palavra já esteve na tela e saiu, é
> **regressão** e se trata como regressão — não como ajuste de desenho.

## ATD_1.2 — vincular empresa virou modal

Pedido dele: *"ao selecionar algumas empresas pelo campo de busca, na ficha,
para vínculo, não está exibindo claramente, verifique o uso de uma caixa
modal, acaba sendo uma saída para não ficar espremendo as coisas"*.

```
Objetivo:     escolher a empresa sem disputar altura com o resto da ficha
Hoje:         modal próprio (`painelAcao === 'vincular'`), 560px, com os
              candidatos por telefone antes da busca e a lista dos achados
              em largura cheia
Por quê:      a gaveta tem teto de 42vh e carregava, ACIMA da lista, o nome,
              o telefone, o botão de empresas, o Tipo, o selo do Bitrix, um
              parágrafo e o campo de busca -- os 10 resultados caíam em ~180px
              numa janela de 900px, com uma SEGUNDA barra de rolagem
Reavaliar se: o modal atrapalhar quem quer ler a conversa enquanto procura a
              empresa. Aí o certo é gaveta lateral, não modal
```

⚠️ **A gaveta ficou com o que é ESTADO** (quem é, que tipo é, o que o Bitrix
acha) **e o modal com o que é ESCOLHA.** Era a mistura dos dois no mesmo teto
que espremia.

| O quê | Confirmado |
|---|---|
| O teto de 10 da rota | **aparece na tela**: *"Mostrando as 10 primeiras"* |
| Empresa sem CNPJ | a linha diz **"sem CNPJ"**, não fica em branco |
| Fechar o modal | limpa o termo e os achados, como os outros painéis |
| O modal fecha | **no sucesso, não no clique** — falha precisa de lugar para aparecer |

🚨 **`limparPaineis()` passou a limpar o termo do vínculo.** Sem isso, quem
procura "Velasco", desiste e abre o vínculo de OUTRA conversa encontraria a
lista anterior já montada — e um clique ali vincularia a empresa certa ao
telefone errado.

## ATD_6.1 — "Criar grupo" voltou a ter texto

Ele perguntou: *"o botão de + não tem opção para criar o grupo"* e, depois,
*"não tínhamos uma demanda de criar o grupo que havia sido entregue?"*.

**Tínhamos.** A demanda é dele (*"podemos criar grupos com os temas"*, 25/08) e
a função foi entregue em **12/08** (`e6eaef8`), com o texto "Criar grupo" na
tela. Em **25/08** (`dbb0600`), refazendo o chat interno, **eu** troquei o
botão por um quadrado de 30px só com o ícone `bi-people`, deixando a palavra
apenas no `title`.

```
Objetivo:     a função entregue continuar achável
Hoje:         botão com ícone E texto, e `.ci__topo` com `flex-wrap` para o
              par busca+botão não se espremer na coluna estreita
Por quê:      regressão minha numa demanda dele já entregue -- a função nunca
              parou de funcionar e ficou inalcançável por três semanas
Reavaliar se: nada. É restituição, não escolha de desenho
```

⚠️ **`title` não é rótulo.** O balão do navegador demora cerca de um segundo e
**não existe em toque** — quem não passa o mouse nunca descobre o que o
quadrado faz.

## ATD_1.2 / EML_1.1 — a régua dos rótulos

**O ícone fica sozinho quando as duas coisas valem: é convenção do gênero e
mora colado ao campo que serve. Ganha palavra o que age sobre a conversa.**

O teste da régua era a própria barra de ações: **cinco botões só de ícone e um
com texto** — e o único legível era "Concluir atendimento", o que encerra.

🚨 **O par perigoso:** *devolver à fila* e *sair da conversa* eram **duas setas
apontando para a esquerda, lado a lado** (`arrow-return-left` e
`box-arrow-left`), fazendo coisas diferentes — uma larga a conversa para a
fila, a outra tira você dela.

| Ganharam palavra | Continuam só ícone |
|---|---|
| Transferir · Convidar · Devolver à fila · Sair · Arquivar (EML) · Criar grupo (ATD_6.1) | lupa · funil · clipe · microfone · emoji · X · anterior/próxima ocorrência · `+` nova mensagem · envelope de não-lida |

⚠️ **O `+` passa na régua e ainda assim confundiu.** "Nova mensagem" e "novo
grupo" são a mesma intenção para quem vem do WhatsApp, e no painel moram em
telas diferentes. Isso **não se conserta com texto no botão** — depende de
decidir se criar grupo do WhatsApp entra no escopo. **`evolution.py` só LÊ
grupo** (`participantes_do_grupo`, `nome_do_grupo`); criar não existe.

## EML_1.1 — a tela deixou de mentir sobre si

O cabeçalho dizia *"Por enquanto dá para ler e consultar. Responder pela tela
vem em breve"* — e a tela tem **Responder** (`Email.vue`), **Encaminhar**,
atalho `r` e a rota `/api/email/enviar` no ar. O `gmail.send` já estava em
`google_auth.ESCOPO_CAIXA`; o comentário de lá também dizia "SÓ LEITURA".

```
Objetivo:     a tela não anunciar capacidade que já tem, nem prometer o que
              já entregou
Hoje:         ícone de ajuda dizendo o que ela faz de verdade; os dois
              comentários obsoletos corrigidos no fonte
Por quê:      o texto era verdade quando foi escrito e nunca fez parte da
              entrega seguinte voltar e matá-lo
Reavaliar se: nunca. Texto que descreve capacidade existente é defeito
```

⚠️ **A trava:** entrega de função nova inclui **varrer o que a tela diz sobre
si mesma**. Tela que anuncia "vem em breve" ou recebe o recurso, ou perde a
frase — as duas coisas convivendo é a tela mentindo.

## Como isto se testa

`frontend/src/ficha_e_rotulos.teste.js`, **12 verificações**, monta as três
telas de verdade.

🚨 **ELE AFIRMA TEXTO VISÍVEL, NUNCA `aria-label` NEM `title`.** Foi
exatamente a confusão entre os dois que deixou o "Criar grupo" inachável: o
`aria-label` estava lá, perfeito, e a tela não dizia nada. `wrapper.text()` só
devolve o que está escrito — é a única afirmação que responde *"dá para
achar?"*.

⚠️ **Não substitui abrir a tela.** Isto prova que a palavra está no DOM; que
ela **cabe**, e onde, só o uso diz. Por isso esta seção fecha em *entregue*,
e vira **Validado** quando ele abrir.

---

## O tipo do contato: um campo, uma cara (28/08)

Pedido dele: *"o tipo… pode ser um botão menor e mais aderente ao design"*.

```
Objetivo:     o tipo ler como etiqueta, não como formulário, e ser o MESMO
              controle nas duas telas onde ele aparece
Hoje:         `<select class="campo__entrada campo__entrada--compacto">` na
              ficha da conversa (ATD_1.2) e na ficha do contato (CAD_1.2),
              com a classe definida UMA vez em `componentes.css`
Por quê:      pedido dele. E a primeira proposta minha (chip + popover só na
              conversa) foi recusada na validação: o mesmo campo passaria a
              ter duas aparências no mesmo sistema
Reavaliar se: a lista de 8 tipos crescer a ponto de o `<select>` nativo
              atrapalhar. Aí a saída é popover NAS DUAS, nunca em uma
```

🚨 **O QUE NÃO ENCOLHEU, E POR QUÊ.** `font-size` continua **16px** e a altura
**44px**: abaixo de 16px o iOS dá zoom sozinho ao focar, e 44px é o alvo de
toque mínimo — regra do padrão dos quatro painéis (05/08), que ganha do
"menor". O que encolheu foi a **largura e o peso**: o campo deixou de ocupar a
linha inteira, ganhou raio de chip e fundo `--superficie-2`.

⚠️ **Continua sendo `<select>` nativo.** Teclado, leitor de tela e a roda do
iOS vêm de graça; popover próprio reproduz isso com dívida.

⚠️ **Os dois tetos por tela saíram** (`.gaveta__tipo`, 12rem, e `.cad__relacao`,
14rem). Quem dimensiona é a classe compartilhada — teto por tela devolveria a
divergência que esta mudança existe para fechar.

### Como isto se defende

`ficha_e_rotulos.teste.js` afirma que **as duas telas usam a mesma classe**. É
afirmação sobre a fonte de propósito: ela não defende o render de hoje, defende
a **próxima edição** — foi por edição isolada numa tela só que o "Criar grupo"
e o rótulo da ficha se perderam.

### A pergunta dele que derrubou a proposta anterior

*"ficou aderente? recursos relacionados se mantêm? tem o melhor caminho?"* —
as três respostas mudaram o trabalho, e eu não as tinha feito antes de propor:

1. **Aderente: não.** O tipo já era `<select>` em `<dl>` nas duas telas; eu ia
   quebrar a consistência que existia, invocando o padrão `.filtro` — que é de
   escolha MÚLTIPLA sobre lista, e o tipo é valor ÚNICO de um registro. Peguei
   o padrão pela aparência, não pela função.
2. **Recursos relacionados: não todos** — ver a seção do E.1, ainda aberto.
3. **Melhor caminho: separar.** O controle menor não depende de decisão dele,
   não cria registro e não mexe em automação. Criar contato pela conversa
   carrega tudo isso e continua esperando.

---

## Migração 039 e o backup que não existia (28/08)

Ele perguntou: *"na aba 'minhas', porque continuam conversas lá que eu
encerrei?"* — e mandou auditar antes de corrigir: *"antes de rodar a migração
039, audite e valide backup"*. A auditoria achou coisa maior que a migração.

### 🚨 O backup do banco do MoviZap NÃO EXISTIA

O cron salvava o banco do hub-fotos (03:00) e o do MoviChat (03:30). O
`backup_projetos.sh` (02:00) empacota o **diretório** `movizap_painel` —
código, docs, migrações — e **não toca no banco**. Busca por qualquer `.sql`,
`.dump` ou `.pgdump` do MoviZap em `/home/claude`, `/var/backups`, `/opt` e
`/srv`: **zero arquivos**. São 192 MB, 37 tabelas, o histórico de atendimento
inteiro. Código se reconstrói do git; isto não.

Agora: `scripts/backup_db.py`, no cron às **02:40**, retenção de 14 dias.

- 🚨 **A senha sai do `.env` dentro do processo** e vai para um `.pgpass` 0600
  apagado no `finally`, inclusive quando o dump falha. Nunca em `argv` — os
  dois scripts antigos usam `PGPASSWORD=<valor> pg_dump`, e `argv` o `auditd`
  grava. É a regra que o `aplicar_migracao.py` já tinha escrito aqui.
- ⚠️ **O arquivo só vira definitivo depois de ABRIR** e de conter as 7 tabelas
  essenciais. Backup que não abre é pior que backup nenhum: dá confiança.

### O defeito que a própria verificação pegou

Na primeira execução o `pg_dump` gravou **SQL cru dentro do `.gz`**: passar um
`gzip.GzipFile` como `stdout=` do subprocess não comprime — o subprocess usa o
`fileno()`, que é o do arquivo de baixo. O `pg_dump` devolveu **0**, satisfeito,
e o arquivo ficou com nome de comprimido e conteúdo de texto. Quem pegou foi a
conferência, não o código de retorno. Hoje o dump vai por um cano e a
compressão é feita em Python.

### O backup foi VALIDADO, não declarado

1. `gzip -t` íntegro; **28 MB, 37 tabelas, 107.775 linhas**.
2. As 3 linhas-alvo estão no dump com o `atendente_id` de antes — prova de que
   ele carrega o que o rollback precisaria.
3. **Restauração de verdade**, em banco separado (`movizap_restore_teste`), com
   `ON_ERROR_STOP=1`: **zero erros**.
4. Contagem tabela a tabela contra o vivo. `conversa`, `contato`, `cliente`,
   `atendente`, `conversa_participante`, `email_mensagem`: iguais. `mensagem` e
   `webhook_evento` divergiam — e a divergência foi **provada** como tráfego
   posterior: o restaurado termina exatamente no evento **45876 (10:00:47)**, e
   toda linha a mais no vivo tem carimbo depois disso.
5. Banco de teste removido.

⚠️ **Restauração exige `vps-root`:** o papel `movizap` tem `rolcreatedb = false`.
Foi autorizado por ele para esta operação, e só para ela.

### A migração

```
Objetivo:     conversa concluída não ficar na lista de ninguém
Hoje:         as 3 concluídas do painel inteiro estavam com dono preso -- 100%
              delas --, e uma com participante sem `saiu_em`
Por quê:      a regra está certa desde a 029 (25/08 10:27); as três foram
              concluídas ANTES dela, a última por 1h40. A 029 mudou o
              comportamento e não corrigiu as linhas que já existiam
Reavaliar se: nada. É correção de dado, e não se repete
```

🚨 **A ORDEM É A REGRA.** `resolvida_por` era NULL nas três, e `atendente_id`
era o ÚNICO lugar onde o autor do fechamento existia — por isso a cópia e a
limpeza vão na MESMA instrução. E `saiu_em` recebe a data da **conclusão**, não
`now()`: datar com hoje faria o histórico dizer que a pessoa ficou dentro da
conversa por 11 dias.

**Conferido relendo o estado:** 0 resolvidas com dono · 0 participantes presos ·
`resolvida_por` preenchido nas três (2157 Erika, 12778 e 12826 Iago) ·
`conversas.listar(atendente_id=121)` devolve **0** · 82 testes de conversa,
conclusão, fila, participantes e caixa por atendente passando.

⚠️ **A 039 quase não rodou.** O `aplicar_migracao.py` recusa arquivo que não
registra a própria versão em `schema_migracao`, e a minha primeira versão não
registrava. Achado na auditoria de backup, não em teste.

⚠️ **O dump avulso foi apagado após o êxito, por decisão dele.** Fica o
`backups/db/desfazer_039.sql` — rollback de uma linha, com os valores lidos
imediatamente antes de aplicar — e a rotina diária a partir de hoje.

---

# ✅ Validado em 2026-08-28 — os textos educativos saíram das telas

Pedido dele, com a régua dentro do próprio pedido: *"as mensagens que ficam
aparecendo ainda estão pelo sistema todo, e já pedi ocultação dela… ocupam
espaços úteis… já entendeu o padrão? elas ajudaram nas etapas de lógica, mas
agora em teste 'sujam' a tela"*.

```
Objetivo:     a tela dizer o que É e o que vai ACONTECER, não por que ela foi
              desenhada assim
Hoje:         143 textos fixos de 6+ palavras no painel, e o que sobrou é
              rótulo, estado vazio, dica de campo e o conteúdo DENTRO do ícone
              de ajuda -- que é o texto já recolhido
Por quê:      pedido dele. O texto de projeto serviu enquanto a lógica estava
              sendo construída; em uso ele come a altura que é do trabalho
Reavaliar se: alguém de fora do time começar a errar o uso de uma tela por
              falta do texto. Aí a resposta é o ícone de ajuda, não a faixa
```

## A régua, e ela veio de um exemplo dele

> *"376 conversa(s) sem triagem. Quem atribui o time é a triagem, e a IA está
> desligada — então hoje a triagem é manual: abra, leia e transfira para o time
> certo. Quando a IA entrar, ela faz isso e estas caem nos times sozinhas."*

O número é **fato** e fica. Tudo depois dele é **aula** e sai.
**Corta-se a frase no fato.**

| Fica | Sai |
|---|---|
| número ao vivo | por que o sistema é assim |
| consequência no momento de agir | o que aconteceria se não fosse |
| o que fazer a seguir | história e data de decisão |
| limite de campo | código de tela e jargão de porão |

## 🚨 Duas telas estavam MENTINDO, e é a mesma falha

| Tela | O que dizia | A verdade |
|---|---|---|
| **E-mail** | *"Por enquanto dá para ler e consultar. Responder pela tela vem em breve."* | tem Responder, Encaminhar, atalho `r` e `/api/email/enviar` no ar |
| **Histórico** | *"classificar é obrigatório justamente para este histórico servir de analytics"* | deixou de ser obrigatório em **11/08** |

Os dois textos eram verdade quando foram escritos, e **nenhuma entrega seguinte
voltou para matá-los**. É o `M12`: função nova inclui varrer o que a tela diz
sobre si mesma. Agora com duas ocorrências provadas, não uma.

## 🚨 A varredura falhou QUATRO vezes por medir a forma da marcação

1. **27/08** — varri por `<h1>` + `<p class="apagado pequeno">` e entreguei
   **13 de 15** telas. Ficaram de fora exatamente as duas de prioridade: o
   E-mail (o `<h1>` de lá tem `class`) e a Caixa de entrada (o texto estava
   dentro do campo de busca).
2. **28/08, manhã** — corrigi as duas que ele citou e deixei a **idêntica** no
   Histórico (`campo__ajuda` sob campo de busca). Exemplo não é escopo.
3. **28/08, tarde** — varri por classe CSS (`apagado|pequeno|fraco|
   campo__ajuda|aviso`) e passei quatro lotes assim.
4. **Ele achou o que isso escondia:** *"A ficha do cliente entra aqui na
   ATD_2.1, consultando o FPSL"* — um `<p>` **sem classe nenhuma**, no estado
   vazio da coluna da conversa, que é a primeira coisa que se vê ao abrir a
   tela. Promessa de roadmap com código de tela dentro.

⚠️ **A varredura definitiva não olha classe:** lê TODO nó de texto de TODO
template, tira interpolação e atributo, e sobra o que a pessoa lê.
`scripts/` não guarda esse script porque ele é de auditoria, não de rotina —
mas o método fica escrito aqui: **varre-se o que está na tela, nunca o seletor
que eu supus que ele usa.**

## O que saiu, por tela

| Tela | O que saiu |
|---|---|
| **Caixa de entrada** | a promessa da ATD_2.1 · a lição da fila parada · encaminhar · convidar · concluir · a data "11/08" da classificação · o "vale-tudo" do comentário · o código ATD_5.1 · a checagem no WhatsApp · a explicação do tipo · a faixa de aviso de "não identificado", que aparecia em **61% das conversas** dizendo o que o botão da ficha já diz |
| **Fila** | cortada no número; e o rodapé sobre atomicidade do "Assumir" |
| **E-mail** | o cabeçalho falso · assinatura · imagem · compositor · vincular remetente · o vazio da caixa |
| **Histórico** | a faixa da busca (para o ícone) · o vazio que mentia |
| **Atendentes** | o Chatwoot e o "falha-fechado funcionando" · o porquê do desligamento · "conversa e transferencia apontam para ele" |
| **Informativos** | "não por recusarem WhatsApp" · o mecanismo do estado de entrega · "gente responde boleto" |
| **Contatos** | o parágrafo do bruto × E.164 · o "não para gerar demanda" dos papéis |
| **IaPrompt** | "o primeiro erro dela em particular" · o congelamento dos times · "o que ela estava lendo naquele dia?" |
| **Sincronização** | "insistir num servidor caído só piora" · o "que seria mentira" · metade da legenda |
| **Automação** | "botão que não faz nada é pior que botão nenhum" · o parágrafo da idempotência |
| **Times · Classificações · Canais · Registro · Sem permissão · Não encontrada** | as justificativas de desenho, mantendo a instrução |

## ⚠️ Corte não pode atravessar abertura de tag

Três cortes levaram junto um `<strong>` ou um `<span class="pequeno">` de
abertura e deixaram o fechamento órfão — `Contatos`, `Informativos` e
`Sincronização` ficaram com marcação inválida.

🚨 **A suíte passou com 75 verdes.** Nenhum teste monta essas três telas. Quem
pegou foi o `npm run build`. É o `M9` por outro lado: placar verde não vê nem
layout nem markup de tela que ninguém monta. **Build entra na conferência de
toda mexida em template, mesmo quando só se apaga texto.**

⚠️ **E o heredoc por `ssh` comeu o travessão**, de novo — terceira vez no mesmo
dia. O MIOLO já manda ir por arquivo + `scp`; passei a fazer assim no meio do
trabalho, e devia ter começado assim.

---

## O tipo não depende mais de empresa vinculada — E.1 (28/08)

Pedido dele: *"o tipo: 'cliente, teste, tecnico, etc' não precisa depender de
empresa vinculada para ter o campo"*.

⚠️ **Ele disse EMPRESA, não contato.** O tipo mora em `contato.relacao`, então
o que faltava não era o campo: era o **registro**.

```
Objetivo:     marcar o que a pessoa é sem precisar achar a empresa dela
Hoje:         escolher o tipo numa conversa sem cadastro CRIA o contato --
                sem empresa (`cliente_id IS NULL`), `origem='movizap'`,
                telefone com `origem_campo='atendimento'`, e nascendo já com
                o tipo escolhido. Rota `PUT /api/conversas/{id}/tipo`
Por quê:      pedido dele, e é o S9 respondido: 61% das conversas não têm
                cadastro, e sem linha em `contato` não havia onde gravar
Reavaliar se: começarem a nascer contatos duplicados do mesmo telefone quando
                o Harmonit trouxer a pessoa depois. A saída é fundir, não
                impedir de criar
```

### O que a validação provou ANTES de eu escrever

| Pergunta | Resposta medida |
|---|---|
| Pode existir contato sem empresa? | **sim** — `contato.cliente_id` é anulável |
| O painel pode criar? | **sim** — `origem` já aceita `'movizap'` no CHECK |
| O sync destruiria? | **não** — toda escrita filtra `origem='harmonit'`, inclusive `_inativar_sumidos` e o DELETE de telefone |
| O telefone conflita? | **não** — o índice único é `(contato_id, e164)` |
| 🚨 Alguém já exercitou? | **não. 0 dos 1.756 contatos existiam sem empresa** |

O último é o que mudou a postura: o schema permitia e **a vida nunca produziu
um**. Tratado como caminho novo, não como caminho existente.

### 🚨 Os quatro consertos que a validação achou

Sem eles a função "funcionaria" e estragaria o resto da ficha:

1. **Os candidatos sumiriam.** `conversa()` só calculava `candidatos` com
   `contato_id IS NULL`. Marcar o tipo cria o contato — e a pessoa perderia a
   lista que leva à empresa certa, **como castigo por ter classificado**. O
   critério passou a ser **sem empresa**, não sem contato.
2. **O selo do Bitrix sumiria junto**, pela mesma linha. Ele serve para ACHAR
   a empresa: vale enquanto ela não existe.
3. **A gaveta continuaria dizendo "Sem cadastro".** O template chaveia em
   `empresa.cliente`, e contato sem empresa devolve `cliente: None`. Ganhou o
   **terceiro estado**: *cadastro sem empresa*.
4. **O contato nasceria com o default.** `relacao` tem default
   `sem_identificacao` (migração 031) — criar e depois atualizar deixaria uma
   janela em que o contato existe dizendo o que ninguém disse.

### Decisões que ele deixou comigo, declaradas

- **Nome do contato:** apelido do WhatsApp; o telefone quando não houver.
  `nome` é `NOT NULL`.
- **`sem_identificacao` fora da lista de escolha:** é o valor de nascimento,
  não uma marcação. Continua em `RELACOES` porque é valor válido do banco.

### ⚠️ A automação troca de linha NA HORA, e a tela avisa

Sem contato, `automacao.chave_do_contato()` devolve `sem_cadastro`; com
contato, devolve a `relacao`. Boas-vindas e `ia_ligada` daquela pessoa passam a
seguir outra regra no instante da marcação. A resposta traz
`automacao_antes`/`automacao_depois`, e a tela escreve: *"Cadastro criado e
marcado como X. A automação por tipo passa a valer para esta pessoa."*

### 🚨 A permissão é ATD_1.2, não CAD_1.2

O perfil `atendimento` não tem CAD_1.2 desde 10/08. Exigir a do cadastro
esconderia o seletor justamente de quem está falando com a pessoa — que é quem
sabe o que ela é. Mesma razão da `buscar-empresa`.

### O que o banco me ensinou no caminho

🚨 **`ck_conversa_identidade`:** grupo tem `grupo_jid` e **não tem telefone**
(`tipo='grupo' AND grupo_jid IS NOT NULL AND telefone_e164 IS NULL`). Eu tinha
escrito o teste supondo que grupo era só um `tipo` diferente, e o banco
recusou. A regra estava no schema o tempo todo.

⚠️ **Um teste de 27/08 ancorava num COMENTÁRIO meu** (`"SEM vínculo: o caso
comum"`), que esta mudança reescreveu. Âncora em comentário é frágil: o
comentário é meu, e eu o reescrevo. Passou a apontar para o que a tela mostra,
e a afirmação ficou mais forte — exige a **escolha**, não só a exibição.

### Como se defende

`tests/teste_tipo_sem_empresa.py`, **11 verificações**, sendo **3 dedicadas aos
quatro consertos** — as que provam que a ficha não se estraga ao classificar.

---

# ✅ Validado em 2026-08-28 — os cinco que ele aprovou da minha lista

Ele mandou: *"3,5,6,7,13 pode validar e fazer, depois vemos os demais"* — cinco
das dezoito sugestões, todas minhas, nenhuma pedida por ele antes.

⚠️ **Esta seção nasceu de uma auditoria dele, não do meu ciclo.** Eu entreguei
os cinco, subi, e ele me chamou para o FPSL. Não voltei para fechar a etapa 4 —
foi ele quem perguntou *"veja se tudo foi documentado"*. É o
`feedback_documentar_antes_de_seguir` furado, e o furo tem a mesma forma de
sempre: o trabalho parece pronto porque está no ar.

## 3 — O freio do informativo (ATD_3.1)

```
Objetivo:     um disparo em andamento poder ser parado pela tela
Hoje:         botão "Pausar" ao lado de "Enviar próximos 20"
Por quê:      `POST /api/informativos/{id}/pausar` existia com ZERO
              chamadores. Envio em massa sem freio na tela
Reavaliar se: nada. É a rota que já existia ganhando porta
```

⚠️ **Só vale enquanto `enviando`** — é a condição do próprio backend. E quando
não vale, o botão **fica cinza dizendo por quê**, em vez de sumir: *"Só dá para
pausar um disparo em andamento — este está rascunho"*.

## 5 — Conectar a caixa de e-mail (EML_1.1)

🚨 **EU IA APAGAR ESTA ROTA.** Tinha proposto remover `/api/email/autorizar`
como duplicata de `/api/auth/google/inicio`. **Errado, e a validação pegou:**

| Rota | O que é | Escopo |
|---|---|---|
| `/api/auth/google/inicio` | **login** | `openid email profile` |
| `/api/email/autorizar` | **consentimento para LER a caixa** | `gmail.modify` + `gmail.send` + calendar |

Não são duplicatas. O que faltava era **o botão**: a única caixa da base
(`iago@movisat.com.br`, 10/08) foi conectada na mão, e a tela dizia *"peça ao
administrador"* — que também não tinha botão.

```
Objetivo:     o owner conectar a própria caixa pela tela
Hoje:         botão "Conectar minha caixa" no vazio da EML_1.1
Por quê:      a rota existia com zero chamadores desde sempre
Reavaliar se: mais de uma pessoa precisar conectar caixa. Hoje é CFG_1.1
```

⚠️ **Só aparece para quem tem CFG_1.1**, que é a permissão que a rota exige —
mostrar para os outros seria oferecer um 403. E navega na **mesma aba**: o
Google devolve para o nosso callback, e aba nova deixaria a original mostrando
"nenhuma caixa" para sempre.

## 6 — Motivo nos botões cinzas

A regra que ele aprovou na escada da IA — *nada some; o travado diz o que
falta* — estava aplicada nos degraus da IA e em lugar nenhum mais.

🚨 **NÃO SÃO OS 17 BOTÕES DESABILITADOS, SÃO NOVE.** Oito ficam cinza enquanto
a ação está **em voo** (`mexendo`, `enviando`, `ocupado`, `vinculando`,
`conectando`, `carregandoAnteriores`): mostram o girando e duram um instante.
Texto neles devolveria o ruído que a rodada dos textos educativos tirou no
mesmo dia.

Ganharam motivo os nove em que o cinza é **uma pergunta sem resposta**:

| Onde | O que passou a dizer |
|---|---|
| compositor (enviar e nota) | *Escreva algo ou anexe um arquivo* |
| encaminhar | *Marque ao menos uma conversa de destino* |
| nova mensagem | *Informe o número, com DDD* / *Escreva a mensagem* |
| convidar | *Marque quem você quer chamar* |
| transferir | *Escolha o time de destino* |
| concluir | *Esta classificação exige um comentário dizendo o que foi* |
| e-mail: responder e encaminhar | *Abra uma mensagem primeiro* |

## 7 — Atalhos na Caixa de entrada

O E-mail tinha **6 teclas** e as ensinava; a Caixa de entrada tinha **zero**. A
tela mais usada era a com menos ferramenta.

```
Objetivo:     quem atende o dia inteiro não precisar do mouse para andar
Hoje:         j / k passam de conversa · / vai para a busca · a assume ·
              c abre o concluir
Por quê:      pedido dele ("3,5,6,7,13 pode validar e fazer"). As teclas
              espelham as do E-mail onde a ação é a mesma, e `/` é
              convenção (Gmail, Slack, GitHub)
Reavaliar se: ele quiser outras teclas — atalho é regra de uso, e a
              escolha continua sendo dele
```

🚨 **NUNCA DENTRO DE CAMPO DE TEXTO** — mesma guarda do E-mail. Sem ela,
escrever "javali" para o cliente pularia de conversa no meio da palavra.
`Ctrl`/`Cmd`/`Alt` também saem: são atalhos do navegador.

⚠️ **Nenhuma tecla destrói.** `c` abre o modal de concluir, não conclui — a
confirmação continua sendo o que decide. E as teclas são **ensinadas** no ícone
de ajuda: atalho que ninguém descobre é o mesmo que não existir.

## 13 — `gerar_env.py` foi para `scripts/`

Ninguém o chamava — nem código, nem cron, nem doc.

🚨 **MOVER NÃO ERA TRIVIAL.** Ele resolve caminho por `Path(__file__).parent`,
que era a raiz do repositório. Com um `.parent` só, ele passaria a gravar o
`.env` **dentro de `scripts/`** — sem erro, sem aviso, e o painel continuaria
lendo o `.env` antigo. Corrigido para `.parent.parent`.

⚠️ **Arquivo que resolve caminho por `__file__` nunca é só mover: é mover e
conferir a âncora.**

## Como isto se defende

`frontend/src/ficha_e_rotulos.teste.js` cresceu para cobrir o 3, o 6 e o 7 —
**80 verificações JS** no total.

🚨 **E o duplo do teste tinha um defeito que reprovava código bom.** Ele casava
rota por prefixo na ordem de inserção, então `/api/informativos` engolia
`/api/informativos/9` e devolvia a LISTA no lugar do disparo: a tela montava
com `aberto` errado e o teste acusava botão desabilitado que na tela real está
ativo. Agora **a chave mais longa vence**. Duplo que mente sobre a rota é pior
que duplo nenhum.

⚠️ E o primeiro teste do informativo que eu escrevi era `expect(... || true)` —
teste de mentira. Trocado por um que monta a tela com o disparo em `enviando` e
em `rascunho`, e afirma os dois estados do botão.

---

## CFG_6.1 — Atalhos de teclado (28/08)

Pedido dele: *"crie nas configurações tela de atalhos e interruptor desligado
para eles e permita edição por lá também"*.

🔵 **SÓ O OWNER VÊ DESDE 24/09**, decisão dele: *"pode exibir a atalhos
somente para o owner tbm"*. Nasceu `atendimento`. No dia da mudança nenhum
atendente tinha ligado atalho (a `preferencia_atendente` tinha uma linha só,
`enviar_com_enter`), então ninguém ficou com tecla ligada sem ter onde desligar.

🚨 **FECHAR SÓ A TELA TERIA DESLIGADO O ENTER DE TODO ATENDENTE, EM SILÊNCIO.**
A Caixa de entrada, o Chat interno e o E-mail leem `enviar_com_enter` de
`GET /api/eu/atalhos`, e a Minha conta grava em `PUT /api/eu/enviar-com-enter` —
as duas presas à `CFG_6.1`. Com ela em `owner`, viria 403, o `catch` das três
telas cairia no desligado, e a decisão de 22/09 (Enter ligado para todos)
morreria sem erro na tela. As duas rotas passaram a `get_usuario`, como foto e
estado; `PUT .../ligados` e `PUT .../teclas` continuam presas à tela.

🚨 **A TELA NASCEU DE UMA PERGUNTA QUE DERRUBOU UM RECURSO MEU.** Ele
perguntou: *"quem pediu esses atalhos? ou eles já são nativos do WhatsApp?"* —
e a resposta honesta era **ninguém pediu, e não são**:

- `j` / `k` vêm do **Gmail** (e antes dele, do `vi`). Está escrito no meu
  próprio commit da tela de e-mail: *"os mesmos do Gmail"*.
- Eu os levei para a **Caixa de entrada**, que é a tela que ele escolheu entre
  cinco mockups **para parecer o WhatsApp**, com a razão registrada: *"quem
  atende passa o dia no WhatsApp"*.
- O meu argumento para propor era *"o E-mail tem 5 atalhos e a Caixa de entrada
  tem zero"* — que compara a tela com **outra tela minha**, não com o que a
  pessoa já sabe usar. Simetria interna, não usabilidade.
- E o `a` **assumia a conversa sem perguntar**, com 380 conversas sem dono e
  nove pessoas testando ao mesmo tempo.

```
Objetivo:     atalho existir sem virar surpresa para quem não o pediu
Hoje:         CFG_6.1 lista os 11 atalhos das duas telas, com interruptor
              por pessoa, DESLIGADO de nascença, e troca de tecla por captura
Por quê:      pedido dele, depois de a pergunta dele mostrar que o recurso
              era meu e que um dos atalhos agia sem confirmar
Reavaliar se: ele quiser as teclas do WhatsApp em vez das do Gmail na Caixa
              de entrada. Aí muda o PADRÃO, e a tela continua igual
```

### 🚨 Desligado é a ausência, não uma opção

Sem linha em `preferencia_atendente` = **desligado**. Quem nunca abriu esta
tela não tem atalho nenhum. Se ausência significasse "ligado", quem não sabe
que existem teria o teclado agindo — que é justamente o risco que o pedido veio
fechar.

⚠️ E no navegador `atalhosLigados` **começa falso** e só vira verdadeiro quando
`/api/eu/atalhos` responde: entre montar a tela e a resposta chegar, nenhuma
tecla age. Se a chamada falhar, continua falso — o lado seguro é o teclado
inerte.

### Por pessoa, não no `config`

A tabela `config` é do **sistema** (repasse por inatividade, horário, avaliação).
Atalho é a **mão de quem usa** — e ele já tinha fixado isso em 27/08: *"quais
teclas é decisão sua — atalho é regra de uso"*. Guardar em `config` faria a
tecla de uma pessoa mudar a de todas, com nove em teste.

Migração **040**: `preferencia_atendente (atendente_id, chave, valor)`, genérica
de propósito — a próxima preferência entra sem migração.

### O catálogo vem do backend

A tela **não sabe** quais atalhos existem: desenha o que `/api/eu/atalhos`
devolver. Escrever a lista no navegador criaria duas verdades, e a que o
operador vê seria a errada — a mesma família do defeito de 17/08, em que a
sidebar lia um contrato de JSON que o servidor tinha deixado de cumprir.

⚠️ O catálogo marca `perigo` no que **muda estado sem perguntar** (`a` assumir,
`e` arquivar), e a tela **avisa antes de a pessoa ligar**, em vez de ela
descobrir apertando.

### Trocar tecla é capturar, não digitar

Clicar na tecla arma a captura e a **próxima tecla apertada** vira o atalho.
Campo de texto aceitaria "Enter" escrito por extenso, espaço, duas letras — e o
backend recusaria depois. Capturar é o gesto real.

🚨 **Duas ações com a mesma tecla na mesma tela é recusa**, com a frase dizendo
quais são. Sem isso, `j` para "próxima" e para "assumir" faria a pessoa assumir
conversa tentando andar na lista, sem ter como saber por quê.

### As 11 ações

| Tela | Ação | Padrão | Age sem perguntar? |
|---|---|---|---|
| WhatsApp | próxima conversa | `j` | não |
| WhatsApp | conversa anterior | `k` | não |
| WhatsApp | ir para a busca | `/` | não |
| WhatsApp | **assumir a conversa** | `a` | 🔴 **sim** |
| WhatsApp | abrir o concluir | `c` | não — abre a janela |
| E-mail | próxima / anterior | `j` `k` | não |
| E-mail | responder | `r` | não |
| E-mail | **arquivar** | `e` | 🔴 **sim** |
| E-mail | marcar não lida | `u` | reversível |
| E-mail | estrela | `s` | reversível |

⚠️ **Fora deste catálogo continuam as teclas presas a campo**, que não passam
pelo interruptor porque não são atalho de tela: `Ctrl+Enter` envia no
compositor da conversa, `Enter` envia no chat interno, `Esc` fecha a busca e a
lista do `@`, `↑`/`↓` andam na lista do `@`.

🚨 **E fica registrada uma incoerência que o teste de usuário vai encontrar:**
na Caixa de entrada `Enter` quebra linha e `Ctrl+Enter` envia; no Chat interno
`Enter` **envia**. É decisão registrada — *"lá a mensagem vai para o cliente e
não volta"* — mas a mesma pessoa escreve nas duas e a mesma tecla faz coisas
opostas.

---

## CFG_7.1 — Geral: os interruptores do sistema (28/08)

Pedido dele em 27/08: *"os acionadores dos interruptores devem ficar lá"*. Em
28/08 ele mandou conferir: *"aproveite para verificar se todos os interruptores
aparecem em suas respectivas telas nas configurações"*.

**Auditei os nove. Sete estavam certos. Dois não.**

| Interruptor | Onde acionava | Estava em `/config`? |
|---|---|---|
| IA por canal · canal ativo | CFG_1.1 | ✅ |
| Boas-vindas e IA por tipo | CFG_5.1 | ✅ |
| Classificação ativa · exige comentário | CFG_4.1 | ✅ |
| Atalhos de teclado | CFG_6.1 | ✅ |
| 🔴 **`jornada_ativa`** | **Atendentes (CAD_2.1)** | **não** |
| 🔴 **`avaliacao_ativa`** | **lugar nenhum** | **não existia** |

### 🔴 A jornada acionava numa tela de cadastro

`config.jornada_ativa` muda **como a fila distribui** — é interruptor do
sistema. O botão vivia em Atendentes, que é tela de cadastro. Escondido onde
ninguém procura configuração: o mesmo padrão que motivou a escada da IA em
27/08.

```
Objetivo:     interruptor do sistema ter um lugar só, e ser esse lugar
Hoje:         o botão está na aba Geral; Atendentes mostra o ESTADO em um
              chip que leva para lá
Por quê:      pedido dele de 27/08, conferido em 28/08 -- e a conferência
              achou que dois não tinham chegado
Reavaliar se: aparecer interruptor de sistema que faça mais sentido junto
              do que ele afeta. A jornada não é o caso: ela afeta a fila,
              não o cadastro da pessoa
```

🚨 **A LEITURA CONTINUA EM ATENDENTES, SÓ A CHAVE MUDOU DE LUGAR.** Aquela tela
precisa do estado para marcar quem está fora do horário na lista. O que saiu de
lá foi o **botão**. Interruptor tem um lugar só; estado se lê onde faz falta.

⚠️ **E a permissão passou a dizer isso:** `GET /api/config/jornada` continua
`CAD_2.1` (quem monta escala lê), e `PUT` passou a exigir **`CFG_7.1`** (quem
configura o painel liga). A regra não vive mais só no desenho da tela.

⚠️ A função `alternarJornadaAtiva` saiu do `Atendentes.vue` junto com o botão —
função sem chamador é peso morto que a próxima pessoa tenta entender.

### 🔴 `avaliacao_ativa` não tinha acionador em tela nenhuma

A chave existe no banco desde o começo, com descrição — *"Pedir nota de 1 a 5 ao
encerrar a conversa"* — e **nenhuma das 20 telas a mencionava**. Um interruptor
invisível.

Ela aparece agora na aba Geral, **travada, com o motivo escrito**: a avaliação
ainda não existe no atendimento, então ligar não faria nada.

🚨 **É a regra que ele aprovou na escada da IA**: nada some, e o que não dá para
usar aparece dizendo o que falta. Ligar um interruptor cujo comportamento não
existe seria pior que escondê-lo — e escondê-lo foi o que estava acontecendo.

⚠️ Bate com o MIOLO: *"Classificar e avaliação de atendimento ⏸️ 31/08"*. **A
chave nasceu antes da funcionalidade**, e agora isso está à vista em vez de
enterrado no banco.

### O que NÃO foi movido, e por quê

`atendente.ativo`, `time.ativo` e `contato.ativo` aparecem fora de `/config` e
**não são interruptores do sistema**: são o estado de um registro, e pertencem
à tela onde o registro vive. Desativar um atendente é ato de cadastro, não
configuração — movê-los faria você sair da ficha da pessoa para desativá-la.

⚠️ **Eu deveria ter feito esta varredura em 27/08**, quando entreguei a aba de
Configurações. Entreguei seis telas e não conferi se todo interruptor tinha
chegado nela. Foi ele quem perguntou, um dia depois.


---

## `CFG_8.1` — Eventos do WhatsApp (15/09)

🟡 **Sugestão minha (S13), aprovada por ele em 15/09** junto com o resto da
lista do que faltava.

A rota `/api/webhook/eventos` existia **desde o começo do projeto** e só era
alcançável por `curl`. Foi ela que achou, em 27/08, o `listMessage` e o
`listResponseMessage` que **nenhuma consulta tinha visto** — e um deles era
uma pessoa respondendo a um menu, que o painel tratava como ruído.

🚨 **O valor da tela é ver o que ninguém sabe procurar.** Consulta SQL responde
pergunta que já se sabe fazer; esta tela mostra o que está chegando, e é assim
que formato novo aparece antes de virar defeito calado.

**O que ela mostra:** os 50 eventos mais recentes com hora, tipo, telefone e
estado (processado, esperando, erro). Clicar em um abre o **corpo cru**.

⚠️ **O payload só é buscado ao abrir UM evento**, nunca na lista: ele carrega o
`base64` de mídia e tem milhares de linhas. Por isso também rola dentro da
própria caixa, com teto de altura — sem isso ele empurraria a tabela para fora
da tela e a pessoa perderia o lugar de onde clicou.

**Permissão:** `owner`. É tela de diagnóstico do sistema, não de atendimento.

⚠️ **A permissão das duas rotas mudou junto** (`CFG_1.1` → `CFG_8.1`): elas
pediam a permissão da tela de Canais porque não havia tela própria. Conferido
antes de trocar — nenhum outro ponto do frontend as chama.

---

# A rodada de 15/09 — achabilidade, erros e o que os quatro pediram

Igual às de 27 e 28/08: separando o que é frase dele (🔵), o que é dos
usuários passada por ele (🟢) e o que eu deliberei (🟡). `CFG_8.1`, acima,
já é parte desta rodada e tem seção própria.

## Achabilidade — o mecanismo já respondia, faltava chegar até ele

**Tique de entrega/leitura** (🟢 Claudia: *"poderia ter uma forma de sabermos
que as mensagens foram enviadas e lidas"*). A tela já sabia desenhar ✓✓ azul
quando `m.entrega === 'lida'` — quem nunca chegava era o dado. O Evolution
manda o status num formato achatado (`data.keyId`) diferente do que a
mensagem original usa (`data.key.id`), e a extração só conhecia o segundo.
**100% dos 31.573 eventos de status já recebidos** caíam fora, sempre.
Corrigido lendo os dois formatos direto do payload cru, sem tocar na
dedução de reentrega. Medido depois: 420 mensagens "lida" no primeiro dia,
contra zero em toda a história antes disso.

**Modal de transferir vazio** (🟢 Claudia: *"cadê os atendentes?"*).
`GET /api/times` exigia `CAD_2.2` — tela de cadastro, permissão só de owner.
Nenhum atendente comum via a lista; o `catch` da tela engolia o 403 em
silêncio (o próprio comentário do código já dizia isso: *"sem estes a tela
ainda mostra conversa; só as ações ficam sem opção"*). Passou a exigir
`ATD_1.1`, que todo perfil de atendimento tem — criar e editar time
continuam só do owner.

**Transferir para uma pessoa.** `conversas.transferir()` aceita
`para_atendente_id` **desde a primeira versão rastreável do projeto** — e a
tela nunca teve o seletor, só o de time. Achado ao investigar o item acima
mais a fundo, a pedido dele. O modal agora tem os dois campos, mutuamente
exclusivos, com a consequência de cada um escrita (time larga na fila,
pessoa já entrega com dono — é o que a própria função sempre disse na
docstring).

**Resposta do cliente só aparecia na lista** (🟢 Rodrigo). O polling de 8s
só chamava `carregar()` (a lista), nunca a conversa aberta. Nova função
`atualizarMensagens()` também refresca a conversa em uso, sem resetar
citação, busca, gaveta ou menção — que é o que `abrir()` faria se fosse
reaproveitada para isto.

🚨 **Essa correção nasceu com um bug, achado no mesmo dia**: a mídia de
mensagem nova não carregava sozinha (caía em "Baixar") porque
`atualizarMensagens()` não chamava `carregarMidiasDaConversa()`. Corrigido
antes de qualquer usuário reportar — achado perguntando "o que acontece
DEPOIS do que acabei de consertar", o mesmo método do `M` do
`Proximos_Passos`.

**Nome de quem enviou** (🟢 Erika: *"não aparece mesmo no carimbo interno o
usuário que enviou"*). `atendente_nome` já vinha em cada mensagem
(`conversas.mensagens()` faz o JOIN desde sempre); só notas internas
desenhavam o autor. Ajuste de template, zero mudança de backend.

**Contato compartilhado sem número** (🟢 Erika). O parser lia
`displayName` do vCard e descartava o `vcard` inteiro. Extrai agora o
`TEL` de dentro dele. ⚠️ Só vale para mensagens **novas**: o vCard não é
gravado em nenhuma coluna, só existe no payload cru do webhook, que expira
em 30 dias.

**Localização sem conteúdo** (🟡 achado ao consertar o item acima, mesmo
padrão). `locationMessage` trazia `degreesLatitude`/`degreesLongitude` e o
parser não olhava. Agora extrai a coordenada e a tela desenha um link
"Ver no mapa". **10 das 14 localizações já recebidas foram recuperadas**
reprocessando o payload ainda vivo; as outras 4 já tinham perdido o payload
no expurgo de 30 dias.

## Erros

**Nome do contato ao vincular** (🟢 Claudia: *"verificar se ao vincular na
ficha, o nome do contato está puxando certinho"*). Eu tinha respondido
"conferido, está certo" **lendo o código**. Medindo o dado: dos 23 contatos
criados pelo atendimento, **5 tinham nome sujo** — três eram só o emoji
`🙏🏼`, um tinha emoji colado ao nome com espaço duplo. O apelido do
WhatsApp entra cru como nome do cadastro. `_nome_para_cadastro()` agora
tira emoji, modificador de tom de pele e juntor invisível antes de gravar;
se sobrar só símbolo, usa o telefone. Um campo "Nome da pessoa" no modal
de vincular deixa quem atende escrever o nome certo na hora. **Os 5
registros sujos foram corrigidos**, autorizado por ele.

**Auth do Google não conectava a caixa de e-mail.** Não era o login — era
`/config/canais`, conectar a caixa. A migração 030 (25/08) trocou o
`UNIQUE` de `email_conta` de `endereco` sozinho para
`(atendente_id, endereco)`, e o `INSERT` de `conectar_caixa()` nunca foi
atualizado: todo `ON CONFLICT (endereco)` quebrava com
`InvalidColumnReference`. Corrigido threading o `atendente_id` pelo
`state` assinado do OAuth — único jeito de saber quem clicou, já que o
callback do Google não carrega sessão.

**Trava de identidade faltando ao criar contato pelo tipo.**
`conversas.definir_tipo()` criava contato novo sem checar se o telefone já
existia em outro cadastro — a mesma checagem que `vincular()` e o parser
do webhook sempre fizeram. Achado ao vivo: o número de teste dele
(`+5518998116168`) virou um contato órfão sem empresa nesse caminho, antes
de ele mesmo vincular corretamente à Velasco pela ficha. Agora
`definir_tipo()` chama `cadastro.por_telefone()` antes do `INSERT`; se
achar candidato, recusa e pede para vincular por lá. O contato órfão
(`91040`) foi apagado, e os 3 testes que documentavam a regra antiga
("este número nunca tem dono") foram reescritos para a realidade atual —
ele vinculou de propósito, e o número tem dono desde 15/09.

## Journals — para não depender de print na hora

**Erro de botão** (🔵: *"proponha um journal para logs de erros de botões,
simples"*, pelo caso da Aline com "Reabrir e assumir"). 17 ações da
Caixa de Entrada agora reportam para `/api/erros/frontend` dentro do
próprio `catch`, sem travar a tela se o próprio reporte falhar. Grava em
`logs/movizap_erros_botao.log`: quem, ação, conversa, URL, navegador,
mensagem. Fica de fora o polling silencioso, de propósito — logar cada
falha de fundo encheria o arquivo sem servir para nada.

Na mesma investigação: achei que `convidar()` era a única das quatro
funções que usam a trava `mexendo` sem `try/finally` em volta do corpo
inteiro — uma exceção fora do laço travava `mexendo` em `true` para
sempre, e o modal de confirmação (o mesmo do "Reabrir e assumir") para de
responder enquanto isso. Corrigido. **Não é a causa confirmada** do caso
da Aline, só a única fresta real achada lendo o código inteiro.

**16/10 — o journal passou a gravar o ALVO** (item 2, pelo erro do "apagar" da
Aline às 11:55, que ficou sem diagnóstico: o id que o navegador mandou não
existia na conversa, e o journal registrava tudo **menos** o `mensagem_id`).
Três mudanças, no ar desde 16/10 18:12:
- `ErroDeBotao` ganhou `alvo_id`, e a linha do journal grava `alvo=`. O
  `relatarErroDeBotao` do frontend manda o id da mensagem no apagar e no
  editar. Se o erro voltar, o diagnóstico fecha pelo log.
- **Duas frases, não uma:** "Esta mensagem não existe mais." e "Esta mensagem
  é de outra conversa — recarregue a página." Antes as duas causas, opostas,
  davam o mesmo texto.
- **Apagar congela a conversa no clique:** a confirmação lia `aberta.value.id`
  só no "sim"; se a conversa aberta mudasse com o diálogo na tela, o pedido ia
  para a conversa nova com o id da mensagem da antiga. Defeito real, achado no
  caminho — **não é a causa confirmada** do caso dela.

**Vínculos** (🔵, ao ver as fichas duplicadas do `+5583987916210`: *"acho
legal termos o log de vínculos, para saber quem vincula o que"*). Grava em
`logs/movizap_vinculos.log`: VINCULOU, DESVINCULOU (lendo o vínculo ANTES
de desfazer, senão o log não diria de quem era) e CRIOU FICHA.

## Features

**Menu lateral recolhível** (🟢 Rodrigo, com a especificação exata: botão
sanduíche, hover expande sem fixar, só o botão fixa). O modo compacto já
existia como `@media` de tela estreita; virou também uma classe
acionável por escolha, independente da largura da tela. Estado salvo por
navegador (`localStorage`), não por preferência do banco — é conveniência
de UI, não regra de uso.

**Selo de mensagem nova e de menção** (🟢 Erika + 🟡 S10/S11 antigos,
confirmados por ela). `/api/chat/nao-lidas` já existia ("o selo do menu"
na própria docstring) sem chamador; `/api/chat/mencoes` também. Um selo só
no menu, que muda de cor quando há menção — dois badges brigariam por
18px.

**Enter para enviar** (🟢 Erika). Preferência por pessoa
(`preferencia_atendente`, mesma tabela dos atalhos). Nasceu desligada em
15/09; **desde 22/09 nasce LIGADA** por decisão dele (*"mudar o envio para
todos pelo 'enter' conforme a opção no perfil"*) -- quem desligar grava
`"false"` e fica desligado.
Ligada: Enter envia, Shift+Enter quebra linha. Desligada: comportamento de
sempre (Ctrl+Enter envia).

**Quadro de tipos de mensagem não tratados** (🟡 S4). 🚨 **Ele já tinha
autorizado isto em agosto e eu deixei cair** — a auditoria de 15/09 achou
que a tela nunca foi escrita. Nova seção na `CFG_3.1` (Sincronização, que
já é a tela de diagnóstico) mostrando o que o parser descartou e por quê,
lendo `webhook_evento.motivo_ignorado` (0,035s a consulta, contra 1,10s por
chave varrendo o payload cru). Hoje: 227 eventos do canal informativo, zero
tipo desconhecido.

**Tela sobrevive ao banco piscar** (🟡 S3). O `apt upgrade` dele reinicia
o Postgres por ~12s; o pool já reconectava sozinho, mas toda tela aberta
cuspia erro cru de driver na janela. Handler novo devolve 503 com um motivo
legível; o cliente HTTP tenta de novo **uma vez, só em GET** — repetir POST
reenviaria mensagem para o cliente, que é pior que o erro na tela.

**O delay de ~7s** (🟡 S16). Sem mexer em nenhum teto: o laço que processa
a fila do webhook dormia os 5s inteiros mesmo com evento esperando. Agora
o webhook "cutuca" um `asyncio.Event` ao gravar, e o laço acorda na hora.
Medido com evento real: **0,01s contra a média de 2,65s** (pior caso 4,99s)
que valia antes.

**Criar grupo do WhatsApp** (🟡 S15). `evolution.py` só lia grupo. Rota
nova (`POST /api/grupos`) confere o WhatsApp de cada número antes de
tentar — o Evolution recusa o lote inteiro por causa de um número ruim.
⚠️ **Não testado com grupo real**: criar grupo com pessoas de verdade não
se desfaz.

**Foto de perfil** (🟢 Erika). Tabela nova `foto_perfil`, por telefone (não
por contato — 61% das conversas não têm cadastro). 🚨 **O arquivo fica em
disco, nunca a URL**: medido no payload real, a URL do WhatsApp expira
(`oe=` no fim). Uma consulta ao Evolution por número por dia; `sem_foto`
distingue "perguntei e não tem" de "nunca perguntei". Provado com a foto
real dele, baixada e em disco.

**Não lidas nas conversas do WhatsApp** (🟢 Erika: *"como no bitrix e
whatsapp"*). Tabela nova `conversa_leitura`, espelhando o
`chat_membro.lido_ate` que o chat interno já usa — por pessoa, porque a
mesma conversa está lida para quem acabou de atender e não lida para quem
vai pegar o plantão. 🚨 **Marco zero aplicado na entrega**: sem isso, toda
conversa antiga apareceria com centenas de "não lidas" no primeiro dia —
medido antes de ligar, uma conversa de agosto já atendida mostrava 536.
O passado entrou como lido (4.500 marcadores); a contagem vale dali para a
frente. Reversível com um `DELETE`.

## O que este erro de escopo me ensinou, de novo

Fui direto duas vezes nesta rodada e as duas vezes o dado provou o
contrário do que eu tinha lido no código: "transferir para pessoa não
existe" (existia desde sempre, um `grep` cortado na primeira linha da
assinatura) e "o nome do contato está certo" (5 de 17 estavam sujos,
lidos no código em vez de medidos no banco). As duas vezes a correção veio
de enumerar TUDO — todos os `INSERT INTO contato`, todos os nomes reais —
em vez de confiar numa amostra ou numa leitura rápida.

## CFG_10.1 — Minha conta

🔵 **24/09: o nome se edita aqui** (`PUT /api/eu/nome`, sem `requer_tela`,
como foto e estado), e **e-mail só aparece para owner e admin, login só para o
owner**. Ver a tabela na CAD_2.1.

🔵 **Pedido dele em 17/09:** *"central de perfil 'minha conta' para foto de
usuario, dados de perfil, tipo de envio 'entrer ou clique'"*. O status é
🟢 pedido do Rodrigo, trazido por ele em 15/09.

🚨 **A COLUNA JÁ EXISTIA E EU AFIRMEI DUAS VEZES QUE NÃO.** O
`atendente.estado` nasceu na migração **001**, com
`disponivel`/`ausente`/`nao_perturbe` — exatamente os três valores que a
memória dizia. Ela não apareceu nas minhas buscas porque **se chama `estado`,
não `status`**, e eu procurei por `status`, `online`, `pausa` e `presenca`.
Fica a regra: **ausência se afirma lendo o `CREATE TABLE`, nunca por `grep` de
uma palavra que eu supus** — é a mesma família do `M13`.

🚨 **O QUE FALTAVA NÃO ERA A COLUNA, ERA O PRODUTO.** Medido em 17/09: `estado`
aparecia em **um** lugar do código (`main.py`, modelo `AtendenteEntrada`), não
chegava ao `/api/sessao/eu`, não era desenhado em tela nenhuma e não decidia
nada. Por isso ele lembrava do status e não o via.

### O que a tela tem

| Bloco | O que faz |
|---|---|
| **Como você está** | os 4 estados, um clique cada, com a explicação do que cada um significa ao lado |
| **Sua foto** | sobe PNG/JPG até 2 MB; sem foto, a tela cai nas **iniciais do nome** |
| **Como você envia** | o mesmo interruptor `enviar_com_enter` da CFG_6.1 |
| **Seus dados** | nome, login, e-mail, perfil e teto de conversas, **em leitura** |

### As decisões, e por quê

⚠️ **`offline` É ESCOLHIDO, NÃO DEDUZIDO.** Não é "sem sessão aberta": é a
pessoa dizendo *"encerrei"*. Deduzir de atividade exigiria bater ponto por
requisição, e o painel fica aberto em aba esquecida o dia inteiro — o derivado
mentiria mais do que informaria.

⚠️ **O TIPO DE ENVIO É ESPELHO, NÃO CÓPIA.** O mesmo interruptor mora na
CFG_6.1, onde responde *"o que o teclado faz por mim"*; aqui responde *"como
EU envio"*. Mesma preferência (`enviar_com_enter`), mesma rota — **duas portas
para o mesmo quarto, nunca dois quartos.** Desde 24/09 a porta da CFG_6.1 é
só do owner; para o atendente, **a Minha conta é a única**, e a rota do Enter
deixou de depender da CFG_6.1 (ver a seção dela).

⚠️ **NOME, LOGIN, E-MAIL E PERFIL SÃO LEITURA.** Todos entram por Google com
domínio travado, então nome e e-mail vêm de lá; perfil é **permissão**, e
permissão é decisão do owner, na tela de cadastro. Mostrar em leitura é melhor
que esconder — regra *"nada some"* (27/08): a pessoa vê o que vale para ela e
por que não pode mudar.

⚠️ **AS ROTAS DE "EU" NÃO PEDEM `requer_tela`.** Trocar a própria foto e dizer
que está em pausa não é permissão de tela: é a pessoa mexendo nela mesma.
Prender isso a um código faria quem não enxerga a `CFG_10.1` ficar preso em
"disponível" — e o status existe justamente para quem atende.

⚠️ **A FOTO GUARDA O CAMINHO, NUNCA OS BYTES**, e o caminho **nunca vem da
tela**: o nome que o navegador manda vira só o nome-base, a pasta é nossa, por
atendente (`/home/claude/movizap_midia/atendente/<id>/`). Mesma decisão da
assinatura (017) e da foto de contato (041).

### O que ficou de fora desta entrega

🔴 **O estado ainda não aparece PARA OS OUTROS.** Esta tela é onde a pessoa se
declara; mostrar a bolinha ao lado do nome de cada um no Chat interno e na
conversa é o passo seguinte, e é o que fecha o pedido do Rodrigo por inteiro.
Sem ele, o estado vale como registro e não como aviso à equipe.


## EML_1.1 — as duas abas que faltavam: Arquivadas e Lixeira (17/09)

🔵 **Pedido dele:** *"não temos lixeira também no movizap? não deveria se
espelhado o uso?"*

Antes de hoje só existia "Entrada". Arquivar já era possível desde a 014, mas
sem tela: a mensagem só sumia. Exclusão não era detectada de jeito nenhum.

### O que a tela ganhou

- Uma segunda fileira de abas, abaixo das contas: **Entrada · Arquivadas ·
  Lixeira**
- Botão **Excluir**, ao lado de Arquivar, na mensagem aberta
- Botão **Restaurar** no lugar de Excluir, quando a mensagem já está na
  lixeira — os dois nunca aparecem juntos
- Aviso vermelho quando a mensagem **sumiu de vez** do Gmail: *"Removida do
  Gmail — esta é a cópia que já tínhamos. Não dá para restaurar lá."*

⚠️ **Restaurar devolve para a Caixa, não para Arquivadas** — decisão dele.
Tecnicamente o Gmail exige as duas operações (`untrash` sozinho não recoloca
o `INBOX`, medido ao vivo em 17/09); o botão faz as duas de uma vez.

📁 Detalhe técnico completo — a varredura, os dois campos novos, os
achados medidos: `docs/02_Modelo_Dados.md`, seção `email_mensagem.na_lixeira_desde`.

---

# ✅ Validado em 2026-09-18 — o botão da ficha e o campo Tipo

> 🚨 **AS DUAS COISAS DESTA RODADA NASCERAM DE SUGESTÃO MINHA QUE ELE NÃO
> PEDIU.** Uma (o S17) ele mandou desfazer; a outra (tirar "Sem identificação"
> da lista) ele corrigiu. Registro aqui porque a origem é o que separa
> demanda de dívida minha — e as duas eram dívida minha.

## ATD_1.2 — o botão "Ficha" volta a abrir só a gaveta

Pedido dele: *"proponha o botão Ficha - vincular para a tela original, de
volta, pois não pedi isso a você. Era para abrir o modal a partir do botão
'vincular empresa', já dentro da ficha e não no botão de Ficha-Vincular"*.

```
Objetivo:     um botão, um efeito -- Ficha abre a ficha
Hoje:         `abrirFicha()` só alterna a gaveta, com cadastro ou sem. O
              modal de vínculo abre pelo botão "Vincular a uma empresa",
              que mora dentro da gaveta
Por quê:      o S17 (15/09, sugestão minha) fazia o botão pular a gaveta e
              abrir o modal direto quando não havia cadastro. Economizava um
              clique e escondia o resto: o Tipo e o selo do Bitrix moram na
              gaveta, e com 319 conversas sem contato a gaveta simplesmente
              nunca abria para a maioria
Reavaliar se: ele achar o clique a mais caro no uso diário -- aí a saída é
              atalho, não sumir com a gaveta
```

## ATD_1.2 — o Tipo mostrava "sem cadastro" para quem tinha tipo

🚨 **O DEFEITO:** no estado "contato sem empresa", o seletor de Tipo estava
preso a um `ref` local (`tipoSemCadastro`) que nascia vazio e **só era
escrito ao SALVAR, nunca ao abrir a ficha**. Quem já tinha tipo via "sem
cadastro" no lugar dele.

**Medido em 18/09, na produção:** 5 contatos `tecnico` sem empresa (7
conversas). E não é cosmético — `contato.relacao` é chave primária da
`relacao_automacao`, a tabela que decide se a saudação automática e a IA
atendem a pessoa (`CFG_5.1`). A tela mentia sobre o que governa o
atendimento.

⚠️ **Atingia os dois públicos:** quem tem `ATD_1.2` via o seletor errado;
quem não tem via o chip fixo *"Sem cadastro"*, que mentia igual.

```
Objetivo:     o campo mostra o que a pessoa É, sempre
Hoje:         `tipoAtual`, um `computed` com get/set: o getter lê
              `empresa.contato.relacao` do servidor, o setter chama
              `trocarTipo`. Não há mais cópia local para dessincronizar
Por quê:      estado de tela duplicando dado de servidor diverge em silêncio
              -- ninguém erra, nada estoura, e o campo mente
Reavaliar se: aparecer um caso em que a tela precise segurar uma escolha
              antes de gravar (rascunho); aí a cópia volta, mas semeada
```

⚠️ **O que isto NÃO conserta, e é anterior:** sem contato nenhum, o
`trocarTipo` não grava otimista (não há `contato` para escrever), então um
PUT que falha deixa a escolha aparente no seletor. Quem avisa é a faixa de
erro. Vale igual para o `:value` de antes e o `v-model` de agora.

## 🚫 "Sem identificação" VOLTOU à lista — decisão dele, corrigindo a minha

Em 28/08 **eu** tirei `sem_identificacao` da escolha, chamando-o de valor de
nascimento da migração 031. Ele corrigiu em 18/09:

> *"sem identificação é sem identificação mesmo, não é só porque tem empresa
> vinculada que é cliente. esse cad deve ser feito a mão"*

**E o banco já concordava com ele:** `conversas.vincular()` insere o contato
**sem definir `relacao`**, então ele nasce `sem_identificacao` pelo default da
coluna. **Vincular empresa nunca marcou ninguém como cliente.** Medido em
18/09: **19 contatos `sem_identificacao`, todos COM empresa** — pessoas que
ninguém identificou ainda, não clientes.

| Onde o Tipo aparece | Antes de 18/09 | Agora |
|---|---|---|
| Contatos (`CAD_1.2`) | 8 valores | 8 valores |
| Conversa, **com** empresa | 8 valores | 8 valores |
| Conversa, **sem** empresa | 7 (sem `sem_identificacao`) | **8** |

Sem o valor na lista não havia como desfazer uma classificação errada de
dentro da conversa — só pela tela de Contatos. `RELACOES_ESCOLHIVEIS` saiu do
código, sem uso.

🚨 **O placeholder `<option value="">"sem cadastro"` agora só aparece enquanto
é verdade** (`v-if="!aberta.contato_id"`): com contato criado não há volta, e
opção que não leva a lugar nenhum é ruído. Ele fica **selecionável, não
cinza** — o painel inteiro não tem uma única `<option>` desabilitada (22
`<option>` em 6 telas, conferido), e a convenção de placeholder aqui é
`<option value="">`, como nas outras 7. A regra do "cinza com motivo" vive em
**botão**, não em item de lista.

## O que a suíte passou a defender

Os 21 testes de `ficha_e_rotulos.teste.js` afirmavam o rótulo do botão, o
modal e a classe do campo — **nenhum afirmava o valor selecionado do Tipo**, e
é por isso que o defeito passou por suíte verde. Entraram 4:

| Teste | O que trava |
|---|---|
| contato `tecnico` sem empresa | o seletor mostra `tecnico`, não `""` |
| sem contato nenhum | o seletor fica em `""` e diz "sem cadastro" |
| `sem_identificacao` escolhível | está nas opções; o placeholder some com cadastro |
| sem permissão | o chip **lê** "Técnico", em vez de "Sem cadastro" fixo |

⚠️ `codigosPermitidos` no duplo virou `ref` (era `computed`, somente leitura):
sem isso não dá para tirar a permissão e conferir o que o outro público vê.


---

# 2026-09-23 — a rodada dos dez itens (ordem de execução aprovada por ele)

Origem de cada linha: 🔵 frase dele · 🟡 sugestão minha. Tudo com teste que
**reprova sem a mudança** (conferido rodando contra a versão anterior), suíte
inteira uma vez antes de publicar, servidor primeiro e tela por último.

| # | Item | O que mudou | Prova |
|---|---|---|---|
| 1 | 🔵 20 | "Sem preferência = desligado" corrigido em `Atalhos.vue`, `preferencia.py` e aqui (linha do Enter): **o Enter é a exceção desde 22/09, nasce LIGADO** | leitura |
| 2 | 🔵 19 | `partesDoTexto` foi para `util/mencao.js`; a tela e o `mencao.teste.js` importam a MESMA função. Teste novo monta o Chat interno e confere o destaque no balão | 9 + 1 |
| 3 | 🔵 18 | O laço de 5 s do Chat interno: **sala primeiro, lista depois, uma vez** (era lista, sala, lista) | reprova na versão antiga: lista ia 2× |
| 4 | 🟡 6 | Teste que trava a porta do `/config` para o atendente, e a REGRA geral: nenhuma aba visível com a mãe invisível, em qualquer perfil | com `CFG_0.1` trancado em memória, 2 reprovam |
| 5 | 🔵 13 | Lista: **não lidas primeiro**, depois a mais recente; concluída no fim; **busca continua só pela mais recente** | reprova na versão antiga |
| 6 | 🔵 21 | O resumo da transferência vira **nota interna** na conversa; o convite ganha "Recado (opcional)", que também vira nota | 5 backend + 3 tela |
| 7 | 🔵 17 | Bolinha do estado de quem responde: lista, cabeçalho (em texto), convidar e transferir (em texto no `<option>`) | 4 backend + 3 tela |
| 8 | 🔵 22 | Aba **Time**: conversas sem dono dos times de que eu sou membro | 4 backend + 2 tela |
| 9 | 🔵 11 | **Bloquear / desbloquear** pelo painel, filtro "Bloqueados (N)", envio ao cliente travado para bloqueado | 9 backend + 4 tela |
| 10 | 🔵 16 | **Editar** (15 min) e **apagar para todos** (48 h) a MINHA mensagem | 11 backend + 5 tela |

Medido antes do item 5: na aba Todas, para uma atendente real, a 1ª conversa
estava **lida** e a última não lida na **posição 98 de 100**. Depois: as 91
não lidas nas posições 0–90 — **23 delas nem entravam nas 100 antes**.

## Prova real (23/09, número dele, conversa 12845, `assumir=False`)

| Passo | Resultado |
|---|---|
| Enviar, **editar** | ✅ o WhatsApp aceitou; `conteudo` novo, `conteudo_original` guardado |
| **Apagar para todos** | ✅ aceito; `apagada_em` marcado, texto preservado |
| **Bloquear** | 🔴 **o WhatsApp recusou: "Error blocking user / bad-request"**. Nada foi anotado nem bloqueado |
| A conversa 12845 | igual antes e depois (`fila`, sem dono) |

🚨 **O BLOQUEIO NÃO FUNCIONA COM O NÚMERO DELE.** O webhook mostra o contato
em `addressingMode: lid`; a Evolution 2.3.7 **não expõe o LID** por nenhuma
rota de leitura (`whatsappNumbers`, `findContacts`). Não provei se vale para
todos — provar exigiria bloquear o número de outra pessoa. A tela agora diz a
causa em vez de "Internal Server Error".

## Decisões que tomei dentro do meu limite

1. **Ordem por "tem não lida", não por quantas** — e o `EXISTS` na ordem, com
   a contagem exata só nas linhas mostradas: 117 ms → **38 ms** (antes da
   mudança eram 25 ms).
2. **A migração 049 trouxe só resumo manual** — 21 dos 22 eram texto
   automático da saída do dono.
3. **Recado de convite só vira nota se alguém entrou**; falhou a nota, o
   convite vale e a tela diz.
4. **Uma régua de estado** (`util/estado.js`), com os rótulos do Chat interno.
   A tela de Atendentes diz "Ausente" onde as outras dizem "em pausa" — **não
   mexi**.
5. **Aba Time é filtro de vista, não permissão** — quem não é do time continua
   vendo a conversa em "Sem dono".
6. **Bloqueio:** sai das abas mas **aparece na busca, marcado**; nota interna
   continua; **só quem está na conversa bloqueia**, **qualquer um desbloqueia**;
   grupo não se bloqueia; histórico, não estado.
7. **Editar e apagar: só o autor.** Janelas 15 min e 48 h (o WhatsApp dá ~2
   dias para apagar; ficamos abaixo).
8. **O acesso a "Bloqueados" só aparece quando há algum** — não é uma quinta aba.

## ⚠️ O que só o uso fecha

- a **barra com quatro abas** (Todas · Sem dono · Minhas · Time) cabendo na
  coluna da lista — build limpo não vê layout (`M9`);
- a aba Time **com 8–9 membros por time** mostra quase tudo para todos: ela
  só separa de verdade quando os times forem revisados na tela Times.


---

# ✅ A verificação de 23/09 (16h), depois da rodada — só leitura

🔵 Pedido dele: *"verifique se os serviços e recursos para uso do movizap
funcionam corretamente"*. Nada foi enviado nem alterado.

| Recurso | Medido |
|---|---|
| Serviço `movizap` | ativo; **3.767 requisições na última hora, 0 erro** no log |
| Tela | a publicada é a nova (`index-nQqmIY-R.js`) |
| WhatsApp | Atendimento e Informativos com estado `open` |
| Webhook | 349 eventos na última hora; **0 pendente; 0 erro em 24 h**; mensagem entrando e saindo |
| E-mail (`ler_caixa`, a cada 2 min) | lendo; 2 `ReadTimeout` do Gmail no log inteiro, recuperados na rodada seguinte |
| Chat interno | 18 mensagens nas últimas 24 h |
| Sync do Harmonit | 05:45 e 17:45 em dia (#106); **os mesmos 7 erros por rodada** há dias |
| Backup do banco | 02:40 (cron) e 15:22 (manual, antes da 049/050) |
| Migrações | 049 e 050 aplicadas; `numero_bloqueado` existe |

## 🔴 O defeito que a verificação achou (existe desde 07/08)

**O atendente fica SEM a lista de times e SEM as classificações na Caixa.**

- A Caixa carrega `/api/times` e `/api/classificacoes` num `Promise.all`;
- `/api/classificacoes` exige `CFG_4.1` (tela de configuração) — atendente
  recebe **403** (20 vezes em 12 h);
- a rejeição derruba o `Promise.all` inteiro, e `times` também fica vazio,
  embora `/api/times` responda 200 (é aberta a `ATD_1.1`).

**Efeito:** no "Transferir", o seletor de time aparece vazio para quem não é
dono — **é por isso que nenhuma conversa tem time**, e a aba Time (entregue
hoje) não recebe nada. No "Concluir", a classificação fica sem opção (ela
não é obrigatória desde 11/08, então concluir funciona).

🟡 **Proposta, não aplicada:** pedir as duas listas separadas e abrir a
LEITURA das classificações a quem atende (`ATD_1.2`); a escrita continua em
`CFG_4.1`. Teste de tela com o 403 simulado. **Esperando a palavra dele.**

⚠️ **Por que a suíte não pegou:** os testes da Caixa montam a tela com o dublê
devolvendo 200 para tudo — o 403 é do perfil, e o dublê não tem perfil.

## A Evolution — avaliada, atualização adiada por ele

As 4 rodam **2.3.7**, a última estável; acima só a 2.4.0-rc (mai/2026), com
licença obrigatória. Detalhe e propostas no `Proximos_Passos` › 0.5 › 3.


## ✅ Corrigido em 23/09 (16h30), com a palavra dele (*"pode aplicar 1"*)

- `GET /api/classificacoes` passou a exigir **`ATD_1.2`** (quem atende); criar,
  editar e desativar continuam em `CFG_4.1`; as **inativas** só vêm para quem
  alcança `CFG_4.1`.
- A Caixa carrega times e classificações com `Promise.allSettled`: uma lista
  que falha não apaga a outra.

**Prova:** `tests/teste_classificacoes_leitura.py` (atendente real de teste)
e o caso novo do `caixa_2309.teste.js` — **os dois reprovam com o código
anterior**; o caso das inativas reprova sem a guarda. Suíte **1.148 verdes**
antes de publicar. **No serviço no ar, como a atendente Karla:** as duas rotas
respondem 200 e os **7 times** aparecem.

⚠️ **Achado da mesma medição:** o cadastro de classificações está **vazio**
(0 linhas; nenhuma das 121 concluídas tem classificação). A lista vazia é
correta — "Classificar" está pausado por ele desde 31/08.

⚠️ **E um defeito MEU no caminho:** a primeira versão do teste das inativas
lia a coluna `ativa`, que não existe (é `ativo`), e passaria sempre. Pego ao
medir o banco; o teste passou a criar uma ativa e uma inativa e conferir pelo
nome.


## 24/09 — presença: status por tempo, offline não recebe, afastamento, fim de expediente

🔵 Pedidos dele, com as respostas que ele deu às perguntas:

| # | Pedido | Onde |
|---|---|---|
| 1 | *"painel de regra de tempo por status, igual ao MSN = 15min sem interação -Ausente; 1h sem interação Offline"* -- interação = **só ação de atendimento** | Configurações › Geral; `presenca.py` |
| 2 | *"Não é possivel receber conversa se estiver offline, ao transferir, no painel, aparece informação para o atendente 'O atendente escolhido está offline e não poderá continuar o atendimento'"* | `conversas.transferir` + painel Transferir |
| 3 | *"Para o owner, pode ter o status para marcar 'sempre online' - dentro da jornada que o owner tbm terá, mas será exclusivo dele"* | Minha conta |
| 4 | modal obrigatório de transferência *"somente em caso de férias ou algo do tipo"* | Atendentes › Editar › Afastamento |
| 5 | *"fim do expediente não transfere, só informará mensagem pronta"*, em branco e com *"'ativar' ou 'não'"* | Geral; `automacao.fora_do_expediente` |
| 6 | jornada: *"copiar para os dias"* e *"mostrar a duração"* | Atendentes › Editar › Jornada |

🟡 **Decisões minhas**, cada uma com o porquê:
- **Ler não é ação.** A Caixa relê a conversa aberta a cada 8 s; contar leitura
  manteria online quem só deixou a aba aberta. Contam as rotas que passam por
  `_exige_estar_na_conversa` (quem ESCREVE) mais assumir e entrar.
- **O sistema só desfaz o que ele fez** (`estado_automatico`): como o MSN, a
  próxima ação devolve a "disponível" quem a regra derrubou; o que a pessoa
  escolheu fica. Escolher estado conta como ação.
- **A regra nasce desligada**; ligar dá "agora" como ponto de partida a quem
  nunca agiu. Ligada de cara, os 10 iriam para offline no mesmo minuto.
- **Mensagem de fim de expediente** só quando a conversa tem dono, a jornada
  está ligada, o dono tem jornada e está fora dela; uma vez a cada 12 h por
  conversa; nunca em grupo. Mesmas travas da saudação.
- **Afastar** exige destino também no backend, transfere uma a uma pelo
  caminho de sempre (rastro + nota) e só afasta se TODAS passaram. Escolher
  estado na Minha conta encerra o afastamento.
- No Transferir, o offline **continua escolhível** (é assim que se lê o aviso);
  quem trava é o botão, e a API.

🚨 **CAIU A REGRA DE 17/09** (*"offline é escolhido, não deduzido"*), por
decisão dele. As frases que a afirmavam na Minha conta passaram a depender da
regra: com ela ligada, a tela diz que o sistema também muda o estado.

🚨 **ACHADO NO CAMINHO — `em_jornada` IGNORAVA O FUSO.** Recebia `now(utc)` e
comparava com a jornada gravada em hora local: 08:00-12:00 virava "fora" às
09:00 de Brasília. O comentário de quem chamava dizia que respeitava o fuso.
Ninguém tinha jornada (medido em 24/09), então nada foi afetado; o teste
`test_em_jornada_usa_o_fuso_da_pessoa` reprova no código antigo.


## 24/09 (tarde) — lote para a Ludmila, auditoria e distribuição automática da fila

### O lote (🔵 *"os que tem mensagem não lida e sem atendimento a mais de 1 dia, pode colocar para ludmilla"*)

Regra lida: conversa direta, sem dono, com a última mensagem sendo do
cliente e com mais de 1 dia. Medido antes: **43** (8 de 1 a 7 dias, 16 de 7 a
30, 19 com mais de 30; a mais antiga de 07/08), nenhuma com time. Feito pelo
caminho de sempre (`conversas.transferir`), registrado em nome do owner e com
a nota *"Transferida em lote para Ludmila por decisão do owner (24/09)"*.
**Uma primeiro, conferida relendo o banco; depois as 42.** 43 de 43 certas,
0 falhas. A Ludmila passou de 13 para 56 conversas abertas.

### A auditoria (pedida por ele) — 8 pontos, 4 achados, todos corrigidos

| # | Ponto | Resultado |
|---|---|---|
| 1 | Trava do owner | 6 de 6 rotas OK. 🚨 **Achado:** e-mail não era único e a entrada pelo Google casava por `sub` OU e-mail sem ordem -- um admin criando conta com o e-mail do owner deixava a entrada dele ambígua, podendo derrubá-la. **Migração 053** (e-mail único) + entrada prefere quem já tem o `sub` |
| 2 | Offline não recebe | 🚨 **Achado:** quando o dono sai, o herdeiro era escolhido sem olhar offline/afastado. Corrigido; o teste reprova no código antigo |
| 3 | Corrida da regra de tempo | OK |
| 4 | Afastamento pela metade | Backend OK; a tela passou a reler a lista quando falha |
| 5 | Fim de expediente | OK (só mensagem do cliente, nunca grupo, nunca duas vezes) |
| 6 | O que a API dá ao admin | OK; o login vai na resposta (não é segredo; a tela esconde) |
| 7 | Rota removida | OK, ninguém a chama |
| 8 | Textos falsos | 🚨 **Achado:** a ajuda da Caixa ensinava j/k/a/c SEMPRE, e os atalhos nascem desligados. Agora só aparece com eles ligados, e mostra a tecla DA PESSOA |

### Distribuição automática da fila (Configurações › Geral)

🔵 Pedido: *"as conversas novas ou que fiquem 10min sem ninguem assumir, vão
automatiamente para a Ludmilla, coloque em uma caixa de seleção"*. Respostas
dele: **1a** só entra conversa em que o cliente escrever depois de ligar;
**2b** nenhuma vai na hora, todas após o tempo; **3** *"se tiver time não vai
a ela"*; **4a** *"Vão para Erika na mesma regra e depois fila se ambas
estiverem offline"*, com aviso.

- Caixas de seleção **Quem recebe** e **Se estiver offline, vai para**, e o
  tempo (10 min). Nasce **desligada**; ligar grava o marco da regra 1a.
- 🟡 Os minutos contam da **primeira** mensagem do cliente depois da última
  resposta nossa; grupos ficam de fora; a nota é do **sistema**; motivo
  `inatividade` (existia no vocabulário e nunca tinha sido usado).
- 🚨 **A trava da corrida:** `transferir(..., so_se_sem_dono=True)` põe a
  condição no próprio UPDATE -- quem assumir no mesmo segundo ganha.
- Fila e Início mostram para onde está indo, que o primeiro está offline, ou
  que parou (`AvisoDistribuicao.vue`).
- Roda no laço de 1 min da presença, **depois** da regra de status.


## 24/09 (fim da tarde) — notificações (CFG_11.1) e a regra de status em 30 min

### Notificações

🔵 Pedidos dele, com as respostas às quatro perguntas: contador nas **abas**
(*"somente minhas e time, por enquanto"*); notificação *"somente de conversas
assumidas"*; teto de **4**, e *"entrar uma nova, dai toca uma vez só e para,
assim não some a atenção"*; *"pisca aba obrigatoriamente"*; tom e volume
*"com minimo de 1 (1 até 5)"* por pessoa; o liga/desliga por pessoa *"só
aparece ao Owner"*, e desligada *"some tudo"*.

| Peça | Onde |
|---|---|
| Verificador (em toda tela, a cada 8 s) | `componentes/Notificador.vue`, montado na casca (`App.vue`) |
| A regra de quando toca, em função pura | `util/regraToque.js` — testada com 2, 20, "conversa nova" e F5 |
| Os tons (Clássico, Suave, Sino, Alerta), gerados no navegador | `util/som.js` — sem arquivo; volume 1–5 sem mudo |
| Rota | `GET /api/eu/notificacoes` (abas, `assumidas`, `donas`, ativa, tom, volume) — conta com a MESMA `conversas.listar` da Caixa |
| Tela | Configurações › **Notificações** (`CFG_11.1`, `atendimento`) |
| Liga/desliga do owner | `atendente.notificacao_ativa` (054); `GET /api/notificacoes/equipe` e `PUT /api/atendentes/{id}/notificacao` recusam quem não é owner |

🟡 Decisões minhas: a primeira leitura depois de abrir o painel **nunca toca**
(senão todo F5 tocaria até 4 vezes); mensagem nova numa conversa que já estava
não lida não toca de novo; a aba só pisca com o painel em **segundo plano**;
desligada pelo owner, o **contador fica** (é informativo); o navegador bloqueia
som antes do primeiro clique, e a tela mostra *"Clique para ativar o som das
notificações"* em vez de falhar calada.

⚠️ **O contador da aba é selo no canto**, fora do fluxo: em linha ele alargava
as abas e as quatro quebravam em duas linhas (visto na prévia).

Medido no ar (24/09, 16:14): a rota leva 92–162 ms por pessoa; os 11 nascem
com notificação ligada. A Ludmila tinha 1 não lida em Minhas numa conversa
que ela só **acompanha** — não toca, porque não é dona. É a regra.

### A regra de status em 30 min

🔵 *"pode ajustar para 30, mas deve ser ajustada no painel por mim mesmo"*:
Ausente = **30 min** (era 15), Offline = 60, gravados na `config`. A regra
**continua desligada** — ele liga na Geral.

### S20 — o script revisado, NÃO aplicado

🔵 *"corrija o script do S20 mas nao implante ainda"*. Dois defeitos corrigidos
(rodar duas vezes deixava o nginx quebrado no disco; falha no `nginx -t` não
restaurava) e backups fora de `sites-enabled`. Exercitado em cópia: aplica uma
vez, na segunda não faz nada, e no caminho de falha restaura idêntico (hash).
Espera a decisão dele.


## 25/09 — o owner sai dos textos, e o Plano 1 (Atendentes e Times)

### O owner é invisível para a operação

🔵 *"owner é invisível para operação do Movizap, não pode ficar sendo usado como
justificativa ou explicação."* Texto de tela diz o que acontece, não quem
decidiu. No ar às 09:28: 9 textos trocados (Notificações, Minha conta, Geral,
Atendentes, Início) e as 4 recusas da API viraram *"Você não tem permissão
para esta alteração."*. Os 43 resumos do lote de 24/09 (*"por decisão do
owner"*) foram reescritos no banco para *"Cliente esperando há mais de 1 dia,
sem atendimento."*, 43 de 43 relidos.

**🚨 Configurações: seis abas abriam sem a barra de abas (corrigido 25/09, 11:27).**
Geral e Atalhos (28/08), depois Eventos, Minha conta (22/09), Notificações
(24/09) e Mensagens rápidas (25/09) montavam a página direto em vez da casca:
clicar na aba sumia com a barra e a pessoa ficava presa. O comentário do
roteador dizia o contrário. Achado pelo owner (*"não encontrei nas minhas
configurações como owner"*). Agora todas montam a casca, e
`config_rotas.teste.js` reprova se uma voltar a montar direto. Detalhe: a
lista de abas é lida ao abrir o painel -- aba nova só aparece depois de
recarregar.

**Plano 1 no ar em 25/09, 10:47** (restart → build → migração 056; a 055 entrou
às 10:31). Suíte completa 1.231 verde antes; conferido depois em produção:
11 ativos, owner fora da lista do admin, laço de afastamentos sem erro.

### Atendentes (CAD_2.1)

| O quê | Como ficou | Origem |
|---|---|---|
| Ativo/Inativo | interruptor na seção **Acesso** do Editar, no lugar do botão "Desligar". Inativar confirma e pede quem recebe as conversas abertas (obrigatório); reativar é direto. A própria conta não tem interruptor. Inativo não entra e a sessão cai; conta, times e histórico ficam | 🔵 *"um interruptor, inativo não loga a conta permanece lá"* |
| Owner para o admin | some da lista, do detalhe (404) e dos membros dos times; salvar um time sem vê-lo não o tira de lá | 🔵 *"owner não deve aparecer para admin"* |
| Teto de conversas | saiu da tela, da API e da Minha conta | 🔵 *"não deve haver máximo de conversas"* |
| Afastar | **Saída** (hoje por padrão) e **Volta** (obrigatória). Saída hoje: transfere já. Saída futura: "Marcar afastamento", substituto obrigatório (offline agora pode ser escolhido; se no dia não puder receber, as conversas vão para a fila). A lista mostra "Férias de dd/mm a dd/mm"; o Editar tem "Cancelar afastamento marcado" | 🔵 *"um calendário já indica a saída e a volta, daí volta"* |
| Volta | automática no dia; a pessoa volta **offline** | 🔵 a volta; 🟡 o offline |
| "mostrar desligados" | virou "mostrar inativos"; o chip, "inativo" | 🟡 |

### Minha conta (CFG_10.1)

Afastado ou com afastamento marcado, aparece o campo **Dia da volta**: hoje ou
antes encerra (ou cancela o marcado). 🔵 *"ela loga e vai na configuração
dela e coloca o dia de ontem"*. Os quatro estados ficam **travados** (e com
cara de travados) enquanto está afastada; o backend recusa também. A frase
antiga, *"Escolher um estado abaixo encerra o afastamento"*, saiu (M12).

### Caixa de entrada › aba Time

🔵 *"o filtro dele pode ter filtro por times que a pessoa estiver inserida"*.
Quem está em dois ou mais times ganha **Filtrar por time** ("Todos os meus
times" ou um deles); com um time só, não aparece. Cada conversa da aba mostra
o selo do time. `/api/times` passou a trazer `sou_membro`.

### Achado lateral, sem mexer

Na Caixa em largura de celular (390 px) a lista já aperta: nomes cortados em
"J..." e as marcas de uma conversa passam por baixo do painel vazio. É
anterior a 25/09.

## 25/09 — Plano 2: notificações

**No ar em 25/09, 10:57** (restart → build; sem migração). Suíte completa
1.236 verde antes.

| O quê | Como ficou | Origem |
|---|---|---|
| Só marca lida o que foi visto | a Caixa relê a conversa aberta a cada 8 s com `?ler=false` quando a aba está escondida; ao voltar para a aba, relê já e marca. Abrir a conversa continua marcando (regra da Erika, 15/09). Antes, a mensagem que chegava com a pessoa fora da tela virava "lida" em até 8 s, sem tocar | 🔵 *"Só marca lida vista"* |
| A conversa à vista não toca | a Caixa avisa ao Notificador qual está aberta (`notificacoes.conversaAberta`); com a aba à vista, ela não toca (e continua contando para o teto de 4) | 🔵 mesma resposta |
| Aviso no canto da tela ("igual do MSN") | balão do navegador com **nome + trecho** (até ~100 caracteres; mídia vira "Foto", "Áudio"...), só com o painel fora de foco, um por conversa (`tag`); clicar abre a conversa. Permissão pedida em contexto: convite no canto ("Ativar avisos na tela" / "Agora não", que some por 7 dias) e linha na CFG_11.1 com o estado (ativado / ativar / bloqueado, com o passo a passo) | 🔵 *"igual do MSN?"*, *"considere UX/UI"*, *"Nome + trecho"*; 🟡 o desenho |
| Contagem das abas | `listar(so_nao_lidas=True)` pela mesma régua da bolinha, sem o teto de 500 que cortava calado; medida em 25/09: de 71–131 ms para 29–45 ms por pessoa a cada 8 s, e o mesmo resultado da lista antiga para os 3 atendentes com mais conversas | 🟡 |
| Ligar/desligar de id inexistente | 404 (era 200 vazio) | 🟡 |

**Fica de fora, com o motivo:** várias abas (medido: ~1 aba por IP, sem dado
por pessoa) · conversa sem dono não toca (a distribuição para a Ludmila existe
e toca pelo fluxo normal, mas **está desligada e sem ninguém escolhido** --
quem liga é ele, na Geral) · Chat interno e E-mail (*"somente minhas e time,
por enquanto"*).

**Limites que a tela diz:** o aviso só sai com uma aba do MoviZap aberta, e o
"Não perturbe" do Windows o cala. Clicar no aviso com a Caixa já aberta agora
abre a conversa (antes a URL mudava e a conversa não: faltava o `watch` no id
da rota).

## 25/09 — Plano 3: mensagens rápidas (CFG_12.1)

**No ar em 25/09, 11:12** (migração 057 às 11:01 → restart → build). Testes
direcionados verdes (214 Python, 207 JS); a suíte completa já tinha rodado
duas vezes na sessão, o teto combinado.

### Configurações › Mensagens rápidas

| O quê | Como ficou | Origem |
|---|---|---|
| Três abas | **Padrões** (owner e admin criam; quem atende vê só para leitura), **Minhas notas** (cada um as suas; só a pessoa vê), **Formulários** (links; owner e admin) | 🔵 *"Serão em tipos: pode criar uma aba disso nas configurações"*, *"Owner e admin criam as do tipo 'Padrões'"*, *"O formulario serão links"* |
| Apelido | obrigatório, até 60; é o que aparece na lista da conversa. Único por tipo (e por dono, nas notas) | 🔵 *"apelido curto como 'Mensagem de encerramento'"* |
| Variáveis | três botões inserem no cursor: **Cliente** `{cliente}` (a empresa), **Nome do contato** `{contato}` (a pessoa; sem cadastro, o nome do WhatsApp), **Saudação do horário** `{saudacao}` (Bom dia até 12h, Boa tarde até 18h, Boa noite). Prévia com "Pastelaria Velasco" e "João" | 🔵 as três e *"Empresa × pessoa"*; 🟡 os cortes, os botões, a prévia, o nome do WhatsApp como reserva |
| Formulário | campo de link; recusa o que não começa com `https://` | 🔵 links; 🟡 a validação |
| Desativar e apagar | "Aparece na conversa" desliga sem apagar; apagar pede confirmação e não mexe no que já foi enviado | 🟡 |

### O botão na conversa

Botão **redondo** com o raio, ao lado do microfone, na Caixa de entrada e no
Chat interno. Abre o menu **Mensagens rápidas** com as abas dos tipos, busca
pelo apelido e teclado (setas, Enter, Esc). Escolher preenche as variáveis com
a conversa aberta e põe o texto **no cursor** do campo, **ainda editável**;
variável sem dado fica em branco e aparece o aviso *"Sem dado para Cliente:
ficou em branco. Confira antes de enviar."* No Chat interno aparecem só
**Minhas notas e Formulários**. No celular, o menu vira folha fixa com 16 px
de margem.
🔵 *"no canto inferior das conversas, pode ter o botão redondinho"*, *"Só o
botão"*, *"Minhas notas e Formulários"* (interno); 🟡 busca, teclado e aviso.

### Anexo com texto, e o áudio

O texto do campo já ia junto do anexo (é a legenda). 🔵 *"se não estiver
assim hoje, já aproveite revisitar e ajustar"*: com **áudio**, o WhatsApp não
mostra legenda, e o cliente não recebia o texto. Agora, com áudio, o texto sai
**numa mensagem própria, logo depois**; imagem, vídeo e documento continuam
com legenda. Falta provar num envio real.

## 25/09 — modo celular (Caixa e Chat interno)

🔵 *"verifique a compatibilidade do movizap somente para chat interno e
externo via navegador mobile, os mesmos recursos, porém somente os chats"*.
No ar às 17:22, com a palavra dele (*"pode sim"*); o computador não mudou.

**Como foi medido antes de construir:** prévia Playwright em 390×844 com
toque (Chromium), frontend copiado em `/tmp`, API simulada. Achou que
**nenhuma das duas telas era usável no celular**: lista e conversa
empilhadas na mesma tela, mensagens somem numa faixa de ~30 px entre
cabeçalho e campo de escrever, ações do balão só apareciam no hover (0
visíveis no toque), menu lateral ocupava 62 px dos 390, alvos de toque
abaixo de 40 px.

| O quê | Como ficou |
|---|---|
| `BarraCelular.vue` | Caixa, Chat interno, Sair — nasce só em largura de celular |
| Navegação | lista **ou** conversa, nunca as duas juntas; botão Voltar e o voltar do aparelho funcionam |
| Ações do balão | viram acessíveis por toque (antes só apareciam com o mouse em cima) |
| URL | `/chat?sala=`, para abrir direto numa sala |
| Alvos de toque | 44 px, o piso já usado no resto do painel |
| Altura da tela | `dvh` no lugar de `vh` — o teclado do celular não empurra o layout |
| Áudio do iPhone | rótulo `audio/mp4` em vez de `audio/ogg` (o iPhone grava MP4/AAC, não Ogg) |

**Provado na prévia:** fluxo inteiro em 390 px, 0 erros de JavaScript, 209
testes JS verdes, computador idêntico em 1280 px. **Falta ele:** testar no
celular real, inclusive o áudio pelo iPhone para `+5518998116168`, e o
celular deitado.

## 15/10 — Ligações do MicroSIP: a aba (LIG_1.1)

🔵 *"considere que vamos precisar de uma aba nova no Movizap para 'Ligações' -
a idéia é um grid simples que tenha as ligações do historico do MicroSip,
consultadas por cliente - ja da base Movizap, ou por Atendente, ou por data ou
por numero, etc, exportar e importar e um botão para baixar a ligação se quiser
ou reproduzir por lá"*.

### A aba Ligações

Grid com uma linha por ligação: quando, sentido (feita, recebida, perdida),
número, cliente, atendente (com o ramal), duração e a gravação. Filtros de
período, atendente, sentido, número e "só com gravação"; paginação de 50.

- **Ouvir e baixar na própria linha.** O áudio vem por `pedirBlob` (o token
  vive no cabeçalho, e `<audio src>` não o manda); arrastar funciona porque o
  blob está inteiro na memória. Um player por vez, e o blob é liberado ao
  trocar ou sair da tela.
- **Exportar CSV** do que está filtrado, com rastro: quem exportou, quando,
  com que filtros e quantas linhas (`ligacao_exportacao`).
- **Faixa de cobertura no topo**, e é ela que impede a tela de mentir por
  omissão: diz quantos atendentes têm agente, com o último contato de cada um,
  e **nomeia quem está de fora**. Sem isso, quem não tem agente instalado
  pareceria não ter ligado. A mesma frase aparece no estado vazio.
- **Cliente em várias empresas** vira "nome +N", nunca uma empresa escolhida
  no lugar das outras. Sem cadastro aparece como "sem cadastro", que é
  diferente de vazio.
- ⚠️ **Não há busca de empresa por nome:** isso é `CAD_1.1`, permissão que
  esta aba não tem. Quando se chega aqui pela ficha de uma conversa, o
  `cliente_id` vem na URL e aparece como chip removível.
- 🚨 **Nasceu só do owner e durou um dia.** Horas depois, em 15/10: *"pode
  exibir a aba para todos"*. Passou à permissão **`atendimento`** — todo
  atendente (e o admin) vê a aba, ouve, baixa e exporta. Fica de fora só o
  perfil `cadastro`. É por isso que o rastro de `ligacao_exportacao` deixou de
  ser detalhe: com a aba aberta a todos, ele é a única resposta para "quem
  levou o quê".
- O **import** que ele pediu junto é o Bloco 9 do plano (retroativo de PC que
  ainda não tinha agente) e não entrou nesta rodada.

## 28/09 — Plano 4: nota editável, Chat interno com a cara da Caixa, anexos em lote

**No ar em 28/09** (migração 061 → restart → build). Suíte completa
1269/1272 antes de publicar (as 3 falhas são de antes desta sessão, sem
relação — dois testes de layout e a documentação da migração 060).
Detalhe técnico em `docs/02_Modelo_Dados.md`.

### Nota interna (Caixa de entrada)

🔵 *"nota interna editável/apagável por quem escreveu, com 'editada por X,
em…' e ícone da versão anterior"*. Mesmo botão de editar/apagar que a
mensagem enviada já tinha, agora também no balão de nota (`.balao--interna`).
**Sem janela de tempo** (decisão dele, 28/09) — é registro interno, nunca
sai para o cliente. Reaproveita as colunas que a Caixa já tinha desde 17/09;
não precisou de tabela nova.

### Chat interno: editar, apagar e o visual da Caixa

🔵 *"editar (15 min) e apagar (48h) a própria mensagem, como na Caixa"* +
*"ajustar o painel interno visualmente igual ao do externo e as
confirmações de envio e leitura tbm"*. O balão do Chat interno passou a
usar o mesmo desenho da Caixa — cor, bico, tique — no lugar da cor de
acento genérica de antes. Tique de leitura: em conversa de duas pessoas,
mostra ✓✓ azul quando o outro leu; em grupo, só quando **todos** leram
(decisão dele). Não existe "entregue" aqui — é tudo local, sem WhatsApp
envolvido.

### Até 10 anexos por envio

🔵 *"até 10 anexos por envio, texto na 1ª mensagem, 25 MB cada"* — Caixa e
Chat interno. Seleciona vários de uma vez; cada um vira um balão, o texto
digitado vai só no primeiro. Se um arquivo do meio falhar, para e avisa
quantos já foram enviados.

**Fica de fora, registrado, não pedido:** o Chat interno ainda marca como
lida mesmo com a aba em segundo plano (a Caixa só marca com a aba visível,
desde o Plano 2) · decifrar a edição cifrada de cliente em grupo (achado de
25/09, é criptografia real, não virou código).


## ATD_1.2 — Ligações, Outros contatos e rascunho (15/10)

**Botão `Ligações`** na ficha: modal com as ligações daquele número nos
**últimos 7 dias**, separadas em `Feitas`, `Recebidas` e `Perdidas`, com hora,
duração, quem atendeu, e ouvir/baixar a gravação na própria linha. O modal diz
**quantos atendentes têm agente instalado** — sem essa linha, "nenhuma ligação"
e "aquele PC não manda" ficam iguais na tela. O rodapé **Ver todas na aba
Ligações** aparece só para quem tem `LIG_1.1`.

**Botão `Outros contatos`** na ficha: os contatos da empresa vinculada, com
papel e telefone, o atual marcado como "este", chip `sem WhatsApp` para quem
foi conferido e não tem, e **Mensagem** por linha, que pula para a conversa
daquele número (ou abre "Nova mensagem" preenchida, se ela ainda não existe).
Vazio **diz por quê**: número sem cadastro é um caso, empresa com um contato só
é outro.

**O `dt>Contato` passou a mostrar o telefone** — os dois primeiros, com `+N`
quando há mais.

**Rascunho por conversa:** o que foi digitado e não enviado fica guardado
naquela conversa (`localStorage`, chave `movizap.rascunho.<id>`), sobrevive a
F5 e à troca de conversa, aparece como chip **rascunho** na lista, e morre em
três momentos: envio bem-sucedido, texto apagado, e fim da sessão do dia.
🚨 Antes disso o texto **vazava** para a conversa seguinte.

**A barra de status** passou a dizer `sessão do dia · até HH:MM`, em cor de
aviso nos últimos 15 minutos.


## ATD_1.2 — a ficha, desenho A (15/10)

🔵 *"essa tela dentro da ficha esta redundante e um pouco feia"* → três mockups
→ *"Tipo A 100%"*.

**O defeito que ele viu:** o mesmo telefone **três vezes** na mesma tela — no
topo, em "Contato" (o nome do contato, derivado, era o próprio número) e na
linha de telefones acrescentada horas antes no Bloco 6. Duas das três eram
minhas, do mesmo dia.

O que está no ar:

1. **O telefone aparece uma vez.** A linha de telefones do Bloco 6 saiu.
2. **Nome derivado não se mostra como nome:** quando `contato.nome` é o próprio
   telefone, a ficha diz **"sem nome no cadastro"**. Ausência de dado com cara
   de dado é tela que mente. A comparação é por dígitos e exige 10 ou mais,
   para não confundir nome com número.
3. **As três consultas dividem uma linha** (`Ligações`, `Contatos`, `Empresas`),
   em vez de três botões soltos numa gaveta que é `flex-direction: column` e
   tem `max-height: 45%`. Rótulo curto na barra, nome inteiro no `title`.
4. **A empresa é um cartão:** razão social com peso, nome fantasia como
   subtítulo, CNPJ e e-mail numa linha de apoio com ícone. Os rótulos "Nome
   fantasia" e "CNPJ/CPF" saíram — o dado fala por si. O e-mail **quebra** em
   vez de cortar com reticências: e-mail cortado não dá para copiar.
5. **Desvincular saiu da pilha das consultas** e foi para o pé, depois de um
   fio, ao lado da contagem de empresas. Eram três botões de ler e um de
   apagar, todos iguais.
6. **O botão `Contatos` só existe havendo empresa** — sem ela o modal só teria
   "este número não está no cadastro", que a ficha já diz em âmbar.

⚠️ **Uma coisa do mockup A que NÃO foi feita:** lá o "Tipo" era chip no topo.
Aqui ele **fica na lista de dados**, porque para quem tem `podeTrocarTipo` ele é
um `<select>` — um controle, não um rótulo. Chip no topo mais campo embaixo
recriaria a duplicação que o desenho existe para matar.

**Provado:** 32 testes em `frontend/src/ficha_1510.teste.js` (a guarda do Bloco
6 que afirmava o contrário foi **reescrita**, não apagada: ela passou a guardar
a decisão nova), suíte de frontend **261 verdes**, e os 4 arquivos de teste que
leem a `CaixaDeEntrada.vue` conferidos à parte.


## ATD_1.2 — o log de ações na conversa (Bloco 11, 15/10)

🔵 *"ao final proponha log dentro da conversa interno apenas sobre ações de
transfernecia, inserir pessoas, etc, pode ser em Nota interna do Movizap"*.

Treze ações passam a deixar **uma linha** na conversa, no ponto do tempo em que
aconteceram: assumir, entrar, convidar, sair, remover alguém, devolver à fila,
transferir, encerrar, vincular, desvincular, mudar o tipo, bloquear e
desbloquear.

🚨 **LINHA, NÃO BALÃO.** Como balão o log entraria no fio com o mesmo peso do
que o cliente escreveu, ganharia o menu de editar e apagar, e a conversa viraria
metade conversa e metade log. Como linha discreta (ícone, quem fez, o que fez,
hora à direita) ele se lê de relance e se ignora de relance.

- **A frase vem do servidor**, nunca montada na tela: montá-la aqui faria o
  mesmo log ter dois textos quando esta tela mudasse, e o histórico não se
  reescreve junto com o frontend.
- **Evento que a tela não reconhece ainda aparece**, com um ponto no lugar do
  ícone. Tela que esconde o que não entende mente por omissão.
- **Sem os fios do separador de dia**: separador de dia aparece uma vez por
  dia; evento, várias vezes por atendimento. Com dois traços cada, o fio da
  conversa viraria uma escada.
- No celular a hora sai da linha — ali o que importa é o que aconteceu.
- **Transferência agora deixa rastro mesmo sem resumo.** A nota de resumo
  (23/09) só é gravada quando há resumo; até hoje, transferir sem escrever nada
  não deixava nenhuma marca na conversa. O evento e a nota de resumo são coisas
  diferentes e os dois continuam: a nota é o texto que quem assume precisa ler,
  o evento é o log.

**Provado:** 14 testes em `tests/teste_eventos_conversa.py` (cada ação, a
recusa de editar e apagar o evento, nota comum continuando editável, não contar
como não lida) e 8 em `frontend/src/eventos_1510.teste.js`.

⚠️ **Um teste que eu tive de desfazer:** a primeira versão chamava
`conversas.bloquear()`, que fala com a **API do WhatsApp de verdade** — a suíte
ficou pendurada nas retentativas de rede e o `timeout` teve de derrubar. Pior:
ia além de ler produção, ia tentar bloquear um número. Hoje o teste prova que
os dois eventos existem para o banco, e diz por escrito que quem prova o resto
é bloquear um número na tela.


## ATD_1.2 — "visto por" na nota (Bloco 12, 15/10)

🔵 *"um icone que ao clicar mostra que ja leu aquela nota, junto ao carimbo de
data e hora, bem pequeno mesmo"*.

Um olho pequeno ao lado do carimbo da nota, com o número de pessoas que a
tiveram na tela. Clicando, a lista: nome e hora de cada uma.

- 🚨 **"Visto por", nunca "leu".** O sistema sabe que a nota esteve na tela.
- 🚨 **Marca ao aparecer**, por `IntersectionObserver`, em lote e com 1,2 s de
  espera: rolar a conversa passa por dezenas de notas, e uma requisição por
  nota seria uma rajada.
- **Falhar ao marcar não vira erro na tela:** a pessoa está lendo e não pediu
  nada; o carimbo se perde e a nota é marcada na próxima vez em que aparecer.
- **Nota anterior ao início do registro diz isso**, em vez de "ninguém viu". A
  data mora no backend; repeti-la na tela criaria uma segunda verdade.
- O observador é remontado ao trocar de conversa e quando chega mensagem nova
  (o refresh de 8 s): elemento novo não nasce observado, e sem isso o recurso
  pareceria funcionar — as notas antigas apareceriam certas.

**Provado:** 11 testes em `tests/teste_nota_vista.py` e 9 em
`frontend/src/visto_por_1510.teste.js`.


## 19/10 — três pedidos dele, medidos antes de escritos

### LIG_1.1 — o REC de cada PC na faixa de cobertura

🔵 *"ajuste a mensagem do painel atual (...) inserindo no fim de cada linha de
o REC está ativado ou não"*.

O que fez o pedido existir: em 19/10, **4 dos 5 PCs com agente estavam com a
gravação automática desligada** no MicroSIP, e a faixa dizia "30 ligações" de
um PC que não tinha gravado nenhuma delas. Medido: 3404 com 32 ligações e 20
gravações; 3348 com 30 e **zero**; 3399 com 11 e zero; 3401 com 3 e zero; 3405
com 116 e zero.

- 🚨 **TRÊS estados, não dois.** O agente só fala do problema: manda
  `gravacao automatica desligada no MicroSIP` quando `Settings.autoRecording`
  ≠ 1, e **cala quando está ligada**. Então "REC ligado" é a ausência do aviso
  na **última** passada, e isso só vale para quem já falou. PC que nunca fez
  passada recebe **"REC não informado"** — dizer "ligado" ali seria a tela
  mentindo (`M12`).
- Quem não tem agente **não ganha chip nenhum**: a pergunta nem existe, e ele
  continua na linha "Sem agente".
- A régua mora no backend (`ligacoes_consulta.rec_do_agente`), uma função pura
  que a suíte exercita nos quatro casos; a tela só escolhe rótulo e cor.

**Provado:** 5 testes em `tests/teste_ligacoes_consulta.py` e 2 em
`frontend/src/ligacoes_1510.teste.js`.

### ATD_1.2 — TÉCNICO edita o nome, como LEAD

🔵 *"para tecnicos, adicione ele na regra do tipo 'LEAD' que permite editar o
nome"*.

O caso real são os técnicos importados em 02/10: o nome do WhatsApp divergia do
cadastro em 7 conversas (08/10), e quem atende não tinha como corrigir dali.
A regra virou uma lista (`RELACOES_COM_NOME_EDITAVEL = ['lead', 'tecnico']`),
nos dois lugares da ficha — com empresa e sem empresa, que é o caso do técnico
por desenho.

⚠️ **A trava de identidade não mudou:** isto edita o `contato.nome`, nunca o
telefone nem o vínculo. O backend já não filtrava por tipo — a regra era só da
tela, e continua sendo.

### CFG_7.1 — logado dentro da jornada não cai em offline

🔵 *"o status dos atendentes devem permanecer online ou ausente quando logados
dentro da jornada"*. Veio de ver o Thiago offline estando logado.

🚨 **O sistema não sabia quem estava logado.** O único relógio era
`ultima_acao_em`, e "ação" é **escrever** (mensagem, nota, chat interno, anexo,
editar, apagar, reagir). Quem passava a manhã lendo conversa não tocava o
relógio: ia a `ausente` em 30 min e a `offline` em 60, logado e olhando a tela.

O sinal que faltava já existia e ninguém usava: **a Caixa pede a lista a cada
8 s** enquanto a aba vive. Essa rota passou a carimbar `atendente.painel_visto_em`
(migração 067), no máximo uma escrita por minuto por pessoa.

- **Dentro da jornada + painel carimbado nos últimos 5 min:** a régua **não**
  põe em offline. O máximo é `ausente`.
- **`ausente` continua valendo**, e isto é de propósito: 30 min sem escrever é
  real, e dizer "disponível" para quem largou a aba aberta seria outra tela
  mentindo. Só `offline` barra distribuição; `ausente` não.
- **Painel fechado volta ao de antes:** 5 min depois o carimbo envelhece e o
  offline por tempo volta a valer.
- **Fora da jornada, nada muda.** E quem **não tem jornada cadastrada** não
  entra na proteção: jornada vazia é "ninguém disse quando", e supor 24 h
  deixaria a pessoa fora do offline para sempre.
- ⚠️ **O carimbo não é ação:** não devolve ninguém a "disponível" e não zera
  `ultima_acao_em`. Se contasse, abrir a Caixa zeraria o relógio de todo mundo
  e a régua nunca marcaria ninguém — há teste só para isso.
- ⚠️ **Escolha manual continua intocada.** Quem escolhe "Fora do expediente"
  na Minha conta fica assim, dentro ou fora da jornada — e era isso que o
  Thiago tinha (`estado_automatico = false`). A régua nova não o conserta;
  **decisão dele** se o sistema deve recusar essa escolha dentro do turno.
- **Os textos da Geral foram corrigidos junto**, porque passaram a mentir: a
  frase "ficar com a tela aberta sem agir não conta" virou "não conta para
  voltar a Disponível", e o cartão ganhou o aviso do novo teto.

**Provado:** 9 testes em `tests/teste_presenca.py` (50 no arquivo).


## 19/10, segunda volta — a jornada manda no status (CFG_7.1, CFG_10.1, ATD_1.1)

🔵 A regra dele, fechando o que de manhã eu tinha lido pela metade: *"dentro da
jornada cadastrada, impossível ficar fora do expediente e se for colocado offline,
volta automaticamente ao enviar mensagem para online e segue regras de tempo para
ausencia"*. E, revendo as seis propostas: *"pode remover esse status então"* (o Não
perturbe), *"se for ausente já cria caixa de aviso de ausência"*, e o prazo da fila
**ajustável na Geral**.

### O que ficou de pé, por dentro

`presenca.aplicar_regra` passa a régua em **três tempos, e a ordem é o desenho**:

1. **offline** — só para quem está **fora** da jornada (ou sem jornada cadastrada);
2. **curativo** — tira do offline quem está **dentro** da jornada, sem afastamento;
3. **ausente** — por último, de propósito: quem o curativo acabou de tirar do
   offline e está parado há mais de meia hora sai **na mesma passada** como "em
   pausa". 🚨 Medido ao vivo com o curativo no fim: **três pessoas ficaram um minuto
   inteiro aparecendo como "Disponível" sem ter aberto o painel**.

E mais três pontas, porque "impossível" só é invariante se alguém **cura**, e não
apenas se a régua deixa de causar:

- `definir_estado_manual` **recusa** `offline` dentro da jornada, com a frase que diz
  o caminho ("use Em pausa… no fim do turno o sistema põe você fora sozinho").
  🚨 Quem barra é o backend; a Minha conta desabilita o botão e **escreve o motivo em
  texto** (`title` não é rótulo, `M10`).
- `registrar_acao` passa a desfazer o `offline` **mesmo escolhido à mão**, dentro da
  jornada. 🚨 Só `offline`: "em pausa" escolhido fica, senão o único estado de uso
  que sobrou deixaria de existir para quem escreve uma mensagem.
- ⚠️ **Dois filtros de afastamento que faltavam.** Sem eles, qualquer nota ou reação
  de quem está de férias a poria "Disponível" com o afastamento de pé; e a borda de
  início do turno — defeito **anterior a hoje**, que estava latente porque a régua
  corrigia em 60 min — acordaria o afastado todo dia às 08:00.

### A trava de FILA, que é outra pergunta

🚨 Sem ela, `B1a` **mataria a reserva da distribuição**: `_destino` só caía da Ludmila
para a Erika quando `pode_receber` falhava, isto é, **só por offline** — e offline
dentro da jornada deixou de existir. A fila ficaria na Ludmila das 08h às 18h e o
"4a" (parada sem destino) nunca mais dispararia.

Então: **painel fechado há mais de 15 min (ajustável) sai da distribuição
automática**, e continua aceitando transferência à mão.

- Mora em `distribuicao._pode_receber_da_fila`, usada pelo `_destino` **e** pelo
  `situacao()` — a mesma função nos dois, senão a tela diria "vai para a Ludmila"
  enquanto a fila ia para a Erika.
- 🚨 **Não** mora em `presenca.pode_receber`: aquela régua serve também o substituto
  de afastamento, e barrar ali significaria não conseguir afastar alguém porque o
  substituto não estava com a aba aberta.
- `situacao()` devolve `parada_motivo`, para o aviso não chamar "painel fechado" de
  "offline" (`M12`).
- 🚨 **O carimbo do painel ganhou um segundo ponto.** Antes só a lista da Caixa
  escrevia `painel_visto_em` — quem passasse 20 min no Chat interno sairia da fila
  **trabalhando**. Agora o pedido de notificações também carimba, e ele roda em toda
  tela (`Notificador.vue` no `App.vue`), sem código novo no navegador.

### "Não perturbe" saiu (migração 068)

Medido antes de propor: ele **não perturbava nada**. Quem barra receber conversa é
`presenca.pode_receber`, e lá só `offline` e afastamento barram — a pessoa marcava,
continuava recebendo distribuição e transferência, e o botão não dizia isso. Zero
linhas no banco usavam o valor.

⚠️ E a remoção expôs um campo morto: **`estados_possiveis`**, que o backend manda em
`GET /api/eu/perfil`, **não era usado por tela nenhuma** — os botões saíam de uma
lista escrita à mão na Minha conta. Tirar o valor do backend não tirava o botão. Agora
a lista local diz o **rótulo** e o backend diz **quais**, que é a divisão certa.

### A Geral passou a dizer os três números e a última passada

Os três que governam o status ficam no mesmo cartão: ausente, offline (fora do turno)
e **sai-da-fila**. E uma linha nova: *"a régua passa a cada 1 min; a última vez que
mexeu em alguém foi …"*. 🚨 **Não existe carimbo de "passada"** e ler
`atendente.atualizado_em` seria mentira — nome, foto, times e afastamento carimbam a
mesma coluna. Grava-se o que é verdade (a última vez que a régua **mudou** alguém,
com as contagens), e o texto diz, em palavras, que silêncio significa *não mexeu em
ninguém*, não *não rodou*.

**Provado:** `tests/teste_presenca.py` e `tests/teste_distribuicao.py` (a trava de
fila, o curativo, a recusa dentro do turno, o afastado que não é ressuscitado, e o
"em pausa" que não é desfeito). Suítes: **1478 Python, 292 JS**.

🔴 **Não entrou, e segue na fila:** o aviso de "em pausa" ao transferir e ao
convidar; o rótulo único nas telas de Atendentes e na lista "Começar conversa" do
chat; o "painel aberto agora" em Atendentes; e o "online há X min" no chat interno.

---

## 21/10 — Agendamentos: o menu em grupos, o orçamento e o compromisso

🔵 Pedido dele de 19/10, em quatro partes: **Ligações para dentro de
Atendimento** · o menu **abrindo em grupos e subgrupos** · o grupo
**Painéis › Operacional** · e a tela **Agendamentos**, servida por um botão
**Agendar** na conversa, com três abas. Plano fechado em
`.claude\plans\1-n-o-dentro-da-merry-raven.md`, com 14 decisões dele.

### O menu (todas as telas)

Grupo e subgrupo passaram a ser **dado da tela** (`telas.py`), com fallback
pelo prefixo para nada sair do lugar. O nome do grupo virou botão: abre e
fecha, vários abertos ao mesmo tempo, lembrado por pessoa em `localStorage`
(`movizap_menu_grupos`, guardando **o que está fechado**). Grupo sem nenhuma
tela visível não é desenhado — é o que deixa **Painéis › Operacional** existir
declarado e nascer vazio. Detalhe em `docs/03_Registro_Telas.md`.

### `ATD_7.1` — Agendamentos

🔵 Decisão 14 dele: **é tela**, em Atendimento, **aberta a todo atendente**.
Mostra o carrossel da semana (ontem, hoje e os 5 próximos), o grid do dia com
hora, cliente, técnico, placas, OS, endereço, responsável, orçamento e estado,
e as ações de cada linha: reagendar, cancelar com motivo, reenviar confirmação
e abrir a conversa de origem.

🚨 **A tela diz a cobertura:** só aparece aqui o que foi agendado pelo
MoviZap. Mesma régua da faixa da aba Ligações — ausência não pode parecer
"não tem".

### `ATD_1.2` — o botão Agendar, atrás do `+`

🔵 Decisão 4 dele: o Agendar fica **junto de anexo, áudio e mensagem rápida**.
Leva ícone **e** palavra, pela régua de rótulo escrita na própria tela ("ganha
palavra o que age sobre a conversa"). A aba que abre depende do contato:
técnico vê **Orçamento** e **Agendar**; cliente vê **Confirmar**. Em conversa
sem contato o botão **explica por que não dá**, em vez de sumir.

O orçamento é documento numerado, com PDF anexado à conversa. 🚨 **O número só
se gasta quando o PDF existe** — reservar antes deixaria buraco na sequência
toda vez que alguém fechasse o modal. 🔵 Decisão 13: deslocamento é **por km**,
e o PDF imprime "77,7 km" (o documento de hoje imprime "77.7 un", e é isso que
faz a coluna parecer trocada). 🔵 Decisão 12: o catálogo tem **dois itens**,
com os nomes tirados do Harmonit uma vez, em 21/10: `KM DESLOCAMENTO` (6971) e
`PAGAMENTO DE TECNICO` (653939) — os mesmos ids que o Painel Financeiro do
FPSL já usa. Emitir orçamento **não depende do Harmonit estar no ar**.

### `CFG_13.1` — a numeração do orçamento (só owner)

O próximo número a ser emitido. ⚠️ A aba diz, em texto, que mudá-lo pode
**repetir documento já emitido pelo sistema atual**, que segue existindo fora
desta VPS.

### A ponte com o FPSL

As OS vivem no FPSL (SQLite, `os_historico`); o MoviZap é Postgres. A ponte é
de **leitura**, autenticada por segredo compartilhado, e cruza pelo
`harmonit_id`. ⚠️ **Lista vazia e FPSL fora do ar são coisas diferentes**: a
falha sobe como erro legível, nunca como "este cliente não tem OS".

## 21/10, terceira volta — as quatro pontas do plano de Agendamentos

### Ponta 1 — o cabeçalho diz o TIPO DA OS (`ATD_1.2`, modal Agendar)

🚨 **A ÚNICA DAS QUATRO QUE SAI PARA O CLIENTE.** O cabeçalho das duas
confirmações era `(SERVIÇO) | placas | cliente`, com a palavra literal; agora é
o **nome do tipo da OS**, em maiúsculas. Sem nome, o segmento **sai fora**:
`FZU5D16 | VELASCO`. Os números e o porquê estão no `docs/02`, na migração 072.

A lista de OS do passo 2 passou a mostrar o tipo ao lado da situação — o
operador vê, **antes de marcar**, o que o cliente vai ler — e diz
"tipo não nomeado no Harmonit" quando é o caso, em vez de calar.

🚨 **A MONTAGEM DAS DUAS MENSAGENS SAIU DO MODAL** para
`frontend/src/util/mensagem_agendamento.js`, porque a `ATD_7.1` também as monta
agora (ponta 2): a mesma mensagem escrita em dois lugares viraria duas
mensagens diferentes no primeiro ajuste de campo.

### Ponta 2 — "Reenviar confirmação" (`ATD_7.1`)

A quarta ação da linha; entregaram-se três em 21/10 (Reagendar, Cancelar, Abrir
conversa).

🚨 **NÃO ENVIA NADA**, e diz isso na tela — 🔵 decisão 6 dele ao pé da letra:
as duas confirmações saem pré-escritas e **quem envia é o atendente**. Ela
mostra os dois textos para copiar e oferece **abrir a conversa com o texto já
no compositor**, pelo rascunho por conversa do Bloco 7 (15/10).

🚨 **MONTA COM A MESMA REGRA DE AGRUPAMENTO** (mesma data e hora ⇒ uma
mensagem só, placas e OS somadas), e por isso junta os compromissos **irmãos**
daquele cliente naquela hora, menos os cancelados: reenviar só a linha clicada
mandaria ao cliente um texto diferente do que ele recebeu.

⚠️ **Compromisso ainda `aguardando` não tem responsável:** o campo sai vazio e
a tela **diz por quê** — quem o preenche é a aba Confirmar, na conversa do
cliente. ⚠️ E não sobrescreve rascunho do colega sem perguntar: perder meia
frase digitada é o defeito que o Bloco 7 nasceu para corrigir.

### Ponta 3 — o mês navegável ao lado do carrossel (`ATD_7.1`)

O carrossel entregava semana anterior / hoje / próxima. O mês é **atalho de
navegação, não uma segunda lista**: escolher um dia move a âncora do carrossel
e recarrega os sete dias. 🚨 **O selo de "tem serviço" não aparece no mês**, de
propósito: o que está carregado é a semana da âncora, então o mês saberia de uns
dias e não de outros — e um mês com pontos em três dias afirmaria que nos
outros não há nada. A tela diz onde as marcas estão.

### Ponta 4 — `CFG_14.1`, Vínculo dos técnicos

🟡 Sugestão minha, não pedido dele. A rota de pendências do vínculo existia
**sem tela**. A aba é **só owner** e mostra os **três buracos separados** —
juntá-los num número só esconderia o que fazer com cada um: técnico daqui sem
cadastro lá, cadastro lá sem contato aqui, e quem casa pelo telefone e ainda
não é do tipo técnico.

🚨 **SÓ LEITURA: ela mostra o trabalho, não o faz.** 🔵 *"nenhuma regra
resolve, é trabalho de cadastro"*. ⚠️ E **lista vazia é diferente de ponte fora
do ar**: se o FPSL não responder, a tela diz que não deu para consultar, em vez
de deixar o cadastro parecer em dia.

## 21/10, quarta volta — as cinco frentes depois do teste dele no navegador

🚨 **O QUE ABRIU ESTA VOLTA FOI USO, NÃO LEITURA.** Ele exercitou o fluxo às
15:11: orçamento nº 2, agendamento 211 criado e confirmado, tipo da OS gravado.
Sete apontamentos saíram dali, e nenhum deles qualquer teste tinha visto — a
família do `M9`.

### F1 — a barreira do técnico saiu (`ATD_1.2` → ponte → Harmonit)

🔵 *"a barreira de agendamento do tecnico não deve existir, no harmonit ja foi
liberada tbm"*. 🚨 **A barreira era NOSSA**: o `os_ponte._escolher_vinculo`
recusava antes de chamar, e foi o que derrubou o teste dele (*"Iago Santos do Ó
Souza ja tem compromisso nesta OS"*).

🚨 **E o Harmonit ainda recusa** — medido ao vivo: com a nossa barreira fora,
`AgendarTecnico` responde `Erro ao cadastrar Evento: TecnicoJaAgendado`. A
recusa dele é **do vínculo**, não do técnico, e a medição mostrou o caminho: nas
547 OS da base, o mesmo técnico tem vários compromissos, inclusive **dois na
mesma OS** (`usuarioId 14316` aparece duas vezes na OS 16921). Cada linha
`ordemServicoxTecnico` guarda **um** `agendamentoId`.

Então a ponte passou a fazer o que o próprio Harmonit faz: quando o vínculo
escolhido já tem compromisso, **cria outro vínculo** para o mesmo técnico
(`SalvarTecnicoOrdemServico`) e agenda nele. Provado na OS 16991: vínculo 1143048
→ compromisso 945220, com o 930447 dele intacto ao lado.

⚠️ **O QUE SOBROU DA GUARDA, e tinha de sobrar:** ambiguidade. Vários técnicos
na OS e nenhuma pista de qual continua sendo recusa — e a conta passou a ser
sobre **todos** os técnicos, não só os livres, senão a OS de três técnicos com
dois agendados escolheria o terceiro sozinha e em silêncio.

🚨 **A PROVA MUDOU JUNTO COM A BARREIRA.** Antes, "a OS tem `agendamentoId`" só
podia ser verdade depois da escrita. Agora é verdade **antes**, e relatar
sucesso por ela seria dizer "agendei" sobre o compromisso de outra pessoa.
Guarda-se o id anterior, e só vale se ele **mudou**.

### F2 — o tipo da OS em selo (`ATD_1.2`, passo 2)

🔵 *"o tipo da OS pode ter mais destaque"*. Era linha miúda cinza junto da
situação; virou **selo com cor por tipo**, ao lado do número da OS — o mesmo
peso, porque é o que o cliente lê no cabeçalho da mensagem. ⚠️ Mapa de cores
**fechado** nos 5 nomes que o Harmonit devolve: tipo fora dele cai no selo
neutro, que **diz** que não tem nome em vez de desaparecer.

### F3 — o calendário sempre aberto, e a trava do modal (`ATD_1.2`, passo 1)

🔵 *"o botão do calendário pode ficar um pouco mais perto ou ja aparecer em
aberto mesmo, ficar sempre aberto"*. 🚨 **Não foi o `showPicker()` do
navegador**: ele depende de cada navegador e fecha sozinho ao clicar fora —
"sempre aberto" não se sustentaria. O calendário é desenhado na tela, com os
horários ao lado, **de 30 em 30 minutos das 7h às 19h** (escolha minha,
declarada). ⚠️ O campo digitado **fica**, e é por ele que entra horário fora do
expediente — e é ele que o teclado e o teste usam. ⚠️ Dia passado não é
proibido: a tela avisa, não barra.

🔵 *"coloque trava nesse modal, se clicar fora dele no movizap ele aparece aviso
de 'cancelar' ou 'continuar'"*. Clicar no fundo **e o X** passam a perguntar.
🚨 O motivo é trabalho perdido: o modal guarda orçamento em digitação, OS
marcadas, data e endereço, e um clique no fundo apagava tudo sem avisar.
⚠️ O aviso diz que fechar perde o que não foi gravado — botão que promete o que
não cumpre é o defeito do "Não perturbe".

### F4 — o endereço em campos separados, com CEP (`ATD_1.2`, passo 3)

Os sete campos do Harmonit, **pré-preenchidos com o endereço da própria OS**
(nova rota `GET /api/agendamento/os/{numero}/endereco`, ao vivo). Endereço
vindo da fonte é melhor que endereço digitado — e das 30 OS amostradas, 23 têm
rua.

🔵 *"não poderíamos ter a consulta do CEP dentro do modal nesse momento? daí
preenche os campos e ela ainda edita se precisar?"* — sim: `GET /api/cep/{cep}`.
🚨 **O Harmonit não tem rota de CEP** (conferido nas 17 rotas de OS e nas de
dados de suporte), então a fonte é o **ViaCEP**, consultado **pelo nosso
backend** e não pelo navegador (escolha declarada: o CEP não sai do computador
do atendente, dá para guardar em memória e não há CORS no caminho).

🚨 **TRÊS RESPOSTAS DIFERENTES, e a tela mostra as três:** achou; o serviço
disse que **não existe**; e **não deu para consultar**. ⚠️ A última **não** é
CEP errado, e confundi-las faria o operador apagar um CEP certo. O ViaCEP
responde **200 com `{"erro": true}`** para CEP inexistente — quem olhasse só o
código HTTP preencheria a tela com campos vazios.

⚠️ O CEP preenche rua, bairro, cidade e UF, e **nunca o número** — ele não
sabe. ⚠️ Tudo continua editável (*"ela ainda edita se precisar"*). ⚠️ Sem rua,
o endereço **não** vai para a OS, e a tela diz isso: mandar CEP sozinho
sobrescreveria o endereço da OS por um que não leva ninguém a lugar nenhum.

A tela mostra, antes de gravar, **a linha que o cliente vai ler**.

**Validado com o que ele mandou:** CEP `19013180`, número `26`. O ViaCEP e a OS
16991 concordam campo a campo, e a escrita mudou `numero` de `S/N` para `26` sem
tocar em mais nada.

### F5 — "Enviar ao cliente" e "Abrir na conversa do técnico" (`ATD_1.2`, aba Confirmar)

🔵 *"os botões de cada texto podem ser: 'Enviar ao cliente' e do outro 'Abrir na
conversa do tecnico', então envia o primeiro e o modal persiste, como orçamento
faz, dai operador decide clicar no outro ou não, não sendo obrigatório"*.

As duas mensagens passam a ser **editáveis no próprio modal** (*"ao invés de
editar na caixa de mensagem, pode editar ali no modal mesmo"*), e o texto
editado é o que vai enviado.

🚨 **O MODAL PERSISTE DEPOIS DE ENVIAR**, como o orçamento: fechar sozinho
levaria embora o texto do técnico, que é o segundo passo — e **opcional**, por
decisão dele.

⚠️ **A DECISÃO 6 DELE CONTINUA VALENDO** (*"quem envia é o atendente"*): o
botão é um clique dele; o que desapareceu foi o desvio pelo compositor.

🚨 **O segundo botão ABRE, não envia**, e isto é limite da rota, não escolha de
desenho: `/responder` exige **estar na conversa**, e a do técnico é outra.
Prometer envio ali seria botão que não cumpre. O texto vai no compositor pelo
rascunho por conversa (Bloco 7), e **não sobrescreve texto não enviado sem
perguntar**.

## 21/10, quinta volta — o `@` na nota interna chama gente NOSSA

Pergunta dele: *"E o @ nas notas internas tbm funcionaria, certo?"* — e a
resposta medida foi **não**, em três lugares: a lista do `@` não abria fora de
grupo, a tela **apagava** as menções ao salvar nota (`const vivos = interna ?
[]`) e o `anotar()` não tinha onde recebê-las. Era recusa deliberada, da época
em que menção só existia como `mentioned` do WhatsApp — que de fato o WhatsApp
ignora em conversa direta.

Depois: *"foco nos nomes internos no caso dos chats, que ja temos por convite
de usuarios"* e *"tem um caminho mais pratico para os @ em chats?"*. Tem, e é
o que entrou.

### 🚨 Não há tabela nova — a máquina do chat interno é a mesma

O aviso de quem foi chamado **sai pelo chat interno**: a nota é gravada e, para
cada chamado, `chat.abrir_direta` acha ou cria a sala direta e `chat.escrever`
grava a mensagem com `mencionados`. Isso reaproveita, sem código novo,
`chat_mencao`, a recusa de quem não é da sala, o **contador separado** de
menção não lida e o selo no menu e na barra do celular.

| Antes seria | Ficou |
|---|---|
| migração `nota_mencao` | nenhuma migração |
| contador novo na `/api/eu/notificacoes` | o contador do chat, que já existe |
| selo novo na Caixa | o selo do chat |
| destaque do nome dentro da nota | o `@Nome` fica como texto na nota |

⚠️ **O preço, dito aqui porque é real:** a nota **não guarda** quem foi
chamado — o registro é a mensagem do chat. Apagada ela, o aviso se perde (a
nota, não). Se algum dia o registro na própria nota for necessário, a tabela
entra em cima disto sem desfazer nada.

### 🚨 A mesma tecla, dois universos

| Onde | O `@` chama | Como o aviso chega |
|---|---|---|
| **Grupo** do WhatsApp | participante do grupo, por **JID**, lista do Evolution ao vivo | o próprio WhatsApp notifica (`mentioned`) |
| **Conversa direta** | **atendente** nosso, por **id** — dono + convidados ativos | mensagem no **chat interno**, com o link da conversa |

Nunca os dois juntos: cliente não se chama em nota, e colega não se chama em
grupo do WhatsApp. Quem resolve é `ehGrupo`, e as duas rotas são irmãs e
separadas de propósito — `/quem-chamar` (grupo, JID) e
`/quem-chamar-interno` (atendente, id).

🚨 **Quem pode ser chamado é quem pode AGIR**, pela mesma régua de
`esta_na_conversa`: dono e convidado ativo, e só atendente **ativo**. Oferecer
na tela quem a rota recusaria seria o defeito; chamar quem não está é **recusa
que diz o nome**, nunca aceitar e ignorar.

### O destino vem do botão, e por isso a tela pergunta

O compositor não sabe, enquanto se digita, se aquilo vai ser nota ou mensagem:
**o destino vem do botão clicado** (decisão dele, de quando o `modoNota` caiu).
Então em conversa direta o `@` é sempre interno, e se o texto for enviado **ao
cliente** a tela avisa antes: o `@Fulano` segue como **texto comum** e ninguém
é chamado. Avisar é o que separa isto de prometer o que não acontece.

### O que a tela diz depois é o que o backend respondeu

A rota devolve `chamados` e `avisos_falhos`. Aviso que saiu: *"Avisei Thiago
pelo chat interno"*. Aviso que falhou: *"A nota ficou gravada, mas não consegui
avisar Thiago pelo chat interno"* — porque **falha no aviso não desfaz a
nota**, e perder o texto escrito para punir uma falha de aviso seria pior.

⚠️ **O recado vem DEPOIS do recarregar da conversa**: `abrir()` limpa o recado,
e um recado posto antes dele morria sem aparecer. Achado pelo teste, não pela
leitura.

### O aviso leva um clique, não um caminho para copiar

`partesDoTexto` (em `util/mencao.js`, a função que a tela e o teste
compartilham) passou a quebrar também o caminho `/atendimento/<id>`, que o
balão do chat rende como link. 🚨 **Só caminho nosso** — acender URL qualquer
seria outra decisão, com outro risco: texto de cliente passa por ali.

### Base da medição, e o que falta

Medido na conversa **80355**, a do número **+5511932726146** (*"a conversa de
base é a do numero +5511932726146"*): contato **Murilo Augusto | YUV**, dona
**Claudia**, 29 mensagens e **11 notas**, com **Erika, Iago, Rodrigo e Thiago**
como convidados ativos. Cinco pessoas nossas dentro de uma conversa direta.

No ar: **508 notas** (492 nos últimos 30 dias) em 249 conversas; **23 convites
ativos** em 17 conversas. Fora dessas 17, a lista do `@` traz só o dono.

### ✅ Decisão dele, 21/10: *"convite é convite, mencioanr é mencionar"*

Eu propus que **mencionar convidasse junto** quem está fora da conversa, e ele
**recusou**. 🚨 **NÃO REABRIR.** São duas ações distintas, e cada uma é uma
decisão de quem atende: a menção continua **recusando com o nome** de quem está
fora e dizendo *"convide primeiro, senão a pessoa recebe o aviso e não consegue
agir"*.

⚠️ A consequência é conhecida e aceita: nas 232 conversas com nota e sem
convidado, a lista do `@` traz só o dono. Quem quiser chamar alguém convida
antes — um clique que a tela já tem.

🔴 **Falta dele:** exercitar na 80355 (chamar alguém numa nota e ver o selo
chegar do outro lado). **Grupos ficam para depois** (*"proponha o ajuste para conversas primeiro e somente depois o de
grupos"*): a ficha de grupo com participantes e as quatro ações, os
participantes oferecidos com o número como rótulo quando não houver nome, o
"diga por que a lista está vazia" quando o Evolution recusa, e o registro da
menção enviada.

---

## 22/10 — a aba Atendimento: ordem, nome, porta e os três selos

🔵 **Pedido dele, numa frase:** *"Na Aba 'atendimento' do movizap, deixar na
orde 'Caixa de entrada' (mudar nome para Whatsapp); abaixo colocar o 'Chat
Interno' e em seguida 'E-mail's' - Itens Fila, Histórico não só aparecem para
Admin e Owner; tbm veja que a quantidade de notificações que aparece no 'Chat
interno' deve aparecer tbm na aba 'Whatsapp' (antiga 'Caixa de entrada' a esse
ponto), conforme notificações da aba 'Minhas' e o mesmo para 'e-mail's' (não
lidos) e na Aba "Atendimento', quando fechada informar a soma dos 3."*

Confirmação dele antes de executar: *"siga com os ajustes do painel, isso mesmo
somente visual para e-mail, pessoal deu feedback que é melhor nessa ordem"*.

### O que entrou

| ponta | onde | como |
|---|---|---|
| **"Caixa de entrada" virou "WhatsApp"** | `telas.py` (`ATD_1.1`) + 9 lugares que o operador lê | o menu é desenhado a partir de `/api/telas`, então o título sai do registro |
| **Ordem: WhatsApp › Chat interno › E-mail** | `telas.py`, movendo os dicts | a ordem do menu **é** a ordem do registro — nenhum mecanismo novo |
| **E-mail dentro do grupo Atendimento** | `EML_1.1` ganhou `grupo: "Atendimento"` | **só visual**, decisão dele |
| **Fila e Histórico só para Admin e Owner** | `ATD_1.3` e `ATD_5.1`: `atendimento` → `equipe` | permissão que já existia; `PERFIS` dá `equipe` a owner + admin, e a mais ninguém |
| **Selo de não lidas no WhatsApp** | `MenuLateral.vue`, lendo `notificacoes.abas.minhas` | o mesmo número da aba "Minhas" |
| **Selo de não lidos no E-mail** | `_email_nao_lidos` em `/api/eu/notificacoes` | mesmo filtro da aba "Entrada" |
| **Soma dos três no grupo fechado** | `somaDoGrupo` no cabeçalho | com as três parcelas nomeadas no `title` |

Resultado medido, por perfil:

| perfil | o que vê em Atendimento |
|---|---|
| `owner` | WhatsApp · Chat interno · E-mail · Fila · Histórico · Informativos · Ligações · Agendamentos |
| `admin` | WhatsApp · Chat interno · E-mail · Fila · Histórico · Ligações · Agendamentos |
| `atendimento` | WhatsApp · Chat interno · E-mail · Ligações · Agendamentos |

### 🚨 `"jamais misturemos whatsapp com gmail"` — e por que isto não viola

A decisão dele de 10/08 aposentou o código `ATD_4.1` e criou o módulo `EML`.
Ela continua inteira: o E-mail tem código, rota, caixa, marcadores, fila e
permissão próprios, e nada disso foi tocado. O que mudou é **um campo de
apresentação** (`grupo`), que o cabeçalho do `telas.py` chama de apresentação,
não permissão, desde 21/10. Ele confirmou isso em voz alta — *"isso mesmo
somente visual para e-mail"* — antes da execução.

O grupo `"E-mail"` continua declarado em `GRUPOS` e ficou **vazio**. O
`MenuLateral` não desenha grupo sem tela visível, então ele sai da tela
sozinho, como "Painéis › Operacional" desde 19/10. Três testes novos guardam
isso: o grupo declarado, o fallback do prefixo ainda apontando para "E-mail"
(para o caso de backend um passo atrás da tela), e o grupo ficar vazio.

### 🚨 O selo não abre um terceiro ritmo de polling

O `MenuLateral` já tinha chamada própria a cada 15 s (`/api/chat/nao-lidas` e
`/api/chat/mencoes`). Os dois selos novos **não** criaram uma terceira: o
`Notificador.vue` está montado no `App.vue`, roda em **toda tela** a cada 8 s,
e o contador de e-mail entrou **na resposta que ele já busca**. Rota nova
significaria um relógio a mais no navegador para o mesmo selo.

⚠️ **O do Chat interno continua com chamada própria**, de propósito:
`/api/chat/mencoes` exige a `ATD_6.1` e traz a conta de **menção** separada —
a que muda a **cor** do selo. Unificar os três numa resposta é limpeza de
outro dia, e exigiria mexer em permissão. A soma nunca discorda das parcelas
(as três saem das mesmas três variáveis); só a parcela do chat pode estar
alguns segundos mais velha.

### 🚨 O filtro do selo de e-mail é o da aba "Entrada", e isso não é detalhe

`_email_nao_lidos` conta `NOT lida AND NOT arquivada AND na_lixeira_desde IS
NULL`, nas caixas que **esta pessoa** conectou e que estão `ativa` — o mesmo
`WHERE` que `/api/email/mensagens?caixa=entrada` usa desde 17/09.

Selo que contasse arquivada ou lixeira mandaria a pessoa abrir a tela para
procurar uma mensagem que **a tela não mostra**. É a `M12` chegando pelo
número em vez do texto. É a mesma regra que o `abas.minhas` segue desde 24/09
("a bolinha não pode discordar da aba"), e foi por ela que este filtro foi
escolhido em vez de um `count` simples.

⚠️ **Quem não conectou caixa recebe `0`, não erro.** A rota serve todo mundo,
inclusive quem não tem a `EML_1.1`, e um erro ali apagaria também o selo do
WhatsApp e o do Chat interno, que vêm na mesma resposta. Medido: 61 não lidos
na única caixa conectada do sistema (atendente 121), `0` para quem não tem
caixa.

🔴 **Hoje só existe UMA caixa de e-mail conectada em todo o MoviZap.** O selo
de e-mail, na prática, só aparece para o owner até alguém mais conectar a sua.

### 🚨 Dois defeitos meus, no mesmo dia, achados antes de ele ver

**1. A varredura do rótulo era sensível a caixa.** O `grep` da Fase 0 procurou
`"Caixa de entrada"` com C maiúsculo e achou 9 lugares. Três textos que o
operador **lê** escrevem `"caixa de entrada"` em minúsculo, no meio da frase,
e passaram batido:

- `Fila.vue`, o `<AjudaDaTela>`: *"A caixa de entrada mostra o que é seu"*
- `CaixaDeEntrada.vue`, o modal de reabrir: *"volta para a caixa de entrada"*
- `Fila.vue`, o cabeçalho do arquivo

O `M13` diz que a varredura lê a tela e não o seletor. **Falta o irmão disso:
ler a tela também não é chutar a forma da palavra.** Varredura de rótulo se faz
sem sensibilidade a caixa, sempre. Quem achou foi um segundo `grep -i` que eu
rodei por outro motivo.

**2. Eu lia um campo que ninguém gravava, e as duas suítes ficaram verdes.** O
`MenuLateral` passou a ler `notificacoes.email_nao_lidos`; a rota passou a
devolver o número; e o `ler()` do `Notificador` **copia campo a campo** — a
linha do meio não existia. Em produção o selo do e-mail ficaria **sempre em
branco** e a soma do grupo fechado sairia sem essa parcela.

🚨 **Nenhuma das duas suítes podia pegar:** os testes do menu setam
`notificacoes.email_nao_lidos` à mão, porque o que eles defendem é o **desenho**
do selo; e nenhum teste ligava a resposta da rota ao estado. É a família do
`M9` — placar verde não vê —, mas **por dentro do estado em vez do layout**. O
que pegou foi ler a cadeia inteira antes do build: **quem devolve → quem grava
→ quem lê**.

É literalmente a lição que o `do_usuario` do `telas.py` carrega escrita no
corpo desde 27/08: *"esta função monta a resposta À MÃO, e é por isso que o
campo novo precisa estar listado aqui"*. Eu li esse comentário nesta mesma
sessão, para outra coisa, e repeti o defeito que ele descreve.

Os 4 testes que entraram em `notificacoes_2509.teste.js` defendem o elo —
**e 3 deles foram provados vermelhos** com a linha removida de propósito, antes
de eu deixá-los no verde. (O quarto, "zero é valor", passa dos dois jeitos: é
documentação, não defesa, e está marcado como tal.)

### O que foi deixado em pé de propósito

- `Email.vue`: `INBOX: 'Caixa de entrada'` é a pasta do **Gmail**, outro
  significado, dentro da tela de e-mail. Trocar ali seria **introduzir** o erro.
  Conferido no bundle publicado: é a única ocorrência que sobrou.
- Os comentários que **narram** história (`avatar.js`, `ChatInterno.vue`,
  `App.vue`, `Clientes.vue`, `sessao.js`, `Inicio.vue`): diário não se
  reescreve.
- **Informativos, Ligações e Agendamentos** ficaram depois dos três, na ordem
  em que já estavam. Ele não os citou; não inventei posição para eles.

### Testes

**1624 Python** (eram 1613) e **396 JS** (eram 392). Os novos:

| arquivo | quantos | o que defende |
|---|---|---|
| `tests/teste_selo_email.py` | 9 | o filtro do contador, a caixa de outra pessoa, caixa inativa, e quem não tem caixa receber 0 |
| `frontend/src/selos_menu_2210.teste.js` | 13 | os três selos, o zero não desenhar, 99+, a soma no grupo fechado, e a cor da menção ficar só no chat |
| `notificacoes_2509.teste.js` | +4 | o elo que faltava (3 provados vermelhos sem a correção) |
| `tests/teste_menu_grupos.py` | +2 | o fallback do `EML` e o grupo "E-mail" declarado e vazio |

Alterados por mudança pedida, não por conserto: `teste_telas.py` (o título, e
o conjunto fechado do admin, que agora nomeia `ATD_1.3`/`ATD_5.1` porque elas
saíram de `permissao == "atendimento"`), `menu_grupos_2110.teste.js` e
`telas_novas.teste.js` (fixtures que imitam o backend).

### Ordem de publicação (`M16`)

Backend primeiro: `telas.py` + `main.py` → restart → conferido ao vivo.
Depois `preferencia.py` (o rótulo dos 5 atalhos, que é backend e eu quase
deixei na fase do frontend) → segundo restart. Só então `npm run build`. Em
nenhum momento a tela pediu o que o servidor ainda não sabia responder.

### 🔴 Falta dele — `M9`, e nada aqui substitui

1. **Abrir o menu** e ver a ordem, o nome "WhatsApp" e os três selos. Nenhum
   teste vê o selo caber nos 18px do item, nem a cor, nem se ele cobre o
   rótulo.
2. **Fechar o grupo "Atendimento"** e conferir a soma — e que o `title` nomeia
   as três parcelas.
3. **Entrar como `atendimento`** e confirmar que Fila e Histórico não aparecem.
4. **Abrir a CFG_6.1 (Atalhos)** e ver se os 5 atalhos agora dizem "WhatsApp".

---

## 22/10, segunda volta — o e-mail: a mensagem que sumiu do Gmail

🔵 **Pedido dele:** *"agora parece que o e-mail não esta validando as não lidas
corretamente conforme integração gmail, talvez esteja considerando lixeira
ainda, o que não pode, evidentemnte"*.

**O palpite acertou o alvo e errou a flag.** A lixeira estava sendo excluída
corretamente; quem entrava era a irmã dela.

### A causa

A varredura (`gmail.sincronizar_exclusoes`, cron de 15 min — dados frescos, não
era defasagem) grava **três** estados, e o filtro das abas conhecia **dois**:

| estado no Gmail | flag | o filtro conhecia? |
|---|---|---|
| ativa | as duas em `NULL` | sim |
| na lixeira / spam | `na_lixeira_desde` | sim |
| **não existe mais** | `sumida_do_gmail_em` | **não** |

Medido na caixa real (conta 2, 826 mensagens):

| | antes | depois |
|---|---|---|
| **selo do menu** | **61** | **5** |
| aba Entrada | 394 msgs, **73 sumidas** | 321 msgs, **0 sumidas** |
| aba Lixeira | 432 | 505 (`+73`) |

As contas fecham: 394 − 73 = 321 e 432 + 73 = 505.

⚠️ **O sincronismo de leitura nunca foi o problema:** `lida` e o rótulo
`UNREAD` do Gmail concordam **perfeitamente** — zero divergências em 826
mensagens, nos dois sentidos. E as 358 não lidas que estão na lixeira sempre
foram excluídas certo.

### 🚨 O defeito era da TELA, e o selo só pôs um número em cima dele

A aba "Entrada" mostrava as 73 desde sempre; a rolagem da lista escondia. Ao
criar o selo (22/10, primeira volta) eu copiei o `WHERE` da aba **de propósito**
— "a bolinha não pode discordar da aba" — e **herdei o defeito junto**.

É da família do `M15`: eu li o `WHERE` e copiei, em vez de ler **o que cada
flag significa**. A coluna `sumida_do_gmail_em` estava no `SELECT` logo ao
lado, com um comentário dizendo que é *"sumiu de vez, isto é só a nossa
cópia"*. Passei por ele e não perguntei por que não estava no `WHERE`.

### 🚨 O segundo buraco, pelo outro lado

A aba Lixeira filtrava só por `na_lixeira_desde`. A mensagem que foi de ativa a
inexistente **entre duas varreduras** (apagada de vez no Gmail, ou purgada
pelos 30 dias) nunca passou pela lixeira — e ficava **presa na Entrada para
sempre**. Eram as 73. Das 266 sumidas, as outras 193 tinham as duas flags e
caíam na Lixeira certo.

🔵 **Decisão dele (opção 1):** a sumida vai para a **Lixeira**, marcada como
*"só a nossa cópia"*. Esconder de todas as abas perderia de vista a única cópia
que existe — o Gmail já não tem a dele, e o conteúdo (texto, HTML, anexos) foi
baixado na importação.

### A correção

| parte | o que mudou |
|---|---|
| **A** | Entrada e Arquivadas passam a exigir `sumida_do_gmail_em IS NULL` |
| **A** | Lixeira passa a `(na_lixeira_desde IS NOT NULL OR sumida_do_gmail_em IS NOT NULL)` — **sem isso as 73 desapareceriam de todas as abas**, que é pior que estarem na errada |
| **B** | `_email_nao_lidos` usa o mesmo filtro |
| **C** | `FILTRO_ENTRADA` / `FILTRO_ARQUIVADAS` / `FILTRO_LIXEIRA` + `filtro_da_caixa()`, num lugar só |

### 🚨 A parte C importa mais que A e B

O filtro existia **copiado à mão em dois lugares**, e foi isso que deixou o
selo errar junto. Agora é **um** fragmento nomeado, lido pela lista e pelo
contador, e dois testes defendem a **causa**:

- `test_o_selo_e_igual_ao_que_a_aba_entrada_mostra` — não afirma nenhum
  filtro; afirma que os **dois caminhos dão o mesmo número**
- `test_a_lista_e_o_contador_leem_a_MESMA_constante` — lê o próprio `main.py` e
  reprova quem voltar a escrever as condições à mão

⚠️ **Limite honesto desses dois:** eles pegam **divergência**, não um filtro
errado-mas-compartilhado. Com o filtro antigo nos dois lugares, o primeiro
passa. Quem pega filtro errado são os casos nomeados por estado
(`test_a_sumida_nao_aparece_na_entrada` e irmãos) — e desses, **6 de 14 foram
provados vermelhos** com o filtro antigo restaurado de propósito.

### 🚨 A tela: quatro botões que mentiam, e fui eu que os tornei alcançáveis

Para uma mensagem que não existe mais no Gmail, **toda** escrita devolve
**404** (`messages/{id}/modify` → `GmailIndisponivel` → 503 na tela): "marcar
não lida", "Arquivar", "Excluir" e "Restaurar".

E o pior: o botão **"Restaurar"** ficava **colado no aviso** que diz
*"Não dá para restaurar lá"*. `M12` na forma mais crua que existe.

Isso era **latente** antes de hoje — a sumida ficava presa na Entrada, onde o
botão era "Excluir". **Mover as sumidas para a Lixeira é o que pôs o
"Restaurar" na frente delas.** Eu criei o alcance, então consertar faz parte da
mudança, não é escopo novo.

O que a tela ganhou:

- **chip "só a nossa cópia"** na lista — antes o aviso só existia com a
  mensagem **aberta**, e na Lixeira convivem agora duas coisas diferentes (a
  que dá para restaurar e a que não existe mais). Sem a marca, distinguir
  custava um clique por mensagem
- um `computed` só, `semEscritaNoGmail`, governando as quatro ações — quatro
  condições separadas divergiriam na primeira correção
- **"Responder" FICA**: compõe mensagem nova, não toca na original. É a única
  ação que ainda faz sentido sobre uma cópia órfã
- o aviso passou a dizer o que saiu e por quê (*"não dá para restaurar,
  arquivar nem excluir lá; só responder"*) — com os botões fora, ele é a
  **única** explicação, e botão que desaparece sem palavra é o rótulo que
  mente, pelo avesso

### Testes

**1638 Python** (eram 1624) e **406 JS** (eram 396).

| arquivo | quantos | provados vermelhos sem a correção |
|---|---|---|
| `tests/teste_filtro_sumida.py` | 14 | **6** |
| `frontend/src/email_sumida_2210.teste.js` | 10 | **5** |

⚠️ **Um defeito na primeira versão do meu próprio teste JS:** a fixture da
sumida vinha com `na_lixeira_desde` preenchido, e nesse caso "Arquivar" e
"Excluir" **já estavam escondidos pela condição antiga** — os testes passavam
sem defender nada. As 73 reais têm `na_lixeira_desde` **nulo**. Corrigida a
fixture para o caso real, os vermelhos subiram de 4 para 5.

### Ordem de publicação (`M16`)

Backend (`main.py`) → restart → conferido ao vivo (selo 5, abas 321/0/505) →
testes → só então `npm run build`.

⚠️ **Houve uma janela**, entre o restart e o build, em que o backend já movia
as sumidas para a Lixeira e o frontend publicado era o antigo: nela, o botão
"Restaurar" estava à vista para as 73. Foi curta e o build a fechou, mas é o
mesmo padrão do `M16` — meio deploy não é "metade pronta". Da próxima vez numa
mudança que **move dados entre telas**, o frontend tem de ir no mesmo passo.

### 🔴 Falta dele (`M9`)

1. **Comparar o selo com o Gmail.** Deve dizer **5**. Se o seu Gmail mostrar
   outro número, a causa é outra e eu volto a medir antes de mexer — esta é a
   confirmação que só ele pode dar.
2. **Abrir a Lixeira**: as 73 novas com o chip *"só a nossa cópia"*, as outras
   sem.
3. **Abrir uma delas**: sem Restaurar, Arquivar e não-lida; com Responder e o
   aviso.
4. **Abrir uma que está só na lixeira**: "Restaurar" tem de estar lá, e
   funcionar.
5. **Conferir a Entrada**: 321 mensagens, nenhuma com o chip.

---

## 22/10, terceira volta — as quatro caixas pelo modelo do Gmail

🔵 **Dois pedidos dele, no mesmo passo:** *"siga com a 2"* (a Entrada e o selo
passam a exigir o rótulo `INBOX`) e *"enviadas devem ter seu proprio grupo,
igual no Gmail"*.

🔵 **E o porquê, que ele deu:** *"precsamos ter ela funcionando, depois dos
formularios, vamos ter caixas fixas logadas compartilhadas, então para
chegarmos la, precisamos que funciona a pessoal"*. A caixa pessoal é o ensaio
da caixa compartilhada — defeito que hoje é chato com uma conta, com várias
viraria outro problema.

### ⚠️ Antes de tudo: um número que eu dei errado

Na volta anterior eu afirmei que *"a aba Entrada está mostrando 219 mensagens
enviadas"*. **Estava errado.** Eu medi chamando a rota **sem** o parâmetro
`marcador`, e a tela manda `marcador=INBOX` — dá para ver no log:
`GET /api/email/mensagens?marcador=INBOX&busca=&caixa=lixeira&conta_id=2`.

| | |
|---|---|
| Entrada **como a tela pede** | 101 msgs, **0** não lidas |
| Entrada como eu medi (sem marcador) | 321 msgs, 1 não lida |

A aba Entrada **nunca** mostrou as enviadas. O defeito real era mais estreito:
**a tela filtrava por `INBOX` e o selo não** — e por isso o selo dizia 1 onde a
tela e o Gmail diziam 0. É o mesmo erro de método do `M15` outra vez: medi uma
coisa parecida com a que importava.

### 🚨 Mas a medição errada achou um defeito verdadeiro: a duplicação

"Entrada" existia em **dois controles** — as abas de caixa
(Entrada/Arquivadas/Lixeira) e a lista de **marcadores** (Caixa de
entrada/Enviados/Com estrela/...) — e a tela mandava **os dois juntos** ao
servidor.

Consequência medida: **11 mensagens enviadas que estão na lixeira ficavam
invisíveis**, porque a aba Lixeira era filtrada pelo rótulo da Entrada. E a
barra "onde estou" escrevia *"Caixa de entrada"* **com a Lixeira aberta** —
`M12` que ninguém viu, porque os dois controles concordavam por acidente
enquanto o marcador começava em `INBOX`.

🔵 O modelo que ele pediu, e que resolve os dois: **caixa é LUGAR, marcador é
ETIQUETA.** `INBOX` e `SENT` saem da lista de marcadores porque viraram lugar;
sobram "Com estrela", "Importantes" e as etiquetas dele.

### As quatro caixas, e a ordem que garante "exatamente uma"

| precedência | condição | caixa |
|---|---|---|
| 1 | `na_lixeira_desde` ou `sumida_do_gmail_em` | **Lixeira** |
| 2 | nossa coluna `arquivada` | **Arquivadas** |
| 3 | tem `INBOX` | **Entrada** |
| 4 | tem `SENT` e **não** tem `INBOX` | **Enviados** |
| 5 | não tem nenhum dos dois | **Arquivadas** (= arquivada no Gmail) |

Medido na caixa real para decidir cada linha:

- **1** mensagem tem `INBOX` **e** `SENT` → a Entrada ganha (linha 4 exige
  `NOT INBOX`). Isso mantém "exatamente uma caixa" verdadeiro; o Gmail
  mostraria nas duas, e essa é a diferença aceita de propósito.
- **1** mensagem não tem nenhum dos dois → é o *"Alerta de segurança"* do
  Google, não lido desde 22/04, **arquivado no Gmail**. Sem a linha 5 ela
  cairia em caixa **nenhuma** — o mesmo defeito das 73 sumidas, que custou a
  volta anterior do mesmo dia. **Foi por ter acabado de errar nisso que eu
  procurei por ela.**
- **0** mensagens têm a coluna `arquivada` — a aba Arquivadas estava vazia, e
  ganhou a primeira ocupante de verdade.

⚠️ **A linha 2 parece redundante e não é:** arquivar pelo painel chama o Gmail
para tirar o `INBOX` **lá**, mas não apaga o marcador **local** (só o `UNREAD`
é apagado, em `marcar_lida`). Sem a nossa coluna com precedência, a mensagem
arquivada pelo painel voltaria para a Entrada.

### O resultado

| caixa | antes | agora |
|---|---|---|
| **Entrada** | 101 (via marcador) | **101** |
| **Enviados** | só via marcador | **219** |
| **Arquivadas** | 0 | **1** |
| **Lixeira** | 505, sem as enviadas | **505**, com as **11** |
| **selo** | **1** | **0** — bate com o Gmail |

**826 mensagens, cada uma em exatamente uma caixa, soma igual ao total.** Não é
inspeção: é consulta que confere as quatro por mensagem.

### 🚨 O limite que fica escrito no código

Os rótulos do Gmail são gravados **uma vez, na importação, e nunca mais
atualizados** — medido: existe **um** `INSERT` (no caminho de importação de
`gmail.ler`) e **um** `DELETE` (do `UNREAD`, em `marcar_lida`). A varredura de
15 min compara **ids**, não rótulos.

Então `INBOX` é a **foto do dia da importação**: arquivar no Gmail *depois*
disso não chega até nós. Hoje isso não aparece, porque a mensagem que motivou
a correção já estava arquivada **antes** de entrar. Ressincronizar rótulos é
frente própria, mais cara (o `docs/02` registra a régua: *"listar é barato,
baixar é caro"*), e está anotada — não prometida.

### Testes

**1651 Python** (eram 1638) e **410 JS** (eram 406).

| arquivo | o que entrou |
|---|---|
| `tests/teste_filtro_sumida.py` | `TestEnviadosEhLugar` (6) + 4 casos de rótulo na parametrização de "exatamente uma caixa" |
| `tests/teste_selo_email.py` | `TestOSeloEhSoDaENTRADA` (3): sem `INBOX` não conta, enviada não conta, com `INBOX` conta |
| `frontend/src/email_sumida_2210.teste.js` | as 4 abas na ordem, as etiquetas **sem** Entrada/Enviados, e o pedido mandando `caixa=lixeira&marcador=` |

🚨 **As fixtures dos testes precisaram ganhar RÓTULO, e isso é parte do
conserto.** Antes, "mensagem na Entrada" era `NOT arquivada AND viva`, e uma
linha sem rótulo nenhum servia de fixture. Com a Entrada exigindo `INBOX`, essa
linha passa a cair em Arquivadas — **e está certo**. A fixture é que era
irreal: mensagem de caixa de entrada sempre tem `INBOX` no Gmail. Afrouxar o
filtro para a fixture passar seria escrever o defeito no código para agradar o
teste.

⚠️ **E um teste JS que precisou de aparato novo:** metade do defeito não estava
no que a tela **desenhava**, e sim no que ela **mandava** (`caixa=lixeira` junto
com `marcador=INBOX`). O duplo de `api.get` passou a **registrar as rotas
pedidas** — sem isso nenhum teste de DOM veria: a lista só vinha vazia, e vazio
parece "não tem mensagem".

### 🔴 Falta dele (`M9`)

1. **O selo deve estar em branco** (0). Confirmar contra o Gmail.
2. **As quatro abas**: Entrada 101 · Enviados 219 · Arquivadas 1 · Lixeira 505.
3. **A lista de etiquetas** não deve mais oferecer "Caixa de entrada" nem
   "Enviados" — só "Com estrela", "Importantes" e as dele.
4. **Abrir a Lixeira e procurar uma enviada**: eram 11 invisíveis.
5. **A barra de cima** deve dizer o lugar onde ele está, não "Caixa de
   entrada" em toda aba.

### O que a suíte achou nesta volta — e só uma coisa era fixture

**1. 🚨 Defeito de produção que esta mudança IA INTRODUZIR.** `restaurar()`
punha o `INBOX` **no Gmail** e limpava `na_lixeira_desde` **aqui**, mas nunca
gravava o marcador local. Com a Entrada passando a exigir `INBOX`, restaurar da
lixeira mandaria a mensagem para **Arquivadas**.

A ironia está escrita no corpo da própria `restaurar`, desde 17/09, sobre o
outro lado: *"o `untrash` SOZINHO NÃO DEVOLVE O `INBOX` (...) sem ele a pessoa
clicaria 'restaurar' e o e-mail sumiria de vez visualmente, mesmo sem ter sido
apagado."* Mesmo defeito, mesma frase, outro lado da casa.

Consertado no **ponto único** (`_mexer_rotulo`, por onde estrela, não-lida,
arquivar, excluir e restaurar passam — o cabeçalho dela já proíbe cópias, pela
lição do `_condicao_busca`). Isso corrigiu de passagem três buracos que ninguém
pediu: `arquivar(True)` deixava o `INBOX` local, `marcar_nao_lida` gravava
`lida = false` sem o marcador `UNREAD`, e `excluir` não gravava `TRASH`.

**2. 🚨 O DUPLO DOS TESTES FICOU IRREAL, por minha causa.** Os dois arquivos de
teste trocavam `gmail._mexer_rotulo` inteiro por um falso, e a docstring deles
diz a intenção: *"Nenhum teste fala com o Gmail."* Enquanto aquela função era
**só rede**, trocá-la inteira cumpria isso. Quando o espelho local entrou nela,
o duplo passou a desligar **regra** junto com a rede — e o teste de restaurar
**reprovou com o código certo**.

A chamada HTTP saiu para `_modificar_no_gmail`, e o duplo desceu para lá. Agora
os testes não tocam a rede **e** exercitam o espelho de verdade: ganharam
cobertura em vez de perder.

> **A regra que fica: duplo se põe na BORDA, nunca no meio da regra.** Duplo
> que cobre regra para de provar a regra — e o sintoma é o pior que existe,
> porque fica verde em produção quebrada ou vermelho em produção boa, sem
> distinguir os dois.

**3. Fixtures irreais em quatro arquivos** (`teste_selo_email`,
`teste_filtro_sumida`, `teste_email_acoes`, `teste_caixa_por_atendente`):
mensagens nascendo **sem rótulo nenhum**. Corrigidas as **fixtures**, não o
filtro — mensagem de caixa de entrada sempre tem `INBOX` no Gmail, e afrouxar o
filtro para a fixture passar seria escrever o defeito no código para agradar o
teste, sendo que o defeito era exatamente contar uma mensagem arquivada.

**4. 🚨 Uma âncora de teste que era PREFIXO de outro nome.**
`teste_gmail_pagina.py` recorta o fonte do `gmail.py` com
`corpo.index("INSERT INTO email_mensagem")` — e isso casa com
`"INSERT INTO email_mensagem_marcador"`. A função nova entrou **antes** no
arquivo, o `index()` passou a recortar a janela errada, e o teste reprovou com a
regra que ele defende (`enviado_em` vem do cabeçalho `Date`) **intacta**.

⚠️ **E nesse eu errei duas vezes:** troquei a âncora suposta por **outra âncora
suposta** (`"INSERT INTO email_mensagem (conta_id"`), chutando a formatação — o
`INSERT` real quebra a linha antes das colunas. Só acertou quando fui **ler** o
arquivo: a âncora exata é o nome da tabela seguido de **quebra de linha**. É o
`M15` dentro da correção do próprio `M15`.

### Ordem de publicação (`M16`)

`main.py` → restart → conferido ao vivo → `gmail.py` (o espelho) → **segundo
restart** → suítes fechadas → `npm run build`. O backend nunca ficou atrás da
tela.

### Placar

**1651 Python** (eram 1638) e **410 JS** (eram 406).

## 22/10 — Formulários próprios: a FRM_1.1 e o link público

🔵 Decisão dele: *"nenhuma possibilidade irá usar o bitrix, esse projeto é
movizap"*. Os 15 formulários de `solicite.movisat.com.br` eram **Bitrix24 CRM
Webforms** e concentravam toda a entrada de demanda da Movisat. Eles passam a
viver aqui; o Bitrix fica no ar só até ele desligar.

**O que entrou nesta primeira volta (Etapa 1):**

- **`forms.movisat.com.br/f/<slug>`** — o formulário aberto, sem login. Nesta
  volta no ar **só o CES** (5 campos); os outros 14 entram como DADO, depois
  que ele validar este no navegador.
- **`FRM_1.1` Solicitações** — a tela que recebe. Lista à esquerda, ficha à
  direita, três estados (`nova`, `em_andamento`, `concluida`), anexo para
  baixar. Grupo **Atendimento**, permissão **`equipe`** (owner e admin, a
  mesma régua da Fila e do Histórico).
- **o selo no menu** — o quarto, ao lado de WhatsApp, Chat interno e E-mail, e
  somado no grupo fechado. Conta as solicitações `nova` **pela mesma coluna
  que a tela filtra**.
- **o interruptor por pessoa**, na `CFG_11.1` — pedido dele: *"controle de
  notificações no 'minha conta' de cada usuário, igual as demais"*. Nasce
  LIGADO, e só aparece para quem tem a FRM_1.1.
- **o interruptor do sistema**, na `CFG_7.1` › Geral — pedir a conta de somar
  em TODO envio. Nasce desligado, e fica **no fim da tela** (dois testes da
  Geral escolhem a caixa pelo índice).

🚨 **A definição do formulário é DADO, não arquivo.** `formulario`,
`formulario_campo` e `formulario_regra` (migração 074) guardam campos,
rótulos, opções com os IDs do Bitrix e as regras condicionais; **uma** tela os
desenha (`CamposDoFormulario.vue`). Formulário novo é linha em tabela.

🚨 **A validação é NOSSA, no servidor.** Medido em 22/10: o Bitrix aceitou
`values=[]` vazio e criou o registro `15620` — toda a validação dos 239 campos
era no navegador, e navegador é do cliente.

🚨 **Campo escondido por regra SOME do registro**, não vira vazio: *"a pessoa
não respondeu"* e *"a pergunta não foi feita"* são coisas diferentes.

🚨 **Alvo de regra `show` nasce escondido, e isso foi medido:** nos 15
formulários **nenhum** campo vem com `visible: false` no loader do Bitrix, e
há **60 ações `show`**. Quem traduz é a carga. Confiar no `visible` faria todo
campo condicional aparecer sempre.

🚨 **O bundle público é separado** (`frontend/dist_publico`, servido em
`/pub/assets` e `/f/{slug}`). Pergunta dele: *"qual a mais segura para os
links que terão acesso externos"*. O bundle do painel publica `sourcemap:
true` — uma rota pública dentro dele entregaria o código-fonte do painel a
qualquer anônimo.

**As defesas do envio, nesta ordem:** isca invisível → tempo mínimo de 3 s
entre abrir e enviar (token assinado, sem sessão) → contagem de envios por IP
→ e **só então** a conta de somar, servida por nós. Decisão dele: *"captcha no
final pode se legal, mas tbm usam pelo cel então não pode virar entrave de
processo"*.

**Os anexos ficam isolados** em `/home/claude/movizap_formularios_anexos`,
fora do projeto e fora do `dist` (*"isolar os anexos sem perder controle na
VPS"*), com lista branca de extensão, 10 MB por arquivo e 25 MB por envio.
⚠️ **O host público nunca serve anexo** — baixar é rota autenticada do painel.

🔴 **O que ainda espera ele:** apagar os 14 registros de teste no Bitrix24
(`resultId` 15620–15646) · dizer para onde cada formulário cai no CRM hoje ·
confirmar o mapa formulário → `problemaId` · o texto dos nossos termos de uso
(o do Bitrix é *boilerplate* em inglês) · revisar os `nosso_nome` dos 239
campos.

### 22/10, ainda na Etapa 1 — os 15 carregados, e a conferência que roda antes de ligar

Os **15 formulários estão carregados** (239 campos), cada um como linha em
tabela. **Só o CES está ligado**; os outros 14 nascem desligados, e ligar é do
owner, na própria tela de Solicitações.

| formulário | campos | de pé no início | regras | arquivo | produto |
|---|---|---|---|---|---|
| CES | 5 | 5 | 0 | 0 | 0 |
| NPS | 9 | 4 | 2 | 0 | 0 |
| Suporte | 13 | 10 | 1 | 1 | 0 |
| Demonstração | 15 | 15 | 0 | 0 | 0 |
| Teste gratuito | 14 | 14 | 0 | 3 | 0 |
| Contato | 8 | 8 | 0 | 0 | 0 |
| Ficha cadastral | 36 | 26 | 2 | 3 | 0 |
| Aditivo | 18 | 14 | 1 | 1 | 1 |
| Substituição de veículos | 17 | 13 | 1 | 1 | 1 |
| Rescisão | 17 | 9 | 2 | 0 | 0 |
| Administrativas | 11 | 7 | 1 | 0 | 0 |
| Financeiras | 10 | 7 | 1 | 0 | 0 |
| Credenciamento técnico | 34 | 31 | 3 | 0 | 0 |
| Pagamento de técnicos | 16 | 16 | 0 | 1 | 0 |
| Fornecedores | 16 | 16 | 0 | 1 | 0 |

🚨 **"De pé no início" é a coluna que o Bitrix não mostrava.** Na ficha
cadastral, **10 dos 36** campos só existem depois de uma escolha; na rescisão,
**8 dos 17**. É esse número que a regra condicional governa, e é por isso que
campo escondido **some do registro** em vez de virar vazio.

**`scripts/conferir_formularios.py` — a conferência antes de ligar.** Ligar um
formulário é abrir uma porta para a internet, e defeito de definição só
apareceria com um cliente real preso numa tela que não envia. O script
**preenche cada formulário em voltas**, como gente (escolher uma opção faz
nascer campo novo), **uma vez por opção do primeiro campo de lista** — que nos
15 é sempre o gatilho (pessoa física/jurídica, tipo de solicitação) — e diz
`ENVIAVEL` ou `TRAVA`. Também confere que a contagem bate com o
`mapa_bruto.json`, que o `nosso_nome` é único e legível, e se existe campo
obrigatório que nenhuma regra alcança (seria formulário impossível de enviar).

**Resultado em 22/10: os 15 ENVIÁVEIS**, 0 problemas. ⚠️ Isto não substitui o
teste no navegador (`M9`): o script prova que a VALIDAÇÃO aceita, não que a
tela esteja legível no celular.

`venv/bin/python scripts/conferir_formularios.py --nomes <CODIGO>` imprime o
de-para **nome de origem → `nosso_nome`**, campo por campo: é a lista para ele
revisar os 239. 🚨 **Sai do banco, não de um documento à parte** — documento
com 239 linhas copiadas envelhece na primeira troca de nome.

### 22/10 — 🔵 ELE LIGOU OS 15: OS 15 NO AR

Pedido dele, textual: *"ligue todos os formulários no ar"*. Os 15 passaram a
`ativo = true` e foram conferidos **um por um pela internet** (`/f/<slug>` 200 e
a definição batendo o número de campos). São **15 links públicos vivos**:

`ces` · `nps` · `suporte` · `demonstracao` · `teste-gratuito` · `contato` ·
`ficha-cadastral` · `aditivo` · `substituicao-veiculos` · `rescisao` ·
`administrativo` · `financeiro` · `credenciamento-tecnico` ·
`pagamento-tecnicos` · `fornecedores`

⚠️ **O que muda de fato com isso, e ele sabe:**

1. 🔴 **Os três formulários com aceite de termo estão no ar SEM a caixa de
   aceite** — teste gratuito, ficha cadastral e fornecedores. O motivo está
   escrito acima: o termo que o Bitrix serve é *boilerplate em inglês* (*"Our
   rules are straightforward…"*), e copiá-lo seria pior que não ter. **No
   Bitrix esses três pedem o aceite; aqui, hoje, não.** Falta o texto dele.
2. ⚠️ **Os dois que tinham reCAPTCHA no Bitrix** (ficha cadastral e
   financeiras) agora se defendem pelas nossas quatro camadas: isca, 3 s
   mínimos, limite por IP e a conta de somar depois de 5 envios do mesmo IP na
   hora. Se aparecer abuso, o interruptor da `CFG_7.1` passa a pedir a conta
   em **todo** envio — é um clique, e não exige entrega.
3. ⚠️ **`product` (Aditivo e Substituição) é campo de TEXTO** nesta etapa: o
   catálogo do Bitrix não tem equivalente nosso. Quem preencher digita o
   produto.
4. ⚠️ **O Bitrix continua no ar em paralelo.** Enquanto os dois existirem, a
   mesma demanda pode entrar pelos dois caminhos; desligar o Bitrix é dele.

✅ Antes de ligar, `scripts/conferir_formularios.py` deu **os 15 ENVIÁVEIS, 0
problemas**. ⚠️ Isso prova que a validação aceita — **não** que os 36 campos da
ficha cadastral estejam confortáveis no celular. Essa leitura é `M9`.

## 22/10 — 🔵 PNL_1.1: o painel da Operação (opção A), e o plano dos outros três

🔵 **Escolha dele**, depois de ver três mockups lado a lado: *"vamos de A
somente para a Operação por enquanto, mas bem documentado para as demais
futuramente"*. Os mockups ficam em
`https://claude.ai/artifact/3mM5bs3gv1hYsyTaShsd6s`.

**No ar:** `PNL_1.1 Operação`, rota `/paineis/operacao`, grupo **Painéis**,
permissão **owner**. É o primeiro habitante do grupo que nasceu declarado e
vazio em 19/10 — e o subgrupo "Operacional" **saiu** (fecha a pendência 6 do
plano: ele nunca teve tela, e o painel chama-se "Operação").

**As 13 colunas, nesta ordem:** `Sem OS` → `Sem situação` → as **11 situações**
da OS do Harmonit (38 · 251 · 677 · 890 · 1316 · 15694 · 15695 · 15696 ·
15746 · 15747 · 15797).

🚨 **"Sem OS" é a primeira porque é de onde a OS nasce.** Hoje **todas** as
solicitações estariam nela — nenhuma virou OS ainda —, e esse é o estado
correto, não uma tela quebrada.

🚨 **"Sem situação" existe por um número medido:** das **574 OS** no cache do
FPSL em 22/10, **127 têm `situacao_id = 0` e 37 têm `NULL`** — 164 que não
estão em nenhuma das 11. Sem essa coluna elas desapareceriam da tela (`M12`).
E os **três** casos (nulo, zero, número fora da lista) caem nela com o número
cru à vista: é a régua do grid do FPSL, *"estado desconhecido mostra o valor
cru"*.

🚨 **Mover o card ainda NÃO existe, e a tela diz isso em vez de oferecer o
gesto.** A rota que escreve `situacaoId` no Harmonit é da volta seguinte e
depende de ele confirmar o mapa formulário → `problemaId`. Precedente: o
`ModalAgendar`, que explica em vez de sumir.

⚠️ **Coluna vazia nasce colapsada**, com o contador à vista — como a coluna
"Pago" do kanban do FPSL. As duas primeiras **nunca** colapsam.

⚠️ **A cor nunca é o único portador:** o estado da solicitação vem escrito na
etiqueta e a situação vem escrita no card.

O card leva para a **FRM_1.1** (`/solicitacoes?solicitacao=<id>`): a ficha dos
34 campos do credenciamento é de lá, e o painel não a repete.

### 🔵 Os outros três painéis — desenhados, medidos, e NÃO implementados

🚨 **Nenhum deles é este com outro filtro** — é por isso que só o da Operação
nasceu. Quando um entrar, entra com módulo e rota próprios, não com um `if`
dentro do `paineis.py`.

**PÓS VENDA** — NPS (9 campos) · CES (5).
🚨 **Não é fila, é MEDIÇÃO**, e isso saiu do formulário, não de gosto: a nota é
uma lista de **1 a 10**, e as regras do NPS já separam quem respondeu —
**8, 9 ou 10 pede INDICAÇÃO** (nome do indicado, telefone, e-mail, empresa) e
**7 ou menos pede O QUE OCORREU**, campo obrigatório. NPS e CES **não geram
OS**: coluna por situação ali não mede nada. A tela quer três medidas (NPS do
mês, CES, respostas), a distribuição das notas, e **duas filas de ação**:
indicações a contatar e reclamações a tratar.
🔴 Falta dele: **o corte do promotor, 8 ou 9** (o formulário do Bitrix trata 8
como promotor; no NPS de mercado 8 é neutro) · se nota baixa avisa alguém na
hora pelo chat interno.

**CONTRATUAL** — Ficha cadastral (36) · Aditivo (18) · Substituição (17) ·
Rescisão (17).
O que trava **não é a situação, é o documento**: três faixas — falta documento
→ a conferir → pronto. A ficha cadastral pede **3 anexos** e **10 dos seus 36
campos** só nascem depois de uma escolha; a rescisão, 8 de 17. O campo
`product` (Aditivo e Substituição) é **texto** nesta etapa.
🔴 Falta dele: **endereço** — puxar do Harmonit, pedir no formulário com
ViaCEP, ou os dois? (o cadastro do MoviZap **não tem endereço em forma
nenhuma**) · o que conta como "pronto" · se a conferência vira OS.

**FINANCEIRO** — Financeiras (10) · Pagamento de técnicos (16) ·
Administrativas (11) · Fornecedores (16).
Fila simples com três medidas, e o único com **elo externo**: *Pagamento de
parceiros técnicos* fala do mesmo assunto que o **Fechamento de Contas dos
Técnicos** do FPSL (`FIN_2.1`, 170 técnicos reais).
⚠️ Risco nomeado: virar **uma segunda contabilidade** ao lado dele. Enquanto o
elo for um link, não há duas verdades.
🔴 Falta dele: ligar ou não ao fechamento do FPSL · se o painel mostra
**valor** — e, se sim, **acrescentar o campo**, porque **nenhum dos quatro
tem** hoje.

⚠️ **O que falta para QUALQUER um deles mostrar OS:** duas rotas que a ponte do
FPSL ainda não tem — **criar OS** (`SalvarOrdemServico` com `id: 0`) e
**escrever `situacaoId`** —, as duas pelo caminho provado do
`os_ponte.py:_corpo_de_escrita` (relê, remonta inteira, grava, relê e compara
os 39 campos). Elas dependem do mapa formulário → `problemaId`, que é decisão
dele.

## 22/10 — 🔍 AUDITORIA DO DIA (pedido dele: *"quer documentar e auditar os feitos?"*)

Medida, não afirmada. O que ela achou, e o que foi feito no mesmo dia:

### 🔴 1. As dez rotas que entraram hoje não tinham teste HTTP nenhum

**17 arquivos** desta suíte usam `TestClient`, e as rotas de 22/10 não. A mais
exposta do projeto — o **POST público de formulário**, que qualquer um na
internet alcança — estava provada só por `curl` meu, à mão.

**Fechado:** `tests/teste_rotas_formularios.py`, **33 testes** cobrindo as três
rotas públicas, as seis do painel de solicitações e a do painel da Operação.
Entre eles: a isca responde sucesso e **não grava**; envio sem o carimbo de
abertura é recusado; anexo em campo que não aceita arquivo é recusado;
formulário desligado responde **404 igual a slug inexistente**; e o que é
interno (`nosso_nome`, `problema_id`, `bitrix_id`) **não sai** na resposta
pública.

⚠️ É a mesma lição de 21/10, quando a auditoria dele achou três módulos em
produção sem teste Python: **prova ao vivo não substitui teste.** O `curl`
provou o dia; só o teste prova a semana que vem.

### 🔴 2. Três funções que a tela usa e nenhum teste chamava

`formularios.listar_solicitacoes` (a lista da FRM_1.1, com os filtros de
formulário e estado), `formularios.lista_para_o_painel` (o cabeçalho com a
contagem de novas) e `formularios.registrar_envio`. Mais `desafio_sempre`,
`nome_legivel` (a desduplicação) e `paineis._resumo`. **Todas cobertas agora.**

### 🚨 3. A suíte nova passou na primeira rodada e REPROVOU na segunda

Achado contra mim mesmo, e o mais útil do dia. Cada envio bom chama
`registrar_envio`, que conta no **SQLite do `ratelimit`** — e esse contador
**sobrevive ao processo e ao restart, de propósito**. Em duas rodadas os envios
de teste passaram de 5 na mesma hora, a rota passou a exigir a conta de somar,
e todo teste seguinte recebia *"Responda a conta para enviar"* no lugar da
frase esperada.

**Remédio:** a fixture `contador_limpo` apaga os eventos da chave
`formulario|testclient` antes e depois de cada teste — só essa chave, porque o
contador dos IPs reais é de produção. Confirmado com **três rodadas seguidas**,
33 verdes em cada.

⚠️ **O que isso ensina além do conserto:** teste que escreve em contador
compartilhado não é determinístico, e *"passou"* na primeira rodada é a forma
mais convincente de esconder isso.

### 🚨 4. Cinco textos passaram a mentir quando o grupo "Painéis" ganhou tela

`M12`, e cada um era verdadeiro quando foi escrito: *"Painéis › Operacional
nasce vazio"* aparecia no cabeçalho de `GRUPOS`, em dois comentários de telas,
no `MenuLateral` (duas vezes) e no **`docs/03`**. Desde a `PNL_1.1` o grupo tem
tela e o subgrupo não existe — quem lesse aprenderia errado, e quem fosse
escrever o segundo painel procuraria um subgrupo que saiu.

**Corrigidos os cinco**, com o exemplo trocado pelo que é verdade hoje: o grupo
declarado e vazio passou a ser o **"E-mail"**.
⚠️ O **`docs/06` não entra nessa correção**: ele é diário, e entrada datada
descreve o que era verdade naquele dia.

### ✅ O que a auditoria conferiu e estava certo

| conferido | estado |
|---|---|
| migrações aplicadas | **076** é a última, e o `validar_miolo.py` confirma (58 tabelas) |
| segredo dos tokens públicos | no `.env`, 64 caracteres, **sem** o aviso de derivação no log |
| pasta de anexos | `/home/claude/movizap_formularios_anexos`, modo **700**, vazia |
| superfície do host público | `/f/`, `/pub/assets/` e `/api/publico/` passam; `/api/conversas` e `/inicio` dão **403**; a raiz dá 404 |
| formulário desligado | **404 na API**, igual a slug inexistente |
| sobras de teste | nenhum formulário `ZZ_`, nenhum anexo, nenhum evento de contador de teste |
| árvore do git | limpa (fora os `.bak_` do dia, que são o desfazer) |

### 🔴 A única sobra deliberada

A **solicitação 39** (`zz Externo · zz Pastelaria Velasco`) continua no banco,
de propósito: é a prova de ponta a ponta pela internet, e serve para ele ver a
tela com conteúdo. **É dele apagar.**

**Suítes depois da auditoria: 1746 Python · 440 JS** (eram 1713/440 antes
dela; 33 testes novos).

### 🔍 22/10 — e CONFERIR A DOCUMENTAÇÃO ACHOU TRÊS COISAS QUE FALTAVAM

Ele perguntou duas vezes *"tudo documentado?"*. Em vez de responder, procurei o
que **não** estava — por `grep`, lugar por lugar. Os três achados foram
consertados no mesmo dia, e **nenhum deles era de código do dia**: eram as
pontas que ficam fora do repositório e do diff.

**1. 🚨 `forms.movisat.com.br` não estava no `03_Exposicao_de_Rede.md`.** Um
domínio **público, sem login**, aberto hoje, fora do documento cuja única
função é dizer *"o que está aberto, e por quê"* — o mesmo tipo de buraco que
aquele doc nasceu para fechar em 11/08, quando a API do Evolution respondia na
internet. **Corrigido:** entrou na tabela de hosts e ganhou seção própria, com
os três caminhos que passam, o 403 genérico, as zonas de `limit_req`, o
certificado e o aviso dos dois formulários que perderam o reCAPTCHA.

**2. 🚨 A pasta de anexos dos formulários não estava em backup NENHUM.** O
`backup_midia.sh` espelha `/home/claude/movizap_midia`; o anexo de formulário
mora em `/home/claude/movizap_formularios_anexos` e ficou de fora. E o conteúdo
dela é o **pior de perder**: é a **única cópia** de um documento que o cliente
mandou (contrato social, comprovante de endereço) — o banco guarda o
**caminho**, não o arquivo, e no e-mail o Gmail tem a cópia, aqui ninguém tem.
**Corrigido:** o script passou a espelhar **duas** pastas, cada uma com o seu
instantâneo datado e a conferência de contagem dos dois lados. ⚠️ Pasta que
ainda não existe é **pulada com aviso no log**, não erro — ela só nasce no
primeiro upload; e **uma pasta que falha não impede a outra**, mas o script
sai diferente de zero, senão o cron ficaria calado. Rodado de verdade em
22/10: mídia **4.597 arquivos** intactos, anexos **0** (como esperado).

**3. O `.env` de um install novo não teria o segredo dos formulários.** O
`gerar_env.py` não o gerava, então máquina nova nasceria com o segredo
**derivado do `jwt_secret`** — que está escrito como *fallback*, não como
normal. **Corrigido:** a chave passou a ser gerada no `.env` novo.

⚠️ **A lição, que vale além destes três:** o diff de hoje estava documentado; o
que faltava era tudo o que vive **fora do repositório** — nginx, cron, backup,
`.env`. "Documentado" não é "o código tem comentário": é *alguém que não estava
aqui consegue achar isto depois*.
