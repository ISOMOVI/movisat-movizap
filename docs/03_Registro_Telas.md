# 03 — Registro de telas e barra de status

Toda tela do MoviZap tem um **código imutável**. O código é ao mesmo tempo **endereço**, **chave de permissão** e **âncora de auditoria**.

---

## Por que existe

Quando alguém diz "deu erro na tela de cadastro", começa uma investigação. Quando diz **"deu erro na `CAD_1.2`, requisição `a3f9`"**, a investigação já acabou.

```
Objetivo:     achar em segundos o código por trás de qualquer erro relatado
Hoje:         = o objetivo, desde a primeira tela
Por quê:      pedido do usuário em 2026-08-04, no modelo de bloco de notas/Excel
Reavaliar se: — fechado
```

## Formato

```
MOD_a.b[.c]
```

| Parte | Significado |
|---|---|
| `MOD` | módulo — `INI` início · `ATD` atendimento · `EML` e-mail · `CAD` cadastro · `CFG` configuração · `REL` relatório |
| `a` | submódulo |
| `b` | tela |
| `c` | aba dentro da tela (opcional) |

🚨 **O código nunca muda.** Título muda, rota muda, arquivo muda — código não. Se uma tela for aposentada, o código é **aposentado junto**, nunca reaproveitado. Reaproveitar código faz o log antigo mentir.

---

## Grupo e subgrupo do menu (21/10)

🔵 Pedido dele em 19/10: o menu abrindo **em grupos e subgrupos**, que ficam
abertos até clicar de novo, e **Ligações dentro de Atendimento**.

🚨 **O grupo saía do PREFIXO do código até 21/10**, num mapa dentro do
`MenuLateral.vue`. Como o código é imutável por regra deste registro, mover
uma tela de grupo era impossível sem fazer o código mentir. Agora:

| Onde | O que |
|---|---|
| `telas.py` | cada tela pode trazer `grupo` e `subgrupo` |
| `telas.GRUPO_PELO_PREFIXO` | o **fallback**: tela sem `grupo` cai onde caía antes |
| `telas.GRUPOS` | os grupos que **existem**, e os subgrupos de cada um |
| `telas.do_usuario()` | leva os dois campos ao frontend |
| `MenuLateral.vue` | desenha dois níveis e o acordeão |

⚠️ **O fallback não é zelo, é a regressão que ele evita:** sem ele, toda tela
que uma entrega não tocar muda de lugar em silêncio.

🚨 **Grupo sem nenhuma tela visível não é desenhado.** É o que deixa um grupo
existir declarado e nascer vazio (decisão dele) sem mentir na tela. Vale igual
para permissão: quem não tem nenhuma tela do grupo não vê o grupo.

⚠️ **O exemplo mudou em 22/10.** Era "Painéis › Operacional"; o grupo
**Painéis** ganhou a `PNL_1.1` (Operação) e o subgrupo "Operacional" **saiu**
— ele nunca teve tela, e o painel chama-se "Operação". Hoje o grupo declarado
e vazio é o **"E-mail"**, porque o item do e-mail mora dentro de
"Atendimento".

**Agrupar não reordena.** A ordem na tela é a de `TELAS`, e `INI_1.1` é a
primeira de propósito — a rota `/` redireciona para `sessao.telas[0].rota`.

**O acordeão guarda o que está FECHADO**, em `localStorage`
(`movizap_menu_grupos`), por pessoa e por navegador. Guardar os abertos faria
toda tela nova nascer escondida para quem já usa o painel. O grupo da tela
aberta agora nasce aberto mesmo se estiver gravado como fechado, e no menu
compacto não há acordeão: o nome do grupo some por CSS, então os itens
aparecem todos.

---

## Telas — espelho de `movizap/telas.py`

> 🚨 **ESTA TABELA É A ÚNICA.** Até 12/08 este arquivo tinha **duas** tabelas
> de telas — "Registro — Fase 1" e "Telas de hoje" — e elas divergiram em
> silêncio: a primeira dava `admin` a seis telas que o código trata como
> `owner`, e não tinha `EML_1.1`, `INI_1.1` nem `CFG_2.2`. Só a segunda tinha
> teste. Duas tabelas do mesmo fato é uma que vai mentir; o conserto não foi
> corrigir células, foi apagar a cópia.
>
> ⚠️ `teste_telas.py` reprova se um código existir no `telas.py` e não
> aparecer aqui. Foi assim que `INI_1.1` e `EML_1.1` ficaram de fora até 10/08.

| Código | Tela | Rota | Permissão | Fase |
|---|---|---|---|---|
| `INI_1.1` | Início | `/inicio` | `atendimento` | 1 |
| `ATD_1.1` | WhatsApp | `/atendimento` | `atendimento` | 1 |
| `ATD_1.2` | Conversa | `/atendimento/{id}` | `atendimento` | 1 |
| `ATD_1.3` | Fila | `/atendimento/fila` | `equipe` | 1 |
| `ATD_3.1` | Informativos | `/informativos` | `informativos` | 1 |
| `ATD_5.1` | Histórico | `/atendimento/historico` | `equipe` | 1 |
| `ATD_6.1` | Chat interno | `/chat` | `atendimento` | 1 |
| `EML_1.1` | E-mail | `/email` | `atendimento` | 1 |
| `FRM_1.1` | Solicitações | `/solicitacoes` | `equipe` | 1 |
| `PNL_1.1` | Operação | `/paineis/operacao` | `owner` | 1 |

### 🚨 `PNL_1.1` mudou de natureza em 29/10 — o card é a OS

Até 28/10 este painel lia **só** `formulario_solicitacao`, e a base tinha **uma**
solicitação: a tela estava tecnicamente certa e praticamente vazia.

🔵 **Decisão D8 dele:** o card é a **OS**, de qualquer origem — *"seja pelo
painel, seja pelo FPSL, seja pelo formulario, seja a mão"*.

O quadro passou a ser a **união de duas fontes**, deduplicada pelo
`numero_ordem`:

1. **as OS do ERP** desde a data matriz, pela ponte do FPSL
   (`GET /api/os/por-situacao`);
2. **as nossas solicitações** que já têm OS — para a OS anterior à data matriz,
   a finalizada com o interruptor ligado, e **a ponte fora do ar**.

| o que | onde |
|---|---|
| a **data matriz** (D9: 24/10/2026, **só o owner muda**) | `config.painel_operacao_desde` · `PUT /api/paineis/operacao/desde` (**403** para quem não é owner) |
| o interruptor **"só as abertas"** | `GET /api/paineis/operacao?so_abertas=0|1`, ligado por padrão |
| as 17 colunas | `movizap/paineis.py` — `SITUACOES` |

🚨 **PONTE FORA DO AR NÃO ESVAZIA O PAINEL**, e a tela **diz**: sem o FPSL o
quadro cai de 10 para 2 cards. Quadro pequeno sem explicação faria o operador
concluir que não há trabalho — e é justo nessa hora que há. É o
`ponte_respondeu` da resposta.

### Mover o card — existe desde 29/10 (Bloco D)

🔵 **Quatro decisões dele, uma frase cada:** *"O card pode ser por arrastar"* ·
*"deve ter o log de quem faz o que SEMPRE"* · *"que tal de caminho proibido é
esse??"* · *"pode mover que tiver acesso a tela, por enquanto somente owner"*.

| peça | como ficou |
|---|---|
| o gesto | **arrastar** o card para a coluna · **e** um `select` das 17 em cada card, porque arrastar não alcança teclado |
| a ordem | 🚨 **LIVRE.** Nada valida transição — nem aqui, nem na ponte, nem o Harmonit. O único recusado é id **fora das 17**, e não por ser proibido: o card ficaria sem coluna |
| quem move | `requer_tela("PNL_1.1")` e **nada além**. Hoje a aba é `owner`, então o alcance é ele; concedida a aba, quem a receber **já move** |
| o log | **toda** passagem em `os_passagem` (migração 083), **inclusive a recusada** |
| a trava de concorrência | a tela manda a situação que **ela** carregou; se o ERP já estiver em outra, a escrita é **recusada** e o painel recarrega |
| `pode_mover` | passou de `False` para **`True`**, e continua sendo a verdade do gesto |

⚠️ **O movimento na tela é otimista e o quadro RECARREGA sempre**, deu certo ou
não: a verdade é o que o ERP confirmou, nunca o que a tela achou que ia
acontecer. A recusa aparece com `role="alert"`.

🚨 **A escrita é a OS INTEIRA** (`SalvarOrdemServico` — o Harmonit não tem
"alterar só a situação"), então a rota lê, remonta, grava, **relê e compara os
40 campos**: diferença fora do `situacaoId` devolve o card para a coluna de
origem.

⚠️ **E a frase que explicava a ausência do gesto não voltou** — ela saiu em
29/10 a pedido dele (*"os comentários tbm devem sumir dali"*) e o quadro
continua sem `porque_nao_move`. Tem trava própria.

### A linha de aviso: três casos de "sem OS", não um

🚨 **Até 29/10 a tela chamava todos de falha** — e ele achou o defeito na tela
minutos depois de ela subir: *"1 sem OS (a escrita no Harmonit falhou)"*, quando
**nada havia falhado**.

| na `solicitacao_os` | significa | a tela escreve |
|---|---|---|
| nenhuma linha | **nunca se tentou** (chamado anterior ao Bloco A, ou formulário que não abre OS) | *"N chamados sem OS, de antes de a abertura ser automática"* |
| linha com `erro` | tentou e **falhou** | *"N OS não abriram em M chamados"* |
| a sobra das duas contas | linha preparada e nunca tentada | *"N sem OS e sem motivo registrado"* |

⚠️ **A terceira frase existe de propósito**: sem ela aquele chamado
desapareceria **entre** as duas outras.

### Os efeitos visuais (do mockup que ele aprovou)

A cor do **catavento** como código de etapa (borda de cima da coluna, borda
esquerda do card), o contador **cheio** com card e **vazado** sem, a **OS na
frente** do card, e sombra com levantada na passagem.

🚨 **A COR NUNCA É O ÚNICO PORTADOR** — regra desta casa, com trava própria: o
**nome da etapa** fica na coluna e o **número da situação** no card.
⚠️ `prefers-reduced-motion` desliga o movimento e **mantém** a sombra.
⚠️ Os **hexes do mockup não entraram**: cada um deles já é um token desta casa,
e duplicá-los quebraria a tela quando o tema mudar.

📘 **O detalhe inteiro, com as 12 decisões dele e a auditoria:**
`docs/16_Pipeline_da_Operacao.md`.
| `CAD_1.1` | Clientes | `/cadastro/clientes` | `cadastro` | 1 |
| `CAD_1.2` | Contatos | `/cadastro/contatos` | `cadastro` | 1 |
| `CAD_2.1` | Atendentes | `/cadastro/atendentes` | `equipe` | 1 |
| `CAD_2.2` | Times | `/cadastro/times` | `equipe` | 1 |
| `CFG_0.1` | Configurações | `/config` | `atendimento` | 1 |
| `CFG_1.1` | Canais | `/config/canais` | `owner` | 1 |
| `CFG_2.1` | IA — prompt | `/config/ia/prompt` | `owner` | 1 |
| `CFG_3.1` | Sincronização | `/config/sync` | `owner` | 1 |
| `CFG_4.1` | Classificações | `/config/classificacoes` | `owner` | 1 |
| `CFG_5.1` | Automação por tipo | `/config/automacao` | `owner` | 1 |
| `CFG_6.1` | Atalhos de teclado | `/config/atalhos` | `owner` | 1 |
| `CFG_7.1` | Geral | `/config/geral` | `owner` | 1 |
| `CFG_8.1` | Eventos do WhatsApp | `/config/eventos` | `owner` | 1 |
| `CFG_9.1` | Registro de telas | `/config/telas` | `owner` | 1 |
| `CFG_10.1` | Minha conta | `/config/minha-conta` | `atendimento` | 1 |
| `CFG_11.1` | Notificações | `/config/notificacoes` | `atendimento` | 1 |
| `CFG_12.1` | Mensagens rápidas | `/config/mensagens-rapidas` | `atendimento` | 1 |
| `CFG_2.2` | IA — analytics | `/config/ia/analytics` | `owner` | 2 |
| `LIG_1.1` | Ligações | `/ligacoes` | `atendimento` | 1 |
| `ATD_7.1` | Agendamentos | `/agendamentos` | `atendimento` | 1 |
| `ORC_1.1` | Orçamentos | `/orcamentos` | `atendimento` | 1 |
| `CFG_13.1` | Orçamento (numeração) | `/config/orcamento` | `owner` | 1 |
| `CFG_14.1` | Vínculo dos técnicos | `/config/vinculo-tecnicos` | `owner` | 1 |
| `REL_1.1` | Relatórios | `/relatorios` | `owner` | 3 |

🚨 **AS SEIS TELAS `CFG_*` SÃO ABAS DA `CFG_0.1` DESDE 27/08** (decisão do
usuário). Elas continuam **existindo** — código, rota e permissão próprios, e
link antigo continua abrindo. O que mudou é que deixaram de ser item de menu:
o registro marca `"aba_de": "CFG_0.1"` e o `MenuLateral` pula quem tem esse
campo, do mesmo jeito que já pulava rota com parâmetro.

⚠️ **`aba_de` É APRESENTAÇÃO, NÃO PERMISSÃO.** As telas-aba continuam sendo
devolvidas por `do_usuario()`, e têm de continuar: a guarda de rota do frontend
usa `sessao.telas` para saber o que este usuário pode abrir. Tirá-las de lá
barraria `/config/canais` para o próprio owner.

🚨 **A `CFG_0.1` PASSOU A `atendimento` EM 22/09, E ISSO NÃO CONCEDE NADA.**
Cada aba mantém a permissão dela e o `Configuracoes.vue` só desenha as que
`sessao.telas` traz: o owner vê dez abas, o atendente vê **uma** — Minha conta.
A casca é casca.

🔵 **ATALHOS (`CFG_6.1`) PASSOU A `owner` EM 24/09**, decisão dele: *"pode
exibir a atalhos somente para o owner tbm"*. Até ali o atendente via duas abas.
🚨 **O Enter não foi junto.** `GET /api/eu/atalhos` (de onde Caixa de entrada,
Chat interno e E-mail leem o `enviar_com_enter`) e `PUT /api/eu/enviar-com-enter`
(o interruptor da Minha conta) saíram da `CFG_6.1` para `get_usuario` —
presas a ela, dariam 403 ao atendente e as três telas cairiam no Enter
desligado em silêncio. Ligar atalhos e trocar teclas continuam presos à tela.
Teste: `TestPortaDoConfig.test_enter_nao_depende_da_tela_de_atalhos`.

⚠️ **ERA UMA PORTA TRANCADA, e ninguém tinha visto.** `CFG_6.1` e `CFG_10.1`
nasceram `atendimento` de propósito (*"cada um mexe em SI MESMO"*), mas têm
`aba_de` — e o `MenuLateral` pula quem tem `aba_de`. Sem item de menu, e com o
`/config` em `owner`, as duas telas PESSOAIS não tinham entrada nenhuma: só
digitando a URL. Medido em 22/09: **9 dos 10 atendentes ativos** sem acesso, e a
tabela `preferencia_atendente` com **uma linha só**, a do owner. Foi o que fez
"nasce desligada, quem quiser liga" nunca ter sido uma escolha de verdade.

🚨 **`do_usuario()` PRECISOU DE UMA LINHA.** Ela monta a resposta à mão, com
quatro campos; um campo novo no registro não chegava ao frontend sozinho —
falha calada, menu igual, suíte verde. Achado validando antes de escrever.

⚠️ **A POSIÇÃO DA `CFG_0.1` NA LISTA NÃO É ESTÉTICA.** A rota `/` do frontend
manda para `sessao.telas[0].rota`: a primeira tela do registro é a tela de
entrada de todo login. Por isso ela entra no bloco das CFG, e a `INI_1.1`
continua sendo a primeira.

## O ícone de cada tela, e o ícone da ajuda

O campo **`icone`** deste registro é o que o menu desenha, e ele é **a fonte
única**: o `MenuLateral` não escolhe ícone, ele desenha o que vem daqui.

| Módulo | Ícone | Onde |
|---|---|---|
| `INI_1.1` Início | `bi-house` | menu |
| `EML_1.1` E-mail | `bi-envelope` | menu |
| `ATD_1.1` WhatsApp | `bi-chat-dots` | menu |
| `ATD_1.2` Conversa | `bi-chat-text` | fora do menu (rota com parâmetro) |
| `ATD_1.3` Fila | `bi-list-ol` | menu |
| `ATD_5.1` Histórico | `bi-clock-history` | menu |
| `ATD_6.1` Chat interno | `bi-chat-left-dots` | menu |
| `LIG_1.1` Ligações | `bi-telephone` | menu |
| `ATD_7.1` Agendamentos | `bi-calendar-check` | menu |
| `ORC_1.1` Orçamentos | `bi-receipt-cutoff` | menu |
| `CFG_13.1` Orçamento | `bi-receipt` | aba |
| `CFG_14.1` Vínculo dos técnicos | `bi-person-vcard` | aba |
| `ATD_3.1` Informativos | `bi-megaphone` | menu |
| `FRM_1.1` Solicitações | `bi-ui-checks` | menu |
| `PNL_1.1` Operação | `bi-kanban` | menu (grupo Painéis) |
| `CAD_1.1` Clientes | `bi-building` | menu |
| `CAD_1.2` Contatos | `bi-person-lines-fill` | menu |
| `CAD_2.1` Atendentes | `bi-people` | menu |
| `CAD_2.2` Times | `bi-diagram-2` | menu |
| `CFG_0.1` Configurações | `bi-sliders` | menu |
| `CFG_1.1` Canais | `bi-whatsapp` | aba |
| `CFG_2.1` IA — prompt | `bi-robot` | aba |
| `CFG_3.1` Sincronização | `bi-arrow-repeat` | aba |
| `CFG_4.1` Classificações | `bi-tags` | aba |
| `CFG_5.1` Automação por tipo | `bi-robot` | aba |
| `CFG_6.1` Atalhos de teclado | `bi-keyboard` | aba |
| `CFG_7.1` Geral | `bi-sliders` | aba |
| `CFG_8.1` Eventos do WhatsApp | `bi-broadcast` | aba |
| `CFG_9.1` Registro de telas | `bi-list-check` | aba |
| `CFG_10.1` Minha conta | `bi-person-circle` | aba |
| `CFG_11.1` Notificações | `bi-bell` | aba |
| `CFG_12.1` Mensagens rápidas | `bi-lightning` | aba |

### `bi-question-circle` — a ajuda da tela (27/08)

Pedido dele: *"as abas tem textos explicativos do que as telas são, o que
fazem e o que falta... transforme em balões ícones apenas, se passar mouse
aparece os textos"*.

**O texto explicativo do cabeçalho virou um ícone** em **15 telas**, com o
componente `componentes/AjudaDaTela.vue`.

🚨 **ERAM 15 E EU ENTREGUEI 13 (corrigido em 28/08).** A varredura de 27/08
procurou a FORMA da marcação — `<h1>Título</h1>` seguido de
`<p class="apagado pequeno">` — e não o alcance do pedido. Ficaram de fora
exatamente as duas telas de prioridade: o **E-mail**, cujo `<h1>` tem
`class="tela__titulo"` e por isso não casou com o padrão, e a **Caixa de
entrada**, cujo texto não estava no cabeçalho e sim dentro do campo de busca
(`campo__ajuda`). Ele cobrou: *"notei que as mensagens que ficam aparecendo
ainda estão pelo sistema todo, e já pedi ocultação dela"*.

⚠️ **A TRAVA QUE ISSO DEIXA:** demanda de varredura ("em todas as telas",
"pelo sistema") começa por uma **lista nominal de telas**, escrita antes de
mexer em código e conferida uma a uma — nunca por padrão de marcação. E as
telas de prioridade entram primeiro, não por último. **O ícone é sempre o mesmo** —
`bi-question-circle` — e é convenção, não escolha por tela: um símbolo
diferente em cada lugar obrigaria a reaprender o que ele faz.

🚨 **O TEXTO NÃO SE PERDE, ELE SE RECOLHE.** Continua no fonte, no DOM e
legível por leitor de tela; some só da vista de quem já sabe o que a tela faz.
Esconder informação atrás de um ícone que não a devolve seria trocar um
problema por outro.

⚠️ **ABRE NO HOVER E NO FOCO.** Só no hover, quem usa teclado e quem usa toque
nunca leriam o texto — é o mesmo defeito que as ações do balão tiveram até
27/08, e que custou uma auditoria.

⚠️ **`visibility`, não `display: none`.** Com `display:none` o conteúdo sai da
árvore e alguns leitores de tela deixam de anunciá-lo — e foi exatamente o
`display:none` que tirou as ações do balão do alcance do teclado.

⚠️ **As telas sem cabeçalho padrão ficaram de fora**, e é correto: Caixa de
entrada, Chat interno, E-mail, Configurações, Início e as auxiliares não têm o
parágrafo explicativo que este ícone substitui.

🚨 **TODA CONFIGURAÇÃO É `owner`, E ISSO É DECISÃO, NÃO DESCUIDO.** A tabela
antiga dizia `admin` em seis dessas linhas. Quem lesse criaria um perfil
`admin` esperando que ele configurasse Canais ou Sincronização, e levaria 403
sem entender: `pode_acessar` devolve **False** para tela `owner` a menos que a
pessoa seja o owner. Em 12/08 o perfil `admin` saiu do vocabulário — ver
"Perfis" abaixo.

## Abas e componentes

Não entram no `telas.py`: **não têm rota nem permissão próprias**, e o
`telas.py` é o registro das rotas — é ele que gera menu e resolve permissão.
Herdam a permissão da tela que os hospeda. **Não é drift.**

Continuam valendo como âncora de auditoria: o log grava `CAD_1.2.2` quando o
erro foi na aba de telefones, e é isso que se procura.

| Código | O quê | Dentro de |
|---|---|---|
| `CAD_1.2.1` | Contato — dados | `CAD_1.2` |
| `CAD_1.2.2` | Contato — telefones | `CAD_1.2` |
| `CAD_1.2.3` | Contato — papéis | `CAD_1.2` |
| — | Gaveta do contato (painel lateral) | `ATD_1.2` — **sem código próprio** |

⚠️ **A gaveta que existe hoje NÃO é a `ATD_2.1`.** Ela abre por botão dentro da
conversa e mostra o que o Harmonit e o Bitrix sabem do número. A `ATD_2.1` é
outra coisa, ainda não construída: a ficha do cliente **consultando o FPSL** —
é o que o próprio texto da tela vazia promete. Até 12/08 a `ATD_2.1` aparecia
nesta tabela como se fosse a gaveta, contradizendo o `docs/10`, que dizia que a
gaveta está "fora do registro". Eram duas coisas com um nome só.

**Reservados, não implementar agora:**
`ATD_2.1` Ficha do cliente com FPSL · `CFG_2.2` IA — analytics · `REL_1.1` Relatórios

🚨 **`ATD_3.1` SAIU DA RESERVA EM 2026-08-07** e subiu para a Fase 1.
Decisão do usuário: *"o informativo é o que vai enviar, sem resposta de
cliente"*. O chip foi pareado no mesmo dia e o canal já entrega (TESTE
BOT com `DELIVERY_ACK` em 2 s).

⚠️ **É a única tela do sistema que alcança cliente de verdade EM LOTE**, e
o canal é irreversível. Por isso a permissão dela é `informativos`, que
**não está em nenhum perfil** além do owner: disparo em massa não é coisa
que se libera por padrão. Para dar a alguém, é acrescentar `informativos`
ao perfil em `telas.PERFIS` — decisão consciente, não efeito colateral.

⚠️ **Por que o chat é `ATD_6.1` e não cabe dentro de `ATD_1`.** Acrescentado
em 12/08. O submódulo `ATD_1` é atendimento a **cliente** — caixa, conversa,
fila. O chat interno é outro assunto: conversa entre atendentes, que nunca sai
para o WhatsApp. Pendurá-lo em `ATD_1` faria o log de auditoria misturar
"falou com cliente" e "falou com colega", que é justamente o que se quer poder
distinguir. Submódulo próprio custa três dígitos.

⚠️ **Por que o Histórico é `ATD_5.1` e não `ATD_2.2`.** Acrescentado em
2026-08-06. O submódulo `ATD_2` é a ficha do contato, e `ATD_3`/`ATD_4` já
estão reservados acima. Poderia ter virado `ATD_2.2`, mas ficaria pendurado no
submódulo da ficha, com quem não tem parentesco nenhum. Histórico é assunto
próprio, então ganha submódulo próprio. **Custo: nenhum — são três dígitos.**

⚠️ **Contagem de linhas não serve como reconciliação.** Até 12/08 este trecho
dizia "a tabela tem 17 linhas e o `telas.py` tem 13 de Fase 1 — a diferença são
`ATD_2.1` e as três abas". A conta estava errada e ninguém percebeu, porque
número em prosa não tem teste. A separação agora é estrutural: **tela** e
**aba/componente** são duas tabelas diferentes, e só a primeira é espelho do
`telas.py`. Quem quiser conferir roda `teste_telas.py`, não conta linha.

---

## Fonte única

Espelha o `abas.py` do MoviServer, sem desvio:

```
telas.py  →  código · título · rota · arquivo · permissão · fase · ativo
```

- **Tela que não está no registro não existe.** Rota sem código registrado não sobe.
- A **navegação** é gerada do registro — menu não se escreve à mão.
- A **permissão** vem do registro: `requer_tela("CAD_1.2")` como dependency da rota. A permissão vive no backend, nunca no `localStorage`.
- O **log de auditoria** grava o código, não a URL. URL muda; código não.
- Conta nova nasce **sem nenhuma tela**: falha fechado.

---

## 🚨 Mexeu na tela? Atualiza o registro NO MESMO COMMIT

Regra pedida pelo usuário em 2026-08-05, e a mais fácil de esquecer.

Mudou **rota, título, ícone, permissão ou fase** de uma tela, o
`movizap/telas.py` muda junto — não no dia seguinte, não "depois que
estabilizar". No mesmo commit.

**Por que isto não é burocracia:**

| Se o registro desatualizar | O que quebra |
|---|---|
| rota mudou, registro não | o menu leva ao **lugar errado** — e o frontend desenha o que vem, então ele obedece o registro errado sem reclamar |
| permissão mudou, registro não | alguém enxerga o que não devia, ou perde acesso sem motivo aparente |
| título mudou, registro não | o log de auditoria descreve uma tela que **já não é aquela** |
| tela saiu, código reaproveitado | 🚨 **o log antigo passa a mentir** — aponta para uma tela que nunca visitou |

**Código aposentado nunca volta.** Tela removida deixa o código queimado para
sempre; a próxima usa número novo. É barato: são três dígitos.

**Como conferir:** `CFG_9.1` mostra o registro inteiro, e
`tests/teste_telas.py` reprova código duplicado, rota duplicada e permissão
vazando. Se o teste passar e a tela estiver errada, é porque o registro
mentiu junto — por isso a atualização é no mesmo commit, não depois.

---

## Barra de status

Fixa no rodapé de **toda** tela principal. Modelo mental: barra do Excel / bloco de notas.

```
┌──────────────────────────────────────────────────────────────────────┐
│ Iago Santos · sessão 01:47 · 04/08/2026 14:52 · CAD_1.2 · req a3f9  │
└──────────────────────────────────────────────────────────────────────┘
```

| Campo | Fonte |
|---|---|
| Usuário logado | sessão |
| Duração da sessão | relógio do cliente, desde o login |
| Data e hora | fuso do usuário |
| **Código da tela** | registro |
| **Id da requisição** | gerado no backend a cada requisição, ecoado no header e no log |

**Por que o id da requisição:** no erro, o que se procura no log não é a tela — é *aquela* requisição. Com o código você acha o arquivo; com o id você acha a linha.

⚠️ A barra faz parte do sistema de design desde a primeira tela. Pregada por cima depois, fica com cara de remendo.

---

## Perfis

| Perfil | Permissões | Telas na prática |
|---|---|---|
| `owner` | todas | tudo, inclusive o que é exclusivo do owner |
| `admin` | `atendimento` `equipe` | as de `atendimento` + `ATD_1.3` `ATD_5.1` `CAD_2.1` `CAD_2.2` `FRM_1.1` (as cinco de `equipe`); no `/config`, só `CFG_10.1`, `CFG_11.1` e `CFG_12.1` (25/09: *"Owner e admin criam"* os Padrões e Formulários) |
| `atendimento` | `atendimento` | `INI_1.1` `ATD_1.*` `ATD_6.1` `ATD_7.1` `LIG_1.1` `ORC_1.1` `EML_1.1` `CFG_0.1` › `CFG_10.1` `CFG_11.1` `CFG_12.1` |
| `cadastro` | `cadastro` | `CAD_1.1` `CAD_1.2` |

Perfil é conjunto de **permissões**, e a permissão de cada tela vem do registro.
**Não existe permissão escrita fora dele.**

🚨 **`admin` SAIU DO VOCABULÁRIO EM 12/08.** Ele existia como perfil e como
permissão, e destravava exatamente duas telas — `CFG_2.2` (Fase 2) e `REL_1.1`
(Fase 3) —, **nenhuma das quais existe**. Na prática, um `admin` tinha o mesmo
alcance de quem tem `atendimento` + `cadastro`, e a doc prometia que ele
configuraria Canais e Sincronização, o que o código nunca permitiu. Ninguém
usava: a base tinha 1 `owner` e 3 `atendimento`.

Decisão do usuário no mesmo dia: **owner é o único administrador, e não nascem
mais owners.** As duas telas futuras passaram a `owner`, o perfil saiu de
`telas.PERFIS` e o `CHECK` da coluna `atendente.perfil` perdeu o valor
(migração 024).

🔵 **`admin` VOLTOU EM 24/09, COM OUTRO ALCANCE.** Decisão dele: *"o perfil
admin deve possuir exibição de telas de atendimento + Times + Atendentes +
Configurações > Minha conta, apenas"*. Não é o admin de 12/08: destrava a
permissão nova `equipe` (Times e Atendentes, antes `owner`) e nada de
`cadastro`. Migração 051 devolve o valor ao `CHECK`.

🚨 **O OWNER CONTINUA ÚNICO, e a trava não é a tela.** A conta do owner passa
de mão trocando o e-mail dela; um admin que editasse a linha do owner viraria
owner. Por isso, em `main.py`: `_so_owner_mexe_no_owner` (dados, senha,
jornada, desligar) e `_so_owner_da_admin` (só o owner cria, promove ou rebaixa
admin). As duas travas são 🟡 minhas, não pedido dele.
⚠️ Ainda em 24/09 ele pediu que o admin pudesse dar admin (*"do Admin permite
tem todos menos owner"*). A remoção da segunda trava foi barrada pelo
classificador de permissões da sessão, e **ele decidiu mantê-la** (*"1 mantem,
admin não vira owner"*): o admin não dá admin.

⚠️ **`informativos` não está em nenhum perfil**, de propósito — só o owner
alcança a `ATD_3.1`. Disparo em massa não se libera por padrão; para dar a
alguém, acrescenta-se `informativos` ao perfil em `telas.PERFIS`, como decisão
consciente.

---

## Códigos aposentados

🚨 **Nunca reaproveitados** — reusar faria o log antigo mentir.

- `ATD_4.1` — era o e-mail dentro do módulo de atendimento. Aposentado em 10/08: o usuário decidiu que e-mail **jamais** se mistura com WhatsApp, e ele virou `EML_1.1`, módulo próprio. A tela nunca existiu, então nada foi logado com ele.

## 21/10, terceira volta — `CFG_14.1`, a aba que fecha uma porta trancada

🟡 **Ponta 4 do plano de Agendamentos, e sugestão minha, não pedido dele.**
A rota `/api/tecnicos-harmonit/pendencias` entrou no ar em 21/10 **sem tela
nenhuma**: o dado existia e ninguém o via. A alternativa honesta era tirar a
rota.

| O que | Onde |
|---|---|
| a tela | `frontend/src/telas/VinculoTecnicos.vue` |
| a aba | `CFG_14.1`, `aba_de: CFG_0.1`, **só owner**, entre Sincronização e Orçamento |
| a rota de dados | `GET /api/tecnicos-harmonit/pendencias` |

⚠️ **A permissão dessa rota mudou de `CFG_7.1` para `CFG_14.1`**: a permissão
de uma rota é a da tela que a consome, e `CFG_7.1` é a Geral, que pode estar
concedida a quem não tem esta aba. O owner enxerga as duas, então ninguém
perdeu acesso.

🚨 **SÓ LEITURA.** Ela mostra os três buracos de cadastro e **não conserta
nada** — 🔵 a conclusão é dele, de 21/10: *"nenhuma regra resolve, é trabalho
de cadastro"*. Quem vincula à mão continua sendo a ficha do contato, na
conversa.


## 🚨 Rotas que exigem OWNER mesmo dentro de uma aba aberta a todos (26/10)

A permissão da tela **não é sempre a permissão de tudo o que se faz nela**. Há
caso em que a aba é aberta e **uma ação dentro dela não é**, e isto fica
registrado aqui porque é neste documento que alguém procura *"quem pode o
quê"*.

| rota | tela | permissão da tela | quem pode | por quê |
|---|---|---|---|---|
| `PUT /api/ligacoes/agentes/{agente_id}/pastas` | `LIG_1.1` | `atendimento` | **owner** | O campo manda um programa no computador de outra pessoa **ler uma pasta e subir o conteúdo**. A aba é `atendimento` por decisão dele de 15/10 (*"pode exibir a aba para todos"*) — e *"todo atendente vê a aba"* não pode virar *"todo atendente aponta o agente do colega para onde quiser"*. **Ver** continua aberto; **escrever** o caminho, não. |

⚠️ **A trava mora na rota, não na tela:** ela usa `auth.get_usuario` e confere
`usuario.get("owner")` por dentro, em vez de `requer_tela("LIG_1.1")` — que é o
que o resto da aba usa. Um teste prende isso
(`tests/teste_pasta_agente.py::test_a_rota_NAO_usa_a_permissao_da_aba`), porque
trocar a guarda por `requer_tela` abriria a ação para todo atendente **sem
mudar uma linha da tela**.
