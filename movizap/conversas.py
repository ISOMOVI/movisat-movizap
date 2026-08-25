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
import base64
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


def _nome_do_grupo(instancia: str, jid: str) -> str | None:
    """Pergunta o nome do grupo ao Evolution. Import tardio, como o `responder`."""
    from . import evolution
    try:
        return evolution.nome_do_grupo(instancia, jid)
    except Exception as e:
        # ⚠️ Nome de grupo é enfeite comparado a receber a mensagem: nunca
        # pode derrubar o processamento do webhook.
        log.info("nome do grupo %s não veio (%s)", jid, e.__class__.__name__)
        return None


def garantir_conversa(cur, canal_id: int, e164: str | None,
                      grupo_jid: str | None = None,
                      grupo_nome: str | None = None,
                      instancia: str | None = None) -> int:
    """A conversa aberta desta IDENTIDADE neste canal, criando se não houver.

    Identidade é o telefone, para conversa direta, ou o JID `…@g.us`, para
    grupo. Exatamente uma das duas — o CHECK `ck_conversa_identidade` garante.

    🚨 O `ON CONFLICT` usa o índice parcial `ux_conversa_aberta`. Sem ele, duas
    mensagens chegando juntas criariam duas conversas para a mesma pessoa e o
    atendente veria a fala dela partida em duas telas. Desde a migração 027 o
    índice é por `COALESCE(grupo_jid, telefone_e164)`, então a mesma garantia
    vale para grupo.

    ⚠️ GRUPO ENTRA NA MESMA LISTA da conversa direta, como no WhatsApp. Não há
    importação em massa: a conversa só nasce quando CHEGA MENSAGEM, então
    grupo parado nunca aparece. Medido em 12/08: o número participa de 62
    grupos, e só os que falam viram conversa.
    """
    if grupo_jid:
        cur.execute(
            """SELECT id, grupo_nome FROM conversa
                WHERE canal_id = %s AND grupo_jid = %s AND estado <> 'resolvida'""",
            (canal_id, grupo_jid))
        achada = cur.fetchone()
        if achada:
            # ⚠️ SÓ PERGUNTA O NOME SE AINDA NÃO TIVER. Perguntar a cada
            # mensagem seria uma chamada HTTP por mensagem de grupo, dentro do
            # processamento do webhook -- que tem de ser rápido.
            if not achada["grupo_nome"] and instancia:
                novo_nome = _nome_do_grupo(instancia, grupo_jid)
                if novo_nome:
                    cur.execute(
                        "UPDATE conversa SET grupo_nome = %s WHERE id = %s",
                        (novo_nome, achada["id"]))
            elif grupo_nome and achada["grupo_nome"] != grupo_nome:
                cur.execute(
                    "UPDATE conversa SET grupo_nome = %s WHERE id = %s",
                    (grupo_nome, achada["id"]))
            return achada["id"]

        cur.execute(
            """INSERT INTO conversa (canal_id, tipo, grupo_jid, grupo_nome,
                                     estado)
               VALUES (%s, 'grupo', %s, %s, 'nova')
               ON CONFLICT (canal_id, COALESCE(grupo_jid, telefone_e164))
                    WHERE estado <> 'resolvida'
               DO UPDATE SET atualizada_em = now()
               RETURNING id""",
            (canal_id, grupo_jid,
             grupo_nome or (_nome_do_grupo(instancia, grupo_jid)
                            if instancia else None)))
        return cur.fetchone()["id"]

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
           ON CONFLICT (canal_id, COALESCE(grupo_jid, telefone_e164))
                WHERE estado <> 'resolvida'
           DO UPDATE SET atualizada_em = now()
           RETURNING id""",
        (canal_id, _contato_do_numero(e164), e164))
    return cur.fetchone()["id"]


def _gravar_mensagem(cur, evento: dict, corpo: dict) -> str:
    data = _cavar(corpo, "data", padrao={})
    chave = _cavar(data, "key", padrao={})
    de_mim = bool(chave.get("fromMe"))

    # 🚨 GRUPO NÃO TEM TELEFONE. O `remoteJid` termina em `@g.us` e a
    # identidade da conversa passa a ser ele. Quem FALOU vem à parte, em
    # `key.participant` -- numa conversa direta o remetente é a própria
    # conversa, num grupo de quinze não é.
    jid_bruto = (chave.get("remoteJid") or "")
    e_grupo = jid_bruto.endswith("@g.us")

    e164 = evento["telefone"]
    if not e_grupo and not e164:
        return "sem telefone: nada a ligar"
    if not evento["canal_id"]:
        return "evento de instância sem canal cadastrado"

    # 🚨 O NOME DO GRUPO NÃO VEM NO PAYLOAD. `pushName` é o perfil de QUEM
    # MANDOU -- para mensagem nossa, o nosso próprio nome de negócio. Gravá-lo
    # como nome do grupo rotulou "Suporte Movisat -> Weso" de "Movisat
    # Rastreamento e Gestão de Frotas" em 12/08. O nome se pergunta ao
    # Evolution, e só quando a conversa AINDA NÃO TEM nome -- uma chamada por
    # grupo, não por mensagem.
    conversa_id = garantir_conversa(
        cur, evento["canal_id"],
        None if e_grupo else e164,
        grupo_jid=jid_bruto if e_grupo else None,
        instancia=evento.get("instancia") if e_grupo else None)
    tipo, texto = _tipo_e_texto(data.get("message") or {})

    # ⚠️ EM GRUPO, `pushName` É DE QUEM FALOU, NÃO DO GRUPO. Guardá-lo em
    # `nome_whatsapp` da conversa faria o nome da conversa mudar a cada
    # mensagem, virando o último que falou.
    if not de_mim and not e_grupo:
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
                entrega, criada_em, citada_id,
                remetente_jid, remetente_nome)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (id_externo) WHERE id_externo IS NOT NULL DO NOTHING
           RETURNING id""",
        (conversa_id, evento["id_externo"],
         "saida" if de_mim else "entrada",
         "atendente" if de_mim else "cliente",
         tipo, texto,
         ENTREGA.get(str(data.get("status") or "").upper()) if de_mim else None,
         _quando(data),
         _citada_id(cur, data),
         # Só em grupo: numa conversa direta o remetente é a conversa, e
         # repetir o mesmo telefone em toda linha não diz nada.
         (chave.get("participant") or None) if e_grupo else None,
         _nome_whatsapp(data) if (e_grupo and not de_mim) else None))
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

def _condicao_busca(termo: str) -> tuple[str, list]:
    """O `WHERE` da busca de conversa — UM só, para a caixa e o Histórico.

    🚨 EXISTIA COMO DOIS TRECHOS COPIADOS, E ELES DIVERGIRAM. A caixa procurava
    só em `contato.nome`; o Histórico procurava em `contato.nome OR
    cliente.nome`. Mesma caixinha na tela, duas regras. Cópia não fica igual
    sozinha -- por isso agora é função, e quem quiser mudar muda nos dois de
    uma vez ou em nenhum.

    🚨 É `OR` EM TUDO, NÃO `if/else`. A versão antiga escolhia telefone OU
    nome: `tel.normalizar` devolvia `None` para "998116168" (falta DDD) e a
    busca caía no ramo de nome, procurando dígitos em `contato.nome` e
    devolvendo VAZIO -- sem dizer que faltava o DDD. Escolher o campo pelo
    formato do que foi digitado é adivinhar; procurar em todos é responder.

    🚨 PROCURA ONDE A TELA MOSTRA. A lista exibe `nome_whatsapp ||
    contato_nome || telefone`, mas o SQL só olhava `contato.nome` -- e 85 das
    131 conversas (65%) não têm `contato_id`. Elas apareciam na tela com nome
    e eram inencontráveis por ele.

    ⚠️ A NOTA INTERNA ENTRA NA BUSCA, por decisão do usuário em 12/08: "a
    nota, uma vez dentro da conversa, faz parte da conversa". Buscar "boleto"
    acha a conversa mesmo que só a anotação diga isso.

    ⚠️ O `%` VAI COMO PARÂMETRO. Montar `ILIKE '%IAGO%'` dentro da string SQL
    faz o psycopg ler `%I` como placeholder -- aconteceu duas vezes em 11/08.
    """
    termo = (termo or "").strip()
    if not termo:
        return "", []

    curinga = f"%{termo}%"
    partes = ["c.nome_whatsapp ILIKE %s", "ct.nome ILIKE %s", "cl.nome ILIKE %s"]
    params: list = [curinga, curinga, curinga]

    # ---- telefone -----------------------------------------------------------
    # Dois caminhos, somados: o número inteiro (com as variantes do nono
    # dígito, como manda a metodologia §2) e o PEDAÇO -- "6168" tem de achar o
    # celular, e para isso não existe normalização possível.
    digitos = "".join(ch for ch in termo if ch.isdigit())
    if digitos:
        analise = tel.normalizar(termo)
        if analise:
            partes.append("c.telefone_e164 = ANY(%s)")
            params.append(sorted(tel.variantes(analise)))
        partes.append("c.telefone_e164 LIKE %s")
        params.append(f"%{digitos}%")

    # ---- conteúdo -----------------------------------------------------------
    # 🚨 `EXISTS`, não JOIN: com JOIN, a conversa em que o termo aparece em oito
    # mensagens voltaria oito vezes na lista, e o DISTINCT não resolveria --
    # as linhas seriam diferentes por causa das colunas da mensagem.
    partes.append(
        "EXISTS (SELECT 1 FROM mensagem m "
        "         WHERE m.conversa_id = c.id AND m.conteudo ILIKE %s)")
    params.append(curinga)

    return "(" + " OR ".join(partes) + ")", params


def _nome_explica(linha: dict, termo: str) -> bool:
    """O que a lista JÁ MOSTRA contém o termo? Então o acerto está à vista.

    ⚠️ Compara em minúscula porque o SQL casou com `ILIKE`. Usar comparação
    sensível a caixa aqui faria "IAGO" parecer inexplicado e a linha ganharia
    um trecho desnecessário -- discordando do próprio filtro que a trouxe.
    """
    termo = (termo or "").strip().casefold()
    if not termo:
        return True
    visiveis = [linha.get("nome_whatsapp"), linha.get("contato_nome"),
                linha.get("cliente_nome"), linha.get("telefone_e164")]
    digitos = "".join(ch for ch in termo if ch.isdigit())
    for valor in visiveis:
        if valor and termo in valor.casefold():
            return True
    # O telefone aparece na tela sem pontuação nenhuma, então o pedaço de
    # dígitos também conta como "à vista".
    fone = linha.get("telefone_e164") or ""
    return bool(digitos and digitos in fone)


def _trechos_achados(ids: list[int], termo: str) -> dict[int, str]:
    """O trecho que fez cada conversa casar, para a lista dizer POR QUÊ.

    ⚠️ Sem isto, a conversa que casou pelo CONTEÚDO aparece na lista com uma
    prévia sem o termo em lugar nenhum, e quem buscou conclui que a busca está
    quebrada.

    🚨 UMA CONSULTA PARA TODAS, NÃO UMA POR LINHA. Com 100 conversas na lista,
    perguntar de uma em uma são 100 idas ao banco a cada tecla digitada.

    ⚠️ E NÃO POR `LATERAL` DENTRO DO `listar`. O parâmetro do LATERAL cairia
    entre os `%s` do SELECT e os do WHERE, e errar essa ordem não dá erro de
    sintaxe -- dá resultado errado, que é o pior tipo. A própria `listar` já
    tem um aviso sobre isso.
    """
    termo = (termo or "").strip()
    if not termo or not ids:
        return {}
    linhas = banco.varios(
        """SELECT DISTINCT ON (conversa_id) conversa_id, conteudo
             FROM mensagem
            WHERE conversa_id = ANY(%s) AND conteudo ILIKE %s
            ORDER BY conversa_id, criada_em DESC, id DESC""",
        (ids, f"%{termo}%"))
    return {l["conversa_id"]: l["conteudo"] for l in linhas}


def listar(estado: str | None = None, atendente_id: int | None = None,
           sem_dono: bool = False, busca: str = "", limite: int = 100,
           relacoes: list[str] | None = None) -> list[dict]:
    """As conversas para a lista da caixa de entrada.

    Cada linha traz o que o doc pede: nome (ou telefone, quando não
    identificado), última mensagem, há quanto tempo, quem atende e o time.
    """
    # ⚠️ GRUPO E CONVERSA DIRETA NA MESMA LISTA, como no WhatsApp. A 027 tinha
    # criado uma aba separada; a 028 desfez. O painel não importa grupo --
    # conversa só nasce quando CHEGA MENSAGEM --, então grupo parado nunca
    # aparece e a ordem por atividade faz o resto.
    condicoes, params = ["1=1"], []
    if estado:
        condicoes.append("c.estado = %s")
        params.append(estado)
    if atendente_id:
        # 🚨 "minhas conversas" passou a incluir as que eu ACOMPANHO. Quem foi
        # convidado precisa ver a conversa na lista dele -- era exatamente
        # disso que o convite servia (migração 021).
        condicoes.append(
            """(c.atendente_id = %s
                OR EXISTS (SELECT 1 FROM conversa_participante p
                            WHERE p.conversa_id = c.id
                              AND p.atendente_id = %s
                              AND p.saiu_em IS NULL))""")
        params.extend([atendente_id, atendente_id])
    if sem_dono:
        condicoes.append("c.atendente_id IS NULL")

    # ---- filtro por tipo de cadastro (pedido do usuário em 25/08) ----------
    # 🚨 "SEM CADASTRO" E "SEM IDENTIFICAÇÃO" SÃO COISAS DIFERENTES, e o
    # usuário fez questão da distinção em 25/08:
    #
    #   sem_cadastro       -> a conversa não tem linha em `contato` nenhuma.
    #                         É o caso COMUM: 211 de 332 conversas (64%).
    #   sem_identificacao  -> o contato EXISTE e o flag da ficha dele ainda não
    #                         foi marcado por ninguém.
    #
    # Colapsar os dois num chip só esconderia justamente o caso majoritário --
    # e é o `sem_cadastro` que o botão `+` e a gaveta existem para resolver.
    if relacoes:
        pedidos = [r for r in relacoes if r]
        partes, params_rel = [], []
        if "sem_cadastro" in pedidos:
            partes.append("c.contato_id IS NULL")
            pedidos = [r for r in pedidos if r != "sem_cadastro"]
        if pedidos:
            partes.append("ct.relacao = ANY(%s)")
            params_rel.append(pedidos)
        if partes:
            condicoes.append("(" + " OR ".join(partes) + ")")
            params.extend(params_rel)
    onde_busca, params_busca = _condicao_busca(busca)
    if onde_busca:
        condicoes.append(onde_busca)
        params.extend(params_busca)

    # ---- a ordem ------------------------------------------------------------
    # 🚨 CONCLUÍDA VAI PARA O FIM DA FILA. A lista é a fila de quem espera, e
    # ordenar só por `ultima_atividade_em` punha a conversa concluída LOGO
    # APÓS a última mensagem do cliente no TOPO de "Sem dono" -- acima de quem
    # ainda espera resposta. Concluir não toca em `ultima_atividade_em` (nem
    # deve: esse campo mede atividade do cliente, não do atendente), então a
    # posição vinha da data da mensagem e não do desfecho.
    #
    # O usuário descreveu o comportamento esperado em 25/08: a conversa
    # concluída "volta a ficar sem dono, mas vai para o fim da fila".
    #
    # ⚠️ NA BUSCA, NÃO. Quem digita um termo está procurando UMA conversa, e
    # empurrar a concluída para depois de 300 abertas é escondê-la de quem
    # sabe que ela existe. Buscar é outra pergunta que listar.
    ordem = ("c.ultima_atividade_em DESC" if busca.strip()
             else "(c.estado = 'resolvida'), c.ultima_atividade_em DESC")

    # 🚨 ORDEM POSICIONAL: os dois %s do SELECT são os PRIMEIROS da query, então
    # entram na frente de tudo que o WHERE já empilhou. Errar isso não dá erro
    # de sintaxe -- dá resultado errado, que é pior.
    params = [atendente_id, atendente_id] + params
    params.append(limite)
    linhas = banco.varios(
        f"""
        SELECT c.id, c.estado, c.telefone_e164, c.contato_id, c.canal_id,
               c.tipo, c.grupo_jid, c.grupo_nome,
               c.ultima_atividade_em, c.criada_em, c.atendente_id,
               -- ⚠️ A tela precisa separar "sou o dono" de "fui convidado":
               -- as duas aparecem na mesma lista, e só o dono responde por ela.
               CASE WHEN %s::bigint IS NULL THEN false
                    ELSE EXISTS (SELECT 1 FROM conversa_participante p2
                                  WHERE p2.conversa_id = c.id
                                    AND p2.atendente_id = %s::bigint
                                    AND p2.saiu_em IS NULL) END AS acompanho,
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
         ORDER BY {ordem}
         LIMIT %s
        """, tuple(params))

    # ⚠️ O TRECHO SÓ APARECE QUANDO O NOME NÃO EXPLICA O ACERTO. Buscar "iago"
    # e ver a linha da conversa do Iago trocar a prévia por um pedaço de
    # mensagem é ruído: o motivo do acerto já está à vista, no nome. O trecho
    # existe para o caso oposto -- a conversa que casou por algo invisível.
    alvo = [l["id"] for l in linhas if not _nome_explica(l, busca)]
    trechos = _trechos_achados(alvo, busca)
    for l in linhas:
        l["trecho"] = trechos.get(l["id"])
    return linhas


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
    # 🚨 A TELA PRECISA SABER QUE ESTÁ VENDO UM PEDAÇO. Quem busca dentro da
    # conversa só acha o que foi carregado; sem este aviso, a busca diria "não
    # encontrado" sobre mensagem que existe no banco -- que é pior do que não
    # ter busca. Comparar com o teto é suficiente e não custa um COUNT: se
    # voltou exatamente o teto, há chance de haver mais.
    linha["truncada"] = len(linha["mensagens"]) >= TETO_MENSAGENS_NA_TELA
    linha["teto_mensagens"] = TETO_MENSAGENS_NA_TELA
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


TETO_MENSAGENS_NA_TELA = 1000


def mensagens(conversa_id: int, limite: int = TETO_MENSAGENS_NA_TELA) -> list[dict]:
    """⚠️ Ordenado pela hora do PROVEDOR, não pela de chegada: fora de ordem é
    normal no WhatsApp, e ordenar por chegada mostraria a conversa embaralhada.

    ⚠️ O TETO É NOSSO, NÃO DO WHATSAPP. Era 300 -- um padrão que eu escrevi, e
    que o frontend nunca sobrescreveu. Subiu para 1.000 por decisão do usuário
    em 12/08. A maior conversa da base tem 130 mensagens, então é folga.

    🚨 QUEM BUSCA DENTRO DA CONVERSA SÓ ACHA O QUE FOI CARREGADO. Por isso
    `conversa()` devolve `truncada`: passando do teto, a tela precisa DIZER que
    está vendo um pedaço, senão a busca responde "não encontrado" sobre
    mensagem que existe.
    """
    # 🚨 O TETO CORTAVA PELO LADO ERRADO. `ORDER BY criada_em ASC LIMIT n`
    # devolve as n mensagens MAIS ANTIGAS -- numa conversa acima do teto, o
    # atendente veria o começo dela e nunca o que o cliente acabou de dizer,
    # com a tela rolando para o "fim" de um pedaço velho. Nenhuma conversa
    # passou do teto ainda (a maior tem 130), então isso nunca apareceu: é
    # defeito latente, e subir o teto sozinho não o corrigiria.
    # Pega-se as n mais RECENTES e reordena para exibir.
    return banco.varios(
        """SELECT * FROM (
               SELECT m.id, m.direcao, m.autor, m.tipo, m.conteudo, m.entrega,
                      m.criada_em, m.id_externo, a.nome AS atendente_nome,
                      -- Quem falou DENTRO do grupo. Nulo em conversa direta,
                      -- onde o remetente é a própria conversa.
                      m.remetente_jid, m.remetente_nome,
                      m.midia_id, md.mime AS midia_mime,
                      md.tamanho AS midia_tamanho,
                      md.nome_original AS midia_nome,
                      m.citada_id,
                      q.conteudo AS citada_conteudo, q.tipo AS citada_tipo,
                      q.autor    AS citada_autor
                 FROM mensagem m
                 LEFT JOIN atendente a ON a.id = m.atendente_id
                 LEFT JOIN midia md ON md.id = m.midia_id
                 LEFT JOIN mensagem q ON q.id = m.citada_id
                WHERE m.conversa_id = %s
                ORDER BY m.criada_em DESC, m.id DESC
                LIMIT %s
           ) recentes
           ORDER BY criada_em, id""", (conversa_id, limite))


def assumir(conversa_id: int, atendente_id: int) -> dict:
    """🚨 ASSUMIR É ATÔMICO. O `WHERE atendente_id IS NULL` é a trava: dois
    atendentes clicando junto, um ganha e o outro é avisado de quem ficou.
    Sem isso, dois humanos respondem o mesmo cliente e ele vê a bagunça.

    Assumir uma conversa ENCERRADA a reabre (12/08). Antes disso, encerrar era
    uma porta só de ida: o `responder` recusa conversa resolvida e a tela
    escondia a barra inteira, então a conversa virava tela morta e o único
    jeito de voltar a falar era o cliente escrever primeiro.

    🚨 REABRIR ESBARRA NO `ux_conversa_aberta` — índice único em
    `(canal_id, telefone_e164) WHERE estado <> 'resolvida'`, que é o que faz o
    cliente que volta reabrir em vez de duplicar. Se ele já escreveu depois do
    encerramento, existe OUTRA conversa aberta com este número e reabrir esta
    estouraria o índice. Nesse caso não se força: devolve qual é a conversa
    viva, porque é nela que a pessoa tem de falar.
    """
    # Caminho comum: conversa aberta e sem dono.
    linha = banco.um(
        """UPDATE conversa SET atendente_id = %s, estado = 'humano',
                               atualizada_em = now()
            WHERE id = %s AND atendente_id IS NULL AND estado <> 'resolvida'
            RETURNING id""", (atendente_id, conversa_id))
    if linha:
        return {"ok": True, "conversa_id": conversa_id, "reaberta": False}

    atual = banco.um(
        """SELECT c.id, c.estado, c.canal_id, c.telefone_e164, c.atendente_id,
                  a.nome AS dono_nome
             FROM conversa c LEFT JOIN atendente a ON a.id = c.atendente_id
            WHERE c.id = %s""", (conversa_id,))
    if not atual:
        return {"ok": False, "motivo": "Conversa não encontrada."}

    if atual["estado"] != "resolvida":
        return {"ok": False,
                "motivo": f"A conversa já foi assumida por "
                          f"{atual['dono_nome'] or 'outra pessoa'}."}

    viva = banco.um(
        """SELECT id FROM conversa
            WHERE canal_id = %s AND telefone_e164 = %s AND estado <> 'resolvida'
            LIMIT 1""", (atual["canal_id"], atual["telefone_e164"]))
    if viva:
        return {"ok": False, "conversa_aberta_id": viva["id"],
                "motivo": f"Este número já tem uma conversa aberta "
                          f"(#{viva['id']}). É nela que a resposta chega."}

    # ⚠️ `resolvida_em` e `segundos_total` são métricas CONGELADAS no
    # fechamento. Deixá-las preenchidas numa conversa que voltou a andar faria
    # a ATD_5.1 listar como encerrada uma conversa aberta. Quem fecha de novo
    # recalcula as duas.
    #
    # 🚨 `resolvida_por` LIMPA JUNTO, pela MESMA razão. Ela é o que a tela
    # inicial conta em "concluídos por mim": conversa reaberta que continuasse
    # com o autor do fechamento seria contada como desfecho sem ter desfecho --
    # e o número subiria sozinho a cada reabrir/concluir do mesmo atendimento.
    reaberta = banco.um(
        """UPDATE conversa
              SET atendente_id = %s, estado = 'humano',
                  resolvida_em = NULL, segundos_total = NULL,
                  resolvida_por = NULL,
                  atualizada_em = now()
            WHERE id = %s AND estado = 'resolvida'
            RETURNING id""", (atendente_id, conversa_id))
    if not reaberta:
        return {"ok": False,
                "motivo": "Alguém mexeu nesta conversa agora. Recarregue."}

    log.info("conversa %s reaberta e assumida pelo atendente %s",
             conversa_id, atendente_id)
    return {"ok": True, "conversa_id": conversa_id, "reaberta": True}


TETO_MENSAGEM = 4000


def responder(conversa_id: int, texto: str, atendente_id: int | None) -> dict:
    """Responde o cliente pelo WhatsApp e grava a mensagem.

    🚨 O NÚMERO VEM DA CONVERSA, NUNCA DO PARÂMETRO. Não é regra de política:
    é o desenho desta função -- ela responde uma conversa que já existe. Para
    falar com quem ainda não escreveu existe `iniciar_conversa`, que é o
    caminho do botão `+` (25/08).

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
        """SELECT c.id, c.telefone_e164, c.estado, c.atendente_id, ca.instancia,
                  c.tipo, c.grupo_jid,
                  -- 🚨 O DESTINO DO ENVIO. Conversa direta vai para o
                  -- telefone; grupo vai para o JID. Os dois saem da CONVERSA:
                  -- responder é responder ESTA conversa. Falar com quem ainda
                  -- não escreveu é `iniciar_conversa`.
                  COALESCE(c.grupo_jid, c.telefone_e164) AS destino
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
            conversa_atual["instancia"], conversa_atual["destino"], texto)
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


# 🚨 25 MB É DECISÃO DO USUÁRIO (12/08), NÃO ESCOLHA MINHA. Eu tinha posto 16
# sozinho, e ele já tinha dito -- no dia anterior -- que limite, filtro e teto
# são decisão dele até prova em contrário. Mudar este número é pedir, nunca
# aplicar.
TETO_ARQUIVO_MB = 25
TETO_ARQUIVO = TETO_ARQUIVO_MB * 1024 * 1024

# O vocabulário de `mensagem.tipo` a partir da família do MIME. É o NOSSO
# vocabulário, não o do Evolution -- os dois se parecem e não são iguais.
_TIPO_POR_FAMILIA = {"image": "imagem", "video": "video", "audio": "audio"}


def iniciar_conversa(canal_id: int, numero_digitado: str, texto: str,
                     atendente_id: int | None) -> dict:
    """Fala primeiro com um número que ainda não escreveu — o botão `+`.

    Pedido do usuário em 25/08: *"o foco do botão + seria enviar mensagem para
    um número que ainda não temos salvo... então o + já valida se tem whatsapp
    e envia a mensagem nova"*.

    A ordem importa e é esta:

      1. normaliza o número (as duas grafias do nono dígito);
      2. **pergunta ao WhatsApp se o número existe** -- antes de criar
         qualquer linha no banco;
      3. se já houver conversa ABERTA com este número neste canal, ABRE ELA;
      4. senão cria a conversa, já com dono;
      5. envia pelo caminho normal (`responder`), que grava, assume e trata o
         eco do webhook;
      6. identifica DEPOIS do envio.

    🚨 O PASSO 2 VEM ANTES DO 4 DE PROPÓSITO. Criar a conversa e só então
    descobrir que o número não tem WhatsApp deixaria uma conversa órfã na
    caixa de entrada, sem nenhuma mensagem, para sempre -- e alguém teria de
    limpar isso à mão. Nada é gravado enquanto não se sabe que dá para falar.

    🚨 NÃO SE INVENTA `false`. `evolution.tem_whatsapp` devolve `None` quando o
    Evolution não respondeu sobre aquele número, e `None` **não** é "não tem":
    é "não sei". Tratar os dois igual recusaria envio legítimo por uma falha
    de rede.

    ⚠️ O PASSO 3 EXISTE POR CAUSA DO BANCO. `ux_conversa_aberta` é único por
    (canal, número) enquanto a conversa não está resolvida: criar outra
    estouraria o índice no meio do envio, que é a pior hora para falhar. Abrir
    a que existe é também o que a pessoa quer -- a fala continua num lugar só.

    ⚠️ IDENTIFICAR DEPOIS, E SÓ QUANDO NÃO HÁ DÚVIDA. `garantir_conversa` já
    liga o contato quando o número responde por UM cadastro. Vários cadastros
    continuam como sugestão na gaveta, sem escolher: chutar de quem é produz
    ficha errada, que é pior que ficha nenhuma.
    """
    from . import evolution  # tardio: evolution não conhece conversas

    texto = (texto or "").strip()
    if not texto:
        return {"ok": False, "motivo": "Escreva a mensagem antes de enviar."}

    analise = tel.analisar(numero_digitado)
    e164 = analise.e164 if analise else None
    if not e164:
        return {"ok": False,
                "motivo": "Não entendi este número. Use DDD + número, "
                          "como (18) 99811-6168."}

    canal = banco.um(
        "SELECT id, instancia, tipo FROM canal WHERE id = %s AND ativo",
        (canal_id,))
    if not canal or not canal["instancia"]:
        return {"ok": False, "motivo": "Canal inválido ou sem instância."}

    # ---- 2. o WhatsApp existe? ---------------------------------------------
    try:
        existe = evolution.tem_whatsapp(canal["instancia"], e164)
    except Exception as e:                                    # noqa: BLE001
        log.warning("nova conversa: falha ao consultar o WhatsApp de %s (%s)",
                    e164, e.__class__.__name__)
        return {"ok": False,
                "motivo": "Não consegui perguntar ao WhatsApp se este número "
                          "existe. Tente de novo em instantes."}

    if existe is False:
        return {"ok": False, "sem_whatsapp": True, "e164": e164,
                "motivo": "Este número não tem WhatsApp. Confira os dígitos e "
                          "teste por um celular antes de cadastrar."}
    if existe is None:
        return {"ok": False,
                "motivo": "O WhatsApp não respondeu sobre este número. Como "
                          "não dá para saber, não enviei."}

    # ---- 3 e 4. abrir a que existe, ou criar --------------------------------
    aberta = banco.um(
        """SELECT id FROM conversa
            WHERE canal_id = %s AND telefone_e164 = %s AND estado <> 'resolvida'""",
        (canal_id, e164))
    if aberta:
        conversa_id, nasceu = aberta["id"], False
    else:
        with banco.cursor() as cur:
            conversa_id = garantir_conversa(cur, canal_id, e164)
            if atendente_id:
                cur.execute(
                    """UPDATE conversa SET atendente_id = %s, estado = 'humano',
                                           atualizada_em = now()
                        WHERE id = %s AND atendente_id IS NULL""",
                    (atendente_id, conversa_id))
        nasceu = True

    # ---- 5. envia pelo caminho normal --------------------------------------
    enviado = responder(conversa_id, texto, atendente_id)
    if not enviado.get("ok"):
        # ⚠️ A conversa recém-criada NÃO é apagada aqui. Ela já existe, e o
        # que falhou foi o envio -- a pessoa vê a conversa aberta e tenta de
        # novo. Apagar deixaria a tela sem para onde voltar.
        return {"ok": False, "conversa_id": conversa_id,
                "motivo": enviado.get("motivo", "Não consegui enviar.")}

    # ---- 6. identificar depois ---------------------------------------------
    linha = banco.um(
        """SELECT c.contato_id, ct.nome AS contato_nome, cl.nome AS cliente_nome
             FROM conversa c
             LEFT JOIN contato ct ON ct.id = c.contato_id
             LEFT JOIN cliente cl ON cl.id = ct.cliente_id
            WHERE c.id = %s""", (conversa_id,))

    log.info("conversa %s iniciada pelo painel para %s (nova=%s)",
             conversa_id, e164, nasceu)
    return {"ok": True, "conversa_id": conversa_id, "nasceu": nasceu,
            "e164": e164,
            "identificada": bool(linha and linha["contato_id"]),
            "contato_nome": linha["contato_nome"] if linha else None,
            "cliente_nome": linha["cliente_nome"] if linha else None}


def responder_com_arquivo(conversa_id: int, dados: bytes, mime: str,
                          nome_arquivo: str, legenda: str,
                          atendente_id: int | None) -> dict:
    """Manda um arquivo para o cliente. Espelha `responder` em tudo que importa.

    🚨 O NÚMERO VEM DA CONVERSA, NUNCA DO QUE FOI ENVIADO. Mesma razão de
    `responder`: esta função responde uma conversa que já existe.

    🚨 ENVIA PRIMEIRO, GRAVA DEPOIS. O contrário registraria como enviado um
    arquivo que o WhatsApp recusou -- e o atendente acharia que mandou.

    🚨 GRAVA COM O `key.id` QUE O WHATSAPP DEVOLVEU, pelo mesmo motivo do
    texto: o Evolution ecoa a nossa própria mensagem pelo webhook, e sem o id
    o eco vira um segundo balão igual.

    ⚠️ O ARQUIVO É GUARDADO NO DISCO como o que chega do cliente, e pelo mesmo
    caminho (`midia.guardar`). Sem isso o balão de saída ficaria sem o anexo:
    o eco do Evolution traz a mídia, mas a mensagem já existe pelo `id_externo`
    e o eco é ignorado -- então quem grava tem de ser este envio.
    """
    from . import evolution  # tardio: evolution não conhece conversas

    if not dados:
        return {"ok": False, "motivo": "Arquivo vazio."}
    if len(dados) > TETO_ARQUIVO:
        return {"ok": False,
                "motivo": f"O arquivo tem {len(dados) / 1024 / 1024:.1f} MB e o "
                          f"teto é {TETO_ARQUIVO_MB} MB."}
    legenda = (legenda or "").strip()
    if len(legenda) > TETO_MENSAGEM:
        return {"ok": False, "motivo": "Legenda longa demais."}

    conversa_atual = banco.um(
        """SELECT c.id, c.telefone_e164, c.estado, c.atendente_id, ca.instancia,
                  c.tipo, c.grupo_jid,
                  -- 🚨 O DESTINO DO ENVIO. Conversa direta vai para o
                  -- telefone; grupo vai para o JID. Os dois saem da CONVERSA:
                  -- responder é responder ESTA conversa. Falar com quem ainda
                  -- não escreveu é `iniciar_conversa`.
                  COALESCE(c.grupo_jid, c.telefone_e164) AS destino
             FROM conversa c JOIN canal ca ON ca.id = c.canal_id
            WHERE c.id = %s""", (conversa_id,))
    if not conversa_atual:
        return {"ok": False, "motivo": "Conversa não encontrada."}
    if conversa_atual["estado"] == "resolvida":
        return {"ok": False,
                "motivo": "Conversa encerrada. Reabra ou espere o cliente escrever."}
    if not conversa_atual["instancia"]:
        return {"ok": False, "motivo": "O canal desta conversa não tem instância."}

    # Quem responde assume, igual ao texto.
    if conversa_atual["atendente_id"] is None and atendente_id:
        banco.executar(
            """UPDATE conversa SET atendente_id = %s, estado = 'humano',
                                   atualizada_em = now()
                WHERE id = %s AND atendente_id IS NULL""",
            (atendente_id, conversa_id))

    tipo = evolution.tipo_de_midia(mime)
    try:
        enviado = evolution.enviar_midia(
            conversa_atual["instancia"], conversa_atual["destino"],
            base64.b64encode(dados).decode("ascii"), mime, nome_arquivo, legenda)
    except evolution.ErroEvolution as e:
        log.warning("conversa %s: arquivo recusado pelo Evolution: %s",
                    conversa_id, e)
        return {"ok": False, "motivo": f"O WhatsApp recusou: {e}"}

    nosso = _TIPO_POR_FAMILIA.get((mime or "").split("/")[0], "documento")
    with banco.cursor() as cur:
        midia_id = midia_mod.guardar(cur, conversa_id, {
            "dados": dados, "mime": mime, "tipo": nosso,
            "nome_original": nome_arquivo,
        })
        cur.execute(
            """INSERT INTO mensagem
                   (conversa_id, id_externo, direcao, autor, tipo, conteudo,
                    atendente_id, entrega, midia_id, criada_em)
               VALUES (%s, %s, 'saida', 'atendente', %s, %s, %s, 'enviada', %s, now())
               ON CONFLICT (id_externo) WHERE id_externo IS NOT NULL DO NOTHING
               RETURNING id""",
            (conversa_id, enviado["id_externo"], nosso,
             legenda or None, atendente_id, midia_id))
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
            "midia_id": midia_id,
            "id_externo": enviado["id_externo"]}


def anotar_com_arquivo(conversa_id: int, dados: bytes, mime: str,
                       nome_arquivo: str, texto: str,
                       atendente_id: int | None) -> dict:
    """Nota interna COM arquivo anexado. Decisão do usuário em 12/08.

    🚨 O ARQUIVO NÃO SAI PARA O CLIENTE, e a garantia é estrutural: esta
    função não chama o `evolution` em lugar nenhum. É o mesmo contrato da nota
    de texto -- o CHECK do banco amarra `tipo = 'nota'` a `direcao = 'interna'`.

    ⚠️ Eu tinha bloqueado anexo em nota, com o argumento de que "prometeria um
    arquivo que o cliente nunca receberia". O argumento estava errado: anexar
    o print de um erro ou o PDF que o cliente mandou por outro canal é
    exatamente o que se quer guardar na conversa sem enviar nada.
    """
    if not dados:
        return {"ok": False, "motivo": "Arquivo vazio."}
    if len(dados) > TETO_ARQUIVO:
        return {"ok": False,
                "motivo": f"O arquivo tem {len(dados) / 1024 / 1024:.1f} MB e o "
                          f"teto é {TETO_ARQUIVO_MB} MB."}
    texto = (texto or "").strip()
    if len(texto) > TETO_MENSAGEM:
        return {"ok": False, "motivo": "Texto da nota longo demais."}
    if not banco.um("SELECT id FROM conversa WHERE id = %s", (conversa_id,)):
        return {"ok": False, "motivo": "Conversa não encontrada."}

    with banco.cursor() as cur:
        midia_id = midia_mod.guardar(cur, conversa_id, {
            "dados": dados, "mime": mime,
            "tipo": _TIPO_POR_FAMILIA.get((mime or "").split("/")[0], "documento"),
            "nome_original": nome_arquivo,
        })
        cur.execute(
            """INSERT INTO mensagem
                   (conversa_id, direcao, autor, tipo, conteudo, atendente_id,
                    midia_id, criada_em)
               VALUES (%s, 'interna', 'atendente', 'nota', %s, %s, %s, now())
               RETURNING id""",
            (conversa_id, texto or None, atendente_id, midia_id))
        nova = cur.fetchone()
    return {"ok": True, "conversa_id": conversa_id,
            "mensagem_id": nova["id"], "midia_id": midia_id}


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


def encerrar(conversa_id: int, classificacao_id: int | None = None,
             comentario: str | None = None,
             atendente_id: int | None = None) -> dict:
    """Conclui o atendimento. Classificar é OPCIONAL desde 11/08.

    ⚠️ A TELA CHAMA ISTO DE "CONCLUIR ATENDIMENTO" desde 25/08. O nome interno
    e a rota continuam `encerrar`: rótulo é da tela, e renomear rota derruba
    quem estiver com o painel aberto no meio do deploy.

    🚨 ERA OBRIGATÓRIO, E A OBRIGATORIEDADE ERA CIRCULAR. O escopo (docs/01,
    item 11) justificava com "é o que alimenta analytics depois" -- mas
    `REL_1.1` é Fase 3, não existe, e nunca houve conversa classificada. Os 9
    rótulos eram invenção minha, e travavam o encerramento de qualquer conversa.

    Volta a ser obrigatória quando houver analytics E uma lista que alguém
    pediu. Até lá, quem quiser classificar classifica; quem não quiser fecha.

    ⚠️ Se vier classificação, ela continua sendo validada: id inexistente ou
    inativo é erro, e a que exige comentário continua exigindo. Aceitar
    qualquer número faria o histórico apontar para nada.

    ----------------------------------------------------------------------
    O QUE MUDOU EM 25/08 (decisão do usuário)

    🚨 CONCLUIR SOLTA O DONO: `atendente_id` volta a NULL e a conversa aparece
    em "sem dono". Concluir é conclusão do ATENDIMENTO, não posse do assunto --
    e conversa fechada que continua contando como "minha" fazia o painel de
    quem atende nunca esvaziar.

    🚨 POR ISSO `resolvida_por` EXISTE (migração 029). Soltar o dono sem
    gravar quem concluiu apagaria o desfecho: `atendente_id` era o único lugar
    onde o autor do fechamento aparecia. Grava-se ANTES de soltar, na mesma
    instrução -- não são dois passos que podem ficar pela metade.

    ⚠️ CONCLUIR VALE COM OUTRAS PESSOAS DENTRO, e os convidados saem junto.
    Quem quer apenas se retirar usa `sair()`, que deixa a conversa com quem
    ficou. São ações diferentes e continuam diferentes.
    """
    conversa_atual = banco.um(
        "SELECT id, criada_em, estado, atendente_id FROM conversa WHERE id = %s",
        (conversa_id,))
    if not conversa_atual:
        return {"ok": False, "motivo": "Conversa não encontrada."}
    if conversa_atual["estado"] == "resolvida":
        return {"ok": False, "motivo": "Este atendimento já foi concluído."}

    classificacao = None
    if classificacao_id is not None:
        classificacao = banco.um(
            "SELECT id, nome, exige_comentario FROM classificacao "
            "WHERE id = %s AND ativo", (classificacao_id,))
        if not classificacao:
            return {"ok": False, "motivo": "Classificação inexistente ou inativa."}

    comentario = (comentario or "").strip() or None
    if classificacao and classificacao["exige_comentario"] and not comentario:
        return {"ok": False,
                "motivo": f"A classificação {classificacao['nome']!r} exige um "
                          f"comentário dizendo o que foi."}

    # ⚠️ Quem chamou sem dizer o autor (teste, rotina) cai no dono de então:
    # é a melhor resposta disponível, e é melhor que NULL. Nunca o contrário --
    # quem concluiu ganha de quem era dono.
    autor = atendente_id or conversa_atual["atendente_id"]

    with banco.cursor() as cur:
        cur.execute(
            """UPDATE conversa
                  SET estado = 'resolvida', resolvida_em = now(),
                      resolvida_por = %s, atendente_id = NULL,
                      classificacao_id = %s, classificacao_texto = %s,
                      segundos_total = EXTRACT(EPOCH FROM (now() - criada_em))::int,
                      atualizada_em = now()
                WHERE id = %s""",
            (autor, classificacao_id, comentario, conversa_id))
        # Os convidados saem junto: conversa concluída não fica na lista de
        # ninguém. `saiu_em` já é como `sair()` marca a saída -- mesmo campo,
        # mesma leitura, e o histórico continua sabendo quem esteve dentro.
        cur.execute(
            """UPDATE conversa_participante SET saiu_em = now()
                WHERE conversa_id = %s AND saiu_em IS NULL""", (conversa_id,))
        sairam = cur.rowcount

    log.info("conversa %s concluída por %s%s%s", conversa_id, autor,
             f" como {classificacao['nome']}" if classificacao else "",
             f", {sairam} participante(s) saíram" if sairam else "")
    return {"ok": True, "conversa_id": conversa_id,
            "resolvida_por": autor, "participantes_saidos": sairam}


def historico(busca: str = "", classificacao_id: int | None = None,
              limite: int = 100) -> list[dict]:
    """ATD_5.1 — os atendimentos concluídos, pesquisáveis.

    ⚠️ A busca por telefone passa pelo normalizador, como em toda a casa: as
    três grafias do mesmo número acham a mesma conversa.

    🚨 O NOME VEM DE `resolvida_por`, COM `atendente_id` DE RESERVA. Desde
    25/08 concluir solta o dono, então o JOIN antigo em `c.atendente_id` daria
    "—" em toda conversa nova -- o histórico passaria a não saber quem atendeu
    justamente a partir do dia em que a regra melhorou. O COALESCE cobre as
    concluídas ANTES da migração 029, que têm dono e não têm `resolvida_por`.
    """
    condicoes, params = ["c.estado = 'resolvida'"], []
    if classificacao_id:
        condicoes.append("c.classificacao_id = %s")
        params.append(classificacao_id)
    # A MESMA regra da caixa de entrada, pela mesma função. Antes de 12/08 aqui
    # se procurava em `ct.nome OR cl.nome` e lá só em `ct.nome`.
    onde_busca, params_busca = _condicao_busca(busca)
    if onde_busca:
        condicoes.append(onde_busca)
        params.extend(params_busca)
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
          LEFT JOIN atendente a
                 ON a.id = COALESCE(c.resolvida_por, c.atendente_id)
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


# ══════════════════════════════════════════════════════════════════════════
# PARTICIPANTES — quem mais está acompanhando a conversa (migração 021)
#
# 🚨 ISTO NÃO É PERMISSÃO. A auditoria de 11/08 mostrou que não existe
# isolamento por conversa: as rotas de atendimento exigem a tela `ATD_1.2` e
# nenhuma pergunta quem é o dono. Convidar faz a conversa APARECER NA LISTA de
# quem foi chamado -- o acesso àquela conversa essa pessoa já tinha.
# ══════════════════════════════════════════════════════════════════════════


def participantes(conversa_id: int) -> list[dict]:
    """Quem está acompanhando agora. Quem saiu não aparece."""
    return banco.varios(
        """SELECT p.atendente_id, a.nome, a.login, p.entrou_em,
                  p.convidado_por, q.nome AS convidado_por_nome
             FROM conversa_participante p
             JOIN atendente a ON a.id = p.atendente_id
             LEFT JOIN atendente q ON q.id = p.convidado_por
            WHERE p.conversa_id = %s AND p.saiu_em IS NULL
            ORDER BY p.entrou_em""", (conversa_id,))


def esta_na_conversa(conversa_id: int, atendente_id: int | None) -> bool:
    """É o dono OU participante ativo. A régua de quem pode AGIR (12/08).

    🚨 ATÉ AQUI NÃO EXISTIA ISOLAMENTO POR CONVERSA, e o efeito não era
    teórico: qualquer atendente com a tela `ATD_1.2` encerrava, transferia e
    devolvia conversa em que não estava. O `souDono || souParticipante` da tela
    governava só o botão *Sair*; os outros ficavam livres, e a rota não
    perguntava nada. Encontrado pelo usuário abrindo a própria conversa depois
    de sair dela.

    ⚠️ LER CONTINUA LIVRE. Isto não fecha a conversa para consulta -- abrir,
    ler o histórico e ver os participantes segue valendo para quem tem
    `ATD_1.2`. O que passa a exigir estar dentro é o que MEXE: responder,
    anotar, encerrar, transferir, devolver e convidar.

    ⚠️ O owner NÃO é exceção. Fazer o dono do sistema passar por cima seria
    justamente perder o registro de quem agiu -- e entrar custa um clique.
    """
    if not atendente_id:
        return False
    linha = banco.um(
        """SELECT 1 FROM conversa c
            WHERE c.id = %s
              AND (c.atendente_id = %s
                   OR EXISTS (SELECT 1 FROM conversa_participante p
                               WHERE p.conversa_id = c.id
                                 AND p.atendente_id = %s
                                 AND p.saiu_em IS NULL))""",
        (conversa_id, atendente_id, atendente_id))
    return linha is not None


def entrar(conversa_id: int, atendente_id: int) -> dict:
    """Entrar por conta própria numa conversa que já tem dono.

    🚨 NÃO EXISTIA CAMINHO PARA ISSO. `convidar` chama OUTRA pessoa e `assumir`
    só funciona em conversa sem dono -- então quem saía de uma conversa com
    dono não tinha como voltar, e quem chegava de fora não tinha como entrar
    sem pedir para alguém convidá-lo.

    ⚠️ ENTRAR NÃO É ASSUMIR. Vira participante; quem responde pela conversa
    continua sendo o dono. Sem dono, o caminho é `assumir`, e a tela oferece
    esse em vez deste.
    """
    conversa_atual = banco.um(
        "SELECT id, atendente_id, estado FROM conversa WHERE id = %s",
        (conversa_id,))
    if not conversa_atual:
        return {"ok": False, "motivo": "Conversa não encontrada."}
    if conversa_atual["estado"] == "resolvida":
        return {"ok": False,
                "motivo": "Conversa encerrada. Reabra para voltar a atender."}
    if conversa_atual["atendente_id"] == atendente_id:
        return {"ok": True, "conversa_id": conversa_id, "papel": "dono"}
    if conversa_atual["atendente_id"] is None:
        return {"ok": False,
                "motivo": "Esta conversa não tem dono — use Assumir."}

    # Reaproveita o caminho do convite: convidado_por = a própria pessoa diz,
    # no histórico, que ninguém a chamou -- ela entrou.
    resultado = convidar(conversa_id, atendente_id, atendente_id)
    if resultado.get("ok"):
        resultado["papel"] = "participante"
    return resultado


def convidar(conversa_id: int, atendente_id: int,
             convidado_por: int | None) -> dict:
    """Chama alguém para a conversa.

    ⚠️ Convite repetido NÃO é erro -- é conflito esperado, a mesma disciplina
    da idempotência de webhook (metodologia §1). Reconvidar quem saiu reabre a
    participação em vez de criar outra linha.
    """
    conversa_atual = banco.um(
        "SELECT id, atendente_id FROM conversa WHERE id = %s", (conversa_id,))
    if not conversa_atual:
        return {"ok": False, "motivo": "Conversa não encontrada."}

    alvo = banco.um("SELECT id, nome, ativo FROM atendente WHERE id = %s",
                    (atendente_id,))
    if not alvo:
        return {"ok": False, "motivo": "Atendente não encontrado."}
    if not alvo["ativo"]:
        return {"ok": False, "motivo": f"{alvo['nome']} está inativo."}

    # 🚨 O dono não é participante: ele é `conversa.atendente_id`. Convidá-lo
    # criaria a mesma pessoa em dois lugares, e a saída dele teria que ser
    # resolvida duas vezes.
    if conversa_atual["atendente_id"] == atendente_id:
        return {"ok": False,
                "motivo": f"{alvo['nome']} já é quem responde por esta conversa."}

    banco.executar(
        """INSERT INTO conversa_participante
               (conversa_id, atendente_id, convidado_por, entrou_em)
           VALUES (%s, %s, %s, now())
           ON CONFLICT (conversa_id, atendente_id) DO UPDATE
              SET saiu_em = NULL,
                  -- 🚨 SÓ quem tinha saído recomeça a contar. Reconvidar quem
                  -- já está dentro não pode mexer em `entrou_em`: a ordem de
                  -- `entrou_em` É A FILA DE HERANÇA da posse, e um convite
                  -- repetido passaria a pessoa para trás sem nada ter mudado.
                  -- Conflito esperado se ignora (metodologia §1).
                  entrou_em = CASE
                      WHEN conversa_participante.saiu_em IS NULL
                          THEN conversa_participante.entrou_em
                      ELSE now() END,
                  convidado_por = CASE
                      WHEN conversa_participante.saiu_em IS NULL
                          THEN conversa_participante.convidado_por
                      ELSE EXCLUDED.convidado_por END""",
        (conversa_id, atendente_id, convidado_por))
    log.info("conversa %s: %s foi convidado", conversa_id, alvo["nome"])
    return {"ok": True, "conversa_id": conversa_id, "atendente_id": atendente_id,
            "nome": alvo["nome"]}


def sair(conversa_id: int, atendente_id: int) -> dict:
    """Sai da conversa. Se quem sai é o DONO, a posse passa para quem ficou.

    Decisão do usuário em 11/08. Os dois casos são diferentes de verdade:

      · participante sai  -> marca `saiu_em`, e nada mais muda;
      · DONO sai          -> o participante ativo mais antigo vira dono, e a
                             transferência fica registrada. Sem ninguém para
                             herdar, a conversa volta para a fila.

    🚨 TUDO NUM CURSOR SÓ, COM A CONVERSA TRAVADA. Entre escolher o herdeiro e
    gravá-lo, o herdeiro pode ter saído -- e a conversa acabaria com um dono
    que não está mais lá. O `FOR UPDATE` serializa as saídas concorrentes, do
    mesmo jeito que o `WHERE atendente_id IS NULL` serializa o `assumir`.
    """
    with banco.cursor() as cur:
        cur.execute("SELECT id, atendente_id, estado FROM conversa "
                    "WHERE id = %s FOR UPDATE", (conversa_id,))
        conversa_atual = cur.fetchone()
        if not conversa_atual:
            return {"ok": False, "motivo": "Conversa não encontrada."}

        era_dono = conversa_atual["atendente_id"] == atendente_id

        cur.execute(
            """UPDATE conversa_participante SET saiu_em = now()
                WHERE conversa_id = %s AND atendente_id = %s AND saiu_em IS NULL
                RETURNING atendente_id""", (conversa_id, atendente_id))
        era_participante = cur.fetchone() is not None

        if not era_dono and not era_participante:
            return {"ok": False, "motivo": "Você não está nesta conversa."}
        if not era_dono:
            return {"ok": True, "conversa_id": conversa_id, "novo_dono": None,
                    "para_fila": False}

        # ── quem sai é o dono: alguém herda
        cur.execute(
            """SELECT p.atendente_id, a.nome FROM conversa_participante p
                 JOIN atendente a ON a.id = p.atendente_id
                WHERE p.conversa_id = %s AND p.saiu_em IS NULL AND a.ativo
                ORDER BY p.entrou_em LIMIT 1""", (conversa_id,))
        herdeiro = cur.fetchone()

        if not herdeiro:
            # ⚠️ Ninguém para herdar: volta para a fila, que é o caminho que já
            # existe para conversa sem dono. Não se inventa estado novo.
            cur.execute(
                """UPDATE conversa SET atendente_id = NULL, estado = 'fila',
                                       atualizada_em = now()
                    WHERE id = %s AND estado <> 'resolvida'""", (conversa_id,))
            cur.execute(
                """INSERT INTO transferencia
                       (conversa_id, de_atendente_id, motivo, resumo)
                   VALUES (%s, %s, 'saida_do_dono', %s)""",
                (conversa_id, atendente_id, "saiu e não havia quem herdasse"))
            log.info("conversa %s voltou para a fila: o dono saiu sem herdeiro",
                     conversa_id)
            return {"ok": True, "conversa_id": conversa_id, "novo_dono": None,
                    "para_fila": True}

        # 🚨 Quem herda deixa de ser participante: agora é o dono. Ficar nos
        # dois lugares faria a próxima saída dele ser tratada duas vezes.
        cur.execute(
            "UPDATE conversa SET atendente_id = %s, atualizada_em = now() "
            "WHERE id = %s", (herdeiro["atendente_id"], conversa_id))
        cur.execute(
            "UPDATE conversa_participante SET saiu_em = now() "
            "WHERE conversa_id = %s AND atendente_id = %s",
            (conversa_id, herdeiro["atendente_id"]))
        cur.execute(
            """INSERT INTO transferencia
                   (conversa_id, de_atendente_id, para_atendente_id, motivo, resumo)
               VALUES (%s, %s, %s, 'saida_do_dono', %s)""",
            (conversa_id, atendente_id, herdeiro["atendente_id"],
             "o dono saiu; herdou quem estava há mais tempo"))
        log.info("conversa %s: dono saiu, %s herdou",
                 conversa_id, herdeiro["nome"])
        return {"ok": True, "conversa_id": conversa_id,
                "novo_dono": herdeiro["atendente_id"],
                "novo_dono_nome": herdeiro["nome"], "para_fila": False}


def remover(conversa_id: int, atendente_id: int, quem_pede: int | None) -> dict:
    """O dono tira alguém da conversa. Decisão do usuário: o próprio sai, e o
    dono também pode remover.

    ⚠️ Não serve para o dono se remover -- para isso existe `sair`, que resolve
    a herança da posse.
    """
    conversa_atual = banco.um(
        "SELECT id, atendente_id FROM conversa WHERE id = %s", (conversa_id,))
    if not conversa_atual:
        return {"ok": False, "motivo": "Conversa não encontrada."}
    if conversa_atual["atendente_id"] != quem_pede:
        return {"ok": False,
                "motivo": "Só quem responde pela conversa pode remover alguém."}
    if atendente_id == quem_pede:
        return {"ok": False, "motivo": "Para sair você mesmo, use 'sair'."}

    linha = banco.um(
        """UPDATE conversa_participante SET saiu_em = now()
            WHERE conversa_id = %s AND atendente_id = %s AND saiu_em IS NULL
            RETURNING atendente_id""", (conversa_id, atendente_id))
    if not linha:
        return {"ok": False, "motivo": "Esta pessoa não está na conversa."}
    return {"ok": True, "conversa_id": conversa_id}
