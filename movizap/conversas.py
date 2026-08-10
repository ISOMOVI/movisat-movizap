"""Máquina de estados: transforma `webhook_evento` cru em conversa e mensagem.

É a segunda metade do passo 4. O webhook grava e responde 200 rápido; quem
interpreta é este módulo, lendo a tabela depois. Separar as duas coisas é o que
impede que uma falha de interpretação vire mensagem perdida — o payload cru
continua lá e o evento pode ser reprocessado.

🚨 IDEMPOTÊNCIA É DO BANCO, NÃO DA DISCIPLINA.
  `ux_mensagem_id_externo`  -> a mesma mensagem não entra duas vezes;
  `ux_conversa_aberta`      -> um telefone tem UMA conversa aberta por canal.
Reprocessar o mesmo evento não duplica nada, e é isso que torna seguro rodar
de novo depois de corrigir um parser.

🚨 NÚMERO AMBÍGUO NÃO GANHA DONO. `cadastro.por_telefone` devolve LISTA: dez
números da base estão em mais de um contato (um deles em oito, centrais de
empresa). Com mais de um candidato, `contato_id` fica NULL e a conversa
aparece como não identificada. Chutar aqui produziria ficha errada na tela do
atendente — que é pior que ficha nenhuma (regra de identidade, 06/08).

⚠️ NÃO EXISTE ENVIO AQUI. Fase 1 é receber; `evolution.py` não tem rota de
envio de propósito. Mensagem com `fromMe` é gravada como saída porque ela
aconteceu de verdade — foi digitada no celular —, não porque o painel mandou.
"""
import asyncio
import logging
from datetime import datetime, timezone

from . import banco, bitrix, cadastro, midia as midia_mod, telefone as tel

log = logging.getLogger("movizap.conversas")

# 5s: a caixa de entrada precisa parecer "ao vivo" sem que ninguém dependa de
# apertar F5. O custo é um SELECT em índice quando não há nada pendente.
INTERVALO_SEG = 5

# Eventos que este módulo sabe interpretar. O resto é marcado como processado
# sem virar nada: `connection.update` e `qrcode.updated` são assunto do vigia,
# que já grava em `canal_evento`.
EVENTOS_TRATADOS = {"messages.upsert", "messages.update", "send.message"}

# `data.message` traz UMA destas chaves. A ordem importa: `extendedTextMessage`
# é texto com citação/link, e precisa ser visto antes do genérico.
TIPOS = [
    ("conversation", "texto"),
    ("extendedTextMessage", "texto"),
    ("imageMessage", "imagem"),
    ("audioMessage", "audio"),
    ("videoMessage", "video"),
    ("documentMessage", "documento"),
    ("documentWithCaptionMessage", "documento"),
    ("stickerMessage", "figurinha"),
    ("locationMessage", "localizacao"),
    ("contactMessage", "contato"),
    ("contactsArrayMessage", "contato"),
]

# O que o WhatsApp chama de status, no vocabulário do nosso CHECK.
ENTREGA = {
    "PENDING": "pendente",
    "SERVER_ACK": "enviada",
    "DELIVERY_ACK": "entregue",
    "READ": "lida",
    "PLAYED": "lida",
    "ERROR": "falhou",
}


def _cavar(corpo, *caminho, padrao=None):
    atual = corpo
    for chave in caminho:
        if not isinstance(atual, dict):
            return padrao
        atual = atual.get(chave)
    return padrao if atual is None else atual


def _quando(data: dict) -> datetime:
    """`messageTimestamp` vem em segundos, às vezes como texto.

    ⚠️ Sem hora do provedor a ordenação da tela passaria a ser a ordem de
    chegada — e fora de ordem é normal no WhatsApp. Cair para "agora" é o
    último recurso, e é melhor que recusar a mensagem.
    """
    bruto = data.get("messageTimestamp")
    try:
        return datetime.fromtimestamp(int(bruto), tz=timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _tipo_e_texto(mensagem: dict) -> tuple[str, str | None]:
    """O tipo da mensagem e o texto que dá para mostrar na lista.

    ⚠️ Tipo desconhecido vira 'texto' com o nome da chave, em vez de estourar:
    o WhatsApp inventa tipo novo e a mensagem não pode sumir por causa disso.
    """
    if not isinstance(mensagem, dict):
        return "texto", None

    for chave, tipo in TIPOS:
        if chave not in mensagem:
            continue
        valor = mensagem[chave]
        if chave == "conversation":
            return tipo, valor if isinstance(valor, str) else None
        if isinstance(valor, dict):
            # legenda da imagem/vídeo, texto do extendedText, nome do arquivo
            texto = (valor.get("text") or valor.get("caption")
                     or valor.get("fileName") or valor.get("displayName"))
            return tipo, texto
        return tipo, None

    conhecidas = [k for k in mensagem if not k.startswith("messageContextInfo")]
    if conhecidas:
        log.info("tipo de mensagem desconhecido: %s", conhecidas[0])
        return "texto", f"[{conhecidas[0]} — tipo ainda não tratado]"
    return "texto", None


def _nome_whatsapp(data: dict) -> str | None:
    """O apelido que a pessoa escolheu no WhatsApp.

    🚨 MEDIDO EM 10/08: `pushName` chega em 721 dos 722 eventos guardados e era
    descartado inteiro. Ao mesmo tempo 35 das 37 conversas não têm vínculo com
    o cadastro -- o atendente via um número cru numa tela em que o nome da
    pessoa já tinha chegado.

    ⚠️ ISTO NÃO IDENTIFICA NINGUÉM. É apelido: a pessoa troca quando quiser e
    dois desconhecidos podem usar o mesmo. Quem diz de quem é a conversa
    continua sendo `contato_id`. Guardar os dois separados é o que impede um
    apelido de virar cadastro.

    Só vale quando NÃO é mensagem nossa: em `fromMe` o `pushName` é o nome do
    nosso próprio número, e gravá-lo renomearia o cliente com o nome da
    Movisat.
    """
    nome = data.get("pushName")
    if not isinstance(nome, str):
        return None
    nome = nome.strip()
    return nome[:120] if nome else None


def _citada_id(cur, data: dict) -> int | None:
    """A mensagem que esta está respondendo, se nós a temos.

    🚨 MEDIDO EM 10/08, e o número é MENOR do que parecia: `contextInfo` chega
    em 392 eventos, mas em 359 deles é `mentionedJid`/`groupMentions`, que não
    é citação nenhuma. Citação de verdade -- com `stanzaId` -- são **33**.
    Desses, 32 apontam para mensagem que já está no banco.

    ⚠️ O `stanzaId` pode apontar para mensagem anterior ao painel. Nesse caso
    fica NULL e a mensagem aparece sem a citação, em vez de sumir.
    """
    ctx = data.get("contextInfo")
    if not isinstance(ctx, dict):
        return None
    stanza = ctx.get("stanzaId")
    if not stanza:
        return None
    cur.execute("SELECT id FROM mensagem WHERE id_externo = %s", (stanza,))
    achada = cur.fetchone()
    return achada["id"] if achada else None


def _contato_do_numero(e164: str) -> int | None:
    """Um dono, ou nenhum. Nunca um chute entre vários."""
    candidatos = cadastro.por_telefone(e164)
    if len(candidatos) == 1:
        return candidatos[0]["id"]
    if len(candidatos) > 1:
        log.info("telefone %s responde por %d contatos: conversa fica sem dono",
                 e164, len(candidatos))
    return None


def garantir_conversa(cur, canal_id: int, e164: str) -> int:
    """A conversa aberta deste número neste canal, criando se não houver.

    🚨 O `ON CONFLICT` usa o índice parcial `ux_conversa_aberta`. Sem ele, duas
    mensagens chegando juntas criariam duas conversas para a mesma pessoa e o
    atendente veria a fala dela partida em duas telas.
    """
    cur.execute(
        """SELECT id FROM conversa
            WHERE canal_id = %s AND telefone_e164 = %s AND estado <> 'resolvida'""",
        (canal_id, e164))
    achada = cur.fetchone()
    if achada:
        return achada["id"]

    cur.execute(
        """INSERT INTO conversa (canal_id, contato_id, telefone_e164, estado)
           VALUES (%s, %s, %s, 'nova')
           ON CONFLICT (canal_id, telefone_e164) WHERE estado <> 'resolvida'
           DO UPDATE SET atualizada_em = now()
           RETURNING id""",
        (canal_id, _contato_do_numero(e164), e164))
    return cur.fetchone()["id"]


def _gravar_mensagem(cur, evento: dict, corpo: dict) -> str:
    data = _cavar(corpo, "data", padrao={})
    chave = _cavar(data, "key", padrao={})
    de_mim = bool(chave.get("fromMe"))

    e164 = evento["telefone"]
    if not e164:
        return "sem telefone: nada a ligar"
    if not evento["canal_id"]:
        return "evento de instância sem canal cadastrado"

    conversa_id = garantir_conversa(cur, evento["canal_id"], e164)
    tipo, texto = _tipo_e_texto(data.get("message") or {})

    # O apelido do WhatsApp, só do lado do cliente. `IS DISTINCT FROM` porque
    # ele vem igual em toda mensagem: sem isso seriam 700 UPDATEs inúteis.
    if not de_mim:
        nome = _nome_whatsapp(data)
        if nome:
            cur.execute(
                """UPDATE conversa
                      SET nome_whatsapp = %s, nome_whatsapp_em = now()
                    WHERE id = %s AND nome_whatsapp IS DISTINCT FROM %s""",
                (nome, conversa_id, nome))

    cur.execute(
        """INSERT INTO mensagem
               (conversa_id, id_externo, direcao, autor, tipo, conteudo,
                entrega, criada_em, citada_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (id_externo) WHERE id_externo IS NOT NULL DO NOTHING
           RETURNING id""",
        (conversa_id, evento["id_externo"],
         "saida" if de_mim else "entrada",
         "atendente" if de_mim else "cliente",
         tipo, texto,
         ENTREGA.get(str(data.get("status") or "").upper()) if de_mim else None,
         _quando(data),
         _citada_id(cur, data)))
    nova = cur.fetchone()

    # 🚨 A MÍDIA VEM NO PRÓPRIO WEBHOOK, em `message.base64`. Só é guardada
    # quando a mensagem é NOVA: em reentrega o arquivo já está no disco, e
    # reescrever seria trabalho por nada em cada repetição do Evolution.
    if nova is not None:
        achado = midia_mod.extrair(data.get("message") or {})
        if achado:
            midia_id = midia_mod.guardar(cur, conversa_id, achado)
            if midia_id:
                cur.execute("UPDATE mensagem SET midia_id = %s WHERE id = %s",
                            (midia_id, nova["id"]))

    # A atividade avança mesmo em reentrega: a conversa continua viva.
    cur.execute(
        "UPDATE conversa SET ultima_atividade_em = %s, atualizada_em = now() "
        "WHERE id = %s AND ultima_atividade_em < %s",
        (_quando(data), conversa_id, _quando(data)))

    if nova is None:
        return f"conversa {conversa_id}: mensagem repetida, ignorada"
    return f"conversa {conversa_id}: mensagem {tipo} gravada"


def _atualizar_entrega(cur, evento: dict, corpo: dict) -> str:
    """`messages.update` normalmente só diz que mudou o status de entrega."""
    from . import informativos

    bruto = str(_cavar(corpo, "data", "status") or "").upper()
    estado = ENTREGA.get(bruto)
    if not estado or not evento["id_externo"]:
        return f"update sem status utilizável ({bruto or 'vazio'})"

    # 🚨 O mesmo status serve ao informativo. É AQUI que "a confirmação é o
    # estado de entrega, não o retorno do POST" acontece: o envio devolve
    # PENDING, e quem diz que chegou é este DELIVERY_ACK -- que pode vir
    # minutos depois, se o aparelho estiver desligado.
    if informativos.registrar_entrega(evento["id_externo"], bruto):
        return f"entrega de informativo -> {estado}"
    cur.execute(
        "UPDATE mensagem SET entrega = %s WHERE id_externo = %s",
        (estado, evento["id_externo"]))
    return f"entrega -> {estado} ({cur.rowcount} mensagem)"


def processar_pendentes(limite: int = 500) -> dict:
    """Consome a fila de `webhook_evento`. É `def`, não `async def`.

    🚨 Quem chama de dentro do loop usa `asyncio.to_thread`, e `to_thread` com
    `async def` NÃO EXECUTA NADA: roda a corrotina na thread, ninguém a aguarda,
    e o único sinal é um RuntimeWarning invisível em produção.
    """
    pendentes = banco.varios(
        """SELECT id, canal_id, instancia, evento, id_externo, telefone, payload
             FROM webhook_evento
            WHERE NOT processado
            ORDER BY id
            LIMIT %s""", (limite,))

    contas = {"lidos": len(pendentes), "mensagens": 0, "entregas": 0,
              "ignorados": 0, "erros": 0}

    for evento in pendentes:
        corpo = evento["payload"] or {}
        try:
            with banco.cursor() as cur:
                if evento["evento"] in ("messages.upsert", "send.message"):
                    nota = _gravar_mensagem(cur, evento, corpo)
                    contas["mensagens"] += 1
                elif evento["evento"] == "messages.update":
                    nota = _atualizar_entrega(cur, evento, corpo)
                    contas["entregas"] += 1
                else:
                    nota = "evento sem conversa (conexão/QR): assunto do vigia"
                    contas["ignorados"] += 1

                # ⚠️ `erro` fica NULL no caminho feliz. A nota é para o log:
                # gravá-la aqui inflaria o contador de erros do resumo e
                # faria a tela acusar problema onde não houve.
                log.debug("evento %s: %s", evento["id"], nota)
                cur.execute(
                    "UPDATE webhook_evento SET processado = true, "
                    "processado_em = now(), erro = NULL WHERE id = %s",
                    (evento["id"],))
        except Exception as e:   # noqa: BLE001 - um evento ruim não para a fila
            contas["erros"] += 1
            log.exception("evento %s falhou ao processar", evento["id"])
            # ⚠️ NÃO marca processado: fica para reprocessar depois de corrigir.
            banco.executar(
                "UPDATE webhook_evento SET erro = %s WHERE id = %s",
                (f"{e.__class__.__name__}: {e}"[:500], evento["id"]))

    if contas["lidos"]:
        log.info("processados %(lidos)s eventos: %(mensagens)s mensagens, "
                 "%(entregas)s entregas, %(ignorados)s ignorados, %(erros)s erros",
                 contas)
    return contas


async def rodar(parar: asyncio.Event) -> None:
    """Laço que consome a fila. Espelha o `vigia.rodar`, e pela mesma razão:
    a mensagem tem que virar conversa mesmo com ninguém olhando a tela.

    🚨 `asyncio.to_thread` recebe `processar_pendentes`, que é `def`. Com
    `async def` ele rodaria a corrotina na thread sem ninguém aguardá-la, e o
    único sinal seria um RuntimeWarning invisível em produção.
    """
    log.info("processador de conversas ativo (a cada %ds)", INTERVALO_SEG)
    while not parar.is_set():
        try:
            await asyncio.to_thread(processar_pendentes)
        except Exception:
            # Parar em silêncio seria pior que não existir: as mensagens
            # continuariam chegando e nada apareceria na tela.
            log.exception("processamento falhou -- segue tentando")
        try:
            await asyncio.wait_for(parar.wait(), timeout=INTERVALO_SEG)
        except asyncio.TimeoutError:
            pass
    log.info("processador de conversas encerrado")


# ============================================================================
# LEITURA — o que a ATD_1.1 e a ATD_1.2 mostram
# ============================================================================

def listar(estado: str | None = None, atendente_id: int | None = None,
           sem_dono: bool = False, busca: str = "", limite: int = 100) -> list[dict]:
    """As conversas para a lista da caixa de entrada.

    Cada linha traz o que o doc pede: nome (ou telefone, quando não
    identificado), última mensagem, há quanto tempo, quem atende e o time.
    """
    condicoes, params = ["1=1"], []
    if estado:
        condicoes.append("c.estado = %s")
        params.append(estado)
    if atendente_id:
        condicoes.append("c.atendente_id = %s")
        params.append(atendente_id)
    if sem_dono:
        condicoes.append("c.atendente_id IS NULL")
    if busca:
        analise = tel.normalizar(busca)
        if analise:
            condicoes.append("c.telefone_e164 = %s")
            params.append(analise)
        else:
            condicoes.append("ct.nome ILIKE %s")
            params.append(f"%{busca}%")

    params.append(limite)
    return banco.varios(
        f"""
        SELECT c.id, c.estado, c.telefone_e164, c.contato_id, c.canal_id,
               c.ultima_atividade_em, c.criada_em, c.atendente_id,
               ct.nome AS contato_nome,
               cl.nome AS cliente_nome,
               a.nome  AS atendente_nome,
               t.nome  AS time_nome,
               ca.nome AS canal_nome,
               u.conteudo AS ultima_mensagem,
               u.direcao  AS ultima_direcao,
               c.nome_whatsapp,
               u.tipo     AS ultimo_tipo,
               (SELECT COUNT(*) FROM mensagem m2
                 WHERE m2.conversa_id = c.id AND m2.direcao = 'entrada') AS qtd_entrada
          FROM conversa c
          LEFT JOIN contato ct ON ct.id = c.contato_id
          LEFT JOIN cliente cl ON cl.id = ct.cliente_id
          LEFT JOIN atendente a ON a.id = c.atendente_id
          LEFT JOIN time t ON t.id = c.time_id
          LEFT JOIN canal ca ON ca.id = c.canal_id
          LEFT JOIN LATERAL (
                SELECT conteudo, direcao, tipo FROM mensagem m
                 WHERE m.conversa_id = c.id
                 ORDER BY m.criada_em DESC, m.id DESC LIMIT 1
          ) u ON true
         WHERE {' AND '.join(condicoes)}
         ORDER BY c.ultima_atividade_em DESC
         LIMIT %s
        """, tuple(params))


def conversa(conversa_id: int) -> dict | None:
    linha = banco.um(
        """SELECT c.*, ct.nome AS contato_nome, cl.nome AS cliente_nome,
                  cl.id AS cliente_id, a.nome AS atendente_nome,
                  t.nome AS time_nome, ca.nome AS canal_nome
             FROM conversa c
             LEFT JOIN contato ct ON ct.id = c.contato_id
             LEFT JOIN cliente cl ON cl.id = ct.cliente_id
             LEFT JOIN atendente a ON a.id = c.atendente_id
             LEFT JOIN time t ON t.id = c.time_id
             LEFT JOIN canal ca ON ca.id = c.canal_id
            WHERE c.id = %s""", (conversa_id,))
    if not linha:
        return None
    linha["mensagens"] = mensagens(conversa_id)
    # Os dados da empresa, quando há vínculo. É o conteúdo do painel lateral:
    # o mesmo que se vê ao clicar no contato dentro do WhatsApp.
    linha["empresa"] = _empresa_da_conversa(linha)
    # ⚠️ Só quando NÃO há vínculo: com cliente identificado, mostrar o que o
    # Bitrix acha seria ruído -- e poderia contradizer o cadastro na cara do
    # atendente.
    linha["bitrix"] = (None if linha.get("contato_id")
                       else bitrix.observacao(telefone_e164=linha["telefone_e164"]))
    # 🚨 Quem NÃO foi identificado precisa dizer por quê: "não é cliente" e
    # "o número responde por 8 cadastros" pedem ações diferentes de quem atende.
    if not linha["contato_id"]:
        candidatos = cadastro.por_telefone(linha["telefone_e164"])
        linha["candidatos"] = [{"id": c["id"], "nome": c["nome"]} for c in candidatos]
    else:
        linha["candidatos"] = []
    return linha


def empresas_do_telefone(conversa_id: int) -> dict:
    """Todas as empresas que este telefone alcança — o grupo da pessoa.

    🚨 Um telefone em vários cadastros NÃO é ambiguidade. Medido na base: são
    grupos empresariais com o mesmo responsável -- a pessoa é uma só, as
    empresas é que são várias. Por isso aqui não se escolhe uma vencedora:
    devolve-se todas, com CNPJ, para o atendente conferir.

    ⚠️ Empresa inativa não aparece: foram removidas da base em 10/08. Se
    voltar a existir, o campo `ativo` já vem junto para a tela marcar.
    """
    conversa_linha = banco.um(
        "SELECT telefone_e164 FROM conversa WHERE id = %s", (conversa_id,))
    if not conversa_linha:
        return {"empresas": []}

    return {"empresas": banco.varios(
        """SELECT DISTINCT cl.id, cl.nome, cl.nome_fantasia, cl.documento,
                  cl.ativo, ct.nome AS contato_nome, ct.id AS contato_id
             FROM contato_telefone tel
             JOIN contato ct ON ct.id = tel.contato_id
             JOIN cliente cl ON cl.id = ct.cliente_id
            WHERE tel.e164 = %s
            ORDER BY cl.nome""",
        (conversa_linha["telefone_e164"],))}


def _empresa_da_conversa(conversa: dict) -> dict | None:
    """Os dados da empresa por trás desta conversa, ou None se não há vínculo.

    ⚠️ SÓ DADO DE EMPRESA. Veículo, contrato e fatura ficam de fora por decisão
    do usuário em 10/08 -- e quando faltar informação de empresa, ela entra
    pela planilha, não por endpoint novo. Manter o escopo aqui é o que impede
    a gaveta de virar um segundo sistema de consulta.
    """
    if not conversa.get("contato_id"):
        return None

    contato = cadastro.contato(conversa["contato_id"])
    if not contato:
        return None

    empresa = {"contato": contato, "cliente": None}
    if contato.get("cliente_id"):
        empresa["cliente"] = cadastro.cliente(contato["cliente_id"])
    return empresa


def vincular(conversa_id: int, cliente_id: int | None = None,
             contato_id: int | None = None) -> dict:
    """Liga esta conversa a um cadastro, à mão, de dentro do atendimento.

    🚨 É AQUI QUE O CADASTRO SE CONSERTA PELO USO. Medido em 07/08: 483 dos 944
    clientes ativos (51%) estão fora do alcance por CADASTRO INCOMPLETO, não
    por recusarem WhatsApp. Cada vínculo feito aqui é um telefone que passa a
    existir -- no lugar onde a informação aparece, por quem está falando com a
    pessoa.

    O telefone é gravado com `origem_campo = 'atendimento'`, que o separa para
    sempre do que veio do sync. Sem essa marca não daria para saber, depois, o
    que o Harmonit trouxe e o que nós afirmamos.

    ⚠️ Vincular por CLIENTE quando ele tem exatamente um contato usa esse
    contato. Com nenhum ou vários, cria um contato novo com o nome do WhatsApp
    -- escolher entre vários seria chute, e é a mesma regra que o
    `_contato_do_numero` já segue do outro lado.
    """
    with banco.cursor() as cur:
        cur.execute("SELECT * FROM conversa WHERE id = %s", (conversa_id,))
        conversa_linha = cur.fetchone()
        if not conversa_linha:
            return {"ok": False, "motivo": "Conversa não encontrada."}

        alvo = contato_id
        if alvo is None:
            if cliente_id is None:
                return {"ok": False, "motivo": "Informe o cliente ou o contato."}
            cur.execute(
                "SELECT id FROM contato WHERE cliente_id = %s AND ativo",
                (cliente_id,))
            existentes = cur.fetchall()
            if len(existentes) == 1:
                alvo = existentes[0]["id"]
            else:
                nome = conversa_linha.get("nome_whatsapp") or conversa_linha["telefone_e164"]
                cur.execute(
                    """INSERT INTO contato (cliente_id, nome, origem, ativo)
                       VALUES (%s, %s, 'movizap', true) RETURNING id""",
                    (cliente_id, nome))
                alvo = cur.fetchone()["id"]

        cur.execute("SELECT id, cliente_id FROM contato WHERE id = %s", (alvo,))
        if not cur.fetchone():
            return {"ok": False, "motivo": "Contato não encontrado."}

        # O telefone passa a existir no cadastro. `ON CONFLICT` porque o número
        # pode já estar lá por outro caminho -- vincular duas vezes não é erro.
        cur.execute(
            """INSERT INTO contato_telefone
                   (contato_id, e164, bruto, origem_campo, tem_whatsapp,
                    verificado_em, principal)
               VALUES (%s, %s, %s, 'atendimento', true, now(), false)
               ON CONFLICT DO NOTHING""",
            (alvo, conversa_linha["telefone_e164"], conversa_linha["telefone_e164"]))

        cur.execute(
            "UPDATE conversa SET contato_id = %s, atualizada_em = now() WHERE id = %s",
            (alvo, conversa_id))

    log.info("conversa %s vinculada ao contato %s", conversa_id, alvo)
    return {"ok": True, "contato_id": alvo}


def desvincular(conversa_id: int) -> dict:
    """Desfaz o vínculo da CONVERSA. Não apaga telefone do cadastro.

    ⚠️ De propósito: vincular errado é engano de tela e tem que ser barato de
    corrigir; apagar telefone é perder informação que alguém digitou. Quem quer
    tirar o número do cadastro faz isso no cadastro, olhando para ele.
    """
    with banco.cursor() as cur:
        cur.execute(
            "UPDATE conversa SET contato_id = NULL, atualizada_em = now() "
            "WHERE id = %s RETURNING id", (conversa_id,))
        if not cur.fetchone():
            return {"ok": False, "motivo": "Conversa não encontrada."}
    return {"ok": True}


def mensagens(conversa_id: int, limite: int = 300) -> list[dict]:
    """⚠️ Ordenado pela hora do PROVEDOR, não pela de chegada: fora de ordem é
    normal no WhatsApp, e ordenar por chegada mostraria a conversa embaralhada."""
    return banco.varios(
        """SELECT m.id, m.direcao, m.autor, m.tipo, m.conteudo, m.entrega,
                  m.criada_em, m.id_externo, a.nome AS atendente_nome,
                  m.midia_id, md.mime AS midia_mime, md.tamanho AS midia_tamanho,
                  md.nome_original AS midia_nome,
                  m.citada_id,
                  q.conteudo AS citada_conteudo, q.tipo AS citada_tipo,
                  q.autor    AS citada_autor
             FROM mensagem m
             LEFT JOIN atendente a ON a.id = m.atendente_id
             LEFT JOIN midia md ON md.id = m.midia_id
             LEFT JOIN mensagem q ON q.id = m.citada_id
            WHERE m.conversa_id = %s
            ORDER BY m.criada_em, m.id
            LIMIT %s""", (conversa_id, limite))


def assumir(conversa_id: int, atendente_id: int) -> dict:
    """🚨 ASSUMIR É ATÔMICO. O `WHERE atendente_id IS NULL` é a trava: dois
    atendentes clicando junto, um ganha e o outro é avisado de quem ficou.
    Sem isso, dois humanos respondem o mesmo cliente e ele vê a bagunça."""
    linha = banco.um(
        """UPDATE conversa SET atendente_id = %s, estado = 'humano',
                               atualizada_em = now()
            WHERE id = %s AND atendente_id IS NULL
            RETURNING id""", (atendente_id, conversa_id))
    if linha:
        return {"ok": True, "conversa_id": conversa_id}

    dono = banco.um(
        """SELECT a.nome FROM conversa c LEFT JOIN atendente a ON a.id = c.atendente_id
            WHERE c.id = %s""", (conversa_id,))
    if not dono:
        return {"ok": False, "motivo": "Conversa não encontrada."}
    return {"ok": False,
            "motivo": f"A conversa já foi assumida por {dono['nome'] or 'outra pessoa'}."}


TETO_MENSAGEM = 4000


def responder(conversa_id: int, texto: str, atendente_id: int | None) -> dict:
    """Responde o cliente pelo WhatsApp e grava a mensagem.

    🚨 O NÚMERO VEM DA CONVERSA, NUNCA DO QUE FOI DIGITADO. É esta linha que
    impede o painel de virar ferramenta de disparo: não existe caminho para
    escolher destinatário. Disparo em massa é Fase 2, com decisão própria.

    🚨 GRAVA COM O `key.id` QUE O WHATSAPP DEVOLVEU. O Evolution ecoa a nossa
    própria mensagem pelo webhook, com `fromMe: true` e o mesmo id; sem gravar
    o id agora, o eco viraria uma segunda mensagem igual na tela.

    ⚠️ ENVIA PRIMEIRO, GRAVA DEPOIS. O contrário registraria como enviada uma
    mensagem que o WhatsApp recusou -- e o atendente acharia que respondeu.
    """
    from . import evolution  # tardio: evolution não conhece conversas

    texto = (texto or "").strip()
    if not texto:
        return {"ok": False, "motivo": "Mensagem vazia."}
    if len(texto) > TETO_MENSAGEM:
        return {"ok": False,
                "motivo": f"Mensagem passa de {TETO_MENSAGEM} caracteres."}

    conversa_atual = banco.um(
        """SELECT c.id, c.telefone_e164, c.estado, c.atendente_id, ca.instancia
             FROM conversa c JOIN canal ca ON ca.id = c.canal_id
            WHERE c.id = %s""", (conversa_id,))
    if not conversa_atual:
        return {"ok": False, "motivo": "Conversa não encontrada."}
    if conversa_atual["estado"] == "resolvida":
        return {"ok": False,
                "motivo": "Conversa encerrada. Reabra ou espere o cliente escrever."}
    if not conversa_atual["instancia"]:
        return {"ok": False, "motivo": "O canal desta conversa não tem instância."}

    # Quem responde assume. Sem isto, dois atendentes respondem o mesmo cliente
    # sem nunca aparecer dono na lista.
    if conversa_atual["atendente_id"] is None and atendente_id:
        banco.executar(
            """UPDATE conversa SET atendente_id = %s, estado = 'humano',
                                   atualizada_em = now()
                WHERE id = %s AND atendente_id IS NULL""",
            (atendente_id, conversa_id))

    try:
        enviado = evolution.enviar_texto(
            conversa_atual["instancia"], conversa_atual["telefone_e164"], texto)
    except evolution.ErroEvolution as e:
        log.warning("conversa %s: envio recusado pelo Evolution: %s", conversa_id, e)
        return {"ok": False, "motivo": f"O WhatsApp recusou: {e}"}

    with banco.cursor() as cur:
        cur.execute(
            """INSERT INTO mensagem
                   (conversa_id, id_externo, direcao, autor, tipo, conteudo,
                    atendente_id, entrega, criada_em)
               VALUES (%s, %s, 'saida', 'atendente', 'texto', %s, %s, 'enviada', now())
               ON CONFLICT (id_externo) WHERE id_externo IS NOT NULL DO NOTHING
               RETURNING id""",
            (conversa_id, enviado["id_externo"], texto, atendente_id))
        nova = cur.fetchone()
        cur.execute(
            """UPDATE conversa
                  SET ultima_atividade_em = now(), atualizada_em = now(),
                      primeira_resposta_em = COALESCE(primeira_resposta_em, now()),
                      segundos_ate_resposta = COALESCE(
                          segundos_ate_resposta,
                          EXTRACT(EPOCH FROM (now() - criada_em))::int)
                WHERE id = %s""", (conversa_id,))

    return {"ok": True, "conversa_id": conversa_id,
            "mensagem_id": nova["id"] if nova else None,
            "id_externo": enviado["id_externo"]}


def anotar(conversa_id: int, texto: str, atendente_id: int | None) -> dict:
    """Nota interna: fica na conversa e NUNCA vai para o cliente.

    ⚠️ O CHECK do banco amarra os dois campos: `tipo = 'nota'` só existe com
    `direcao = 'interna'`. É o banco impedindo que uma nota vaze como mensagem.
    """
    texto = (texto or "").strip()
    if not texto:
        return {"ok": False, "motivo": "Nota vazia."}
    if not banco.um("SELECT id FROM conversa WHERE id = %s", (conversa_id,)):
        return {"ok": False, "motivo": "Conversa não encontrada."}

    linha = banco.um(
        """INSERT INTO mensagem
               (conversa_id, direcao, autor, tipo, conteudo, atendente_id, criada_em)
           VALUES (%s, 'interna', 'atendente', 'nota', %s, %s, now())
           RETURNING id""", (conversa_id, texto, atendente_id))
    return {"ok": True, "conversa_id": conversa_id, "mensagem_id": linha["id"]}


def fila() -> list[dict]:
    """As conversas sem dono, agrupadas por time e ordenadas por ESPERA.

    🚨 O BALDE "SEM TRIAGEM" VEM PRIMEIRO, E NÃO É DETALHE DE TELA. Quem
    atribui time é a triagem, e a triagem é a IA — que está desligada. Se a
    fila só agrupasse por time, ela apareceria VAZIA enquanto gente real
    espera, porque `time_id` de todas é NULL. Fila que esconde quem espera é
    pior que fila nenhuma.

    ⚠️ Ordena por espera, não por chegada: quem esperou mais aparece primeiro.
    """
    linhas = banco.varios(
        """
        SELECT c.id, c.telefone_e164, c.estado, c.time_id, c.ultima_atividade_em,
               c.criada_em, t.nome AS time_nome, ct.nome AS contato_nome,
               EXTRACT(EPOCH FROM (now() - c.ultima_atividade_em))::bigint AS espera_seg
          FROM conversa c
          LEFT JOIN time t ON t.id = c.time_id
          LEFT JOIN contato ct ON ct.id = c.contato_id
         WHERE c.atendente_id IS NULL AND c.estado <> 'resolvida'
         ORDER BY c.ultima_atividade_em
        """)

    grupos: dict = {}
    for linha in linhas:
        chave = linha["time_id"]
        if chave not in grupos:
            grupos[chave] = {
                "time_id": chave,
                "time_nome": linha["time_nome"],
                "sem_triagem": chave is None,
                "esperando": 0,
                "espera_maior_seg": 0,
                "conversas": [],
            }
        grupo = grupos[chave]
        grupo["esperando"] += 1
        grupo["espera_maior_seg"] = max(grupo["espera_maior_seg"],
                                        linha["espera_seg"] or 0)
        grupo["conversas"].append(linha)

    # Times ativos sem ninguém esperando também aparecem: "0" é informação.
    for t in banco.varios("SELECT id, nome FROM time WHERE ativo ORDER BY nome"):
        grupos.setdefault(t["id"], {
            "time_id": t["id"], "time_nome": t["nome"], "sem_triagem": False,
            "esperando": 0, "espera_maior_seg": 0, "conversas": [],
        })

    return sorted(grupos.values(),
                  key=lambda g: (not g["sem_triagem"], -g["espera_maior_seg"]))


# 🚨 `transferencia.motivo` tem CHECK no banco: é VOCABULÁRIO FECHADO, não
# texto livre. Descobri em 07/08 gravando "motivo de teste" e levando
# CheckViolation. O texto que a pessoa escreve vai no `resumo` -- que é onde o
# doc manda o resumo da transferência ir, de qualquer forma.
MOTIVOS = ("manual", "inatividade", "ia_triagem", "sem_time")


def _recebe_transferencia(cur, atendente_id: int) -> bool:
    """O owner assume qualquer conversa, mas ninguém transfere PARA ele.

    ⚠️ A tela já não o oferece, mas a API é pública -- e foi assim que o painel
    de demandas apagou dados em 07/08: a tela nunca fazia aquilo, a rota fazia.
    """
    cur.execute("SELECT transferivel FROM atendente WHERE id = %s", (atendente_id,))
    linha = cur.fetchone()
    return bool(linha and linha["transferivel"])


def transferir(conversa_id: int, time_id: int | None,
               para_atendente_id: int | None, motivo: str = "manual",
               de_atendente_id: int | None = None,
               texto_resumo: str | None = None) -> dict:
    """Manda a conversa para um time ou uma pessoa, deixando rastro.

    🚨 Enquanto a IA não existe, ISTO É A TRIAGEM: um humano decide o destino
    lendo a conversa. Quando a IA entrar, ela chama o mesmo caminho — e a
    tabela `transferencia` já vai ter o histórico das duas eras.

    ⚠️ Transferir para TIME tira o dono de propósito: a conversa volta a ser
    responsabilidade coletiva e reaparece na fila daquele time. Transferir
    para PESSOA já entrega com dono.
    """
    atual = banco.um("SELECT id, atendente_id FROM conversa WHERE id = %s", (conversa_id,))
    if not atual:
        return {"ok": False, "motivo": "Conversa não encontrada."}
    if not time_id and not para_atendente_id:
        return {"ok": False, "motivo": "Escolha um time ou uma pessoa."}
    if time_id and not banco.um("SELECT id FROM time WHERE id = %s AND ativo", (time_id,)):
        return {"ok": False, "motivo": "Time inexistente ou inativo."}
    if motivo not in MOTIVOS:
        return {"ok": False,
                "motivo": f"Motivo inválido. Vale: {', '.join(MOTIVOS)}."}

    with banco.cursor() as cur:
        # 🚨 Ninguém transfere PARA o owner. A tela já não o oferece, mas a API
        # é pública -- e foi por confiar na tela que o painel de demandas
        # apagou dados em 07/08.
        if para_atendente_id and not _recebe_transferencia(cur, para_atendente_id):
            return {"ok": False,
                    "motivo": "Esta pessoa não recebe transferência."}
        cur.execute(
            """UPDATE conversa
                  SET time_id = COALESCE(%s, time_id),
                      atendente_id = %s,
                      estado = %s,
                      qtd_transferencias = qtd_transferencias + 1,
                      atualizada_em = now()
                WHERE id = %s""",
            (time_id, para_atendente_id,
             "humano" if para_atendente_id else "fila", conversa_id))
        cur.execute(
            """INSERT INTO transferencia
                   (conversa_id, de_atendente_id, para_atendente_id, para_time_id,
                    motivo, resumo)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (conversa_id, de_atendente_id or atual["atendente_id"],
             para_atendente_id, time_id, motivo, texto_resumo))
    log.info("conversa %s transferida (time=%s pessoa=%s)",
             conversa_id, time_id, para_atendente_id)
    return {"ok": True, "conversa_id": conversa_id}


def devolver_para_fila(conversa_id: int, de_atendente_id: int | None,
                       observacao: str | None = None) -> dict:
    """Larga a conversa sem fechá-la. É um dos três caminhos de entrada da fila."""
    linha = banco.um(
        """UPDATE conversa SET atendente_id = NULL, estado = 'fila',
                               atualizada_em = now()
            WHERE id = %s AND estado <> 'resolvida' RETURNING id""", (conversa_id,))
    if not linha:
        return {"ok": False, "motivo": "Conversa encerrada ou inexistente."}
    banco.executar(
        """INSERT INTO transferencia (conversa_id, de_atendente_id, motivo, resumo)
           VALUES (%s, %s, 'manual', %s)""",
        (conversa_id, de_atendente_id, observacao))
    return {"ok": True, "conversa_id": conversa_id}


def encerrar(conversa_id: int, classificacao_id: int,
             comentario: str | None = None) -> dict:
    """Fecha a conversa. CLASSIFICAR É OBRIGATÓRIO — escopo, item 11.

    🚨 A classificação marcada com `exige_comentario` (o "Outro") pede texto.
    Sem isso ele vira o vale-tudo onde metade das conversas acaba, e o
    analytics morre junto: "no que gastamos atendimento" fica sem resposta.
    """
    conversa_atual = banco.um(
        "SELECT id, criada_em, estado FROM conversa WHERE id = %s", (conversa_id,))
    if not conversa_atual:
        return {"ok": False, "motivo": "Conversa não encontrada."}
    if conversa_atual["estado"] == "resolvida":
        return {"ok": False, "motivo": "Esta conversa já está encerrada."}

    classificacao = banco.um(
        "SELECT id, nome, exige_comentario FROM classificacao WHERE id = %s AND ativo",
        (classificacao_id,))
    if not classificacao:
        return {"ok": False, "motivo": "Classificação inexistente ou inativa."}

    comentario = (comentario or "").strip() or None
    if classificacao["exige_comentario"] and not comentario:
        return {"ok": False,
                "motivo": f"A classificação {classificacao['nome']!r} exige um "
                          f"comentário dizendo o que foi."}

    banco.executar(
        """UPDATE conversa
              SET estado = 'resolvida', resolvida_em = now(),
                  classificacao_id = %s, classificacao_texto = %s,
                  segundos_total = EXTRACT(EPOCH FROM (now() - criada_em))::int,
                  atualizada_em = now()
            WHERE id = %s""",
        (classificacao_id, comentario, conversa_id))
    log.info("conversa %s encerrada como %s", conversa_id, classificacao["nome"])
    return {"ok": True, "conversa_id": conversa_id}


def historico(busca: str = "", classificacao_id: int | None = None,
              limite: int = 100) -> list[dict]:
    """ATD_5.1 — as conversas encerradas, pesquisáveis.

    ⚠️ A busca por telefone passa pelo normalizador, como em toda a casa: as
    três grafias do mesmo número acham a mesma conversa.
    """
    condicoes, params = ["c.estado = 'resolvida'"], []
    if classificacao_id:
        condicoes.append("c.classificacao_id = %s")
        params.append(classificacao_id)
    if busca:
        e164 = tel.normalizar(busca)
        if e164:
            condicoes.append("c.telefone_e164 = %s")
            params.append(e164)
        else:
            condicoes.append("(ct.nome ILIKE %s OR cl.nome ILIKE %s)")
            params.extend([f"%{busca}%", f"%{busca}%"])
    params.append(limite)

    return banco.varios(
        f"""
        SELECT c.id, c.telefone_e164, c.criada_em, c.resolvida_em,
               c.segundos_total, c.qtd_transferencias, c.resolvida_pela_ia,
               c.classificacao_texto,
               ct.nome AS contato_nome, cl.nome AS cliente_nome,
               a.nome AS atendente_nome, t.nome AS time_nome,
               cf.nome AS classificacao_nome,
               (SELECT COUNT(*) FROM mensagem m WHERE m.conversa_id = c.id) AS qtd_mensagens
          FROM conversa c
          LEFT JOIN contato ct ON ct.id = c.contato_id
          LEFT JOIN cliente cl ON cl.id = ct.cliente_id
          LEFT JOIN atendente a ON a.id = c.atendente_id
          LEFT JOIN time t ON t.id = c.time_id
          LEFT JOIN classificacao cf ON cf.id = c.classificacao_id
         WHERE {' AND '.join(condicoes)}
         ORDER BY c.resolvida_em DESC
         LIMIT %s
        """, tuple(params))


def resumo() -> dict:
    """O cabeçalho da caixa de entrada — e a prova de que a fila anda."""
    return {
        "conversas": banco.um("SELECT COUNT(*) AS n FROM conversa")["n"],
        "sem_dono": banco.um(
            "SELECT COUNT(*) AS n FROM conversa "
            "WHERE atendente_id IS NULL AND estado <> 'resolvida'")["n"],
        "nao_identificadas": banco.um(
            "SELECT COUNT(*) AS n FROM conversa WHERE contato_id IS NULL")["n"],
        "mensagens": banco.um("SELECT COUNT(*) AS n FROM mensagem")["n"],
        "eventos_pendentes": banco.um(
            "SELECT COUNT(*) AS n FROM webhook_evento WHERE NOT processado")["n"],
        # 🚨 SÓ FALHA DE VERDADE. Até 07/08 este contador somava também os
        # eventos descartados de propósito (canal informativo, grupo), porque
        # o motivo do descarte era gravado no campo `erro`. O painel acusava
        # 16 erros num sistema saudável -- e alarme falso é o que faz alguém
        # parar de olhar. Ver migração 009.
        "eventos_com_erro": banco.um(
            "SELECT COUNT(*) AS n FROM webhook_evento WHERE erro IS NOT NULL")["n"],
        # Informativo: aparece na tela como número, não como problema.
        "eventos_ignorados": banco.um(
            "SELECT COUNT(*) AS n FROM webhook_evento "
            "WHERE motivo_ignorado IS NOT NULL")["n"],
    }
