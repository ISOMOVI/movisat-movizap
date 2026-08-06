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

from movizap import harmonit, sync  # noqa: E402

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
            "contatoPrincipalId": 1603978,
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
        bruto = velasco()
        cliente_id, _ = sync._gravar_cliente(cur, bruto)
        contato_id = sync._gravar_contato(cur, cliente_id, bruto)
        cur.execute("SELECT harmonit_id FROM contato WHERE id=%s", (contato_id,))
        assert cur.fetchone()["harmonit_id"] == "1603978"

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
        cont = sync.Contadores()
        sync._gravar_telefones(cur, contato_id, bruto, cont)
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
            sync._gravar_telefones(cur, contato_id, bruto, sync.Contadores())
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
        sync._gravar_telefones(cur, contato_id, bruto, sync.Contadores())

        cur.execute(
            "UPDATE contato_telefone SET tem_whatsapp=true, verificado_em=now() "
            "WHERE contato_id=%s AND origem_campo='celular'", (contato_id,))

        sync._gravar_telefones(cur, contato_id, bruto, sync.Contadores())

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
        cont = sync.Contadores()
        sync._gravar_telefones(cur, contato_id, bruto, cont)
        assert cont.erros == 0 and cont.vazios == 0


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
