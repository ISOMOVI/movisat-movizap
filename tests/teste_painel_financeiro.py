# -*- coding: utf-8 -*-
r"""O PAINEL DO FINANCEIRO — a `PNL_1.4` e as dez colunas dele (06/11).

🔵 Pedido dele: *"do 1"* — as colunas do Financeiro, que era a pendência de
05/11 — seguido da lista das dez, e *"conclua e exiba o financeiro no paniel
para owner"*.

🚨 **AS CINCO REGRAS QUE ESTE ARQUIVO PRENDE:**

1. **AS DEZ COLUNAS SÃO AS DELE, NA ORDEM DELE.** Ordem é a coisa mais fácil de
   perder: um `sorted()` bem-intencionado destruiria o fluxo sem quebrar nada
   visível. A comparação é da lista inteira, posição por posição.
2. **"INADIMPLENTES" ENTRA SEM A AUTOMAÇÃO.** Ele escreveu *"INADIMPLENTES
   (Automação move para pipeline Cobrança)"* — o parêntese é comportamento
   futuro, e o painel "Cobrança" **não existe** nem no vocabulário do banco.
   ⚠️ A trava prende os dois lados: o nome da coluna é só `INADIMPLENTES`, e
   **não há `Cobrança` em painel nenhum** — para o dia em que alguém "lembrar"
   de ligar a automação e mover card para o vazio.
3. **DOIS FINS, e não um.** "Atendimento feito" e "Não atendido" são os dois
   fins; marcar só a última diria que chegar em "Atendimento feito" não é
   terminar.
4. **ESTA TELA NÃO FALA COM O HARMONIT.** As colunas são nossas; mover escreve
   só aqui.
5. 🚨 **A TELA APARECE SOZINHA NA ABA DE PERMISSÃO** (`CFG_15.1`, de hoje mais
   cedo), porque a lista de concedíveis sai do REGISTRO e não de lista escrita à
   mão. Era o desenho; esta é a primeira prova dele com um painel que não
   existia quando a aba nasceu.

Roda:  venv/bin/python -m pytest tests/teste_painel_financeiro.py
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

CODIGO = "PNL_1.4"

# 🔵 As dez, na ordem dele, copiadas da mensagem de 06/11.
AS_DEZ = [
    "Nova solicitação",
    "Contratos assinados",
    "Contrato vinculado no financeiro",
    "Aguardando prazo",
    "Aguardando Datascope",
    "Em tratativa",
    "Aguardando terceiros",
    "INADIMPLENTES",
    "Atendimento feito",
    "Não atendido",
]
OS_DOIS_FINS = {"Atendimento feito", "Não atendido"}


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
# O CATÁLOGO — sem entrada no `telas.py` a tela sobe INVISÍVEL
# ============================================================================
def teste_a_tela_tem_entrada_no_catalogo():
    """🚨 Lição dele de 03/11: *"ESTÁ NO AR NÃO É 200"*."""
    t = registro_telas.por_codigo(CODIGO)
    assert t["titulo"] == "Financeiro"
    assert t["rota"] == "/paineis/financeiro"
    assert t["grupo"] == "Painéis"
    # 🔵 *"exiba o financeiro no paniel para owner"*.
    assert t["permissao"] == "owner"
    assert t["fase"] == 1
    # ⚠️ NÃO é aba de ninguém: é painel próprio, com item de menu próprio.
    assert t.get("aba_de") is None


def teste_o_painel_chega_ao_menu_do_owner():
    """⚠️ `do_usuario` monta a resposta à mão: campo ou tela que não entra nessa
    montagem fica no registro e nunca chega ao menu (defeito de 27/08)."""
    vistas = {t["codigo"] for t in registro_telas.do_usuario({"owner": True})}
    assert CODIGO in vistas


def teste_quem_nao_e_owner_nao_ve_o_financeiro():
    u = {"permissoes": ["atendimento", "equipe"]}
    assert registro_telas.pode_acessar(u, CODIGO) is False


# ============================================================================
# AS DEZ COLUNAS — as dele, na ordem dele
# ============================================================================
def teste_as_dez_colunas_sao_as_dele_e_na_ordem_dele():
    aba = pipeline.aba_por_codigo(CODIGO)
    assert aba is not None
    assert aba["painel"] == "financeiro"
    assert aba["titulo"] == "Financeiro"
    etapas = [e["titulo"] for e in pipeline.etapas(aba["id"])]
    assert etapas == AS_DEZ
    # ⚠️ Ordem NÃO é alfabética: um `sorted()` destruiria o fluxo em silêncio.
    assert etapas != sorted(etapas)


def teste_sao_dez_e_nenhuma_coluna_a_mais():
    """⚠️ Conta fechada: coluna sobrando é tão errado quanto coluna faltando --
    e seria o sintoma de a migração ter rodado duas vezes com nome diferente."""
    aba = pipeline.aba_por_codigo(CODIGO)
    assert len(pipeline.etapas(aba["id"])) == 10


def teste_os_dois_fins_sao_os_dois_e_so_eles():
    """🚨 Dois fins, e não um. No Pós-venda só a última era `final` porque só
    havia um fim; aqui marcar só "Não atendido" diria que chegar em "Atendimento
    feito" não é terminar -- e isso é falso."""
    aba = pipeline.aba_por_codigo(CODIGO)
    finais = {e["titulo"] for e in pipeline.etapas(aba["id"]) if e["final"]}
    assert finais == OS_DOIS_FINS


class TestInadimplentes:
    """🚨 O parêntese dele era COMPORTAMENTO, não nome de coluna."""

    def teste_a_coluna_se_chama_so_INADIMPLENTES(self):
        aba = pipeline.aba_por_codigo(CODIGO)
        titulos = [e["titulo"] for e in pipeline.etapas(aba["id"])]
        assert "INADIMPLENTES" in titulos
        # ⚠️ Nenhum título carrega a anotação da automação.
        assert not [t for t in titulos if "Automa" in t or "Cobran" in t]

    def teste_o_painel_Cobranca_nao_existe_em_lugar_nenhum(self):
        """🚨 A trava que impede alguém de "lembrar" de ligar a automação: o
        destino dela não existe, nem como tela, nem no vocabulário de painel
        (`painel_aba_painel_conhecido`), nem como aba no banco. Mover card para
        pipeline que não existe não é automação, é perder o card.
        """
        assert "cobranca" not in paineis.PAINEIS
        assert not [c for c in registro_telas.CODIGOS_VALIDOS
                    if "COB" in c.upper()]
        assert banco.um("SELECT count(*) n FROM painel_aba "
                        "WHERE painel = 'cobranca'")["n"] == 0


# ============================================================================
# O QUADRO — vazio, e a tela DIZ isso
# ============================================================================
def teste_o_quadro_abre_com_as_dez_colunas_e_zero_cards():
    """🔴 Nascer vazio é ESTADO, não defeito: a origem dos cards segue em aberto
    por decisão dele (*"3 por enquanto matem assim"*). ⚠️ E a `PainelAba` escreve
    *"Nenhum card nesta aba ainda."* -- quadro vazio que não explica por que está
    vazio é `M12`."""
    q = paineis.quadro_da_aba(CODIGO)
    assert q is not None
    assert q["painel"] == "financeiro"
    assert [c["titulo"] for c in q["colunas"]] == AS_DEZ
    assert q["total"] == 0
    # 🚨 `situacao_id` nulo em TODAS: aqui não existe coluna do ERP.
    assert all(c["situacao_id"] is None for c in q["colunas"])


# ============================================================================
# POR HTTP
# ============================================================================
def teste_a_rota_devolve_o_quadro_para_o_owner(cliente, token_owner):
    r = cliente.get(f"/api/paineis/aba/{CODIGO}",
                    headers={"Authorization": f"Bearer {token_owner}"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["aba"] == CODIGO
    assert [c["titulo"] for c in corpo["colunas"]] == AS_DEZ


def teste_sem_login_e_401(cliente):
    assert cliente.get(f"/api/paineis/aba/{CODIGO}").status_code == 401


# ============================================================================
# 🚨 A PROVA DO DESENHO DA `CFG_15.1`: painel novo entra SOZINHO
# ============================================================================
def teste_o_financeiro_aparece_na_aba_de_permissao_sem_uma_linha_de_codigo():
    """🚨 A `CFG_15.1` nasceu de manhã com três painéis e NÃO foi tocada por
    esta entrega. A lista de concedíveis sai do grupo "Painéis" do REGISTRO --
    se saísse de lista escrita à mão, o Financeiro ficaria de fora e ninguém
    descobriria até ele procurar a coluna e não achar.
    """
    assert CODIGO in permissao_paineis.codigos_concediveis()
    grade = permissao_paineis.grade()
    codigos = [t["codigo"] for t in grade["telas"]]
    assert CODIGO in codigos
    # 🚨 NÃO FIXA A LISTA INTEIRA, e isto é conserto de um defeito meu de hoje:
    # a primeira versão asseverava `== ["PNL_1.1", ..., "PNL_1.4"]` e ficou
    # vermelha meia hora depois, quando o Contratual (`PNL_1.5`) entrou. Um
    # teste que existe para provar que *"painel novo entra sozinho"* não pode
    # ser justamente o que obriga a editar teste quando um painel novo entra.
    # ⚠️ A asseveração certa é a ORDEM DO REGISTRO, que é o contrato real.
    do_registro = [t["codigo"] for t in registro_telas.ativas()
                   if registro_telas.grupo_da(t) == "Painéis"]
    assert codigos == do_registro
    # ⚠️ E a coluna leva o título da ABA, que é o que distingue as do Pós-venda.
    financeiro = [t for t in grade["telas"] if t["codigo"] == CODIGO][0]
    assert financeiro["aba_titulo"] == "Financeiro"
    assert financeiro["aba_de"] is None
    # ⚠️ O owner continua com TODAS marcadas -- agora quatro, não três.
    donos = [p for p in grade["pessoas"] if p["owner"]]
    assert donos and CODIGO in donos[0]["concedidas"]
