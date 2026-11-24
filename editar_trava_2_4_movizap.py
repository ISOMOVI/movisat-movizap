# -*- coding: utf-8 -*-
"""Tarefa 2.4, trava da rota do MoviZap — por HTTP, com e sem login."""
import pathlib

q = pathlib.Path("tests/teste_rota_servico_dos_tecnicos.py")
bq = q.read_bytes()
CRLF = b"\r\n" in bq
u = bq.decode("utf-8").replace("\r\n", "\n")

VELHO = '''def teste_sem_login_e_401(cliente):
    assert cliente.get(CAMINHO).status_code == 401'''

NOVO = '''def teste_sem_login_e_401(cliente):
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
    assert chamou == [], "a ponte foi chamada mesmo sem justificativa"'''

assert VELHO in u and u.count(VELHO) == 1
u = u.replace(VELHO, NOVO, 1)
print("  ok: as 3 travas da rota de 2.4")

saida = u.replace("\n", "\r\n") if CRLF else u
q.write_bytes(saida.encode("utf-8"))
print("gravado:", q, len(saida), "bytes")
