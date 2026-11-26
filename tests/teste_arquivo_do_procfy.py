# -*- coding: utf-8 -*-
r"""O ARQUIVO DO PROCFY SAI COMO A REGRA MANDA — 25/11.

🔵 Ele: *"o arquivo precisa ser gerado corretamente - como na regra"*.

📏 A REGRA, que ja esta no codigo do FPSL: o modelo
`modelo_importacao_procfy.xlsx` tem **14 colunas e zero linhas de exemplo**, e a
ordem delas foi lida do arquivo (`PROCFY_COLUNAS`).

🚨 **O DEFEITO QUE ESTAS TRAVAS PRENDEM.** Quem escreve o binario e o MoviZap, e
ele montava o cabecalho com `list(linhas[0].keys())` -- a ordem de insercao do
PRIMEIRO dicionario que chegou pela ponte. Funcionava por coincidencia: no dia
em que alguem reordenasse o dicionario no FPSL, ou acrescentasse uma chave, o
arquivo sairia com outra ordem **em silencio** e o Procfy recusaria a
importacao. A ordem tem de vir da REGRA, nao do dado.

⚠️ E dois irmaos do mesmo defeito:
  · `linhas` vazia dava `colunas = []` -- um arquivo **sem cabecalho nenhum**;
  · o nome do arquivo saia do nome do tecnico cru, e o nosso contato se chama
    `Franck | Campinas - SP`: `|` e caractere **proibido** em nome de arquivo no
    Windows, e o download chegaria quebrado.

Roda:  venv/bin/python -m pytest tests/teste_arquivo_do_procfy.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, fpsl_ponte, main  # noqa: E402
from movizap.config import settings  # noqa: E402

ROTA = "/api/paineis/servico-dos-tecnicos/arquivo/{}"

# 📏 As 14 colunas do modelo, na ordem dele. Esta tupla e COPIA DELIBERADA da
# regra do FPSL: e ela que faz a trava reprovar se alguem mudar a ordem de um
# lado so. Trava que importa a constante do codigo medido nao mede nada.
COLUNAS = ("Tipo de Lançamento", "Data de pagamento", "Data de competência",
           "Descrição", "Valor", "Categoria", "Recebido de/Pago a", "Pago?",
           "Observações", "Contas bancárias",
           "Número de Documento / Nosso número", "Modo de pagamento",
           "Centro de Custo", "Tags (Por Marcação)")


def _linha(**troca):
    linha = {c: "" for c in COLUNAS}
    linha.update({"Tipo de Lançamento": "Despesa", "Valor": "570,00",
                  "Descrição": "OS 17120 | Franck"})
    linha.update(troca)
    return linha


@pytest.fixture(scope="module")
def cliente():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def cab():
    """O token de verdade, como as travas irmas desta rota fazem.

    ⚠️ Trocar a dependencia por `dependency_overrides` NAO funciona aqui: o
    `Depends(auth.requer_tela("PNL_1.6"))` foi resolvido no import e cada
    chamada de `requer_tela` devolve uma funcao NOVA, entao a chave do
    dicionario nunca e a mesma. Pedir com token e mais simples e mede a porta
    de verdade.
    """
    return {"Authorization": f"Bearer {auth.criar_token(settings.admin_login)}"}


@pytest.fixture
def previa(monkeypatch):
    estado = {"resposta": {"ok": True, "tecnico": "Franck | Campinas - SP",
                           "colunas": list(COLUNAS),
                           "linhas": [_linha()], "total": 570.0,
                           "artefatos": 1, "em_branco": [], "aviso": None}}
    monkeypatch.setattr(fpsl_ponte, "previa_do_arquivo",
                        lambda lote_id, **k: estado["resposta"])
    return estado


def _planilha(corpo: bytes):
    import io

    from openpyxl import load_workbook
    livro = load_workbook(io.BytesIO(corpo))
    folha = livro.active
    return [[c.value for c in linha] for linha in folha.iter_rows()]


def teste_o_cabecalho_tem_as_14_colunas_na_ordem_da_regra(previa, cliente, cab):
    r = cliente.get(ROTA.format(7), headers=cab)
    assert r.status_code == 200, r.text
    linhas = _planilha(r.content)
    assert linhas[0] == list(COLUNAS), linhas[0]
    assert len(linhas[0]) == 14


def teste_a_ORDEM_vem_da_regra_e_nao_do_dado(previa, cliente, cab):
    """🚨 O defeito: o cabeçalho saía da ordem de inserção do dicionário. Aqui a
    linha chega EMBARALHADA e o arquivo tem de sair na ordem da regra."""
    embaralhada = {c: "" for c in reversed(COLUNAS)}
    embaralhada["Valor"] = "570,00"
    previa["resposta"]["linhas"] = [embaralhada]
    r = cliente.get(ROTA.format(7), headers=cab)
    assert r.status_code == 200, r.text
    linhas = _planilha(r.content)
    assert linhas[0] == list(COLUNAS), "a ordem tem de ser a da regra"
    # E o valor continua debaixo da coluna certa.
    assert linhas[1][COLUNAS.index("Valor")] == "570,00"


def teste_linha_que_NAO_casa_com_a_regra_e_RECUSADA(previa, cliente, cab):
    """🚨 Coluna faltando ou sobrando não sai calada: arquivo que o Procfy
    recusa na importação é pior que erro aqui, porque o erro aparece longe."""
    faltando = _linha()
    del faltando["Centro de Custo"]
    previa["resposta"]["linhas"] = [faltando]
    r = cliente.get(ROTA.format(7), headers=cab)
    assert r.status_code == 500, r.text
    assert "Centro de Custo" in r.text


def teste_sem_linha_nenhuma_NAO_sai_arquivo_sem_cabecalho(previa, cliente, cab):
    """⚠️ `linhas` vazia dava `colunas = []` -- planilha sem cabeçalho."""
    previa["resposta"]["linhas"] = []
    r = cliente.get(ROTA.format(7), headers=cab)
    assert r.status_code == 400, r.text


def teste_o_nome_do_arquivo_e_SEGURO(previa, cliente, cab):
    """🚨 O nosso contato se chama `Franck | Campinas - SP`, e `|` é proibido em
    nome de arquivo no Windows. Aspas e quebra de linha quebrariam o próprio
    cabeçalho HTTP."""
    previa["resposta"]["tecnico"] = 'Franck | Campinas - SP "x"\n'
    r = cliente.get(ROTA.format(7), headers=cab)
    assert r.status_code == 200, r.text
    nome = r.headers["content-disposition"]
    for proibido in ('|', '"x"', "\n", "\r", "/", "\\", ":", "*", "?", "<", ">"):
        assert proibido not in nome.replace('filename="', "").rstrip('"'), proibido
    assert nome.endswith('.xlsx"')
    assert "Franck" in nome, "o nome ainda diz de quem é o arquivo"


def teste_a_aba_da_planilha_tem_nome(previa, cliente, cab):
    """Detalhe que o Procfy lê: a folha se chama `Lançamentos`."""
    import io

    from openpyxl import load_workbook
    r = cliente.get(ROTA.format(7), headers=cab)
    livro = load_workbook(io.BytesIO(r.content))
    assert livro.active.title == "Lançamentos"
