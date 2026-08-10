"""Leitura da caixa pelo Gmail — só o que a tela precisa, nada além.

🚨 O GMAIL NÃO É EFÊMERO, e isso decide tudo aqui. Diferente do webhook do
Evolution -- que dispara uma vez e não guarda --, a mensagem continua no
Google e é buscável pelo id. Por isso:

  metadados + texto + html  -> guardados (é o que a tela desenha)
  anexo (bytes)             -> NUNCA guardados; só nome/tamanho/tipo
  bruto (RFC822)            -> só quando a mensagem for atendida

Guardar tudo custaria ~360 MB/ano para duplicar o que o Google já guarda, num
banco que tem 16 MB. Ver `migracoes/015`.

⚠️ SÓ LEITURA. O escopo pedido é `gmail.readonly`. Este módulo não marca como
lida, não move, não apaga e não envia -- nem por engano, porque o token não
permite.
"""
import base64
import logging
import pathlib
import time
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime

import httpx

from . import banco
from .config import settings

log = logging.getLogger("movizap.gmail")

API = "https://gmail.googleapis.com/gmail/v1/users/me"
TROCAR = "https://oauth2.googleapis.com/token"

# Teto por execução. A primeira carga de uma caixa antiga pode ter milhares de
# mensagens; puxar tudo numa tacada é o que faz o serviço parecer travado e
# estourar a cota da API. O ponto de retomada fica na conta.
TETO_POR_EXECUCAO = 200


class GmailIndisponivel(Exception):
    """Falha de transporte. NUNCA vira 'não há mensagens'."""


CHAVE_SA = pathlib.Path("/home/claude/movizap_painel/.google_sa.json")

ESCOPOS_SA = " ".join([
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
])


def _token_delegado(endereco: str) -> str:
    """Token agindo COMO `endereco`, sem consentimento individual.

    🚨 A conta de serviço assina um JWT dizendo "sou eu, e quero agir como
    fulano" (campo `sub`). É o que permite o time inteiro usar o painel sem
    cada pessoa autorizar -- e o que faz um atendente novo só precisar existir
    no cadastro.

    ⚠️ A chave lê e envia e-mail de QUALQUER pessoa do domínio. Ela mora em
    `.google_sa.json` com permissão 600, fora do git.
    """
    import json
    import time

    from jose import jwt

    if not CHAVE_SA.is_file():
        raise GmailIndisponivel("Chave da conta de serviço não está no servidor.")

    sa = json.loads(CHAVE_SA.read_text(encoding="utf-8"))
    agora = int(time.time())
    assinado = jwt.encode(
        {"iss": sa["client_email"], "sub": endereco, "scope": ESCOPOS_SA,
         "aud": sa["token_uri"], "iat": agora, "exp": agora + 3600},
        sa["private_key"], algorithm="RS256",
        headers={"kid": sa["private_key_id"]})

    r = httpx.post(sa["token_uri"], timeout=30, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assinado,
    })
    if r.status_code != 200:
        # ⚠️ Nunca registrar o corpo: carrega a asserção assinada.
        log.warning("delegação recusada para %s: HTTP %s", endereco, r.status_code)
        raise GmailIndisponivel(
            f"O Google recusou agir como {endereco}. Confira a delegação "
            f"em todo o domínio no Admin Console.")
    return r.json()["access_token"]


def _token_de_acesso(conta: dict) -> str:
    """Troca o refresh token por um token de 1 hora.

    ⚠️ O refresh token é a credencial de longo prazo e não sai daqui. Se o
    Google recusá-lo, a conta é desativada com motivo -- em vez de o serviço
    tentar para sempre e encher o log.
    """
    # 🚨 OS DOIS CAMINHOS CONVIVEM, de propósito. Conta com token próprio
    # segue usando o dela; conta sem token usa a delegação. Trocar tudo de uma
    # vez faria a caixa que JÁ FUNCIONA depender de algo que nunca rodou em
    # produção -- e a falha apareceria como "caixa vazia", não como erro.
    if not conta.get("refresh_token"):
        return _token_delegado(conta["endereco"])

    resposta = httpx.post(TROCAR, timeout=20, data={
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": conta["refresh_token"],
        "grant_type": "refresh_token",
    })
    if resposta.status_code != 200:
        log.warning("refresh recusado para conta %s: HTTP %s",
                    conta["id"], resposta.status_code)
        banco.executar(
            "UPDATE email_conta SET ativa = false, atualizada_em = now() "
            " WHERE id = %s", (conta["id"],))
        raise GmailIndisponivel(
            "O Google revogou a autorização desta caixa. Autorize de novo.")
    return resposta.json()["access_token"]


def _pedir(cliente: httpx.Client, caminho: str, **params) -> dict:
    r = cliente.get(f"{API}{caminho}", params=params, timeout=30)
    if r.status_code == 429 or r.status_code >= 500:
        # Cota ou instabilidade: é para tentar de novo depois, não para
        # interpretar como caixa vazia.
        raise GmailIndisponivel(f"Gmail respondeu {r.status_code}.")
    if r.status_code != 200:
        raise GmailIndisponivel(f"Gmail recusou {caminho}: {r.status_code}")
    return r.json()


def _texto(parte: dict, acumulado: dict) -> None:
    """Desce o MIME juntando texto e html, e listando anexos sem baixá-los."""
    mime = parte.get("mimeType") or ""
    corpo = parte.get("body") or {}

    if parte.get("filename"):
        acumulado["anexos"].append({
            "nome": parte["filename"],
            "mime": mime,
            "tamanho": corpo.get("size") or 0,
            "id_externo": corpo.get("attachmentId"),
        })
        return

    dados = corpo.get("data")
    if dados:
        try:
            conteudo = base64.urlsafe_b64decode(dados + "=" * (-len(dados) % 4))
            texto = conteudo.decode("utf-8", errors="replace")
        except Exception:
            texto = ""
        if mime == "text/plain" and not acumulado["texto"]:
            acumulado["texto"] = texto
        elif mime == "text/html" and not acumulado["html"]:
            acumulado["html"] = texto

    for filho in parte.get("parts") or []:
        _texto(filho, acumulado)


def _cabecalho(cabecalhos: list, nome: str) -> str:
    for c in cabecalhos:
        if (c.get("name") or "").lower() == nome.lower():
            return c.get("value") or ""
    return ""


def _quando(valor: str) -> datetime | None:
    try:
        return parsedate_to_datetime(valor)
    except (TypeError, ValueError):
        return None


def _identificar(remetente: str) -> tuple[int | None, int | None]:
    """De quem é este e-mail, quando dá para saber com CERTEZA.

    🚨 Mesma regra da conversa de WhatsApp: um dono ou nenhum, nunca um chute
    entre vários. Dois clientes com o mesmo endereço é caso real (contador,
    matriz) -- e escolher um custa mais que deixar NULL.
    """
    if not remetente:
        return None, None
    achados = banco.varios(
        "SELECT id FROM cliente WHERE lower(email) = lower(%s) AND ativo",
        (remetente,))
    cliente_id = achados[0]["id"] if len(achados) == 1 else None

    contatos = banco.varios(
        "SELECT id FROM contato WHERE lower(email) = lower(%s) AND ativo",
        (remetente,))
    contato_id = contatos[0]["id"] if len(contatos) == 1 else None
    return cliente_id, contato_id


def sincronizar_marcadores(conta: dict, cliente: httpx.Client) -> int:
    """Os marcadores são a navegação da tela. Casam pelo ID do provedor.

    🚨 Nome muda ("Financeiro" vira "Fin"); id não. Casar por nome faria a tela
    perder a caixa inteira numa renomeação.
    """
    dados = _pedir(cliente, "/labels")
    n = 0
    for m in dados.get("labels") or []:
        banco.executar(
            """INSERT INTO email_marcador (conta_id, id_externo, nome, natureza)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (conta_id, id_externo)
               DO UPDATE SET nome = EXCLUDED.nome""",
            (conta["id"], m["id"], m.get("name") or m["id"],
             "sistema" if m.get("type") == "system" else "usuario"))
        n += 1
    return n


def marcar_lida(mensagem_id: int) -> dict:
    """Tira o `UNREAD` no Gmail, não só na nossa base.

    🚨 SEM ISTO O PAINEL MENTE. Abrir aqui e continuar não-lida lá faz os dois
    contadores divergirem -- e quem usa os dois desconfia do painel, que é o
    que faz voltar para a ferramenta antiga.

    ⚠️ Escrita REVERSÍVEL de propósito: é a primeira coisa que o painel altera
    na caixa de alguém, e marcar lida se desfaz com um clique.
    """
    linha = banco.um(
        """SELECT m.id, m.id_externo, m.lida, c.id AS conta_id, c.endereco,
                  c.refresh_token
             FROM email_mensagem m JOIN email_conta c ON c.id = m.conta_id
            WHERE m.id = %s""", (mensagem_id,))
    if not linha:
        return {"ok": False, "motivo": "Mensagem não encontrada."}
    if linha["lida"]:
        return {"ok": True, "ja_estava": True}

    token = _token_de_acesso(linha)
    r = httpx.post(
        f"{API}/messages/{linha['id_externo']}/modify",
        headers={"Authorization": f"Bearer {token}"},
        json={"removeLabelIds": ["UNREAD"]}, timeout=30)
    if r.status_code != 200:
        raise GmailIndisponivel(f"O Gmail recusou marcar como lida ({r.status_code}).")

    banco.executar("UPDATE email_mensagem SET lida = true WHERE id = %s",
                   (mensagem_id,))
    banco.executar(
        """DELETE FROM email_mensagem_marcador mm
            USING email_marcador mk
            WHERE mk.id = mm.marcador_id AND mm.mensagem_id = %s
              AND mk.id_externo = 'UNREAD'""", (mensagem_id,))
    return {"ok": True, "ja_estava": False}


def ler(conta_id: int | None = None, limite: int = TETO_POR_EXECUCAO) -> dict:
    """Lê o que ainda não temos. Devolve contadores de FLUXO, não de estoque.

    ⚠️ `novas` é o que ENTROU nesta execução. Contador que devolve o total da
    caixa toda vez não responde "o que mudou desde ontem" -- foi o defeito
    corrigido no sync do Harmonit em 06/08.
    """
    onde = "WHERE ativa" + (" AND id = %s" if conta_id else "")
    contas = banco.varios(
        f"SELECT id, endereco, refresh_token, puxar_desde, guardar_bruto "
        f"FROM email_conta {onde}",
        (conta_id,) if conta_id else ())
    if not contas:
        return {"contas": 0, "novas": 0, "repetidas": 0, "marcadores": 0}

    total = {"contas": len(contas), "novas": 0, "repetidas": 0, "marcadores": 0}

    for conta in contas:
        token = _token_de_acesso(conta)
        with httpx.Client(headers={"Authorization": f"Bearer {token}"}) as cliente:
            total["marcadores"] += sincronizar_marcadores(conta, cliente)

            consulta = ""
            if conta["puxar_desde"]:
                consulta = f"after:{conta['puxar_desde']:%Y/%m/%d}"

            lista = _pedir(cliente, "/messages", q=consulta,
                           maxResults=min(limite, 500))
            for resumo in lista.get("messages") or []:
                ja = banco.um(
                    "SELECT id FROM email_mensagem "
                    " WHERE conta_id = %s AND id_externo = %s",
                    (conta["id"], resumo["id"]))
                if ja:
                    total["repetidas"] += 1
                    continue

                m = _pedir(cliente, f"/messages/{resumo['id']}", format="full")
                carga = m.get("payload") or {}
                cabecalhos = carga.get("headers") or []
                acumulado = {"texto": "", "html": "", "anexos": []}
                _texto(carga, acumulado)

                de = _cabecalho(cabecalhos, "From")
                nome, endereco = parseaddr(de)
                cliente_id, contato_id = _identificar(endereco)

                import json
                banco.executar(
                    """INSERT INTO email_mensagem
                         (conta_id, id_externo, thread_externa, remetente,
                          remetente_nome, destinatarios, assunto, enviado_em,
                          texto, html, tem_anexo, anexos, cliente_id, contato_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (conta_id, id_externo) DO NOTHING""",
                    (conta["id"], m["id"], m.get("threadId"),
                     endereco.lower() or None, nome or None,
                     _cabecalho(cabecalhos, "To") or None,
                     _cabecalho(cabecalhos, "Subject") or None,
                     _quando(_cabecalho(cabecalhos, "Date")),
                     acumulado["texto"] or None, acumulado["html"] or None,
                     bool(acumulado["anexos"]),
                     json.dumps(acumulado["anexos"]),
                     cliente_id, contato_id))

                # 🚨 SEM ISTO O FILTRO DA TELA NÃO TEM COMO FUNCIONAR. O
                # `labelIds` diz em quais pastas a mensagem está -- e uma
                # mensagem está em várias ao mesmo tempo (INBOX + IMPORTANT +
                # UNREAD). Jogar fora deixava a lateral toda zerada.
                nova = banco.um(
                    "SELECT id FROM email_mensagem "
                    " WHERE conta_id = %s AND id_externo = %s",
                    (conta["id"], m["id"]))
                for etiqueta in m.get("labelIds") or []:
                    banco.executar(
                        """INSERT INTO email_mensagem_marcador
                                (mensagem_id, marcador_id)
                           SELECT %s, id FROM email_marcador
                            WHERE conta_id = %s AND id_externo = %s
                           ON CONFLICT DO NOTHING""",
                        (nova["id"], conta["id"], etiqueta))

                # `UNREAD` é marcador no Gmail, não coluna. Traduzir aqui
                # evita a tela ter que conhecer o vocabulário da API.
                if "UNREAD" not in (m.get("labelIds") or []):
                    banco.executar(
                        "UPDATE email_mensagem SET lida = true WHERE id = %s",
                        (nova["id"],))

                total["novas"] += 1

        banco.executar(
            "UPDATE email_conta SET ultima_leitura_em = now(), "
            " atualizada_em = now() WHERE id = %s", (conta["id"],))

    log.info("gmail: %s novas, %s repetidas", total["novas"], total["repetidas"])
    return total
