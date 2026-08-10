"""Agenda do Google — só a faixa de HOJE, na tela inicial.

🚨 NÃO É UM CALENDÁRIO. Decisão de 10/08: a tela inicial responde "o que eu
faço agora", e compromisso do dia é exatamente isso. Virar calendário faria a
inicial deixar de ser "o que precisa de você" e virar um Google Agenda pior
que o original -- e aí ninguém usa nenhum dos dois.

⚠️ SÓ LEITURA (`calendar.readonly`). Este módulo não cria, não move e não
apaga compromisso -- nem por engano, porque o token não permite.

⚠️ USA O MESMO REFRESH TOKEN DA CAIXA. É o mesmo cliente OAuth e o mesmo
consentimento; separar em duas autorizações faria a pessoa consentir duas
vezes para a mesma coisa.
"""
import logging
from datetime import datetime, time, timedelta, timezone

import httpx

from . import banco, gmail
from .config import settings

log = logging.getLogger("movizap.agenda")

API = "https://www.googleapis.com/calendar/v3"
TETO = 5          # a faixa mostra poucos: é resumo, não lista


def hoje(conta_id: int | None = None) -> dict:
    """Os próximos compromissos de hoje. Falha em silêncio, de propósito.

    🚨 A AGENDA NUNCA DERRUBA A TELA INICIAL. Ela é um complemento; se o
    Google estiver fora, ou o escopo não tiver sido concedido, a inicial
    continua mostrando conversas e canais. Por isso o erro vira `{eventos: []}`
    com motivo, e não exceção.
    """
    onde = "WHERE ativa" + (" AND id = %s" if conta_id else "")
    conta = banco.um(
        f"SELECT id, endereco, refresh_token FROM email_conta {onde} LIMIT 1",
        (conta_id,) if conta_id else ())
    if not conta:
        return {"eventos": [], "motivo": "nenhuma conta conectada"}

    # 🚨 NÃO USA `gmail._token_de_acesso`: aquela função marca a conta como
    # INATIVA quando o Google recusa o refresh. Uma instabilidade ao buscar
    # COMPROMISSO desligaria a leitura de E-MAIL -- dois recursos diferentes,
    # um derrubando o outro. Aqui a falha só faz a faixa sumir.
    try:
        r = httpx.post(gmail.TROCAR, timeout=20, data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": conta["refresh_token"],
            "grant_type": "refresh_token",
        })
        if r.status_code != 200:
            return {"eventos": [], "motivo": "autorização da agenda expirada"}
        token = r.json()["access_token"]
    except httpx.HTTPError:
        return {"eventos": [], "motivo": "Google fora do ar"}

    agora = datetime.now(timezone.utc).astimezone()
    fim_do_dia = datetime.combine(agora.date(), time(23, 59, 59), agora.tzinfo)

    try:
        r = httpx.get(
            f"{API}/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "timeMin": agora.isoformat(),
                "timeMax": fim_do_dia.isoformat(),
                "singleEvents": "true",      # série vira ocorrência
                "orderBy": "startTime",
                "maxResults": TETO,
            },
            timeout=20)
    except httpx.HTTPError as e:
        log.warning("agenda indisponível: %s", e)
        return {"eventos": [], "motivo": "Google fora do ar"}

    if r.status_code == 403:
        # Escopo não concedido é o caso normal de quem ainda não reautorizou.
        return {"eventos": [], "motivo": "sem permissão de agenda"}
    if r.status_code != 200:
        log.warning("agenda respondeu %s", r.status_code)
        return {"eventos": [], "motivo": f"Google respondeu {r.status_code}"}

    eventos = []
    for e in r.json().get("items") or []:
        inicio = (e.get("start") or {})
        # ⚠️ Evento de dia inteiro vem como `date`, não `dateTime` -- tratar
        # os dois como o mesmo campo é o que faz sumir da tela sem erro.
        quando = inicio.get("dateTime") or inicio.get("date")
        eventos.append({
            "titulo": e.get("summary") or "(sem título)",
            "quando": quando,
            "dia_inteiro": "dateTime" not in inicio,
            "local": e.get("location"),
            "link": e.get("hangoutLink"),
        })

    return {"eventos": eventos, "motivo": None}
