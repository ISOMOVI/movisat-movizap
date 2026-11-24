# -*- coding: utf-8 -*-
r"""A ROTA DO QUADRO DA `PNL_1.6`, E A ORDEM QUE A FAZIA SUMIR — 19/11.

🚨 ESTE ARQUIVO GUARDA UM DEFEITO QUE ELE ACHOU OLHANDO A TELA: *"a tela não
aparece no movizap. a aba aparece mas o conteúdo não"*.

📏 Medido no log de produção, nos dois acessos dele:

    19/11 08:12:14  GET /paineis/servico-dos-tecnicos      -> 200
    19/11 08:12:14  GET /api/paineis/servico-dos-tecnicos  -> 400 "Painel desconhecido."

A causa não era a tela nem a permissão: era a ORDEM DE REGISTRO das rotas. O
curinga `@app.get("/api/paineis/{painel}")` estava declarado ~1.300 linhas
ACIMA da rota específica, e o FastAPI casa na ordem em que as rotas entram --
então `servico-dos-tecnicos` era lido como o NOME de um painel, e o
`paineis_mod.quadro` recusava com 400.

🚨 POR QUE NENHUMA SUÍTE PEGOU: as 9 provas por HTTP da rodada de 18/11 eram
todas do lado do FPSL (`/pagamento/...`). Deste lado havia quatro arquivos
citando a `PNL_1.6` -- e os quatro conferiam REGISTRO (catálogo, menu, roteador),
nunca um pedido de verdade. 🚨 `M9`/`feedback_rota_nova_pede_teste_http`: a
ordem das rotas é invisível na leitura do arquivo, e só um pedido HTTP a prova.

⚠️ NADA AQUI ESCREVE. O quadro do pagamento é um dublê -- a rota de verdade iria
ao FPSL, e teste que fala com serviço de fora não é trava, é sorteio.

Roda:  venv/bin/python -m pytest tests/teste_rota_servico_dos_tecnicos.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main  # noqa: E402
from movizap import telas as registro_telas  # noqa: E402
from movizap.config import settings  # noqa: E402

CODIGO = "PNL_1.6"
CAMINHO = "/api/paineis/servico-dos-tecnicos"
CURINGA = "/api/paineis/{painel}"

QUADRO_DUBLE = {
    "colunas": [
        {"chave": "movimentacao", "titulo": "Movimentação", "cards": []},
        {"chave": "validacao", "titulo": "Validação", "cards": []},
        {"chave": "procfy", "titulo": "Procfy", "cards": []},
        {"chave": "enviado", "titulo": "Pagamento enviado", "cards": []},
    ],
    "total": 0,
}


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
# A TRAVA PRINCIPAL — a ordem
# ============================================================================
def teste_a_rota_especifica_vem_ANTES_do_curinga():
    """🚨 A trava que não depende de rede nem de banco.

    Quem mover a `quadro_do_servico` para baixo do curinga de novo vê este
    teste vermelho com a razão escrita.
    """
    caminhos = [getattr(r, "path", None) for r in main.app.routes]
    assert CAMINHO in caminhos, "a rota do quadro sumiu do app"
    assert CURINGA in caminhos, "o curinga mudou de forma; reveja este teste"
    assert caminhos.index(CAMINHO) < caminhos.index(CURINGA), (
        "a rota específica voltou para baixo do curinga: "
        "GET /api/paineis/servico-dos-tecnicos vai cair em 400 de novo"
    )


def teste_o_quadro_responde_e_nao_cai_no_curinga(cliente, token_owner,
                                                 monkeypatch):
    """O pedido de verdade, que é o que faltava em 18/11."""
    monkeypatch.setattr(main.fpsl_ponte, "quadro_do_pagamento",
                        lambda: QUADRO_DUBLE)
    r = cliente.get(CAMINHO,
                    headers={"Authorization": f"Bearer {token_owner}"})
    assert r.status_code == 200, r.text
    # 🚨 A FRASE DO DEFEITO, nomeada: se ela voltar, o curinga está comendo a
    # rota outra vez -- e um 400 genérico não diria qual erro é.
    assert "Painel desconhecido" not in r.text
    assert [c["chave"] for c in r.json()["colunas"]][0] == "movimentacao"


def teste_sem_login_e_401(cliente):
    assert cliente.get(CAMINHO).status_code == 401


# ============================================================================
# TAREFA 2.4 — excluir o card inteiro
# 🔵 *"Excluir o card inteiro devolvendo tudo a coluna 1, com justificativa
# unica"*.
# 🚨 PELA ROTA, e nao pela funcao: a rota nova e o corpo dela sao justamente o
# que a leitura do arquivo nao prova (`feedback_rota_nova_pede_teste_http`).
# ⚠️ A ponte e DUBLE -- a rota de verdade iria ao FPSL, e teste que fala com
# servico de fora nao e trava, e sorteio.
# ============================================================================
DEVOLVER_LOTE = "/api/paineis/servico-dos-tecnicos/devolver-lote"


def teste_excluir_o_card_sem_login_e_401(cliente):
    assert cliente.post(DEVOLVER_LOTE,
                        json={"lote_id": 1, "justificativa": "zz"}
                        ).status_code == 401


def teste_excluir_o_card_passa_lote_e_justificativa_para_a_ponte(
        cliente, token_owner, monkeypatch):
    visto = {}

    def duble(lote_id, justificativa, *, por=None):
        visto.update(lote_id=lote_id, justificativa=justificativa, por=por)
        return {"ok": True, "devolvidos": 3, "para": "movimentacao"}

    monkeypatch.setattr(main.fpsl_ponte, "devolver_lote", duble)
    r = cliente.post(DEVOLVER_LOTE,
                     headers={"Authorization": f"Bearer {token_owner}"},
                     json={"lote_id": 7, "justificativa": "zz lote errado"})
    assert r.status_code == 200, r.text
    assert r.json()["devolvidos"] == 3
    assert visto["lote_id"] == 7
    assert visto["justificativa"] == "zz lote errado"
    # 🔵 Quem devolveu fica gravado: e o `por` que o historico do artefato
    # mostra depois.
    assert visto["por"], "o nome de quem excluiu nao foi adiante"


def teste_excluir_o_card_SEM_justificativa_e_recusado_pelo_corpo(
        cliente, token_owner, monkeypatch):
    """🚨 A recusa e do CORPO (422), antes de a ponte ser chamada: laranja sem
    motivo e cor sem informacao, e o lote inteiro em laranja mudo seria N
    itens sem explicacao."""
    chamou = []
    monkeypatch.setattr(main.fpsl_ponte, "devolver_lote",
                        lambda *a, **k: chamou.append(1) or {"ok": True})
    r = cliente.post(DEVOLVER_LOTE,
                     headers={"Authorization": f"Bearer {token_owner}"},
                     json={"lote_id": 7, "justificativa": ""})
    assert r.status_code == 422, r.text
    assert chamou == [], "a ponte foi chamada mesmo sem justificativa"


def teste_quem_nao_e_owner_nao_entra(cliente, monkeypatch):
    """⚠️ A tela move dinheiro e gera o arquivo do Procfy: ela nasce `owner`, e
    a concessão nomeada da `CFG_15.1` é o único outro caminho."""
    u = {"permissoes": ["atendimento", "equipe"]}
    assert registro_telas.pode_acessar(u, CODIGO) is False


# ============================================================================
# O QUE A TELA PRECISA PARA EXISTIR
# ============================================================================
def teste_a_tela_e_aba_do_financeiro_e_nao_item_de_menu():
    t = registro_telas.por_codigo(CODIGO)
    assert t["rota"] == "/paineis/servico-dos-tecnicos"
    assert t["aba_de"] == "PNL_1.4"
    assert t["permissao"] == "owner"
