"""Cliente HTTP do Harmonit — só leitura.

O MoviZap **lê** do Harmonit e nunca escreve. Cadastro criado aqui não sobe
para lá (escopo da Fase 1, item 4). Por isso este cliente não tem POST nem PUT:
o que não existe não é chamado por engano.

É bloqueante de propósito. O `banco.py` é bloqueante, o sync inteiro é
bloqueante, e a rota o joga numa thread. Misturar `async def` com trabalho
bloqueante foi o que produziu o `asyncio.to_thread(async_def)` que não executa
nada e só avisa por um `RuntimeWarning` invisível em produção.

LIÇÕES HERDADAS DO CLIENTE DO FPSL (incidente de 2026-07-28, ~14h fora do ar):

  🚨 Token só é descartado em **401**. Descartar em qualquer erro transforma
  falha de dado em tempestade de autenticação: cada leitura vira uma chamada a
  `/Account/Token`, justamente o endpoint que costuma estar sofrendo.

  🚨 Falha de autenticação abre um **disjuntor**. Sem recuo, uma varredura
  reinsiste para sempre num servidor já caído.

MEDIDO NA API REAL EM 2026-08-06:

  - `/ObterClientes` responde `{data: {sumario: {contador}, lista: [...]}}`.
    **Não é `data` direto na lista**;
  - 🚨 **`take` tem teto de 100.** Acima disso a resposta é HTTP 400 com
    `errorMessage` dizendo o limite. A API é honesta -- quem tem que checar
    somos nós;
  - `/ObterCliente?Id=X` responde `data` como **dict** quando acha e **null**
    quando não acha. (A armadilha de "achou = list, não achou = dict truthy"
    é de OUTRO endpoint. Aqui não se aplica -- conferido na API real.)
  - base tem **1.050 clientes**, sendo **944 ativos**.
"""
import logging
import time

import httpx

from .config import settings

log = logging.getLogger("movizap.harmonit")

# 🚨 Teto da API, medido em 06/08. Pedir mais volta HTTP 400.
TAKE_MAX = 100

FALHAS_PARA_ABRIR = 3
ESPERA_ABERTO_SEG = 600

_token: str | None = None
_falhas_seguidas = 0
_aberto_ate = 0.0
_ultimo_erro = ""


class HarmonitIndisponivel(RuntimeError):
    """A API não respondeu, ou respondeu erro. Não é "não achou"."""


def estado() -> dict:
    """Para a CFG_3.1 conseguir dizer 'a API está fora' em vez de 'sem dado'."""
    resta = int(_aberto_ate - time.time())
    return {
        "aberto": resta > 0,
        "segundos_restantes": max(resta, 0),
        "falhas_seguidas": _falhas_seguidas,
        "ultimo_erro": _ultimo_erro,
    }


def _registrar_falha_auth(motivo: str) -> None:
    global _falhas_seguidas, _aberto_ate, _ultimo_erro
    _falhas_seguidas += 1
    _ultimo_erro = motivo
    if _falhas_seguidas >= FALHAS_PARA_ABRIR:
        _aberto_ate = time.time() + ESPERA_ABERTO_SEG
        log.error("harmonit: DISJUNTOR ABERTO por %ss apos %s falhas -- %s",
                  ESPERA_ABERTO_SEG, _falhas_seguidas, motivo)


def _registrar_sucesso() -> None:
    global _falhas_seguidas, _aberto_ate, _ultimo_erro
    if _falhas_seguidas or _aberto_ate:
        log.info("harmonit: autenticacao normalizada, disjuntor fechado")
    _falhas_seguidas = 0
    _aberto_ate = 0.0
    _ultimo_erro = ""


def _checar_disjuntor() -> None:
    resta = _aberto_ate - time.time()
    if resta > 0:
        raise HarmonitIndisponivel(
            f"disjuntor aberto, {int(resta)}s restantes. Último erro: {_ultimo_erro}"
        )


def reiniciar() -> None:
    """Zera token e disjuntor. Existe para os testes -- estado de módulo que
    vaza entre testes produz falha que só aparece na ordem errada."""
    global _token, _falhas_seguidas, _aberto_ate, _ultimo_erro
    _token = None
    _falhas_seguidas = 0
    _aberto_ate = 0.0
    _ultimo_erro = ""


def _renovar_token(c: httpx.Client) -> str:
    global _token
    _checar_disjuntor()
    try:
        r = c.get("/Account/Token", params={
            "clientId": settings.harmonit_client_id,
            "secretId": settings.harmonit_secret_id,
        })
    except httpx.TimeoutException:
        _registrar_falha_auth("timeout no /Account/Token")
        raise HarmonitIndisponivel("timeout na autenticação") from None

    if r.status_code != 200:
        motivo = f"HTTP {r.status_code}"
        try:
            msg = (r.json() or {}).get("errorMessage")
            if msg:
                motivo = f"HTTP {r.status_code}: {str(msg)[:160]}"
        except Exception:
            pass
        _registrar_falha_auth(motivo)
        raise HarmonitIndisponivel(f"falha na autenticação ({motivo})")

    token = ((r.json() or {}).get("data") or {}).get("token")
    if not token:
        _registrar_falha_auth("200 sem token no corpo")
        raise HarmonitIndisponivel("token não retornado")

    _token = token
    _registrar_sucesso()
    # 🚨 comprimento, nunca o valor
    log.info("harmonit: token renovado (%s caracteres)", len(token))
    return _token


def abrir_sessao() -> httpx.Client:
    return httpx.Client(base_url=settings.harmonit_base_url, timeout=60)


def _get(c: httpx.Client, path: str, params: dict) -> dict:
    """GET com renovação de token em 401 e uma única retentativa."""
    global _token
    _checar_disjuntor()
    if not _token:
        _renovar_token(c)

    def chamar():
        return c.get(path, params=params,
                     headers={"Authorization": f"Bearer {_token}"})

    try:
        r = chamar()
        if r.status_code == 401:
            _token = None  # aqui SIM: 401 é o único erro que fala de token
            _renovar_token(c)
            r = chamar()
    except httpx.TimeoutException:
        raise HarmonitIndisponivel(f"timeout em {path}") from None

    try:
        corpo = r.json()
    except Exception:
        raise HarmonitIndisponivel(
            f"{path} respondeu HTTP {r.status_code} sem JSON") from None

    if not isinstance(corpo, dict):
        raise HarmonitIndisponivel(f"{path} respondeu {type(corpo).__name__}, não dict")

    erro = corpo.get("errorMessage")
    if erro:
        # Foi assim que o teto do `take` apareceu: a API DIZ o que houve.
        raise HarmonitIndisponivel(f"{path}: {str(erro)[:200]}")

    if r.status_code != 200:
        raise HarmonitIndisponivel(f"{path} respondeu HTTP {r.status_code}")

    return corpo


def obter_cliente(harmonit_id) -> dict | None:
    """Um cliente pelo id. `None` quando não existe -- e isso NÃO é erro.

    A numeração do Harmonit tem buracos. Confundir "não existe" com "falhou" é
    o que fez o painel acusar 76% de falha num sistema saudável.
    """
    with abrir_sessao() as c:
        corpo = _get(c, "/ObterCliente", {"Id": str(harmonit_id)})
    dados = corpo.get("data")
    if dados is None:
        return None
    if isinstance(dados, list):
        # Defensivo: outro endpoint do Harmonit devolve lista. Se este mudar,
        # é melhor ler o primeiro do que estourar longe da causa.
        return dados[0] if dados else None
    if not isinstance(dados, dict):
        raise HarmonitIndisponivel(f"/ObterCliente devolveu {type(dados).__name__}")
    return dados


def contar_clientes(somente_ativos: bool = False) -> int:
    with abrir_sessao() as c:
        corpo = _get(c, "/ObterClientes", {
            "skip": 0, "take": 1,
            "somenteAtivos": "true" if somente_ativos else "false",
        })
    dados = corpo.get("data") or {}
    return int((dados.get("sumario") or {}).get("contador") or 0)


def paginar_clientes(somente_ativos: bool = False, take: int = TAKE_MAX,
                     limite: int | None = None):
    """Percorre a base inteira, uma página por vez.

    Devolve (pagina, lista). Para quando a lista vier vazia: página vazia é o
    fim da base, não falha.
    """
    if take > TAKE_MAX:
        # Falhar aqui, com o motivo, em vez de tomar HTTP 400 no meio da varredura.
        raise ValueError(f"take={take} passa do teto do Harmonit ({TAKE_MAX})")

    lidos = 0
    pagina = 0
    with abrir_sessao() as c:
        while True:
            corpo = _get(c, "/ObterClientes", {
                "skip": pagina * take, "take": take,
                "somenteAtivos": "true" if somente_ativos else "false",
            })
            dados = corpo.get("data")
            if not isinstance(dados, dict):
                return
            lista = dados.get("lista") or []
            if not lista:
                return
            yield pagina, lista
            lidos += len(lista)
            pagina += 1
            if limite is not None and lidos >= limite:
                return
            if len(lista) < take:
                return
