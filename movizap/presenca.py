"""Presença do atendente — o status por tempo, o "sempre online" e o afastamento.

🔵 Pedidos dele em 24/09:
  · *"painel de regra de tempo por status, igual ao MSN = 15min sem interação
    -Ausente; 1h sem interação Offline"* -- e interação é **só ação de
    atendimento** (resposta dele à pergunta): enviar, abrir, assumir,
    transferir, concluir. Olhar a tela sem agir não conta;
  · *"Não é possivel receber conversa se estiver offline"* (a trava mora em
    `conversas.transferir`);
  · *"Para o owner, pode ter o status para marcar 'sempre online' - dentro da
    jornada que o owner tbm terá, mas será exclusivo dele"*;
  · o modal obrigatório de transferência *"somente em caso de férias ou algo
    do tipo"* -- `afastar()`.

🚨 O SISTEMA SÓ DESFAZ O QUE ELE MESMO FEZ. `estado_automatico` diz se o
estado atual veio da regra. Se veio, a próxima ação devolve a pessoa a
"disponível" (como o MSN voltava a "online" ao mexer no mouse). Se foi a pessoa
quem escolheu, fica -- a regra de 17/09 (*"offline é escolhido"*) caiu por
decisão dele, mas a escolha manual continua sendo respeitada.

🚨 A REGRA NASCE DESLIGADA. Ninguém tinha `ultima_acao_em` antes da 052: ligada
de cara, os 10 iriam para offline no mesmo minuto e deixariam de receber
transferência. Ao ligar, quem está sem registro ganha "agora" como ponto de
partida.
"""
import asyncio
import logging
from datetime import date, datetime, timezone

from . import banco

log = logging.getLogger("movizap.presenca")

INTERVALO_SEG = 60

CHAVE_LIGADA = "presenca_regra_ligada"
CHAVE_MIN_AUSENTE = "presenca_minutos_ausente"
CHAVE_MIN_OFFLINE = "presenca_minutos_offline"
CHAVE_MSG_LIGADA = "fora_expediente_ligada"
CHAVE_MSG_TEXTO = "fora_expediente_texto"

PADRAO_AUSENTE = 15
PADRAO_OFFLINE = 60
TETO_TEXTO = 4000

MENSAGEM_OFFLINE = ("O atendente escolhido está offline e não poderá continuar "
                    "o atendimento.")


# A MESMA exceção de `operacao`: é ela que `main.py` transforma em 400 com a
# frase. Uma classe própria aqui chegaria à tela como 500.
from .operacao import DadoInvalido  # noqa: E402


# ---------------------------------------------------------------- config

def _ler(chave: str) -> str | None:
    linha = banco.um("SELECT valor FROM config WHERE chave = %s", (chave,))
    return linha["valor"] if linha else None


def _gravar(cur, chave: str, valor: str, descricao: str) -> None:
    cur.execute(
        """INSERT INTO config (chave, valor, descricao, atualizado_em)
           VALUES (%s, %s, %s, now())
           ON CONFLICT (chave) DO UPDATE
              SET valor = EXCLUDED.valor, atualizado_em = now()""",
        (chave, valor, descricao))


def _inteiro(valor: str | None, padrao: int) -> int:
    try:
        return int(valor) if valor is not None else padrao
    except ValueError:
        return padrao


def config() -> dict:
    """As regras como a tela as mostra."""
    return {
        "regra_ligada": _ler(CHAVE_LIGADA) == "true",
        "minutos_ausente": _inteiro(_ler(CHAVE_MIN_AUSENTE), PADRAO_AUSENTE),
        "minutos_offline": _inteiro(_ler(CHAVE_MIN_OFFLINE), PADRAO_OFFLINE),
        "mensagem_ligada": _ler(CHAVE_MSG_LIGADA) == "true",
        "mensagem_texto": _ler(CHAVE_MSG_TEXTO) or "",
    }


def definir_config(regra_ligada: bool, minutos_ausente: int, minutos_offline: int,
                   mensagem_ligada: bool, mensagem_texto: str) -> dict:
    if not 1 <= int(minutos_ausente) <= 24 * 60:
        raise DadoInvalido("O tempo para Ausente vai de 1 minuto a 24 horas.")
    if not 1 <= int(minutos_offline) <= 24 * 60:
        raise DadoInvalido("O tempo para Offline vai de 1 minuto a 24 horas.")
    if int(minutos_offline) <= int(minutos_ausente):
        raise DadoInvalido("O tempo para Offline tem de ser maior que o de Ausente.")
    texto = (mensagem_texto or "").strip()
    if len(texto) > TETO_TEXTO:
        raise DadoInvalido(f"A mensagem passa de {TETO_TEXTO} caracteres.")
    # ⚠️ Ligar sem texto não manda nada -- e a tela tem de dizer isso em vez de
    # mostrar "ligada" sobre um envio que nunca acontece.
    if mensagem_ligada and not texto:
        raise DadoInvalido("Escreva a mensagem antes de ativá-la.")

    estava_ligada = config()["regra_ligada"]
    with banco.cursor() as cur:
        _gravar(cur, CHAVE_LIGADA, "true" if regra_ligada else "false",
                "Status por tempo sem ação de atendimento. Nasce desligada.")
        _gravar(cur, CHAVE_MIN_AUSENTE, str(int(minutos_ausente)),
                "Minutos sem ação de atendimento até Ausente.")
        _gravar(cur, CHAVE_MIN_OFFLINE, str(int(minutos_offline)),
                "Minutos sem ação de atendimento até Offline.")
        _gravar(cur, CHAVE_MSG_LIGADA, "true" if mensagem_ligada else "false",
                "Mensagem automática de fim de expediente. Nasce desligada.")
        _gravar(cur, CHAVE_MSG_TEXTO, texto,
                "Texto da mensagem de fim de expediente.")
        if regra_ligada and not estava_ligada:
            # 🚨 O PONTO DE PARTIDA. Sem isto, quem nunca agiu desde a 052
            # contaria como parado desde sempre e cairia em offline agora.
            cur.execute("UPDATE atendente SET ultima_acao_em = now() "
                        "WHERE ultima_acao_em IS NULL")
    log.info("presença: regra %s (%s/%s min), mensagem %s",
             "ligada" if regra_ligada else "desligada",
             minutos_ausente, minutos_offline,
             "ligada" if mensagem_ligada else "desligada")
    return config()


# ---------------------------------------------------------------- ação

def registrar_acao(atendente_id: int | None) -> None:
    """Uma AÇÃO DE ATENDIMENTO aconteceu. Zera o relógio e, se o estado atual
    foi posto pela regra, devolve a pessoa a "disponível".

    ⚠️ Roda mesmo com a regra desligada: o relógio precisa estar certo no dia
    em que ela for ligada. Custa um UPDATE por ação.
    """
    if not atendente_id:
        return
    banco.executar(
        """UPDATE atendente
              SET ultima_acao_em = now(),
                  estado = CASE WHEN estado_automatico THEN 'disponivel' ELSE estado END,
                  estado_automatico = false
            WHERE id = %s""", (atendente_id,))


def definir_estado_manual(atendente_id: int, estado: str) -> None:
    """A pessoa escolheu o estado. Conta como ação (senão, quem escolhe
    "disponível" depois de 2 h parado voltaria a offline no minuto seguinte).

    🔵 25/09: AFASTADO NÃO MUDA O ESTADO POR AQUI. Até então, escolher um
    estado apagava o afastamento sem aviso. Agora a barra fica travada, e o
    caminho de volta é o dele: *"ela loga e vai na configuração dela e coloca
    o dia de ontem"* (`definir_minha_volta`).
    """
    linha = banco.um("SELECT afastamento_motivo, afastado_ate FROM atendente "
                     "WHERE id = %s", (atendente_id,))
    if linha and linha["afastamento_motivo"]:
        ate = (f" até {linha['afastado_ate']:%d/%m}" if linha["afastado_ate"] else "")
        raise DadoInvalido(
            f"Você está afastado{ate}. Para voltar antes, mude a data de volta "
            "na Minha conta.")
    banco.executar(
        """UPDATE atendente
              SET estado = %s, estado_automatico = false,
                  ultima_acao_em = now(), atualizado_em = now()
            WHERE id = %s""", (estado, atendente_id))


def definir_sempre_online(atendente_id: int, ligado: bool) -> None:
    """Exclusivo do owner -- o CHECK `ck_sempre_online_so_owner` é a outra
    ponta, e quem chama recusa antes para a mensagem ser legível."""
    banco.executar(
        "UPDATE atendente SET sempre_online = %s, atualizado_em = now() WHERE id = %s",
        (bool(ligado), atendente_id))


# ---------------------------------------------------------------- a regra

def _protegidos(agora: datetime) -> list[int]:
    """Owners com "sempre online" DENTRO da jornada deles agora."""
    from .operacao import em_jornada  # tardio: operacao é grande e não precisa disto
    return [linha["id"] for linha in banco.varios(
        "SELECT id FROM atendente WHERE sempre_online AND owner AND ativo")
        if em_jornada(linha["id"], agora)]


def aplicar_regra(agora: datetime | None = None, forcar: bool = False,
                  somente: list[int] | None = None) -> dict:
    """Passa a régua: offline primeiro (quem está parado há muito também está
    parado há pouco), depois ausente. Devolve quem mudou.

    ⚠️ `forcar` e `somente` EXISTEM PARA O TESTE, e só para ele. A suíte roda
    no banco de produção, e o laço do serviço lê a mesma `config`: um teste
    que LIGASSE a regra no banco mandaria atendentes reais para offline.
    Com os dois, o teste passa a régua só nas linhas dele, sem tocar a config.
    """
    cfg = config()
    if not cfg["regra_ligada"] and not forcar:
        return {"ligada": False, "ausentes": [], "offline": []}
    agora = agora or datetime.now(timezone.utc)
    protegidos = _protegidos(agora)
    with banco.cursor() as cur:
        cur.execute(
            """UPDATE atendente
                  SET estado = 'offline', estado_automatico = true,
                      atualizado_em = now()
                WHERE ativo AND estado <> 'offline'
                  AND ultima_acao_em < %s - make_interval(mins => %s)
                  AND NOT (id = ANY(%s::bigint[]))
                  AND (%s::bigint[] IS NULL OR id = ANY(%s::bigint[]))
            RETURNING id""", (agora, cfg["minutos_offline"], protegidos,
                              somente, somente))
        offline = [r["id"] for r in cur.fetchall()]
        cur.execute(
            """UPDATE atendente
                  SET estado = 'ausente', estado_automatico = true,
                      atualizado_em = now()
                WHERE ativo AND estado = 'disponivel'
                  AND ultima_acao_em < %s - make_interval(mins => %s)
                  AND NOT (id = ANY(%s::bigint[]))
                  AND (%s::bigint[] IS NULL OR id = ANY(%s::bigint[]))
            RETURNING id""", (agora, cfg["minutos_ausente"], protegidos,
                              somente, somente))
        ausentes = [r["id"] for r in cur.fetchall()]
    if offline or ausentes:
        log.info("presença: %d ausente(s), %d offline", len(ausentes), len(offline))
    return {"ligada": True, "ausentes": ausentes, "offline": offline}


async def rodar(parar: asyncio.Event) -> None:
    """Laço de um minuto. Espelha `vigia.rodar`: a regra tem de valer mesmo
    com ninguém olhando a tela -- é justamente quando ninguém olha que ela
    importa."""
    log.info("presença ativa (a cada %ds)", INTERVALO_SEG)
    while not parar.is_set():
        # 🔵 25/09: as datas do afastamento vêm PRIMEIRO -- quem sai hoje fica
        # offline antes da regra de status e da distribuição olharem.
        try:
            await asyncio.to_thread(aplicar_afastamentos)
        except Exception:                                     # noqa: BLE001
            log.exception("afastamentos falharam -- segue tentando")
        try:
            await asyncio.to_thread(aplicar_regra)
        except Exception:                                     # noqa: BLE001
            log.exception("regra de presença falhou -- segue tentando")
        # 🔵 24/09: a distribuição da fila roda no mesmo minuto, DEPOIS da
        # regra de status -- assim ela já vê quem acabou de ficar offline.
        try:
            from . import distribuicao
            await asyncio.to_thread(distribuicao.distribuir)
        except Exception:                                     # noqa: BLE001
            log.exception("distribuição da fila falhou -- segue tentando")
        try:
            await asyncio.wait_for(parar.wait(), timeout=INTERVALO_SEG)
        except asyncio.TimeoutError:
            pass


# ---------------------------------------------------------------- afastamento

def conversas_abertas(atendente_id: int) -> list[int]:
    return [r["id"] for r in banco.varios(
        """SELECT id FROM conversa
            WHERE atendente_id = %s AND estado <> 'resolvida'
            ORDER BY id""", (atendente_id,))]


def pode_receber(atendente_id: int) -> tuple[bool, str]:
    """Quem pode receber conversa. Mesma régua da transferência."""
    linha = banco.um(
        """SELECT ativo, transferivel, estado, afastamento_motivo
             FROM atendente WHERE id = %s""", (atendente_id,))
    if not linha or not linha["ativo"]:
        return False, "Atendente inexistente ou inativo."
    if not linha["transferivel"]:
        return False, "Esta pessoa não recebe transferência."
    if linha["afastamento_motivo"] or linha["estado"] == "offline":
        return False, MENSAGEM_OFFLINE
    return True, ""


def _hoje_de(atendente_id: int) -> date:
    """O dia de HOJE no fuso da pessoa. 🚨 Não é `date.today()`: o servidor
    roda em UTC, e às 21h de Brasília já é amanhã lá -- o mesmo erro de 3 h que
    `em_jornada` tinha em 24/09."""
    linha = banco.um(
        """SELECT (now() AT TIME ZONE COALESCE(fuso, 'America/Sao_Paulo'))::date AS hoje
             FROM atendente WHERE id = %s""", (atendente_id,))
    return linha["hoje"]


def _pode_substituir(substituto_id: int, atendente_id: int) -> None:
    """O substituto de um afastamento MARCADO: ativo, recebe transferência e
    não é a própria pessoa. Offline hoje não impede -- o que vale é o dia da
    saída, e nesse dia, se ele não puder receber, as conversas vão para a fila.
    """
    if int(substituto_id) == int(atendente_id):
        raise DadoInvalido("Escolha outra pessoa para receber as conversas.")
    linha = banco.um("SELECT ativo, transferivel FROM atendente WHERE id = %s",
                     (substituto_id,))
    if not linha or not linha["ativo"]:
        raise DadoInvalido("Quem vai receber as conversas está inativo ou não existe.")
    if not linha["transferivel"]:
        raise DadoInvalido("Esta pessoa não recebe transferência.")


def _para_a_fila(cur, conversa_id: int, atendente_id: int, texto: str) -> None:
    """Solta a conversa para a fila, com nota do sistema dizendo por quê.
    Mesmo efeito que o antigo "desligar" tinha, uma conversa por vez."""
    cur.execute(
        """UPDATE conversa SET atendente_id = NULL, estado = 'fila',
                               atualizada_em = now()
            WHERE id = %s AND atendente_id = %s AND estado <> 'resolvida'""",
        (conversa_id, atendente_id))
    if not cur.rowcount:
        return  # alguém já a pegou, ou foi concluída no meio do caminho
    cur.execute(
        """UPDATE conversa_participante SET saiu_em = now()
            WHERE conversa_id = %s AND atendente_id = %s AND saiu_em IS NULL""",
        (conversa_id, atendente_id))
    cur.execute(
        """INSERT INTO mensagem (conversa_id, direcao, autor, tipo, conteudo, criada_em)
           VALUES (%s, 'interna', 'sistema', 'nota', %s, now())""",
        (conversa_id, texto))


def transferir_abertas(atendente_id: int, substituto_id: int | None,
                       texto_resumo: str, fila_se_falhar: bool) -> dict:
    """Passa as conversas abertas da pessoa para o substituto.

    ⚠️ CADA CONVERSA É UMA TRANSFERÊNCIA PRÓPRIA, pelo caminho de sempre
    (`conversas.transferir`), com rastro e nota. Com `fila_se_falhar` (o laço
    no dia da saída, e o inativar sem ninguém para receber), a que não puder
    ir ao substituto vai para a fila. Sem ele (quem clica na tela escolheu um
    substituto), a falha volta para a tela decidir.
    """
    from . import conversas  # tardio: conversas importa módulos que importam este

    abertas = conversas_abertas(atendente_id)
    pode = bool(substituto_id) and pode_receber(int(substituto_id))[0]
    falhas, para_fila = [], []
    for conversa_id in abertas:
        r = (conversas.transferir(conversa_id, None, int(substituto_id), "manual",
                                  de_atendente_id=atendente_id,
                                  texto_resumo=texto_resumo)
             if pode else {"ok": False, "motivo": MENSAGEM_OFFLINE})
        if r.get("ok"):
            continue
        if fila_se_falhar:
            para_fila.append(conversa_id)
        else:
            falhas.append({"conversa_id": conversa_id, "motivo": r.get("motivo")})
    if para_fila:
        with banco.cursor() as cur:
            for conversa_id in para_fila:
                _para_a_fila(cur, conversa_id, atendente_id,
                             f"Voltou para a fila: {texto_resumo}")
    return {"abertas": len(abertas), "falhas": falhas, "na_fila": len(para_fila)}


def afastar(atendente_id: int, motivo: str, ate: date | None,
            transferir_para: int | None, de: date | None = None) -> dict:
    """Férias, licença... com o dia da SAÍDA e o da VOLTA.

    🔵 25/09: *"ao definir o motivo, um calendário já indica a saída e a volta,
    daí volta"*. A volta é obrigatória -- é ela que encerra sozinha.

    · Saída HOJE: transfere agora e deixa offline, como sempre foi. 🔵 24/09:
      *"em caso de conversas em aberto, perguntar para qual usuario transferir
      elas ... é obrigatório e dai executa"* -- e, se uma transferência falhar,
      a pessoa NÃO é afastada, para ninguém ficar offline segurando conversa.
    · Saída FUTURA: só marca (`afasta_*`). 🔵 *"No dia da saída"* o laço
      transfere para o substituto escolhido aqui -- obrigatório também, porque
      até lá podem chegar conversas.
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise DadoInvalido("Diga o motivo do afastamento (férias, licença...).")
    if len(motivo) > 60:
        raise DadoInvalido("O motivo passa de 60 caracteres.")
    alvo = banco.um(
        """SELECT id, nome, ativo, afastamento_motivo, afasta_em
             FROM atendente WHERE id = %s""", (atendente_id,))
    if not alvo or not alvo["ativo"]:
        raise DadoInvalido("Atendente inexistente ou inativo.")
    if alvo["afastamento_motivo"]:
        raise DadoInvalido(f"{alvo['nome']} já está afastado. Encerre o afastamento atual antes.")
    if alvo["afasta_em"]:
        raise DadoInvalido(
            f"{alvo['nome']} já tem afastamento marcado para {alvo['afasta_em']:%d/%m}. "
            "Cancele o marcado antes.")

    hoje = _hoje_de(atendente_id)
    de = de or hoje
    if de < hoje:
        raise DadoInvalido("A saída não pode ser num dia que já passou.")
    if not ate:
        raise DadoInvalido("Escolha o dia da volta.")
    if ate <= de:
        raise DadoInvalido("A volta tem de ser depois da saída.")

    if de > hoje:
        if not transferir_para:
            raise DadoInvalido("Escolha quem vai receber as conversas no dia da saída.")
        _pode_substituir(transferir_para, atendente_id)
        banco.executar(
            """UPDATE atendente
                  SET afasta_em = %s, afasta_ate = %s, afasta_motivo = %s,
                      afasta_substituto_id = %s, atualizado_em = now()
                WHERE id = %s""", (de, ate, motivo, int(transferir_para), atendente_id))
        log.info("atendente %s: afastamento marcado de %s a %s (%s)",
                 atendente_id, de, ate, motivo)
        return {"ok": True, "agendado": True, "transferidas": 0}

    abertas = conversas_abertas(atendente_id)
    if abertas:
        if not transferir_para:
            raise DadoInvalido(
                f"{alvo['nome']} tem {len(abertas)} conversa(s) em aberto: "
                "escolha quem vai recebê-las.")
        if int(transferir_para) == int(atendente_id):
            raise DadoInvalido("Escolha outra pessoa para receber as conversas.")
        ok, motivo_recusa = pode_receber(int(transferir_para))
        if not ok:
            raise DadoInvalido(motivo_recusa)

    r = transferir_abertas(atendente_id, transferir_para,
                           f"{alvo['nome']} entrou em afastamento ({motivo}).",
                           fila_se_falhar=False)
    if r["falhas"]:
        return {"ok": False, "transferidas": r["abertas"] - len(r["falhas"]),
                "falhas": r["falhas"]}
    _comecar(atendente_id, motivo, de, ate)
    log.info("atendente %s afastado (%s) até %s; %d conversa(s) transferida(s)",
             atendente_id, motivo, ate, r["abertas"])
    return {"ok": True, "agendado": False, "transferidas": r["abertas"]}


def _comecar(atendente_id: int, motivo: str, de: date, ate: date) -> None:
    banco.executar(
        """UPDATE atendente
              SET estado = 'offline', estado_automatico = false,
                  afastamento_motivo = %s, afastado_de = %s, afastado_ate = %s,
                  afasta_em = NULL, afasta_ate = NULL, afasta_motivo = NULL,
                  afasta_substituto_id = NULL,
                  atualizado_em = now()
            WHERE id = %s""", (motivo, de, ate, atendente_id))


def aplicar_afastamentos(somente: list[int] | None = None) -> dict:
    """O laço do minuto: começa os marcados para hoje e encerra os que chegaram
    ao dia da volta. Roda sempre -- não depende da regra de status.

    ⚠️ `somente` EXISTE PARA O TESTE: a suíte roda no banco de produção.

    🟡 Na volta automática a pessoa volta OFFLINE: à meia-noite ela não está
    diante da tela, e "disponível" faria chegar transferência a quem ainda não
    entrou. O estado se acerta quando ela escolhe na barra.
    """
    iniciados = []
    for linha in banco.varios(
            """SELECT id, nome, afasta_em, afasta_ate, afasta_motivo,
                      afasta_substituto_id
                 FROM atendente
                WHERE ativo AND afasta_em IS NOT NULL
                  AND afasta_em <= (now() AT TIME ZONE COALESCE(fuso, 'America/Sao_Paulo'))::date
                  AND (%s::bigint[] IS NULL OR id = ANY(%s::bigint[]))""",
            (somente, somente)):
        r = transferir_abertas(
            linha["id"], linha["afasta_substituto_id"],
            f"{linha['nome']} entrou em afastamento ({linha['afasta_motivo']}).",
            fila_se_falhar=True)
        _comecar(linha["id"], linha["afasta_motivo"], linha["afasta_em"], linha["afasta_ate"])
        log.info("afastamento marcado começou: atendente %s (%d transferida(s), %d na fila)",
                 linha["id"], r["abertas"] - r["na_fila"], r["na_fila"])
        iniciados.append(linha["id"])

    encerrados = [r["id"] for r in banco.varios(
        """UPDATE atendente
              SET afastamento_motivo = NULL, afastado_de = NULL, afastado_ate = NULL,
                  estado = 'offline', estado_automatico = false,
                  ultima_acao_em = now(), atualizado_em = now()
            WHERE afastamento_motivo IS NOT NULL AND afastado_ate IS NOT NULL
              AND afastado_ate <= (now() AT TIME ZONE COALESCE(fuso, 'America/Sao_Paulo'))::date
              AND (%s::bigint[] IS NULL OR id = ANY(%s::bigint[]))
        RETURNING id""", (somente, somente))]
    if encerrados:
        log.info("afastamento encerrado pela data de volta: %s", encerrados)
    return {"iniciados": iniciados, "encerrados": encerrados}


def retornar(atendente_id: int) -> dict:
    """Encerrar, por quem administra: tira o afastamento em curso (a pessoa
    volta disponível, e o relógio começa agora) e cancela o marcado."""
    banco.executar(
        """UPDATE atendente
              SET estado = CASE WHEN afastamento_motivo IS NOT NULL
                                THEN 'disponivel' ELSE estado END,
                  afastamento_motivo = NULL, afastado_de = NULL, afastado_ate = NULL,
                  afasta_em = NULL, afasta_ate = NULL, afasta_motivo = NULL,
                  afasta_substituto_id = NULL,
                  estado_automatico = false,
                  ultima_acao_em = now(), atualizado_em = now()
            WHERE id = %s""", (atendente_id,))
    return {"ok": True}


def definir_minha_volta(atendente_id: int, volta: date) -> dict:
    """🔵 25/09: *"ela loga e vai na configuração dela e coloca o dia de
    ontem"*. A pessoa muda a própria data de volta; hoje ou antes encerra.

    · Afastamento em curso: volta <= hoje encerra agora, e ela fica
      disponível (está diante da tela); depois de hoje, só muda a data.
    · Afastamento marcado: volta <= hoje cancela; senão muda a volta, que
      tem de ser depois da saída.
    """
    linha = banco.um(
        """SELECT afastamento_motivo, afasta_em
             FROM atendente WHERE id = %s""", (atendente_id,))
    if not linha:
        raise DadoInvalido("Atendente não encontrado.")
    hoje = _hoje_de(atendente_id)

    if linha["afastamento_motivo"]:
        if volta <= hoje:
            retornar(atendente_id)
            return {"ok": True, "encerrado": True}
        banco.executar("UPDATE atendente SET afastado_ate = %s, atualizado_em = now() "
                       "WHERE id = %s", (volta, atendente_id))
        return {"ok": True, "encerrado": False, "volta": volta.isoformat()}

    if linha["afasta_em"]:
        if volta <= hoje:
            retornar(atendente_id)
            return {"ok": True, "encerrado": True}
        if volta <= linha["afasta_em"]:
            raise DadoInvalido(
                f"A volta tem de ser depois da saída ({linha['afasta_em']:%d/%m}).")
        banco.executar("UPDATE atendente SET afasta_ate = %s, atualizado_em = now() "
                       "WHERE id = %s", (volta, atendente_id))
        return {"ok": True, "encerrado": False, "volta": volta.isoformat()}

    raise DadoInvalido("Você não está afastado.")
