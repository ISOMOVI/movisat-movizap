"""HORA ÚTIL — a conta do prazo do chamado.

🔵 Decisão dele (11/11), com as palavras dele: *"existe a jornada dos
operadores - mas pode usar como regra esse que passei e fazer a conta mesmo.
alias, use 08:30 - 17:00 para calculo, será fixo."*

🚨 A JORNADA DOS ATENDENTES NÃO ENTRA AQUI, E É DE PROPÓSITO. A jornada é
**por pessoa** (`operacao.jornada_do_atendente`, faixas por dia da semana) e
muda quando alguém troca de escala. Prazo de card não pode depender de quem
está escalado hoje: dois cards iguais venceriam em horas diferentes, e o card
mudaria de prazo ao ser transferido.

⚠️ **FERIADO NÃO ENTRA.** Não existe tabela de feriado no sistema -- medido em
11/11 (`grep -rn "feriado"` em `movizap/*.py` = zero) -- e inventar um
calendário nacional seria escopo que ninguém pediu, além de errar nos feriados
municipais, que são os que de fato fecham a operação. Só sábado e domingo saem
da conta. Quando ele quiser feriado, é tabela e é frente própria.

⚠️ **24 HORAS ÚTEIS NÃO É UM DIA.** A janela tem **8,5 h**, então 24 h úteis
são **2 dias e 7 horas**: um chamado aberto na segunda às 09:00 vence na
quarta às 11:30. O número é dele; se o que ele quis dizer foi "um dia útil", o
valor é 8,5 e se troca em `PRAZO_CHAMADO_HORAS`, numa linha.

🚨 ESTE MÓDULO NÃO FALA COM O BANCO NEM COM A REDE. É aritmética de data, e é
por isso que o teste dele não precisa de fixture.
"""
import datetime as dt
import logging
from zoneinfo import ZoneInfo

log = logging.getLogger("movizap.horas_uteis")

FUSO = ZoneInfo("America/Sao_Paulo")

# A janela fixa, dele.
ABRE = dt.time(8, 30)
FECHA = dt.time(17, 0)

# O prazo do chamado, em horas ÚTEIS, contado da abertura até a conclusão.
PRAZO_CHAMADO_HORAS = 24

_SEGUNDOS_NO_DIA = ((FECHA.hour * 3600 + FECHA.minute * 60)
                    - (ABRE.hour * 3600 + ABRE.minute * 60))


def _local(quando: dt.datetime) -> dt.datetime:
    """Traz para `America/Sao_Paulo`. Ingênuo é tratado como local.

    ⚠️ Datetime ingênuo chega de fixture e de JSON solto; assumir UTC aqui
    deslocaria o prazo em 3 horas e o erro só apareceria perto da borda do dia.
    """
    if quando.tzinfo is None:
        return quando.replace(tzinfo=FUSO)
    return quando.astimezone(FUSO)


def _eh_dia_util(dia: dt.date) -> bool:
    return dia.weekday() < 5


def _abertura(dia: dt.date) -> dt.datetime:
    return dt.datetime.combine(dia, ABRE, tzinfo=FUSO)


def _fechamento(dia: dt.date) -> dt.datetime:
    return dt.datetime.combine(dia, FECHA, tzinfo=FUSO)


def dentro_do_expediente(quando: dt.datetime) -> bool:
    q = _local(quando)
    return _eh_dia_util(q.date()) and _abertura(q.date()) <= q < _fechamento(q.date())


def _proximo_inicio(quando: dt.datetime) -> dt.datetime:
    """O primeiro instante útil a partir de `quando` (ele mesmo, se já é útil).

    🚨 Chamado aberto às 19h não começa a contar às 19h: começa às 08:30 do
    próximo dia útil. Sem isto, um chamado da noite de sexta nasceria com meio
    prazo já gasto.
    """
    q = _local(quando)
    for _ in range(14):  # teto: 14 dias cobre qualquer fim de semana
        if _eh_dia_util(q.date()):
            if q < _abertura(q.date()):
                return _abertura(q.date())
            if q < _fechamento(q.date()):
                return q
        q = _abertura(q.date() + dt.timedelta(days=1))
    raise RuntimeError("não achei dia útil em 14 dias — a janela está vazia?")


def segundos_uteis_entre(inicio: dt.datetime, fim: dt.datetime) -> float:
    """Quantos segundos de expediente há entre dois instantes. Nunca negativo."""
    a, b = _local(inicio), _local(fim)
    if b <= a:
        return 0.0
    total = 0.0
    dia = a.date()
    while dia <= b.date():
        if _eh_dia_util(dia):
            de = max(a, _abertura(dia))
            ate = min(b, _fechamento(dia))
            if ate > de:
                total += (ate - de).total_seconds()
        dia += dt.timedelta(days=1)
    return total


def vencimento(inicio: dt.datetime,
               horas: float = PRAZO_CHAMADO_HORAS) -> dt.datetime:
    """Quando vence um prazo de `horas` ÚTEIS contadas de `inicio`.

    ⚠️ O instante devolvido cai SEMPRE dentro do expediente (ou exatamente no
    fechamento), nunca de madrugada nem no domingo -- dizer "vence domingo às
    3h" para um prazo em hora útil seria mentir com precisão.
    """
    restam = float(horas) * 3600.0
    if restam <= 0:
        return _proximo_inicio(inicio)
    atual = _proximo_inicio(inicio)
    for _ in range(400):  # teto: ~1,5 ano de dias úteis
        sobra_hoje = (_fechamento(atual.date()) - atual).total_seconds()
        if restam <= sobra_hoje:
            return atual + dt.timedelta(seconds=restam)
        restam -= sobra_hoje
        atual = _proximo_inicio(_abertura(atual.date() + dt.timedelta(days=1)))
    raise RuntimeError("prazo não fechou em 400 dias úteis")


def prazo_do_chamado(criado_em: dt.datetime | None) -> dict | None:
    """O que o card mostra: quando vence, e se já passou.

    🔵 *"Abrirá com prazo de 24hrs uteis (08:00 - 18:00) para conclusão, apenas
    informativo do card e controle de atraso"* -- com a janela que ele fixou
    depois, 08:30-17:00.

    🚨 **INFORMATIVO, E SÓ.** Nada aqui bloqueia mover, finalizar ou abrir
    card. Prazo que barra gesto é regra de negócio, e ele pediu aviso.

    ⚠️ Devolve `None` sem data de criação, e quem mostra escreve "não medido"
    em vez de inventar um prazo a partir de agora.
    """
    if not criado_em:
        return None
    try:
        vence = vencimento(criado_em, PRAZO_CHAMADO_HORAS)
    except Exception:  # noqa: BLE001 -- card não pode cair por causa de prazo
        log.exception("não consegui calcular o prazo de %r", criado_em)
        return None
    agora = dt.datetime.now(FUSO)
    return {
        "vence_em": vence.isoformat(),
        "horas": PRAZO_CHAMADO_HORAS,
        "atrasado": agora > vence,
        # Quanto falta (ou quanto passou), em segundos ÚTEIS -- é o número que
        # faz sentido para quem trabalha só dentro da janela.
        "segundos_uteis": (
            -segundos_uteis_entre(vence, agora) if agora > vence
            else segundos_uteis_entre(agora, vence)),
        "janela": "%02d:%02d-%02d:%02d" % (ABRE.hour, ABRE.minute,
                                           FECHA.hour, FECHA.minute),
    }
