"""Grupo do WhatsApp — a conversa deixa de ser sempre um telefone.

Migrações 027 e 028. O que se protege aqui:

  · grupo entra sem telefone, com o JID como identidade;
  · o índice único continua impedindo conversa duplicada, agora por JID;
  · grupo fica na MESMA lista da conversa direta, como no WhatsApp;
  · o envio vai para o JID inteiro, não para os dígitos dele;
  · quem falou no grupo é guardado por mensagem.

🚨 Escreve em `conversa` e `mensagem`, tabelas de PRODUÇÃO. JID de teste com
prefixo `zz` e telefone de DDD inexistente.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas, evolution  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

JID = "zz120363000000000001@g.us"
JID2 = "zz120363000000000002@g.us"
FONE = "+5599977770000"


def limpar():
    for chave in (JID, JID2):
        banco.executar(
            """DELETE FROM mensagem WHERE conversa_id IN
               (SELECT id FROM conversa WHERE grupo_jid = %s)""", (chave,))
        banco.executar("DELETE FROM conversa WHERE grupo_jid = %s", (chave,))
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (FONE,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (FONE,))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def canal():
    limpar()
    c = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not c:
        pytest.skip("canal atendimento não cadastrado")
    yield c["id"]
    limpar()


def criar_grupo(canal_id, jid=JID, nome="zz Grupo de Teste"):
    with banco.cursor() as cur:
        return conversas.garantir_conversa(cur, canal_id, None,
                                           grupo_jid=jid, grupo_nome=nome)


class TestOModeloAceitaGrupo:
    def test_grupo_nasce_sem_telefone(self, canal):
        cid = criar_grupo(canal)
        linha = banco.um(
            "SELECT tipo, telefone_e164, grupo_jid, grupo_nome "
            "  FROM conversa WHERE id = %s", (cid,))
        assert linha["tipo"] == "grupo"
        assert linha["telefone_e164"] is None
        assert linha["grupo_jid"] == JID
        assert linha["grupo_nome"] == "zz Grupo de Teste"

    def test_conversa_direta_continua_nascendo_direta(self, canal):
        with banco.cursor() as cur:
            cid = conversas.garantir_conversa(cur, canal, FONE)
        linha = banco.um(
            "SELECT tipo, grupo_jid FROM conversa WHERE id = %s", (cid,))
        assert linha["tipo"] == "direta"
        assert linha["grupo_jid"] is None

    def test_o_banco_recusa_conversa_sem_identidade(self, canal):
        """O CHECK `ck_conversa_identidade`: cada tipo tem a SUA chave."""
        import psycopg
        with pytest.raises(psycopg.errors.CheckViolation):
            banco.executar(
                """INSERT INTO conversa (canal_id, tipo, estado)
                   VALUES (%s, 'direta', 'nova')""", (canal,))

    def test_o_banco_recusa_grupo_com_telefone(self, canal):
        import psycopg
        with pytest.raises(psycopg.errors.CheckViolation):
            banco.executar(
                """INSERT INTO conversa (canal_id, tipo, grupo_jid,
                                         telefone_e164, estado)
                   VALUES (%s, 'grupo', %s, %s, 'nova')""",
                (canal, JID, FONE))


class TestNaoDuplica:
    def test_o_mesmo_grupo_devolve_a_MESMA_conversa(self, canal):
        """🚨 O índice único passou a ser por `COALESCE(grupo_jid, telefone)`.
        Sem isso, duas mensagens chegando juntas partiriam o grupo em duas
        telas -- o mesmo defeito que o índice antigo já evitava por telefone."""
        assert criar_grupo(canal) == criar_grupo(canal)

    def test_grupos_diferentes_sao_conversas_diferentes(self, canal):
        assert criar_grupo(canal, JID) != criar_grupo(canal, JID2)

    def test_o_nome_do_grupo_e_ATUALIZADO_quando_muda(self, canal):
        """O nome muda no WhatsApp e o webhook traz o atual."""
        cid = criar_grupo(canal, JID, "zz Nome Velho")
        criar_grupo(canal, JID, "zz Nome Novo")
        assert banco.um("SELECT grupo_nome FROM conversa WHERE id = %s",
                        (cid,))["grupo_nome"] == "zz Nome Novo"


class TestGrupoFicaNaMESMALista:
    """🚨 A 027 tinha criado uma aba "Grupos"; a 028 desfez, três horas depois.

    O usuário apontou a contradição: eu propus como régua que o atendente não
    deve sentir que trocou de aplicativo, e desenhei uma aba que o WhatsApp
    não tem.

    E a aba resolvia um problema que quase não existe: o painel NÃO importa
    grupo. A conversa só nasce quando CHEGA MENSAGEM -- dos 62 grupos de que o
    número participa, só entram os que falam.
    """

    def test_grupo_aparece_na_caixa_de_entrada(self, canal):
        cid = criar_grupo(canal)
        assert cid in [c["id"] for c in conversas.listar()]

    def test_grupo_e_conversa_direta_vem_na_MESMA_chamada(self, canal):
        grupo = criar_grupo(canal)
        with banco.cursor() as cur:
            direta = conversas.garantir_conversa(cur, canal, FONE)
        ids = [c["id"] for c in conversas.listar()]
        assert grupo in ids and direta in ids

    def test_a_lista_diz_qual_e_qual(self, canal):
        """A tela precisa saber desenhar o ícone e o nome certos."""
        cid = criar_grupo(canal)
        linha = next(c for c in conversas.listar() if c["id"] == cid)
        assert linha["tipo"] == "grupo"
        assert linha["grupo_nome"] == "zz Grupo de Teste"
        assert linha["telefone_e164"] is None

    def test_grupo_sem_dono_entra_na_fila(self, canal):
        """Grupo é atendimento como qualquer outro: sem dono, está esperando."""
        cid = criar_grupo(canal)
        na_fila = [c["id"] for g in conversas.fila() for c in g["conversas"]]
        assert cid in na_fila

    def test_nao_existe_mais_coluna_atender(self):
        """Coluna morta esperando um recurso que ninguém pediu é dívida."""
        cols = [r["column_name"] for r in banco.varios(
            "SELECT column_name FROM information_schema.columns "
            " WHERE table_name = 'conversa'")]
        assert "atender" not in cols


class TestOEnvioVaiParaOJID:
    @pytest.mark.parametrize("entrada,esperado", [
        ("120363000000000001@g.us", "120363000000000001@g.us"),
        ("+5518998116168", "5518998116168"),
        ("(18) 99811-6168", "18998116168"),
        ("", ""),
        (None, ""),
    ])
    def test_destino_para_evolution(self, entrada, esperado):
        """🚨 Tirar o que não é dígito de um JID deixaria só o número do grupo,
        sem o `@g.us` -- e o Evolution mandaria a resposta para um telefone
        que não existe. A API aceita e a mensagem some."""
        assert evolution.destino_para_evolution(entrada) == esperado

    def test_responder_em_grupo_manda_para_o_JID(self, canal, monkeypatch):
        cid = criar_grupo(canal)
        enviados = []

        def fingir(instancia, destino, texto, citando=None):
            enviados.append(destino)
            return {"id_externo": "TESTE_GRUPO_1"}

        monkeypatch.setattr(evolution, "enviar_texto", fingir)
        r = conversas.responder(cid, "oi grupo", None)
        assert r["ok"] is True, r.get("motivo")
        assert enviados == [JID], "a resposta não foi para o grupo"

    def test_responder_em_conversa_direta_continua_indo_para_o_telefone(
            self, canal, monkeypatch):
        with banco.cursor() as cur:
            cid = conversas.garantir_conversa(cur, canal, FONE)
        enviados = []
        monkeypatch.setattr(evolution, "enviar_texto",
                            lambda i, d, t, citando=None: enviados.append(d)
                            or {"id_externo": "TESTE_DIRETA_1"})
        conversas.responder(cid, "oi", None)
        assert enviados == [FONE]


class TestQuemFalouNoGrupo:
    def test_a_coluna_existe_e_aceita_o_remetente(self, canal):
        """Num grupo de quinze, sem isto o histórico vira monólogo de autor
        desconhecido."""
        cid = criar_grupo(canal)
        banco.executar(
            """INSERT INTO mensagem (conversa_id, direcao, autor, tipo,
                                     conteudo, criada_em,
                                     remetente_jid, remetente_nome)
               VALUES (%s, 'entrada', 'cliente', 'texto', 'oi', now(), %s, %s)""",
            (cid, "5518998116168@s.whatsapp.net", "Fulano"))
        m = conversas.mensagens(cid)[-1]
        assert m["remetente_nome"] == "Fulano"
        assert m["remetente_jid"].startswith("5518998116168")

    def test_conversa_direta_nao_guarda_remetente(self, canal):
        """Repetir o mesmo telefone em toda linha não diz nada."""
        with banco.cursor() as cur:
            cid = conversas.garantir_conversa(cur, canal, FONE)
        banco.executar(
            """INSERT INTO mensagem (conversa_id, direcao, autor, tipo,
                                     conteudo, criada_em)
               VALUES (%s, 'entrada', 'cliente', 'texto', 'oi', now())""",
            (cid,))
        assert conversas.mensagens(cid)[-1]["remetente_nome"] is None


class TestNadaMudouParaQuemJaExistia:
    def test_toda_conversa_direta_tem_telefone_e_nenhum_jid(self):
        errado = banco.um(
            """SELECT count(*) n FROM conversa
                WHERE tipo = 'direta'
                  AND (telefone_e164 IS NULL OR grupo_jid IS NOT NULL)""")["n"]
        assert errado == 0

    def test_o_indice_unico_e_por_identidade(self):
        d = banco.um("SELECT indexdef d FROM pg_indexes WHERE indexname = %s",
                     ("ux_conversa_aberta",))["d"]
        assert "COALESCE" in d and "grupo_jid" in d
