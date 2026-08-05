"""Testes do banco `movizap` -- as travas do modelo funcionando de verdade.

Conferir que a constraint EXISTE nao prova nada: prova-se tentando gravar o
estado invalido e exigindo que o banco recuse. Transicao invalida tem que ser
IMPOSSIVEL, nao improvavel (metodologia, item 6).

Cada teste roda numa transacao que sofre rollback: o banco nao guarda lixo.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
psycopg = pytest.importorskip("psycopg")

ENV = Path("/home/claude/movizap_painel/.env")


def _cfg():
    d = {}
    if not ENV.exists():
        return d
    for l in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in l and not l.strip().startswith("#"):
            k, _, v = l.partition("=")
            d[k.strip()] = v.strip()
    return d


CFG = _cfg()
pytestmark = pytest.mark.skipif(
    "MOVIZAP_DB_SENHA" not in CFG,
    reason="banco nao configurado no .env",
)


@pytest.fixture
def cur():
    """Conexao com rollback garantido -- nenhum teste suja o banco."""
    conn = psycopg.connect(
        host=CFG["MOVIZAP_DB_HOST"], port=CFG["MOVIZAP_DB_PORTA"],
        dbname=CFG["MOVIZAP_DB_NOME"], user=CFG["MOVIZAP_DB_USUARIO"],
        password=CFG["MOVIZAP_DB_SENHA"],
    )
    try:
        with conn.cursor() as c:
            yield c
    finally:
        conn.rollback()
        conn.close()


def canal(cur):
    cur.execute("INSERT INTO canal (nome,tipo,instancia) "
                "VALUES ('t','atendimento',NULL) RETURNING id")
    return cur.fetchone()[0]


def conversa(cur, canal_id, fone="+5518999990001", estado="humano"):
    cur.execute("INSERT INTO conversa (canal_id,telefone_e164,estado) "
                "VALUES (%s,%s,%s) RETURNING id", (canal_id, fone, estado))
    return cur.fetchone()[0]


class TestIdempotenciaDoWebhook:
    """A regra numero um do projeto: reentrega nao duplica."""

    def test_mesmo_id_externo_duas_vezes_e_recusado(self, cur):
        c = conversa(cur, canal(cur))
        sql = ("INSERT INTO mensagem (conversa_id,id_externo,direcao,autor,tipo,"
               "conteudo,criada_em) VALUES (%s,'ABC123','entrada','cliente',"
               "'texto','oi',now())")
        cur.execute(sql, (c,))
        with pytest.raises(psycopg.errors.UniqueViolation):
            cur.execute(sql, (c,))

    def test_id_externo_nulo_pode_repetir(self, cur):
        # mensagem nossa nao tem id do provedor -- o UNIQUE e parcial
        c = conversa(cur, canal(cur))
        sql = ("INSERT INTO mensagem (conversa_id,id_externo,direcao,autor,tipo,"
               "conteudo,criada_em) VALUES (%s,NULL,'saida','atendente',"
               "'texto','ola',now())")
        cur.execute(sql, (c,))
        cur.execute(sql, (c,))   # nao pode estourar


class TestNotaInternaNuncaSai:
    """🚨 Um dia alguem escreve 'cliente chato'. Nao pode sair."""

    def test_nota_marcada_como_saida_e_recusada(self, cur):
        c = conversa(cur, canal(cur))
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO mensagem (conversa_id,direcao,autor,tipo,conteudo,"
                "criada_em) VALUES (%s,'saida','atendente','nota','x',now())", (c,))

    def test_interna_que_nao_e_nota_e_recusada(self, cur):
        c = conversa(cur, canal(cur))
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO mensagem (conversa_id,direcao,autor,tipo,conteudo,"
                "criada_em) VALUES (%s,'interna','atendente','texto','x',now())", (c,))

    def test_nota_interna_valida_passa(self, cur):
        c = conversa(cur, canal(cur))
        cur.execute(
            "INSERT INTO mensagem (conversa_id,direcao,autor,tipo,conteudo,"
            "criada_em) VALUES (%s,'interna','atendente','nota',"
            "'cliente ja ligou 3x',now())", (c,))


class TestUmaConversaAbertaPorTelefone:
    """E isto que faz o cliente que volta REABRIR em vez de criar outra."""

    def test_duas_abertas_no_mesmo_canal_e_telefone_sao_recusadas(self, cur):
        k = canal(cur)
        conversa(cur, k, "+5518999990002", "humano")
        with pytest.raises(psycopg.errors.UniqueViolation):
            conversa(cur, k, "+5518999990002", "bot")

    def test_depois_de_resolvida_pode_abrir_outra(self, cur):
        k = canal(cur)
        conversa(cur, k, "+5518999990003", "resolvida")
        conversa(cur, k, "+5518999990003", "nova")   # nao pode estourar

    def test_mesmo_telefone_em_canais_diferentes_pode(self, cur):
        a, b = canal(cur), canal(cur)
        conversa(cur, a, "+5518999990004")
        conversa(cur, b, "+5518999990004")


class TestAvaliacao:
    @pytest.mark.parametrize("invalida", [0, 6, -1, 10])
    def test_nota_fora_de_1_a_5_e_recusada(self, cur, invalida):
        # um teste por valor: statement que falha aborta a transacao, e
        # continuar usando o mesmo cursor daria erro de causa diferente
        c = conversa(cur, canal(cur), f"+5518999{abs(invalida):06d}")
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute("UPDATE conversa SET avaliacao=%s WHERE id=%s",
                        (invalida, c))

    @pytest.mark.parametrize("valida", [1, 3, 5])
    def test_nota_de_1_a_5_passa(self, cur, valida):
        c = conversa(cur, canal(cur), f"+55189991{valida:05d}")
        cur.execute("UPDATE conversa SET avaliacao=%s WHERE id=%s", (valida, c))

    def test_avaliacao_nula_e_normal(self, cur):
        # cliente que nao responde NAO e pendencia
        c = conversa(cur, canal(cur), "+5518999990006")
        cur.execute("UPDATE conversa SET resolvida_em=now() WHERE id=%s", (c,))
        cur.execute("SELECT avaliacao FROM conversa WHERE id=%s", (c,))
        assert cur.fetchone()[0] is None


class TestLoginIgnoraCaixa:
    """'Admin' e 'admin' sao a MESMA conta -- nao podem nascer duas."""

    def test_mesmo_login_em_outra_caixa_e_recusado(self, cur):
        cur.execute("INSERT INTO atendente (login,nome) VALUES ('Zezinho','Ze')")
        with pytest.raises(psycopg.errors.UniqueViolation):
            cur.execute("INSERT INTO atendente (login,nome) VALUES ('ZEZINHO','Ze 2')")

    def test_logins_realmente_diferentes_convivem(self, cur):
        cur.execute("INSERT INTO atendente (login,nome) VALUES ('ana','Ana')")
        cur.execute("INSERT INTO atendente (login,nome) VALUES ('ana2','Ana 2')")


class TestFronteiraDoSync:
    def test_origem_so_aceita_harmonit_ou_movizap(self, cur):
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute("INSERT INTO cliente (nome,origem) VALUES ('X','outro')")

    def test_harmonit_id_e_unico_quando_existe(self, cur):
        cur.execute("INSERT INTO cliente (nome,origem,harmonit_id) "
                    "VALUES ('A','harmonit','999')")
        with pytest.raises(psycopg.errors.UniqueViolation):
            cur.execute("INSERT INTO cliente (nome,origem,harmonit_id) "
                        "VALUES ('B','harmonit','999')")

    def test_varias_linhas_movizap_sem_harmonit_id(self, cur):
        # o UNIQUE e parcial: NULL nao colide com NULL
        for n in ("A", "B", "C"):
            cur.execute("INSERT INTO cliente (nome,origem) VALUES (%s,'movizap')", (n,))


class TestSemente:
    def test_os_sete_times_do_chatwoot(self, cur):
        cur.execute("SELECT nome FROM time ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == [
            "Contratual", "Comercial", "Financeiro", "Suporte",
            "Geral", "Pós Venda", "agendamento"]

    def test_todo_time_tem_descricao(self, cur):
        # 🚨 a descricao e ENTRADA DA IA: time sem ela = IA chutando
        cur.execute("SELECT nome FROM time WHERE descricao IS NULL OR descricao=''")
        assert cur.fetchall() == []

    def test_outro_exige_comentario(self, cur):
        cur.execute("SELECT exige_comentario FROM classificacao WHERE nome='Outro'")
        assert cur.fetchone()[0] is True
