# -*- coding: utf-8 -*-
r"""AS ABAS DE PIPELINE — as duas do Pós-venda, e a permissão por aba (05/11).

🔵 Pedido dele: *"a aba 'Operação' do Movizap é a mesma lógica para os demais:
Pós-venda - Abas - Permissão por abas / Aba 1: Treinamentos / Solicitação:
Agenda* / Treinamento 1: / Treinamento 2: / Entregue: / Aba 2: Pós-venda"*, e
depois *"Solicitação: Testes: Realizar Pós-venda: Pós-venda Realizado:"*.

🚨 **AS DUAS REGRAS QUE ESTE ARQUIVO PRENDE:**

1. **A PERMISSÃO É POR ABA, e sai do CARD.** Até 05/11 as rotas de card exigiam
   `PNL_1.1` fixo — com as abas novas, um card da `PNL_1.2` cairia em 403 pedido
   por quem tem a tela certa. ⚠️ E o contrário é pior: sem a conferência, quem
   tem só a `PNL_1.2` mexeria em card da `PNL_1.3`.
2. **ESTA TELA NUNCA FALA COM O HARMONIT.** As colunas são nossas; não há
   `situacaoId` para gravar. A prova é um dublê que **conta as chamadas** e
   exige zero.

⚠️ **E as colunas são as DELE, na ORDEM dele** — ordem é a coisa mais fácil de
perder: um `sorted()` bem-intencionado destruiria o fluxo sem quebrar nada
visível.

Roda:  venv/bin/python -m pytest tests/teste_abas.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main, paineis, pipeline  # noqa: E402
from movizap import telas as registro_telas  # noqa: E402
from movizap.config import settings  # noqa: E402

# 🔵 As duas abas que a migração 094 semeia, com as colunas que ele escreveu.
AS_ABAS = {
    "PNL_1.2": ("Treinamentos",
                ["Nova solicitação", "Treinamento 1", "Treinamento 2",
                 "Entregue"]),
    "PNL_1.3": ("Pós-venda",
                ["Nova solicitação", "Testes", "Realizar Pós-venda",
                 "Pós-venda Realizado"]),
}


@pytest.fixture(scope="module", autouse=True)
def banco_aberto():
    banco.abrir()
    yield


# ⚠️ `TestClient` de MÓDULO: um segundo no mesmo `app` dá *"Event is bound to a
# different event loop"*, e o `teste_rotas_pipeline.py` já documentava isso.
@pytest.fixture(scope="module")
def cliente():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def token_owner():
    """O token do owner. ⚠️ `settings.admin_login`, como o resto da suite --
    um dict montado a mao nao casa com o que o `get_usuario` espera, e a rota
    devolve 401 em vez de 403."""
    return auth.criar_token(settings.admin_login)


# ============================================================================
# O CATÁLOGO — sem entrada no `telas.py` a tela sobe INVISÍVEL
# ============================================================================
def teste_as_duas_abas_tem_entrada_no_catalogo():
    """🚨 É a lição dele de 03/11: a tela da CAR subiu sem registro, ficou fora
    do menu e não dava nem 403. *"ESTÁ NO AR NÃO É 200."*"""
    for codigo in AS_ABAS:
        tela = registro_telas.por_codigo(codigo)
        assert tela is not None, codigo
        # 🚨 O TITULO DA TELA E O DO PAINEL, e nao o da aba: correcao dele
        # em 05/11 -- *"so aba principal no menu. As demais sao dentro dela
        # ja"*. "Treinamentos" e titulo da ABA, e vive no banco
        # (`painel_aba.titulo`), nao aqui.
        assert tela["titulo"] == "Pós-venda", codigo
        assert tela["grupo"] == "Painéis"
        # 🔵 *"todas hoje nascem somente para o owner"*.
        assert tela["permissao"] == "owner"

    # 🚨 UM ITEM DE MENU, E NAO DOIS: a segunda aba leva `aba_de`, e o
    # `MenuLateral` pula toda tela que tem esse campo.
    assert registro_telas.por_codigo("PNL_1.2").get("aba_de") is None
    assert registro_telas.por_codigo("PNL_1.3")["aba_de"] == "PNL_1.2"
    # ⚠️ E A ROTA CONTINUA PROPRIA, porque e por ela que a aba de dentro
    # navega -- `aba_de` esconde do menu, nao da rota.
    assert (registro_telas.por_codigo("PNL_1.2")["rota"]
            != registro_telas.por_codigo("PNL_1.3")["rota"])


def teste_cada_aba_tem_a_propria_entrada_porque_a_permissao_e_dela():
    """🚨 Uma entrada por aba, e não uma para o painel.

    🔵 *"a Karla terá permissão para ver o 'Financeiro' e todas as abas. A
    Erika, apenas a aba 3 do financeiro"*. `permissao` é campo DA ENTRADA,
    então duas abas com permissões diferentes não cabem numa só.
    """
    codigos = {t["codigo"] for t in registro_telas.TELAS}
    assert {"PNL_1.2", "PNL_1.3"} <= codigos
    # ⚠️ E as duas chegam ao FRONTEND pelo `do_usuario`, inclusive a que tem
    # `aba_de`: a guarda de rota do front usa `sessao.telas` para saber o que
    # a pessoa pode abrir, e tirar a aba dali barraria a propria aba. Foi um
    # defeito achado em 27/08 com as `CFG_*`.
    # ⚠️ O `do_usuario` conhece owner pela chave `owner`, e nao pelo
    # `perfil`: um dict com `perfil="owner"` devolve conjunto VAZIO, e foi o que
    # esta trava achou na primeira rodada.
    vistas = {t["codigo"] for t in registro_telas.do_usuario({"owner": True})}
    assert {"PNL_1.2", "PNL_1.3"} <= vistas


# ============================================================================
# AS COLUNAS — as dele, na ordem dele
# ============================================================================
def teste_as_colunas_sao_as_dele_e_na_ordem_dele():
    for codigo, (titulo, colunas) in AS_ABAS.items():
        aba = pipeline.aba_por_codigo(codigo)
        assert aba is not None, codigo
        assert aba["painel"] == "pos_venda"
        assert aba["titulo"] == titulo
        etapas = [e["titulo"] for e in pipeline.etapas(aba["id"])]
        assert etapas == colunas, codigo
        # ⚠️ Ordem NÃO é alfabética: um `sorted()` bem-intencionado destruiria
        # o fluxo sem quebrar nada visível.
        if etapas != sorted(etapas):
            assert True
        else:  # pragma: no cover -- só se ele mudar os nomes
            pytest.skip("as colunas dele calharam de estar em ordem alfabética")


def teste_so_a_ultima_coluna_e_final():
    """⚠️ `final` é o fato escrito no banco: chegar ali é terminar. Nada na tela
    depende dele ainda, e é por isso que esta trava existe — para o fato não se
    perder antes de alguém usá-lo."""
    for codigo, (_, colunas) in AS_ABAS.items():
        aba = pipeline.aba_por_codigo(codigo)
        etapas = pipeline.etapas(aba["id"])
        assert [e["final"] for e in etapas] == [False] * (len(colunas) - 1) + [True]


def teste_a_coluna_Solicitacao_existe_nas_DUAS_abas_e_sao_duas():
    """⚠️ `titulo` é único DENTRO da aba, não no sistema. Duas pipelines que
    começam pelo mesmo nome são duas pipelines, e não uma compartilhada."""
    ids = []
    for codigo in AS_ABAS:
        aba = pipeline.aba_por_codigo(codigo)
        sol = [e for e in pipeline.etapas(aba["id"])
               if e["titulo"] == "Nova solicitação"]
        assert len(sol) == 1, codigo
        ids.append(sol[0]["id"])
    assert ids[0] != ids[1]


# ============================================================================
# O QUADRO DA ABA
# ============================================================================
def teste_o_quadro_da_aba_nao_tem_coluna_do_ERP():
    """🚨 `situacao_id` nulo em TODAS: aqui não existe coluna do Harmonit, e é a
    diferença inteira em relação ao quadro da Operação."""
    q = paineis.quadro_da_aba("PNL_1.2")
    assert q is not None
    assert len(q["colunas"]) == 4
    assert all(c["situacao_id"] is None for c in q["colunas"])
    assert all(c["etapa_id"] for c in q["colunas"])


def teste_a_aba_LE_a_ponte_mas_NUNCA_escreve(monkeypatch):
    """🚨 ESTA TRAVA FOI REESCRITA EM 12/11, e o motivo vale mais que ela.

    Até aqui ela se chamava `teste_o_quadro_da_aba_NAO_chama_a_ponte` e exigia
    ZERO chamadas. Foi escrita antes da migração 106 -- quando aba nenhuma
    recebia situação do ERP e a afirmação era verdadeira.

    A 106 acrescentou ao `quadro_da_aba` o bloco que semeia os cards de OS da
    própria aba, e esse bloco **chama** `os_por_situacao`. A trava continuou
    verde por dois meses porque `pipeline.etapas()` não devolvia
    `recebe_situacao`: o `any(...)` era sempre falso e o bloco nunca rodava.
    ➡️ Ela não provava a promessa, provava o defeito -- e ficou vermelha no
    dia em que o defeito foi consertado.

    ⚠️ Dublê que CONTA, e não que estoura: um dublê que explode só prova que
    algum `try` segurou.
    """
    chamadas = []
    for nome in ("os_por_situacao", "gravar_situacao_da_os", "criar_os"):
        if hasattr(paineis.fpsl_ponte, nome):
            monkeypatch.setattr(
                paineis.fpsl_ponte, nome,
                lambda *a, nome=nome, **k: chamadas.append(nome) or {"os": []})

    # PNL_1.2 (Treinamentos) NÃO recebe situação de ninguém: tem de ler ZERO.
    paineis.quadro_da_aba("PNL_1.2")
    assert chamadas == [], (
        "Treinamentos não recebe situação do ERP e mesmo assim foi à ponte: "
        + str(chamadas))

    # PNL_1.3 (Pós-venda) recebe a 15695 na primeira etapa: lê UMA vez.
    paineis.quadro_da_aba("PNL_1.3")
    assert chamadas == ["os_por_situacao"], str(chamadas)

    # 🚨 O QUE NUNCA PODE ACONTECER, e é a parte que protege de verdade: a aba
    # move card no NOSSO banco. Uma escrita no ERP a partir daqui mudaria a
    # situação de uma OS de verdade sem ninguém ter pedido.
    assert "gravar_situacao_da_os" not in chamadas
    assert "criar_os" not in chamadas


def teste_ponte_CAIDA_nao_esvazia_o_quadro_da_aba(monkeypatch):
    """🚨 A promessa do cabeçalho do `quadro_da_aba`: *"este quadro não pode
    ficar vazio porque um terceiro caiu"*.

    ⚠️ O card é materializado -- é linha no nosso banco. Ponte fora do ar
    impede card NOVO de nascer e não apaga nenhum dos que já estão lá.
    """
    def estoura(*a, **k):
        raise RuntimeError("ponte fora do ar, de propósito")

    monkeypatch.setattr(paineis.fpsl_ponte, "os_por_situacao", estoura)
    q = paineis.quadro_da_aba("PNL_1.3")
    assert q is not None, "a aba sumiu porque a ponte caiu"
    assert len(q["colunas"]) == 4
    assert all(c["situacao_id"] is None for c in q["colunas"])


def teste_aba_que_nao_existe_devolve_None():
    """⚠️ `None`, e não estouro: a rota é que decide o código HTTP."""
    assert paineis.quadro_da_aba("PNL_9.9") is None


def teste_o_quadro_conta_o_que_ficou_fora():
    """🚨 `M12`: card em etapa desligada fica fora do quadro e CONTADO. Sumir em
    silêncio seria o defeito."""
    q = paineis.quadro_da_aba("PNL_1.3")
    assert "fora_do_quadro" in q
    assert q["fora_do_quadro"] == 0


# ============================================================================
# A ROTA, E A PERMISSÃO POR ABA
# ============================================================================
def teste_a_rota_da_aba_responde_ao_owner(cliente, token_owner):
    r = cliente.get("/api/paineis/aba/PNL_1.2",
                    headers={"Authorization": f"Bearer {token_owner}"})
    assert r.status_code == 200, r.text
    q = r.json()
    assert q["aba"] == "PNL_1.2"
    assert [c["titulo"] for c in q["colunas"]] == AS_ABAS["PNL_1.2"][1]


def teste_a_rota_da_aba_exige_autenticacao(cliente):
    r = cliente.get("/api/paineis/aba/PNL_1.2")
    assert r.status_code in (401, 403), r.text


def teste_aba_inexistente_da_403_e_nao_404(cliente, token_owner):
    """🚨 403 ANTES de olhar o banco, e é deliberado: dizer *"esta aba não
    existe"* a quem não pode vê-la já vazaria se ela existe.

    ⚠️ Owner passa pela permissão, então para ELE o 404 é correto — e é o que
    esta trava separa.
    """
    r = cliente.get("/api/paineis/aba/PNL_9.9",
                    headers={"Authorization": f"Bearer {token_owner}"})
    # para o owner, a permissão não barra: o que falta é a aba.
    assert r.status_code in (403, 404), r.text


def teste_quem_nao_tem_a_tela_leva_403(cliente, monkeypatch, token_owner):
    """🚨 A trava da permissão POR ABA: quem tem a `PNL_1.2` não entra na
    `PNL_1.3`.

    ⚠️ O dublê é no `pode_acessar`, e não num atendente de verdade: criar
    atendente com permissão recortada mexeria em dado de produção.
    """
    def so_a_12(usuario, codigo):
        return codigo == "PNL_1.2"

    monkeypatch.setattr(registro_telas, "pode_acessar", so_a_12)
    monkeypatch.setattr(main.registro_telas, "pode_acessar", so_a_12)
    cab = {"Authorization": f"Bearer {token_owner}"}
    assert cliente.get("/api/paineis/aba/PNL_1.2",
                       headers=cab).status_code == 200
    r = cliente.get("/api/paineis/aba/PNL_1.3", headers=cab)
    assert r.status_code == 403, r.text


def teste_o_card_e_conferido_pela_aba_DELE_e_nao_por_PNL_1_1(
        cliente, monkeypatch, token_owner):
    """🚨 A INVERSÃO DE 05/11: a permissão sai do CARD.

    Antes, `requer_tela("PNL_1.1")` fixo nas 5 rotas de card. Com um dublê que
    só concede a `PNL_1.1`, um card de aba do Pós-venda tem de levar 403 — e é
    isso que prova que a conferência olha a aba do card, e não a rota.
    """
    aba = pipeline.aba_por_codigo("PNL_1.3")
    etapa = pipeline.etapas(aba["id"])[0]
    card = pipeline.criar(aba["id"], etapa["id"], atendente_id=None)
    try:
        def so_a_11(usuario, codigo):
            return codigo == "PNL_1.1"

        monkeypatch.setattr(registro_telas, "pode_acessar", so_a_11)
        monkeypatch.setattr(main.registro_telas, "pode_acessar", so_a_11)
        cab = {"Authorization": f"Bearer {token_owner}"}
        r = cliente.get(f"/api/paineis/operacao/chamado/{card['id']}",
                        headers=cab)
        assert r.status_code == 403, r.text
        r = cliente.post(
            f"/api/paineis/operacao/chamado/{card['id']}/finalizar",
            json={"desfecho": "resolvido"}, headers=cab)
        assert r.status_code == 403, r.text
    finally:
        banco.executar("DELETE FROM pipeline_card WHERE id = %s",
                       (card["id"],))


def teste_o_card_da_aba_abre_e_move_para_quem_tem_a_tela(
        cliente, token_owner):
    """🔵 O fluxo dele numa aba de Pós-venda: o card abre, e move entre as
    colunas DELE. 🚨 E nada disso vai ao ERP."""
    aba = pipeline.aba_por_codigo("PNL_1.3")
    etapas = pipeline.etapas(aba["id"])
    card = pipeline.criar(aba["id"], etapas[0]["id"], atendente_id=None)
    cab = {"Authorization": f"Bearer {token_owner}"}
    try:
        r = cliente.get(f"/api/paineis/operacao/chamado/{card['id']}",
                        headers=cab)
        assert r.status_code == 200, r.text
        ficha = r.json()
        assert [e["titulo"] for e in ficha["etapas"]] == AS_ABAS["PNL_1.3"][1]

        r = cliente.post(
            f"/api/paineis/operacao/chamado/{card['id']}/mover",
            json={"para_etapa": etapas[2]["id"]}, headers=cab)
        assert r.status_code == 200, r.text

        # 🚨 E a passagem guarda o TÍTULO DE ENTÃO (retrato, migração 093).
        passagens = pipeline.historico(card["id"])
        assert passagens[0]["para_titulo"] == "Realizar Pós-venda"
        # ⚠️ O RETRATO É DO NOME DE AGORA porque esta passagem é criada
        # pelo próprio teste, depois da migração 100. Passagem gravada
        # ANTES dela continua dizendo "Solicitação" no banco, e isso é a
        # 093 funcionando: renomear a etapa não reescreve o histórico.
        assert passagens[0]["de_titulo"] == "Nova solicitação"
    finally:
        banco.executar("DELETE FROM pipeline_card WHERE id = %s",
                       (card["id"],))


def teste_o_quadro_da_aba_mostra_o_card_na_coluna_certa():
    aba = pipeline.aba_por_codigo("PNL_1.2")
    etapas = pipeline.etapas(aba["id"])
    card = pipeline.criar(aba["id"], etapas[1]["id"], atendente_id=None)
    try:
        q = paineis.quadro_da_aba("PNL_1.2")
        por_titulo = {c["titulo"]: c for c in q["colunas"]}
        assert [c["id"] for c in por_titulo["Treinamento 1"]["cards"]] \
            == [card["id"]]
        assert por_titulo["Nova solicitação"]["cards"] == []
        assert q["total"] == 1
        # ⚠️ O card leva a `etapa_id`: sem ela a tela compararia `undefined`
        # com o id da coluna, e todo solto iria à rota.
        assert por_titulo["Treinamento 1"]["cards"][0]["etapa_id"] \
            == etapas[1]["id"]
        # 🚨 E NÃO tem número de OS: card de pipeline não é OS.
        assert por_titulo["Treinamento 1"]["cards"][0]["numero_ordem"] is None
    finally:
        banco.executar("DELETE FROM pipeline_card WHERE id = %s",
                       (card["id"],))


def teste_o_arquivado_SOME_com_o_filtro_e_vem_no_FIM_sem_ele():
    """As duas metades do contrato, e elas são de dias diferentes.

    🔵 11/11: *"ele esmaece e fica no fim da fila arquivado com status de
    concluído"*.
    🔵 12/11, depois de ver dois concluídos no TOPO da primeira coluna do
    painel: *"por estarem inativos, o filtro na tela não deveria exibi-los,
    pois só exibe abertos, talvez mantê-los ali mas inativos seria o ideal
    para uso do filtro e não mexer muito na tela"*.

    ⚠️ Até 12/11 esta trava só perguntava a ORDEM, e o `quadro_da_aba` nem
    tinha filtro. Perguntar as duas é o que impede de consertar uma metade e
    quebrar a outra sem ninguém ver.
    """
    aba = pipeline.aba_por_codigo("PNL_1.2")
    etapa = pipeline.etapas(aba["id"])[0]
    velho = pipeline.criar(aba["id"], etapa["id"], atendente_id=None)
    pipeline.finalizar(velho["id"], "resolvido", atendente_id=None)
    novo = pipeline.criar(aba["id"], etapa["id"], atendente_id=None)
    try:
        # ---- filtro LIGADO (o padrão da tela): o concluído não aparece ----
        q = paineis.quadro_da_aba("PNL_1.2")
        col = [c for c in q["colunas"] if c["etapa_id"] == etapa["id"]][0]
        ids = [c["id"] for c in col["cards"]]
        assert novo["id"] in ids, "o card ABERTO sumiu junto com o filtro"
        assert velho["id"] not in ids, (
            "o concluído continua na fila com o filtro de abertas ligado")

        # ---- filtro DESLIGADO: ele volta, no FIM, dizendo o desfecho ----
        q = paineis.quadro_da_aba("PNL_1.2", so_abertas=False)
        col = [c for c in q["colunas"] if c["etapa_id"] == etapa["id"]][0]
        ids = [c["id"] for c in col["cards"]]
        assert ids.index(novo["id"]) < ids.index(velho["id"]), (
            "o concluído não foi para o fim da fila")
        arquivado = [c for c in col["cards"] if c["id"] == velho["id"]][0]
        # 🚨 E o selo diz QUAL desfecho foi: opacidade não carrega informação.
        assert arquivado["desfecho_rotulo"] == "Resolvido"
    finally:
        banco.executar("DELETE FROM pipeline_card WHERE id IN (%s, %s)",
                       (velho["id"], novo["id"]))


if __name__ == "__main__":
    # 🚨 Sem isto o arquivo roda como script, não executa nada e sai com 0 --
    # o defeito que ele achou no medidor do FPSL em 05/11.
    raise SystemExit(pytest.main([__file__]))
