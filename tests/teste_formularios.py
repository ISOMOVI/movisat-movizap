"""Formulários próprios — Etapa 1 (22/10, migração 074).

🚨 O TESTE QUE JUSTIFICA O MÓDULO: **o obrigatório é recusado NO SERVIDOR**.
Medido em 22/10 no Bitrix24, enviando `values=[]` vazio no formulário de
Contato: foi ACEITO e criou o registro `15620`. Lá a validação dos 239 campos
era toda no navegador -- e navegador é do cliente. Se esta suíte ficar verde
com a validação removida, o módulo inteiro perdeu a razão de existir.

🚨 AS REGRAS CONDICIONAIS SÃO COBRADAS DE UM ARQUIVO COMPARTILHADO
(`tests/casos_regras_formulario.json`), lido TAMBÉM pelo vitest em
`frontend/src/formulario_2210.teste.js`. Servidor e navegador avaliam a mesma
estrutura; caso novo entra no JSON e as duas suítes o cobram sozinhas.

🚨 ESCREVE EM TABELAS DE PRODUÇÃO (`formulario`, `formulario_campo`,
`formulario_regra`, `formulario_solicitacao`, `formulario_arquivo`), como o
resto da suíte: tudo com o código `ZZ_TESTE_FRM` e tudo apagado no fim.
⚠️ E NÃO TOCA NA `config` -- `desafio_sempre` é interruptor do sistema, e um
teste meu já desligou a distribuição de produção por nove minutos em 19/10.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, formularios, operacao  # noqa: E402

RAIZ = Path("/home/claude/movizap_painel")
CASOS = json.loads((RAIZ / "tests" / "casos_regras_formulario.json")
                   .read_text(encoding="utf-8"))["casos"]
MAPA = json.loads((RAIZ / "dados" / "formularios_bitrix" / "mapa_bruto.json")
                  .read_text(encoding="utf-8"))

CODIGO = "ZZ_TESTE_FRM"
SLUG = "zz-teste-frm"


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield


@pytest.fixture
def limpo():
    """Apaga o formulário de teste antes e depois.

    🚨 A SOLICITAÇÃO SAI PRIMEIRO, E A ORDEM NÃO É DETALHE: `formulario_campo`
    e `formulario_regra` são `ON DELETE CASCADE` (são definição), mas
    `formulario_solicitacao` NÃO é -- de propósito. Apagar um formulário com
    solicitação recebida é recusado pelo banco, e tem de ser: solicitação é o
    que o cliente escreveu, e não pode desaparecer porque alguém mexeu na
    definição. O teste existe dentro dessa regra, não contra ela.
    """
    def apagar():
        banco.executar(
            """DELETE FROM formulario_solicitacao
                WHERE formulario_id IN (SELECT id FROM formulario
                                         WHERE codigo = %s)""", (CODIGO,))
        banco.executar("DELETE FROM formulario WHERE codigo = %s", (CODIGO,))
    apagar()
    yield
    apagar()


def gravar(bitrix_id: str = "70"):
    return formularios.gravar_definicao(MAPA[bitrix_id], codigo=CODIGO,
                                        slug=SLUG, setor="Teste",
                                        titulo="zz Teste de formulario")


# ----------------------------------------------------------------------------
# ⚠️ FIXTURE REALISTA, E ISSO CUSTOU UMA RODADA VERMELHA: preencher todo campo
# com "zz valor" reprovava em `CNPJ`, que no Bitrix é do tipo `double`. A
# fixture é que não representava o formulário -- o código estava certo em
# recusar letra onde se pede número.
# ----------------------------------------------------------------------------
def valor_de(campo: dict) -> str:
    if campo["tipo"] == "list":
        return str(campo["opcoes"][0]["value"])
    if campo["tipo"] == "double":
        return "12345678000199"
    if campo["tipo"] == "date":
        return "2026-10-22"
    if campo["tipo"] == "email":
        return "zz-teste@movisat.com.br"
    if campo["tipo"] == "phone":
        return "+5518998116168"
    return "zz valor"


def preencher(d: dict, pular: tuple = ()) -> dict:
    """Todo campo que ESTÁ DE PÉ, com valor do tipo certo.

    🚨 PREENCHE EM VOLTAS, como gente: escolher uma opção faz nascer campo
    novo (CPF aparece quando o contrato é pessoa física), e esse campo também
    é obrigatório. Uma passada só pela lista deixaria o formulário incompleto
    e o teste reprovaria no código certo -- foi o que aconteceu na primeira
    rodada desta suíte.
    """
    valores: dict = {}
    for _ in range(len(d["regras"]) + 2):
        de_pe = formularios.visiveis(d, valores)
        antes = len(valores)
        for c in d["campos"]:
            if c["nome"] in valores or c["nome"] not in de_pe:
                continue
            if c["tipo"] in formularios.TIPOS_DECORATIVOS or c["tipo"] in pular:
                continue
            if c["tipo"] == "file":
                continue          # anexo não é valor: vai em `arquivos`
            valores[c["nome"]] = valor_de(c)
        if len(valores) == antes:
            break
    return valores


# ============================================================================
# As regras, pelos casos compartilhados
# ============================================================================
@pytest.mark.parametrize("caso", CASOS, ids=[c["nome"] for c in CASOS])
def teste_visiveis_pelos_casos_compartilhados(caso):
    d = {"campos": caso["campos"], "regras": caso["regras"]}
    assert formularios.visiveis(d, caso["valores"]) == set(caso["visiveis"])


# ============================================================================
# A carga da definição
# ============================================================================
def teste_a_carga_bate_com_o_mapa(limpo):
    """A contagem de campos carregada é a do `mapa_bruto.json`, formulário por
    formulário. ⚠️ Conta pelo BANCO, não pelo retorno da escrita."""
    for bitrix_id in MAPA:
        gravar(bitrix_id)
        d = formularios.definicao(SLUG, so_ativo=False)
        esperado = MAPA[bitrix_id]["data"]["fields"]
        assert len(d["campos"]) == len(esperado), bitrix_id
        assert [c["nome"] for c in d["campos"]] == [c["name"] for c in esperado]


def teste_alvo_de_show_nasce_escondido(limpo):
    """🚨 O `visible` DO LOADER NÃO DIZ QUEM NASCE ESCONDIDO: nos 15, nenhum
    campo vem com `visible: false`, e há 60 ações `show`. Quem traduz é a
    carga. Sem isto, todo campo condicional apareceria sempre -- e a tela
    ficaria "só um pouco mais comprida", que ninguém nota."""
    # 32 = Suporte: uma regra, três campos mostrados por ela.
    gravar("32")
    d = formularios.definicao(SLUG, so_ativo=False)
    escondidos = {c["nome"] for c in d["campos"] if not c["visivel"]}
    assert escondidos == {"COMPANY_TITLE", "COMPANY_UF_CRM_1646332310941",
                          "CONTACT_UF_CRM_1646331183902"}
    # E o loader, de onde isto saiu, não marca NENHUM como invisível:
    assert all(c.get("visible") for c in MAPA["32"]["data"]["fields"])


def teste_carga_e_idempotente_e_preserva_solicitacao(limpo):
    """Recarregar reescreve definição e NÃO apaga o que já chegou."""
    gravar("70")
    d = formularios.definicao(SLUG, so_ativo=False)
    formularios.registrar(d, {"CONTACT_NAME": "zz Antes"})
    antes = banco.um("SELECT count(*) AS n FROM formulario_solicitacao "
                     "WHERE formulario_id = %s", (d["id"],))["n"]
    gravar("70")
    depois = banco.um("SELECT count(*) AS n FROM formulario_solicitacao "
                      "WHERE formulario_id = %s", (d["id"],))["n"]
    assert antes == depois == 1
    assert len(formularios.definicao(SLUG, so_ativo=False)["campos"]) == 5


def teste_nosso_nome_e_legivel_e_unico(limpo):
    """O `nosso_nome` nasce do rótulo (que já é humano) e não repete."""
    gravar("98")   # ficha cadastral: 36 campos, o maior
    d = formularios.definicao(SLUG, so_ativo=False)
    nomes = [c["nosso_nome"] for c in d["campos"]]
    assert len(nomes) == len(set(nomes))
    assert "razao-social" in nomes or any("cnpj" in n for n in nomes)
    # Nenhum nome legível carrega o lixo do nome de origem.
    assert not any("uf-crm" in n for n in nomes)


def teste_tipo_desconhecido_para_na_carga(limpo):
    """Tipo que não conhecemos para AQUI, não na tela do cliente -- onde
    viraria caixa de texto e ninguém notaria."""
    bruto = json.loads(json.dumps(MAPA["70"]))
    bruto["data"]["fields"][0]["type"] = "assinatura-digital"
    with pytest.raises(operacao.DadoInvalido):
        formularios.gravar_definicao(bruto, codigo=CODIGO, slug=SLUG,
                                     setor="Teste")


# ============================================================================
# A validação — o ponto do módulo
# ============================================================================
def teste_obrigatorio_e_recusado_no_servidor(limpo):
    """🚨 O TESTE QUE JUSTIFICA O MÓDULO. O Bitrix aceitou vazio (registro
    15620 em 22/10); nós não."""
    gravar("70")
    d = formularios.definicao(SLUG, so_ativo=False)
    with pytest.raises(operacao.DadoInvalido) as e:
        formularios.validar(d, {})
    # A frase é a que a PESSOA lê: traz o rótulo, não o nome do campo.
    assert "Primeiro Nome" in str(e.value)


def teste_opcao_de_lista_fora_da_lista_e_recusada(limpo):
    gravar("70")
    d = formularios.definicao(SLUG, so_ativo=False)
    with pytest.raises(operacao.DadoInvalido):
        formularios.validar(d, {"CONTACT_NAME": "zz", "CONTACT_LAST_NAME": "zz",
                                "DEAL_UF_CRM_DEAL_1649449139431": "999999"})


def teste_campo_escondido_nao_vira_campo_vazio(limpo):
    """🚨 ESCONDIDO SOME, NÃO FICA VAZIO. "A pessoa não respondeu" e "a
    pergunta não foi feita" são coisas diferentes, e guardar as duas como `""`
    perderia a diferença para sempre. Mesmo que o cliente mande o valor."""
    gravar("32")
    d = formularios.definicao(SLUG, so_ativo=False)
    gatilho = "CONTACT_UF_CRM_6227C13CCA255"
    valores = preencher(d)
    valores[gatilho] = "1754"           # pessoa FISICA: a empresa nao aparece
    valores["COMPANY_TITLE"] = "zz Empresa mandada por fora"
    valores["COMPANY_UF_CRM_1646332310941"] = "99999999999999"   # o CNPJ, idem
    limpos = formularios.validar(d, valores)
    assert "COMPANY_TITLE" not in limpos
    assert limpos[gatilho] == "1754"


def teste_obrigatorio_escondido_nao_e_cobrado(limpo):
    """O oposto do de cima: pergunta que não foi feita não pode travar o
    envio."""
    gravar("32")
    d = formularios.definicao(SLUG, so_ativo=False)
    banco.executar("""UPDATE formulario_campo SET obrigatorio = true
                       WHERE formulario_id = %s AND nome = %s""",
                   (d["id"], "COMPANY_TITLE"))
    d = formularios.definicao(SLUG, so_ativo=False)
    valores = preencher(d)
    valores["CONTACT_UF_CRM_6227C13CCA255"] = "1754"
    limpos = formularios.validar(d, valores)      # não levanta
    assert "COMPANY_TITLE" not in limpos


def teste_telefone_sai_normalizado(limpo):
    """O telefone passa pelo módulo da casa, não por regex nova."""
    gravar("32")
    d = formularios.definicao(SLUG, so_ativo=False)
    campo = next(c for c in d["campos"] if c["tipo"] == "phone")
    valores = preencher(d)
    valores[campo["nome"]] = "(18) 99811-6168"
    assert formularios.validar(d, valores)[campo["nome"]] == "+5518998116168"


def teste_envio_com_campos_demais_e_recusado(limpo):
    gravar("70")
    d = formularios.definicao(SLUG, so_ativo=False)
    with pytest.raises(operacao.DadoInvalido):
        formularios.validar(d, {f"campo_{i}": "x" for i in range(200)})


# ============================================================================
# Anexo
# ============================================================================
def teste_nome_de_arquivo_nunca_vira_caminho(tmp_path, monkeypatch):
    """⚠️ O nome vem da INTERNET. `../../.env` é um nome esquisito, e nada
    além disso: o arquivo tem de cair dentro da pasta de anexos."""
    monkeypatch.setattr(formularios, "PASTA_ANEXOS", tmp_path)
    r = formularios.guardar_arquivo("../../.env.pdf", b"nada")
    caminho = Path(r["caminho"]).resolve()
    assert caminho.is_relative_to(tmp_path.resolve())
    assert r["nome_original"] == ".env.pdf"


def teste_extensao_fora_da_lista_branca_e_recusada(tmp_path, monkeypatch):
    monkeypatch.setattr(formularios, "PASTA_ANEXOS", tmp_path)
    with pytest.raises(operacao.DadoInvalido):
        formularios.guardar_arquivo("instalador.exe", b"MZ")
    assert not list(tmp_path.iterdir())


def teste_arquivo_grande_demais_e_recusado(tmp_path, monkeypatch):
    monkeypatch.setattr(formularios, "PASTA_ANEXOS", tmp_path)
    monkeypatch.setattr(formularios, "TETO_ARQUIVO", 10)
    with pytest.raises(operacao.DadoInvalido):
        formularios.guardar_arquivo("foto.jpg", b"0123456789A")


def teste_arquivo_obrigatorio_e_cobrado(limpo):
    gravar("96")   # teste gratuito: tem campo de arquivo
    d = formularios.definicao(SLUG, so_ativo=False)
    arquivo = next(c for c in d["campos"] if c["tipo"] == "file")
    banco.executar("""UPDATE formulario_campo SET obrigatorio = true
                       WHERE formulario_id = %s AND nome = %s""",
                   (d["id"], arquivo["nome"]))
    d = formularios.definicao(SLUG, so_ativo=False)
    valores = preencher(d)
    with pytest.raises(operacao.DadoInvalido):
        formularios.validar(d, valores, arquivos={})
    # Com os anexos, passa. ⚠️ SAO TRES campos de arquivo no teste gratuito, e
    # o Bitrix ja marcava outros como obrigatorios: anexar um so continua
    # faltando -- foi o que a primeira versao deste teste nao viu.
    anexos = {c["nome"]: [{"nome_original": "x.pdf"}] for c in d["campos"]
              if c["tipo"] == "file" and c["obrigatorio"]}
    assert arquivo["nome"] in anexos
    formularios.validar(d, valores, arquivos=anexos)


# ============================================================================
# A solicitação: gravar, ler e contar
# ============================================================================
def teste_registrar_e_ler_a_solicitacao(limpo):
    gravar("70")
    d = formularios.definicao(SLUG, so_ativo=False)
    nota = str(next(c for c in d["campos"]
                    if c["tipo"] == "list")["opcoes"][0]["value"])
    limpos = formularios.validar(d, {"CONTACT_NAME": "zz Teste",
                                     "CONTACT_LAST_NAME": "zz Clone",
                                     "DEAL_UF_CRM_DEAL_1649449139431": nota})
    r = formularios.registrar(d, limpos, ip="127.0.0.1")
    lida = formularios.uma(r["id"])
    assert lida["estado"] == "nova"
    # 🚨 A lista mostra o RÓTULO da opção, não o id do Bitrix.
    por_rotulo = {x["rotulo"]: x["valor"] for x in lida["respostas"]}
    assert por_rotulo["Primeiro Nome"] == "zz Teste"
    assert por_rotulo["Satisfação com atendimento recebido"] == "10"


def teste_valor_de_campo_que_saiu_da_definicao_continua_aparecendo(limpo):
    """⚠️ A solicitação é RETRATO. Campo que a definição perdeu aparece pela
    chave crua -- sumi-lo seria a tela mentir sobre o que a pessoa
    respondeu."""
    gravar("70")
    d = formularios.definicao(SLUG, so_ativo=False)
    r = formularios.registrar(d, {"CAMPO_QUE_NAO_EXISTE_MAIS": "zz resposta"})
    lida = formularios.uma(r["id"])
    fora = [x for x in lida["respostas"] if x.get("fora_da_definicao")]
    assert [x["valor"] for x in fora] == ["zz resposta"]


def teste_estado_e_contagem_de_novas(limpo):
    gravar("70")
    d = formularios.definicao(SLUG, so_ativo=False)
    r = formularios.registrar(d, {"CONTACT_NAME": "zz Teste"})
    antes = formularios.contar_novas()
    formularios.definir_estado(r["id"], "concluida", None)
    assert formularios.contar_novas() == antes - 1
    with pytest.raises(operacao.DadoInvalido):
        formularios.definir_estado(r["id"], "arquivada", None)


def teste_formulario_desligado_nao_existe_para_o_publico(limpo):
    """🚨 Os dois casos dão a MESMA resposta: um 404 que distingue "não existe"
    de "está desligado" conta ao mundo quais formulários a casa tem."""
    gravar("70")
    with pytest.raises(formularios.FormularioNaoExiste):
        formularios.definicao(SLUG)                 # so_ativo=True
    formularios.definicao(SLUG, so_ativo=False)     # o painel vê
    banco.executar("UPDATE formulario SET ativo = true WHERE codigo = %s", (CODIGO,))
    assert formularios.definicao(SLUG)["slug"] == SLUG


# ============================================================================
# As defesas do envio público
# ============================================================================
def teste_abertura_recusa_rapido_demais_e_token_falso():
    token = formularios.abertura()
    with pytest.raises(operacao.DadoInvalido):
        formularios.conferir_abertura(token)        # 0 s de preenchimento
    with pytest.raises(operacao.DadoInvalido):
        formularios.conferir_abertura("a1.inventado")
    with pytest.raises(operacao.DadoInvalido):
        formularios.conferir_abertura("")


def teste_abertura_velha_demais_e_recusada(monkeypatch):
    corpo = f"a{int(__import__('time').time()) - formularios.ABERTURA_VALE_SEG - 60}"
    with pytest.raises(operacao.DadoInvalido) as e:
        formularios.conferir_abertura(formularios._assinar(corpo))
    assert "muito tempo aberta" in str(e.value)


def teste_abertura_de_3_segundos_passa(monkeypatch):
    corpo = f"a{int(__import__('time').time()) - formularios.SEGUNDOS_MINIMOS - 1}"
    formularios.conferir_abertura(formularios._assinar(corpo))   # não levanta


def teste_desafio_confere_a_conta_e_nao_guarda_nada():
    d = formularios.novo_desafio()
    certa = sum(int(n) for n in __import__("re").findall(r"\d+", d["pergunta"]))
    formularios.conferir_desafio(d["token"], certa)       # não levanta
    formularios.conferir_desafio(d["token"], str(certa))  # texto também
    with pytest.raises(operacao.DadoInvalido):
        formularios.conferir_desafio(d["token"], certa + 1)
    with pytest.raises(operacao.DadoInvalido):
        formularios.conferir_desafio("d1:2.assinaturafalsa", 2)


def teste_desafio_so_aparece_depois_de_estourar(monkeypatch):
    """🔵 *"captcha no final pode se legal, mas tbm usam pelo cel então não
    pode virar entrave de processo"*: nos primeiros envios, nada."""
    contados = {"n": 0}
    monkeypatch.setattr(formularios, "desafio_sempre", lambda: False)
    monkeypatch.setattr(formularios.ratelimit, "quantos_eventos",
                        lambda chave, *a, **k: contados["n"])
    assert formularios.exige_desafio("203.0.113.9") is False
    contados["n"] = formularios.ENVIOS_ANTES_DO_DESAFIO
    assert formularios.exige_desafio("203.0.113.9") is True


def teste_contador_fora_do_ar_nao_exige_desafio(monkeypatch):
    """⚠️ Na dúvida, NÃO exige: o banco de contagem fora do ar não pode
    impedir um cliente de pedir suporte."""
    monkeypatch.setattr(formularios, "desafio_sempre", lambda: False)
    monkeypatch.setattr(formularios.ratelimit, "quantos_eventos",
                        lambda *a, **k: 0)
    assert formularios.exige_desafio("203.0.113.9") is False
