"""Tela inicial — o que precisa de gente AGORA, e nada além disso.

🚨 A RÉGUA: se o número está em zero e isso é bom, ele encolhe. O que cresce
na tela é o que está esperando alguém. Contador de volume ("1.482 mensagens
processadas") é relatório, não painel de trabalho -- e relatório tem código
próprio reservado (REL_1.1).

⚠️ Cada número devolve junto a ROTA que o resolve. Número sem para onde ir
vira enfeite: quem olha não tem o que fazer com ele.
"""
from . import banco


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


def resumo(atendente_id: int | None = None) -> dict:
    """O estado do dia, em uma consulta por pergunta.

    `atendente_id` separa "esperando VOCÊ" de "esperando alguém" -- são ações
    diferentes: uma é sua, a outra é da equipe.
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

    return {
        # Cada item traz `rota`: número que não leva a lugar nenhum é enfeite.
        "atencao": [
            {"chave": "em_aberto", "rotulo": "conversas em aberto",
             "valor": filas["em_aberto"], "rota": "/atendimento",
             "nota": "nenhuma tem dono" if filas["em_aberto"]
                     and filas["sem_dono"] == filas["em_aberto"] else None},
            {"chave": "minhas", "rotulo": "esperando sua resposta",
             "valor": filas["minhas"], "rota": "/atendimento"},
            {"chave": "adiadas", "rotulo": "adiadas que venceram",
             "valor": filas["adiadas_vencidas"], "rota": "/atendimento/fila"},
        ],
        "canais": _canais(),
        "saude": {
            "pendentes": fila_tecnica["pendentes"],
            "com_erro": fila_tecnica["com_erro"],
            "sync": ultimo_sync,
        },
        "alcance": alcance,
    }
