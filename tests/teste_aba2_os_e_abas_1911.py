# -*- coding: utf-8 -*-
r"""A OS DO ARTEFATO E A TIRA DE ABAS DA `PNL_1.6` — 19/11.

🔵 Pedido dele: *"faltam várias coisas e melhorias de UX/UI principalmente em
relação a funcionalidade e estilos dos cards -- como a aba1 apresenta -- foque
na aba 2 e finalize a entrega e serviços dela"*.

Duas peças entraram no servidor, e este arquivo trava as duas:

**1. `GET /api/paineis/servico-dos-tecnicos/os/{artefato_id}`** — a caixa *"A
OS no Harmonit"* que a aba 1 ganhou em 19/11, agora na aba 2.
🚨 **O NÚMERO DA OS SAI DO ARTEFATO, NUNCA DA CONSULTA.** É a mesma régua da
rota irmã daquele dia: aceitar `numero_os` de fora deixaria quem alcança a
`PNL_1.6` ler **qualquer** OS do ERP. O teste manda `?numero_os=99999` e exige
que a ficha lida continue sendo a do artefato.

**2. `abas` no quadro** — sem ela a `PNL_1.6` era um beco: ela não aparece no
menu por desenho (`aba_de: PNL_1.4`), e quem entrava não tinha caminho de volta
para a aba 1.

🚨 **E A VARREDURA DE SOMBRA, que é a lição de 19/11**: contar rota registrada
não é pedir uma rota, e a ordem de registro é invisível na leitura do arquivo.
Aqui a rota nova é testada contra o `path_regex` de **todas** as rotas GET
declaradas antes dela.

⚠️ NADA AQUI FALA COM O FPSL NEM COM O HARMONIT: os dois são dublê. Teste que
depende de serviço de fora não é trava, é sorteio.

Roda:  venv/bin/python -m pytest tests/teste_aba2_os_e_abas_1911.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main  # noqa: E402
from movizap.config import settings  # noqa: E402

CAMINHO_DO_QUADRO = "/api/paineis/servico-dos-tecnicos"
CAMINHO_DA_OS = "/api/paineis/servico-dos-tecnicos/os/{}"

# 📏 O artefato 7 e a OS 16689 são reais no quadro de 19/11 (SWM - COMERCIO E
# LOCACAO DE IMOVEIS LTDA, tipo Contrato). ⚠️ Aqui eles são dublê: o que o
# teste prova é o CAMINHO do número, não o conteúdo da ficha.
ARTEFATO = 7
OS_DO_ARTEFATO = 16689

QUADRO_DUBLE = {
    "colunas": [
        {"chave": "movimentacao", "cards": [
            {"tecnico_id": 14262, "tecnico_nome": "Franck", "artefatos": [
                {"id": ARTEFATO, "numero_os": OS_DO_ARTEFATO,
                 "valor_pagamento": 80.0, "valor_km": 12.5},
            ]},
        ]},
        {"chave": "preparacao", "cards": []},
        {"chave": "validacao", "cards": []},
        {"chave": "procfy", "cards": []},
        {"chave": "enviado", "cards": []},
    ],
    "artefatos": 1,
}

ABAS_DUBLE = [
    {"codigo_tela": "PNL_1.4", "titulo": "Financeiro"},
    {"codigo_tela": "PNL_1.6", "titulo": "Serviço dos técnicos"},
]


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


@pytest.fixture()
def sem_fpsl(monkeypatch):
    """O quadro e a ficha, os dois de mentira — e a ficha ANOTA o número que
    recebeu, que é o que este arquivo mede."""
    pedidos = []
    monkeypatch.setattr(main.fpsl_ponte, "quadro_do_pagamento",
                        lambda: QUADRO_DUBLE)
    monkeypatch.setattr(main.pipeline, "abas", lambda painel: ABAS_DUBLE)

    def ficha(numero_os, usuario):
        pedidos.append(numero_os)
        return {"numero_os": numero_os, "descricao": "RESSARCIMENTO",
                "solucao_tecnica": None, "chamado": None,
                "tem_agendamento": False, "agendamentos": []}

    monkeypatch.setattr(main, "_ficha_da_os", ficha)
    return pedidos


# ============================================================================
# A VARREDURA DE SOMBRA — a lição de 19/11
# ============================================================================
def teste_a_rota_da_os_nao_esta_escondida_por_nenhuma_anterior():
    """🚨 Contar rota registrada NÃO é pedir uma rota.

    O FastAPI casa na ORDEM DE REGISTRO. Esta trava testa o caminho literal
    contra o `path_regex` de cada rota GET declarada **antes** dela — que é
    exatamente o que o curinga `/api/paineis/{painel}` fez com o quadro em
    18/11 e ninguém viu até ele abrir a tela.
    """
    alvo = CAMINHO_DA_OS.format(ARTEFATO)
    minha = None
    for i, r in enumerate(main.app.routes):
        if getattr(r, "path", None) == "/api/paineis/servico-dos-tecnicos/os/{artefato_id}":
            minha = i
            break
    assert minha is not None, "a rota da OS do artefato sumiu do app"

    escondem = []
    for r in main.app.routes[:minha]:
        metodos = getattr(r, "methods", set()) or set()
        regex = getattr(r, "path_regex", None)
        if "GET" in metodos and regex is not None and regex.match(alvo):
            escondem.append(getattr(r, "path", "?"))
    assert not escondem, (
        "estas rotas casam com %s antes dela e a engolem: %s" % (alvo, escondem))


# ============================================================================
# O NÚMERO SAI DO ARTEFATO
# ============================================================================
def teste_le_a_os_do_artefato(cliente, token_owner, sem_fpsl):
    r = cliente.get(CAMINHO_DA_OS.format(ARTEFATO),
                    headers={"Authorization": f"Bearer {token_owner}"})
    assert r.status_code == 200, r.text
    assert sem_fpsl == [OS_DO_ARTEFATO]
    assert r.json()["numero_os"] == OS_DO_ARTEFATO


def teste_numero_de_fora_e_ignorado(cliente, token_owner, sem_fpsl):
    """🚨 A trava que impede a tela de virar leitor de qualquer OS do ERP."""
    r = cliente.get(CAMINHO_DA_OS.format(ARTEFATO) + "?numero_os=99999",
                    headers={"Authorization": f"Bearer {token_owner}"})
    assert r.status_code == 200, r.text
    assert sem_fpsl == [OS_DO_ARTEFATO], (
        "a consulta de fora mudou qual OS foi lida: %s" % sem_fpsl)


def teste_artefato_fora_do_quadro_e_404_com_a_frase(cliente, token_owner,
                                                    sem_fpsl):
    """🚨 404 com a razão, e não ficha vazia: vazio é indistinguível de OS sem
    dados, e quem lê concluiria que não há o que ver."""
    r = cliente.get(CAMINHO_DA_OS.format(999999),
                    headers={"Authorization": f"Bearer {token_owner}"})
    assert r.status_code == 404
    assert "não está no quadro" in r.text
    assert sem_fpsl == [], "leu uma OS para um artefato que não existe"


def teste_sem_login_e_401(cliente):
    assert cliente.get(CAMINHO_DA_OS.format(ARTEFATO)).status_code == 401


# ============================================================================
# A TIRA DE ABAS
# ============================================================================
def teste_o_quadro_traz_as_abas_do_financeiro(cliente, token_owner, sem_fpsl):
    """🔵 Sem esta lista a `PNL_1.6` é um beco: ela não está no menu por
    desenho, e a volta para a aba 1 só existe pela tira."""
    r = cliente.get(CAMINHO_DO_QUADRO,
                    headers={"Authorization": f"Bearer {token_owner}"})
    assert r.status_code == 200, r.text
    corpo = r.json()
    codigos = [a["codigo_tela"] for a in corpo["abas"]]
    assert codigos == ["PNL_1.4", "PNL_1.6"]
    # ⚠️ A ROTA NÃO VEM DAQUI: quem a resolve é o `sessao.telas` da tela, e é
    # isso que faz aba sem permissão cair fora sem segunda régua.
    assert all("rota" not in a for a in corpo["abas"])


def teste_o_quadro_continua_respondendo_as_cinco_colunas(cliente, token_owner,
                                                         sem_fpsl):
    r = cliente.get(CAMINHO_DO_QUADRO,
                    headers={"Authorization": f"Bearer {token_owner}"})
    assert [c["chave"] for c in r.json()["colunas"]] == [
        "movimentacao", "preparacao", "validacao", "procfy", "enviado"]
