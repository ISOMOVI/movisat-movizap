"""AS ETAPAS DOS 15 FORMULÁRIOS — 11/11.

🔵 Dele: *"Os formulários devem seguir como a padronização do formulário de
suporte, no quesito de estilo, validação de campos, disposição e lógica"* ·
*"tudo que foi pedido deve ser entregue, principalmente os formularios que ainda
nao sairam"*.

🚨 A TRAVA QUE IMPORTA É A DA PERGUNTA FORA DE TODA ETAPA. Etapa que cita campo
inexistente faz a pergunta sumir da tela; pergunta que ficou fora de toda etapa
**o cliente nunca vê**, e o formulário segue "funcionando" com uma pergunta
menos. O segundo é o perigoso, e é silencioso.

⚠️ Nenhum teste aqui escreve: todos leem o estado dos 15.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

DECORATIVOS = ("page", "layout")


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    yield


def formularios():
    """Os formularios DE CLIENTE -- os que vieram do Bitrix.

    🔵 27/11: `AND NOT interno`. Nasceu o `COMPRAS` (migracao 122), interno,
    `classico` e sem etapas -- e ele fez SETE travas deste arquivo reprovarem
    de uma vez, inclusive a contagem de 16.

    🚨 **O ESCOPO ERA O DEFEITO, NAO A TRAVA.** Afrouxar a contagem para 17 ou
    tirar a cobranca do formato apagaria o que este arquivo existe para medir:
    que os DEZESSEIS do cliente estao todos no formato novo, com etapas, e sem
    pergunta fora de etapa. Formulario interno nao tem pagina publica, nao
    passa pelo carregador do Bitrix e nao usa o formato por etapas -- ele nao
    e um dos 16, e contar junto era a pergunta errada.

    ⚠️ E a contagem FICA EM 16 de proposito: ela e a trava de que nenhum dos
    quinze (mais o Contato) desapareceu.
    """
    return banco.varios(
        """SELECT id, slug, formato, etapas FROM formulario
            WHERE NOT interno ORDER BY slug""")


def campos(form_id):
    return banco.varios(
        """SELECT nosso_nome, tipo FROM formulario_campo
            WHERE formulario_id = %s ORDER BY ordem, id""", (form_id,))


class TestOsQuinzeSairam:
    def test_todos_estao_no_formato_NOVO(self):
        """🔵 *"os formularios que ainda nao sairam"* — eram 14 em `classico`."""
        fora = [f["slug"] for f in formularios() if f["formato"] != "novo"]
        assert fora == [], fora

    def test_todos_tem_etapas(self):
        sem = [f["slug"] for f in formularios() if not f["etapas"]]
        assert sem == [], sem

    def test_sao_dezesseis(self):
        """🔵 11/11: o 16o nasceu -- *"Ideias e sugestoes"*, o Bitrix 38.

        🚨 Ele nao estava entre os 15 levantados em 22/10: e o 7o cartao do
        SAC, e apareceu quando o clone do SAC foi medido. Era o UNICO dos 8
        cartoes da pagina sem formulario nosso.
        """
        slugs = [f["slug"] for f in formularios()]
        assert len(slugs) == 16, slugs
        assert "ideias-sugestoes" in slugs


class TestNenhumaPerguntaFicaDeFORA:
    """🚨 O defeito silencioso: a pergunta existe, é obrigatória, e o cliente
    nunca a vê porque nenhuma etapa a cita."""

    def test_toda_pergunta_esta_em_EXATAMENTE_uma_etapa(self):
        for f in formularios():
            perguntas = [c["nosso_nome"] for c in campos(f["id"])
                         if c["tipo"] not in DECORATIVOS]
            citados = [n for e in f["etapas"] for n in (e.get("campos") or [])]
            assert sorted(set(citados)) == sorted(set(perguntas)), f["slug"]
            # e nenhuma repetida: campo em duas etapas aparece duas vezes
            assert len(citados) == len(set(citados)), f["slug"]

    def test_nenhuma_etapa_cita_DECORATIVO(self):
        """⚠️ `page` e `layout` (o traço) não são pergunta. Citar um deles poria
        no trilho um 'campo' que a tela não sabe desenhar."""
        for f in formularios():
            decor = {c["nosso_nome"] for c in campos(f["id"])
                     if c["tipo"] in DECORATIVOS}
            citados = {n for e in f["etapas"] for n in (e.get("campos") or [])}
            assert not (citados & decor), (f["slug"], citados & decor)

    def test_nenhuma_etapa_esta_VAZIA(self):
        """Passo sem campo é um clique no trilho que não faz nada."""
        for f in formularios():
            for e in f["etapas"]:
                assert e.get("campos"), (f["slug"], e.get("titulo"))


class TestOSuporteEhAbaseENaoFoiTocado:
    """🚨 *"o formulario suporte é a base"*. As etapas dele são as que ELE
    escreveu, e o meu molde as reescreveria -- chamaria *"Veiculos e anexos"* de
    "Anexos", trocando a palavra dele pela minha no único que já estava certo."""

    def test_os_titulos_do_suporte_sao_os_DELE(self):
        f = next(x for x in formularios() if x["slug"] == "suporte")
        titulos = [e["titulo"] for e in f["etapas"]]
        assert titulos == ["Contrato", "Seus dados", "A solicitacao",
                           "Veiculos e anexos"], titulos

    def test_e_o_gerador_o_declara_INTOCAVEL(self):
        import inspect
        sys.path.insert(0, "/home/claude/movizap_painel/scripts")
        fonte = Path("/home/claude/movizap_painel/scripts/"
                     "etapas_dos_formularios.py").read_text(encoding="utf-8")
        assert 'INTOCAVEIS = ("suporte",)' in fonte
        assert inspect  # usado só para deixar claro que é leitura de fonte


class TestOsTitulosServem:
    def test_nenhum_titulo_GENERICO(self):
        """⚠️ *"Página 1"* no trilho não diz nada a quem preenche. Quando as
        páginas do formulário vinham sem nome de verdade, o molde do Suporte
        ganhou -- e é por isso que `fornecedores` tem "Contrato / Seus dados /
        A solicitação" e não "Página 1 / 2 / 3"."""
        import re
        generico = re.compile(r"^\s*(p[áa]gina|page|etapa|step)\s*\d*\s*$",
                              re.I)
        for f in formularios():
            for e in f["etapas"]:
                assert not generico.match(e["titulo"] or ""), (f["slug"],
                                                               e["titulo"])

    def test_quem_tem_PAGINA_COM_NOME_usa_a_do_formulario(self):
        """O agrupamento é de quem desenhou o formulário, não meu."""
        f = next(x for x in formularios()
                 if x["slug"] == "credenciamento-tecnico")
        titulos = [e["titulo"] for e in f["etapas"]]
        assert "EMPRESA" in titulos
        assert "TABELA DE SERVIÇOS" in titulos

    def test_uma_etapa_SO_nao_e_trilho(self):
        """🚨 A tela só desenha o trilho com mais de uma etapa. Um único `page`
        com 12 campos devolveria a mesma página comprida de antes, com um título
        novo e nada mais -- foi o caso da `demonstracao`."""
        f = next(x for x in formularios() if x["slug"] == "demonstracao")
        assert len(f["etapas"]) > 1


class TestAValidacaoContinuaDePE:
    def test_os_64_campos_validados_seguem_validados(self):
        """⚠️ Escrever as etapas não podia mexer em `validacao` -- são colunas
        diferentes, e esta trava é o que prova que o `UPDATE` foi cirúrgico.

        🔵 11/11, mais tarde: **60 -> 64**, porque o 16o entrou com quatro
        (CNPJ, CPF, e-mail, telefone). ⚠️ E o numero aqui e CONTAGEM: quem
        garante que nenhuma validacao se perca na carga e a trava
        `test_toda_validacao_DO_BANCO_esta_declarada_no_script`, que compara
        banco com script em vez de contar.
        """
        assert banco.um(
            "SELECT count(*) n FROM formulario_campo "
            "WHERE validacao IS NOT NULL")["n"] == 64

    def test_e_nenhum_campo_foi_criado_ou_removido(self):
        """🔵 *"não inventar - Só ajustar"*.

        📏 **235 campos**, medidos em 11/11: 11 do Suporte e **224 nos outros
        14**; 17 decorativos (`page`/`layout`) e **218 perguntas de verdade**.
        ⚠️ Eu havia escrito **215** em três lugares -- soma errada da tabela,
        corrigida.
        """
        # 🔵 11/11, MAIS TARDE: o 16o entrou (Bitrix 38, "Ideias e
        # sugestoes") com 11 campos -- 235 + 11 = 246. ⚠️ A trava continua
        # valendo pelo que ela mede: campo criado ou removido por acidente.
        # O que mudou foi o numero, e mudou porque um formulario NASCEU.
        #
        # 🔵 27/11: `WHERE NOT interno`, e o numero FICA EM 246. O `COMPRAS`
        # (migracao 122) trouxe 3 campos e a contagem crua passou a 249 --
        # mas esta trava mede *"nao inventar - So ajustar"* nos formularios
        # DO CLIENTE, e um formulario interno novo nao e campo criado por
        # acidente num deles. Trocar 246 por 249 seria deixar a trava medir a
        # soma de dois conjuntos diferentes, que e como ela deixaria de
        # acusar o acidente que existe para acusar.
        assert banco.um(
            """SELECT count(*) n FROM formulario_campo c
                JOIN formulario f ON f.id = c.formulario_id
               WHERE NOT f.interno""")["n"] == 246


def _carregador():
    """O modulo `scripts/carregar_formularios.py`, sem rodar a carga."""
    import importlib.util
    cam = Path(__file__).resolve().parents[1] / "scripts" / "carregar_formularios.py"
    spec = importlib.util.spec_from_file_location("_cf", cam)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestACargaNaoApagaOQueEstaNoAr:
    """🚨 O DEFEITO QUE ESTAS TRAVAS GUARDAM, medido em 11/11.

    `scripts/carregar_formularios.py` SEM ARGUMENTO teria apagado **55 das 60
    validacoes**, revertido **14 formularios** de `novo` para `classico` e
    perdido as **etapas dos 15** -- em silencio, sem erro nenhum.

    A causa nao e um bug de codigo: e DUAS VERDADES. O arquivo se declara a
    fonte unica (*"gravar_definicao APAGA e reescreve os campos a cada
    carga"*), mas as validacoes entraram pelas migracoes 103/104 e as etapas
    pelo `etapas_dos_formularios.py`, direto no banco. A verdade que o script
    tinha era a menor.

    ⚠️ Nenhuma suite pegaria isso: o estado no ar estava CERTO. Só quem rodasse
    a carga descobriria -- depois.
    """

    def test_toda_validacao_DO_BANCO_esta_declarada_no_script(self):
        """A trava central: validacao que so existe no banco morre na carga."""
        mod = _carregador()
        declaradas = {
            (codigo, campo)
            for codigo, campos_ in mod.VALIDACOES.items()
            for campo in campos_
        }
        no_banco = {
            (r["codigo"], r["nosso_nome"])
            for r in banco.varios(
                """SELECT f.codigo, c.nosso_nome
                     FROM formulario_campo c
                     JOIN formulario f ON f.id = c.formulario_id
                    WHERE c.validacao IS NOT NULL""")
        }
        orfas = sorted(no_banco - declaradas)
        assert orfas == [], (
            "validacao que a proxima carga apagaria: %s" % orfas)

    def test_o_formato_novo_nao_depende_de_LISTA(self):
        """🚨 `FORMATO_NOVO = {"SUPORTE"}` era a lista que divergiu.

        `None` = todos. Lista volta a divergir no dia em que o 17o formulario
        nascer e ninguem lembrar de acrescenta-lo.
        """
        mod = _carregador()
        assert mod.FORMATO_NOVO is None

    def test_o_tipo_do_NOVO_TITULAR_sobrevive_a_carga(self):
        """🚨 Os dois campos de quem ASSUME o contrato.

        A migracao 104 os consertou no banco (`string` -> `email`/`phone`) e a
        carga os devolvia a `string`, porque o tipo vem do Bitrix. Agora o
        conserto mora no `AJUSTES`, que a carga aplica.
        """
        mod = _carregador()
        ajuste = (mod.AJUSTES.get("RESCISAO") or {}).get("campos") or {}
        assert ajuste.get("e-mail-do-novo-titular", {}).get("tipo") == "email"
        assert ajuste.get("telefone-com-ddd-do-novo-titular",
                          {}).get("tipo") == "phone"
        tipos = {
            r["nosso_nome"]: r["tipo"]
            for r in banco.varios(
                """SELECT c.nosso_nome, c.tipo FROM formulario_campo c
                     JOIN formulario f ON f.id = c.formulario_id
                    WHERE f.codigo = 'RESCISAO'""")
        }
        assert tipos.get("e-mail-do-novo-titular") == "email"
        assert tipos.get("telefone-com-ddd-do-novo-titular") == "phone"

    def test_o_documento_do_PARCEIRO_nao_e_obrigatorio(self):
        """🔵 23/11, dele: *"formulario de pagamento de parceiros esta errado,
        ele nao precisa de cpf e cnpj, obviamente pois nao puxa de base
        alguma, devem ser somente preencheiveis"*.

        🚨 O QUE ESTAVA ERRADO, MEDIDO EM 23/11: nos DOIS formularios de
        parceiro tecnico, CPF e CNPJ visiveis, os dois `obrigatorio = True` e
        NENHUMA regra condicional. Pessoa fisica tinha de inventar um CNPJ
        para o botao Enviar funcionar; pessoa juridica, um CPF. No
        CREDENCIAMENTO isso fechava a porta de entrada do parceiro.

        ⚠️ A trava mede os DOIS lados de proposito: o `AJUSTES` (que a carga
        aplica) e o banco (o que a internet le agora). Um sem o outro e meia
        verdade -- foi assim que 55 validacoes quase morreram em 11/11.
        """
        mod = _carregador()
        for codigo in ("PAGAMENTO_TECNICOS", "CREDENCIAMENTO"):
            ajuste = (mod.AJUSTES.get(codigo) or {}).get("campos") or {}
            for campo in ("cpf", "cnpj"):
                assert ajuste.get(campo, {}).get("obrigatorio") is False, (
                    "%s/%s: o ajuste nao desobriga, e a carga devolveria o "
                    "obrigatorio do Bitrix" % (codigo, campo))

        linhas = banco.varios(
            """SELECT f.codigo, c.nosso_nome, c.obrigatorio, c.validacao
                 FROM formulario_campo c
                 JOIN formulario f ON f.id = c.formulario_id
                WHERE f.codigo IN ('PAGAMENTO_TECNICOS', 'CREDENCIAMENTO')
                  AND c.nosso_nome IN ('cpf', 'cnpj')""")
        assert len(linhas) == 4, (
            "esperava os 4 documentos dos 2 formularios, achei %d" % len(linhas))
        for r in linhas:
            assert r["obrigatorio"] is False, (
                "%s/%s continua obrigatorio" % (r["codigo"], r["nosso_nome"]))
            # ⚠️ O CAMPO FICA INTEIRO, e isto e o pedido dele ao pe da letra:
            # *"somente preencheiveis"*. A validacao de FORMATO continua, e nao
            # ha contradicao -- ela so fala quando a pessoa escreve algo. Campo
            # vazio passa; CPF pela metade, nao. Tirar as duas coisas juntas
            # seria aceitar documento quebrado, que ele nao pediu.
            assert r["validacao"] == r["nosso_nome"], (
                "%s/%s perdeu a validacao de formato" % (r["codigo"],
                                                         r["nosso_nome"]))

    def test_quem_busca_cliente_bate_banco_x_script(self):
        """🔵 23/11, dele, sobre o botao Buscar: **tirar onde nao ha base**.

        🚨 O DEFEITO: `temBusca` era `ehNovo && validacao === 'cnpj'`, e
        `FORMATO_NOVO = None` poe os 16 em `novo` -- entao todo formulario com
        CNPJ ganhou o botao. O `cliente_por_documento` varre a tabela
        `cliente` (os clientes NOSSOS): parceiro tecnico, fornecedor e
        interessado em teste gratuito nunca estao la. O botao aparecia e a
        resposta certa era sempre "nao achou".

        ⚠️ A `FICHA_CADASTRAL` fica FORA de proposito: e a ficha de clientes
        NOVOS -- quem preenche, por definicao, ainda nao esta na base.
        """
        mod = _carregador()
        assert mod.BUSCA_CLIENTE == {
            "SUPORTE", "ADITIVO", "ADMINISTRATIVO", "FINANCEIRO", "RESCISAO",
            "SUBSTITUICAO",
        }
        no_banco = {
            r["codigo"]
            for r in banco.varios(
                "SELECT codigo FROM formulario WHERE busca_cliente")
        }
        assert no_banco == mod.BUSCA_CLIENTE, (
            "banco x script divergem: so no banco %s / so no script %s"
            % (sorted(no_banco - mod.BUSCA_CLIENTE),
               sorted(mod.BUSCA_CLIENTE - no_banco)))

    def test_a_definicao_publica_leva_o_busca_cliente(self):
        """🚨 O ELO QUE NENHUMA DAS DUAS TRAVAS ACIMA VE, E ELE QUEBROU.

        A coluna pode estar certa no banco e certa no script, e a internet
        continuar sem saber. Campo novo nao entra sozinho na cadeia -- quem
        devolve, quem grava, quem le
        ([[feedback_campo_novo_nao_entra_sozinho]]).

        🚨 ESTA TRAVA NASCEU MEDINDO A FUNCAO E ISSO NAO BASTOU. Em 23/11 ela
        passou verde com `formularios.definicao(...)` enquanto a INTERNET
        recebia a chave ausente: `_publico_do_formulario` monta o payload dela
        campo por campo, e a chave nova nao entrou. O botao sumiu dos 6
        contratuais, no ar, com a suite verde.
        ⚠️ Rota se mede PEDINDO A ROTA ([[feedback_rota_nova_pede_teste_http]]).
        """
        from fastapi.testclient import TestClient
        from movizap.main import app
        with TestClient(app) as c:
            assert c.get("/api/publico/formulario/suporte").json()[
                "busca_cliente"] is True
            assert c.get("/api/publico/formulario/pagamento-tecnicos").json()[
                "busca_cliente"] is False

    def test_o_derivador_de_etapas_pode_ser_IMPORTADO(self):
        """🚨 `main()` solto no fim rodava o relatorio e podia `sys.exit(1)`
        na cara de quem importou -- e o carregador agora o importa."""
        cam = (Path(__file__).resolve().parents[1] / "scripts"
               / "etapas_dos_formularios.py")
        fonte = cam.read_text(encoding="utf-8")
        assert '__name__ == "__main__"' in fonte
        assert not fonte.rstrip().endswith("\nmain()")


class TestOsCampoDoDecimoSexto:
    """O 16o formulario, campo a campo -- e os erros do Bitrix que ficaram
    para tras (🔵 *"o formulario suporte e a base, os erros de bitrix ficam
    para tras"*)."""

    def _campos(self):
        f = banco.um("SELECT id FROM formulario WHERE codigo = 'IDEIAS'")
        assert f, "o formulario IDEIAS nao existe"
        return {c["nosso_nome"]: c for c in banco.varios(
            """SELECT nosso_nome, tipo, obrigatorio, visivel, validacao,
                      linhas
                 FROM formulario_campo WHERE formulario_id = %s
                ORDER BY ordem""", (f["id"],))}

    def test_sao_onze_campos(self):
        assert len(self._campos()) == 11

    def test_CPF_e_CNPJ_nascem_ESCONDIDOS(self):
        """🚨 O Bitrix marca os ONZE como obrigatorios, CPF **e** CNPJ juntos
        -- e ninguem e as duas coisas. Quem resolve sao as 3 regras
        condicionais do proprio formulario: PJ mostra empresa e CNPJ, PF
        mostra CPF. Entao os tres nascem escondidos, e e isso que faz a
        obrigatoriedade do Bitrix parar de ser impossivel."""
        c = self._campos()
        assert c["cnpj"]["visivel"] is False
        assert c["cpf"]["visivel"] is False
        assert c["empresa"]["visivel"] is False

    def test_a_validacao_dos_quatro(self):
        c = self._campos()
        assert c["cnpj"]["validacao"] == "cnpj"
        assert c["cpf"]["validacao"] == "cpf"
        assert c["e-mail"]["validacao"] == "email"
        assert c["telefone"]["validacao"] == "telefone"

    def test_o_campo_de_DETALHE_tem_seis_linhas(self):
        """🚨 Pedir *"detalhe ao maximo"* numa caixa de UMA linha e o
        formulario desencorajando a resposta que ele quer."""
        c = self._campos()
        alvo = [k for k in c if k.startswith("detalhe-ao-maximo")]
        assert len(alvo) == 1, alvo
        assert c[alvo[0]]["linhas"] == 6

    def test_nasce_DESLIGADO(self):
        """🔵 Regua da casa: carregar a definicao e publicar sao dois atos, e
        so o segundo e dele."""
        f = banco.um("SELECT ativo FROM formulario WHERE codigo = 'IDEIAS'")
        assert f["ativo"] is False
