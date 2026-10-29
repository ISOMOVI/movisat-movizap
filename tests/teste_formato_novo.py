"""O FORMATO NOVO do formulário público — etapas, máscaras e identidade (29/10).

🔵 Pedido dele: *"ele ainda não passou por aqueles ajustes de UX/UI e
customização, certo? igual outros, ajuste ele no novo formato 'etapas, logo,
cor, placas, etc'"* -- sobre o Suporte. O desenho é o de 23/10
(`Desktop\\Formularios_Movisat_Design.md`, blocos 1, 3, 5 e 6).

🚨 O QUE ESTE ARQUIVO PROVA, E POR QUE CADA UM IMPORTA:

  1. a definição carrega `formato`, `etapas` e a `validacao` de cada campo;
  2. a rota pública TRADUZ as etapas de `nosso_nome` para o nome de origem --
     e continua não vazando `nosso_nome`, que é nome interno;
  3. etapa que cita campo inexistente PARA NA CARGA;
  4. 🚨 **pergunta que ficou fora de toda etapa PARA NA CARGA** -- é o defeito
     perigoso desta frente: o cliente nunca veria a pergunta, e o formulário
     continuaria "funcionando" com uma a menos;
  5. máscara citando campo inexistente para na carga;
  6. os outros 14 continuam `classico`, com etapas nulas;
  7. 🚨 **CPF MASCARADO É RECUSADO PELO SERVIDOR** -- é o que obriga a tela a
     gravar o valor limpo, e o motivo de `validacao_campo.limpar` existir;
  8. campo múltiplo aceita LISTA e aceita valor único -- os dois formatos, que
     é o que o repetidor exige de quem lê.

🚨 ESCREVE EM TABELAS DE PRODUÇÃO, como o resto da suíte: o formulário de
teste tem código `ZZ_TESTE_FORMATO` e é apagado no fim.

⚠️ NÃO TOCA NA `config` nem no contador real do `ratelimit` -- as duas lições
de 19/10 e de 22/10.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, formularios, main  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

RAIZ = Path("/home/claude/movizap_painel")
MAPA = json.loads((RAIZ / "dados" / "formularios_bitrix" / "mapa_bruto.json")
                  .read_text(encoding="utf-8"))

CODIGO = "ZZ_TESTE_FORMATO"
SLUG = "zz-teste-formato"
# O 32 é o Suporte -- o mesmo bruto que a carga usa, para as etapas de teste
# serem as de verdade.
BRUTO = MAPA["32"]

ETAPAS = [
    {"titulo": "Contrato",
     "campos": ["contrato-pessoa-fisica-ou-juridica", "empresa", "cnpj", "cpf"]},
    {"titulo": "Seus dados",
     "campos": ["primeiro-nome", "sobrenome", "e-mail", "telefone"]},
    {"titulo": "A solicitacao",
     "campos": ["tipo-de-solicitacao", "assunto", "detalhe-a-ocorrencia"]},
    {"titulo": "Veiculos e anexos",
     "campos": ["veiculo-e-placa-somente-se-for-referente",
                "arquivo-ou-print-caso-desejar"]},
]
VALIDACOES = {
    "cnpj": "cnpj", "cpf": "cpf", "e-mail": "email", "telefone": "telefone",
    "veiculo-e-placa-somente-se-for-referente": "placa",
}


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield


def apagar():
    banco.executar(
        """DELETE FROM formulario_solicitacao
            WHERE formulario_id IN (SELECT id FROM formulario WHERE codigo = %s)""",
        (CODIGO,))
    banco.executar("DELETE FROM formulario WHERE codigo = %s", (CODIGO,))


def gravar(**extra):
    return formularios.gravar_definicao(
        BRUTO, codigo=CODIGO, slug=SLUG, setor="Teste",
        titulo="zz Teste de formato", painel="operacao", **extra)


@pytest.fixture
def novo():
    apagar()
    gravar(formato="novo", etapas=ETAPAS, validacoes=VALIDACOES)
    yield formularios.definicao(SLUG, so_ativo=False)
    apagar()


# ---------------------------------------------------------------------------
# 1 e 2 -- a definição e o que a internet recebe
# ---------------------------------------------------------------------------
def test_definicao_traz_formato_etapas_e_validacao(novo):
    assert novo["formato"] == "novo"
    assert [e["titulo"] for e in novo["etapas"]] == [
        "Contrato", "Seus dados", "A solicitacao", "Veiculos e anexos"]
    por_nosso = {c["nosso_nome"]: c for c in novo["campos"]}
    assert por_nosso["cnpj"]["validacao"] == "cnpj"
    assert por_nosso["veiculo-e-placa-somente-se-for-referente"]["validacao"] == "placa"
    # ⚠️ Campo sem máscara fica NULO, e isso é o normal.
    assert por_nosso["assunto"]["validacao"] is None


def test_rota_publica_traduz_as_etapas_e_nao_vaza_nome_interno(novo):
    publico = main._publico_do_formulario(novo, ip=None)

    assert publico["formato"] == "novo"
    # 🚨 A TRADUÇÃO: a etapa é escrita em `nosso_nome` e sai em nome de origem,
    # porque é por `nome` que a tela casa o campo.
    de_nosso = {c["nosso_nome"]: c["nome"] for c in novo["campos"]}
    assert publico["etapas"][0]["campos"][0] == de_nosso[
        "contrato-pessoa-fisica-ou-juridica"]
    assert publico["etapas"][0]["campos"][0].startswith("CONTACT_UF_CRM")

    # 🚨 `nosso_nome` continua fora do corpo público -- é nome interno.
    assert all("nosso_nome" not in c for c in publico["campos"])
    assert "nosso_nome" not in json.dumps(publico, default=str)

    # Toda pergunta aparece em exatamente uma etapa.
    citados = [n for e in publico["etapas"] for n in e["campos"]]
    perguntas = [c["nome"] for c in publico["campos"]
                 if c["tipo"] not in formularios.TIPOS_DECORATIVOS]
    assert sorted(citados) == sorted(perguntas)
    assert len(citados) == len(set(citados))

    # A máscara vai junto, porque é a tela que a aplica.
    por_nome = {c["nome"]: c for c in publico["campos"]}
    assert por_nome[de_nosso["cpf"]]["validacao"] == "cpf"


# ---------------------------------------------------------------------------
# 3, 4 e 5 -- a carga recusa o que a tela não poderia mostrar
# ---------------------------------------------------------------------------
def test_etapa_citando_campo_que_nao_existe_para_na_carga():
    apagar()
    erradas = [dict(e) for e in ETAPAS]
    erradas[0] = {"titulo": "Contrato",
                  "campos": erradas[0]["campos"] + ["campo-que-nao-existe"]}
    with pytest.raises(DadoInvalido) as e:
        gravar(formato="novo", etapas=erradas)
    assert "campo-que-nao-existe" in str(e.value)
    apagar()


def test_pergunta_fora_de_toda_etapa_para_na_carga():
    """🚨 O defeito perigoso: a pergunta simplesmente não apareceria, e o
    formulário seguiria aceitando envio -- com uma pergunta a menos e ninguém
    sabendo."""
    apagar()
    sem_a_ultima = [dict(e) for e in ETAPAS[:-1]]
    with pytest.raises(DadoInvalido) as e:
        gravar(formato="novo", etapas=sem_a_ultima)
    assert "fora de toda etapa" in str(e.value)
    apagar()


def test_mascara_citando_campo_que_nao_existe_para_na_carga():
    apagar()
    with pytest.raises(DadoInvalido) as e:
        gravar(formato="novo", etapas=ETAPAS,
               validacoes={**VALIDACOES, "cnpj-errado": "cnpj"})
    assert "cnpj-errado" in str(e.value)
    apagar()


# ---------------------------------------------------------------------------
# 6 -- os outros continuam como estavam
# ---------------------------------------------------------------------------
def test_o_padrao_e_classico_e_sem_etapas():
    apagar()
    gravar()
    d = formularios.definicao(SLUG, so_ativo=False)
    assert d["formato"] == "classico"
    assert d["etapas"] is None
    assert all(c["validacao"] is None for c in d["campos"])
    # E a rota pública devolve `etapas: None`, que é o que faz a tela desenhar
    # o rolo único de sempre.
    assert main._publico_do_formulario(d, ip=None)["etapas"] is None
    apagar()


def test_os_quinze_de_producao_so_tem_o_suporte_em_novo():
    """🚨 Interruptor nasce desligado. Se este teste ficar vermelho, alguém
    ligou o formato novo em outro formulário -- e isso é decisão DELE, não
    efeito colateral de uma carga."""
    linhas = banco.varios(
        "SELECT codigo, formato FROM formulario WHERE codigo <> %s", (CODIGO,))
    novos = sorted(l["codigo"] for l in linhas if l["formato"] == "novo")
    assert novos == ["SUPORTE"]


# ---------------------------------------------------------------------------
# 7 e 8 -- o que o servidor aceita, que é quem manda
# ---------------------------------------------------------------------------
def test_documento_colado_em_qualquer_formato_e_canonizado(novo):
    """🚨 ESTE TESTE MUDOU DE LADO EM 29/10, E O MOTIVO É UM ACHADO DELE.

    A primeira versão provava que o servidor **recusava** CPF mascarado --
    porque o campo é `double` no Bitrix e `float("111.444.777-35")` estoura.
    Então ele colou `WQ0P6GLD000108`, o CNPJ **alfanumérico** da Pastelaria
    Velasco que está na nossa própria base, e a mesma regra o recusaria: um
    CNPJ válido respondendo *"informe um número"*.

    🔵 Decisão dele: *"deve permitir todos os formatos para CNPJ bem como
    alfanuméricos"* e *"podem colar somente numero ou . e - e / tbm"*.

    Agora a `validacao` do campo manda mais que o `tipo`, e o servidor
    **canoniza** em vez de recusar: sem pontuação, em maiúscula. O que ele
    ainda garante é o FORMATO (quantos caracteres) -- o dígito verificador é
    frase na tela, e mudar isso é régua, decisão dele.
    """
    de_nosso = {c["nosso_nome"]: c["nome"] for c in novo["campos"]}
    pf = {
        de_nosso["contrato-pessoa-fisica-ou-juridica"]: "1754",  # Pessoa Física
        de_nosso["primeiro-nome"]: "Iago",
        de_nosso["sobrenome"]: "Teste",
        de_nosso["e-mail"]: "iago@movisat.com.br",
        de_nosso["telefone"]: "18998116168",
        de_nosso["tipo-de-solicitacao"]: "1348",  # Problema de software
        de_nosso["assunto"]: "zz teste de formato",
        de_nosso["detalhe-a-ocorrencia"]: "zz teste de formato",
    }

    # CPF, nas duas escritas, guarda a mesma coisa.
    for escrito in ("111.444.777-35", "11144477735"):
        limpo = formularios.validar(novo, {**pf, de_nosso["cpf"]: escrito})
        assert limpo[de_nosso["cpf"]] == "11144477735"

    # 🚨 E O CNPJ ALFANUMÉRICO, que é o caso que ele achou. ⚠️ Vai como Pessoa
    # Jurídica (1756), porque é a regra do próprio formulário que mostra o
    # campo CNPJ -- em PF ele some, e campo escondido não entra no registro.
    pj = {**pf, de_nosso["contrato-pessoa-fisica-ou-juridica"]: "1756",
          de_nosso["empresa"]: "Velasco Leite Pastelaria ME"}
    pj.pop(de_nosso["cpf"], None)
    for escrito in ("WQ0P6GLD000108", "WQ.0P6.GLD/0001-08", "wq0p6gld000108",
                    "WQ 0P6 GLD 0001-08"):
        limpo = formularios.validar(novo, {**pj, de_nosso["cnpj"]: escrito})
        assert limpo[de_nosso["cnpj"]] == "WQ0P6GLD000108"

    # E o numérico de sempre continua valendo.
    limpo = formularios.validar(
        novo, {**pj, de_nosso["cnpj"]: "12.345.678/0001-95"})
    assert limpo[de_nosso["cnpj"]] == "12345678000195"

    # ⚠️ O que o servidor AINDA recusa é o formato: documento incompleto.
    with pytest.raises(DadoInvalido) as e:
        formularios.validar(novo, {**pj, de_nosso["cnpj"]: "WQ0P6GLD0001"})
    assert "14 caracteres" in str(e.value)


def test_campo_multiplo_aceita_lista_e_valor_unico(novo):
    """🚨 O repetidor muda o FORMATO do que é gravado: um valor vira lista. Quem
    lê precisa aceitar os dois, porque as solicitações antigas continuam com
    valor único -- e é por isso que o `+` entra agora, com 1 solicitação na
    base, e não em um mês."""
    de_nosso = {c["nosso_nome"]: c["nome"] for c in novo["campos"]}
    placa = de_nosso["veiculo-e-placa-somente-se-for-referente"]
    base = {
        de_nosso["contrato-pessoa-fisica-ou-juridica"]: "1754",
        de_nosso["cpf"]: "11144477735",
        de_nosso["primeiro-nome"]: "Iago",
        de_nosso["sobrenome"]: "Teste",
        de_nosso["e-mail"]: "iago@movisat.com.br",
        de_nosso["telefone"]: "18998116168",
        de_nosso["tipo-de-solicitacao"]: "1348",
        de_nosso["assunto"]: "zz teste de formato",
        de_nosso["detalhe-a-ocorrencia"]: "zz teste de formato",
    }

    varias = formularios.validar(novo, {**base, placa: ["ABC1234", "ABC1D23"]})
    assert varias[placa] == ["ABC1234", "ABC1D23"]

    uma = formularios.validar(novo, {**base, placa: "ABC1234"})
    assert uma[placa] == "ABC1234"

    # ⚠️ Linha vazia do repetidor NÃO vira valor: quem clicou no `+` e desistiu
    # não deixa um item em branco na lista.
    com_vazia = formularios.validar(novo, {**base, placa: ["ABC1234", "", "  "]})
    assert com_vazia[placa] == ["ABC1234"]


# ---------------------------------------------------------------------------
# A busca de cliente pelo documento (29/10) -- 🔵 pedido dele
# ---------------------------------------------------------------------------
# ⚠️ Todos passam `ip=None`: com IP a função escreve no contador do
# `ratelimit`, que é um SQLite de PRODUÇÃO e sobrevive ao processo. Foi um
# contador compartilhado que fez esta suíte passar na 1ª rodada e reprovar na
# 2ª em 22/10. O teto por IP tem teste próprio, e é o único que usa IP -- com
# uma chave que não é de ninguém.
def test_busca_exige_documento_completo():
    for ruim in ("", "123", "12.345.678/0001", "abc"):
        with pytest.raises(DadoInvalido):
            formularios.cliente_por_documento(ruim, ip=None)


def test_busca_acha_pelo_documento_com_e_sem_mascara():
    linha = banco.um(
        """SELECT documento, nome FROM cliente
            WHERE documento ~ '^[0-9]{14}$' AND documento <> repeat('0', 14)
            ORDER BY id LIMIT 1""")
    assert linha, "a base de clientes nao tem CNPJ numerico -- teste sem base"
    d = linha["documento"]
    mascarado = f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"

    for forma in (d, mascarado):
        r = formularios.cliente_por_documento(forma, ip=None)
        assert r["achou"] is True
        assert r["nome"] == linha["nome"]
    # 🚨 Só o nome e a frota saem. Documento, `harmonit_id` e e-mail não.
    # ⚠️ `placas` entrou em 29/10 (pedido dele) e `placas_erro` só aparece
    # quando a ponte do FPSL falha -- por isso o conjunto é testado contra o
    # que PODE existir, nunca contra campo a mais.
    chaves = set(formularios.cliente_por_documento(d, ip=None))
    assert chaves <= {"achou", "nome", "varios", "placas", "placas_erro"}
    assert {"achou", "nome", "varios"} <= chaves


def test_busca_nao_casa_com_o_documento_de_fachada():
    """🚨 8 dos 960 clientes têm 14 zeros no documento -- é preenchimento de
    fachada da base, não CNPJ. Sem a guarda, quem digitasse zeros receberia o
    nome de uma empresa de verdade."""
    assert formularios.cliente_por_documento("0" * 14, ip=None) == {"achou": False}
    assert formularios.cliente_por_documento("0" * 11, ip=None) == {"achou": False}


def test_nao_achar_nao_e_erro():
    """⚠️ A maior parte de quem preenche o formulário público ainda não é
    cliente. Responder erro ali seria mentira."""
    r = formularios.cliente_por_documento("99999999999999", ip=None)
    assert r == {"achou": False}


def test_busca_tem_teto_por_hora():
    """🚨 A rota é pública: sem teto, ela é um oráculo de 'este CNPJ é
    cliente?' para qualquer um na internet.

    ⚠️ Usa uma chave de IP que não é de ninguém e a apaga no fim -- o contador
    dos IPs reais é de produção.
    """
    import sqlite3
    from movizap import ratelimit

    ip = "203.0.113.77"   # TEST-NET-3, reservado para documentação
    chave = f"busca|{ip}"

    def zerar():
        try:
            with sqlite3.connect(ratelimit.ARQUIVO) as conn:
                conn.execute("DELETE FROM eventos WHERE chave = ?", (chave,))
        except sqlite3.Error:
            pass

    zerar()
    try:
        for _ in range(formularios.BUSCAS_POR_HORA):
            formularios.cliente_por_documento("99999999999999", ip=ip)
        with pytest.raises(DadoInvalido) as e:
            formularios.cliente_por_documento("99999999999999", ip=ip)
        assert "Muitas consultas" in str(e.value)
    finally:
        zerar()


def test_rota_da_busca_exige_o_carimbo_de_abertura():
    """⚠️ Quem chama por fora da nossa página é exatamente quem não queremos
    consultando a base -- e sem o carimbo a resposta é recusa, não dado.

    🚨 USA O `suporte` DE VERDADE, não o formulário de teste: a rota lê a
    definição com `so_ativo=True`, e o de teste nasce desligado -- ele daria
    404 e o teste passaria pelo motivo errado. Nada é escrito aqui.

    ⚠️ O `with TestClient` roda o ciclo de vida do app, que FECHA o pool no
    fim. Por isso o pool é reaberto depois: sem isso, todo teste seguinte
    deste arquivo morre com "banco não foi aberto".
    """
    from fastapi.testclient import TestClient

    try:
        with TestClient(main.app) as c:
            r = c.post("/api/publico/formulario/suporte/cliente",
                       data={"documento": "99999999999999", "abertura": ""})
            assert r.status_code == 400
            assert "Recarregue" in r.json()["detail"]

            # E formulário que não existe responde 404 igual ao resto.
            r = c.post("/api/publico/formulario/nao-existe/cliente",
                       data={"documento": "99999999999999", "abertura": ""})
            assert r.status_code == 404
    finally:
        banco.abrir()


# ---------------------------------------------------------------------------
# Os AJUSTES nossos em cima da definição do Bitrix (29/10) -- 🔵 pedidos dele
# ---------------------------------------------------------------------------
AJUSTES = {
    "fora": ["sobrenome", "assunto"],
    "campos": {
        "primeiro-nome": {"rotulo": "Nome completo"},
        "telefone": {"fantasma": "(00) 123456789"},
        "tipo-de-solicitacao": {"opcoes": [
            {"value": "backup", "label": "Acesso ao Backup de dados"},
            {"value": "veiculo", "label": "Problemas com o veículo"},
        ]},
        "detalhe-a-ocorrencia": {"linhas": 6},
        "veiculo-e-placa-somente-se-for-referente": {
            "rotulo": "Veículo e placa", "fonte": "weso_placas"},
    },
}
ETAPAS_AJUSTADAS = [
    {"titulo": "Contrato",
     "campos": ["contrato-pessoa-fisica-ou-juridica", "empresa", "cnpj", "cpf"]},
    {"titulo": "Seus dados", "campos": ["primeiro-nome", "e-mail", "telefone"]},
    {"titulo": "A solicitacao",
     "campos": ["tipo-de-solicitacao", "detalhe-a-ocorrencia"]},
    {"titulo": "Veiculos e anexos",
     "campos": ["veiculo-e-placa-somente-se-for-referente",
                "arquivo-ou-print-caso-desejar"]},
]


@pytest.fixture
def ajustado():
    apagar()
    gravar(formato="novo", etapas=ETAPAS_AJUSTADAS, validacoes=VALIDACOES,
           ajustes=AJUSTES)
    yield formularios.definicao(SLUG, so_ativo=False)
    apagar()


def test_campo_tirado_deixa_de_existir(ajustado):
    """🔵 *"na aba 2, somente 1 caixa para o nome já serve"* e *"o assunto já é
    o próprio tipo de solicitação"*.

    🚨 TIRADO NÃO É ESCONDIDO: o campo não vem na definição, não aparece na
    tela e não entra no registro. Quem some por regra condicional é outra
    coisa, e continua existindo.
    """
    nossos = {c["nosso_nome"] for c in ajustado["campos"]}
    assert "sobrenome" not in nossos
    assert "assunto" not in nossos
    assert len(ajustado["campos"]) == 11   # eram 13


def test_rotulo_trocado_nao_renomeia_o_campo(ajustado):
    """🚨 A ARMADILHA DESTA FRENTE, e ela é silenciosa: o `nosso_nome` é
    DERIVADO do rótulo. Se o ajuste trocasse o rótulo antes de o nome ser
    calculado, "Primeiro Nome" viraria `nome-completo` -- e as tabelas `ETAPAS`
    e `VALIDACOES`, que citam `primeiro-nome`, apontariam para um campo que não
    existe mais."""
    por_nosso = {c["nosso_nome"]: c for c in ajustado["campos"]}
    assert "primeiro-nome" in por_nosso
    assert por_nosso["primeiro-nome"]["rotulo"] == "Nome completo"


def test_opcoes_rotulo_fantasma_altura_e_fonte_entram(ajustado):
    por_nosso = {c["nosso_nome"]: c for c in ajustado["campos"]}

    # 🔵 As opções passam a ser NOSSAS -- as do Bitrix (1340, 1342...) eram ids
    # da base deles.
    valores = [o["value"] for o in por_nosso["tipo-de-solicitacao"]["opcoes"]]
    assert valores == ["backup", "veiculo"]

    assert por_nosso["telefone"]["fantasma"] == "(00) 123456789"
    assert por_nosso["detalhe-a-ocorrencia"]["linhas"] == 6
    assert por_nosso["veiculo-e-placa-somente-se-for-referente"]["fonte"] == "weso_placas"

    # E saem na rota pública, que é quem desenha.
    publico = main._publico_do_formulario(ajustado, ip=None)
    por_nome = {c["nome"]: c for c in publico["campos"]}
    assert por_nome[por_nosso["telefone"]["nome"]]["fantasma"] == "(00) 123456789"
    assert por_nome[por_nosso["detalhe-a-ocorrencia"]["nome"]]["linhas"] == 6


def test_a_opcao_velha_do_bitrix_passa_a_ser_recusada(ajustado):
    """🚨 Trocar a lista é trocar o que o servidor ACEITA. `1348` era "Problema
    de software" no Bitrix e não existe mais -- um link antigo, ou um POST
    guardado, tem de ser recusado, não gravado com valor morto."""
    de_nosso = {c["nosso_nome"]: c["nome"] for c in ajustado["campos"]}
    base = {
        de_nosso["contrato-pessoa-fisica-ou-juridica"]: "1754",
        de_nosso["cpf"]: "11144477735",
        de_nosso["primeiro-nome"]: "Iago Teste",
        de_nosso["e-mail"]: "iago@movisat.com.br",
        de_nosso["telefone"]: "18998116168",
        de_nosso["detalhe-a-ocorrencia"]: "zz teste",
    }
    with pytest.raises(DadoInvalido):
        formularios.validar(
            ajustado, {**base, de_nosso["tipo-de-solicitacao"]: "1348"})

    limpo = formularios.validar(
        ajustado, {**base, de_nosso["tipo-de-solicitacao"]: "backup"})
    assert limpo[de_nosso["tipo-de-solicitacao"]] == "backup"


def test_ajuste_citando_campo_que_nao_existe_para_na_carga():
    apagar()
    with pytest.raises(DadoInvalido) as e:
        gravar(formato="novo", etapas=ETAPAS_AJUSTADAS,
               ajustes={"fora": ["campo-que-nao-existe"]})
    assert "campo-que-nao-existe" in str(e.value)
    apagar()


def test_os_ajustes_de_producao_estao_no_suporte():
    """⚠️ Lê o SUPORTE de verdade: é ele que ele vai abrir no navegador.

    🔵 As 4 opções dele, em ordem alfabética (*"só coloque em ordem
    alfabética"*).
    """
    d = formularios.definicao("suporte")
    por_nosso = {c["nosso_nome"]: c for c in d["campos"]}

    assert "sobrenome" not in por_nosso and "assunto" not in por_nosso
    assert por_nosso["primeiro-nome"]["rotulo"] == "Nome completo"
    assert por_nosso["telefone"]["fantasma"] == "(00) 123456789"
    assert por_nosso["detalhe-a-ocorrencia"]["linhas"] == 6
    assert por_nosso["veiculo-e-placa-somente-se-for-referente"]["fonte"] == "weso_placas"

    rotulos = [o["label"] for o in por_nosso["tipo-de-solicitacao"]["opcoes"]]
    assert rotulos == [
        "Acesso ao Backup de dados",
        "Problemas com o veículo",
        "Problemas com rastreamento",
        "Sugestão de melhoria",
    ]
    # 🚨 A prova da ordem alfabética é a própria ordenação, não a minha palavra
    # de que digitei na ordem.
    assert rotulos == sorted(rotulos, key=lambda s: s.lower())


# ---------------------------------------------------------------------------
# A frota do cliente (29/10)
# ---------------------------------------------------------------------------
def test_a_ponte_das_placas_responde_e_cruza_as_duas_bases():
    """🚨 SÃO DUAS BASES: o Harmonit diz DE QUEM é a placa (`clienteId`) e a
    WESO diz que ela está ATIVA (tem rastreador) e dá o APELIDO. Nenhuma
    responde sozinha -- a WESO não tem `cliente_id`.

    ⚠️ Se o FPSL estiver fora do ar, este teste é PULADO em vez de reprovar: a
    ponte é outro serviço, e suíte vermelha por serviço vizinho parado ensina a
    ignorar vermelho.
    """
    from movizap import fpsl_ponte

    if not fpsl_ponte.configurada():
        pytest.skip("ponte do FPSL nao configurada neste ambiente")
    try:
        placas = fpsl_ponte.placas_ativas("886302")   # MOTO HELP, 77 ativas
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"FPSL fora do ar: {e}")

    assert placas, "o cliente 886302 tinha 77 placas ativas em 29/10"
    uma = placas[0]
    assert set(uma) == {"placa", "apelido", "veiculo"}
    assert uma["placa"] == uma["placa"].strip().upper()


def test_a_busca_devolve_as_placas_e_nao_o_id_interno():
    """🚨 `harmonit_id` NÃO SAI na resposta -- é id interno. O que sai são as
    placas, e a chave `placas` existe sempre que o cliente foi achado."""
    linha = banco.um(
        """SELECT documento FROM cliente
            WHERE harmonit_id = '886302' AND documento IS NOT NULL""")
    if not linha:
        pytest.skip("o cliente 886302 nao tem documento nesta base")
    r = formularios.cliente_por_documento(linha["documento"], ip=None)
    assert r["achou"] is True
    assert "harmonit_id" not in r
    assert "placas" in r


# ---------------------------------------------------------------------------
# A REGRA DA PLACA (29/10) — 🔵 *"só é possível abrir chamados para placas
# ativas na weso. o match é basicamente de 100% mesmo. essa é a regra"*
# ---------------------------------------------------------------------------
# 🚨 E UM ERRO MEU DE MÉTODO, registrado aqui porque é o que estes testes
# impedem de voltar: eu havia escrito que a lista "sugere, nunca restringe" --
# ninguém me disse isso. Inferi de uma medição minha e tratei a inferência como
# decisão. A regra do negócio é dele.
def _campo_de_placa(d):
    for c in d["campos"]:
        if c.get("fonte") == "weso_placas":
            return c["nome"]
    raise AssertionError("o formulario de teste perdeu o campo de placa")


def test_sem_placa_informada_a_regra_nao_se_aplica(ajustado):
    """⚠️ `None` não é "passou": é "não havia o que conferir". O campo de placa
    é opcional, e chamado sem veículo existe (dúvida de usabilidade, sugestão
    de melhoria)."""
    assert formularios.conferir_regra_da_placa(ajustado, {}) is None
    placa = _campo_de_placa(ajustado)
    assert formularios.conferir_regra_da_placa(ajustado, {placa: ""}) is None
    assert formularios.conferir_regra_da_placa(ajustado, {placa: ["", "  "]}) is None


def test_placas_informadas_le_lista_e_valor_unico(ajustado):
    placa = _campo_de_placa(ajustado)
    assert formularios.placas_informadas(ajustado, {placa: "ABC1234"}) == ["ABC1234"]
    assert formularios.placas_informadas(
        ajustado, {placa: ["ABC1234", "", "XYZ1D23"]}) == ["ABC1234", "XYZ1D23"]


def test_placa_sem_rastreador_ativo_e_recusada(ajustado, monkeypatch):
    """🔵 A regra dele. ⚠️ A frase DIZ O QUE FAZER -- "placa não permitida"
    deixaria a pessoa sem saída: ela não sabe o que é a WESO nem consegue
    consertar o cadastro sozinha."""
    placa = _campo_de_placa(ajustado)
    monkeypatch.setattr(
        formularios.fpsl_ponte, "conferir_placas",
        lambda placas: {p: {"ativa": False, "apelido": None} for p in placas})

    with pytest.raises(DadoInvalido) as e:
        formularios.conferir_regra_da_placa(ajustado, {placa: "ZZZ9999"})
    frase = str(e.value)
    assert "rastreador ativo" in frase
    assert "ZZZ9999" in frase          # diz QUAL placa
    assert "WhatsApp" in frase         # e diz o que fazer


def test_uma_placa_inativa_no_meio_de_boas_recusa_o_envio(ajustado, monkeypatch):
    """🚨 Não se grava "o que deu": o chamado é um só, e aceitar metade das
    placas em silêncio faria a pessoa achar que pediu para três veículos."""
    placa = _campo_de_placa(ajustado)
    monkeypatch.setattr(
        formularios.fpsl_ponte, "conferir_placas",
        lambda placas: {p: {"ativa": p != "ZZZ9999"} for p in placas})

    with pytest.raises(DadoInvalido) as e:
        formularios.conferir_regra_da_placa(
            ajustado, {placa: ["BYL2170", "ZZZ9999"]})
    assert "ZZZ9999" in str(e.value)
    assert "BYL2170" not in str(e.value)


def test_placa_ativa_passa_e_fica_marcada_como_conferida(ajustado, monkeypatch):
    placa = _campo_de_placa(ajustado)
    monkeypatch.setattr(
        formularios.fpsl_ponte, "conferir_placas",
        lambda placas: {p: {"ativa": True, "apelido": "SAVEIRO"} for p in placas})
    assert formularios.conferir_regra_da_placa(
        ajustado, {placa: "BYL2170"}) is True


def test_ponte_fora_do_ar_deixa_passar_marcado(ajustado, monkeypatch):
    """🚨 A decisão que esta casa toma quando a culpa é nossa: o chamado passa,
    e o rastro fica (`placas_conferidas = false`, migração 081).

    Recusar por indisponibilidade NOSSA transformaria o nosso problema no
    problema do cliente -- e ele não tem como consertar.
    """
    placa = _campo_de_placa(ajustado)

    def caiu(placas):
        raise formularios.fpsl_ponte.FpslIndisponivel("ponte fora do ar")

    monkeypatch.setattr(formularios.fpsl_ponte, "conferir_placas", caiu)
    assert formularios.conferir_regra_da_placa(
        ajustado, {placa: "BYL2170"}) is False


def test_a_conferencia_pergunta_so_a_weso():
    """🚨 QUEM DIZ "ATIVA" É A WESO SOZINHA, e isso é o ponto da rota nova.

    A outra rota (`/placas-ativas`) cruza WESO x Harmonit para saber **de
    quem** é a placa. Exigir o Harmonit TAMBÉM aqui recusaria as **30 placas**
    (medido em 29/10) que estão ativas na WESO e não estão no cadastro do
    Harmonit -- e pela regra dele essas podem abrir chamado.

    ⚠️ Pulado se o FPSL estiver fora do ar: a ponte é outro serviço, e suíte
    vermelha por serviço vizinho parado ensina a ignorar vermelho.
    """
    from movizap import fpsl_ponte

    if not fpsl_ponte.configurada():
        pytest.skip("ponte do FPSL nao configurada neste ambiente")
    try:
        r = fpsl_ponte.conferir_placas(
            ["AOY 4C94", "aoy-4c94", "SAVEIRO AOY4C94", "ZZZ9999"])
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"FPSL fora do ar: {e}")

    # 🚨 AOY 4C94 é uma das 30 órfãs: ativa na WESO, ausente no Harmonit.
    assert r["AOY 4C94"]["ativa"] is True
    # ⚠️ A chave é normalizada, e a placa é procurada DENTRO do texto -- o campo
    # pede "Veículo e Placa".
    assert r["aoy-4c94"]["ativa"] is True
    assert r["SAVEIRO AOY4C94"]["ativa"] is True
    assert r["ZZZ9999"]["ativa"] is False


def test_a_rota_publica_da_placa_nao_diz_de_quem_ela_e():
    """🚨 Devolve `{conferiu, ativa, apelido}` e nada mais. Dizer o cliente
    faria desta rota um jeito de descobrir o dono de qualquer placa."""
    from fastapi.testclient import TestClient

    try:
        with TestClient(main.app) as c:
            r = c.post("/api/publico/formulario/suporte/placa",
                       data={"placa": "ZZZ9999", "abertura": ""})
            # Sem carimbo de abertura é recusa, como no envio.
            assert r.status_code == 400
    finally:
        banco.abrir()
