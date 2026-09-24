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

    🟡 Escolher qualquer estado que não seja offline encerra um afastamento:
    é a pessoa dizendo que voltou.
    """
    banco.executar(
        """UPDATE atendente
              SET estado = %s, estado_automatico = false,
                  ultima_acao_em = now(), atualizado_em = now(),
                  afastamento_motivo = CASE WHEN %s = 'offline'
                                            THEN afastamento_motivo END,
                  afastado_ate = CASE WHEN %s = 'offline' THEN afastado_ate END
            WHERE id = %s""", (estado, estado, estado, atendente_id))


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
        return False, "Atendente inexistente ou desligado."
    if not linha["transferivel"]:
        return False, "Esta pessoa não recebe transferência."
    if linha["afastamento_motivo"] or linha["estado"] == "offline":
        return False, MENSAGEM_OFFLINE
    return True, ""


def afastar(atendente_id: int, motivo: str, ate: date | None,
            transferir_para: int | None) -> dict:
    """Férias, licença... Transfere as conversas abertas e deixa offline.

    🔵 *"em caso de conversas em aberto, perguntar para qual usuario transferir
    elas 'abre modal de lista de usuarios', é obrigatório e dai executa"*.
    Obrigatório aqui também, não só na tela: sem destino, nada acontece.

    ⚠️ CADA CONVERSA É UMA TRANSFERÊNCIA PRÓPRIA, pelo caminho de sempre
    (`conversas.transferir`), com rastro e nota. Se uma falhar, as outras
    seguem e a resposta diz quais ficaram -- e a pessoa NÃO é afastada, para
    ninguém ficar offline segurando conversa.
    """
    from . import conversas  # tardio: conversas importa módulos que importam este

    motivo = (motivo or "").strip()
    if not motivo:
        raise DadoInvalido("Diga o motivo do afastamento (férias, licença...).")
    if len(motivo) > 60:
        raise DadoInvalido("O motivo passa de 60 caracteres.")
    alvo = banco.um("SELECT id, nome, ativo FROM atendente WHERE id = %s",
                    (atendente_id,))
    if not alvo or not alvo["ativo"]:
        raise DadoInvalido("Atendente inexistente ou desligado.")

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

    falhas = []
    for conversa_id in abertas:
        r = conversas.transferir(
            conversa_id, None, int(transferir_para), "manual",
            de_atendente_id=atendente_id,
            texto_resumo=f"{alvo['nome']} entrou em afastamento ({motivo}).")
        if not r.get("ok"):
            falhas.append({"conversa_id": conversa_id, "motivo": r.get("motivo")})
    if falhas:
        return {"ok": False, "transferidas": len(abertas) - len(falhas),
                "falhas": falhas}

    banco.executar(
        """UPDATE atendente
              SET estado = 'offline', estado_automatico = false,
                  afastamento_motivo = %s, afastado_ate = %s,
                  atualizado_em = now()
            WHERE id = %s""", (motivo, ate, atendente_id))
    log.info("atendente %s afastado (%s); %d conversa(s) transferida(s)",
             atendente_id, motivo, len(abertas))
    return {"ok": True, "transferidas": len(abertas)}


def retornar(atendente_id: int) -> dict:
    """Fim do afastamento: volta disponível, e o relógio começa agora."""
    banco.executar(
        """UPDATE atendente
              SET afastamento_motivo = NULL, afastado_ate = NULL,
                  estado = 'disponivel', estado_automatico = false,
                  ultima_acao_em = now(), atualizado_em = now()
            WHERE id = %s""", (atendente_id,))
    return {"ok": True}
