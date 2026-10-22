"""Registro central das telas do MoviZap — fonte única de verdade.

Espelha o contrato do `abas.py` do MoviServer, com uma diferença: aqui cada
tela tem um CÓDIGO IMUTÁVEL (`ATD_1.1`, `CAD_1.2`...), e é ele que aparece na
barra de status, no log de auditoria e na permissão.

Regras que não mudam:
  - tela que não está aqui NÃO EXISTE: rota sem código registrado não sobe;
  - o código é imutável -- título, rota e arquivo podem mudar, código não;
  - código aposentado NUNCA é reaproveitado (faria o log antigo mentir);
  - o owner enxerga tudo, independente do que estiver gravado;
  - conta nova nasce sem nenhuma tela: falha fechado.

Ver `docs/03_Registro_Telas.md`.
"""

# `fase` documenta quando a tela entra. Só as de fase 1 sobem agora; as demais
# ficam registradas para o código já estar reservado e nunca ser reusado.
TELAS = [
    # ---- INI: a porta de entrada ----
    # 🚨 PRIMEIRA DA LISTA DE PROPÓSITO. A rota `/` do frontend redireciona
    # para `sessao.telas[0].rota` -- ser a primeira é o que faz esta tela ser
    # o destino de todo login, por senha ou pelo Google.
    {
        "codigo": "INI_1.1",
        "titulo": "Início",
        "rota": "/inicio",
        "icone": "bi-house",
        "descricao": "O que precisa de gente agora.",
        "grupo": "Início",
        "permissao": "atendimento",
        "fase": 1,
    },
    # ---- EML: e-mail ----
    # 🚨 MÓDULO PRÓPRIO, NÃO ATD. Decisão do usuário em 10/08: "jamais
    # misturemos whatsapp com gmail, nunca". Caixa própria, marcadores
    # próprios, fila própria -- e o código diz isso antes do primeiro clique.
    {
        "codigo": "EML_1.1",
        "titulo": "E-mail",
        "rota": "/email",
        "icone": "bi-envelope",
        "descricao": "Caixa de e-mail, separada do WhatsApp.",
        "grupo": "E-mail",
        "permissao": "atendimento",
        "fase": 1,
    },
    # ---- ATD: atendimento ----
    {
        "codigo": "ATD_1.1",
        "titulo": "Caixa de entrada",
        "rota": "/atendimento",
        "icone": "bi-chat-dots",
        "descricao": "Conversas abertas, por canal e por time.",
        "grupo": "Atendimento",
        "permissao": "atendimento",
        "fase": 1,
    },
    {
        "codigo": "ATD_1.2",
        "titulo": "Conversa",
        "rota": "/atendimento/{id}",
        "icone": "bi-chat-text",
        "descricao": "A conversa em si, com a ficha do cliente ao lado.",
        "grupo": "Atendimento",
        "permissao": "atendimento",
        "fase": 1,
    },
    {
        "codigo": "ATD_1.3",
        "titulo": "Fila",
        "rota": "/atendimento/fila",
        "icone": "bi-list-ol",
        "descricao": "Conversas esperando atendente.",
        "grupo": "Atendimento",
        "permissao": "atendimento",
        "fase": 1,
    },
    {
        # Submódulo 5 porque 2 é a ficha do contato e 3/4 estão reservados
        # (Informativos e E-mail). Código não se reaproveita -- ver o doc.
        "codigo": "ATD_5.1",
        "titulo": "Histórico",
        "rota": "/atendimento/historico",
        "icone": "bi-clock-history",
        "descricao": "Conversas encerradas, pesquisáveis.",
        "grupo": "Atendimento",
        "permissao": "atendimento",
        "fase": 1,
    },
    # ---- CAD: cadastro ----
    {
        "codigo": "CAD_1.1",
        "titulo": "Clientes",
        "rota": "/cadastro/clientes",
        "icone": "bi-building",
        "descricao": "Clientes, sincronizados do Harmonit ou criados aqui.",
        "grupo": "Cadastro",
        "permissao": "cadastro",
        "fase": 1,
    },
    {
        "codigo": "CAD_1.2",
        "titulo": "Contatos",
        "rota": "/cadastro/contatos",
        "icone": "bi-person-lines-fill",
        "descricao": "Pessoas, seus telefones e papéis.",
        "grupo": "Cadastro",
        "permissao": "cadastro",
        "fase": 1,
    },
    {
        "codigo": "CAD_2.1",
        "titulo": "Atendentes",
        "rota": "/cadastro/atendentes",
        "icone": "bi-people",
        "descricao": "Contas do painel e o que cada uma enxerga.",
        # 🔵 `equipe` e não `owner` desde 24/09: o `admin` administra a equipe
        # (ver PERFIS). O que protege o owner DENTRO da tela está em `main.py`,
        # `_so_owner_mexe_no_owner` -- a permissão da tela não basta.
        "grupo": "Cadastro",
        "permissao": "equipe",
        "fase": 1,
    },
    {
        "codigo": "CAD_2.2",
        "titulo": "Times",
        "rota": "/cadastro/times",
        "icone": "bi-diagram-2",
        "descricao": "Times que recebem transferência, e quem está em cada um.",
        "grupo": "Cadastro",
        "permissao": "equipe",
        "fase": 1,
    },
    # ---- CFG: configuração ----
    #
    # 🚨 AS SEIS TELAS DE CONFIGURAÇÃO VIRARAM ABAS DE UMA SÓ (27/08, decisão
    # do usuário). O campo `aba_de` é o que faz isso: a tela CONTINUA existindo
    # com código, rota e permissão próprios -- ela só deixa de ser item de
    # menu. Link antigo não quebra, a permissão continua valendo tela a tela e
    # o `teste_router.py` continua comparando registro contra roteador.
    #
    # 🚨 O `aba_de` PRECISA SAIR EM `do_usuario()` TAMBÉM. Descoberto validando
    # antes de escrever: aquela função monta a resposta à mão, com quatro
    # campos, e um campo novo aqui simplesmente não chegaria ao frontend --
    # falha calada, com o menu igual e a suíte verde.
    #
    # 🚨 A POSIÇÃO IMPORTA E NÃO É ESTÉTICA. A rota `/` do frontend manda para
    # `sessao.telas[0].rota`: a primeira tela do registro é a tela de entrada
    # de todo login. Por isso a CFG_0.1 entra AQUI, no bloco das CFG, e não no
    # topo -- a INI_1.1 continua sendo a primeira, como o comentário dela diz.
    #
    # 🚨 CÓDIGO NOVO, NUNCA REAPROVEITADO. `CFG_0.1` estava livre e não está em
    # CODIGOS_APOSENTADOS (que tem só `ATD_4.1`) -- conferido antes de
    # escrever. Reaproveitar código faz o log antigo mentir.
    {
        "codigo": "CFG_0.1",
        "titulo": "Configurações",
        "rota": "/config",
        "icone": "bi-sliders",
        "descricao": "As configurações do painel, em abas. O interruptor da IA mora aqui.",
        # 🚨 `atendimento` E NÃO `owner` DESDE 22/09, e a casca não concede nada:
        # cada aba continua com a permissão dela, e o `Configuracoes.vue` só
        # desenha as que `sessao.telas` traz. Owner vê as dez; atendente vê
        # uma -- Minha conta (Atalhos passou a `owner` em 24/09).
        #
        # ⚠️ ERA UMA PORTA TRANCADA. `CFG_6.1` e `CFG_10.1` nasceram
        # `atendimento` ("cada um mexe em SI MESMO"), mas têm `aba_de` -- e o
        # `MenuLateral` pula toda tela com `aba_de`. Sem item de menu e com o
        # `/config` em `owner`, as duas telas PESSOAIS não tinham entrada
        # nenhuma: 9 dos 10 atendentes ativos só chegariam nelas digitando a
        # URL. A tabela de preferência tinha UMA linha, a do owner.
        "grupo": "Configuração",
        "permissao": "atendimento",
        "fase": 1,
    },
    {
        "codigo": "CFG_1.1",
        "titulo": "Canais",
        "rota": "/config/canais",
        "icone": "bi-whatsapp",
        "descricao": "Conectar e acompanhar os números de WhatsApp.",
        "permissao": "owner",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    {
        "codigo": "CFG_2.1",
        "titulo": "IA — prompt",
        "rota": "/config/ia/prompt",
        "icone": "bi-robot",
        "descricao": "Versões do prompt e o que a IA pode fazer.",
        "permissao": "owner",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    {
        "codigo": "CFG_3.1",
        "titulo": "Sincronização",
        "rota": "/config/sync",
        "icone": "bi-arrow-repeat",
        "descricao": "Leitura do Harmonit: a cada 12h e sob demanda.",
        "permissao": "owner",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    {
        "codigo": "CFG_4.1",
        "titulo": "Classificações",
        "rota": "/config/classificacoes",
        "icone": "bi-tags",
        "descricao": "Motivos de fechamento de conversa.",
        "permissao": "owner",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    # 🚨 CÓDIGO NOVO, NUNCA REAPROVEITADO. `CFG_5.1` estava livre e não está
    # em CODIGOS_APOSENTADOS -- conferido antes de escrever. Reaproveitar
    # código faz o log antigo mentir.
    {
        "codigo": "CFG_5.1",
        "titulo": "Automação por tipo",
        "rota": "/config/automacao",
        "icone": "bi-robot",
        "descricao": "O que roda sozinho quando chega mensagem, por tipo de contato.",
        "permissao": "owner",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    {
        # 🚨 OS INTERRUPTORES DO SISTEMA MORAM AQUI (28/08). Ele mandou
        # conferir se todos tinham chegado à aba de Configurações, e dois não
        # tinham: `jornada_ativa` acionava em ATENDENTES, tela de cadastro, e
        # `avaliacao_ativa` não tinha acionador em tela nenhuma.
        #
        # ⚠️ `owner`: interruptor que muda o painel inteiro não é de quem
        # atende.
        "codigo": "CFG_7.1",
        "titulo": "Geral",
        "rota": "/config/geral",
        "icone": "bi-sliders",
        "descricao": "Os interruptores que valem para o painel inteiro.",
        "permissao": "owner",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    {
        # 🚨 NASCE DE UMA PERGUNTA DELE QUE DERRUBOU UM RECURSO MEU: *"quem
        # pediu esses atalhos? ou eles já são nativos do WhatsApp?"*. Ninguém
        # pediu -- `j`/`k` vêm do Gmail --, e um deles (`a`) assumia conversa
        # sem perguntar. A resposta dele foi esta tela: *"crie nas
        # configurações tela de atalhos e interruptor desligado para eles e
        # permita edição por lá também"*.
        #
        # 🔵 `owner` DESDE 24/09, decisão dele: *"pode exibir a atalhos somente
        # para o owner tbm"*. Nasceu `atendimento` ("cada pessoa edita o
        # PRÓPRIO teclado").
        #
        # 🚨 O "ENVIAR COM ENTER" NÃO SAIU JUNTO. Ele morava nesta mesma
        # permissão, e a Caixa de entrada, o Chat interno e o E-mail o leem de
        # `/api/eu/atalhos`: fechar só a tela devolveria 403 aos atendentes, as
        # três telas cairiam no desligado em silêncio e a decisão de 22/09
        # (Enter ligado para todos) morreria sem ninguém ver. Ler as próprias
        # preferências e gravar o Enter passaram a `get_usuario`, como foto e
        # estado; ligar atalhos e trocar teclas continuam presos a esta tela.
        "codigo": "CFG_6.1",
        "titulo": "Atalhos de teclado",
        "rota": "/config/atalhos",
        "icone": "bi-keyboard",
        "descricao": "As teclas de cada tela. Nascem desligadas.",
        "permissao": "owner",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    {
        # 🟡 S13, 15/09: a rota `/api/webhook/eventos` existia desde o começo
        # e só era alcançável por `curl`. Foi ela que achou, em 27/08, o
        # `listMessage` e o `listResponseMessage` que nenhuma consulta tinha
        # visto -- um deles era uma pessoa respondendo a um menu.
        "codigo": "CFG_8.1",
        "titulo": "Eventos do WhatsApp",
        "rota": "/config/eventos",
        "icone": "bi-broadcast",
        "descricao": "O que o WhatsApp mandou, cru. Para ver formato novo.",
        "permissao": "owner",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    {
        "codigo": "CFG_9.1",
        "titulo": "Registro de telas",
        "rota": "/config/telas",
        "icone": "bi-list-check",
        "descricao": "Este registro, para conferência e auditoria.",
        "permissao": "owner",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    {
        # 🔵 Pedido dele em 17/09: *"central de perfil 'minha conta' para foto
        # de usuario, dados de perfil, tipo de envio 'entrer ou clique'"*. O
        # status é 🟢 pedido do Rodrigo, trazido em 15/09.
        #
        # 🚨 O `atendente.estado` JÁ EXISTIA desde a 001, com três valores, e
        # não chegava a tela nenhuma -- por isso ele lembrava do status e não
        # o via. A 044 acrescentou o quarto (`offline`) e esta tela é o
        # produto que faltava em cima da coluna.
        #
        # ⚠️ `atendimento` e não `owner`: cada um mexe em SI MESMO. Era a mesma
        # razão da CFG_6.1 até 24/09, e é o contrário do que vale para as telas de
        # cadastro, onde se edita a ficha dos outros.
        "codigo": "CFG_10.1",
        "titulo": "Minha conta",
        "rota": "/config/minha-conta",
        "icone": "bi-person-circle",
        "descricao": "Sua foto, seus dados, como você envia e como você está.",
        "permissao": "atendimento",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    {
        # 🔵 24/09: *"o sistema de notificações ficara em configuração, cada um
        # poderá ajustar o seu tom, volume - com minimo de 1 (1 até 5), pisca
        # aba obrigatoriamente"*. `atendimento` pela razão da Minha conta: cada
        # um mexe no SEU tom. O liga/desliga por pessoa é do owner e mora na
        # mesma tela, num bloco que só ele vê -- a trava está na rota.
        "codigo": "CFG_11.1",
        "titulo": "Notificações",
        "rota": "/config/notificacoes",
        "icone": "bi-bell",
        "descricao": "O som, a aba piscando e o aviso no canto da tela quando chega mensagem numa conversa sua.",
        "permissao": "atendimento",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    {
        # 🔵 25/09 (Plano 3): *"pode criar uma aba disso nas configurações ...
        # Owner e admin criam as do tipo 'Padrões'; outra aba é 'Minhas Notas'
        # onde ela pode criar as notas dela"*, e *"Formulários"* (links).
        # `atendimento` pela razão da Minha conta: cada um mexe nas SUAS notas
        # -- e sem isso seria a porta trancada de 28/08. Quem escreve Padrões e
        # Formulários (owner e admin) é conferido na rota.
        "codigo": "CFG_12.1",
        "titulo": "Mensagens rápidas",
        "rota": "/config/mensagens-rapidas",
        "icone": "bi-lightning",
        "descricao": "Textos prontos para a conversa: padrões da equipe, suas notas e formulários.",
        "permissao": "atendimento",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    {
        # 🚨 SUBIU PARA FASE 1 EM 07/08. Decisão do usuário: "o informativo é o
        # que vai enviar, sem resposta de cliente". O canal foi pareado no
        # mesmo dia e já entrega (TESTE BOT com DELIVERY_ACK em 2s).
        #
        # ⚠️ É a única tela do sistema que ALCANÇA CLIENTE DE VERDADE em lote.
        # O canal é irreversível: mensagem enviada não volta.
        "codigo": "ATD_3.1",
        "titulo": "Informativos",
        "rota": "/informativos",
        "icone": "bi-megaphone",
        "descricao": "Disparo de boleto e aviso, com ritmo e teto por hora.",
        "grupo": "Atendimento",
        "permissao": "informativos",
        "fase": 1,
    },
    # ---- reservados: código já ocupado, tela ainda não existe ----
    {
        "codigo": "ATD_6.1",
        "titulo": "Chat interno",
        "rota": "/chat",
        "icone": "bi-chat-left-dots",
        # ⚠️ "entre atendentes" e não "com cliente" -- a descrição aparece na
        # CFG_9.1 e é o que distingue esta tela da caixa de entrada.
        "descricao": "Conversa entre atendentes. Não sai para o cliente.",
        "grupo": "Atendimento",
        "permissao": "atendimento",
        "fase": 1,
    },
    {
        "codigo": "CFG_2.2",
        "titulo": "IA — analytics",
        "rota": "/config/ia/analytics",
        "icone": "bi-graph-up",
        "descricao": "Custo, resolução sem humano e o que ela não soube.",
        # 12/08: era "admin". O perfil saiu do vocabulário -- ver PERFIS.
        "permissao": "owner",
        "fase": 2,
    },
    # ---- LIG: ligações do MicroSIP ----
    {
        # 🔵 15/10: *"considere que vamos precisar de uma aba nova no Movizap
        # para 'Ligações' - a idéia é um grid simples que tenha as ligações do
        # historico do MicroSip, consultadas por cliente - ja da base Movizap,
        # ou por Atendente, ou por data ou por numero, etc"*.
        #
        # 🚨 NASCEU SÓ DO OWNER E DUROU UM DIA. Em 15/10, poucas horas depois:
        # *"pode exibir a aba para todos"*. Virou permissão `atendimento` em
        # vez de permissão própria concedida a cada perfil, porque é isso que
        # o `test_admin_ve_exatamente_o_que_ele_decidiu` prevê ("tela nova de
        # atendimento entra sozinha -- é a permissão"): o conjunto fechado do
        # admin, que guarda a frase dele de 24/09, continua intacto.
        #
        # ⚠️ Fica de fora o perfil `cadastro` (só CAD_1.1/CAD_1.2). Se for para
        # lá também, volta a ser permissão própria, concedida perfil a perfil.
        #
        # 🚨 Todo atendente passa a poder OUVIR, BAIXAR e EXPORTAR. O rastro de
        # `ligacao_exportacao` deixa de ser detalhe: é a única resposta para
        # "quem levou o quê".
        #
        # ⚠️ Módulo novo (LIG). Até 21/10 o menu tirava o nome do grupo do
        # prefixo, e `LIG` precisava estar no mapa do `MenuLateral` para não
        # aparecer cru. 🔵 Em 19/10 ele pediu Ligações DENTRO de Atendimento:
        # por isso esta tela leva `grupo` explícito abaixo, e o prefixo `LIG`
        # sobrou só como fallback em `GRUPO_PELO_PREFIXO`.
        "codigo": "LIG_1.1",
        "titulo": "Ligações",
        "rota": "/ligacoes",
        "icone": "bi-telephone",
        "descricao": "Ligações do MicroSIP: por cliente, atendente, data ou número.",
        "grupo": "Atendimento",
        "permissao": "atendimento",
        "fase": 1,
    },
    # ---- ATD_7.1: a tela de Agendamentos (21/10) ----
    {
        # 🔵 Decisão 14 dele (19/10): **Agendamentos é TELA**, em Atendimento,
        # **aberta a todo atendente** -- por isso `atendimento`, e não
        # permissão própria concedida perfil a perfil.
        #
        # 🚨 ISTO NÃO É O `agenda.py`. Aquele é a agenda do Google que alimenta
        # a tela Início, e o topo dele diz desde que nasceu que **não é um
        # calendário** -- virar calendário faria a Início deixar de ser "o que
        # precisa de você". O calendário é esta tela.
        #
        # ⚠️ Código conferido contra `CODIGOS_APOSENTADOS` (só `ATD_4.1`).
        "codigo": "ATD_7.1",
        "titulo": "Agendamentos",
        "rota": "/agendamentos",
        "icone": "bi-calendar-check",
        "descricao": "Os serviços agendados: semana, grid e as ações de cada compromisso.",
        "permissao": "atendimento",
        "grupo": "Atendimento",
        "fase": 1,
    },
    # ---- CFG_13.1: a numeração do orçamento (21/10) ----
    {
        # 🔵 Decisão 9 dele: numeração própria do orçamento, com **aba de
        # configuração exclusiva do owner**.
        #
        # ⚠️ `aba_de` -> não vira item de menu, e é assim que as outras CFG_*
        # funcionam: a casca é o `/config`, e cada aba tem a permissão dela.
        "codigo": "CFG_13.1",
        "titulo": "Orçamento",
        "rota": "/config/orcamento",
        "icone": "bi-receipt",
        "descricao": "O próximo número de orçamento a ser emitido.",
        "permissao": "owner",
        "grupo": "Configuração",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    # ---- CFG_14.1: o vinculo dos tecnicos (21/10) ----
    {
        # 🟡 Ponta 4 do plano: a rota `/api/tecnicos-harmonit/pendencias`
        # entrou no ar em 21/10 **sem tela nenhuma** -- porta trancada, o
        # defeito que a casa já catalogou. A alternativa honesta era tirar
        # a rota.
        #
        # 🚨 SÓ LEITURA. Ela mostra os três buracos de cadastro; não
        # conserta nada. 🔵 A conclusão é dele, de 21/10: *"nenhuma regra
        # resolve -- é trabalho de cadastro"*. Quem vincula à mão é a ficha
        # do contato, na conversa.
        #
        # ⚠️ `aba_de` -> não vira item de menu: a casca é o `/config`, como
        # em todas as CFG_*.
        #
        # ⚠️ Código conferido contra `CODIGOS_APOSENTADOS` (só `ATD_4.1`).
        "codigo": "CFG_14.1",
        "titulo": "Vínculo dos técnicos",
        "rota": "/config/vinculo-tecnicos",
        "icone": "bi-person-vcard",
        "descricao": "O que falta para o agendamento achar o técnico na OS do Harmonit.",
        "permissao": "owner",
        "grupo": "Configuração",
        "fase": 1,
        "aba_de": "CFG_0.1",
    },
    {
        "codigo": "REL_1.1",
        "titulo": "Relatórios",
        "rota": "/relatorios",
        "icone": "bi-file-earmark-bar-graph",
        "descricao": "Volume, tempo de resposta, desfecho.",
        # 12/08: era "admin". O perfil saiu do vocabulário -- ver PERFIS.
        "permissao": "owner",
        "fase": 3,
    },
]

FASE_ATUAL = 1

# Perfis são conjuntos de permissão, e permissão só existe se alguma tela a usa.
# 🚨 `admin` SAIU EM 12/08, e o que ele destravava era NADA. Como permissão,
# aparecia em duas telas -- CFG_2.2 (Fase 2) e REL_1.1 (Fase 3) --, nenhuma das
# quais existe. Como perfil, dava `atendimento` + `cadastro` e mais o `admin`
# que não abria nada: o alcance real era idêntico a ter os dois outros. A doc,
# enquanto isso, prometia que um admin configuraria Canais e Sincronização --
# e o código nunca permitiu, porque `pode_acessar` recusa tela `owner` a quem
# não é owner. Ninguém usava: 1 owner e 3 atendimento na base.
#
# Decisão do usuário: **owner é o único administrador, e não nascem mais
# owners.** As duas telas futuras viraram `owner` e o CHECK de
# `atendente.perfil` perdeu o valor (migração 024).
#
# ⚠️ Perfil desconhecido devolve conjunto VAZIO, que é menu vazio. Se sobrasse
# alguém com `perfil = 'admin'`, ele perderia tudo em silêncio -- por isso a
# migração recusa rodar se existir linha assim, em vez de converter no escuro.
#
# 🔵 `admin` VOLTOU EM 24/09, com alcance novo e decidido por ele: *"o perfil
# admin deve possuir exibição de telas de atendimento + Times + Atendentes +
# Configurações > Minha conta, apenas"*. Não é mais o admin de 12/08: agora
# destrava uma permissão que existe (`equipe`, Times e Atendentes) e nada de
# `cadastro`. O owner continua único (migração 051). Minha conta já vem com
# `atendimento`, e as outras abas do /config são `owner`.
PERFIS = {
    "owner": None,  # None = tudo, inclusive o que é só do owner
    "admin": {"atendimento", "equipe"},
    "atendimento": {"atendimento"},
    "cadastro": {"cadastro"},
}

# 🚨 CÓDIGO APOSENTADO NUNCA VOLTA. Esta lista existe para ninguém
# "redescobrir" um número livre daqui a três meses e fazer o log antigo mentir.
#
#   ATD_4.1  reservado para e-mail na fase 2, quando e-mail seria mais um canal
#            de atendimento. Aposentado em 10/08: decisão do usuário de que
#            e-mail JAMAIS se mistura com WhatsApp -- virou EML_1.1, módulo
#            próprio. A tela nunca existiu, então nada foi logado com ele.
CODIGOS_APOSENTADOS = {"ATD_4.1"}

CODIGOS_VALIDOS = {t["codigo"] for t in TELAS}
PERMISSOES_VALIDAS = {t["permissao"] for t in TELAS}

# ---------------------------------------------------------------------------
# Agrupamento do menu -- APRESENTAÇÃO, não permissão.
#
# 🚨 ATÉ 21/10 O GRUPO SAÍA DO PREFIXO DO CÓDIGO, dentro do `MenuLateral.vue`.
# Era isso que tornava impossível pôr "Ligações" dentro de Atendimento sem
# mudar o código da tela -- e código é imutável por regra deste registro.
# Agora o grupo é DADO da tela, e o prefixo virou só o fallback.
#
# ⚠️ O FALLBACK É OBRIGATÓRIO. Tela sem `grupo` continua caindo onde caía
# ontem; sem ele, toda tela que esta entrega não tocou mudaria de lugar, e
# rótulo que sai do lugar é regressão.
GRUPO_PELO_PREFIXO = {
    "ATD": "Atendimento",
    "CAD": "Cadastro",
    "CFG": "Configuração",
    "EML": "E-mail",
    "INI": "Início",
    "LIG": "Ligações",
    "REL": "Relatórios",
}

# Os grupos que EXISTEM, e os subgrupos de cada um.
#
# 🔵 19/10, decisão dele: o menu abre em "grupos e subgrupos", e
# **Painéis › Operacional nasce vazio** -- o grupo é criado aqui e só aparece
# na tela quando tiver a primeira tela dentro. É o `MenuLateral` que não
# desenha grupo sem item visível; esta lista só declara que ele existe.
#
# ⚠️ A ORDEM NA TELA NÃO SAI DAQUI, e sim da ordem de `TELAS` -- o menu
# preserva a ordem em que o backend manda, e `INI_1.1` é a primeira da lista
# de propósito (a rota `/` redireciona para `sessao.telas[0].rota`). Esta
# lista é a declaração do que existe; quem ordena é o registro acima.
GRUPOS = {
    "Início": [],
    "E-mail": [],
    "Atendimento": [],
    "Cadastro": [],
    "Configuração": [],
    "Relatórios": [],
    "Painéis": ["Operacional"],
}


def grupo_da(tela: dict) -> str:
    """O grupo de menu desta tela. Sem `grupo` gravado, vale o prefixo."""
    prefixo = tela["codigo"].split("_")[0]
    return tela.get("grupo") or GRUPO_PELO_PREFIXO.get(prefixo, prefixo)


class CodigoDeTelaInvalido(Exception):
    """Levantada quando uma rota referencia um código que não existe.

    É erro de programação, não de uso: por isso estoura em vez de degradar.
    """


def por_codigo(codigo: str) -> dict:
    for t in TELAS:
        if t["codigo"] == codigo:
            return t
    raise CodigoDeTelaInvalido(
        f"{codigo!r} não está no registro. Tela sem código registrado não sobe -- "
        f"ver docs/03_Registro_Telas.md"
    )


def ativas() -> list[dict]:
    """Só as telas da fase atual. As reservadas existem, mas não sobem."""
    return [t for t in TELAS if t["fase"] <= FASE_ATUAL]


def pode_acessar(usuario: dict, codigo: str) -> bool:
    if usuario.get("owner"):
        return True
    tela = por_codigo(codigo)
    if tela["permissao"] == "owner":
        return False
    return tela["permissao"] in set(usuario.get("permissoes") or [])


def do_usuario(usuario: dict) -> list[dict]:
    """As telas que ESTE usuário vê. Owner vê tudo que está ativo.

    🚨 ESTA FUNÇÃO MONTA A RESPOSTA À MÃO, e é por isso que o `aba_de` precisa
    estar listado aqui. Sem esta linha ele fica no registro e nunca chega ao
    frontend: o menu continuaria mostrando as seis telas de configuração, a
    suíte continuaria verde, e ninguém descobriria. Achado validando antes de
    escrever, em 27/08.

    ⚠️ ELA CONTINUA DEVOLVENDO AS TELAS-ABA. Tem de continuar: a guarda de rota
    do frontend usa `sessao.telas` para saber o que este usuário pode abrir --
    tirá-las daqui barraria `/config/canais`. Quem não desenha item de menu
    para elas é o `MenuLateral`, e a decisão é de APRESENTAÇÃO, não permissão.
    """
    return [
        {
            "codigo": t["codigo"],
            "titulo": t["titulo"],
            "rota": t["rota"],
            "icone": t["icone"],
            "aba_de": t.get("aba_de"),
            # 21/10: o menu deixou de deduzir o grupo do prefixo. Vale a mesma
            # advertência do `aba_de` acima -- campo que não entra nesta
            # montagem à mão fica no registro e nunca chega à tela.
            "grupo": grupo_da(t),
            "subgrupo": t.get("subgrupo"),
        }
        for t in ativas()
        if pode_acessar(usuario, t["codigo"])
    ]


def permissoes_do_perfil(perfil: str) -> set[str]:
    if perfil not in PERFIS:
        return set()
    concedidas = PERFIS[perfil]
    if concedidas is None:
        return set(PERMISSOES_VALIDAS)
    return set(concedidas)
