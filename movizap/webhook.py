"""Recebimento do webhook do Evolution — só grava, não interpreta.

🚨 ESTA É A METADE QUE VEM ANTES DO PAREAMENTO, DE PROPÓSITO.

Todo parser deste projeto foi escrito contra a DOCUMENTAÇÃO do Evolution
2.3.7, não contra o que ele de fato manda. Guardar o corpo inteiro, cru, antes
de qualquer interpretação, é o que permite conferir o formato real com UMA
mensagem — em vez de descobrir a divergência com catorze telas construídas em
cima de uma suposição.

É a mitigação escrita do risco de parear o chip por último
(`Proximos_Passos.md`, e `01_Escopo_Fase_1.md`).

AS REGRAS DA CASA (metodologia §1, "a regra número um deste projeto"):

  🚨 **Responder 200 rápido, processar depois.** Se o processamento demorar, o
  Evolution considera falha e reenvia — e o problema piora sozinho. Aqui a
  requisição faz um INSERT e volta. Máquina de estados, conversa e IA são
  outro passo, lendo desta tabela.

  🚨 **Idempotência é do banco, não da disciplina.** `ux_webhook_externo` faz
  da reentrega um conflito esperado: ignora e responde 200. **Nunca deduplicar
  por conteúdo ou timestamp** — o cliente manda "ok" duas vezes de propósito,
  e isso é legítimo.

  🚨 **Fora de ordem é normal.** A ordenação de tela é por hora do provedor,
  não por ordem de chegada.

  ⚠️ **Campo desconhecido não derruba nada.** O que não for reconhecido fica
  no `payload` e vira consulta depois. Estourar aqui perderia a mensagem que
  este módulo existe para não perder.

O CANAL INFORMATIVO

  Decisão do usuário em 06/08: "somente o canal Atendimento terá IA, o
  informativo nem recebe mensagem". Mas gente **responde boleto** — a mensagem
  vai chegar de qualquer jeito. Ela é gravada aqui e marcada como processada,
  sem virar conversa e sem acionar IA: honra o "não recebe" sem jogar fora o
  que chegou.
"""
import json
import logging

from . import banco, telefone

log = logging.getLogger("movizap.webhook")

# Eventos que trazem mensagem. O resto (conexão, presença, contatos) é
# gravado igual, mas não tem id de mensagem para deduplicar.
EVENTOS_DE_MENSAGEM = {"messages.upsert", "messages.update", "send.message"}


def _cavar(corpo: dict, *caminho, padrao=None):
    """Desce por um caminho de chaves sem estourar em nenhum nível.

    O payload do Evolution aninha fundo e nem todo evento traz todo nível.
    `corpo["data"]["key"]["id"]` estoura em três lugares diferentes.
    """
    atual = corpo
    for chave in caminho:
        if not isinstance(atual, dict):
            return padrao
        atual = atual.get(chave)
    return padrao if atual is None else atual


def _canal_da_instancia(instancia: str) -> dict | None:
    return banco.um("SELECT id, tipo, ia_ligada FROM canal WHERE instancia = %s",
                    (instancia,))


def registrar(corpo: dict) -> dict:
    """Grava o evento cru. Devolve o que o endpoint responde -- rápido.

    Nunca levanta por causa do conteúdo: qualquer coisa que chegue é gravada,
    porque o que não dá para interpretar hoje é justamente o que interessa
    conferir depois.
    """
    if not isinstance(corpo, dict):
        corpo = {"corpo_nao_era_objeto": repr(corpo)[:2000]}

    instancia = _cavar(corpo, "instance") or _cavar(corpo, "instanceName") or ""
    evento = _cavar(corpo, "event") or ""

    id_externo = _cavar(corpo, "data", "key", "id")
    jid = _cavar(corpo, "data", "key", "remoteJid") or ""
    de_mim = _cavar(corpo, "data", "key", "fromMe")

    # O JID vem como `5518998116168@s.whatsapp.net`. O normalizador já trata,
    # e é por ele que a busca vai casar com o cadastro.
    numero = telefone.normalizar(jid) if jid else None

    canal = _canal_da_instancia(instancia) if instancia else None

    # 🚨 Grupo tem `@g.us` e a Fase 1 não atende grupo. Grava e marca
    # processado, para não ficar numa fila que ninguém vai consumir.
    e_grupo = "@g.us" in jid
    informativo = bool(canal and canal["tipo"] == "informativo")
    ignorar = e_grupo or informativo

    linha = banco.um(
        """
        INSERT INTO webhook_evento
            (canal_id, instancia, evento, id_externo, de_mim, telefone,
             payload, processado, processado_em, erro)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                CASE WHEN %s THEN now() ELSE NULL END, %s)
        ON CONFLICT (instancia, id_externo) WHERE id_externo IS NOT NULL
        DO NOTHING
        RETURNING id
        """,
        (
            canal["id"] if canal else None,
            instancia or None,
            evento or None,
            id_externo,
            de_mim,
            numero,
            json.dumps(corpo, ensure_ascii=False, default=str),
            ignorar,
            ignorar,
            "grupo: fora da Fase 1" if e_grupo else
            ("canal informativo: não vira conversa" if informativo else None),
        ),
    )

    if linha is None:
        # Reentrega. Conflito ESPERADO -- não é erro, e o Evolution só precisa
        # do 200 para parar de reenviar.
        log.info("reentrega ignorada: %s / %s", instancia, id_externo)
        return {"ok": True, "repetido": True}

    log.info("webhook %s: %s de %s%s", linha["id"], evento or "?",
             numero or jid or "?", " (ignorado)" if ignorar else "")
    return {"ok": True, "id": linha["id"], "ignorado": ignorar}


# ── Consulta, para conferir o formato real depois do pareamento ────────────

def ultimos(limite: int = 20) -> list[dict]:
    return banco.varios(
        """SELECT id, canal_id, instancia, evento, id_externo, de_mim,
                  telefone, recebido_em, processado, erro
             FROM webhook_evento ORDER BY recebido_em DESC LIMIT %s""",
        (limite,))


def payload(evento_id: int) -> dict | None:
    """O corpo cru de um evento. É o que se lê depois da primeira mensagem
    real para conferir se o formato bate com o que os parsers supõem."""
    return banco.um("SELECT * FROM webhook_evento WHERE id = %s", (evento_id,))


def resumo() -> dict:
    return banco.um("""
        SELECT count(*)                                        AS total,
               count(*) FILTER (WHERE NOT processado)          AS pendentes,
               count(*) FILTER (WHERE erro IS NOT NULL)        AS ignorados,
               count(DISTINCT telefone)                        AS telefones,
               max(recebido_em)                                AS ultimo
          FROM webhook_evento
    """)
