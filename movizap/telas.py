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
        "permissao": "atendimento",
        "fase": 1,
    },
    {
        "codigo": "ATD_1.2",
        "titulo": "Conversa",
        "rota": "/atendimento/{id}",
        "icone": "bi-chat-text",
        "descricao": "A conversa em si, com a ficha do cliente ao lado.",
        "permissao": "atendimento",
        "fase": 1,
    },
    {
        "codigo": "ATD_1.3",
        "titulo": "Fila",
        "rota": "/atendimento/fila",
        "icone": "bi-list-ol",
        "descricao": "Conversas esperando atendente.",
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
        "permissao": "cadastro",
        "fase": 1,
    },
    {
        "codigo": "CAD_1.2",
        "titulo": "Contatos",
        "rota": "/cadastro/contatos",
        "icone": "bi-person-lines-fill",
        "descricao": "Pessoas, seus telefones e papéis.",
        "permissao": "cadastro",
        "fase": 1,
    },
    {
        "codigo": "CAD_2.1",
        "titulo": "Atendentes",
        "rota": "/cadastro/atendentes",
        "icone": "bi-people",
        "descricao": "Contas do painel e o que cada uma enxerga.",
        "permissao": "owner",
        "fase": 1,
    },
    {
        "codigo": "CAD_2.2",
        "titulo": "Times",
        "rota": "/cadastro/times",
        "icone": "bi-diagram-2",
        "descricao": "Times que recebem transferência.",
        "permissao": "owner",
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
        "permissao": "owner",
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
        # ⚠️ `atendimento` e não `owner`: cada pessoa edita o PRÓPRIO teclado.
        "codigo": "CFG_6.1",
        "titulo": "Atalhos de teclado",
        "rota": "/config/atalhos",
        "icone": "bi-keyboard",
        "descricao": "As teclas de cada tela. Nascem desligadas.",
        "permissao": "atendimento",
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
PERFIS = {
    "owner": None,  # None = tudo, inclusive o que é só do owner
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
