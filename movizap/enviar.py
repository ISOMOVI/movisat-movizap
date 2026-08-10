"""Envio de e-mail pelo painel, com a assinatura do atendente.

🚨 E-MAIL ENVIADO NÃO VOLTA. Mesma régua do WhatsApp: nada de volume antes de
mandar UM e conferir. Este módulo envia uma mensagem por chamada, de propósito
-- não existe função que receba lista de destinatários.

⚠️ SAI SEMPRE DO ENDEREÇO DO ATENDENTE, nunca de um remetente escolhido na
tela. Decisão do usuário em 10/08. O Gmail só aceita enviar como o dono do
token (ou aliases confirmados), então tentar outro remetente falharia -- e
falharia em silêncio, com o Google trocando o `From` sozinho.
"""
import base64
import logging
import mimetypes
import pathlib
from email.message import EmailMessage
from email.utils import make_msgid

import httpx

from . import banco, gmail

log = logging.getLogger("movizap.enviar")

TETO_CORPO = 100_000     # e-mail não é lugar de despejar texto sem fim


class EnvioRecusado(Exception):
    """Motivo em português, pronto para a tela."""


def _assinatura(atendente_id: int | None) -> tuple[str, pathlib.Path | None]:
    if not atendente_id:
        return "", None
    linha = banco.um(
        "SELECT assinatura_html, assinatura_imagem FROM atendente WHERE id = %s",
        (atendente_id,))
    if not linha:
        return "", None
    caminho = None
    if linha["assinatura_imagem"]:
        p = pathlib.Path(linha["assinatura_imagem"])
        # ⚠️ Conferir o disco: assinatura apontando para arquivo que sumiu
        # geraria e-mail com imagem quebrada, que é pior que sem imagem.
        caminho = p if p.is_file() else None
    return (linha["assinatura_html"] or ""), caminho


def enviar(conta_id: int, para: str, assunto: str, corpo: str,
           atendente_id: int | None = None,
           responder_a: int | None = None) -> dict:
    """Manda UMA mensagem. Devolve o id do Gmail, para casar depois.

    `responder_a` é o id de uma mensagem nossa: quando vem, a resposta entra
    na MESMA conversa do Gmail (thread), em vez de abrir uma nova -- que é o
    que faz o cliente ver "Re:" no lugar certo.
    """
    para = (para or "").strip()
    if "@" not in para:
        raise EnvioRecusado("Destinatário inválido.")
    if not (assunto or "").strip():
        raise EnvioRecusado("Escreva um assunto.")
    if len(corpo or "") > TETO_CORPO:
        raise EnvioRecusado("Mensagem longa demais.")

    conta = banco.um(
        "SELECT id, endereco, refresh_token FROM email_conta "
        " WHERE id = %s AND ativa", (conta_id,))
    if not conta:
        raise EnvioRecusado("Caixa não conectada.")

    html_assinatura, imagem = _assinatura(atendente_id)

    msg = EmailMessage()
    msg["To"] = para
    msg["From"] = conta["endereco"]          # sempre o dono do token
    msg["Subject"] = assunto.strip()

    thread = None
    if responder_a:
        alvo = banco.um(
            "SELECT id_externo, thread_externa, assunto FROM email_mensagem "
            " WHERE id = %s", (responder_a,))
        if alvo:
            thread = alvo["thread_externa"]
            # 🚨 `In-Reply-To` é o que faz o cliente ver a resposta ENCAIXADA
            # na conversa. Sem ele o Gmail abre fio novo e a pessoa perde o
            # contexto do que ela mesma escreveu.
            msg["In-Reply-To"] = f"<{alvo['id_externo']}>"
            msg["References"] = f"<{alvo['id_externo']}>"

    corpo_html = (corpo or "").replace("\n", "<br>")
    cid = None
    if imagem:
        cid = make_msgid()
        html_assinatura += f'<br><img src="cid:{cid[1:-1]}" alt="">'

    msg.set_content(corpo or "")             # versão texto, para quem não lê HTML
    msg.add_alternative(
        f"<div>{corpo_html}</div><br>{html_assinatura}", subtype="html")

    if imagem and cid:
        tipo, _ = mimetypes.guess_type(imagem.name)
        principal, _, sub = (tipo or "image/png").partition("/")
        # A imagem vai DENTRO do e-mail: link externo o destinatário pode não
        # carregar, e `data:` URI o Gmail remove.
        msg.get_payload()[1].add_related(
            imagem.read_bytes(), maintype=principal, subtype=sub, cid=cid)

    bruto = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    corpo_envio = {"raw": bruto}
    if thread:
        corpo_envio["threadId"] = thread

    token = gmail._token_de_acesso(conta)
    r = httpx.post(f"{gmail.API}/messages/send",
                   headers={"Authorization": f"Bearer {token}"},
                   json=corpo_envio, timeout=30)
    if r.status_code != 200:
        log.warning("envio recusado: HTTP %s", r.status_code)
        raise EnvioRecusado(f"O Gmail recusou o envio ({r.status_code}).")

    enviado = r.json()
    log.info("e-mail enviado para %s (id %s)", para, enviado.get("id"))
    return {"ok": True, "id_externo": enviado.get("id"),
            "thread": enviado.get("threadId")}
