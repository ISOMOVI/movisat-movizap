# -*- coding: utf-8 -*-
r"""A TIRA DE ABAS É DO PAINEL, e não de uma lista em código (06/11).

🔵 Achado por ele: *"os itens do pós venda estão aparecendo dentro do financeiro
e contratual. qual a dificuldade em natê-los separados?"* · e o desenho, no
minuto seguinte: *"o financeiro tera suas proprias abas, mas por agora só 1, o
mesmo para o contratual, só o pós venda ja temos as duas pipelines em abas"*.

🚨 **O DEFEITO.** A `PainelAba.vue` declarava `AS_ABAS = [PNL_1.2, PNL_1.3]` em
código e filtrava só por **permissão**. Eu reusei a tela nos dois painéis novos e
a tira foi junto: quem é owner tem as duas abas do Pós-venda, então a tira delas
aparecia **dentro** do Financeiro e do Contratual. ⚠️ Não era permissão errada —
era a lista **não ter dono**.

🚨 **A TRAVA É ESTRUTURAL, e tinha de ser.** Ela não diz "o Financeiro tem uma
aba": varre **todos** os painéis e cobra que as abas de um nunca apareçam no
quadro de outro. Assim, quando ele criar a segunda aba do Financeiro, a trava
continua valendo e nenhum teste precisa ser editado — foi o erro que eu já
cometi hoje com a lista fixa de painéis no `teste_permissao_paineis.py`.

Roda:  venv/bin/python -m pytest tests/teste_abas_por_painel.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from movizap import banco, paineis, pipeline  # noqa: E402
from movizap import telas as registro_telas  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield


def todas_as_abas():
    return banco.varios(
        "SELECT codigo_tela, painel, titulo FROM painel_aba WHERE ativo "
        "ORDER BY painel, ordem")


def teste_ha_mais_de_um_painel_com_aba():
    """Se o `SELECT` quebrar, tudo aqui passaria vazio e não protegeria nada."""
    paineis_com_aba = {a["painel"] for a in todas_as_abas()}
    assert len(paineis_com_aba) > 1


def teste_o_quadro_traz_as_abas_IRMAS_e_so_elas():
    """🚨 A trava do defeito dele, para TODOS os painéis de uma vez."""
    por_painel = {}
    for a in todas_as_abas():
        por_painel.setdefault(a["painel"], []).append(a["codigo_tela"])

    for a in todas_as_abas():
        q = paineis.quadro_da_aba(a["codigo_tela"])
        assert q is not None, a["codigo_tela"]
        vindas = [x["codigo_tela"] for x in q["abas"]]
        esperado = por_painel[a["painel"]]
        assert vindas == esperado, (
            f"{a['codigo_tela']} (painel {a['painel']}) devolveu {vindas}, "
            f"esperado {esperado}")
        # 🚨 E O ESSENCIAL: nenhuma aba de OUTRO painel entrou.
        de_fora = [c for c in vindas if c not in esperado]
        assert de_fora == [], f"{a['codigo_tela']} trouxe abas de fora: {de_fora}"


def teste_nenhuma_aba_de_um_painel_vaza_para_o_quadro_de_outro():
    """⚠️ O mesmo fato pelo outro lado, que é como o defeito aparecia na tela:
    abrir o Financeiro e ver "Treinamentos / Pós-venda"."""
    for a in todas_as_abas():
        q = paineis.quadro_da_aba(a["codigo_tela"])
        for outra in todas_as_abas():
            if outra["painel"] == a["painel"]:
                continue
            vindas = {x["codigo_tela"] for x in q["abas"]}
            assert outra["codigo_tela"] not in vindas, (
                f"a aba {outra['codigo_tela']} ({outra['painel']}) apareceu no "
                f"quadro de {a['codigo_tela']} ({a['painel']})")


def teste_a_tira_so_existe_com_mais_de_uma_aba():
    """🔵 *"o financeiro tera suas proprias abas, mas por agora só 1"*. A tela
    desenha a tira em `abasVisiveis.length > 1` -- com uma aba, nada. ⚠️ Esta
    trava descreve o ESTADO de hoje, e é a única daqui que muda de resultado
    quando ele criar a segunda aba do Financeiro; as outras continuam valendo."""
    quantas = {}
    for a in todas_as_abas():
        quantas[a["painel"]] = quantas.get(a["painel"], 0) + 1
    assert quantas["pos_venda"] == 2
    assert quantas["financeiro"] == 1
    assert quantas["contratual"] == 1


def teste_o_titulo_da_aba_vem_do_BANCO_e_nao_do_registro():
    """🚨 É o que distingue as duas do Pós-venda: no `telas.py` as duas se
    chamam "Pós-venda". Se a tira usasse o título do registro, a tela mostraria
    duas abas com o mesmo nome e escolher uma seria chute."""
    q = paineis.quadro_da_aba("PNL_1.2")
    titulos = [a["titulo"] for a in q["abas"]]
    assert titulos == ["Treinamentos", "Pós-venda"]
    do_registro = [registro_telas.por_codigo(a["codigo_tela"])["titulo"]
                   for a in q["abas"]]
    assert do_registro == ["Pós-venda", "Pós-venda"]
    assert titulos != do_registro


def teste_a_ordem_das_abas_e_a_do_banco_e_nao_alfabetica():
    """⚠️ A ordem é dele (*"Aba 1: Treinamentos / Aba 2: Pós-venda"*) e vive em
    `painel_aba.ordem`. Um `sorted()` poria "Pós-venda" antes de
    "Treinamentos"."""
    q = paineis.quadro_da_aba("PNL_1.2")
    titulos = [a["titulo"] for a in q["abas"]]
    assert titulos == ["Treinamentos", "Pós-venda"]
    assert titulos != sorted(titulos)


def teste_toda_aba_do_banco_tem_entrada_no_registro():
    """🚨 Lição dele de 03/11: tela sem registro sobe invisível. ⚠️ E aqui há um
    segundo motivo: o frontend resolve a ROTA de cada aba pelo `sessao.telas` --
    aba sem entrada no registro viraria um item de tira **sem link**."""
    for a in todas_as_abas():
        tela = registro_telas.por_codigo(a["codigo_tela"])
        assert tela["rota"], a["codigo_tela"]
        assert registro_telas.grupo_da(tela) == "Painéis", a["codigo_tela"]


def teste_as_abas_do_quadro_chegam_ao_menu_do_owner():
    """⚠️ A tira filtra pelo `sessao.telas`: se `do_usuario` não devolvesse a
    aba, a tira ficaria vazia para quem pode ver tudo."""
    vistas = {t["codigo"]: t for t in registro_telas.do_usuario({"owner": True})}
    for a in todas_as_abas():
        assert a["codigo_tela"] in vistas, a["codigo_tela"]
        assert vistas[a["codigo_tela"]]["rota"]


def teste_pipeline_abas_filtra_pelo_painel():
    """A função que o `quadro_da_aba` usa, conferida direto -- para o defeito
    não poder voltar por baixo, numa refatoração que troque a chamada."""
    for painel in ("pos_venda", "financeiro", "contratual"):
        for a in pipeline.abas(painel):
            assert a["painel"] == painel
