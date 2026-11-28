# -*- coding: utf-8 -*-
r"""O PAINEL DO CONTRATUAL — a `PNL_1.5` e as seis colunas dele (06/11).

🔵 Pedido dele: *"Depois gere a mesmta tela do 'Financeiro' para o 'Contratual'
- seguindo o seguindo modelo para colunas"*, com a lista colada · e *"as regras
de criação de cards em 'financeiro', 'pós-venda' e 'Contratual' ainda ficam em
branco mesmo. Mas eleas ja devem aparecer no menu para owner"*.

🚨 **A TRAVA PRINCIPAL DESTE ARQUIVO É UMA LEITURA MINHA, E ELA ESTÁ AQUI JUSTO
POR ISSO.** A lista dele começava com *"Regras de automação e gatilhos"* e
*"pesquisar"*, que eu li como a MOLDURA da tela de onde ele copiou (o link de
automação e a caixa de busca do CRM), não como etapas. Se a leitura estiver
errada, é esta trava que fica vermelha quando alguém consertar a migração — e é
assim que a decisão aparece, em vez de sumir.

As outras quatro regras: as seis colunas são as dele **na ordem dele** · os
**três fins** são Assinado, Não assinado e Desistiu de cancelar · a grafia é a
**dele** (sem acento em "pendencias") · e o painel **nasce vazio**, por decisão
dele.

Roda:  venv/bin/python -m pytest tests/teste_painel_contratual.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main, paineis, permissao_paineis  # noqa: E402
from movizap import pipeline  # noqa: E402
from movizap import telas as registro_telas  # noqa: E402
from movizap.config import settings  # noqa: E402

CODIGO = "PNL_1.5"

# 🔵 As seis, na ordem dele.
AS_SEIS = [
    "Elaborar contrato",
    "Aguardando pendencias",
    "Aguardando assinatura",
    "Assinado",
    "Não assinado",
    "Desistiu de cancelar",
]
OS_TRES_FINS = {"Assinado", "Não assinado", "Desistiu de cancelar"}
# 🚨 As duas linhas da mensagem dele que NÃO são coluna.
A_MOLDURA = ("Regras de automação e gatilhos", "pesquisar")


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield


@pytest.fixture(scope="module")
def cliente():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def token_owner():
    return auth.criar_token(settings.admin_login)


# ============================================================================
# O CATÁLOGO
# ============================================================================
def teste_a_tela_tem_entrada_no_catalogo():
    """🚨 Lição dele de 03/11: *"ESTÁ NO AR NÃO É 200"*."""
    t = registro_telas.por_codigo(CODIGO)
    assert t["titulo"] == "Contratual"
    assert t["rota"] == "/paineis/contratual"
    assert t["grupo"] == "Painéis"
    # 🔵 *"eleas ja devem aparecer no menu para owner"*.
    assert t["permissao"] == "owner"
    assert t["fase"] == 1
    # ⚠️ Painel próprio, com item de menu próprio -- não é aba de ninguém.
    assert t.get("aba_de") is None


def teste_o_painel_chega_ao_menu_do_owner():
    vistas = {t["codigo"] for t in registro_telas.do_usuario({"owner": True})}
    assert CODIGO in vistas


def teste_quem_nao_e_owner_nao_ve_o_contratual():
    u = {"permissoes": ["atendimento", "equipe"]}
    assert registro_telas.pode_acessar(u, CODIGO) is False


# ============================================================================
# AS SEIS COLUNAS
# ============================================================================
def teste_as_seis_colunas_sao_as_dele_e_na_ordem_dele():
    aba = pipeline.aba_por_codigo(CODIGO)
    assert aba is not None
    assert aba["painel"] == "contratual"
    assert aba["titulo"] == "Contratual"
    etapas = [e["titulo"] for e in pipeline.etapas(aba["id"])]
    assert etapas == AS_SEIS
    # ⚠️ Ordem NÃO é alfabética: um `sorted()` destruiria o fluxo em silêncio.
    assert etapas != sorted(etapas)


def teste_a_moldura_da_mensagem_dele_NAO_virou_coluna():
    """🚨 ESTA TRAVA GUARDA UMA LEITURA MINHA, não um fato dele.

    A lista colada começava com *"Regras de automação e gatilhos"* e
    *"pesquisar"*. Eu li as duas como moldura da tela de origem: a primeira é o
    link de automação do CRM, a segunda é a caixa de busca em minúscula no meio
    de títulos capitalizados -- e na lista do Financeiro, meia hora antes, a
    linha equivalente era o cabeçalho literal "Colunas".

    ⚠️ Se a leitura estiver errada, é AQUI que aparece: consertar a migração 097
    deixa esta trava vermelha, e quem consertar vê o raciocínio escrito.
    """
    aba = pipeline.aba_por_codigo(CODIGO)
    titulos = [e["titulo"] for e in pipeline.etapas(aba["id"])]
    for linha in A_MOLDURA:
        assert linha not in titulos
    # ⚠️ Nem como pedaço de outro título -- um "pesquisar" grudado em algo
    # passaria pela comparação exata acima.
    assert not [t for t in titulos
                if "pesquis" in t.lower() or "gatilho" in t.lower()]


def teste_sao_seis_e_nenhuma_coluna_a_mais():
    aba = pipeline.aba_por_codigo(CODIGO)
    assert len(pipeline.etapas(aba["id"])) == 6


def teste_os_tres_fins_sao_os_tres_e_so_eles():
    """🚨 Três fins. Marcar só a última diria que chegar em "Assinado" não é
    terminar -- e isso é falso."""
    aba = pipeline.aba_por_codigo(CODIGO)
    finais = {e["titulo"] for e in pipeline.etapas(aba["id"]) if e["final"]}
    assert finais == OS_TRES_FINS


def teste_a_grafia_e_a_DELE():
    """⚠️ "pendencias" sem acento e "Desistiu de cancelar" inteiro, como ele
    escreveu. Corrigir ortografia de rótulo ditado é renomear a coluna dele sem
    pedir -- e o rótulo é o que o operador procura com os olhos."""
    aba = pipeline.aba_por_codigo(CODIGO)
    titulos = [e["titulo"] for e in pipeline.etapas(aba["id"])]
    assert "Aguardando pendencias" in titulos
    assert "Aguardando pendências" not in titulos
    assert "Desistiu de cancelar" in titulos


# ============================================================================
# O QUADRO E A ROTA
# ============================================================================
def teste_o_quadro_abre_com_as_seis_colunas_dele():
    """🔴 Vazio por decisão dele: *"as regras de criação de cards (...) ainda
    ficam em branco mesmo"*. A `PainelAba` escreve "Nenhum card nesta aba
    ainda." -- quadro vazio que não diz por quê é `M12`."""
    q = paineis.quadro_da_aba(CODIGO)
    assert q is not None
    assert q["painel"] == "contratual"
    assert [c["titulo"] for c in q["colunas"]] == AS_SEIS
    # 🚨 ERA `assert q["total"] == 0`, E ELA ESTAVA CERTA EM 06/11: o painel
    # nasceu desenhado e **vazio por decisão dele**, com a origem dos cards em
    # aberto. ⚠️ Em 11/11 ele decidiu a origem, e a trava passou a **reprovar
    # quando o sistema funciona** -- o pior tipo de vermelho, porque ensina a
    # ignorar o placar.
    #
    # O que fica no lugar não depende do que a operação tem hoje: todo card
    # que aparecer tem de estar numa coluna DESTA aba. É assim que se pega
    # card órfão sem exigir fila vazia.
    etapas_desta_aba = {c["etapa_id"] for c in q["colunas"]}
    for coluna in q["colunas"]:
        for card in coluna["cards"]:
            assert card["etapa_id"] in etapas_desta_aba, card
    assert q["total"] == sum(len(c["cards"]) for c in q["colunas"])
    # ⚠️ E card fora de coluna é CONTADO, nunca escondido (`M12`).
    assert q["fora_do_quadro"] == 0, q["fora_do_quadro"]
    assert all(c["situacao_id"] is None for c in q["colunas"])


def teste_a_rota_devolve_o_quadro_para_o_owner(cliente, token_owner):
    r = cliente.get(f"/api/paineis/aba/{CODIGO}",
                    headers={"Authorization": f"Bearer {token_owner}"})
    assert r.status_code == 200
    assert [c["titulo"] for c in r.json()["colunas"]] == AS_SEIS


def teste_sem_login_e_401(cliente):
    assert cliente.get(f"/api/paineis/aba/{CODIGO}").status_code == 401


# ============================================================================
# OS CINCO PAINÉIS, JUNTOS
# ============================================================================
def teste_os_cinco_paineis_do_vocabulario_existem_agora():
    """🚨 O `paineis.PAINEIS` declarava quatro desde 22/10 e três não tinham
    tela. Com 096 e 097, os quatro têm. ⚠️ `COM_TELA` continua sendo só
    `operacao` de propósito: ele governa o `quadro()`, que fala com o Harmonit
    -- e os três novos passam pelo `quadro_da_aba`, que não fala."""
    abas = {r["painel"] for r in banco.varios(
        "SELECT DISTINCT painel FROM painel_aba WHERE ativo")}
    # 🔵 27/11: entrou `compras` (migração 122, `PNL_1.7`).
    # 🚨 E ESTA TRAVA FOI A QUE ME CORRIGIU. Eu havia concluído que
    # `paineis.PAINEIS` não precisava de `'compras'`, porque o
    # `quadro_da_aba` monta sem ele -- e monta mesmo. O que eu não vi é que a
    # igualdade abaixo é o que faz deste dicionário o VOCABULÁRIO declarado:
    # painel ativo no banco e ausente dele é divergência, e é justamente isso
    # que a linha pega. ⚠️ O teste mudou de NOME junto com o número, porque
    # deixá-lo chamando-se "os quatro" seria o nome mentindo.
    assert abas == {"operacao", "pos_venda", "contratual", "financeiro",
                    "compras"}
    assert set(paineis.PAINEIS) == abas


def teste_o_contratual_aparece_na_aba_de_permissao_sem_uma_linha_de_codigo():
    """🚨 A `CFG_15.1` não foi tocada por esta entrega nem pela do Financeiro.
    As cinco telas de painel aparecem lá porque a lista sai do REGISTRO."""
    assert CODIGO in permissao_paineis.codigos_concediveis()
    grade = permissao_paineis.grade()
    codigos = [t["codigo"] for t in grade["telas"]]
    # 🔵 18/11: entrou a `PNL_1.6`, a segunda aba do Financeiro
    # (*"Serviço dos técnicos"*). ⚠️ UMA ENTRADA POR ABA porque a
    # permissão é campo da entrada -- 🔵 *"a Karla tera permissao para ver
    # o 'Financeiro' e todas as abas. A Erika, apenas a aba 3"*.
    # 🔵 27/11: entrou a `PNL_1.7`, Compras -- e OUTRA VEZ sem uma linha de
    # código na `CFG_15.1`: a lista sai do REGISTRO, e Compras nasce lá
    # porque `grupo_da(t) == "Painéis"`. 🔵 Ele, no mesmo dia: *"inserir na
    # tela de permissoes de acesso e depois eu defino quem verá"*.
    assert codigos == ["PNL_1.1", "PNL_1.2", "PNL_1.3", "PNL_1.4",
                       "PNL_1.5", "PNL_1.6", "PNL_1.7"]
    contratual = [t for t in grade["telas"] if t["codigo"] == CODIGO][0]
    assert contratual["aba_titulo"] == "Contratual"
    donos = [p for p in grade["pessoas"] if p["owner"]]
    assert donos and CODIGO in donos[0]["concedidas"]


def teste_os_cinco_paineis_tem_item_de_menu_proprio_para_o_owner():
    """⚠️ Os três novos NÃO levam `aba_de`: cada um é um item. O Pós-venda
    continua sendo UM item com duas abas dentro (correção dele de 05/11)."""
    telas = registro_telas.do_usuario({"owner": True})
    pnl = [t for t in telas if t["codigo"].startswith("PNL_")]
    # 🔵 18/11: a `PNL_1.6` entrou -- a segunda aba do
    # Financeiro, *"Serviço dos técnicos"*. São SEIS
    # entradas de menu agora, e uma por ABA porque a
    # permissão é campo da entrada.
    # 🔵 27/11: SETE entradas -- entrou a `PNL_1.7` (Compras).
    assert len(pnl) == 7
    sem_aba_de = [t["codigo"] for t in pnl if not t["aba_de"]]
    # 🚨 A `PNL_1.6` NÃO entra aqui, e eu errei isso primeiro: ela é a
    # SEGUNDA aba do Financeiro, então leva `aba_de: PNL_1.4` -- 🔵 *"só
    # aba principal no menu. As demais são dentro dela já"*. Sem o
    # campo, o Financeiro ganharia dois itens de menu, que é o que ele
    # mandou não fazer em 05/11.
    # 🔵 27/11: CINCO itens de menu -- Compras entra como item porque não
    # tem `aba_de`. As duas sem item continuam sendo a `PNL_1.3` (dentro do
    # Pós-venda) e a `PNL_1.6` (dentro do Financeiro).
    assert sem_aba_de == ["PNL_1.1", "PNL_1.2", "PNL_1.4", "PNL_1.5",
                          "PNL_1.7"]
    # 🚨 A `PNL_1.3` é a única com `aba_de`, e é a de dentro do Pós-venda.
    # 🔵 18/11: passaram a ser DUAS as telas de painel com `aba_de` -- a
    # `PNL_1.3` (aba 2 do Pós-venda) e a `PNL_1.6` (aba 2 do Financeiro,
    # *"Serviço dos técnicos"*).
    # 🚨 A regra é a dele, de 05/11: *"só aba principal no menu. As demais
    # são dentro dela já"*. Então painel com duas abas tem UM item de
    # menu, e a segunda aba se alcança pela tira de dentro.
    assert [t["codigo"] for t in pnl if t["aba_de"]] == ["PNL_1.3",
                                                         "PNL_1.6"]
