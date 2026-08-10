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
    {
        "codigo": "CFG_1.1",
        "titulo": "Canais",
        "rota": "/config/canais",
        "icone": "bi-whatsapp",
        "descricao": "Conectar e acompanhar os números de WhatsApp.",
        "permissao": "owner",
        "fase": 1,
    },
    {
        "codigo": "CFG_2.1",
        "titulo": "IA — prompt",
        "rota": "/config/ia/prompt",
        "icone": "bi-robot",
        "descricao": "Versões do prompt e o que a IA pode fazer.",
        "permissao": "owner",
        "fase": 1,
    },
    {
        "codigo": "CFG_3.1",
        "titulo": "Sincronização",
        "rota": "/config/sync",
        "icone": "bi-arrow-repeat",
        "descricao": "Leitura do Harmonit: a cada 12h e sob demanda.",
        "permissao": "owner",
        "fase": 1,
    },
    {
        "codigo": "CFG_4.1",
        "titulo": "Classificações",
        "rota": "/config/classificacoes",
        "icone": "bi-tags",
        "descricao": "Motivos de fechamento de conversa.",
        "permissao": "owner",
        "fase": 1,
    },
    {
        "codigo": "CFG_9.1",
        "titulo": "Registro de telas",
        "rota": "/config/telas",
        "icone": "bi-list-check",
        "descricao": "Este registro, para conferência e auditoria.",
        "permissao": "owner",
        "fase": 1,
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
        "codigo": "CFG_2.2",
        "titulo": "IA — analytics",
        "rota": "/config/ia/analytics",
        "icone": "bi-graph-up",
        "descricao": "Custo, resolução sem humano e o que ela não soube.",
        "permissao": "admin",
        "fase": 2,
    },
    {
        "codigo": "REL_1.1",
        "titulo": "Relatórios",
        "rota": "/relatorios",
        "icone": "bi-file-earmark-bar-graph",
        "descricao": "Volume, tempo de resposta, desfecho.",
        "permissao": "admin",
        "fase": 3,
    },
]

FASE_ATUAL = 1

# Perfis são conjuntos de permissão, e permissão só existe se alguma tela a usa.
PERFIS = {
    "owner": None,  # None = tudo, inclusive o que é só do owner
    "admin": {"admin", "atendimento", "cadastro"},
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
    """As telas que ESTE usuário vê no menu. Owner vê tudo que está ativo."""
    return [
        {
            "codigo": t["codigo"],
            "titulo": t["titulo"],
            "rota": t["rota"],
            "icone": t["icone"],
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
