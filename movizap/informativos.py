"""Canal informativo — o que sai daqui alcança cliente de verdade (ATD_3.1).

Decisão do usuário em 07/08: *"o informativo é o que vai enviar, sem resposta
de cliente"*.

🚨 AS QUATRO REGRAS DA METODOLOGIA §4, TRADUZIDAS EM CÓDIGO

  1. **O canal é irreversível.** Mensagem enviada não volta. Por isso nada aqui
     dispara sozinho: o disparo nasce `rascunho` e só sai por ação explícita.
  2. **Começa com 1.** `enviar_teste()` manda para UM destino e para. O resto
     fica `pendente` no banco, esperando você conferir.
  3. **Ritmo, não rajada.** `intervalo_seg` e `teto_por_hora` são colunas, não
     combinação verbal. O laço respeita os dois.
  4. **Nunca enviar para `tem_whatsapp = false`.** O público é montado só com
     quem foi verificado e existe -- NULL não entra, porque NULL é "não
     verificado", que é diferente de "não tem".

🚨 E a que veio do dado, medida em 07/08: dos 944 clientes ativos, **369 são
alcançáveis**. Os outros 575 não estão fora porque recusaram -- 483 deles estão
fora por CADASTRO INCOMPLETO (só fixo, ou telefone nenhum). A tela mostra essa
quebra: disparar para 369 achando que falou com 944 é o erro que este módulo
existe para não deixar acontecer.
"""
import logging

from . import banco

log = logging.getLogger("movizap.informativos")

TETO_CORPO = 4000


class DisparoInvalido(ValueError):
    """Vira 400 com a frase que o usuário lê."""


def cobertura() -> dict:
    """Quantos clientes o informativo alcança, e por que os outros ficam fora.

    ⚠️ As três razões de exclusão pedem AÇÕES DIFERENTES, e por isso são
    contadas separadas: "não usa WhatsApp" é fato do cliente; "só tem fixo" e
    "sem telefone" são buraco no cadastro do Harmonit, que dá para corrigir.
    """
    tem_wa = ("EXISTS (SELECT 1 FROM contato ct JOIN contato_telefone t "
              "ON t.contato_id = ct.id WHERE ct.cliente_id = cl.id AND t.tem_whatsapp)")
    tem_cel = ("EXISTS (SELECT 1 FROM contato ct JOIN contato_telefone t "
               "ON t.contato_id = ct.id WHERE ct.cliente_id = cl.id "
               "AND length(t.e164) = 14)")
    tem_qq = ("EXISTS (SELECT 1 FROM contato ct JOIN contato_telefone t "
              "ON t.contato_id = ct.id WHERE ct.cliente_id = cl.id)")

    def conta(condicao: str) -> int:
        return banco.um(f"SELECT COUNT(*) AS n FROM cliente cl "
                        f"WHERE cl.ativo AND {condicao}")["n"]

    alcancaveis = conta(tem_wa)
    sem_wa_com_cel = conta(f"NOT {tem_wa} AND {tem_cel}")
    so_fixo = conta(f"NOT {tem_wa} AND NOT {tem_cel} AND {tem_qq}")
    sem_fone = conta(f"NOT {tem_qq}")
    total = banco.um("SELECT COUNT(*) AS n FROM cliente WHERE ativo")["n"]

    return {
        "clientes_ativos": total,
        "alcancaveis": alcancaveis,
        "sem_whatsapp_com_celular": sem_wa_com_cel,
        "so_telefone_fixo": so_fixo,
        "sem_telefone": sem_fone,
        # O que dá para consertar mexendo no cadastro, não no cliente.
        "fora_por_cadastro": so_fixo + sem_fone,
        "telefones_alvo": banco.um(
            "SELECT COUNT(DISTINCT t.e164) AS n FROM contato_telefone t "
            "JOIN contato ct ON ct.id = t.contato_id "
            "JOIN cliente cl ON cl.id = ct.cliente_id "
            "WHERE cl.ativo AND t.tem_whatsapp")["n"],
    }


def publico() -> list[dict]:
    """Os destinos de um disparo para toda a base alcançável.

    🚨 `DISTINCT ON (t.e164)` -- um número que está em oito contatos recebe UMA
    vez. Sem isso, a central de uma empresa receberia o mesmo boleto oito
    vezes, e o cliente veria spam vindo de nós.
    """
    return banco.varios("""
        SELECT DISTINCT ON (t.e164)
               t.e164 AS telefone_e164, ct.id AS contato_id, cl.id AS cliente_id,
               cl.nome AS cliente_nome
          FROM contato_telefone t
          JOIN contato ct ON ct.id = t.contato_id
          JOIN cliente cl ON cl.id = ct.cliente_id
         WHERE cl.ativo AND t.tem_whatsapp
         ORDER BY t.e164, ct.id
    """)


def criar(titulo: str, corpo: str, canal_id: int | None = None,
          criado_por: int | None = None, intervalo_seg: int = 5,
          teto_por_hora: int = 200) -> dict:
    """Monta o disparo em RASCUNHO, com a lista de destinos congelada.

    ⚠️ Congelar a lista é de propósito: se o público fosse calculado na hora do
    envio, um sync do Harmonit no meio do disparo mudaria quem recebe, e
    ninguém saberia dizer depois para quem foi.
    """
    titulo = (titulo or "").strip()
    corpo = (corpo or "").strip()
    if not titulo:
        raise DisparoInvalido("Dê um título ao informativo.")
    if not corpo:
        raise DisparoInvalido("O corpo da mensagem está vazio.")
    if len(corpo) > TETO_CORPO:
        raise DisparoInvalido(f"O corpo passa de {TETO_CORPO} caracteres.")

    if canal_id is None:
        canal = banco.um("SELECT id FROM canal WHERE tipo = 'informativo' AND ativo")
        if not canal:
            raise DisparoInvalido("Não há canal informativo ativo.")
        canal_id = canal["id"]

    destinos = publico()
    if not destinos:
        raise DisparoInvalido(
            "Nenhum cliente ativo tem telefone com WhatsApp verificado.")

    with banco.cursor() as cur:
        cur.execute(
            """INSERT INTO disparo (canal_id, titulo, corpo, criado_por,
                                    intervalo_seg, teto_por_hora)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (canal_id, titulo, corpo, criado_por, intervalo_seg, teto_por_hora))
        disparo_id = cur.fetchone()["id"]
        for d in destinos:
            cur.execute(
                """INSERT INTO disparo_destino
                       (disparo_id, cliente_id, contato_id, telefone_e164)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (disparo_id, telefone_e164) DO NOTHING""",
                (disparo_id, d["cliente_id"], d["contato_id"], d["telefone_e164"]))

    log.info("disparo %s criado com %d destinos", disparo_id, len(destinos))
    return ver(disparo_id)


def ver(disparo_id: int) -> dict | None:
    linha = banco.um(
        """SELECT d.*, c.nome AS canal_nome, a.nome AS autor_nome
             FROM disparo d
             LEFT JOIN canal c ON c.id = d.canal_id
             LEFT JOIN atendente a ON a.id = d.criado_por
            WHERE d.id = %s""", (disparo_id,))
    if not linha:
        return None
    linha["destinos"] = banco.varios(
        """SELECT estado, COUNT(*) AS n FROM disparo_destino
            WHERE disparo_id = %s GROUP BY estado ORDER BY estado""",
        (disparo_id,))
    linha["total_destinos"] = sum(x["n"] for x in linha["destinos"])
    return linha


def listar() -> list[dict]:
    return banco.varios("""
        SELECT d.id, d.titulo, d.estado, d.criado_em, d.iniciado_em,
               d.concluido_em, a.nome AS autor_nome,
               (SELECT COUNT(*) FROM disparo_destino x WHERE x.disparo_id = d.id) AS total,
               (SELECT COUNT(*) FROM disparo_destino x WHERE x.disparo_id = d.id
                 AND x.estado = 'pendente') AS pendentes,
               (SELECT COUNT(*) FROM disparo_destino x WHERE x.disparo_id = d.id
                 AND x.estado IN ('entregue','lido')) AS entregues,
               (SELECT COUNT(*) FROM disparo_destino x WHERE x.disparo_id = d.id
                 AND x.estado = 'falhou') AS falharam
          FROM disparo d LEFT JOIN atendente a ON a.id = d.criado_por
         ORDER BY d.criado_em DESC LIMIT 50
    """)


def _enviar_um(destino: dict, disparo: dict) -> dict:
    """Manda para UM destino e grava o resultado. Não decide ritmo."""
    from . import evolution

    instancia = banco.um("SELECT instancia FROM canal WHERE id = %s",
                         (disparo["canal_id"],))
    if not instancia or not instancia["instancia"]:
        return {"ok": False, "motivo": "canal sem instância"}

    try:
        enviado = evolution.enviar_texto(
            instancia["instancia"], destino["telefone_e164"], disparo["corpo"])
    except Exception as e:                              # noqa: BLE001
        banco.executar(
            """UPDATE disparo_destino SET estado = 'falhou', erro = %s,
                                          atualizado_em = now()
                WHERE id = %s""", (f"{type(e).__name__}: {e}"[:400], destino["id"]))
        log.warning("disparo %s destino %s falhou: %s",
                    disparo["id"], destino["id"], e)
        return {"ok": False, "motivo": str(e)}

    banco.executar(
        """UPDATE disparo_destino SET estado = 'enviado', id_externo = %s,
                                      enviado_em = now(), erro = NULL,
                                      atualizado_em = now()
            WHERE id = %s""", (enviado["id_externo"], destino["id"]))
    return {"ok": True, "id_externo": enviado["id_externo"]}


def enviar_teste(disparo_id: int, telefone: str | None = None) -> dict:
    """🚨 O "começa com 1" da metodologia, como função.

    Manda para UM destino e PARA. O disparo continua em rascunho e o resto
    continua pendente. A confirmação é reler o estado de entrega depois --
    nunca o retorno desta chamada.
    """
    disparo = ver(disparo_id)
    if not disparo:
        raise DisparoInvalido("Disparo não encontrado.")

    if telefone:
        from . import telefone as tel
        alvo = tel.normalizar(telefone)
        if not alvo:
            raise DisparoInvalido(f"Telefone {telefone!r} não é válido.")
        destino = {"id": None, "telefone_e164": alvo}
        # Teste avulso não mexe na fila: não grava estado em destino nenhum.
        from . import evolution
        instancia = banco.um("SELECT instancia FROM canal WHERE id = %s",
                             (disparo["canal_id"],))["instancia"]
        enviado = evolution.enviar_texto(instancia, alvo, disparo["corpo"])
        log.info("disparo %s: teste avulso para %s", disparo_id, alvo)
        return {"ok": True, "avulso": True, "telefone": alvo,
                "id_externo": enviado["id_externo"]}

    destino = banco.um(
        """SELECT id, telefone_e164 FROM disparo_destino
            WHERE disparo_id = %s AND estado = 'pendente'
            ORDER BY id LIMIT 1""", (disparo_id,))
    if not destino:
        raise DisparoInvalido("Não há destino pendente neste disparo.")

    resultado = _enviar_um(destino, disparo)
    resultado["telefone"] = destino["telefone_e164"]
    resultado["avulso"] = False
    return resultado


def enviar_lote(disparo_id: int, quantos: int = 20) -> dict:
    """Envia o próximo pedaço da fila, respeitando o teto por hora.

    ⚠️ NÃO dorme entre envios aqui: quem chama é a rota, e rota que dorme
    segura um worker. O intervalo vive no laço de fundo.
    """
    import time

    disparo = ver(disparo_id)
    if not disparo:
        raise DisparoInvalido("Disparo não encontrado.")
    if disparo["estado"] not in ("rascunho", "enviando"):
        raise DisparoInvalido(f"Disparo está {disparo['estado']}.")

    # 🚨 Teto por hora: conta o que JÁ saiu na última hora, não o que se
    # pretende mandar. É o que impede a rajada mesmo com alguém insistindo no
    # botão.
    ja_saiu = banco.um(
        """SELECT COUNT(*) AS n FROM disparo_destino
            WHERE disparo_id = %s AND enviado_em > now() - interval '1 hour'""",
        (disparo_id,))["n"]
    espaco = max(0, disparo["teto_por_hora"] - ja_saiu)
    if espaco == 0:
        return {"enviados": 0, "falhas": 0, "motivo": "teto por hora atingido",
                "ja_saiu_na_hora": ja_saiu}

    fila = banco.varios(
        """SELECT id, telefone_e164 FROM disparo_destino
            WHERE disparo_id = %s AND estado = 'pendente'
            ORDER BY id LIMIT %s""", (disparo_id, min(quantos, espaco)))

    if fila and disparo["estado"] == "rascunho":
        banco.executar(
            "UPDATE disparo SET estado = 'enviando', iniciado_em = now() "
            "WHERE id = %s", (disparo_id,))

    enviados, falhas = 0, 0
    for i, destino in enumerate(fila):
        r = _enviar_um(destino, disparo)
        enviados += int(r["ok"])
        falhas += int(not r["ok"])
        if i < len(fila) - 1:
            time.sleep(disparo["intervalo_seg"])

    restam = banco.um(
        "SELECT COUNT(*) AS n FROM disparo_destino "
        "WHERE disparo_id = %s AND estado = 'pendente'", (disparo_id,))["n"]
    if restam == 0:
        banco.executar(
            "UPDATE disparo SET estado = 'concluido', concluido_em = now() "
            "WHERE id = %s AND estado = 'enviando'", (disparo_id,))

    return {"enviados": enviados, "falhas": falhas, "restam": restam}


def pausar(disparo_id: int) -> dict:
    n = banco.executar(
        "UPDATE disparo SET estado = 'pausado' WHERE id = %s AND estado = 'enviando'",
        (disparo_id,))
    return {"ok": bool(n)}


def registrar_entrega(id_externo: str, estado_wa: str) -> bool:
    """O webhook chama isto quando chega o status de uma mensagem enviada.

    🚨 É AQUI que "a confirmação é o estado de entrega, não o retorno do POST"
    se materializa. O POST devolve `PENDING`; quem diz que chegou é o
    `DELIVERY_ACK` que volta pelo webhook, minutos depois se o aparelho estiver
    desligado.
    """
    mapa = {"DELIVERY_ACK": "entregue", "READ": "lido", "PLAYED": "lido",
            "ERROR": "falhou"}
    novo = mapa.get((estado_wa or "").upper())
    if not novo or not id_externo:
        return False
    n = banco.executar(
        "UPDATE disparo_destino SET estado = %s, atualizado_em = now() "
        "WHERE id_externo = %s AND estado <> %s", (novo, id_externo, novo))
    return bool(n)


def respostas_recebidas() -> dict:
    """Cliente responde boleto — e no informativo isso não vira conversa.

    ⚠️ Sem este contador as respostas ficam INVISÍVEIS: são gravadas com
    `motivo_ignorado` e ninguém olha. Não vira conversa (decisão do usuário),
    mas para de ser invisível.
    """
    return {
        "total": banco.um(
            """SELECT COUNT(*) AS n FROM webhook_evento w
                JOIN canal c ON c.id = w.canal_id
               WHERE c.tipo = 'informativo' AND w.evento = 'messages.upsert'
                 AND w.de_mim IS NOT TRUE""")["n"],
        "ultimas": banco.varios(
            """SELECT w.id, w.telefone, w.recebido_em,
                      w.payload->'data'->'message'->>'conversation' AS texto
                 FROM webhook_evento w JOIN canal c ON c.id = w.canal_id
                WHERE c.tipo = 'informativo' AND w.evento = 'messages.upsert'
                  AND w.de_mim IS NOT TRUE
                ORDER BY w.id DESC LIMIT 20"""),
    }
