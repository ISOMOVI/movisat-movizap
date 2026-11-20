# -*- coding: utf-8 -*-
r"""A OS DO CARD ABERTO, NAS ABAS DE PIPELINE — 19/11.

🔵 Dele: *"nos cards do financeiro, aba1, faltam trazer os dados das OS para os
cards, no menu da direita do card aberto"* · *"igual os cards que são de OS do
operacional"*.

🚨 O DEFEITO ERA DE OMISSÃO, o mesmo formato de 18/11: o card do Financeiro
**tem** OS (`numero_os`), a Operação já lia a ficha dela no ERP desde 29/10, e o
diálogo das abas nunca pediu essa leitura -- a coluna da direita tinha só as
passagens de etapa. Nenhuma suíte reclamava, porque nada estava errado: estava
AUSENTE.

As três regras que este arquivo trava:

1. **O número da OS sai do CARD, não da consulta.** Aceitar `numero_os` de fora
   deixaria quem alcança uma aba qualquer ler qualquer OS do ERP.
2. **A permissão é a do CARD** (`_exigir_aba`), e não uma tela fixa -- é a régua
   de 05/11 que fez o `_exigir_aba` nascer. A `/api/paineis/operacao/ficha`
   continua exigindo `PNL_1.1`, e o card de uma aba não tem essa tela.
3. **Card sem OS é 404 com a frase**, nunca ficha vazia: o chamado de verdade
   não tem OS, e a tela precisa distinguir *"não tem"* de *"não li"*.

⚠️ NADA AQUI ESCREVE, e a ficha é dublê: a de verdade vai ao Harmonit.

Roda:  venv/bin/python -m pytest tests/teste_ficha_da_os_do_card.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main  # noqa: E402
from movizap.config import settings  # noqa: E402

FICHA_DUBLE = {
    "numero_os": 0,
    "descricao": "texto da descrição",
    "solucao_tecnica": None,
    "tem_agendamento": False,
    "agendamentos": [],
    "chamado": None,
    "observacoes": [],
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


@pytest.fixture(scope="module")
def card_com_os():
    """Um card REAL de aba que tem OS. ⚠️ Lê, não cria: card de teste em aba de
    produção viraria lixo no quadro de alguém."""
    linha = banco.um(
        """SELECT id, numero_os FROM pipeline_card
            WHERE numero_os IS NOT NULL AND desfecho IS NULL
            ORDER BY id LIMIT 1""")
    if not linha:
        pytest.skip("nenhum card de aba com OS em produção agora")
    return linha


@pytest.fixture(scope="module")
def card_sem_os():
    linha = banco.um(
        """SELECT id FROM pipeline_card
            WHERE numero_os IS NULL ORDER BY id LIMIT 1""")
    if not linha:
        pytest.skip("nenhum card de aba sem OS em produção agora")
    return linha


def teste_o_numero_da_os_sai_do_card(cliente, token_owner, card_com_os,
                                     monkeypatch):
    """🚨 A trava da regra 1: o que a rota lê é o `numero_os` DAQUELE card."""
    pedidos = []

    def duble(numero_os, usuario):
        pedidos.append(numero_os)
        return dict(FICHA_DUBLE, numero_os=numero_os)

    monkeypatch.setattr(main, "_ficha_da_os", duble)
    r = cliente.get(f"/api/paineis/operacao/chamado/{card_com_os['id']}/os",
                    headers={"Authorization": f"Bearer {token_owner}"})
    assert r.status_code == 200, r.text
    assert pedidos == [card_com_os["numero_os"]]
    assert r.json()["descricao"] == "texto da descrição"


def teste_card_sem_os_e_404_com_a_frase(cliente, token_owner, card_sem_os):
    """⚠️ 404 DIZENDO O QUE É: a tela usa isso para não desenhar a caixa."""
    r = cliente.get(f"/api/paineis/operacao/chamado/{card_sem_os['id']}/os",
                    headers={"Authorization": f"Bearer {token_owner}"})
    assert r.status_code == 404
    assert "não tem OS" in r.json()["detail"]


def teste_sem_login_e_401(cliente, card_com_os):
    r = cliente.get(f"/api/paineis/operacao/chamado/{card_com_os['id']}/os")
    assert r.status_code == 401


def teste_a_rota_nao_aceita_numero_de_fora(cliente, token_owner, card_com_os,
                                           monkeypatch):
    """🚨 Mandar `?numero_os=` não muda nada: a consulta é ignorada."""
    pedidos = []
    monkeypatch.setattr(
        main, "_ficha_da_os",
        lambda numero_os, usuario: (pedidos.append(numero_os)
                                    or dict(FICHA_DUBLE, numero_os=numero_os)))
    r = cliente.get(f"/api/paineis/operacao/chamado/{card_com_os['id']}/os"
                    "?numero_os=99999",
                    headers={"Authorization": f"Bearer {token_owner}"})
    assert r.status_code == 200, r.text
    assert pedidos == [card_com_os["numero_os"]]


def teste_a_ficha_da_operacao_continua_exigindo_a_PNL_1_1():
    """⚠️ A porta velha NÃO foi afrouxada por esta entrega -- e isso é o que faz
    a rota nova precisar existir, em vez de rebaixar a antiga."""
    rota = [r for r in main.app.routes
            if getattr(r, "path", None) == "/api/paineis/operacao/ficha"][0]
    fonte = rota.endpoint.__doc__ or ""
    assert "502" in fonte  # a rota certa, e não uma homônima
    from movizap import telas as registro_telas
    u = {"permissoes": ["atendimento"]}
    assert registro_telas.pode_acessar(u, "PNL_1.1") is False
