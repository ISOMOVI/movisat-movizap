"""Entrada pelo Google — para o time inteiro poder usar o painel.

🚨 POR QUE ISTO EXISTE. Os 4 atendentes importados do Chatwoot nasceram com
`senha_hash` NULL e **nenhum deles consegue entrar**. Decisão do usuário em
07/08: não haveria senha por conta; em 10/08, com o acesso ao Google Cloud,
virou "vamos tentar o auth". Este módulo é o que tira o painel de "só o dono"
para "o time".

AS TRÊS TRAVAS, e por que cada uma existe
-----------------------------------------
1. **Domínio.** Só e-mail `@movisat.com.br` passa. Sem isto, qualquer conta
   Google do mundo que chegue ao callback vira candidata a atendente -- e o
   painel tem dado de cliente.

2. **Conta tem que existir.** Quem não tem linha em `atendente` é RECUSADO,
   não criado. Criar sozinho faria qualquer pessoa do domínio virar atendente
   sem ninguém decidir. Cadastrar é ato de gestão, e mora na CAD_2.1.

3. **`state` assinado.** Sem ele, um terceiro monta a URL de callback e
   dispara a troca de código. O `state` é um JWT de 10 minutos, e a validação
   é o que prova que o retorno veio de um início nosso.

⚠️ O `id_token` vem da resposta do endpoint de token do Google, por TLS, com o
nosso client secret na requisição -- não é algo que o navegador possa forjar.
Por isso o corpo é lido sem reverificar a assinatura, mas `aud` e o domínio
SÃO conferidos: é o que impede um token emitido para outro aplicativo.
"""
import base64
import json
import logging
import time
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt

from . import auth, banco
from .config import settings

log = logging.getLogger("movizap.google")

AUTORIZAR = "https://accounts.google.com/o/oauth2/v2/auth"
TROCAR = "https://oauth2.googleapis.com/token"
VALIDADE_STATE = 600          # 10 min: tempo de fazer login, não mais

# 🚨 SÓ LEITURA, por decisão do usuário em 10/08. Responder e enviar pedem
# `gmail.send`, que é outro pedido de consentimento -- e só faz sentido quando
# a tela existir e ele vir o que ela faz.
ESCOPO_CAIXA = " ".join([
    # ler a caixa
    "https://www.googleapis.com/auth/gmail.modify",
    # enviar e responder
    "https://www.googleapis.com/auth/gmail.send",
])
# gmail.modify cobre ler, marcar lida, mover e arquivar. Fica de fora o
# https://mail.google.com/, que e acesso total inclusive apagar em
# definitivo: "Excluir" no painel move para a Lixeira, como o Gmail faz.

ESCOPO_AGENDA = "https://www.googleapis.com/auth/calendar.readonly"


class GoogleRecusado(Exception):
    """Motivo em português, já pronto para a tela."""


def configurado() -> bool:
    """A tela só mostra o botão se houver credencial. Botão que não funciona
    é pior que botão ausente: rende chamado."""
    return bool(getattr(settings, "google_client_id", "")
                and getattr(settings, "google_client_secret", ""))


def _novo_state() -> str:
    return jwt.encode({"tipo": "movizap_google_state", "exp": int(time.time()) + VALIDADE_STATE},
                      settings.jwt_secret, algorithm=auth.ALGORITMO)


def _state_valido(state: str) -> bool:
    try:
        corpo = jwt.decode(state, settings.jwt_secret, algorithms=[auth.ALGORITMO])
    except JWTError:
        return False
    return corpo.get("tipo") == "movizap_google_state"


def url_da_caixa() -> str:
    """Consentimento para LER a caixa -- fluxo à parte do login.

    ⚠️ `access_type=offline` e `prompt=consent` não são enfeite: sem eles o
    Google devolve só um token de uma hora, e a leitura de fundo pararia
    sozinha. O refresh token vem UMA vez, no consentimento -- guardar na hora
    ou perder.
    """
    return AUTORIZAR + "?" + urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect,
        "response_type": "code",
        "scope": f"openid email {ESCOPO_CAIXA} {ESCOPO_AGENDA}",
        "state": jwt.encode(
            {"tipo": "movizap_caixa_state", "exp": int(time.time()) + VALIDADE_STATE},
            settings.jwt_secret, algorithm=auth.ALGORITMO),
        "hd": settings.google_dominio,
        "access_type": "offline",
        "prompt": "consent",
    })


def _e_state_de_caixa(state: str) -> bool:
    try:
        corpo = jwt.decode(state, settings.jwt_secret, algorithms=[auth.ALGORITMO])
    except JWTError:
        return False
    return corpo.get("tipo") == "movizap_caixa_state"


def conectar_caixa(codigo: str, state: str) -> dict:
    """Guarda a autorização da caixa. Não mexe em sessão nem em login.

    🚨 A linha em `email_conta` nasce AQUI, e não num cadastro à mão: a caixa
    que existe é a que foi autorizada. Cadastrar endereço sem consentimento
    criaria conta que nunca vai ler nada.
    """
    from . import banco

    if not _e_state_de_caixa(state):
        raise GoogleRecusado("Pedido de autorização expirado. Tente de novo.")

    resposta = httpx.post(TROCAR, timeout=20, data={
        "code": codigo,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect,
        "grant_type": "authorization_code",
    })
    if resposta.status_code != 200:
        # ⚠️ Nunca registrar o corpo: carrega código e pedaços de credencial.
        log.warning("autorização da caixa recusada: HTTP %s", resposta.status_code)
        raise GoogleRecusado(
            "O Google recusou. Confira se a Gmail API está ativa no projeto "
            "e se o escopo gmail.readonly está na tela de consentimento.")

    dados = resposta.json()
    refresh = dados.get("refresh_token")
    corpo = _corpo_do_id_token(dados.get("id_token") or "")
    email = (corpo.get("email") or "").strip().lower()

    if not email.endswith("@" + settings.google_dominio.lower()):
        raise GoogleRecusado(f"Só caixas @{settings.google_dominio}.")

    # ⚠️ Sem refresh token a caixa lê por uma hora e para. Melhor recusar com
    # o motivo do que criar uma conta que morre sozinha depois do almoço.
    if not refresh:
        raise GoogleRecusado(
            "O Google não devolveu autorização de longo prazo. Revogue o "
            "acesso do MoviZap em myaccount.google.com e autorize de novo.")

    banco.executar(
        """INSERT INTO email_conta (endereco, provedor, refresh_token,
                                    puxar_desde, ativa)
           VALUES (%s, 'gmail', %s, DATE '2026-01-01', true)
           ON CONFLICT (endereco) DO UPDATE
              SET refresh_token = EXCLUDED.refresh_token,
                  ativa = true,
                  atualizada_em = now()""",
        (email, refresh))

    log.info("caixa autorizada: %s", email)
    return {"endereco": email}


def url_de_entrada() -> str:
    return AUTORIZAR + "?" + urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect,
        "response_type": "code",
        "scope": "openid email profile",
        "state": _novo_state(),
        # `hd` é dica ao Google, NÃO garantia: ele filtra a tela de escolha,
        # mas quem manipular a URL passa por cima. A trava de verdade é a
        # conferência do domínio abaixo.
        "hd": settings.google_dominio,
        "prompt": "select_account",
    })


def _corpo_do_id_token(id_token: str) -> dict:
    partes = id_token.split(".")
    if len(partes) != 3:
        raise GoogleRecusado("Resposta do Google em formato inesperado.")
    corpo = partes[1] + "=" * (-len(partes[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(corpo))


def entrar(codigo: str, state: str) -> dict:
    """Troca o código pelo e-mail, confere as travas e devolve o nosso token."""
    if not _state_valido(state):
        raise GoogleRecusado("Pedido de entrada expirado. Tente de novo.")

    try:
        resposta = httpx.post(TROCAR, timeout=20, data={
            "code": codigo,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect,
            "grant_type": "authorization_code",
        })
    except httpx.HTTPError as e:
        log.warning("Google fora do ar: %s", e)
        raise GoogleRecusado("Não consegui falar com o Google. Tente de novo.")

    if resposta.status_code != 200:
        # ⚠️ NUNCA registrar o corpo: ele carrega código e, em erro de
        # configuração, pedaços da credencial.
        log.warning("troca de código recusada: HTTP %s", resposta.status_code)
        raise GoogleRecusado("O Google recusou a entrada.")

    dados = _corpo_do_id_token(resposta.json().get("id_token") or "")

    if dados.get("aud") != settings.google_client_id:
        raise GoogleRecusado("Este acesso não é deste aplicativo.")

    email = (dados.get("email") or "").strip().lower()
    if not dados.get("email_verified") or not email:
        raise GoogleRecusado("O Google não confirmou este e-mail.")

    dominio = settings.google_dominio.lower()
    if not email.endswith("@" + dominio):
        raise GoogleRecusado(f"Só contas @{dominio} entram no painel.")

    # 🚨 CONTA TEM QUE EXISTIR. Casa pelo `google_sub` (quem já entrou) ou
    # pelo e-mail (primeira vez). Nunca cria.
    linha = banco.um(
        "SELECT id, login, nome, ativo FROM atendente "
        " WHERE google_sub = %s OR lower(email) = %s",
        (dados.get("sub"), email))
    if not linha:
        raise GoogleRecusado(
            f"{email} não tem conta no painel. Peça para o administrador "
            f"cadastrar em Atendentes.")
    if not linha["ativo"]:
        raise GoogleRecusado("Esta conta está inativa.")

    # Grava o `sub` na primeira entrada: é ele, não o e-mail, que identifica
    # a conta Google para sempre -- e-mail muda, `sub` não.
    banco.executar(
        "UPDATE atendente SET google_sub = %s, atualizado_em = now() "
        " WHERE id = %s AND google_sub IS DISTINCT FROM %s",
        (dados.get("sub"), linha["id"], dados.get("sub")))

    log.info("entrada pelo Google: %s (atendente %s)", email, linha["id"])
    return {"token": auth.criar_token(linha["login"]), "nome": linha["nome"]}
