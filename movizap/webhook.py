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

# 🚨 MEDIDO EM 07/08, NA PRIMEIRA MENSAGEM REAL: o Evolution manda a PRÓPRIA
# CHAVE DE API dentro do corpo, em `apikey` — nos 70 primeiros eventos, todos.
# "Gravar cru" não pode significar guardar credencial: a chave que comanda o
# canal ficaria no banco, nos backups e em qualquer exportação, para sempre.
#
# ⚠️ O campo é trocado por um marcador em vez de sumir. Campo ausente e campo
# omitido de propósito são coisas diferentes na hora de conferir o formato, e
# a conferência é a razão de esta tabela existir.
CAMPOS_SIGILOSOS = ("apikey",)
MARCADOR = "[removido pelo MoviZap -- credencial nao se guarda]"


def _sem_segredo(corpo: dict) -> dict:
    """Devolve o corpo sem as credenciais que o Evolution embute nele.

    Só no topo, de propósito: descer recursivamente em payload arbitrário é
    caro por mensagem e o Evolution põe a chave num lugar só. Se aparecer em
    outro nível, o teste `teste_webhook` acusa.
    """
    if not any(c in corpo for c in CAMPOS_SIGILOSOS):
        return corpo
    limpo = dict(corpo)
    for campo in CAMPOS_SIGILOSOS:
        if campo in limpo:
            limpo[campo] = MARCADOR
    return limpo


def _jid_do_cliente(chave: dict) -> str:
    """O JID que É um telefone.

    🚨 MEDIDO EM 07/08: as mensagens vieram com `addressingMode: "lid"`, que
    não existe na documentação do 2.3.7 contra a qual este parser foi escrito.
    No modo LID o WhatsApp identifica a pessoa por um número interno
    (`...@lid`) que NÃO é telefone — e o telefone vem no `remoteJidAlt`.

    Nos 7 primeiros casos o `remoteJid` ainda veio como `@s.whatsapp.net`, mas
    tratar isto agora é barato; descobrir depois seria uma conversa ligada ao
    contato errado, em silêncio.
    """
    if not isinstance(chave, dict):
        return ""
    principal = chave.get("remoteJid") or ""
    alternativo = chave.get("remoteJidAlt") or ""
    if principal.endswith("@lid") and alternativo:
        return alternativo
    return principal or alternativo


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
    jid = _jid_do_cliente(_cavar(corpo, "data", "key", padrao={}))
    de_mim = _cavar(corpo, "data", "key", "fromMe")

    # O JID vem como `5518998116168@s.whatsapp.net`. O normalizador já trata,
    # e é por ele que a busca vai casar com o cadastro.
    # ⚠️ `@lid` nunca chega aqui: `_jid_do_cliente` já trocou pelo telefone.
    numero = telefone.normalizar(jid) if jid else None

    canal = _canal_da_instancia(instancia) if instancia else None

    # 🚨 GRUPO DEIXOU DE SER DESCARTADO EM 12/08 (migração 027). O `@g.us` não
    # é telefone -- `numero` fica nulo e a identidade da conversa passa a ser o
    # próprio JID. O que impede a enxurrada não é mais descartar: é o grupo
    # nascer com `atender = false`, fora da caixa de entrada.
    #
    # ⚠️ O CANAL INFORMATIVO CONTINUA DESCARTANDO GRUPO E TUDO MAIS. Ele é
    # disparo, não conversa -- e um grupo virando atendimento ali seria
    # resposta num canal que ninguém lê.
    informativo = bool(canal and canal["tipo"] == "informativo")
    ignorar = informativo

    linha = banco.um(
        """
        INSERT INTO webhook_evento
            (canal_id, instancia, evento, id_externo, de_mim, telefone,
             payload, processado, processado_em, motivo_ignorado)
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
            json.dumps(_sem_segredo(corpo), ensure_ascii=False, default=str),
            ignorar,
            ignorar,
            # 🚨 VAI EM `motivo_ignorado`, NÃO EM `erro`. Descartar de propósito
            # não é falhar. Enquanto isto morava no campo `erro`, o painel
            # acusava 16 falhas num sistema em que nada falhou -- e alarme
            # falso é o que faz alguém parar de olhar o painel. Corrigido na
            # migração 009. É a mesma lição do `ok`/`vazio`/`erro` do sync,
            # cometida de novo em outro lugar.
            "canal informativo: não vira conversa" if informativo else None,
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
