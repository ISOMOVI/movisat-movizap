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

# Onde o anexo espera até o envio. Fora do projeto, como a mídia: é rascunho,
# e depois de enviado quem guarda a cópia é o Gmail.
PASTA_ANEXOS = pathlib.Path("/home/claude/movizap_anexos")

# 🚨 Teto por mensagem. O Gmail recusa acima de 25 MB, e recusa DEPOIS de
# receber tudo -- o usuário esperaria o upload inteiro para tomar erro. 20 MB
# deixa margem: o base64 do MIME infla o conteúdo em ~33%.
TETO_ANEXOS = 20 * 1024 * 1024


def guardar_anexo(nome: str, dados: bytes) -> dict:
    """Guarda um anexo de rascunho e devolve o ID que o envio vai usar.

    ⚠️ O nome do arquivo vem do cliente e NUNCA vira caminho: cada anexo ganha
    uma pasta com id próprio, e só o nome-base é preservado, para o
    destinatário ver o arquivo com o nome certo.
    """
    import uuid

    if len(dados) > TETO_ANEXOS:
        raise EnvioRecusado("Anexo maior que 20 MB.")

    seguro = pathlib.Path(nome.replace("\\", "/")).name or "arquivo"
    ident = uuid.uuid4().hex
    pasta = PASTA_ANEXOS / ident
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / seguro).write_bytes(dados)
    return {"id": ident, "nome": seguro, "tamanho": len(dados)}


def _resolver_anexos(ids: list[str] | None) -> list[pathlib.Path]:
    """IDs viram caminhos AQUI, no servidor -- nunca no cliente.

    🚨 Se a tela mandasse caminho, `../../.env` viraria anexo e o e-mail sairia
    com o segredo dentro, sem erro nenhum. O id é hexadecimal e resolve para
    uma pasta nossa; qualquer outra coisa é recusada.
    """
    achados = []
    for ident in ids or []:
        if not (ident or "").isalnum():
            raise EnvioRecusado("Anexo inválido.")
        pasta = PASTA_ANEXOS / ident
        arquivos = [p for p in pasta.glob("*") if p.is_file()] if pasta.is_dir() else []
        if not arquivos:
            raise EnvioRecusado("Anexo não está mais disponível. Suba de novo.")
        achados.append(arquivos[0])

    total = sum(p.stat().st_size for p in achados)
    if total > TETO_ANEXOS:
        raise EnvioRecusado(
            f"Anexos somam {total/1024/1024:.1f} MB — o teto é 20 MB.")
    return achados


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


def _lista(valor: str | None) -> str:
    """Vários endereços separados por vírgula ou ponto e vírgula.

    ⚠️ Ponto e vírgula é o que o Outlook produz ao copiar contatos, e chega
    colado sem ninguém perceber -- o cabeçalho exige vírgula.
    """
    if not valor:
        return ""
    partes = [p.strip() for p in valor.replace(";", ",").split(",")]
    return ", ".join(p for p in partes if p)


def enviar(conta_id: int, para: str, assunto: str, corpo: str,
           atendente_id: int | None = None,
           responder_a: int | None = None,
           cc: str | None = None, cco: str | None = None,
           html: str | None = None, anexos: list[str] | None = None) -> dict:
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

    if _lista(cc):
        msg["Cc"] = _lista(cc)

    # 🚨 `Bcc` NÃO VIAJA no e-mail entregue. O servidor lê o cabeçalho para
    # decidir para quem mandar e o REMOVE antes da entrega -- é isso que faz a
    # cópia ser oculta. Tratá-lo como Cc mostraria a lista a todo mundo, que é
    # o oposto do que quem usa Cco quer.
    if _lista(cco):
        msg["Bcc"] = _lista(cco)
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

    # 🚨 O EDITOR MANDA HTML. Quando vier, ele É o corpo; `corpo` continua
    # sendo a versão em texto, para quem lê e-mail sem HTML -- e são as duas
    # partes da MESMA mensagem, não duas mensagens.
    corpo_html = html or (corpo or "").replace("\n", "<br>")
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

    # ⚠️ Os anexos entram DEPOIS da assinatura embutida: `add_attachment`
    # transforma a mensagem em `multipart/mixed`, e fazer isso antes deixaria
    # a imagem da assinatura fora do bloco `related` -- ela sumiria.
    for arquivo in _resolver_anexos(anexos):
        tipo, _ = mimetypes.guess_type(arquivo.name)
        principal, _, sub = (tipo or "application/octet-stream").partition("/")
        msg.add_attachment(arquivo.read_bytes(), maintype=principal,
                           subtype=sub or "octet-stream",
                           filename=arquivo.name)

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
