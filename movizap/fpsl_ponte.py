"""A ponte para o FPSL — as OS que o agendamento cita. SOMENTE LEITURA.

🔵 Decisão 8 dele (19/10): *"o FPSL expõe endpoint de OS e o MoviZap consome
pelo `FPSL_BASE_URL`"*. Do outro lado está `fpsl_weso/routers/os_ponte.py`.

🚨 LISTA VAZIA E FPSL FORA DO AR SÃO COISAS DIFERENTES, e é esta a razão de
este arquivo existir em vez de um `httpx.get` solto na rota: devolver `[]`
quando a ponte cai faria a tela dizer "este cliente não tem OS" -- e o
operador agendaria por cima de serviço existente. Toda falha aqui sobe como
`FpslIndisponivel`, e a tela diz que não deu para consultar.

⚠️ O `FPSL_BASE_URL` do `.env` aponta para `127.0.0.1:8005`, que é um **nginx**
(`fpsl.conf:116`, escutando em `0.0.0.0`) repassando para a aplicação em
`127.0.0.1:8004` -- medido em 21/10. Por isso o padrão aqui é **8004, direto**:
chamada entre dois serviços da mesma máquina não precisa atravessar um
servidor web que escuta em todas as interfaces. O `.env` continua ganhando,
para o valor seguir configurável sem mexer em código.

🚨 A CHAVE DO CRUZAMENTO É O `harmonit_id`, e ele é **text** no MoviZap
(`cliente.harmonit_id`, 959 de 959 preenchidos, todos numéricos) e **int** no
FPSL (`os_historico.cliente_id`). A conversão mora aqui, num lugar só.
"""
import logging

import httpx

from .config import settings

log = logging.getLogger(__name__)

# Curto de propósito: isto roda dentro de um clique do operador. É melhor
# dizer "não deu para consultar agora" em 4 s do que pendurar a tela.
TEMPO_LIMITE = 4.0

# A aplicação do FPSL, direto -- ver a advertência do topo sobre o 8005.
BASE_PADRAO = "http://127.0.0.1:8004"


class FpslIndisponivel(RuntimeError):
    """O FPSL não respondeu, ou respondeu erro. **Não é "não achou"**."""


def configurada() -> bool:
    """Sem segredo, a ponte está desligada -- e quem desenha a tela precisa
    saber disso para não mostrar uma lista vazia como se fosse resposta."""
    return bool(settings.ponte_fpsl_segredo)


def _base() -> str:
    return (settings.fpsl_base_url or "").rstrip("/") or BASE_PADRAO


def _pedir(caminho: str, params: dict) -> dict:
    if not configurada():
        raise FpslIndisponivel(
            "a ponte com o FPSL não está configurada neste servidor"
        )
    try:
        r = httpx.get(
            _base() + caminho,
            params=params,
            headers={"X-Ponte-Key": settings.ponte_fpsl_segredo},
            timeout=TEMPO_LIMITE,
        )
    except httpx.TimeoutException:
        log.warning("timeout consultando o FPSL em %s", caminho)
        raise FpslIndisponivel("o FPSL não respondeu no tempo") from None
    except httpx.HTTPError as e:
        log.warning("falha de rede consultando o FPSL em %s: %s", caminho, e)
        raise FpslIndisponivel("não foi possível falar com o FPSL") from None

    if r.status_code == 401:
        # Segredo trocado de um lado só. Dizer isto por extenso economiza a
        # investigação inteira -- o sintoma seria "a lista não carrega".
        raise FpslIndisponivel(
            "o FPSL recusou a chave da ponte (os dois .env estão iguais?)"
        )
    if r.status_code >= 400:
        raise FpslIndisponivel(f"o FPSL respondeu {r.status_code}")
    try:
        return r.json()
    except ValueError:
        raise FpslIndisponivel("o FPSL respondeu algo que não é JSON") from None


def os_do_cliente(harmonit_id: str, meses: int = 6, abertas: bool = True) -> list[dict]:
    """As OS daquele cliente, no recorte. 🚨 Estoura se a ponte falhar."""
    try:
        cliente_id = int(str(harmonit_id).strip())
    except (TypeError, ValueError):
        # Cliente sem harmonit_id não tem OS do lado de lá: é ausência de
        # vínculo, não falha de ponte.
        return []
    dados = _pedir(
        "/api/os/por-cliente",
        {"cliente_id": cliente_id, "meses": meses, "abertas": 1 if abertas else 0},
    )
    return dados.get("os") or []


def clientes_com_os(meses: int = 6, abertas: bool = True) -> dict[str, int]:
    """`harmonit_id` -> quantas OS, para a etapa 2 da aba Agendar.

    🔵 Decisão 5 dele: a etapa do cliente lista **só clientes com OS em aberto**
    nos últimos 6 meses. A chave volta como **texto**, que é o tipo do
    `cliente.harmonit_id` deste lado -- converter aqui evita cast em toda
    junção lá na frente.
    """
    dados = _pedir(
        "/api/os/clientes-com-os",
        {"meses": meses, "abertas": 1 if abertas else 0},
    )
    return {
        str(c["cliente_id"]): int(c.get("quantas") or 0)
        for c in (dados.get("clientes") or [])
        if c.get("cliente_id") is not None
    }
