"""Painéis por setor — o da Operação (22/10, migrações 075 e 076).

🔵 Decisão dele depois de ver três mockups lado a lado: *"vamos de A somente
para a Operação por enquanto, mas bem documentado para as demais
futuramente"*.

O que esta suíte guarda:

  · 🚨 **o mapa formulário → painel é DADO** (coluna `formulario.painel`), e
    "sem painel" é um valor legítimo -- o formulário de Contato não aparece em
    painel nenhum, por decisão dele;
  · 🚨 **a coluna "Sem situação" existe e recebe os três casos** que não são
    uma das 11 situações: `situacao_id` nulo, zero, e um número que não está na
    lista. Em 22/10, **164 das 574 OS** do cache do FPSL estavam em `0` ou
    `NULL` -- sem essa coluna, desapareceriam da tela;
  · **o painel só mostra o que é dele**: solicitação de outro painel não entra;
  · **os três painéis que ainda não existem recusam com uma frase que diz
    isso**, não com 404 -- 404 faria parecer erro de digitação;
  · `pode_mover` é FALSO e traz o porquê: a rota que escreve `situacaoId` no
    Harmonit ainda não existe, e oferecer o gesto sem gravar seria pior.

🚨 ESCREVE EM TABELAS DE PRODUÇÃO (`formulario`, `formulario_solicitacao`),
como o resto da suíte: tudo com o código `ZZ_TESTE_PNL` e apagado no fim.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, formularios, paineis, telas  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

RAIZ = Path("/home/claude/movizap_painel")
MAPA = json.loads((RAIZ / "dados" / "formularios_bitrix" / "mapa_bruto.json")
                  .read_text(encoding="utf-8"))

CODIGO = "ZZ_TESTE_PNL"
SLUG = "zz-teste-pnl"


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield


@pytest.fixture
def formulario_de_operacao():
    """Um formulário de teste NO painel da Operação, apagado no fim.

    ⚠️ A solicitação sai primeiro: a FK não é `ON DELETE CASCADE` de propósito
    (o que o cliente escreveu não desaparece porque alguém mexeu na
    definição).
    """
    def apagar():
        banco.executar(
            """DELETE FROM formulario_solicitacao
                WHERE formulario_id IN (SELECT id FROM formulario
                                         WHERE codigo = %s)""", (CODIGO,))
        banco.executar("DELETE FROM formulario WHERE codigo = %s", (CODIGO,))

    apagar()
    formularios.gravar_definicao(MAPA["32"], codigo=CODIGO, slug=SLUG,
                                 setor="Teste", titulo="zz Teste painel",
                                 painel="operacao")
    d = formularios.definicao(SLUG, so_ativo=False)
    yield d
    apagar()


def solicitar(d, **campos):
    """Grava uma solicitação e, se pedido, finge a OS que ela gerou."""
    r = formularios.registrar(d, {"CONTACT_NAME": "zz Painel"})
    if campos:
        sets = ", ".join(f"{k} = %s" for k in campos)
        banco.executar(
            f"UPDATE formulario_solicitacao SET {sets} WHERE id = %s",
            (*campos.values(), r["id"]))
    return r["id"]


# ============================================================================
# O mapa é dado
# ============================================================================
def teste_o_mapa_dos_quatro_paineis_esta_no_banco():
    """🔵 O mapa dele (plano, §2.1), e ele vive em coluna -- mover um
    formulário de painel não pode exigir deploy."""
    por_painel = {
        (r["painel"] or "sem_painel"): r["n"] for r in banco.varios(
            "SELECT painel, count(*) AS n FROM formulario GROUP BY painel")}
    assert por_painel.get("operacao") == 4
    assert por_painel.get("pos_venda") == 2
    assert por_painel.get("contratual") == 4
    assert por_painel.get("financeiro") == 4
    # 🚨 "SEM PAINEL — Contato" é decisão dele, não cadastro incompleto.
    assert por_painel.get("sem_painel") == 1
    assert banco.um("SELECT painel FROM formulario WHERE codigo = 'CONTATO'")["painel"] is None


def teste_os_quatro_da_operacao_sao_os_que_ele_nomeou():
    codigos = [f["codigo"] for f in paineis.quadro("operacao")["formularios"]]
    assert set(codigos) == {"SUPORTE", "DEMONSTRACAO", "TESTE_GRATUITO",
                            "CREDENCIAMENTO"}


def teste_recarregar_nao_muda_o_painel_nem_liga_formulario(formulario_de_operacao):
    """A carga reescreve o painel (é o mapa dele) e NÃO toca em `ativo`."""
    banco.executar("UPDATE formulario SET ativo = true WHERE codigo = %s", (CODIGO,))
    formularios.gravar_definicao(MAPA["32"], codigo=CODIGO, slug=SLUG,
                                 setor="Teste", painel="operacao")
    linha = banco.um("SELECT painel, ativo FROM formulario WHERE codigo = %s", (CODIGO,))
    assert linha["painel"] == "operacao"
    assert linha["ativo"] is True


# ============================================================================
# As colunas
# ============================================================================
def teste_as_colunas_sao_as_11_situacoes_mais_duas():
    q = paineis.quadro("operacao")
    assert len(q["colunas"]) == len(paineis.SITUACOES) + 2
    # 🚨 A ORDEM É O DESENHO: "Sem OS" primeiro, porque é de onde a OS nasce.
    assert q["colunas"][0]["chave"] == "sem_os"
    assert q["colunas"][1]["chave"] == "sem_situacao"
    assert q["colunas"][2]["situacao_id"] == 38


def teste_solicitacao_sem_os_fica_na_primeira_coluna(formulario_de_operacao):
    ident = solicitar(formulario_de_operacao)
    q = paineis.quadro("operacao")
    sem_os = next(c for c in q["colunas"] if c["chave"] == "sem_os")
    assert ident in [c["id"] for c in sem_os["cards"]]


@pytest.mark.parametrize("situacao", [None, 0, 99999])
def teste_os_tres_casos_sem_situacao_caem_na_mesma_coluna(
        formulario_de_operacao, situacao):
    """🚨 Nulo (nunca lida), zero (o Harmonit respondeu 0) e um número fora da
    lista das 11. Em 22/10, 127 OS estavam em `0` e 37 em `NULL`."""
    ident = solicitar(formulario_de_operacao, os_id=99901, situacao_id=situacao)
    q = paineis.quadro("operacao")
    coluna = next(c for c in q["colunas"] if c["chave"] == "sem_situacao")
    assert ident in [c["id"] for c in coluna["cards"]]


def teste_situacao_conhecida_vai_para_a_coluna_dela(formulario_de_operacao):
    ident = solicitar(formulario_de_operacao, os_id=99902, situacao_id=15746)
    q = paineis.quadro("operacao")
    coluna = next(c for c in q["colunas"] if c["situacao_id"] == 15746)
    assert ident in [c["id"] for c in coluna["cards"]]
    assert coluna["titulo"] == "Financeiro"


def teste_o_card_leva_a_os_e_a_situacao_crua(formulario_de_operacao):
    """A solicitação E a OS lado a lado, como ele pediu -- e a situação crua à
    vista, nunca um rótulo inventado."""
    ident = solicitar(formulario_de_operacao, os_id=99903, numero_ordem="17042",
                      situacao_id=0)
    q = paineis.quadro("operacao")
    card = next(c for coluna in q["colunas"] for c in coluna["cards"]
                if c["id"] == ident)
    assert card["numero_ordem"] == "17042"
    assert card["situacao_id"] == 0


def teste_solicitacao_de_outro_painel_nao_entra(formulario_de_operacao):
    """O CES é de Pós venda: não pode aparecer na Operação."""
    ces = formularios.definicao("ces", so_ativo=False)
    r = formularios.registrar(ces, {"CONTACT_NAME": "zz Painel outro"})
    try:
        ids = [c["id"] for coluna in paineis.quadro("operacao")["colunas"]
               for c in coluna["cards"]]
        assert r["id"] not in ids
    finally:
        banco.executar("DELETE FROM formulario_solicitacao WHERE id = %s", (r["id"],))


# ============================================================================
# O que ainda não existe — e a tela diz
# ============================================================================
def teste_mover_ainda_nao_existe_e_o_painel_explica():
    q = paineis.quadro("operacao")
    assert q["pode_mover"] is False
    assert "Harmonit" in q["porque_nao_move"]


@pytest.mark.parametrize("painel", ["pos_venda", "contratual", "financeiro"])
def teste_os_tres_paineis_sem_tela_recusam_dizendo_o_que_sao(painel):
    """🚨 Não é 404: 404 faria parecer erro de digitação. A frase diz que o
    painel está desenhado e esperando decisão dele."""
    with pytest.raises(DadoInvalido) as e:
        paineis.quadro(painel)
    assert "ainda não existe" in str(e.value)


def teste_painel_inventado_e_recusado():
    with pytest.raises(DadoInvalido):
        paineis.quadro("marketing")


# ============================================================================
# Permissão
# ============================================================================
def teste_o_painel_e_do_owner():
    """⚠️ `owner`, não `equipe`: o card mostra a OS do Harmonit e mover o card
    vai escrever no ERP."""
    assert telas.pode_acessar({"owner": True, "permissoes": []}, "PNL_1.1")
    for perfil in ("admin", "atendimento", "cadastro"):
        usuario = {"owner": False, "permissoes": list(telas.PERFIS[perfil] or [])}
        assert not telas.pode_acessar(usuario, "PNL_1.1"), perfil


def teste_o_grupo_paineis_deixou_de_nascer_vazio():
    """🔵 19/10 ele criou o grupo vazio; 22/10 ele ganhou o primeiro habitante.

    ⚠️ E o subgrupo "Operacional" saiu: nunca teve tela, e o painel chama-se
    "Operação" -- manter os dois faria o menu desenhar
    "Painéis › Operacional › Operação". Fecha a pendência 6 do plano.
    """
    assert telas.GRUPOS["Painéis"] == []
    dentro = [t["codigo"] for t in telas.TELAS if telas.grupo_da(t) == "Painéis"]
    assert dentro == ["PNL_1.1"]
