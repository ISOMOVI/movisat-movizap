# -*- coding: utf-8 -*-
r"""O TERMO POSTO A MAO NO CARD DO CONTRATUAL — 25/11.

🔵 Ele: *"os cards fechados na aba contratual devem ter o numero do termo antes
do nome do cliente: TERMO: '12345 - PASTELARIA VELASCO'"* e, sobre a origem do
numero, *"o operador coloca a mao no card, pois so depois de assinado que ele
sera gerado oficialmente"*.

📏 MEDIDO antes de escrever: o quadro do Contratual tem **6 cards e nenhum com
termo**, porque os seis sao **solicitacoes sem OS**, e o termo nao e campo da OS
-- e extraido de dentro dela. As respostas dos formularios foram abertas: CNPJ,
placas, endereco, responsavel, e **nenhum campo de termo**.

🚨 **POR HTTP, NAO POR FUNCAO** (`feedback_rota_nova_pede_teste_http`): rota
nova pede pedido de verdade. 401 sem login, 403 sem a aba do card, e card que
nao existe recusado.

🚨 **E O QUE ESTAS TRAVAS PRENDEM DE MAIS IMPORTANTE:** o termo da OS **ganha**
do posto a mao, e a tela diz **qual e a origem**. Tela que mostra numero
digitado com cara de oficial e tela mentindo (`M12`).

🚨 O DUBLE FICA NA BORDA: o banco. A regra -- aparar, limitar, limpar, a
precedencia da OS, o `termo_a_mao` -- roda de verdade.

⚠️ **E O QUE ESTE ARQUIVO NAO PODE PROVAR, dito e nao vendido como verde:** com
o `banco.executar` dublado, o **Postgres nunca ve a consulta**. Na primeira
escrita de verdade ela falhou com `could not determine data type of parameter
$3` -- faltava `::text` no parametro dentro do `CASE WHEN`. O SQL se prova
escrevendo (`M17` linha 5), e foi assim que o defeito apareceu.

Roda:  venv/bin/python -m pytest tests/teste_termo_posto_a_mao.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, main, paineis, pipeline  # noqa: E402

ROTA = "/api/paineis/operacao/chamado/{}/termo"
CARD = 4360          # um dos 6 cards do Contratual, medido
ABA_CONTRATUAL = 302


@pytest.fixture
def cliente():
    return TestClient(main.app)


@pytest.fixture
def logado(monkeypatch):
    """Sessão de quem tem a aba do Contratual."""
    usuario = {"id": 121, "nome": "Iago", "owner": True}
    monkeypatch.setitem(main.app.dependency_overrides, auth.get_usuario,
                        lambda: usuario)
    yield usuario
    main.app.dependency_overrides.pop(auth.get_usuario, None)


@pytest.fixture
def banco_falso(monkeypatch):
    """A borda: o card e as escritas."""
    estado = {"card": {"id": CARD, "aba_id": ABA_CONTRATUAL,
                       "codigo_tela": "PNL_1.5"},
              "gravado": [], "termo": None}

    def um(sql, params=()):
        s = " ".join(sql.split())
        if "FROM pipeline_card" in s or "from pipeline_card" in s:
            return dict(estado["card"]) if estado["card"] else None
        return None

    def executar(sql, params=()):
        estado["gravado"].append((" ".join(sql.split()), params))
        return 1

    monkeypatch.setattr(pipeline.banco, "um", um)
    monkeypatch.setattr(pipeline.banco, "executar", executar)
    monkeypatch.setattr(pipeline, "aba_do_card",
                        lambda cid: {"codigo_tela": "PNL_1.5"}
                        if estado["card"] else None)
    return estado


def _card_cru(termo=None):
    """Um card como a `cards_da_aba` o devolve.

    ⚠️ As chaves obrigatorias vem da leitura do `_card_do_chamado`
    (`c["id"]`, `etapa_id`, `criado_em`, `numero_ordem`, `situacao_id`,
    `solicitacao_id`): fixture curta demais reprovava por falta de chave, nao
    pela regra -- e fixture irreal nao se conserta afrouxando o codigo.
    """
    return {"id": 1, "etapa_id": 888, "criado_em": None,
            "numero_ordem": None, "situacao_id": None,
            "solicitacao_id": None, "valores": {}, "termo": termo}


# ---------------------------------------------------------------- a rota -----
def teste_sem_login_e_401(cliente):
    r = cliente.post(ROTA.format(CARD), json={"termo": "12345"})
    assert r.status_code == 401, r.text


def teste_sem_a_aba_do_card_e_403(cliente, logado, monkeypatch, banco_falso):
    """🚨 A permissão é a da aba do PRÓPRIO card, como no `finalizar` -- não a
    de uma aba qualquer que a pessoa tenha."""
    monkeypatch.setattr(main, "_exigir_aba",
                        lambda codigo, usuario: (_ for _ in ()).throw(
                            main.HTTPException(status_code=403,
                                               detail="sem a aba")))
    r = cliente.post(ROTA.format(CARD), json={"termo": "12345"})
    assert r.status_code == 403, r.text


def teste_grava_e_devolve_o_numero(cliente, logado, banco_falso, monkeypatch):
    monkeypatch.setattr(main, "_exigir_aba", lambda codigo, usuario: None)
    r = cliente.post(ROTA.format(CARD), json={"termo": " 12345 "})
    assert r.status_code == 200, r.text
    assert r.json()["termo"] == "12345", "o número sai aparado"
    sql, params = banco_falso["gravado"][-1]
    assert "UPDATE pipeline_card" in sql
    assert "termo" in sql and "termo_por" in sql and "termo_em" in sql
    assert "12345" in params and 121 in params


def teste_card_que_nao_existe_e_recusado(cliente, logado, banco_falso,
                                         monkeypatch):
    monkeypatch.setattr(main, "_exigir_aba", lambda codigo, usuario: None)
    banco_falso["card"] = None
    r = cliente.post(ROTA.format(999999), json={"termo": "12345"})
    assert r.status_code in (400, 404), r.text
    assert banco_falso["gravado"] == [], "não escreveu nada"


# ------------------------------------------------------------- a regra -------
def teste_vazio_LIMPA_o_campo(banco_falso):
    """⚠️ Operador que digitou errado precisa poder apagar. E o CHECK do banco
    exige que `termo` e `termo_em` sejam nulos juntos."""
    for vazio in ("", "   ", None):
        banco_falso["gravado"].clear()
        saida = pipeline.gravar_termo(CARD, vazio, atendente_id=121)
        assert saida["termo"] is None, repr(vazio)
        sql, params = banco_falso["gravado"][-1]
        assert None in params, "grava NULO, não cadeia vazia"


def teste_numero_longo_demais_e_recusado(banco_falso):
    """⚠️ Teto porque a coluna é `text` e a tela tem largura: um parágrafo no
    lugar do número empurraria o nome do cliente para fora do card."""
    with pytest.raises(paineis.DadoInvalido):
        pipeline.gravar_termo(CARD, "9" * 40, atendente_id=121)
    assert banco_falso["gravado"] == []


def teste_NAO_grava_passagem_de_etapa(banco_falso):
    """🚨 MEDIDO: o `etapa_desde` do card sai de `max(pipeline_passagem.em)`.
    Uma passagem a cada digitação zeraria o contador de "parado nesta etapa
    desde", que é o que mostra card esquecido."""
    pipeline.gravar_termo(CARD, "12345", atendente_id=121)
    for sql, _p in banco_falso["gravado"]:
        assert "pipeline_passagem" not in sql, sql


# ------------------------------------------- a precedencia, e a verdade ------
def teste_o_termo_da_OS_GANHA_do_posto_a_mao():
    """🚨 Quando a OS existe, o número dela é o oficial."""
    card = _card_cru("99999")
    saida = paineis._card_do_chamado(card, {}, {"termo": "8953"})
    assert saida["termo"] == "8953"
    assert saida["termo_a_mao"] is False


def teste_sem_termo_na_OS_vale_o_posto_a_mao():
    card = _card_cru("12345")
    saida = paineis._card_do_chamado(card, {}, {"termo": None})
    assert saida["termo"] == "12345"
    assert saida["termo_a_mao"] is True, "a tela precisa saber a origem"


def teste_sem_termo_nenhum_continua_nulo():
    """⚠️ Nulo, e não cadeia vazia: a tela sabe dizer "não tem"."""
    card = _card_cru(None)
    saida = paineis._card_do_chamado(card, {}, None)
    assert saida["termo"] is None
    assert saida["termo_a_mao"] is False


def teste_a_consulta_da_aba_TRAZ_o_termo_do_card():
    """🚨 Campo novo não entra sozinho (`feedback_campo_novo_nao_entra_sozinho`):
    quem devolve -> quem grava -> quem lê. Sem isto na consulta, a coluna
    existiria no banco e a tela nunca a veria."""
    import inspect
    fonte = inspect.getsource(pipeline.cards_da_aba)
    assert "c.termo" in fonte
    assert "termo_em" in fonte
    assert "termo_por" in fonte, "o NOME de quem pôs também é lido"
