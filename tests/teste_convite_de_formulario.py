"""O CONVITE de formulário — o link do chat que abre o formulário preenchido.

🔵 **Pedido dele, 11/11:** formulários *"pré-preenchidos quando abertos pelo
botão dentro do chat"*.

🚨 **O QUE ESTE ARQUIVO GUARDA, E É O PONTO DA FRENTE INTEIRA:**

  1. **dado de cliente NÃO vai na URL** — o que viaja é um bilhete opaco, e o
     link montado não contém o CNPJ, o telefone nem o nome;
  2. **a sugestão é por RÓTULO, não por tipo** — a `rescisao` tem dois campos
     `phone` e dois `email`, e os segundos são *"... do novo titular"*.
     Sugerir o telefone do cliente ali não é defeito de tela: é escrever a
     pessoa errada num termo;
  3. **abrir não gasta** o convite, e **vencido some**;
  4. **os valores são sugestão, nunca verdade** — o envio revalida tudo.

🚨 **ESCREVE EM TABELAS DE PRODUÇÃO**, como o resto da suíte: o formulário de
teste tem código `ZZ_TESTE_CONV`, a conversa sai num telefone de DDD
inexistente, e tudo é apagado no fim.
"""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import auth, banco, formularios, main  # noqa: E402
from movizap.config import settings  # noqa: E402

RAIZ = Path("/home/claude/movizap_painel")
MAPA = json.loads((RAIZ / "dados" / "formularios_bitrix" / "mapa_bruto.json")
                  .read_text(encoding="utf-8"))

CODIGO = "ZZ_TESTE_CONV"
SLUG = "zz-teste-conv"
FONE = "+559995557001"
EMPRESA = "Zz Teste Convite Empresa"
CNPJ = "12.345.678/0001-90"


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield


def _limpar():
    # 🚨 O `TestClient` com `with` roda o ciclo de vida da aplicacao e FECHA O
    # POOL na saida. Sem reabrir, a limpeza de depois do teste estoura com
    # *"banco nao foi aberto"* -- e o residuo fica no banco de producao.
    banco.abrir()
    banco.executar(
        """DELETE FROM formulario_convite
            WHERE slug = %s OR conversa_id IN
                  (SELECT id FROM conversa WHERE telefone_e164 = %s)""",
        (SLUG, FONE))
    banco.executar(
        """DELETE FROM formulario_solicitacao
            WHERE formulario_id IN (SELECT id FROM formulario WHERE codigo = %s)""",
        (CODIGO,))
    banco.executar("DELETE FROM formulario WHERE codigo = %s", (CODIGO,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (FONE,))
    banco.executar(
        """DELETE FROM contato WHERE cliente_id IN
                  (SELECT id FROM cliente WHERE nome = %s)""", (EMPRESA,))
    banco.executar("DELETE FROM cliente WHERE nome = %s", (EMPRESA,))


@pytest.fixture(autouse=True)
def limpo():
    _limpar()
    yield
    _limpar()


@pytest.fixture
def formulario():
    """📏 MEDIDO: o `MAPA["70"]` é a **pesquisa CES**, não o Suporte — tem
    *"Primeiro Nome"*, *"Sobrenome"* e *"Nome da Empresa"*, e **não** tem
    Telefone, E-mail nem CNPJ.

    ⚠️ Serve para o ciclo de vida do convite (criar, abrir, vencer,
    desligar), que não depende de rótulo. Quem exercita o MAPA DE RÓTULOS é a
    `TestSugestaoPorRotulo`, lendo os formulários de verdade."""
    formularios.gravar_definicao(MAPA["70"], codigo=CODIGO, slug=SLUG,
                                 setor="Teste", titulo="zz Teste de convite",
                                 painel="operacao")
    banco.executar("UPDATE formulario SET ativo = true WHERE codigo = %s",
                   (CODIGO,))
    return formularios.definicao(SLUG)


@pytest.fixture
def conversa():
    """Uma conversa com cliente PJ e contato, que é o caso cheio."""
    canal = banco.um("SELECT id FROM canal WHERE tipo = 'atendimento' "
                     "AND ativo LIMIT 1")
    if not canal:
        pytest.skip("nenhum canal de atendimento ativo")
    cli = banco.um(
        """INSERT INTO cliente (nome, nome_fantasia, documento, tipo_pessoa,
                                email, origem)
           VALUES (%s, %s, %s, 1, %s, 'movizap') RETURNING id""",
        (EMPRESA, EMPRESA, CNPJ, "empresa@teste.invalid"))
    ct = banco.um(
        """INSERT INTO contato (cliente_id, nome, email, origem)
           VALUES (%s, %s, %s, 'movizap') RETURNING id""",
        (cli["id"], "Maria Aparecida Souza", "maria@teste.invalid"))
    cv = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, contato_id)
           VALUES (%s, %s, 'nova', %s) RETURNING id""",
        (canal["id"], FONE, ct["id"]))
    return {"id": cv["id"], "cliente_id": cli["id"], "contato_id": ct["id"]}


@pytest.fixture
def cliente_http():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def token():
    return auth.criar_token(settings.admin_login)


def _rotulos(d):
    return {c["nome"]: c["rotulo"] for c in d["campos"]}


# ----------------------------------------------------- o que a conversa sabe

class TestFatosDaConversa:
    def test_junta_telefone_empresa_nome_email_e_CNPJ(self, conversa):
        f = formularios.fatos_da_conversa(conversa["id"])
        assert f["telefone"] == FONE
        assert f["empresa"] == EMPRESA
        assert f["nome_completo"] == "Maria Aparecida Souza"
        assert f["primeiro_nome"] == "Maria"
        assert f["sobrenome"] == "Aparecida Souza"
        assert f["email"] == "maria@teste.invalid"
        assert f["cnpj"] == CNPJ

    def test_PJ_nao_vira_CPF(self, conversa):
        """🚨 O documento é UM campo no cadastro e DOIS no formulário. Quem
        decide é o `tipo_pessoa`, **nunca o comprimento do texto** — cadastro
        com documento pela metade existe."""
        f = formularios.fatos_da_conversa(conversa["id"])
        assert "cpf" not in f

    def test_PF_vira_CPF_e_nao_CNPJ(self, conversa):
        banco.executar("UPDATE cliente SET tipo_pessoa = 2 WHERE id = %s",
                       (conversa["cliente_id"],))
        f = formularios.fatos_da_conversa(conversa["id"])
        assert f["cpf"] == CNPJ and "cnpj" not in f

    def test_tipo_pessoa_indefinido_NAO_sugere_documento(self, conversa):
        """⚠️ `0` e `3` (Estrangeiro) não sugerem documento nenhum: documento
        no campo errado é pior que campo vazio."""
        for tipo in (0, 3):
            banco.executar("UPDATE cliente SET tipo_pessoa = %s WHERE id = %s",
                           (tipo, conversa["cliente_id"]))
            f = formularios.fatos_da_conversa(conversa["id"])
            assert "cnpj" not in f and "cpf" not in f, tipo

    def test_conversa_sem_contato_devolve_so_o_que_existe(self):
        """⚠️ Conversa sem cadastro não é erro: é o caso comum de quem escreve
        pela primeira vez. Volta o telefone, e o nome do WhatsApp se houver."""
        canal = banco.um("SELECT id FROM canal WHERE tipo = 'atendimento' "
                         "AND ativo LIMIT 1")
        if not canal:
            pytest.skip("nenhum canal de atendimento ativo")
        cv = banco.um(
            """INSERT INTO conversa (canal_id, telefone_e164, estado,
                                     nome_whatsapp)
               VALUES (%s, %s, 'nova', %s) RETURNING id""",
            (canal["id"], FONE, "Zé do Posto"))
        f = formularios.fatos_da_conversa(cv["id"])
        assert f["telefone"] == FONE
        assert f["nome_completo"] == "Zé do Posto"
        assert "empresa" not in f and "cnpj" not in f

    def test_conversa_que_nao_existe_devolve_vazio(self):
        assert formularios.fatos_da_conversa(99999999) == {}


# ------------------------------------------------- a sugestão é por RÓTULO

# 🚨 AS TRAVAS DE RÓTULO LEEM OS FORMULÁRIOS DE VERDADE, e é de propósito:
# o mapa de sugestão existe por causa das armadilhas que **os formulários
# reais** têm (os dois `phone` da rescisão, os dois da ficha cadastral, o
# `double` que é CNPJ, CPF, RG e quantidade de veículos). Um formulário de
# mentira não tem nenhuma delas, e a trava mediria nada.
#
# ⚠️ São LEITURA: `valores_sugeridos` não escreve.
SUPORTE_LIDO = "suporte"


class TestSugestaoPorRotulo:
    def test_cada_fato_cai_no_campo_do_rotulo_certo(self):
        d = formularios.definicao(SUPORTE_LIDO)
        s = formularios.valores_sugeridos(SUPORTE_LIDO, {
            "telefone": FONE, "empresa": EMPRESA, "cnpj": CNPJ,
            "nome_completo": "Maria Aparecida Souza",
            "email": "maria@teste.invalid"})
        por_rotulo = {_rotulos(d)[n]: v for n, v in s.items()}
        assert por_rotulo["Telefone"] == FONE
        assert por_rotulo["Empresa"] == EMPRESA
        assert por_rotulo["CNPJ"] == CNPJ
        assert por_rotulo["Nome completo"] == "Maria Aparecida Souza"
        assert por_rotulo["E-mail"] == "maria@teste.invalid"

    def test_o_CPF_fica_VAZIO_quando_o_cliente_e_PJ(self):
        """⚠️ O Suporte tem CNPJ **e** CPF. Preencher os dois diria que a
        empresa também tem CPF."""
        d = formularios.definicao(SUPORTE_LIDO)
        s = formularios.valores_sugeridos(SUPORTE_LIDO, {"cnpj": CNPJ})
        assert {_rotulos(d)[n] for n in s} == {"CNPJ"}

    def test_RESCISAO_nao_sugere_nada_no_campo_do_NOVO_TITULAR(self):
        """🚨 A TRAVA QUE JUSTIFICA O DESENHO INTEIRO.

        A `rescisao` tem **dois** campos `phone` e **dois** `email`, e os
        segundos são *"Telefone com DDD do novo titular"* e *"E-mail do novo
        titular"*. Mapear por TIPO poria o telefone de quem está rescindindo
        no campo de quem vai assumir o contrato — e isso não é erro de tela, é
        a pessoa errada escrita num termo.
        """
        d = formularios.definicao("rescisao")
        s = formularios.valores_sugeridos(
            "rescisao", {"telefone": FONE, "email": "maria@teste.invalid"})
        rot = _rotulos(d)
        escritos = {rot[n] for n in s}
        assert "Telefone" in escritos
        assert "E-mail" in escritos
        for rotulo in escritos:
            assert "novo titular" not in rotulo.lower(), rotulo

    def test_FICHA_CADASTRAL_nao_poe_o_contato_como_quem_ASSINA(self):
        """⚠️ A ficha pede *"Nome completo do responsável em assinar o
        contrato"*, que **não** bate exato com *"Nome completo"*. Então ela
        nasce sem nome sugerido — e isso é o certo: quem fala no WhatsApp não
        é necessariamente quem assina."""
        d = formularios.definicao("ficha-cadastral")
        s = formularios.valores_sugeridos(
            "ficha-cadastral", {"nome_completo": "Maria Aparecida Souza"})
        rot = _rotulos(d)
        for rotulo in (rot[n] for n in s):
            assert "assinar" not in rotulo.lower(), rotulo

    def test_fato_vazio_nao_entra(self):
        s = formularios.valores_sugeridos(
            SUPORTE_LIDO, {"telefone": "", "empresa": None, "cnpj": "   "})
        assert s == {}

    def test_um_campo_recebe_UMA_sugestao(self):
        """⚠️ O Suporte tem *"Nome completo"* e **não** tem *"Primeiro
        Nome"*. O nome inteiro ganha, e o primeiro nome não entra em cima
        dele: um campo recebe uma sugestão."""
        d = formularios.definicao(SUPORTE_LIDO)
        s = formularios.valores_sugeridos(
            SUPORTE_LIDO, {"nome_completo": "Maria Aparecida Souza",
                           "primeiro_nome": "Maria"})
        assert [_rotulos(d)[n] for n in s] == ["Nome completo"]
        assert list(s.values()) == ["Maria Aparecida Souza"]

    def test_quem_so_tem_PRIMEIRO_NOME_recebe_o_primeiro(self):
        """📏 Medido: a `rescisao` pede *"Primeiro Nome"* e *"Sobrenome"*, e o
        Suporte pede *"Nome completo"*. O mesmo fato cai em campos diferentes,
        e é o rótulo que decide."""
        d = formularios.definicao("rescisao")
        s = formularios.valores_sugeridos(
            "rescisao", {"nome_completo": "Maria Aparecida Souza",
                         "primeiro_nome": "Maria",
                         "sobrenome": "Aparecida Souza"})
        por_rotulo = {_rotulos(d)[n]: v for n, v in s.items()}
        assert por_rotulo["Primeiro Nome"] == "Maria"
        assert por_rotulo["Sobrenome"] == "Aparecida Souza"


# -------------------------------------------------------- o convite em si

class TestOConvite:
    def test_o_LINK_nao_leva_dado_do_cliente(self, formulario, conversa):
        """🚨 A TRAVA DO DESENHO: o que viaja na URL é um bilhete opaco.

        Query string entra no `access.log` do nginx, no histórico do navegador
        de quem abriu, e em qualquer repasse do link por WhatsApp. Base64 não
        resolveria nada disso — esconde do olho, não do log.
        """
        fatos = formularios.fatos_da_conversa(conversa["id"])
        c = formularios.criar_convite(
            SLUG, formularios.valores_sugeridos(SLUG, fatos),
            conversa_id=conversa["id"])
        url = c["url"]
        assert c["bilhete"] in url
        for segredo in (CNPJ, FONE, EMPRESA, "maria@teste.invalid",
                        "Maria", "Souza", "12345678"):
            assert segredo not in url, segredo
        # ⚠️ E o bilhete não deriva de nada: não contém o id nem o slug.
        assert str(c["id"]) != c["bilhete"]

    def test_os_valores_chegam_pela_ROTA_e_nao_pelo_link(self, formulario,
                                                         conversa):
        fatos = formularios.fatos_da_conversa(conversa["id"])
        c = formularios.criar_convite(
            SLUG, formularios.valores_sugeridos(SLUG, fatos),
            conversa_id=conversa["id"])
        lido = formularios.convite(c["bilhete"])
        assert lido["slug"] == SLUG
        # 📏 O formulario de teste e a pesquisa CES: os rotulos que ele tem em
        # comum com o mapa de sugestao sao estes tres.
        rot = _rotulos(formulario)
        assert {rot[n] for n in lido["valores"]} == {"Nome da Empresa",
                                                     "Primeiro Nome",
                                                     "Sobrenome"}

    def test_abrir_NAO_gasta_o_convite(self, formulario, conversa):
        """🚨 Recarregar a página, perder a aba, voltar no dia seguinte:
        gastar no primeiro `GET` viraria *"o link não funciona mais"*."""
        c = formularios.criar_convite(SLUG, {}, conversa_id=conversa["id"])
        for _ in range(3):
            assert formularios.convite(c["bilhete"]) is not None
        linha = banco.um("SELECT aberturas, aberto_em FROM formulario_convite "
                         "WHERE id = %s", (c["id"],))
        assert linha["aberturas"] == 3
        assert linha["aberto_em"] is not None

    def test_VENCIDO_some_igual_a_inexistente(self, formulario, conversa):
        """⚠️ A mesma resposta de "não existe", de propósito: convite vencido
        não deve contar que existiu."""
        c = formularios.criar_convite(SLUG, {}, conversa_id=conversa["id"])
        banco.executar("UPDATE formulario_convite SET expira_em = now() "
                       "- interval '1 minute' WHERE id = %s", (c["id"],))
        assert formularios.convite(c["bilhete"]) is None

    def test_bilhete_vazio_ou_falso_devolve_None(self):
        for b in ("", "   ", None, "nao-existe-este-bilhete"):
            assert formularios.convite(b) is None

    def test_formulario_DESLIGADO_depois_do_convite_para_de_sugerir(
            self, formulario, conversa):
        """⚠️ O link deixa de pré-preencher, e a página dirá que não achou o
        formulário — o que é a verdade."""
        c = formularios.criar_convite(SLUG, {}, conversa_id=conversa["id"])
        banco.executar("UPDATE formulario SET ativo = false WHERE codigo = %s",
                       (CODIGO,))
        assert formularios.convite(c["bilhete"]) is None

    def test_convite_para_formulario_que_nao_existe_RECUSA(self):
        """🚨 Nasceria como um link que abre *"Formulário não encontrado"*, e
        quem recebeu acharia que a Movisat mandou link quebrado."""
        with pytest.raises(formularios.FormularioNaoExiste):
            formularios.criar_convite("zz-nao-existe", {})

    def test_campo_que_nao_existe_na_definicao_e_DESCARTADO(self, formulario):
        c = formularios.criar_convite(SLUG, {"CAMPO_INVENTADO": "x"})
        assert c["campos_sugeridos"] == 0
        assert formularios.convite(c["bilhete"])["valores"] == {}

    def test_campos_demais_recusa(self, formulario):
        from movizap.operacao import DadoInvalido
        nomes = [c["nome"] for c in formulario["campos"]]
        demais = {n: "x" for n in nomes}
        # ⚠️ O teto é 60 e o Suporte tem 11 campos: para exercitar o teto sem
        # inventar campo, baixo o teto no processo.
        antes = formularios.CONVITE_TETO_DE_VALORES
        formularios.CONVITE_TETO_DE_VALORES = 2
        try:
            with pytest.raises(DadoInvalido):
                formularios.criar_convite(SLUG, demais)
        finally:
            formularios.CONVITE_TETO_DE_VALORES = antes

    def test_a_lista_da_conversa_NAO_traz_os_valores(self, formulario,
                                                     conversa):
        """⚠️ Mostrar os valores poria a ficha do cliente numa lista."""
        formularios.criar_convite(SLUG, {"COMPANY_TITLE": EMPRESA},
                                  conversa_id=conversa["id"])
        lista = formularios.convites_da_conversa(conversa["id"])
        assert len(lista) == 1
        assert "valores" not in lista[0]
        assert lista[0]["slug"] == SLUG
        assert lista[0]["vencido"] is False


# ----------------------------------------------------------------- as rotas

class TestAsRotas:
    def test_a_rota_publica_devolve_os_valores(self, cliente_http,
                                               formulario, conversa):
        c = formularios.criar_convite(SLUG, {"COMPANY_TITLE": EMPRESA},
                                      conversa_id=conversa["id"])
        r = cliente_http.get(f"/api/publico/convite/{c['bilhete']}")
        assert r.status_code == 200, r.text
        assert r.json() == {"slug": SLUG, "valores": {"COMPANY_TITLE": EMPRESA}}

    def test_a_rota_publica_NAO_pede_login(self, cliente_http, formulario):
        """⚠️ É a página do cliente que a chama, e ela não tem sessão."""
        c = formularios.criar_convite(SLUG, {})
        r = cliente_http.get(f"/api/publico/convite/{c['bilhete']}")
        assert r.status_code == 200

    def test_bilhete_falso_404_com_a_MESMA_frase_do_vencido(self,
                                                            cliente_http,
                                                            formulario):
        c = formularios.criar_convite(SLUG, {})
        banco.executar("UPDATE formulario_convite SET expira_em = now() "
                       "- interval '1 minute' WHERE id = %s", (c["id"],))
        vencido = cliente_http.get(f"/api/publico/convite/{c['bilhete']}")
        falso = cliente_http.get("/api/publico/convite/nao-existe")
        assert vencido.status_code == falso.status_code == 404
        assert vencido.json()["detail"] == falso.json()["detail"]

    def test_criar_pela_conversa_exige_login(self, cliente_http, conversa):
        r = cliente_http.post(
            f"/api/conversas/{conversa['id']}/link-de-formulario",
            json={"slug": SLUG})
        assert r.status_code in (401, 403)

    def test_criar_pela_conversa_devolve_o_link_pronto(self, cliente_http,
                                                       token, formulario,
                                                       conversa):
        r = cliente_http.post(
            f"/api/conversas/{conversa['id']}/link-de-formulario",
            json={"slug": SLUG},
            headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["slug"] == SLUG
        # 📏 Tres: "Nome da Empresa", "Primeiro Nome" e "Sobrenome" -- o que
        # a pesquisa CES tem em comum com o mapa de sugestao.
        assert d["campos_sugeridos"] == 3
        assert d["url"].endswith(d["bilhete"])
        for segredo in (CNPJ, FONE, EMPRESA):
            assert segredo not in d["url"]

    def test_conversa_que_nao_existe_404(self, cliente_http, token,
                                         formulario):
        r = cliente_http.post(
            "/api/conversas/99999999/link-de-formulario",
            json={"slug": SLUG},
            headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404

    def test_formulario_desligado_404_com_frase_que_diz_O_QUE_RESOLVE(
            self, cliente_http, token, formulario, conversa):
        banco.executar("UPDATE formulario SET ativo = false WHERE codigo = %s",
                       (CODIGO,))
        r = cliente_http.post(
            f"/api/conversas/{conversa['id']}/link-de-formulario",
            json={"slug": SLUG},
            headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404
        assert "publicado" in r.json()["detail"]

    def test_a_lista_da_conversa_responde(self, cliente_http, token,
                                          formulario, conversa):
        formularios.criar_convite(SLUG, {}, conversa_id=conversa["id"])
        r = cliente_http.get(
            f"/api/conversas/{conversa['id']}/links-de-formulario",
            headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        assert len(r.json()["convites"]) == 1


# -------------------------------------------------- o envio marca o convite

class TestOEnvioMarcaOConvite:
    def test_marcar_usado_nao_invalida_o_convite(self, formulario, conversa):
        """⚠️ O rastro de quem convidou quem é o que explica, depois, de onde
        saiu a solicitação. Invalidar apagaria a origem."""
        c = formularios.criar_convite(SLUG, {}, conversa_id=conversa["id"])
        r = formularios.registrar(formulario, {}, ip="testclient")
        formularios.marcar_convite_usado(c["bilhete"], r["id"])
        linha = banco.um("SELECT usado_em, solicitacao_id "
                         "FROM formulario_convite WHERE id = %s", (c["id"],))
        assert linha["usado_em"] is not None
        assert linha["solicitacao_id"] == r["id"]
        # 🚨 E o convite CONTINUA valendo: a pessoa pode ter mandado dois
        # chamados pelo mesmo link, e o segundo não pode bater em porta
        # fechada.
        assert formularios.convite(c["bilhete"]) is not None

    def test_FK_quebrada_nao_estoura_e_NAO_marca(self, formulario, conversa):
        """📏 Medido: a marca e o id vão no MESMO `UPDATE`, então solicitação
        que não existe perde as duas — a FK desfaz a instrução inteira.

        ⚠️ Esta trava guarda a parte que importa: **não estoura**. Marca de
        rastro que derruba o envio seria pior que marca que falta, e o cliente
        do outro lado já leu *"recebemos"*.
        """
        c = formularios.criar_convite(SLUG, {}, conversa_id=conversa["id"])
        formularios.marcar_convite_usado(c["bilhete"], 999999999)
        linha = banco.um("SELECT usado_em FROM formulario_convite "
                         "WHERE id = %s", (c["id"],))
        assert linha["usado_em"] is None
        assert formularios.convite(c["bilhete"]) is not None

    def test_marcar_bilhete_vazio_nao_faz_nada_nem_estoura(self):
        formularios.marcar_convite_usado("", 1)
        formularios.marcar_convite_usado(None, 1)

