"""Painéis por setor — o da Operação (22/10, migrações 075 e 076).

🔵 Decisão dele depois de ver três mockups lado a lado: *"vamos de A somente
para a Operação por enquanto, mas bem documentado para as demais
futuramente"*.

O que esta suíte guarda:

  · 🚨 **o mapa formulário → painel é DADO** (coluna `formulario.painel`), e
    "sem painel" é um valor legítimo -- o formulário de Contato não aparece em
    painel nenhum, por decisão dele;
  · 🚨 **as colunas são EXATAMENTE as 17 situações dele, na ordem dele**
    (29/10: *"qualquer aba fora dessas não deve estar no painel"* e *"as
    situações já estão na Ordem"*). ⚠️ Até 28/10 eram 13 -- as 11 situações de
    então mais "Sem OS" e "Sem situação" --, e as duas saíram porque o motivo
    de cada uma caiu no mesmo dia: a OS passou a nascer **automática no envio**
    (antes era por botão), e as 164 OS com situação 0/nula são de outras
    origens, não solicitações deste painel;
  · 🚨 **e o que não tem coluna é CONTADO, não escondido** (`fora_do_quadro`):
    solicitação sem OS ou com situação fora das 17 não cabe em coluna nenhuma,
    e sumir da tela é `M12`;
  · **o painel só mostra o que é dele**: solicitação de outro painel não entra;
  · **os três painéis que ainda não existem recusam com uma frase que diz
    isso**, não com 404 -- 404 faria parecer erro de digitação;
  · `pode_mover` é FALSO: a rota que escreve `situacaoId` no Harmonit ainda
    não existe, e oferecer o gesto sem gravar seria pior. ⚠️ A FRASE que
    explicava isso na tela saiu em 29/10, a pedido dele (*"os comentários tbm
    devem sumir dali"*) -- o comportamento não mudou, e é o que este teste
    guarda.

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
    """⚠️ Lido do BANCO, não da resposta do painel: a lista de formulários saiu
    do quadro em 29/10 (ele mandou tirar da tela), mas o mapa continua sendo o
    dele e continua tendo de ser estes quatro."""
    codigos = {r["codigo"] for r in banco.varios(
        "SELECT codigo FROM formulario WHERE painel = 'operacao'")}
    assert codigos == {"SUPORTE", "DEMONSTRACAO", "TESTE_GRATUITO",
                       "CREDENCIAMENTO"}


def teste_a_resposta_do_painel_nao_traz_mais_a_lista_de_formularios():
    """🔵 29/10: *"os comentários tbm devem sumir dali"* -- a lista com a
    contagem de campos saiu da tela, e o backend parou de mandá-la."""
    assert "formularios" not in paineis.quadro("operacao")


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
def teste_as_colunas_sao_exatamente_as_dezessete_dele():
    """🔵 29/10: *"qualquer aba fora dessas não deve estar no painel"*."""
    q = paineis.quadro("operacao")
    assert len(paineis.SITUACOES) == 17
    assert len(q["colunas"]) == 17
    # 🚨 Toda coluna É uma situação -- não há mais coluna sem `situacao_id`.
    assert all(c["situacao_id"] for c in q["colunas"])


def teste_a_ordem_das_colunas_e_a_dele_e_nao_alfabetica_nem_por_id():
    """🔵 *"as situações já estão na Ordem"* -- a ordem é o FLUXO da operação.

    🚨 Este teste existe porque ordem é a coisa mais fácil de perder: qualquer
    `sorted()` bem-intencionado em cima de `SITUACOES` destruiria o desenho sem
    quebrar nada visível.
    """
    q = paineis.quadro("operacao")
    titulos = [c["titulo"] for c in q["colunas"]]
    assert titulos[0] == "Novo Solicitação 1ª"
    assert titulos[1] == "Pendente de ação da Movisat"
    assert titulos[-1] == "Contratual"
    assert titulos != sorted(titulos)
    ids = [c["situacao_id"] for c in q["colunas"]]
    assert ids != sorted(ids)
    # E o começo do fluxo é a situação em que a OS nasce.
    assert ids[0] == 38


def teste_a_solicitacao_sem_os_e_contada_em_vez_de_escondida(formulario_de_operacao):
    """🚨 `M12`: a coluna "Sem OS" saiu, e o card não tem onde cair -- mas o
    número aparece. Sumir em silêncio seria o defeito."""
    ident = solicitar(formulario_de_operacao)
    q = paineis.quadro("operacao")
    nos_cards = [c["id"] for coluna in q["colunas"] for c in coluna["cards"]]
    assert ident not in nos_cards
    assert q["fora_do_quadro"]["sem_os"] >= 1


@pytest.mark.parametrize("situacao", [None, 0, 99999])
def teste_situacao_fora_das_dezessete_e_contada_com_o_numero_cru(
        formulario_de_operacao, situacao):
    """Nulo (nunca lida), zero (o Harmonit respondeu 0) e um número que não
    está na lista. ⚠️ O número cru aparece, nunca um rótulo inventado -- é a
    régua do grid do FPSL."""
    solicitar(formulario_de_operacao, os_id=99901, situacao_id=situacao)
    fora = paineis.quadro("operacao")["fora_do_quadro"]
    assert fora["situacao_fora"] >= 1
    if situacao is not None:
        assert situacao in fora["situacoes"]


def teste_situacao_conhecida_vai_para_a_coluna_dela(formulario_de_operacao):
    ident = solicitar(formulario_de_operacao, os_id=99902, situacao_id=15746)
    q = paineis.quadro("operacao")
    coluna = next(c for c in q["colunas"] if c["situacao_id"] == 15746)
    assert ident in [c["id"] for c in coluna["cards"]]
    assert coluna["titulo"] == "Financeiro"


def teste_o_card_leva_a_os_e_a_situacao_crua(formulario_de_operacao):
    """A solicitação E a OS lado a lado, como ele pediu -- e a situação à vista.

    ⚠️ Com uma situação DAS 17: até 28/10 este teste usava `situacao_id = 0`,
    que ia para a coluna "Sem situação". Ela não existe mais, e com zero o card
    não teria coluna nenhuma.
    """
    ident = solicitar(formulario_de_operacao, os_id=99903, numero_ordem="17042",
                      situacao_id=15746)
    q = paineis.quadro("operacao")
    card = next(c for coluna in q["colunas"] for c in coluna["cards"]
                if c["id"] == ident)
    assert card["numero_ordem"] == "17042"
    assert card["situacao_id"] == 15746


def teste_solicitacao_de_outro_painel_nao_entra(formulario_de_operacao):
    """O CES é de Pós venda: não pode aparecer na Operação -- nem nos cards,
    nem na conta do que ficou fora."""
    ces = formularios.definicao("ces", so_ativo=False)
    antes = paineis.quadro("operacao")["fora_do_quadro"]["sem_os"]
    r = formularios.registrar(ces, {"CONTACT_NAME": "zz Painel outro"})
    try:
        q = paineis.quadro("operacao")
        ids = [c["id"] for coluna in q["colunas"] for c in coluna["cards"]]
        assert r["id"] not in ids
        # ⚠️ E nem na contagem: ela é só do painel, não do banco todo.
        assert q["fora_do_quadro"]["sem_os"] == antes
    finally:
        banco.executar("DELETE FROM formulario_solicitacao WHERE id = %s", (r["id"],))


# ============================================================================
# O que ainda não existe — e a tela diz
# ============================================================================
def teste_mover_ainda_nao_existe_e_a_frase_saiu_da_tela():
    """⚠️ Duas coisas, e elas são diferentes: mover continua não existindo
    (`pode_mover` falso, e é o que impede o `draggable`), e a FRASE que
    explicava isso saiu em 29/10 a pedido dele."""
    q = paineis.quadro("operacao")
    assert q["pode_mover"] is False
    assert "porque_nao_move" not in q


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

# ============================================================================
# BLOCO B — o card é a OS, de qualquer origem (D8)
# ============================================================================
# 🔵 *"seja pelo painel, seja pelo FPSL, seja pelo formulario, seja a mão"*.
#
# ⚠️ A PONTE É TROCADA POR DUBLÊ em tudo o que segue: a suíte não pode
# depender do FPSL de pé, nem do que o ERP tem hoje.
def _duble_de_os(**extra):
    base = {
        "numero_os": 17099, "os_id": 927999, "situacao_id": 38,
        "sem_situacao": False, "situacao_zero": False, "tem_coluna": True,
        "tipo": 1783, "tipo_nome": "Solicitação de Cliente", "problema": 12760,
        "produto_id": 670990, "cliente_id": 68546,
        "data_previsao": "29/10/2026 10:00:00", "status": 2,
        "status_str": "Nova", "finalizada": False, "placas": [],
        "n_oficinas": 0, "tecnicos": [], "visto_em": "2026-10-29T18:00:00Z",
        "atualizado_em": "2026-10-29T18:00:00Z",
    }
    base.update(extra)
    return base


@pytest.fixture
def ponte_de_os(monkeypatch):
    def instalar(*os_do_erp, estoura=None):
        def falso(desde, so_abertas=True, teto=600):
            if estoura:
                raise estoura
            return {"desde": desde, "so_abertas": so_abertas,
                    "quantas": len(os_do_erp), "no_teto": False,
                    "sem_coluna": 0, "os": list(os_do_erp)}
        monkeypatch.setattr(paineis.fpsl_ponte, "os_por_situacao", falso)
    return instalar


def teste_os_do_erp_sem_solicitacao_viram_card(ponte_de_os):
    """🔵 D8: a OS aberta à mão no Harmonit é card. É a MAIORIA hoje -- 10 dos
    10 cards medidos em 29/10 não têm solicitação."""
    ponte_de_os(_duble_de_os())
    q = paineis.quadro("operacao")
    coluna = next(c for c in q["colunas"] if c["situacao_id"] == 38)
    card = next(c for c in coluna["cards"] if c["numero_ordem"] == 17099)
    assert card["origem"] == "erp"
    assert card["slug"] is None
    assert card["tipo_nome"] == "Solicitação de Cliente"


def teste_a_mesma_os_nao_vira_dois_cards(formulario_de_operacao, ponte_de_os):
    """🚨 A deduplicação é pelo `numero_ordem`: a solicitação e a OS do ERP são
    a MESMA coisa vista de dois lados."""
    sid = solicitar(formulario_de_operacao, os_id=927999,
                    numero_ordem="17099", situacao_id=38)
    ponte_de_os(_duble_de_os())
    q = paineis.quadro("operacao")
    todos = [c for col in q["colunas"] for c in col["cards"]
             if c["numero_ordem"] in (17099, "17099")]
    assert len(todos) == 1
    # 🚨 E o card ganha os DOIS lados: o chamado (slug) e a OS (tipo_nome).
    assert todos[0]["slug"] == SLUG
    assert todos[0]["id"] == sid
    assert todos[0]["tipo_nome"] == "Solicitação de Cliente"


def teste_ponte_caida_nao_esvazia_o_painel(formulario_de_operacao, ponte_de_os):
    """🚨 Quadro vazio por falha de rede faria o operador concluir que não há
    trabalho -- e é justo nessa hora que há. A tela cai para o nosso banco e
    DIZ que caiu."""
    solicitar(formulario_de_operacao, os_id=1, numero_ordem="555",
              situacao_id=38)
    ponte_de_os(estoura=RuntimeError("o FPSL nao respondeu no tempo"))
    q = paineis.quadro("operacao")
    assert q["ponte_respondeu"] is False
    assert "nao respondeu" in q["ponte_motivo"]
    # 🚨 E o card do nosso banco CONTINUA LÁ.
    coluna = next(c for c in q["colunas"] if c["situacao_id"] == 38)
    assert any(c["numero_ordem"] == "555" for c in coluna["cards"])


def teste_os_com_situacao_fora_das_dezessete_e_contada(ponte_de_os):
    """🚨 `situacao_id = 0` não é situação, e esta volta NÃO o traduz -- são
    129 OS no cache e a tradução é decisão dele. Contada, nunca escondida."""
    ponte_de_os(_duble_de_os(numero_os=17098, situacao_id=0))
    q = paineis.quadro("operacao")
    assert q["fora_do_quadro"]["situacao_fora"] >= 1
    assert 0 in q["fora_do_quadro"]["situacoes"]


def teste_o_interruptor_chega_na_ponte(ponte_de_os, monkeypatch):
    """O `so_abertas` da tela tem de atravessar até a ponte."""
    vistos = []

    def falso(desde, so_abertas=True, teto=600):
        vistos.append(so_abertas)
        return {"desde": desde, "so_abertas": so_abertas, "quantas": 0,
                "no_teto": False, "sem_coluna": 0, "os": []}

    monkeypatch.setattr(paineis.fpsl_ponte, "os_por_situacao", falso)
    paineis.quadro("operacao", so_abertas=True)
    paineis.quadro("operacao", so_abertas=False)
    assert vistos == [True, False]


# ============================================================================
# A data matriz (D9)
# ============================================================================
def teste_a_data_matriz_nasce_no_dia_que_ele_pediu():
    """🔵 *"não vamos retroagir mais do que o dia que pedi"*."""
    assert paineis.DATA_MATRIZ_PADRAO == "2026-10-24"


def teste_data_matriz_torta_no_banco_nao_derruba_o_painel():
    """⚠️ Um `desde` inválido faria a ponte recusar com 422 e a tela abrir
    vazia. Cai no padrão e registra."""
    anterior = paineis.data_matriz()
    try:
        banco.executar(
            """INSERT INTO config (chave, valor, descricao, atualizado_em)
               VALUES (%s, %s, %s, now())
               ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor""",
            (paineis.CHAVE_DATA_MATRIZ, "24/10/2026", "zz teste"))
        assert paineis.data_matriz() == paineis.DATA_MATRIZ_PADRAO
    finally:
        paineis.definir_data_matriz(anterior)


def teste_definir_data_matriz_recusa_formato_errado():
    for torta in ("24/10/2026", "2026-13-01", "ontem", ""):
        with pytest.raises(DadoInvalido):
            paineis.definir_data_matriz(torta)


def teste_definir_data_matriz_grava_e_rele():
    """A prova é RELER o estado, nunca o retorno da escrita."""
    anterior = paineis.data_matriz()
    try:
        paineis.definir_data_matriz("2026-10-20")
        assert paineis.data_matriz() == "2026-10-20"
    finally:
        paineis.definir_data_matriz(anterior)
