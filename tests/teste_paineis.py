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

from movizap import banco, formularios, paineis, pipeline, telas  # noqa: E402
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
    formulário de painel não pode exigir deploy.

    🚨 O MAPA MUDOU EM 12/11, e o registro da mudança é esta trava. Até 11/11
    valia *"o Contato e o IDEIAS não têm painel, e isso é decisão dele"*. Em
    12/11 ele decidiu o contrário: *"pode gerar card para Pós-venda"* e, sobre
    a etapa, *"isso, nova solicitação"*. A migração 108 é quem mudou o banco.
    O pós-venda passou de 2 para 4, e ninguém mais fica de fora.
    """
    por_painel = {
        (r["painel"] or "sem_painel"): r["n"] for r in banco.varios(
            "SELECT painel, count(*) AS n FROM formulario GROUP BY painel")}
    assert por_painel.get("operacao") == 4
    assert por_painel.get("pos_venda") == 4
    assert por_painel.get("contratual") == 4
    assert por_painel.get("financeiro") == 4

    # 🚨 A GUARDA SIMÉTRICA, que substitui a de "nomear os dois sem painel":
    # agora NENHUM formulário pode ficar sem painel. 🔵 12/11: *"a ideia é que
    # os formulários virem cards em todas as pipelines e não os mesmo"*.
    #
    # ⚠️ Formulário sem painel é exatamente o que some de toda fila sem
    # ninguém notar: o envio entra na lista de Solicitações e não nasce card
    # em lugar nenhum. Se um formulário novo nascer assim, fica vermelho aqui.
    assert por_painel.get("sem_painel") is None, (
        "formulario sem painel: "
        + str(sorted(r["codigo"] for r in banco.varios(
            "SELECT codigo FROM formulario WHERE painel IS NULL"))))

    # ⚠️ Os dois que mudaram, nomeados: contar sozinho deixaria passar uma
    # troca que levasse o Contato para outro painel sem ninguém decidir isso.
    for codigo in ("CONTATO", "IDEIAS"):
        linha = banco.um(
            "SELECT painel, ativo FROM formulario WHERE codigo = %s",
            (codigo,))
        assert linha["painel"] == "pos_venda", (codigo, linha["painel"])


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
    # 🔵 11/11, MAIS TARDE: SAO 14. As tres do fim (15746 Financeiro, 15695
    # Pos venda, 16492 Contratual) sairam por decisao dele -- *"essas etapas
    # finais do OP devem ser excluídas e deveria ter nascido no painel
    # Financeiro, na etapa correta 'Nova solicitação'"*.
    # 🚨 ELAS NAO FORAM APAGADAS: foram REENDERECADAS para os paineis
    # Financeiro, Pos-venda e Contratual (migracao 106), e ha trava propria
    # para isso em `teste_destino_do_card.py` -- inclusive a que garante que
    # nenhuma delas fique SEM destino, que e o caso em que a OS desapareceria
    # de todas as telas.
    assert len(paineis.SITUACOES) == 14
    # 🔵 05/11: SÃO 18, e a 18ª é a `Chamados` -- *"vamos criar uma coluna
    # nova antes de 'Nova solicitação', chamada 'Chamados'"*.
    # 🚨 As 17 DELE continuam 17: a `Chamados` não entra na `SITUACOES`, e é
    # essa separação que mantém esta trava dizendo o que ele pediu em 29/10
    # (*"qualquer aba fora dessas não deve estar no painel"*) sobre as colunas
    # do ERP, que são as únicas de que aquela frase falava.
    # 🔵 11/11: SÃO 19 — as 17 do ERP, a `Chamados` na frente e a
    # `Serviço Realizado` (etapa NOSSA, migração 105) depois da 1316.
    # ⚠️ `len(SITUACOES)` continua 17: as nossas não entram na tupla.
    # 🔵 11/11, mais tarde: 16 = as 14 do ERP + `Chamados` + `Servico
    # Realizado`.
    assert len(q["colunas"]) == 16
    # 🚨 Toda coluna de SITUAÇÃO é uma situação; a `Chamados` é etapa nossa,
    # e `situacao_id` nulo é o que a marca como tal.
    # 🚨 "DO ERP" DEIXOU DE SER "TUDO MENOS CHAMADOS" EM 11/11. Com a
    # `Serviço Realizado`, há DUAS etapas nossas, e o que as separa das do ERP
    # é o `situacao_id` nulo -- não o nome de uma delas. Esta linha dizia
    # `chave != "chamados"` e, com a etapa nova, passou a contar 18 "do ERP".
    do_erp = [c for c in q["colunas"] if c["situacao_id"] is not None]
    nossas = [c for c in q["colunas"] if c["situacao_id"] is None]
    assert len(do_erp) == 14
    assert len(nossas) == 2, [c["titulo"] for c in nossas]
    assert {c["titulo"] for c in nossas} == {"Chamados", "Serviço Realizado"}
    # ⚠️ E toda etapa nossa traz `etapa_id`: é por ele que o arrasto posta.
    assert all(c.get("etapa_id") for c in nossas)
    assert q["colunas"][0]["chave"] == "chamados"
    assert q["colunas"][0]["situacao_id"] is None


def teste_a_ordem_das_colunas_e_a_dele_e_nao_alfabetica_nem_por_id():
    """🔵 *"as situações já estão na Ordem"* -- a ordem é o FLUXO da operação.

    🚨 Este teste existe porque ordem é a coisa mais fácil de perder: qualquer
    `sorted()` bem-intencionado em cima de `SITUACOES` destruiria o desenho sem
    quebrar nada visível.
    """
    q = paineis.quadro("operacao")
    # 🔵 A `Chamados` vem ANTES de todas, e a ordem das 17 do ERP não se
    # mexeu: a análise do chamado acontece antes de existir OS.
    assert [c["titulo"] for c in q["colunas"]][0] == "Chamados"
    # 🔵 11/11: e a `Serviço Realizado` entra LOGO DEPOIS de `Serviço
    # Agendado`, que é a ordem que ele descreveu -- não no fim, nem por id.
    titulos = [c["titulo"] for c in q["colunas"]]
    assert titulos[titulos.index("Serviço Realizado") - 1] == "Serviço Agendado"
    # 🚨 A SEPARAÇÃO É POR `situacao_id` NULO, e não pelo nome de uma das
    # etapas nossas: desde 11/11 são duas (`Chamados` e `Serviço
    # Realizado`), e filtrar por `chave != "chamados"` deixava um nulo
    # entrar na comparação -- o `sorted()` estourava com `None < int`.
    do_erp = [c for c in q["colunas"] if c["situacao_id"] is not None]
    titulos = [c["titulo"] for c in do_erp]
    assert titulos[0] == "Novo Solicitação 1ª"
    assert titulos[1] == "Pendente de ação da Movisat"
    # 🔵 11/11: a ultima coluna do ERP deixou de ser `Contratual` -- ela saiu
    # da Operacao. A ultima agora e `Não atendido`, que era a penultima.
    # ⚠️ O que esta trava mede continua sendo a ORDEM DELE: a primeira, a
    # segunda e a ultima, e que a lista nao esta em ordem alfabetica nem por
    # id. Trocar o nome do fim nao afrouxa nada.
    assert titulos[-1] == "Não atendido"
    assert titulos != sorted(titulos)
    ids = [c["situacao_id"] for c in do_erp]
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
    ident = solicitar(formulario_de_operacao, os_id=99902, situacao_id=16488)
    q = paineis.quadro("operacao")
    coluna = next(c for c in q["colunas"] if c["situacao_id"] == 16488)
    assert ident in [c["id"] for c in coluna["cards"]]
    # 11/11: o cenario deixou de ser a 15746, que saiu da Operacao.
    assert coluna["titulo"] == "Entrega de materiais prontos"


def teste_o_card_leva_a_os_e_a_situacao_crua(formulario_de_operacao):
    """A solicitação E a OS lado a lado, como ele pediu -- e a situação à vista.

    ⚠️ Com uma situação DAS 17: até 28/10 este teste usava `situacao_id = 0`,
    que ia para a coluna "Sem situação". Ela não existe mais, e com zero o card
    não teria coluna nenhuma.
    """
    ident = solicitar(formulario_de_operacao, os_id=99903, numero_ordem="17042",
                      situacao_id=16488)
    q = paineis.quadro("operacao")
    card = next(c for coluna in q["colunas"] for c in coluna["cards"]
                if c["id"] == ident)
    assert card["numero_ordem"] == "17042"
    assert card["situacao_id"] == 16488


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
def teste_mover_existe_e_a_frase_antiga_nao_voltou():
    """🚨 A TERCEIRA TRAVA MINHA A GUARDAR A VERDADE ANTIGA no mesmo dia, e as
    três no mesmo recurso: uma exigia a palavra "Harmonit" numa frase errada,
    outra exigia `pode_mover` falso na rota, e esta aqui.

    O que mudou: mover **passou a existir** (Bloco D, 29/10 — *"O card pode ser
    por arrastar"*).

    ⚠️ O que NÃO mudou e continua travado: a FRASE que explicava a ausência do
    gesto saiu da tela a pedido dele (*"os comentários tbm devem sumir dali"*) e
    **não voltou** — o quadro não devolve `porque_nao_move`.
    """
    q = paineis.quadro("operacao")
    assert q["pode_mover"] is True
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
    # 🔵 05/11: entraram as DUAS abas do Pos-venda, e a ordem e a dele.
    # 🚨 UMA ENTRADA POR ABA porque a permissao e por aba -- *"a Karla tera
    # permissao para ver o 'Financeiro' e todas as abas. A Erika, apenas a
    # aba 3 do financeiro"*. `permissao` e campo da entrada, entao duas abas
    # com permissoes diferentes nao cabem numa so.
    # 🔵 06/11: o Financeiro (`PNL_1.4`, 10 colunas) e o Contratual
    # (`PNL_1.5`, 6) entraram, e com eles os QUATRO paineis declarados em
    # `paineis.PAINEIS` desde 22/10 passaram a ter tela. ⚠️ `COM_TELA` segue
    # sendo so `operacao`, e e certo: ele governa o `quadro()`, que fala com o
    # Harmonit -- os tres novos passam pelo `quadro_da_aba`, que nao fala.
    # 🔵 18/11: a `PNL_1.6`, segunda aba do Financeiro -- *"Serviço dos
    # técnicos"*, as cinco colunas do pagamento de técnico. 🚨 Ela tem TELA
    # PRÓPRIA e não a `PainelAba`: as cinco colunas não são etapas nossas
    # nem situações do ERP, e sim estados do artefato de pagamento, que
    # vive no FPSL.
    # 🔵 27/11: a `PNL_1.7`, Compras. 🚨 SEM `aba_de` -- ele escolheu item
    # proprio no menu, porque Compras nao e desdobramento de painel nenhum.
    assert dentro == ["PNL_1.1", "PNL_1.2", "PNL_1.3", "PNL_1.4",
                      "PNL_1.5", "PNL_1.6", "PNL_1.7"]
    # ⚠️ E a nova nasce SÓ OWNER como as outras, e aqui pesa mais: esta
    # tela move dinheiro e gera o arquivo que vai ao Procfy.
    assert telas.por_codigo("PNL_1.6")["permissao"] == "owner"
    # ⚠️ E AS DUAS NASCEM SO DO OWNER: *"todas hoje nascem somente para o
    # owner"*. Conceder e gesto dele.
    for codigo in ("PNL_1.2", "PNL_1.3"):
        assert telas.por_codigo(codigo)["permissao"] == "owner"

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


# ============================================================================
# ÁREA E — O TERMO NO CARD E A BUSCA POR TERMO (05/11)
# ============================================================================
# 🔵 *"termo no card e busca"*.
#
# 🚨 O TERMO NÃO É CAMPO DA OS NO HARMONIT. Ele vive dentro do texto da
# `descricao`, e a ponte o extrai e o guarda no cache
# (`fpsl_weso/termo_da_os.py`, com a medição que desenhou a extração: 200 OS
# lidas ao vivo em 05/11, 173 com termo e 0 ambíguas). Daqui para cima ele é
# só mais um campo que a ponte devolve.
#
# ⚠️ OS SEM TERMO É O CASO NORMAL EM 1 DE CADA 7 — venda, cartão RFID e
# manutenção não nascem de termo. Nada na tela escreve "sem termo".
def _o_card(quadro: dict, numero):
    """O card de uma OS, de qualquer coluna. ⚠️ Estoura se não existir — card
    que desapareceu do quadro é o defeito, não um `None` a comparar."""
    return next(c for col in quadro["colunas"] for c in col["cards"]
                if c["numero_ordem"] == numero)


class TestOTermoNoCard:

    def teste_o_termo_da_ponte_chega_no_card(self, ponte_de_os):
        ponte_de_os(_duble_de_os(termo="8937"))
        q = paineis.quadro("operacao")
        card = _o_card(q, 17099)
        assert card["termo"] == "8937"

    def teste_os_sem_termo_tem_card_com_termo_nulo(self, ponte_de_os):
        """⚠️ O card EXISTE e entra na coluna: a OS de venda é trabalho da
        operação como qualquer outra. O que falta é a referência do papel."""
        ponte_de_os(_duble_de_os())
        card = _o_card(paineis.quadro("operacao"), 17099)
        assert card["termo"] is None

    def teste_o_card_de_solicitacao_sem_os_na_ponte_tem_termo_nulo(
            self, formulario_de_operacao):
        """🚨 NULO DE PROPÓSITO, como os vizinhos `tipo_nome` e `placas`: o
        termo mora na OS, e esta OS não veio na lista da ponte. Preencher com
        o que o nosso banco "acha" seria inventar estado do ERP."""
        # ⚠️ Com uma situação DAS 17, senão o card não tem coluna nenhuma.
        ident = solicitar(formulario_de_operacao, os_id=927001,
                          numero_ordem="17901", situacao_id=16488)
        q = paineis.quadro("operacao")
        card = next(c for col in q["colunas"] for c in col["cards"]
                    if c["id"] == ident)
        assert card["origem"] == "formulario"
        assert card["termo"] is None


class TestABuscaPorTermo:

    def teste_a_busca_acha_pelo_termo_e_diz_que_casou_por_termo(self,
                                                               ponte_de_os):
        """🚨 O `casou_por` pesa mais aqui que em qualquer outro campo: termo e
        número de OS são os dois números de 4-5 dígitos do card, e sem dizer
        qual casou quem procura `8937` não sabe se achou a OS 8937 ou as 6 OS
        do termo 8937."""
        ponte_de_os(_duble_de_os(termo="8937"))
        q = paineis.quadro("operacao", busca="8937")
        assert q["total"] == 1
        assert q["filtro_casou_por"] == ["termo"]

    def teste_as_varias_os_do_mesmo_termo_vem_juntas(self, ponte_de_os):
        """🔵 É PARA ISTO QUE A BUSCA POR TERMO SERVE: um termo gera a OS
        financeira e uma OS por placa — 6 OS do termo 8937 na medição de
        05/11. Procurar o termo tem de trazer o conjunto, não uma delas."""
        ponte_de_os(
            _duble_de_os(numero_os=17082, os_id=1, termo="8937"),
            _duble_de_os(numero_os=17081, os_id=2, termo="8937"),
            _duble_de_os(numero_os=17076, os_id=3, termo="8940"),
        )
        q = paineis.quadro("operacao", busca="8937")
        assert {c["numero_ordem"] for col in q["colunas"]
                for c in col["cards"]} == {17082, 17081}

    def teste_card_sem_termo_nao_casa_por_termo(self, ponte_de_os):
        """⚠️ Nulo não é "casa com tudo" — e é 1 de cada 7 cards."""
        ponte_de_os(_duble_de_os(termo=None))
        assert paineis.quadro("operacao", busca="8937")["total"] == 0

    def teste_a_busca_pelo_numero_da_os_continua_dizendo_OS(self, ponte_de_os):
        """🚨 NÃO REGRESSÃO: o campo novo não pode roubar o rótulo do antigo.
        Procurar o número da OS tem de continuar dizendo *casou por OS*."""
        ponte_de_os(_duble_de_os(numero_os=17099, termo="8937"))
        q = paineis.quadro("operacao", busca="17099")
        assert q["filtro_casou_por"] == ["OS"]

    def teste_quando_casa_nos_dois_os_dois_sao_ditos(self, ponte_de_os):
        """⚠️ O caso que existe de verdade: a OS 8937 e o termo 8937 são
        números iguais em papéis diferentes. A tela diz *"casou por OS,
        termo"* em vez de escolher um."""
        ponte_de_os(_duble_de_os(numero_os=8937, termo="8937"))
        q = paineis.quadro("operacao", busca="8937")
        assert q["filtro_casou_por"] == ["OS", "termo"]


# ============================================================================
# O FILTRO "SÓ AS ABERTAS" E O CARD DE CHAMADO
# ============================================================================
def teste_o_filtro_de_abertas_alcanca_o_card_de_CHAMADO():
    """🔵 12/11, dele, depois de ver dois concluídos no topo da coluna
    Chamados: *"por estarem inativos, o filtro na tela não deveria exibi-los,
    pois só exibe abertos"*.

    🚨 AS TRAVAS QUE EXISTIAM PROVAVAM OUTRA COISA: que o `so_abertas`
    atravessa até a ponte. A ponte filtra as OS do ERP — e o card de chamado
    vem do NOSSO banco, por outro caminho, onde ninguém olhava o desfecho.
    📏 Medido antes do conserto: ligado ou desligado, a coluna devolvia os
    mesmos 5 cards, 2 deles concluídos.

    ⚠️ FILTRA, NÃO APAGA: com o interruptor desligado o card volta — e no
    fim da fila, pela régua dele de 11/11.
    """
    aba = pipeline.aba_por_codigo("PNL_1.1")
    etapa = [e for e in pipeline.etapas(aba["id"])
             if e["titulo"] == "Chamados"][0]
    velho = pipeline.criar(aba["id"], etapa["id"], atendente_id=None)
    pipeline.finalizar(velho["id"], "resolvido", atendente_id=None)
    novo = pipeline.criar(aba["id"], etapa["id"], atendente_id=None)
    try:
        q = paineis.quadro("operacao", so_abertas=True)
        col = q["colunas"][0]
        ids = [c.get("id") for c in col["cards"]]
        assert novo["id"] in ids, "o card ABERTO sumiu junto com o filtro"
        assert velho["id"] not in ids, (
            "o concluído continua na coluna com o filtro de abertas ligado")

        q = paineis.quadro("operacao", so_abertas=False)
        col = q["colunas"][0]
        ids = [c.get("id") for c in col["cards"]]
        assert velho["id"] in ids, "o concluído sumiu de vez, e devia só sair da fila"
        assert ids.index(novo["id"]) < ids.index(velho["id"]), (
            "o concluído não foi para o fim da fila")
    finally:
        banco.executar("DELETE FROM pipeline_card WHERE id IN (%s, %s)",
                       (velho["id"], novo["id"]))


class TestAOrigemDoCardDeEtapaNossa:
    """🚨 A pergunta dele em 18/11: *"Então pq os cards informam que não vem de
    OS no painel?"* — e o campo `origem` respondia "chamado" para card de OS.

    📏 Os 8 cards do Financeiro naquele dia eram TODOS OS (17120, 17119, 17122,
    17127, 17125, 17129, 17134, 17136) e nenhum veio de formulário: a
    `formulario_solicitacao` não tinha uma linha dos 4 formulários que apontam
    a etapa 875. Quem os trouxe foi `recebe_situacao = 15746`.

    ⚠️ E a tela usava esse `origem` para pintar a borda cujo comentário no CSS
    dizia, com estas palavras, *"ele não é uma OS"*.

    🚨 **O QUE NÃO MUDA, e três destes testes travam:** `numero_ordem` e
    `situacao_id` continuam NULOS. São eles que a tela lê para manter o card sem
    arrasto e sem `<select>` de mover — enchê-los ligaria o arrasto ao ERP numa
    aba cujo mover grava só no nosso banco. **O que muda é o rótulo, não a
    guarda.**
    """

    def _card(self, **extra):
        linha = {"id": 2645, "etapa_id": 875, "solicitacao_id": None,
                 "cliente_id": 84792, "numero_os": 17134,
                 "criado_em": None, "desfecho": None, "desfecho_em": None,
                 "desfecho_por_nome": None, "valores": None,
                 "solicitada_em": None, "formulario": None, "slug": None,
                 "observacoes": 2, "etapa_desde": None}
        linha.update(extra)
        return paineis._card_do_chamado(linha, {}, None)

    def test_card_COM_OS_nao_se_chama_chamado(self):
        assert self._card()["origem"] == "erp_em_etapa_nossa"

    def test_card_SEM_OS_continua_chamado(self):
        """⚠️ Guarda-de-regressão: consertar um não pode apagar o outro."""
        assert self._card(numero_os=None)["origem"] == "chamado"

    def test_os_DOIS_NULOS_da_guarda_ficam(self):
        """🚨 O contrato que mantém o card sem arrasto para o ERP."""
        for card in (self._card(), self._card(numero_os=None)):
            assert card["numero_ordem"] is None
            assert card["situacao_id"] is None
            assert card["os_id"] is None

    def test_o_numero_da_OS_continua_em_numero_os(self):
        """⚠️ É daí que o componente do card tira a OS, justamente porque
        `numero_ordem` é nulo de propósito."""
        assert self._card()["numero_os"] == 17134

    def test_os_campos_de_12_11_continuam_vindo(self):
        """🔵 12/11, dele: *"nos cards do financeiro, faltam informações sobre o
        tipo do termo, número do termo"* / *"igual da OP"*.

        🚨 Eles JÁ vinham e a tela os jogava fora — o conserto de 18/11 foi na
        tela. Este teste existe para o servidor não voltar a nulá-los."""
        da_os = {"tipo_nome": "Instalação", "status_str": "Iniciada",
                 "termo": "8955", "prioridade": 382,
                 "placas": [{"placa": "UVO 8E01"}],
                 "tecnicos": [{"nome": "Franck"}],
                 "visto_em": "2026-11-18T12:49:21+00:00",
                 "finalizada": False}
        linha = {"id": 2645, "etapa_id": 875, "solicitacao_id": None,
                 "cliente_id": 84792, "numero_os": 17134, "criado_em": None,
                 "desfecho": None, "desfecho_em": None,
                 "desfecho_por_nome": None, "valores": None,
                 "solicitada_em": None, "formulario": None, "slug": None,
                 "observacoes": 2, "etapa_desde": None}
        card = paineis._card_do_chamado(linha, {}, da_os)
        assert card["termo"] == "8955"
        assert card["tipo_nome"] == "Instalação"
        assert card["status_str"] == "Iniciada"
        assert card["placas"] == [{"placa": "UVO 8E01"}]
        assert card["visto_em"] == "2026-11-18T12:49:21+00:00"
        # ...e a origem continua dizendo que é OS.
        assert card["origem"] == "erp_em_etapa_nossa"
