"""Testes do sync do Harmonit.

Metodologia §6: "Leitura do Harmonit -- o formato duplo precisa de fixture
real". A fixture aqui é o payload MEDIDO na API em 2026-08-06, não um payload
inventado que confirma o que o código já faz.

Cada teste roda numa transação com rollback: o banco não guarda lixo, e
nenhum teste depende do que outro deixou.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
psycopg = pytest.importorskip("psycopg")
from psycopg.rows import dict_row  # noqa: E402

from movizap import harmonit, identidade, sync, telefone  # noqa: E402


def gravar_telefones(cur, contato_id, bruto, cont=None):
    """O fluxo real em duas passagens, para um cliente só.

    Existe porque o sync deixou de gravar telefone durante a leitura: decidir
    de quem é um número compartilhado exige ver todos os clientes antes. Sem
    este atalho, cada teste teria que remontar as duas passagens à mão.
    """
    cont = cont or sync.Contadores()
    harmonit_id = str(bruto["id"])
    telefones = sync.extrair_telefones(bruto, cont)
    donos = {e164: harmonit_id for _c, e164, _t, _g in telefones}
    sync._gravar_telefones(cur, contato_id, harmonit_id, telefones, donos, cont)
    return cont

ENV = Path("/home/claude/movizap_painel/.env")


def _cfg():
    d = {}
    if not ENV.exists():
        return d
    for linha in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.strip().startswith("#"):
            k, _, v = linha.partition("=")
            d[k.strip()] = v.strip()
    return d


CFG = _cfg()
pytestmark = pytest.mark.skipif(
    "MOVIZAP_DB_SENHA" not in CFG, reason="banco nao configurado no .env")


@pytest.fixture
def cur():
    conn = psycopg.connect(
        host=CFG["MOVIZAP_DB_HOST"], port=CFG["MOVIZAP_DB_PORTA"],
        dbname=CFG["MOVIZAP_DB_NOME"], user=CFG["MOVIZAP_DB_USUARIO"],
        password=CFG["MOVIZAP_DB_SENHA"], row_factory=dict_row,
    )
    try:
        with conn.cursor() as c:
            yield c
    finally:
        conn.rollback()
        conn.close()


# ── Payload REAL, copiado da API em 06/08 ────────────────────────────────────
# Velasco: telefone é fixo no DDD 68, celular é o WhatsApp conhecido no 18,
# telefone2 vem inteiramente em branco. Os três casos num registro só.
#
# 🚨 O `contatoPrincipalId` é DERIVADO do harmonit_id de teste, nunca o real
# (1603978). Enquanto o banco estava vazio, usar o id verdadeiro passava; assim
# que o sync gravou os 1.050 clientes de verdade, três testes passaram a
# enxergar a LINHA DE PRODUÇÃO da Velasco e liam os telefones dela. Teste que
# escreve em tabela de produção precisa da própria linha -- inclusive da
# própria chave estrangeira.
def velasco(harmonit_id="9990001"):
    return {
        "id": harmonit_id,
        "nome": "Velasco Leite Pastelaria ME",
        "nomeFantasia": "Pastelaria Velasco",
        "cnpJ_CPF": "WQ0P6GLD000108",
        "tipoPessoa": 1,
        "tipoPessoaDesc": "Jurídica",
        "situacaoClienteId": 331,
        "ativo": True,
        "contatoPrincipal": {
            "contatoPrincipalId": f"teste-{harmonit_id}",
            "email": "pastelaria.velasco@geradornv.com.br",
            "telefone": {"ddd": "68", "ddi": "55", "phone": "37148157"},
            "telefone2": {"ddd": "", "ddi": "", "phone": ""},
            "celular": {"ddd": "18", "ddi": "55", "phone": "998116168"},
        },
    }


class TestUpsertCliente:
    def test_cria_e_depois_atualiza_sem_duplicar(self, cur):
        bruto = velasco()
        id1, criado1 = sync._gravar_cliente(cur, bruto)
        assert criado1 is True

        bruto["nomeFantasia"] = "Pastelaria Velasco II"
        id2, criado2 = sync._gravar_cliente(cur, bruto)
        assert id2 == id1
        assert criado2 is False

        cur.execute("SELECT count(*) AS n FROM cliente WHERE harmonit_id=%s",
                    (bruto["id"],))
        assert cur.fetchone()["n"] == 1

        cur.execute("SELECT nome_fantasia FROM cliente WHERE id=%s", (id1,))
        assert cur.fetchone()["nome_fantasia"] == "Pastelaria Velasco II"

    def test_grava_os_campos_medidos_na_api(self, cur):
        cliente_id, _ = sync._gravar_cliente(cur, velasco())
        cur.execute("SELECT * FROM cliente WHERE id=%s", (cliente_id,))
        linha = cur.fetchone()
        assert linha["nome"] == "Velasco Leite Pastelaria ME"
        assert linha["documento"] == "WQ0P6GLD000108"  # CNPJ alfanumérico
        assert linha["tipo_pessoa"] == 1
        assert linha["origem"] == "harmonit"
        assert linha["ativo"] is True

    def test_ativo_false_do_harmonit_chega_no_banco(self, cur):
        bruto = velasco()
        bruto["ativo"] = False
        cliente_id, _ = sync._gravar_cliente(cur, bruto)
        cur.execute("SELECT ativo FROM cliente WHERE id=%s", (cliente_id,))
        assert cur.fetchone()["ativo"] is False

    def test_cliente_sem_nome_nao_derruba_o_lote(self, cur):
        bruto = velasco()
        bruto["nome"] = "   "
        bruto["nomeFantasia"] = None
        cliente_id, _ = sync._gravar_cliente(cur, bruto)
        assert cliente_id
        cur.execute("SELECT nome FROM cliente WHERE id=%s", (cliente_id,))
        assert "sem nome" in cur.fetchone()["nome"]


class TestOrigemMovizapEIntocavel:
    """🚨 Metodologia §3: o sync nunca apaga o que não é dele."""

    def test_cliente_nosso_com_mesmo_harmonit_id_nao_e_tocado(self, cur):
        cur.execute(
            "INSERT INTO cliente (nome, origem, harmonit_id) "
            "VALUES ('Cadastro nosso', 'movizap', %s) RETURNING id",
            ("9990002",))
        nosso = cur.fetchone()["id"]

        bruto = velasco("9990002")
        devolvido, criado = sync._gravar_cliente(cur, bruto)
        assert devolvido == 0, "o sync devolveu id de linha que não é dele"
        assert criado is False

        cur.execute("SELECT nome, origem FROM cliente WHERE id=%s", (nosso,))
        linha = cur.fetchone()
        assert linha["nome"] == "Cadastro nosso"
        assert linha["origem"] == "movizap"

    def test_inativacao_nao_encosta_em_cadastro_nosso(self, cur):
        cur.execute("INSERT INTO cliente (nome, origem, harmonit_id, ativo) "
                    "VALUES ('So nosso', 'movizap', NULL, true) RETURNING id")
        nosso = cur.fetchone()["id"]
        cur.execute("INSERT INTO cliente (nome, origem, harmonit_id, ativo) "
                    "VALUES ('Do harmonit', 'harmonit', %s, true) RETURNING id",
                    ("9990003",))
        deles = cur.fetchone()["id"]

        sync._inativar_sumidos(cur, {"9999999"})  # 9990003 não está na lista

        cur.execute("SELECT ativo FROM cliente WHERE id=%s", (nosso,))
        assert cur.fetchone()["ativo"] is True, "inativou cadastro do MoviZap"
        cur.execute("SELECT ativo FROM cliente WHERE id=%s", (deles,))
        assert cur.fetchone()["ativo"] is False

    def test_lista_vazia_nao_inativa_a_base_inteira(self, cur):
        """🚨 O guarda-corpo. Leitura que falhou não pode virar apagão."""
        cur.execute("INSERT INTO cliente (nome, origem, harmonit_id, ativo) "
                    "VALUES ('Do harmonit', 'harmonit', %s, true) RETURNING id",
                    ("9990004",))
        deles = cur.fetchone()["id"]

        assert sync._inativar_sumidos(cur, set()) == 0

        cur.execute("SELECT ativo FROM cliente WHERE id=%s", (deles,))
        assert cur.fetchone()["ativo"] is True


class TestContato:
    def test_usa_o_contato_principal_id_como_chave(self, cur):
        bruto = velasco("9990020")
        cliente_id, _ = sync._gravar_cliente(cur, bruto)
        contato_id = sync._gravar_contato(cur, cliente_id, bruto)
        cur.execute("SELECT harmonit_id FROM contato WHERE id=%s", (contato_id,))
        assert cur.fetchone()["harmonit_id"] == "teste-9990020"

    def test_sem_contato_principal_id_usa_chave_estavel(self, cur):
        """🚨 ~8% vêm sem o id. Sem chave estável, o contato seria recriado
        a cada sync -- e a base cresceria sozinha."""
        bruto = velasco("9990005")
        bruto["contatoPrincipal"]["contatoPrincipalId"] = None
        cliente_id, _ = sync._gravar_cliente(cur, bruto)

        primeiro = sync._gravar_contato(cur, cliente_id, bruto)
        segundo = sync._gravar_contato(cur, cliente_id, bruto)
        assert primeiro == segundo, "recriou o contato em vez de reaproveitar"

        cur.execute("SELECT harmonit_id FROM contato WHERE id=%s", (primeiro,))
        assert cur.fetchone()["harmonit_id"] == "cli:9990005"

    def test_nome_do_contato_vem_do_cliente(self, cur):
        """Não existe `nome` no contatoPrincipal -- conferido na API real."""
        bruto = velasco()
        assert "nome" not in bruto["contatoPrincipal"]
        cliente_id, _ = sync._gravar_cliente(cur, bruto)
        contato_id = sync._gravar_contato(cur, cliente_id, bruto)
        cur.execute("SELECT nome FROM contato WHERE id=%s", (contato_id,))
        assert cur.fetchone()["nome"] == "Pastelaria Velasco"


class TestTelefones:
    def _gravar(self, cur, bruto):
        cliente_id, _ = sync._gravar_cliente(cur, bruto)
        contato_id = sync._gravar_contato(cur, cliente_id, bruto)
        cont = gravar_telefones(cur, contato_id, bruto)
        return contato_id, cont

    def test_grava_fixo_e_celular_e_ignora_o_vazio(self, cur):
        contato_id, cont = self._gravar(cur, velasco())
        cur.execute("SELECT e164, origem_campo, principal FROM contato_telefone "
                    "WHERE contato_id=%s ORDER BY origem_campo", (contato_id,))
        linhas = cur.fetchall()
        assert [l["e164"] for l in linhas] == ["+5518998116168", "+556837148157"]
        assert [l["origem_campo"] for l in linhas] == ["celular", "telefone"]

    def test_vazio_conta_como_vazio_e_NAO_como_erro(self, cur):
        """🚨 712 dos 1.200 campos vêm vazios. Contar isso como erro é o que
        faz o painel acusar 76% de falha num sistema saudável."""
        _, cont = self._gravar(cur, velasco())
        assert cont.vazios == 1  # telefone2
        assert cont.erros == 0

    def test_ddd_00_conta_como_erro(self, cur):
        """DDD 00 existe de verdade na base -- medido em 06/08."""
        bruto = velasco("9990006")
        bruto["contatoPrincipal"]["telefone"] = {
            "ddd": "00", "ddi": "55", "phone": "00001058"}
        _, cont = self._gravar(cur, bruto)
        assert cont.erros == 1
        assert cont.vazios == 1

    def test_celular_e_marcado_como_principal(self, cur):
        contato_id, _ = self._gravar(cur, velasco())
        cur.execute("SELECT principal FROM contato_telefone "
                    "WHERE contato_id=%s AND origem_campo='celular'", (contato_id,))
        assert cur.fetchone()["principal"] is True

    def test_o_bruto_guarda_o_que_veio(self, cur):
        contato_id, _ = self._gravar(cur, velasco())
        cur.execute("SELECT bruto FROM contato_telefone "
                    "WHERE contato_id=%s AND origem_campo='celular'", (contato_id,))
        assert "998116168" in cur.fetchone()["bruto"]

    def test_rodar_duas_vezes_nao_duplica(self, cur):
        bruto = velasco("9990007")
        cliente_id, _ = sync._gravar_cliente(cur, bruto)
        contato_id = sync._gravar_contato(cur, cliente_id, bruto)
        for _ in range(3):
            gravar_telefones(cur, contato_id, bruto)
        cur.execute("SELECT count(*) AS n FROM contato_telefone WHERE contato_id=%s",
                    (contato_id,))
        assert cur.fetchone()["n"] == 2

    def test_SYNC_NAO_APAGA_TEM_WHATSAPP(self, cur):
        """🚨 O teste mais importante deste arquivo.

        `tem_whatsapp` é do Evolution. Se o UPDATE do sync incluísse essa
        coluna, cada sincronização apagaria a verificação real -- e ninguém
        perceberia, porque NULL e false se parecem numa tela.
        """
        bruto = velasco("9990008")
        cliente_id, _ = sync._gravar_cliente(cur, bruto)
        contato_id = sync._gravar_contato(cur, cliente_id, bruto)
        gravar_telefones(cur, contato_id, bruto)

        cur.execute(
            "UPDATE contato_telefone SET tem_whatsapp=true, verificado_em=now() "
            "WHERE contato_id=%s AND origem_campo='celular'", (contato_id,))

        gravar_telefones(cur, contato_id, bruto)

        cur.execute("SELECT tem_whatsapp, verificado_em FROM contato_telefone "
                    "WHERE contato_id=%s AND origem_campo='celular'", (contato_id,))
        linha = cur.fetchone()
        assert linha["tem_whatsapp"] is True, "o sync apagou a verificação do Evolution"
        assert linha["verificado_em"] is not None

    def test_contato_principal_ausente_nao_estoura(self, cur):
        bruto = velasco("9990009")
        bruto["contatoPrincipal"] = None
        cliente_id, _ = sync._gravar_cliente(cur, bruto)
        contato_id = sync._gravar_contato(cur, cliente_id, bruto)
        cont = gravar_telefones(cur, contato_id, bruto)
        assert cont.erros == 0 and cont.vazios == 0


class TestPrincipal:
    """🔴 Achado na auditoria de 06/08.

    A regra "principal = campo celular" deixou 659 dos 1.050 contatos sem
    nenhum telefone principal -- os que têm fixo e não têm celular. Quando o
    atendimento perguntasse "qual é o número deste cliente", 63% da base não
    tinha resposta.
    """

    def _telefones(self, cur, bruto):
        cliente_id, _ = sync._gravar_cliente(cur, bruto)
        contato_id = sync._gravar_contato(cur, cliente_id, bruto)
        gravar_telefones(cur, contato_id, bruto)
        cur.execute("SELECT e164, origem_campo, principal FROM contato_telefone "
                    "WHERE contato_id=%s", (contato_id,))
        return contato_id, cur.fetchall()

    def test_celular_ganha_quando_existe(self, cur):
        _, linhas = self._telefones(cur, velasco("9990010"))
        principais = [l["e164"] for l in linhas if l["principal"]]
        assert principais == ["+5518998116168"]

    def test_SO_FIXO_ainda_assim_tem_principal(self, cur):
        """O caso dos 659. Fixo responde melhor que nada."""
        bruto = velasco("9990011")
        bruto["contatoPrincipal"]["celular"] = {"ddd": "", "ddi": "", "phone": ""}
        _, linhas = self._telefones(cur, bruto)
        principais = [l["e164"] for l in linhas if l["principal"]]
        assert principais == ["+556837148157"], "contato com fixo ficou sem principal"

    def test_movel_no_campo_telefone_ganha_do_fixo(self, cur):
        """O Harmonit guarda celular no campo `telefone` também."""
        bruto = velasco("9990012")
        bruto["contatoPrincipal"]["celular"] = {"ddd": "", "ddi": "", "phone": ""}
        bruto["contatoPrincipal"]["telefone"] = {
            "ddd": "18", "ddi": "55", "phone": "32214455"}     # fixo
        bruto["contatoPrincipal"]["telefone2"] = {
            "ddd": "18", "ddi": "55", "phone": "997776666"}    # movel
        _, linhas = self._telefones(cur, bruto)
        principais = [l["e164"] for l in linhas if l["principal"]]
        assert principais == ["+5518997776666"]

    def test_nunca_ha_dois_principais(self, cur):
        _, linhas = self._telefones(cur, velasco("9990013"))
        assert sum(1 for l in linhas if l["principal"]) == 1

    def test_sem_telefone_nenhum_nao_estoura(self, cur):
        bruto = velasco("9990014")
        for campo in ("telefone", "telefone2", "celular"):
            bruto["contatoPrincipal"][campo] = {"ddd": "", "ddi": "", "phone": ""}
        _, linhas = self._telefones(cur, bruto)
        assert linhas == []

    def test_escolha_e_estavel_entre_execucoes(self, cur):
        bruto = velasco("9990015")
        contato_id, _ = self._telefones(cur, bruto)
        for _ in range(3):
            gravar_telefones(cur, contato_id, bruto)
        cur.execute("SELECT count(*) AS n FROM contato_telefone "
                    "WHERE contato_id=%s AND principal", (contato_id,))
        assert cur.fetchone()["n"] == 1


class TestEscolherPrincipalPuro:
    """A regra isolada, sem banco -- é onde o erro de ordem apareceria."""

    def test_ordem_de_preferencia(self):
        escolher = sync._escolher_principal
        assert escolher([]) is None
        assert escolher([("telefone", "+551832214455", telefone.FIXO)]) \
            == "+551832214455"
        assert escolher([
            ("telefone", "+551832214455", telefone.FIXO),
            ("celular", "+5518998116168", telefone.MOVEL),
        ]) == "+5518998116168"
        assert escolher([
            ("telefone", "+551832214455", telefone.FIXO),
            ("telefone2", "+5518997776666", telefone.MOVEL),
        ]) == "+5518997776666"


class TestIdentidade:
    """A regra medida em docs/08_Identidade.md, auditada em 06/08."""

    def test_sentinela_do_dotnet_nao_e_data(self):
        """🚨 `0001-01-01` parseia sem erro e vira o ano 1. Gravado como data,
        o registro SEM data ganharia toda disputa de antiguidade -- a regra
        ficaria invertida e nada acusaria."""
        assert identidade.data_cadastro({"dataCadastro": "0001-01-01T00:00:00"}) is None
        assert identidade.data_cadastro({"dataCadastro": ""}) is None
        assert identidade.data_cadastro({}) is None
        real = identidade.data_cadastro({"dataCadastro": "2017-11-16T00:00:00"})
        assert real and real.year == 2017

    def test_sufixo_societario_nao_distingue_empresa(self):
        assert identidade.mesma_empresa(
            "FAXT TELECOMUNICACOES LTDA.", "FAXT TELECOMUNICACOES LTDA")
        assert identidade.mesma_empresa(
            "MOTO HELP ENTREGAS (MATRIZ)", "MOTO HELP ENTREGAS RAPIDAS LTDA")

    def test_empresas_diferentes_nao_se_confundem(self):
        assert not identidade.mesma_empresa(
            "ALPHA CLICHERIA E SOLUCOES GRAFICAS LTDA", "SMART CLICHERIA LIMITADA ME")
        assert not identidade.mesma_empresa(
            "GM ENERGIA SOLAR LTDA", "FOTOVOLTEC SOLUCOES EM ENERGIA LTDA")
        assert not identidade.mesma_empresa("DANIEL MATIAS", "EDUARDO GONCALVES")

    def test_nome_vazio_nunca_casa(self):
        """Dois nomes vazios não são 'a mesma empresa' -- seriam TODAS."""
        assert not identidade.mesma_empresa("", "")
        assert not identidade.mesma_empresa("LTDA", "ME")

    def test_mesmo_cliente_o_mais_antigo_fica_com_o_numero(self):
        brutos = {
            "100": {"id": 100, "nome": "FAXT TELECOM LTDA",
                    "dataCadastro": "2020-01-01T00:00:00"},
            "200": {"id": 200, "nome": "FAXT TELECOM LTDA.",
                    "dataCadastro": "2024-01-01T00:00:00"},
        }
        donos, revisao = identidade.decidir_donos(
            brutos, {"100": {"+5519999990000"}, "200": {"+5519999990000"}})
        assert donos == {"+5519999990000": "100"}
        assert revisao == {}

    def test_quem_nao_tem_data_perde_o_desempate(self):
        """🚨 O oposto do que o sentinela faria."""
        brutos = {
            "100": {"id": 100, "nome": "FAXT TELECOM LTDA", "dataCadastro": None},
            "200": {"id": 200, "nome": "FAXT TELECOM LTDA.",
                    "dataCadastro": "2024-01-01T00:00:00"},
        }
        donos, _ = identidade.decidir_donos(
            brutos, {"100": {"+5519999990000"}, "200": {"+5519999990000"}})
        assert donos == {"+5519999990000": "200"}, "quem não tem data ganhou"

    def test_EMPRESAS_DIFERENTES_NINGUEM_RECEBE(self):
        """🚨 A decisão do usuário em 06/08: o duvidoso não sobe."""
        brutos = {
            "100": {"id": 100, "nome": "GM ENERGIA SOLAR LTDA",
                    "dataCadastro": "2020-01-01T00:00:00"},
            "200": {"id": 200, "nome": "FOTOVOLTEC SOLUCOES LTDA",
                    "dataCadastro": "2024-01-01T00:00:00"},
        }
        donos, revisao = identidade.decidir_donos(
            brutos, {"100": {"+5538999990000"}, "200": {"+5538999990000"}})
        assert donos == {}, "atribuiu um número disputado por empresas distintas"
        assert "+5538999990000" in revisao

    def test_misto_tambem_vai_para_revisao(self):
        """Grupo econômico + um estranho: ninguém recebe."""
        brutos = {
            "100": {"id": 100, "nome": "FAZENDA DA TOCA LTDA", "dataCadastro": None},
            "200": {"id": 200, "nome": "FAZENDA DA TOCA LTDA", "dataCadastro": None},
            "300": {"id": 300, "nome": "MANTIQUEIRA ALIMENTOS LTDA.",
                    "dataCadastro": None},
        }
        donos, revisao = identidade.decidir_donos(
            brutos, {k: {"+5521999990000"} for k in ("100", "200", "300")})
        assert donos == {}
        assert revisao

    def test_numero_de_um_dono_so_nao_vira_revisao(self):
        brutos = {"100": {"id": 100, "nome": "SOZINHA LTDA", "dataCadastro": None}}
        donos, revisao = identidade.decidir_donos(brutos, {"100": {"+5519888880000"}})
        assert donos == {"+5519888880000": "100"}
        assert revisao == {}

    def test_marca_de_revisao_no_nome(self):
        assert identidade.motivo_de_revisao({"nome": "[NÃO USAR] MOTO HELP"})
        assert identidade.motivo_de_revisao({"nome": "CENTRO LOGISTICO (INATIVADO)"})
        assert identidade.motivo_de_revisao({"nome": "EMPRESA NORMAL LTDA"}) is None


class TestTelefoneEmRevisaoNaoEGravado:
    def test_numero_de_outro_dono_nao_entra(self, cur):
        bruto = velasco("9990030")
        cliente_id, _ = sync._gravar_cliente(cur, bruto)
        contato_id = sync._gravar_contato(cur, cliente_id, bruto)
        cont = sync.Contadores()
        telefones = sync.extrair_telefones(bruto, cont)
        # ninguém é dono: é o caso "em revisão"
        sync._gravar_telefones(cur, contato_id, "9990030", telefones, {}, cont)
        cur.execute("SELECT count(*) AS n FROM contato_telefone WHERE contato_id=%s",
                    (contato_id,))
        assert cur.fetchone()["n"] == 0
        assert cont.nao_atribuidos == len(telefones)


class TestClienteHarmonit:
    def test_take_acima_do_teto_falha_antes_de_sair_da_maquina(self):
        """🚨 O teto é 100, medido em 06/08. Falhar aqui, com o motivo, é
        melhor que tomar HTTP 400 no meio de uma varredura de 1.050."""
        with pytest.raises(ValueError, match="teto"):
            next(harmonit.paginar_clientes(take=200))

    def test_origem_invalida_e_recusada(self):
        with pytest.raises(ValueError, match="origem"):
            sync.executar(origem="qualquer")

    def test_estado_do_disjuntor_e_legivel(self):
        harmonit.reiniciar()
        e = harmonit.estado()
        assert e["aberto"] is False
        assert e["falhas_seguidas"] == 0
