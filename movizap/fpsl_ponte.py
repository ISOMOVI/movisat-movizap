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

# ⚠️ `banco` entrou em 18/11 com a frente de Serviço dos Técnicos: o
# ORÇAMENTO é o único dado desta ponte que nasce deste lado (🔵 decisão
# dele), e ele mora na tabela `orcamento`. 🚨 Sem ciclo: `banco` não
# importa este módulo.
from . import banco
from .config import settings

log = logging.getLogger(__name__)

# 🔵 11/11, DECISÃO DELE: *"sim, pode fazer"* -- subir o teto da leitura.
#
# 🚨 ERAM 4 s, E O NÚMERO ESTAVA ERRADO PARA O CASO QUE ACONTECE. A régua
# original ("melhor dizer 'não deu' em 4 s do que pendurar a tela") vale quando
# a demora é anômala. Medido em 09/11: sob exaustão do pool de conexões do
# Harmonit (`all pooled connections were in use and max pool size was
# reached`), cada leitura leva **~15,5 s** e aí volta erro -- 164 ocorrências em
# 07/11, 73 em 09/11. Com 4 s, abrir o card NUNCA conseguia nem chegar à
# mensagem de erro do ERP: estourava antes e dizia *"o FPSL não respondeu no
# tempo"*, culpando a peça errada.
#
# ⚠️ 20 s é acima do perfil medido e ainda abaixo do teto da ESCRITA (25 s),
# que é o que de fato não pode ser ultrapassado: a leitura é o primeiro passo
# dela.
TEMPO_LIMITE = 20.0

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
        log.warning("timeout consultando o FPSL em %s (teto de %ss)",
                    caminho, TEMPO_LIMITE)
        # 🚨 A FRASE NÃO ACUSA QUEM NÃO FOI. O que medimos é só isto: não veio
        # resposta no teto. A causa conhecida e recorrente é o Harmonit sem
        # conexão livre, e dizer "o FPSL não respondeu" mandava quem lê olhar
        # o serviço errado. ⚠️ Mas não afirmamos a causa -- "costuma ser".
        # ⚠️ Não digo "nada foi escrito" aqui: este caminho é só de LEITURA
        # (`_pedir` faz GET), e a frase pertence ao caminho da escrita.
        raise FpslIndisponivel(
            f"não veio resposta no tempo ({int(TEMPO_LIMITE)}s). Quando isso "
            "acontece, costuma ser o Harmonit sem conexão livre -- pode "
            "tentar de novo") from None
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
            #
            # 🚨 60s DESDE 18/11, E O PORQUÊ IMPORTA MAIS QUE O NÚMERO. Eram
            # 25s, e o cliente do Harmonit do outro lado esperava 30s **por
            # chamada**: o teto de dentro era maior que o de fora. A rota de
            # situação faz até 4 chamadas ao ERP, então o orçamento estourava
            # aqui e a resposta virava `incerto: True` — "pode ter gravado e
            # ninguém sabe", o único estado que não se audita.
            #
            # 🔵 Decidido por ele em 18/11, com a conta fechada: 18s por
            # chamada lá dentro, 2 leituras + 22s de reserva para gravar e
            # reler = 58s, dentro destes 60.
            #
            # ⚠️ O QUE ISTO CUSTA, e é sabido: no pior caso o operador espera
            # ~1 min no clique. É o preço até o mover otimista entrar — e aí
            # ninguém espera, porque o card anda na hora e a escrita corre
            # atrás.
            timeout=60.0,
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


# ============================================================================
# A FRASE DE CADA CAUSA — 🔵 pendência dele, 18/11
# ============================================================================
# 🔵 *"os motivos de recusa deve aparecer descritos ao inves de erro generico,
# para que me tragam o problema ja cientes"*.
#
# 🚨 O QUE CHEGAVA ANTES, e é o que motivou o pedido: `(HTTPException)`, ou um
# `dict` do Python dentro da frase, ou o nome de uma exceção. Diagnóstico de
# quem escreveu o código, não de quem atende — e **nenhum deles dizia o que
# fazer**. Quem lia não chegava já ciente: chegava com uma pergunta.
#
# 🚨 A DIVISÃO DE TRABALHO: a ponte do FPSL **nomeia a causa** (ela é quem vê a
# recusa crua do ERP); aqui se **escreve a frase**, porque frase é tela. Dois
# lugares, uma verdade.
#
# ⚠️ E A REGRA QUE VALE MAIS QUE A TABELA: causa que ninguém traduziu aparece
# **por extenso**, nunca encurtada e nunca como um genérico. Erro feio pelo
# menos pode ser lido.
FRASE_DA_CAUSA = {
    "leitura_falhou":
        "O Harmonit está sobrecarregado e não respondeu. Nada foi escrito — "
        "dá para tentar de novo em alguns instantes.",
    # 🚨 ESTA SEPARAÇÃO NASCEU DE UM DEFEITO MEU, no ar por uma hora em 18/11:
    # a retentativa da leitura trouxe um texto único e passou a chamar de
    # "Harmonit sobrecarregado" também a OS que simplesmente **não existe**.
    # ⚠️ Motivo descrito e errado é pior que genérico: manda consertar a coisa
    # errada. É `M12` dentro da própria correção que o pedido dele gerou.
    "os_nao_encontrada":
        "O Harmonit não tem nenhuma OS com este número — confira o número. "
        "Nada foi escrito.",
    "corpo_furado":
        "A leitura da OS no Harmonit veio incompleta, então não gravei: "
        "gravar assim apagaria dado da OS. Nada foi escrito.",
    "sem_cliente_no_cache":
        "Esta OS ainda não entrou no cache de OS, e sem o cliente a escrita a "
        "desvincularia do cadastro. Nada foi escrito.",
    "conflito_de_situacao":
        None,   # ⚠️ a frase do FPSL já é boa e diz as duas situações por nome
    "recusa_do_erp":
        None,   # 🚨 o texto do Harmonit vai POR EXTENSO, sem tradução
    "escrita_sem_resposta":
        "A escrita saiu e o Harmonit não respondeu, então não sei se gravou. "
        "A auditoria da madrugada confere e avisa.",
    "tecnico_ja_agendado":
        "Esta linha do técnico na OS já carrega um compromisso.",
    "vinculo_nao_e_nosso":
        "Este compromisso está numa linha de técnico que não criamos. Removê-la "
        "levaria o vínculo e o compromisso de outra pessoa, então não mexi.",
    # ⚠️ A linha é nossa, mas o compromisso que está nela hoje não é o que
    # íamos apagar. Alguém mexeu no meio, e apagar levaria o compromisso errado.
    "compromisso_mudou":
        None,   # a frase do FPSL já diz os dois ids, e os ids é que ajudam aqui
    # 🚨 Medido na Velasco: o DELETE leva o compromisso E a linha. Se o novo
    # nasceu na mesma linha do antigo, apagar levaria o novo junto.
    "mesma_linha_do_novo":
        None,   # idem: a frase do FPSL explica a mecânica, e traduzir perderia
}

# 🚨 AS CAUSAS QUE NÃO SE RETENTA, e o porquê de ser uma lista curta e explícita
# em vez de "tudo menos X": 🔵 *"esse botão não serve sem sabermos o problema
# mesmo, só cansa a req"*. Repetir uma recusa de negócio colhe a mesma recusa e
# gasta o pool do Harmonit, que é o recurso escasso.
#
# 🔵 E a régua dele, 18/11: *"por regra, somente o cache ou timeout daria erro,
# pois as informações de preenchimento estão corretas"* — medido: **0 das 643**
# OS da base carece dos campos obrigatórios.
#
# ⚠️ `escrita_sem_resposta` não se retenta por outro motivo: não se sabe se
# gravou. Quem resolve é a auditoria, relendo.
#
# ⚠️ E `os_nao_encontrada` não se retenta porque o Harmonit RESPONDEU, e
# respondeu claro: o número não existe. Repetir não faz a OS passar a existir.
CAUSAS_QUE_NAO_SE_RETENTA = frozenset({
    "recusa_do_erp", "conflito_de_situacao", "vinculo_nao_e_nosso",
    "escrita_sem_resposta", "os_nao_encontrada",
})


def frase_da_recusa(resposta: dict) -> str:
    """O que a tela diz sobre esta recusa. Nunca vazio, nunca genérico."""
    cru = (resposta.get("motivo") or "").strip()
    frase = FRASE_DA_CAUSA.get(resposta.get("causa"))
    if frase:
        return frase
    # 🚨 Sem tradução: o texto cru, por extenso. É o pior caso e ainda assim é
    # legível — ao contrário de "erro ao mover".
    return cru or "O Harmonit recusou e não disse o motivo."


def pode_retentar(resposta: dict) -> bool:
    """Se vale chamar de novo. ⚠️ Causa desconhecida NÃO se retenta.

    🚨 O padrão é não repetir: uma causa que ninguém classificou pode ser
    recusa de negócio, e insistir nela gasta o pool para colher o mesmo "não".
    """
    causa = resposta.get("causa")
    return bool(causa) and causa not in CAUSAS_QUE_NAO_SE_RETENTA


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


def cancelar_agendamento(*, numero_os: int, agendamento_id: int,
                         vinculo_id: int, vinculo_criado: bool) -> dict:
    """Apaga o compromisso daquela OS no Harmonit.

    🚨 APAGA A LINHA DO TÉCNICO JUNTO, e não é escolha nossa: medido na
    Velasco em 18/11, o `DELETE` do ERP leva o compromisso **e** a linha. Não
    existe cancelar deixando a linha.

    ⚠️ `vinculo_criado` NÃO é opcional aqui de propósito: quem chama tem de
    dizer se a linha é nossa. Omitir viraria `False` do outro lado, que é
    recusa -- e é a recusa certa, porque quem não sabe não apaga.
    """
    try:
        return _postar("/api/os/cancelar-agendamento", {
            "numero_os": int(numero_os),
            "agendamento_id": int(agendamento_id),
            "vinculo_id": int(vinculo_id),
            "vinculo_criado": bool(vinculo_criado),
        })
    except FpslIndisponivel as e:
        return {"ok": False, "apagou": False, "numero_os": int(numero_os),
                "motivo": str(e)}


def reagendar_tecnico(*, numero_os: int, inicio, fim=None,
                      agendamento_id_antigo: int, vinculo_id_antigo: int,
                      vinculo_criado: bool,
                      tecnico_telefone: str | None = None,
                      tecnico_id: int | None = None,
                      tecnico_nome: str | None = None) -> dict:
    """Cria o compromisso novo e **só então** apaga o antigo.

    🚨 A ORDEM É A REGRA, e vem da única assimetria deste caminho: se
    apagássemos primeiro e a criação falhasse, a OS ficaria com **zero**
    compromisso -- o técnico perde a visita da agenda e ninguém percebe. Na
    ordem daqui, a falha deixa **dois**: visível, corrigível, e a resposta diz
    qual não saiu.

    ⚠️ O compromisso ganha `id` novo no Harmonit; o antigo deixa de existir.
    🔵 Consequência aceita por ele em 18/11, porque o ERP não dá outro caminho.
    """
    corpo = {
        "numero_os": int(numero_os),
        "inicio": inicio.isoformat() if hasattr(inicio, "isoformat") else inicio,
        "agendamento_id_antigo": int(agendamento_id_antigo),
        "vinculo_id_antigo": int(vinculo_id_antigo),
        "vinculo_criado": bool(vinculo_criado),
        "tecnico_telefone": tecnico_telefone or None,
        "tecnico_id": tecnico_id or None,
        "tecnico_nome": tecnico_nome or None,
    }
    if fim is not None:
        corpo["fim"] = fim.isoformat() if hasattr(fim, "isoformat") else fim
    try:
        return _postar("/api/os/reagendar-tecnico", corpo)
    except FpslIndisponivel as e:
        return {"ok": False, "reagendou": False, "apagou_o_antigo": False,
                "numero_os": int(numero_os), "motivo": str(e)}


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
        resposta = _postar("/api/os/situacao", corpo)
        # 🔵 Pendência dele, 18/11: a tela recebe a FRASE, não o diagnóstico.
        # ⚠️ O cru fica em `motivo`, intocado: a frase é um acréscimo, nunca
        # uma substituição — quem for depurar precisa do texto do ERP.
        if not resposta.get("ok"):
            resposta["frase"] = frase_da_recusa(resposta)
            resposta["pode_retentar"] = pode_retentar(resposta)
        return resposta
    except FpslIndisponivel as e:
        incerto = bool(getattr(e, "incerto", False))
        # 🚨 Timeout da PONTE (não do Harmonit) é o `incerto`: a escrita pode
        # ter chegado e a resposta ter se perdido. Depois de 18/11 ele passou a
        # ser raro -- o orçamento de 18s/60s existe para a rota desistir antes
        # de nós --, mas raro não é nunca, e quem resolve é a auditoria.
        causa = "escrita_sem_resposta" if incerto else "leitura_falhou"
        resposta = {"ok": False, "gravou": None if incerto else False,
                    "incerto": incerto, "numero_os": int(numero_os),
                    "para": int(situacao_id), "causa": causa,
                    "motivo": ("🚨 " if incerto else "") + str(e)}
        resposta["frase"] = frase_da_recusa(resposta)
        resposta["pode_retentar"] = pode_retentar(resposta)
        return resposta


def ficha_da_os(numero_os: int) -> dict:
    """A OS ao vivo, para o card aberto — o Bloco E.

    🔵 Ele: *"onde estão os temas do card, após clicar?"*.

    🚨 ESTOURA `FpslIndisponivel` quando a ponte cai, e NÃO devolve ficha
    vazia: ficha vazia é indistinguível de OS sem dados, e o operador
    concluiria que não há o que ver. Quem chama mostra *"não deu para ler a OS
    agora"*.
    """
    return _pedir("/api/os/ficha", {"numero_os": int(numero_os)})


def gravar_prioridade_da_os(numero_os: int, prioridade_id: int,
                            prioridade_esperada: int | None = None) -> dict:
    """Escreve a prioridade da OS no Harmonit — Bloco F, fase 1.

    ⚠️ Escreve a OS INTEIRA do outro lado; o plano dele já avisava disso.
    🚨 `gravou: None` no timeout, pelo mesmo motivo da situação.
    """
    corpo = {"numero_os": int(numero_os),
             "prioridade_id": int(prioridade_id),
             "prioridade_esperada": prioridade_esperada,
             "conferir_antes": True}
    try:
        return _postar("/api/os/prioridade", corpo)
    except FpslIndisponivel as e:
        incerto = bool(getattr(e, "incerto", False))
        return {"ok": False, "gravou": None if incerto else False,
                "incerto": incerto, "numero_os": int(numero_os),
                "motivo": ("🚨 " if incerto else "") + str(e)}


# ============================================================================
# SERVIÇO DOS TÉCNICOS — 🔵 a aba 2 do Financeiro, 18/11
# ============================================================================
# 🔵 *"É possível fazer tudo no FPSL com as rotas e etc, mas o painel é aqui."*
# Os dados e os gestos moram no FPSL; daqui saem as chamadas e a tela.
#
# 🚨 **O ORÇAMENTO É O ÚNICO DADO QUE NASCE DESTE LADO**, e é por isso que estas
# funções existem em vez de a tela falar com a ponte direto: 🔵 decisão dele de
# 18/11, o orçamento é o do MoviZap -- a tabela `orcamento`, com numeração
# nossa (hoje nos nº 1 a 4), que liga técnico + lista de OS + total + PDF.
# O FPSL não tem como sabê-lo, e adivinhar seria inventar dado.
#
# ⚠️ E A ETAPA 2322 TAMBÉM É NOSSA: *"Serviço Realizado"* é `pipeline_etapa`,
# não situação do Harmonit. A porta dupla da coluna 2 só fecha se este lado
# disser quais OS estão lá -- é o conserto do funil de 11/11 (70 → 16 → 8 OS).


def _pagamento(caminho: str, corpo: dict) -> dict:
    """Uma chamada à ponte de pagamento. 🚨 Recusa é resposta, não exceção."""
    try:
        return _postar("/api/pagamento" + caminho, corpo)
    except FpslIndisponivel as e:
        return {"ok": False, "motivo": str(e)}


def _orcamento_por_os() -> dict:
    """`numero_os` -> número do orçamento, a partir de `orcamento.ordens_os`.

    🚨 UMA CONSULTA PARA TODOS, e não uma por artefato: a coluna 1 tem 58
    artefatos hoje, e uma ida ao banco por card seria N+1 numa tela que abre
    com o quadro inteiro -- o mesmo motivo do `quantas_observacoes`.

    ⚠️ `ordens_os` é uma LISTA: um orçamento pode cobrir várias OS (o nº 3
    cobre a 17015 e a 17016). Então a chave é a OS, e o valor é o orçamento --
    nunca o contrário.
    """
    mapa: dict[int, int] = {}
    for linha in banco.varios(
            "SELECT numero, ordens_os FROM orcamento "
            " WHERE ordens_os IS NOT NULL ORDER BY numero"):
        for numero_os in (linha["ordens_os"] or []):
            try:
                mapa[int(numero_os)] = int(linha["numero"])
            except (TypeError, ValueError):
                continue
    return mapa


def _os_na_etapa_nossa() -> list[int]:
    """As OS que estão na etapa NOSSA 2322 (*"Serviço Realizado"*).

    🚨 É A PORTA DUPLA DA COLUNA 2, e é o conserto do funil que ele mandou
    medir em 11/11: o Fechamento antigo exigia **só** a situação 15694 do
    Harmonit, e foi isso que derrubou 70 OS para 16, e 16 para 8.
    """
    return [l["numero_os"] for l in banco.varios(
        "SELECT numero_os FROM pipeline_card "
        " WHERE etapa_id = %s AND numero_os IS NOT NULL AND desfecho IS NULL",
        (ETAPA_SERVICO_REALIZADO,))]


# 🚨 A etapa NOSSA *"Serviço Realizado"*, na aba da Operação. ⚠️ O número é
# dado, não escolha: ela nasceu na migração 105 e o `paineis` já a conhece.
ETAPA_SERVICO_REALIZADO = 2322


def quadro_do_pagamento() -> dict:
    """As cinco colunas, com o orçamento preenchido deste lado.

    🔵 A ordem que ele pediu no card é **Orçamento — OS — TERMO**, e o primeiro
    só existe aqui.
    """
    quadro = _pagamento_get("/quadro")
    orcamentos = _orcamento_por_os()
    for coluna in quadro.get("colunas") or []:
        for card in coluna.get("cards") or []:
            for a in card.get("artefatos") or []:
                # ⚠️ O que já veio persistido do FPSL (gravado no `preparar`)
                # MANDA: a partir da coluna 2 o número é o que foi usado, e
                # não o que o cruzamento diria hoje. Orçamento emitido depois
                # não pode reescrever o que já foi para o arquivo.
                if a.get("orcamento_numero") is None:
                    a["orcamento_numero"] = orcamentos.get(a.get("numero_os"))
                # 🔵 *"Entra, e o card diz que falta"* -- a ausência fica à
                # vista em amarelo, e não vira artefato inexistente.
                a["sem_orcamento"] = a.get("orcamento_numero") is None
    return quadro


def _pagamento_get(caminho: str, params: dict | None = None) -> dict:
    try:
        return _pedir("/api/pagamento" + caminho, params or {})
    except FpslIndisponivel:
        # 🚨 QUADRO VAZIO NUNCA: a tela diz que não conseguiu ler, como o
        # painel da Operação faz. Vazio silencioso faria o operador concluir
        # que não há pagamento a preparar -- justo quando há.
        raise


def preparar_pagamentos(artefatos: list[int], *, por: str | None = None) -> dict:
    """🔵 *"Os itens flegados e clicados em preparar"*.

    🚨 **O ORÇAMENTO VAI JUNTO, e é aqui que ele se torna persistente**: do
    `preparar` em diante o número é o que vai ao arquivo do Procfy como *"Nº de
    Documento"*, e o cruzamento não é refeito -- orçamento emitido depois não
    reescreve o que já foi.
    """
    orcamentos = _orcamento_por_os()
    quadro = _pagamento_get("/quadro")
    por_id = {a["id"]: a for coluna in (quadro.get("colunas") or [])
              for card in (coluna.get("cards") or [])
              for a in (card.get("artefatos") or [])}
    corpo = [{"id": i,
              "orcamento_numero": orcamentos.get(
                  (por_id.get(i) or {}).get("numero_os"))}
             for i in artefatos]
    return _pagamento("/preparar", {"artefatos": corpo, "por": por})


def conferir_situacao(artefato_id: int) -> dict:
    """🔵 *"A preparação vai trazer essas situações a tela"*, com a porta dupla."""
    return _pagamento("/conferir-situacao",
                      {"artefato_id": artefato_id,
                       "etapas_nossas": _os_na_etapa_nossa()})


def dar_ciente(artefato_id: int, *, por: str | None = None) -> dict:
    return _pagamento("/ciente", {"artefato_id": artefato_id, "por": por})


def devolver_artefato(artefato_id: int, justificativa: str, *,
                      por: str | None = None) -> dict:
    """🔵 *"devolvido ao card na coluna de Movimentação abrindo um campo de
    justificativa"*. 🚨 Sempre para a coluna 1, de qualquer etapa."""
    return _pagamento("/devolver", {"artefato_id": artefato_id,
                                    "justificativa": justificativa,
                                    "por": por})


def auditar_lote(lote_id: int, *, por: str | None = None) -> dict:
    return _pagamento("/auditar", {"lote_id": lote_id, "por": por})


def datascope_do_artefato(artefato_id: int) -> dict:
    return _pagamento("/datascope", {"artefato_id": artefato_id})


def guardar_comprovante(artefato_id: int, *, arquivo=None, valor=None,
                        dispensa=None, por: str | None = None) -> dict:
    return _pagamento("/comprovante", {
        "artefato_id": artefato_id, "arquivo": arquivo, "valor": valor,
        "dispensa": dispensa, "por": por})


def revalidar_lote(lote_id: int, *, por: str | None = None) -> dict:
    """🔵 O botão **[ atualizar ]** de todo card. 🚨 Não move nada."""
    return _pagamento("/revalidar", {"lote_id": lote_id, "por": por,
                                     "etapas_nossas": _os_na_etapa_nossa()})


# 🔴 OS QUATRO DO CADASTRO DO PROCFY, que vivem no `/config` (a casa de todo
# interruptor, `CFG_7.1`) e nascem VAZIOS.
# 🔵 Decisão dele, 18/11: *"pode gerar com elas em branco nesse momento, pois
# podem preencher a mão por informação confidencial ou depois nos passar"*.
# ⚠️ O arquivo SAI com elas vazias, e a resposta diz quais saíram assim.
CHAVES_DO_PROCFY = ("procfy_categoria", "procfy_conta_bancaria",
                    "procfy_modo_pagamento", "procfy_centro_de_custo",
                    "procfy_tags")


def _config_do_procfy(cfg: dict | None = None) -> dict:
    """⚠️ A config chega por PARÂMETRO quando o teste a fornece: a régua de
    19/10 é que teste não lê nem escreve a `config` real."""
    if cfg is not None:
        return {c: (cfg.get(c) or "") for c in CHAVES_DO_PROCFY}
    linhas = banco.varios(
        "SELECT chave, valor FROM config WHERE chave = ANY(%s)",
        (list(CHAVES_DO_PROCFY),))
    achado = {l["chave"]: (l["valor"] or "") for l in linhas}
    return {c: achado.get(c, "") for c in CHAVES_DO_PROCFY}


def previa_do_arquivo(lote_id: int, *, cfg: dict | None = None) -> dict:
    """🔵 *"dentro deles um resumo dos artefatos que vão para pagamento"*.

    ⚠️ NÃO move card: ver o resumo é leitura."""
    return _pagamento("/previa-do-arquivo",
                      {"lote_id": lote_id, "config": _config_do_procfy(cfg)})


def montar_arquivo(lote_id: int, *, por: str | None = None,
                   cfg: dict | None = None) -> dict:
    """🔵 *"o botão de ação da vez é 'Montar Arquivo'"*."""
    return _pagamento("/montar-arquivo",
                      {"lote_id": lote_id, "por": por,
                       "config": _config_do_procfy(cfg)})


def enviar_pagamento(lote_id: int, *, por: str | None = None) -> dict:
    return _pagamento("/enviar", {"lote_id": lote_id, "por": por})
