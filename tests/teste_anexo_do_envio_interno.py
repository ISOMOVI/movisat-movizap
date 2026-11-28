# -*- coding: utf-8 -*-
r"""O ANEXO DO ENVIO INTERNO — a parte que faltava, 27/11.

🔵 Ele: *"pode terminar o que faltou - meu teste e so depois do entregue"*.

🚨 **O QUE ESTAVA SEM TRAVA, E É O CAMINHO QUE ELE VAI USAR.** O
`teste_formulario_interno.py` dublou `registrar` e `pipeline.criar`, então
provou o portão, a injeção do solicitante e a autoria do card — mas **nunca
exercitou um arquivo**. E anexar o orçamento é o segundo gesto do MVP dele.

A peça sem medida era a mais frágil do multipart: os anexos chegam em **duas
listas paralelas** (`campos` e `arquivos`), porque campo de nome dinâmico não
dá para declarar do outro lado. Quem confere o par é a rota — e um par
desalinhado grava o arquivo no campo errado **em silêncio**.

⚠️ **ONDE ESTÃO OS DUBLÊS.** Só `guardar_arquivo` (que escreve no disco),
`registrar` e `pipeline.criar`. O `validar` é o **de verdade**, e é ele que
cobra arquivo obrigatório — é a regra que se quer medir. Nada aqui escreve em
disco nem no banco.

⚠️ Isto é cobertura de um caminho que já está no ar, não conserto: não houve
vermelho antes, e eu não vendo como se houvesse (`M17` linha 1 vale para
defeito, e aqui o defeito seria eu descobrir um — se descobrir, reporto).

Roda:  venv/bin/python -m pytest tests/teste_anexo_do_envio_interno.py
"""
import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main  # noqa: E402
from movizap.config import settings  # noqa: E402

POST = "/api/interno/formulario/{}"

# A definição REAL do COMPRAS depois da migração 123, campo por campo e na
# ordem em que o banco os devolve. 🚨 Dublê irreal não se conserta afrouxando
# o código -- conserta-se o dublê, e por isso esta lista é copiada do banco.
CAMPOS = [
    {"nome": "SUGESTAO", "nosso_nome": "justificativa",
     "rotulo": "Justificativa", "tipo": "text", "obrigatorio": True,
     "multiplo": False, "visivel": True, "ordem": 1, "opcoes": [],
     "ajuda": None, "validacao": None, "fantasma": None, "linhas": 5,
     "fonte": None},
    {"nome": "VALOR", "nosso_nome": "valor", "rotulo": "Valor estimado",
     "tipo": "string", "obrigatorio": False, "multiplo": False,
     "visivel": True, "ordem": 2, "opcoes": [], "ajuda": None,
     "validacao": None, "fantasma": None, "linhas": None, "fonte": None},
    {"nome": "ANEXO", "nosso_nome": "anexo", "rotulo": "Anexo",
     "tipo": "file", "obrigatorio": False, "multiplo": False,
     "visivel": True, "ordem": 3, "opcoes": [], "ajuda": None,
     "validacao": None, "fantasma": None, "linhas": None, "fonte": None},
    {"nome": "CONTACT_NAME", "nosso_nome": "solicitante",
     "rotulo": "Solicitante", "tipo": "string", "obrigatorio": True,
     "multiplo": False, "visivel": True, "ordem": 4, "opcoes": [],
     "ajuda": None, "validacao": None, "fantasma": None, "linhas": None,
     "fonte": None},
]


def _definicao(campos=None, obrigar_anexo=False):
    lista = [dict(c) for c in (campos or CAMPOS)]
    if obrigar_anexo:
        for c in lista:
            if c["nome"] == "ANEXO":
                c["obrigatorio"] = True
    return {"id": 99001, "codigo": "COMPRAS", "slug": "compras",
            "titulo": "Sugestão de compras", "setor": "Administrativo",
            "botao": "Enviar sugestão", "descricao": None, "ativo": True,
            "gera_os": False, "problema_id": None, "tipo_os_id": None,
            "prioridade_id": None, "formato": "classico", "etapas": None,
            "busca_cliente": False, "interno": True, "painel": "compras",
            "campos": lista, "regras": []}


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield


@pytest.fixture(scope="module")
def cliente():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def cab():
    return {"Authorization":
            f"Bearer {auth.criar_token(settings.admin_login)}"}


@pytest.fixture
def espiao(monkeypatch):
    """Guarda o que a rota mandou gravar, e não grava nada."""
    visto = {"arquivos": [], "valores": None, "card": None}

    def _guardar(nome, dados):
        visto["arquivos"].append({"nome": nome, "bytes": len(dados)})
        return {"nome_original": nome, "caminho": "/nao/escrevi/" + nome,
                "bytes": len(dados)}

    def _registrar(d, valores, arquivos=None, ip=None, vinculo=None,
                   placas_conferidas=None):
        visto["valores"] = dict(valores)
        visto["guardados"] = list(arquivos or [])
        return {"id": 99002, "criada_em": None, "mensagem": "Recebemos."}

    def _criar(aba_id, etapa_id, solicitacao_id=None, cliente_id=None,
               atendente_id=None, **resto):
        visto["card"] = {"solicitacao_id": solicitacao_id,
                         "atendente_id": atendente_id}
        return {"id": 99003}

    monkeypatch.setattr(main.formularios_mod, "guardar_arquivo", _guardar)
    monkeypatch.setattr(main.formularios_mod, "registrar", _registrar)
    monkeypatch.setattr(main.formularios_mod, "etapa_de_destino",
                        lambda slug: {"id": 7547, "aba_id": 2582})
    monkeypatch.setattr(main.pipeline, "criar", _criar)
    return visto


@pytest.fixture
def definicao(monkeypatch):
    def _por(d):
        monkeypatch.setattr(main.formularios_mod, "definicao",
                            lambda slug, so_ativo=True: d)
    return _por


VALORES = {"SUGESTAO": "Cabo de rede cat6, 20 metros", "VALOR": "R$ 184,00"}


# ============================================================================
# O PAR `campos` × `arquivos`
# ============================================================================
def teste_o_anexo_vai_para_o_campo_que_a_tela_disse(cliente, cab, espiao,
                                                    definicao):
    definicao(_definicao())
    r = cliente.post(
        POST.format("compras"),
        data={"valores": json.dumps(VALORES), "campos": ["ANEXO"]},
        files=[("arquivos", ("orcamento.pdf", b"%PDF-1.4 teste",
                             "application/pdf"))],
        headers=cab)
    assert r.status_code == 201, r.text[:300]
    assert espiao["arquivos"] == [{"nome": "orcamento.pdf", "bytes": 14}]
    assert espiao["guardados"][0]["campo"] == "ANEXO"
    assert espiao["guardados"][0]["mime"] == "application/pdf"


def teste_dois_anexos_saem_pareados_na_ordem(cliente, cab, espiao, definicao):
    """⚠️ A ordem das duas listas é o contrato. Se a rota ler `campos[i]` com o
    `arquivos[j]` errado, o anexo fica no campo errado EM SILÊNCIO."""
    definicao(_definicao())
    r = cliente.post(
        POST.format("compras"),
        data={"valores": json.dumps(VALORES), "campos": ["ANEXO", "ANEXO"]},
        files=[("arquivos", ("a.pdf", b"aaa", "application/pdf")),
               ("arquivos", ("b.png", b"bbbb", "image/png"))],
        headers=cab)
    assert r.status_code == 201, r.text[:300]
    assert [a["nome"] for a in espiao["arquivos"]] == ["a.pdf", "b.png"]
    assert [a["bytes"] for a in espiao["arquivos"]] == [3, 4]
    assert [g["campo"] for g in espiao["guardados"]] == ["ANEXO", "ANEXO"]
    assert [g["mime"] for g in espiao["guardados"]] == ["application/pdf",
                                                        "image/png"]


def teste_anexo_em_campo_que_NAO_aceita_arquivo_e_recusado(
        cliente, cab, espiao, definicao):
    """🚨 O nome do campo vem da TELA, e tela é do navegador. Sem esta recusa,
    bastaria trocar o nome no inspetor para pendurar arquivo em campo de
    texto -- e o `validar` descartaria o valor, deixando um anexo órfão."""
    definicao(_definicao())
    r = cliente.post(
        POST.format("compras"),
        data={"valores": json.dumps(VALORES), "campos": ["SUGESTAO"]},
        files=[("arquivos", ("x.pdf", b"x", "application/pdf"))],
        headers=cab)
    assert r.status_code == 400, r.text[:300]
    assert "campo que não aceita arquivo" in r.text
    assert espiao["valores"] is None, "recusou e gravou"


def teste_campo_sem_arquivo_correspondente_e_recusado(cliente, cab, espiao,
                                                      definicao):
    """⚠️ Mais arquivos que nomes: o nome vira vazio e cai na mesma recusa --
    o par não se completa, e a rota não inventa um campo."""
    definicao(_definicao())
    r = cliente.post(
        POST.format("compras"),
        data={"valores": json.dumps(VALORES), "campos": []},
        files=[("arquivos", ("x.pdf", b"x", "application/pdf"))],
        headers=cab)
    assert r.status_code == 400, r.text[:300]
    assert espiao["valores"] is None


def teste_sem_anexo_o_envio_passa_porque_o_campo_e_opcional(
        cliente, cab, espiao, definicao):
    """🔵 O anexo é opcional -- decisão dele. Quem não tem orçamento envia."""
    definicao(_definicao())
    r = cliente.post(POST.format("compras"),
                     data={"valores": json.dumps(VALORES)}, headers=cab)
    assert r.status_code == 201, r.text[:300]
    assert espiao["arquivos"] == []
    assert espiao["guardados"] == []


# ============================================================================
# A VALIDAÇÃO DO SERVIDOR VÊ O ARQUIVO
# ============================================================================
def teste_arquivo_obrigatorio_e_cobrado_pelo_SERVIDOR(cliente, cab, espiao,
                                                      definicao):
    """🚨 `validar` recebe os arquivos POR CAMPO e cobra o obrigatório. Sem
    passar o `por_campo`, um campo `file` obrigatório passaria vazio -- e o
    `validar` é o mesmo da rota pública justamente para não repetir o buraco
    do Bitrix de 22/10."""
    definicao(_definicao(obrigar_anexo=True))
    r = cliente.post(POST.format("compras"),
                     data={"valores": json.dumps(VALORES)}, headers=cab)
    assert r.status_code == 400, r.text[:300]
    assert "anexe o arquivo" in r.text.lower()
    assert espiao["valores"] is None

    # E com o arquivo, passa.
    r = cliente.post(
        POST.format("compras"),
        data={"valores": json.dumps(VALORES), "campos": ["ANEXO"]},
        files=[("arquivos", ("o.pdf", b"ok", "application/pdf"))],
        headers=cab)
    assert r.status_code == 201, r.text[:300]


def teste_o_valor_estimado_atravessa_o_validar(cliente, cab, espiao,
                                               definicao):
    """🔵 27/11: o campo novo da migração 123.

    🚨 E A CHAVE CURTA É O QUE FAZ O RESUMO DO CARD LIDERAR COM O PREÇO:
    `valores` é `jsonb` e ordena por tamanho de chave --
    `VALOR` (5) < `SUGESTAO` (8) < `CONTACT_NAME` (12).
    """
    definicao(_definicao())
    r = cliente.post(POST.format("compras"),
                     data={"valores": json.dumps(VALORES)}, headers=cab)
    assert r.status_code == 201, r.text[:300]
    assert espiao["valores"]["VALOR"] == "R$ 184,00"
    assert espiao["valores"]["SUGESTAO"] == "Cabo de rede cat6, 20 metros"
    assert len("VALOR") < len("SUGESTAO") < len("CONTACT_NAME")


def teste_o_anexo_nao_contorna_o_portao_do_interno(cliente, cab, espiao,
                                                   definicao):
    """⚠️ A trava do `interno` vale no caminho com arquivo também: mandar
    anexo não é uma porta lateral."""
    d = _definicao()
    d["interno"] = False
    definicao(d)
    r = cliente.post(
        POST.format("compras"),
        data={"valores": json.dumps(VALORES), "campos": ["ANEXO"]},
        files=[("arquivos", ("x.pdf", b"x", "application/pdf"))],
        headers=cab)
    assert r.status_code == 404, r.text[:300]
    assert espiao["arquivos"] == []
