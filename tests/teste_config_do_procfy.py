# -*- coding: utf-8 -*-
r"""AS CINCO CHAVES DO PROCFY GANHAM TELA — 25/11.

📏 O DEFEITO, medido hoje: as chaves `procfy_categoria`,
`procfy_conta_bancaria`, `procfy_modo_pagamento`, `procfy_centro_de_custo` e
`procfy_tags` sao lidas pelo gerador do arquivo (`CHAVES_DO_PROCFY` no
`fpsl_ponte`), vivem na tabela `config` -- e **NENHUMA ROTA AS ESCREVE**.
Ninguem consegue preenche-las, nem o owner. O arquivo sai com as cinco colunas
em branco e ninguem tem como mudar isso.

🚨 E o mesmo defeito do passo 3 (`pipeline_card.termo`): **coluna sem tela e
dado inalcancavel**. La o campo entrou no mesmo passo da coluna; aqui a coluna
ja existia sozinha havia dias.

🔵 Ele, 18/11, sobre o arquivo sair com elas vazias: *"pode gerar com elas em
branco nesse momento, pois podem preencher a mao por informacao confidencial ou
depois nos passar"*. Entao preencher continua OPCIONAL -- o que muda e passar a
ser POSSIVEL.

Roda:  venv/bin/python -m pytest tests/teste_config_do_procfy.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, main  # noqa: E402
from movizap.config import settings  # noqa: E402

ROTA = "/api/paineis/servico-dos-tecnicos/config-procfy"
CHAVES = ("procfy_categoria", "procfy_conta_bancaria",
          "procfy_modo_pagamento", "procfy_centro_de_custo", "procfy_tags")


@pytest.fixture(scope="module")
def cliente():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def cab():
    return {"Authorization": f"Bearer {auth.criar_token(settings.admin_login)}"}


@pytest.fixture
def config(monkeypatch):
    """A borda: a tabela `config`."""
    estado = {"valores": {}, "escritas": []}

    def varios(sql, params=()):
        s = " ".join(sql.split())
        if "FROM config" in s:
            return [{"chave": k, "valor": v}
                    for k, v in estado["valores"].items()]
        return []

    def executar(sql, params=()):
        estado["escritas"].append((" ".join(sql.split()), params))
        if len(params) >= 2:
            estado["valores"][params[0]] = params[1]
        return 1

    monkeypatch.setattr(main.banco, "varios", varios)
    monkeypatch.setattr(main.banco, "executar", executar)
    return estado


def teste_sem_login_e_401(cliente):
    assert cliente.get(ROTA).status_code == 401
    assert cliente.put(ROTA, json={"procfy_categoria": "x"}).status_code == 401


def teste_le_as_CINCO_chaves_mesmo_vazias(cliente, cab, config):
    """⚠️ Chave que não existe sai como cadeia vazia, e não desaparece da
    resposta: a tela precisa desenhar os cinco campos no primeiro acesso, que é
    exatamente o estado de hoje (nenhuma das cinco existe)."""
    r = cliente.get(ROTA, headers=cab)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert set(corpo) == set(CHAVES), corpo
    assert all(corpo[c] == "" for c in CHAVES)


def teste_grava_e_le_de_volta(cliente, cab, config):
    r = cliente.put(ROTA, headers=cab, json={
        "procfy_categoria": " Serviços de terceiros ",
        "procfy_modo_pagamento": "PIX"})
    assert r.status_code == 200, r.text
    # ⚠️ Aparado: espaço na ponta viraria célula com espaço na planilha dele.
    assert r.json()["procfy_categoria"] == "Serviços de terceiros"
    assert r.json()["procfy_modo_pagamento"] == "PIX"
    assert config["valores"]["procfy_categoria"] == "Serviços de terceiros"
    # 🚨 ON CONFLICT: a chave pode já existir, e gravar duas vezes não pode
    # estourar nem criar linha duplicada.
    assert any("ON CONFLICT" in sql for sql, _p in config["escritas"])


def teste_o_que_NAO_foi_mandado_fica_como_estava(cliente, cab, config):
    """🚨 A tela pode mandar um campo só. Tratar ausência como "apagar" perderia
    o que a pessoa já tinha preenchido -- "não mandei" não é "limpe"."""
    config["valores"]["procfy_conta_bancaria"] = "conta 123"
    cliente.put(ROTA, headers=cab, json={"procfy_categoria": "X"})
    assert config["valores"]["procfy_conta_bancaria"] == "conta 123"


def teste_vazio_EXPLICITO_limpa(cliente, cab, config):
    """⚠️ Mandar o campo vazio é diferente de não mandar: isso limpa."""
    config["valores"]["procfy_tags"] = "tag antiga"
    r = cliente.put(ROTA, headers=cab, json={"procfy_tags": "   "})
    assert r.json()["procfy_tags"] == ""
    assert config["valores"]["procfy_tags"] == ""


def teste_chave_DESCONHECIDA_e_recusada(cliente, cab, config):
    """🚨 A rota não é um gravador genérico de `config`: só as cinco do Procfy.
    Sem isto, uma rota de painel escreveria qualquer chave do sistema."""
    r = cliente.put(ROTA, headers=cab,
                    json={"procfy_categoria": "ok", "jornada_ligada": "true"})
    assert r.status_code == 422, r.text
    assert config["escritas"] == [], "não gravou nada"


def teste_valor_longo_demais_e_recusado(cliente, cab, config):
    """⚠️ Teto porque isto vira célula de planilha, e um parágrafo numa coluna
    de categoria quebra a importação."""
    r = cliente.put(ROTA, headers=cab, json={"procfy_categoria": "x" * 300})
    assert r.status_code == 422, r.text
    assert config["escritas"] == []
