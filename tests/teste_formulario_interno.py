# -*- coding: utf-8 -*-
r"""FORMULÁRIO INTERNO — as duas portas novas e as três recusas, 27/11.

🔵 Dele, 27/11: o painel de Compras *"sera somente interno"*, e o caminho de
envio *"talvez um botao de acao no chat interno? para forms internos igual no
chat com clientes"*.

🚨 **O PROBLEMA QUE ESTE ARQUIVO EXISTE PARA RESOLVER.** Até hoje o único jeito
de enviar formulário era `POST /api/publico/formulario/{slug}` — protegido por
isca, token de abertura, desafio e rate-limit, e **por nada que exija login**.
Um painel "somente interno" alimentado por uma URL pública seria interno só por
não ser divulgado, e `M7` diz que **trava mede uso, não palavra**.

🚨 **POR HTTP, NÃO POR FUNÇÃO** (`feedback_rota_nova_pede_teste_http`): contar
rota registrada não é pedir uma rota. Foi a ORDEM de registro que fez a
`PNL_1.6` sumir em 19/11, invisível na leitura do arquivo.

⚠️ **ONDE ESTÃO OS DUBLÊS, E POR QUE SÓ AÍ.** O dublê fica na **borda** — a
leitura da definição (`definicao`), a escrita (`registrar`) e o nascimento do
card (`pipeline.criar`) —, nunca em cima da regra que se quer medir. O que é
exercitado de verdade: o portão do `interno` nas duas rotas públicas, o 401 sem
sessão, a recusa da porta interna a formulário que não é interno, e **a injeção
do solicitante**. Dublê que cobre a regra fica verde em produção quebrada
(`feedback_duplo_se_poe_na_borda`).

⚠️ E duas travas leem o Postgres **de verdade**, só que sem escrever: as
consultas de `internos()` e de `ativos_para_convite()`. É a cadeia que nenhum
dublê prova.

Roda:  venv/bin/python -m pytest tests/teste_formulario_interno.py
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

GET_PUBLICO = "/api/publico/formulario/{}"
POST_PUBLICO = "/api/publico/formulario/{}"
GET_INTERNO = "/api/interno/formularios"
POST_INTERNO = "/api/interno/formulario/{}"

FRASE_404 = "Formulário não encontrado."

# A definição mínima que serve às duas portas. `SUGESTAO` e `CONTACT_NAME`
# são os nomes reais do formulário COMPRAS -- ver a migração 122 e o porquê do
# `SUGESTAO` (jsonb reordena chave por tamanho) em `docs/02_Modelo_Dados.md`.
CAMPOS = [
    {"nome": "SUGESTAO", "nosso_nome": "justificativa",
     "rotulo": "Justificativa", "tipo": "text", "obrigatorio": True,
     "multiplo": False, "visivel": True, "ordem": 1, "opcoes": None,
     "ajuda": None, "validacao": None, "fantasma": None, "linhas": 5,
     "fonte": None},
    {"nome": "CONTACT_NAME", "nosso_nome": "solicitante",
     "rotulo": "Solicitante", "tipo": "string", "obrigatorio": True,
     "multiplo": False, "visivel": True, "ordem": 3, "opcoes": None,
     "ajuda": None, "validacao": None, "fantasma": None, "linhas": None,
     "fonte": None},
]


def _definicao(interno: bool, ativo: bool = True) -> dict:
    return {"id": 99001, "codigo": "ZZTESTE", "slug": "zz-teste",
            "titulo": "Formulário de teste", "setor": "Administrativo",
            "botao": "Enviar", "descricao": None, "ativo": ativo,
            "gera_os": False, "problema_id": None, "tipo_os_id": None,
            "prioridade_id": None, "formato": "classico", "etapas": None,
            "busca_cliente": False, "interno": interno,
            "campos": CAMPOS, "regras": []}


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
def sem_escrita(monkeypatch):
    """Segura `registrar`, `etapa_de_destino` e `pipeline.criar`.

    🚨 Devolve o que a rota recebeu, para a asserção medir o que ela MANDOU
    gravar -- e não o que ela respondeu. `M17` linha 5: o estado, não o HTTP.
    """
    visto = {}

    def _registrar(d, valores, arquivos=None, ip=None, vinculo=None,
                   placas_conferidas=None):
        visto["valores"] = dict(valores)
        visto["ip"] = ip
        return {"id": 99002, "criada_em": None, "mensagem": "Recebemos."}

    def _criar(aba_id, etapa_id, solicitacao_id=None, cliente_id=None,
               atendente_id=None, **resto):
        visto["card"] = {"aba_id": aba_id, "etapa_id": etapa_id,
                         "solicitacao_id": solicitacao_id,
                         "atendente_id": atendente_id}
        return {"id": 99003}

    monkeypatch.setattr(main.formularios_mod, "registrar", _registrar)
    monkeypatch.setattr(main.formularios_mod, "etapa_de_destino",
                        lambda slug: {"id": 7547, "aba_id": 2582})
    monkeypatch.setattr(main.pipeline, "criar", _criar)
    return visto


# ============================================================================
# As rotas existem, e ANTES do curinga da SPA
# ============================================================================
def teste_as_duas_rotas_internas_estao_registradas():
    """⚠️ Esta é a trava mais fraca do arquivo e está aqui só para dar nome ao
    defeito quando as de baixo caírem juntas. Rota registrada não é rota que
    responde -- quem prova isso são os pedidos."""
    caminhos = [getattr(r, "path", None) for r in main.app.routes]
    assert GET_INTERNO in caminhos
    assert POST_INTERNO.format("{slug}") in caminhos


def teste_as_internas_vem_antes_do_curinga_da_spa():
    """🚨 Registrada abaixo do `/{caminho:path}` a rota cai no index.html e o
    envio responde **200 com uma página HTML** -- que é o pior dos dois mundos,
    porque parece ter dado certo."""
    caminhos = [getattr(r, "path", None) for r in main.app.routes]
    curinga = caminhos.index("/{caminho:path}")
    assert caminhos.index(GET_INTERNO) < curinga
    assert caminhos.index(POST_INTERNO.format("{slug}")) < curinga


# ============================================================================
# A trava: a internet não alcança formulário interno
# ============================================================================
def teste_o_GET_publico_recusa_formulario_interno(cliente, monkeypatch):
    monkeypatch.setattr(main.formularios_mod, "definicao",
                        lambda slug, so_ativo=True: _definicao(interno=True))
    r = cliente.get(GET_PUBLICO.format("zz-teste"))
    assert r.status_code == 404
    assert r.json()["detail"] == FRASE_404


def teste_a_recusa_e_IDENTICA_a_de_um_slug_que_nao_existe(cliente,
                                                          monkeypatch):
    """🚨 A frase é a mesma de propósito: recusa diferente **conta de fora que
    o formulário existe**. Quem varre `/f/<palpite>` separaria "não existe" de
    "existe e é interno" só pela resposta.

    ⚠️ A asserção compara as DUAS respostas em vez de conferir a frase
    literal: assim ela continua valendo se um dia a frase mudar.
    """
    monkeypatch.setattr(main.formularios_mod, "definicao",
                        lambda slug, so_ativo=True: _definicao(interno=True))
    interno = cliente.get(GET_PUBLICO.format("zz-teste"))

    def _nao_existe(slug, so_ativo=True):
        raise main.formularios_mod.FormularioNaoExiste(slug)

    monkeypatch.setattr(main.formularios_mod, "definicao", _nao_existe)
    inexistente = cliente.get(GET_PUBLICO.format("zz-nada-aqui"))

    assert interno.status_code == inexistente.status_code == 404
    assert interno.json() == inexistente.json()


def teste_o_POST_publico_recusa_formulario_interno(cliente, monkeypatch,
                                                   sem_escrita):
    """🚨 A porta de ESCRITA é a que importa: um GET recusado e um POST aceito
    deixariam a trava valendo nada."""
    monkeypatch.setattr(main.formularios_mod, "definicao",
                        lambda slug, so_ativo=True: _definicao(interno=True))
    r = cliente.post(POST_PUBLICO.format("zz-teste"),
                     data={"valores": json.dumps(
                         {"SUGESTAO": "cabo de rede",
                          "CONTACT_NAME": "Qualquer Um"})})
    assert r.status_code == 404, f"a porta pública aceitou: {r.text[:200]}"
    assert "valores" not in sem_escrita, "recusou e gravou -- pior que aceitar"


def teste_formulario_que_NAO_e_interno_continua_passando_na_porta_publica(
        cliente, monkeypatch):
    """⚠️ A OUTRA METADE. Trava que recusa tudo não é trava, é pane: os 15
    formulários de cliente têm de continuar abrindo."""
    monkeypatch.setattr(main.formularios_mod, "definicao",
                        lambda slug, so_ativo=True: _definicao(interno=False))
    r = cliente.get(GET_PUBLICO.format("zz-teste"))
    assert r.status_code == 200
    assert r.json()["slug"] == "zz-teste"


# ============================================================================
# A porta interna: login obrigatório
# ============================================================================
def teste_a_lista_interna_exige_sessao(cliente):
    assert cliente.get(GET_INTERNO).status_code in (401, 403)


def teste_o_envio_interno_exige_sessao(cliente, sem_escrita):
    r = cliente.post(POST_INTERNO.format("zz-teste"),
                     data={"valores": json.dumps({"SUGESTAO": "x"})})
    assert r.status_code in (401, 403)
    assert "valores" not in sem_escrita


def teste_a_porta_interna_recusa_formulario_que_nao_e_interno(
        cliente, cab, monkeypatch, sem_escrita):
    """🚨 A porta interna serve SÓ formulário interno, e isso não é simetria
    decorativa: sem esta recusa, quem tem o chat interno enviaria pela porta
    autenticada um formulário de cliente -- sem isca, sem desafio e sem
    rate-limit, e com o nome dele injetado no lugar do nome do cliente."""
    monkeypatch.setattr(main.formularios_mod, "definicao",
                        lambda slug, so_ativo=True: _definicao(interno=False))
    r = cliente.post(POST_INTERNO.format("zz-teste"),
                     data={"valores": json.dumps({"SUGESTAO": "x"})},
                     headers=cab)
    assert r.status_code == 404
    assert "valores" not in sem_escrita


# ============================================================================
# 🚨 O SOLICITANTE NÃO SE FALSIFICA
# ============================================================================
def teste_o_solicitante_vem_do_LOGIN_e_nao_do_que_o_navegador_manda(
        cliente, cab, monkeypatch, sem_escrita):
    """🚨 O ponto mais importante do arquivo.

    `CONTACT_NAME` é o TÍTULO do card fechado (`paineis._nome_do_chamado` lê
    só `COMPANY_TITLE` e `CONTACT_NAME`). Se a rota confiasse no que o
    navegador manda, bastaria abrir o inspetor para registrar outra pessoa
    como quem pediu a compra -- e o card mostraria o nome dela.

    ⚠️ O envio abaixo manda um nome de propósito, e o esperado sai da MESMA
    fonte que a rota usa, nunca escrito à mão aqui.
    """
    monkeypatch.setattr(main.formularios_mod, "definicao",
                        lambda slug, so_ativo=True: _definicao(interno=True))
    eu = auth.buscar_usuario(settings.admin_login)

    r = cliente.post(POST_INTERNO.format("zz-teste"),
                     data={"valores": json.dumps(
                         {"SUGESTAO": "Cabo de rede cat6, 20 metros",
                          "CONTACT_NAME": "Outra Pessoa Qualquer"})},
                     headers=cab)

    assert r.status_code == 201, r.text[:300]
    assert sem_escrita["valores"]["CONTACT_NAME"] == eu["nome"]
    assert sem_escrita["valores"]["CONTACT_NAME"] != "Outra Pessoa Qualquer"
    assert sem_escrita["valores"]["SUGESTAO"] == "Cabo de rede cat6, 20 metros"


def teste_o_card_nasce_com_a_autoria_de_quem_clicou(cliente, cab, monkeypatch,
                                                    sem_escrita):
    """⚠️ A rota pública manda `atendente_id=None` porque não há quem; a
    interna tem, e `pipeline_card.criado_por` é onde essa autoria mora.

    🚨 Medido em 27/11: `formulario_solicitacao` **não tem** coluna de autor.
    Eu havia escrito no plano um `aberta_por` em `registrar()` -- a coluna não
    existe, e inventá-la seria migração nova para guardar duas vezes o mesmo
    fato. A autoria é a do card.
    """
    monkeypatch.setattr(main.formularios_mod, "definicao",
                        lambda slug, so_ativo=True: _definicao(interno=True))
    eu = auth.buscar_usuario(settings.admin_login)

    r = cliente.post(POST_INTERNO.format("zz-teste"),
                     data={"valores": json.dumps({"SUGESTAO": "cabo"})},
                     headers=cab)

    assert r.status_code == 201, r.text[:300]
    assert sem_escrita["card"]["atendente_id"] == eu["id"]
    assert sem_escrita["card"]["solicitacao_id"] == 99002


def teste_o_envio_interno_continua_cobrando_o_obrigatorio(cliente, cab,
                                                          monkeypatch,
                                                          sem_escrita):
    """🚨 A validação é a do SERVIDOR, igual à pública.

    Em 22/10 o Bitrix aceitou `values=[]` e criou o registro 15620, porque lá
    a validação toda era no navegador -- e navegador é do cliente. Ter login
    não muda isso: login diz QUEM, não diz que o dado presta.
    """
    monkeypatch.setattr(main.formularios_mod, "definicao",
                        lambda slug, so_ativo=True: _definicao(interno=True))
    r = cliente.post(POST_INTERNO.format("zz-teste"),
                     data={"valores": json.dumps({})}, headers=cab)
    assert r.status_code == 400, r.text[:300]
    assert "Justificativa" in r.text
    assert "valores" not in sem_escrita


# ============================================================================
# As duas consultas, lidas no Postgres de verdade (sem escrever)
# ============================================================================
def teste_a_lista_interna_devolve_exatamente_o_que_a_consulta_diz(cliente,
                                                                   cab):
    """Mede a CONSULTA contra o Postgres, não um dublê.

    🚨 **O QUE ESTA TRAVA AINDA NÃO PROVA, E EU NÃO VENDO COMO PROVADO.** Hoje
    ela compara dois conjuntos **vazios**: o único formulário interno é o
    `COMPRAS`, e ele está `ativo = false` -- ligar formulário é gesto dele,
    pela `FRM_1.1`. Então o que está provado aqui é a metade `ativo` do
    filtro, e a metade `interno` passa a ser medida **no dia em que ele
    ligar**. A outra metade foi medida em 27/11 numa cópia do banco com o
    `COMPRAS` ligado: a lista devolveu `['compras']` e o
    `ativos_para_convite()` **não** o devolveu.

    ⚠️ Escrever `assert devolvidos` aqui faria a trava reprovar por causa de
    uma decisão dele -- e foi o que a minha primeira versão fez.
    """
    r = cliente.get(GET_INTERNO, headers=cab)
    assert r.status_code == 200
    devolvidos = {f["slug"] for f in r.json()}

    reais = {l["slug"] for l in banco.varios(
        "SELECT slug FROM formulario WHERE interno AND ativo")}
    assert devolvidos == reais

    de_cliente = {l["slug"] for l in banco.varios(
        "SELECT slug FROM formulario WHERE NOT interno")}
    assert not (devolvidos & de_cliente)


def teste_o_COMPRAS_existe_e_esta_fora_das_duas_listas_publicas():
    """⚠️ A trava que mede DADO REAL hoje, e não conjunto vazio.

    O `COMPRaS` existe no banco, é `interno` e está desligado. As duas listas
    que a internet alcança -- a do convite e a interna -- não o devolvem, cada
    uma pelo seu motivo. Se alguém "simplificar" o filtro de uma delas, este
    teste cai.
    """
    from movizap import formularios

    linha = banco.um(
        "SELECT interno, ativo FROM formulario WHERE codigo = 'COMPRAS'")
    assert linha, "o formulário COMPRAS não está no banco (migração 122)"
    assert linha["interno"] is True

    oferecidos = {f["slug"] for f in formularios.ativos_para_convite()}
    assert "compras" not in oferecidos

    internos = {f["slug"] for f in formularios.internos()}
    assert ("compras" in internos) == bool(linha["ativo"]), (
        "a lista interna e o campo `ativo` discordam")


def teste_o_convite_nao_pode_nascer_de_formulario_interno():
    """🚨 A TERCEIRA PORTA, e eu quase a esqueci. O convite
    (`formulario_convite`) é um link opaco que abre a página pública -- se um
    formulário interno pudesse virar convite, a trava das outras duas portas
    seria contornada por um bilhete.

    ⚠️ Esta mede a FUNÇÃO que cria o convite, e não a lista: a lista é o que a
    tela oferece, e `criar_convite` é o que o servidor aceita. Oferecer de
    menos não impede ninguém de mandar o slug na mão.
    """
    from movizap import formularios

    with pytest.raises(formularios.FormularioNaoExiste):
        formularios.criar_convite("compras")

    oferecidos = {f["slug"] for f in formularios.ativos_para_convite()}
    internos = {l["slug"] for l in banco.varios(
        "SELECT slug FROM formulario WHERE interno")}
    assert not (oferecidos & internos), (
        f"formulário interno oferecido para convite: {oferecidos & internos}")


def teste_a_definicao_devolve_a_marca_interno():
    """⚠️ Sem esta coluna no `SELECT`, as rotas acima leriam `KeyError` --
    e o `try` da rota de envio engoliria isso em silêncio, igual ao
    `NameError` do `formularios_mod` em 11/11."""
    from movizap import formularios

    d = formularios.definicao("compras", so_ativo=False)
    assert d["interno"] is True
    assert d["ativo"] is False, (
        "o COMPRAS está LIGADO e quem liga formulário é ele, pela tela")
