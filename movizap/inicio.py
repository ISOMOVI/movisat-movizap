"""Tela inicial — o que precisa de gente AGORA, e o desfecho de quem já atendeu.

🚨 A RÉGUA, E O QUE MUDOU EM 25/08. A régua original era "aqui não entra número
de volume, isso é relatório". Ela continua valendo para VOLUME -- "1.482
mensagens processadas" não diz o que fazer e não entra. O que passou a entrar,
por decisão do usuário, é **desfecho**: quantos atendimentos foram concluídos,
por mim e pela equipe, no período. Desfecho não é volume: é o outro lado do que
está aberto, e é o que faz a tela ser um mini-CRM de atendimento em vez de uma
lista de pendência.

⚠️ Continua sem gráfico e sem tabela. Número, período, e a rota que o abre.

⚠️ Cada número devolve junto a ROTA que o resolve. Número sem para onde ir
vira enfeite: quem olha não tem o que fazer com ele.

🚨 O QUE É DO OWNER NÃO SAI DAQUI PARA OUTRO PERFIL. Canais, saúde da fila
técnica e alcance do cadastro só entram no JSON quando quem pede é owner --
CFG_1.1 é tela de owner, e até 25/08 esta rota entregava a mesma informação
para qualquer perfil pela porta da frente. Esconder na tela não resolveria:
o JSON continuaria respondendo a quem soubesse pedir.
"""
from . import banco

# Os períodos do cartão de desfecho, na ordem em que a tela os oferece. Os
# cortes correspondentes estão escritos dentro da consulta de `_desfecho`.
PERIODOS = ("hoje", "semana", "mes")


def _canais() -> list[dict]:
    """Os canais e o último estado que o vigia registrou.

    ⚠️ `canal_evento` é histórico: interessa a última linha de cada canal, não
    a contagem. Sem o DISTINCT ON o canal apareceria uma vez por evento.
    """
    return banco.varios(
        """
        SELECT c.id, c.nome, c.tipo, c.ia_ligada,
               e.estado, e.em AS desde
          FROM canal c
          LEFT JOIN LATERAL (
                SELECT estado, em FROM canal_evento ce
                 WHERE ce.canal_id = c.id
                 ORDER BY ce.em DESC LIMIT 1
          ) e ON true
         ORDER BY c.tipo DESC, c.nome
        """)


def _desfecho(atendente_id: int | None) -> dict:
    """Atendimentos concluídos, por período, meus e da equipe.

    🚨 LÊ `resolvida_por`, NÃO `atendente_id`. Concluir solta o dono desde
    25/08 (migração 029) -- contar por `atendente_id` daria zero em toda
    conversa concluída, que é exatamente o número que este cartão existe para
    mostrar.

    ⚠️ As conversas fechadas ANTES da 029 têm `resolvida_por` nulo: não dá
    para saber quem as concluiu, e chutar o dono seria inventar. Elas contam
    para a equipe e para ninguém em particular -- e a tela diz isso.
    """
    # ⚠️ Os cortes de período são ESCRITOS, não montados. A casa não concatena
    # nada em SQL -- nem valor interno, nem expressão "que eu mesmo escrevi".
    # Três períodos cabem em três pares de FILTER, e o que se lê é o que roda.
    linha = banco.um(
        """SELECT
             count(*) FILTER (WHERE resolvida_em >= date_trunc('day', now()))
                                                                AS equipe_hoje,
             count(*) FILTER (WHERE resolvida_em >= now() - interval '7 days')
                                                                AS equipe_semana,
             count(*) FILTER (WHERE resolvida_em >= now() - interval '30 days')
                                                                AS equipe_mes,
             count(*) FILTER (WHERE resolvida_em >= date_trunc('day', now())
                                AND resolvida_por = %s)         AS minhas_hoje,
             count(*) FILTER (WHERE resolvida_em >= now() - interval '7 days'
                                AND resolvida_por = %s)         AS minhas_semana,
             count(*) FILTER (WHERE resolvida_em >= now() - interval '30 days'
                                AND resolvida_por = %s)         AS minhas_mes,
             count(*) FILTER (WHERE resolvida_em >= date_trunc('day', now())
                                AND resolvida_por IS NULL)      AS sem_autor_hoje
           FROM conversa
          WHERE resolvida_em IS NOT NULL""",
        (atendente_id, atendente_id, atendente_id))

    # A média só do que tem resposta: conversa que ninguém respondeu não tem
    # tempo de resposta, e entrar como zero puxaria a média para baixo dizendo
    # que a equipe é rápida justamente onde ela não atendeu.
    tempo = banco.um(
        """SELECT avg(segundos_ate_resposta)::int AS media_equipe,
                  avg(segundos_ate_resposta) FILTER (
                        WHERE resolvida_por = %s)::int AS media_minha
             FROM conversa
            WHERE segundos_ate_resposta IS NOT NULL
              AND resolvida_em >= now() - interval '30 days'""",
        (atendente_id,))

    return {
        "periodos": list(PERIODOS),
        "minhas": {p: linha[f"minhas_{p}"] for p in PERIODOS},
        "equipe": {p: linha[f"equipe_{p}"] for p in PERIODOS},
        "sem_autor_hoje": linha["sem_autor_hoje"],
        "segundos_ate_resposta": {
            "minha": tempo["media_minha"],
            "equipe": tempo["media_equipe"],
        },
    }


def _configuracao(atendente_id: int | None) -> dict | None:
    """"Como você está configurado" — só-leitura, para quem não é owner.

    🚨 EXISTE PORQUE HOJE NÃO HÁ ONDE DESCOBRIR ISSO. Quem não é owner não vê
    a CAD_2.1 nem a CAD_2.2: não tem como saber em que times está, que filas
    enxerga, ou por que uma tela não aparece no menu dele. Sem esta resposta a
    conclusão natural é "o painel está quebrado" -- e o chamado vem para cá.

    ⚠️ NADA AQUI É EDITÁVEL. Quem muda é o owner, e o texto diz isso. Mostrar
    um campo que não salva seria pior que não mostrar.
    """
    if not atendente_id:
        return None

    eu = banco.um(
        """SELECT a.nome, a.perfil, a.estado, a.fuso, a.transferivel
             FROM atendente a WHERE a.id = %s""", (atendente_id,))
    if not eu:
        return None

    # 0 = domingo no banco (`dia_semana`), e `EXTRACT(DOW)` também devolve 0
    # para domingo -- as duas contagens batem, e é por isso que não há +1 aqui.
    jornada_hoje = banco.varios(
        """SELECT inicio, fim FROM atendente_jornada
            WHERE atendente_id = %s
              AND dia_semana = EXTRACT(DOW FROM now())::int
            ORDER BY inicio""", (atendente_id,))

    dentro = banco.um(
        """SELECT EXISTS (
              SELECT 1 FROM atendente_jornada
               WHERE atendente_id = %s
                 AND dia_semana = EXTRACT(DOW FROM now())::int
                 AND now()::time BETWEEN inicio AND fim) AS dentro""",
        (atendente_id,))["dentro"]

    times = banco.varios(
        """SELECT t.nome FROM atendente_time at
             JOIN time t ON t.id = at.time_id
            WHERE at.atendente_id = %s ORDER BY t.nome""", (atendente_id,))

    # 🚨 SEM LINHA AQUI = VÊ A FILA INTEIRA. O padrão é permissivo de propósito
    # (migração 001), e a tela precisa dizer isso com todas as letras -- lista
    # vazia lida como "não vejo nada" é a leitura oposta da verdade.
    filas = banco.varios(
        """SELECT t.nome FROM atendente_time_permissao p
             JOIN time t ON t.id = p.time_id
            WHERE p.atendente_id = %s ORDER BY t.nome""", (atendente_id,))

    return {
        "perfil": eu["perfil"],
        "estado": eu["estado"],
        "fuso": eu["fuso"],
        "transferivel": eu["transferivel"],
        "jornada_hoje": [{"inicio": str(f["inicio"]), "fim": str(f["fim"])}
                         for f in jornada_hoje],
        "dentro_do_horario": dentro,
        "times": [t["nome"] for t in times],
        "filas": [f["nome"] for f in filas],
        "ve_a_fila_inteira": not filas,
    }


def resumo(atendente_id: int | None = None, owner: bool = False) -> dict:
    """O estado do dia, em uma consulta por pergunta.

    `atendente_id` separa "esperando VOCÊ" de "esperando alguém" -- são ações
    diferentes: uma é sua, a outra é da equipe.

    `owner` decide o que sequer é CONSULTADO. Não é filtro de saída: as
    consultas de canal, fila técnica e alcance nem rodam para quem não é
    owner. Consultar e depois descartar gastaria banco para esconder dado.
    """
    filas = banco.um(
        """
        SELECT
          count(*) FILTER (WHERE estado <> 'resolvida')                  AS em_aberto,
          count(*) FILTER (WHERE estado <> 'resolvida'
                             AND atendente_id IS NULL)                   AS sem_dono,
          count(*) FILTER (WHERE estado <> 'resolvida'
                             AND atendente_id = %s)                      AS minhas,
          count(*) FILTER (WHERE estado = 'adiada'
                             AND adiada_ate IS NOT NULL
                             AND adiada_ate <= now())                    AS adiadas_vencidas
          FROM conversa
        """, (atendente_id,))

    # Conversas que eu ACOMPANHO sem ser dono. Elas já aparecem na minha lista
    # desde a migração 021, e não apareciam em número nenhum -- quem foi
    # convidado para cinco conversas não tinha onde ver isso.
    acompanho = banco.um(
        """SELECT count(*) AS n
             FROM conversa_participante p
             JOIN conversa c ON c.id = p.conversa_id
            WHERE p.atendente_id = %s AND p.saiu_em IS NULL
              AND c.estado <> 'resolvida'
              AND (c.atendente_id IS DISTINCT FROM %s)""",
        (atendente_id, atendente_id))["n"] if atendente_id else 0

    resposta = {
        # ---- Faixa A: o meu dia ----
        # Cada item traz `rota`: número que não leva a lugar nenhum é enfeite.
        "meu_dia": [
            {"chave": "minhas", "rotulo": "esperando sua resposta",
             "valor": filas["minhas"], "rota": "/atendimento?minhas=1"},
            {"chave": "acompanho", "rotulo": "acompanhando",
             "valor": acompanho, "rota": "/atendimento?minhas=1"},
        ],
        # ---- Faixa B: a operação ----
        "atencao": [
            {"chave": "em_aberto", "rotulo": "conversas em aberto",
             "valor": filas["em_aberto"], "rota": "/atendimento",
             "nota": "nenhuma tem dono" if filas["em_aberto"]
                     and filas["sem_dono"] == filas["em_aberto"] else None},
            {"chave": "sem_dono", "rotulo": "sem dono",
             "valor": filas["sem_dono"], "rota": "/atendimento?sem_dono=1"},
            {"chave": "adiadas", "rotulo": "adiadas que venceram",
             "valor": filas["adiadas_vencidas"], "rota": "/atendimento/fila"},
        ],
        "desfecho": _desfecho(atendente_id),
        "owner": owner,
    }

    if not owner:
        # Quem não é owner recebe, no lugar do bloco de infraestrutura, a
        # explicação do próprio acesso.
        resposta["configuracao"] = _configuracao(atendente_id)
        return resposta

    # 🚨 `motivo_ignorado` NÃO é erro. Descartar de propósito (grupo, canal
    # informativo) é comportamento normal; misturar os dois faz o painel
    # acusar falha num sistema saudável -- foi o defeito corrigido em 07/08.
    fila_tecnica = banco.um(
        """
        SELECT count(*) FILTER (WHERE NOT processado)          AS pendentes,
               count(*) FILTER (WHERE erro IS NOT NULL)        AS com_erro
          FROM webhook_evento
        """)

    ultimo_sync = banco.um(
        """SELECT iniciado_em, origem, lidos, erros, mensagem_erro
             FROM sync_execucao ORDER BY id DESC LIMIT 1""")

    alcance = banco.um(
        """
        SELECT (SELECT count(*) FROM cliente WHERE ativo)              AS clientes,
               (SELECT count(*) FROM contato_telefone
                 WHERE tem_whatsapp)                                   AS com_whatsapp,
               (SELECT count(*) FROM contato_telefone
                 WHERE tem_whatsapp IS NULL)                           AS nao_verificados,
               (SELECT count(*) FROM cliente WHERE ativo AND email IS NOT NULL)
                                                                       AS com_email
        """)

    resposta["canais"] = _canais()
    resposta["saude"] = {
        "pendentes": fila_tecnica["pendentes"],
        "com_erro": fila_tecnica["com_erro"],
        "sync": ultimo_sync,
    }
    resposta["alcance"] = alcance
    return resposta
