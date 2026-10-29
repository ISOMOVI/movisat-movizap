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


def placas_ativas(harmonit_id: str) -> list[dict]:
    """As placas ativas do cliente, pelo cruzamento Harmonit x WESO do FPSL.

    🚨 Erro NÃO vira lista vazia: sobe `FpslIndisponivel`, e quem chama diz
    "não deu para consultar" em vez de "você não tem veículo" -- a mesma razão
    de `os_do_cliente` existir aqui em vez de um `httpx.get` solto.
    """
    corpo = _pedir("/api/os/placas-ativas", {"cliente_id": int(harmonit_id)})
    return corpo.get("placas") or []


def conferir_placas(placas: list[str]) -> dict:
    """`{placa escrita: {ativa, apelido}}`. 🔵 Regra dele: chamado só para placa
    ativa na WESO.

    🚨 Erro NÃO vira "nenhuma ativa": sobe `FpslIndisponivel`, e quem chama
    decide -- e a decisão tomada na rota é **deixar passar marcado**, porque
    indisponibilidade nossa não pode barrar o chamado do cliente.
    """
    corpo = _postar("/api/os/placas-ativas/conferir", {"placas": placas})
    return corpo.get("placas") or {}


def _postar(caminho: str, corpo: dict) -> dict:
    """Igual ao `_pedir`, do outro verbo. 🚨 Falha NUNCA vira sucesso mudo."""
    if not configurada():
        raise FpslIndisponivel(
            "a ponte com o FPSL não está configurada neste servidor")
    try:
        r = httpx.post(
            _base() + caminho,
            json=corpo,
            headers={"X-Ponte-Key": settings.ponte_fpsl_segredo},
            # Mais folgado que a leitura: esta chamada fala com o Harmonit por
            # dentro, e o Harmonit é lento. Ainda assim tem teto: o operador
            # está esperando um clique.
            timeout=25.0,
        )
    except httpx.TimeoutException:
        # 🚨 TIMEOUT NÃO QUER DIZER "NÃO GRAVOU": a escrita pode ter chegado ao
        # Harmonit e a resposta ter se perdido na volta. O `incerto` é o que
        # impede a retentativa cega de quem chama -- numa criação de OS, ela
        # abriria a segunda. Quem só lê pode ignorar a marca.
        erro = FpslIndisponivel("o FPSL não respondeu no tempo")
        erro.incerto = True
        raise erro from None
    except httpx.HTTPError as e:
        log.warning("falha de rede no POST %s: %s", caminho, e)
        raise FpslIndisponivel("não foi possível falar com o FPSL") from None
    if r.status_code == 401:
        raise FpslIndisponivel(
            "o FPSL recusou a chave da ponte (os dois .env estão iguais?)")
    if r.status_code >= 400:
        raise FpslIndisponivel(f"o FPSL respondeu {r.status_code}")
    try:
        return r.json()
    except ValueError:
        raise FpslIndisponivel("o FPSL respondeu algo que não é JSON") from None


def tecnico_do_harmonit(telefone: str) -> dict:
    """O cadastro do técnico no Harmonit, pelo telefone do contato.

    🔵 Decisão dele, 21/10: o orçamento leva **o nome do cadastro do
    Harmonit**. 🚨 Não achar NÃO é erro: devolve `{"achado": False}` e quem
    chama usa o nome do contato, dizendo isso na tela.
    """
    try:
        return _pedir("/api/os/tecnico-por-telefone", {"telefone": telefone})
    except FpslIndisponivel as e:
        return {"achado": False, "motivo": str(e)}


def tecnicos_do_harmonit(ativos: bool = True) -> dict:
    """O cadastro de técnicos, para a varredura de vínculo.

    🚨 ESTOURA quando a ponte cai, em vez de devolver lista vazia: vazio aqui
    faria a varredura relatar "nenhum casou" como se fosse fato.
    """
    return _pedir("/api/os/tecnicos", {"ativos": 1 if ativos else 0})


def agendar_tecnico(*, numero_os: int, inicio, fim=None,
                    tecnico_telefone: str | None = None,
                    tecnico_id: int | None = None,
                    tecnico_nome: str | None = None) -> dict:
    """Cria o compromisso na OS do Harmonit, pela ponte.

    🔵 Decisão 7 dele: a escrita no Harmonit é o **2º passo**, e ele mandou
    ligá-la em 21/10, depois do relatório do teste na OS 16991.

    🚨 DEVOLVE `{"ok": False, "motivo": ...}` EM VEZ DE ESTOURAR quando o
    Harmonit recusa — recusa é resposta, não falha de ponte. Quem chama grava
    o motivo ao lado do compromisso, e o agendamento do MoviZap continua
    valendo: o dono é este lado.
    """
    corpo = {
        "numero_os": int(numero_os),
        "inicio": inicio.isoformat() if hasattr(inicio, "isoformat") else inicio,
        "tecnico_telefone": tecnico_telefone or None,
        "tecnico_id": tecnico_id or None,
        "tecnico_nome": tecnico_nome or None,
    }
    if fim is not None:
        corpo["fim"] = fim.isoformat() if hasattr(fim, "isoformat") else fim
    try:
        return _postar("/api/os/agendar-tecnico", corpo)
    except FpslIndisponivel as e:
        return {"ok": False, "numero_os": int(numero_os), "motivo": str(e)}


# Os sete campos de endereço, com os nomes do Harmonit. 🚨 `endereco` aqui é a
# RUA, como lá -- e não a linha montada que a mensagem usa. A tradução para
# `logradouro` acontece uma única vez, no `agendamento`.
CAMPOS_DE_ENDERECO = ("cep", "endereco", "numero", "bairro", "cidade", "uf",
                      "complemento")


def endereco_da_os(numero_os: int) -> dict:
    """O endereço estruturado da OS, para pré-preencher o modal.

    🚨 Estoura `FpslIndisponivel` quando a ponte cai: endereço vazio por falha
    de rede faria o operador digitar por cima de um cadastro que existe.
    """
    return _pedir("/api/os/endereco", {"numero_os": int(numero_os)})


def gravar_endereco_da_os(numero_os: int, endereco: dict,
                          conferir: bool = False) -> dict:
    """Grava o endereço na OS do Harmonit, pela ponte.

    🔵 Pedido dele, 21/10: *"vai enviar para o endereço da OS e salvar ela lá
    no harmonit corretamente"*.

    🚨 DEVOLVE `{"ok": False, "motivo": ...}` EM VEZ DE ESTOURAR, como o
    `agendar_tecnico`: o dono do compromisso é este lado, e a OS não gravada
    não derruba o agendamento -- fica dita.

    ⚠️ Do outro lado isto é uma escrita de OS INTEIRA (o Harmonit não tem
    "atualizar só o endereço"), e lá a rota relê e compara os 39 campos. O
    `fora_do_endereco` da resposta é o que importa quando vem preenchido.
    """
    corpo = {"numero_os": int(numero_os), "conferir": bool(conferir)}
    corpo.update({c: endereco.get(c) for c in CAMPOS_DE_ENDERECO})
    try:
        return _postar("/api/os/endereco", corpo)
    except FpslIndisponivel as e:
        return {"ok": False, "numero_os": int(numero_os), "motivo": str(e)}


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


def criar_os(*, cliente_id: int, tipo_id: int, problema_id: int,
             situacao_id: int, prioridade_id: int, descricao: str,
             produto_servico_id: int | None = None,
             conferir: bool = False) -> dict:
    """Cria a OS de análise do chamado no Harmonit, pela ponte.

    🔵 Decisão D4 dele (29/10): *"todo chamado de suporte abrirá uma OS"*.

    🚨 DEVOLVE `{"ok": False, "motivo": ...}` EM VEZ DE ESTOURAR, como o
    `agendar_tecnico` e o `gravar_endereco_da_os`: o dono do chamado é este
    lado. O cliente já leu *"recebemos"*; derrubar o envio porque o ERP está
    fora do ar transformaria um problema nosso em chamado perdido.

    🚨 `criada` NA RESPOSTA TEM TRÊS VALORES, e o terceiro é o que importa:
    `True` nasceu · `False` não nasceu · **`None` = NÃO SE SABE**. Quem chama
    **não pode tentar de novo** no caso `None`, ou nascem duas OS.

    🚨 TIMEOUT É `None`, NÃO `False`, e foi o erro que eu quase deixei aqui:
    *"não respondeu no tempo"* não quer dizer *"não gravou"* -- a escrita pode
    ter chegado ao Harmonit e a resposta ter se perdido na volta. Dizer `False`
    ali convidaria a retentativa que abre a segunda OS. É o que o `incerto` do
    `_postar` carrega.

    ⚠️ `conferir: true` é ensaio a seco: a ponte monta o corpo, devolve e NÃO
    escreve. Foi assim que o corpo inteiro foi provado antes de a primeira OS
    de verdade existir no ERP.
    """
    corpo = {
        "cliente_id": int(cliente_id),
        "tipo_id": int(tipo_id),
        "problema_id": int(problema_id),
        "situacao_id": int(situacao_id),
        "prioridade_id": int(prioridade_id),
        "descricao": descricao,
        "produto_servico_id": produto_servico_id,
        "conferir": bool(conferir),
    }
    try:
        return _postar("/api/os/criar", corpo)
    except FpslIndisponivel as e:
        # Ver a advertência do docstring: `None` quando a escrita pode ter
        # chegado, `False` só quando é certo que não chegou.
        return {"ok": False,
                "criada": None if getattr(e, "incerto", False) else False,
                "motivo": str(e)}


def os_por_situacao(desde: str, so_abertas: bool = True,
                    teto: int = 600) -> dict:
    """As OS do ERP por situação, desde a data matriz — o Bloco B.

    🔵 D8 dele: o card do painel é a OS, de qualquer origem. 🔵 D9: a data
    matriz é 24/10/2026 e só o owner a muda.

    🚨 ESTOURA `FpslIndisponivel` quando a ponte cai, e NÃO devolve lista
    vazia: quem chama é o painel, e quadro vazio por falha de rede faria o
    operador concluir que não há trabalho — justo na hora em que há. O painel
    pega a exceção e DIZ que está vendo menos.
    """
    return _pedir("/api/os/por-situacao",
                  {"desde": desde, "so_abertas": 1 if so_abertas else 0,
                   "teto": teto})


def gravar_situacao_da_os(numero_os: int, situacao_id: int,
                          situacao_esperada: int | None = None,
                          conferir_antes: bool = True) -> dict:
    """Escreve a situação da OS no Harmonit, pela ponte — o Bloco D.

    🔵 É o motivo que ele deu para o painel existir: *"hoje ainda não usamos a
    situação da OS, por isso o painel e consulta para atualizar a situação no
    painel"*.

    🚨 DEVOLVE `{"ok": False, "motivo": ...}` EM VEZ DE ESTOURAR, como as outras
    escritas: quem chama registra a passagem com o motivo, e **o registro é o
    ponto** — *"deve ter o log de quem faz o que SEMPRE"*.

    🚨 TIMEOUT VIRA `incerto`, e quem chama NÃO pode tentar de novo às cegas: a
    escrita pode ter chegado ao Harmonit e a resposta ter se perdido na volta.
    Aqui isso sai como `ok: False` com `incerto: True`, e a passagem fica
    gravada dizendo exatamente isso.
    """
    corpo = {
        "numero_os": int(numero_os),
        "situacao_id": int(situacao_id),
        "situacao_esperada": situacao_esperada,
        "conferir_antes": bool(conferir_antes),
    }
    try:
        return _postar("/api/os/situacao", corpo)
    except FpslIndisponivel as e:
        incerto = bool(getattr(e, "incerto", False))
        return {"ok": False, "gravou": None if incerto else False,
                "incerto": incerto, "numero_os": int(numero_os),
                "para": int(situacao_id),
                "motivo": ("🚨 " if incerto else "") + str(e)}


def ficha_da_os(numero_os: int) -> dict:
    """A OS ao vivo, para o card aberto — o Bloco E.

    🔵 Ele: *"onde estão os temas do card, após clicar?"*.

    🚨 ESTOURA `FpslIndisponivel` quando a ponte cai, e NÃO devolve ficha
    vazia: ficha vazia é indistinguível de OS sem dados, e o operador
    concluiria que não há o que ver. Quem chama mostra *"não deu para ler a OS
    agora"*.
    """
    return _pedir("/api/os/ficha", {"numero_os": int(numero_os)})
