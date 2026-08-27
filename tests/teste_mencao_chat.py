"""Menção no chat interno — migração 037, 27/08.

Pedido do usuário: *"interessante e pode ser, tanto no interno quanto no do
whatsa"*.

🚨 O QUE ISTO DEFENDE. Menção não é enfeite: é o aviso de que alguém precisa de
você. Os dois jeitos de estragá-la são silenciosos:

  1. **aceitar e ignorar** — chamar quem não está na sala, a mensagem sair, e
     a pessoa nunca ver. É o "parâmetro aceito e ignorado", que este projeto
     cataloga como o pior defeito;
  2. **guardar só a última** — foi o que a 034 fez com a reação e a 036 teve
     de desfazer. Uma mensagem pode chamar três pessoas.

🚨 MEDE COMPORTAMENTO, NÃO NOME. Cada teste chama a função e **relê o estado**;
nenhum procura a palavra "mencao" no fonte.

⚠️ Escreve em tabelas de PRODUÇÃO com logins `zz`, e apaga só o que criou.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, chat  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_mencao_"


def limpar():
    alvo = """(SELECT sala_id FROM chat_membro WHERE atendente_id IN
                 (SELECT id FROM atendente WHERE login LIKE %s)
               UNION
               SELECT sala_id FROM chat_mensagem WHERE atendente_id IN
                 (SELECT id FROM atendente WHERE login LIKE %s))"""
    banco.executar(f"DELETE FROM chat_sala WHERE id IN {alvo}",
                   (LOGIN + "%", LOGIN + "%"))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def sala():
    """Um grupo com três pessoas, e uma quarta FORA dele."""
    limpar()
    ids = {}
    for n in ("ana", "bruno", "carla", "dora"):
        ids[n] = banco.um(
            """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
               VALUES (%s, %s, %s, 'x', 'atendimento', true) RETURNING id""",
            (f"Teste {n}", LOGIN + n, f"{LOGIN}{n}@movisat.com.br"))["id"]
    grupo = chat.criar_grupo("zz sala da menção", ids["ana"],
                             [ids["bruno"], ids["carla"]])
    yield {"ids": ids, "sala_id": grupo["sala_id"]}
    limpar()


class TestGravaEDevolve:
    def test_a_mencao_chega_na_mensagem(self, sala):
        ids, s = sala["ids"], sala["sala_id"]
        r = chat.escrever(s, ids["ana"], "@Teste bruno olha isso", [ids["bruno"]])
        assert r["ok"] is True
        # Relê o estado: o que vale é o que o banco gravou.
        msgs = chat.mensagens(s, ids["bruno"])
        ultima = msgs[-1]
        assert [c["id"] for c in ultima["mencionados"]] == [ids["bruno"]]

    def test_uma_mensagem_chama_VARIAS_pessoas(self, sala):
        """🚨 A lição da 034→036: coluna única guarda a última e apaga as
        outras em silêncio. Aqui as duas têm de sobreviver."""
        ids, s = sala["ids"], sala["sala_id"]
        chat.escrever(s, ids["ana"], "@bruno @carla os dois",
                      [ids["bruno"], ids["carla"]])
        ultima = chat.mensagens(s, ids["ana"])[-1]
        assert sorted(c["id"] for c in ultima["mencionados"]) == \
               sorted([ids["bruno"], ids["carla"]])

    def test_me_chamou_vem_pronto_e_e_por_pessoa(self, sala):
        """A tela não deve descobrir isso comparando ids: quem sabe quem é
        "eu" nesta requisição é quem a atendeu."""
        ids, s = sala["ids"], sala["sala_id"]
        chat.escrever(s, ids["ana"], "@bruno", [ids["bruno"]])
        assert chat.mensagens(s, ids["bruno"])[-1]["me_chamou"] is True
        assert chat.mensagens(s, ids["carla"])[-1]["me_chamou"] is False

    def test_mensagem_sem_mencao_traz_lista_vazia_e_nao_estoura(self, sala):
        ids, s = sala["ids"], sala["sala_id"]
        chat.escrever(s, ids["ana"], "sem chamar ninguém")
        ultima = chat.mensagens(s, ids["ana"])[-1]
        assert ultima["mencionados"] == []
        assert ultima["me_chamou"] is False


class TestRecusa:
    def test_chamar_quem_NAO_esta_na_sala_e_recusado(self, sala):
        """🚨 O DEFEITO QUE ISTO IMPEDE: aceitar e ignorar faria a pessoa achar
        que avisou alguém que nunca vai ver a mensagem."""
        ids, s = sala["ids"], sala["sala_id"]
        r = chat.escrever(s, ids["ana"], "@dora socorro", [ids["dora"]])
        assert r["ok"] is False
        assert "Teste dora" in r["motivo"], "a recusa tem de dizer QUEM não está"

    def test_a_mensagem_recusada_NAO_e_gravada(self, sala):
        """⚠️ Meia gravação seria pior que nenhuma: a mensagem apareceria
        enviada e ninguém teria sido chamado."""
        ids, s = sala["ids"], sala["sala_id"]
        antes = len(chat.mensagens(s, ids["ana"]))
        chat.escrever(s, ids["ana"], "@dora socorro", [ids["dora"]])
        assert len(chat.mensagens(s, ids["ana"])) == antes

    def test_repetir_a_mesma_pessoa_nao_duplica(self, sala):
        ids, s = sala["ids"], sala["sala_id"]
        chat.escrever(s, ids["ana"], "@bruno @bruno", [ids["bruno"], ids["bruno"]])
        assert len(chat.mensagens(s, ids["ana"])[-1]["mencionados"]) == 1

    def test_quem_nao_e_da_sala_nao_escreve_nem_com_mencao_valida(self, sala):
        ids, s = sala["ids"], sala["sala_id"]
        r = chat.escrever(s, ids["dora"], "@bruno", [ids["bruno"]])
        assert r["ok"] is False


class TestNaoLidas:
    def test_a_mencao_aparece_como_nao_lida_para_quem_foi_chamado(self, sala):
        ids, s = sala["ids"], sala["sala_id"]
        chat.escrever(s, ids["ana"], "@bruno", [ids["bruno"]])
        salas = chat.mencoes_nao_lidas(ids["bruno"])
        assert [x["sala_id"] for x in salas] == [s]
        assert salas[0]["quantas"] == 1

    def test_quem_NAO_foi_chamado_nao_ve_mencao_nenhuma(self, sala):
        ids, s = sala["ids"], sala["sala_id"]
        chat.escrever(s, ids["ana"], "@bruno", [ids["bruno"]])
        assert chat.mencoes_nao_lidas(ids["carla"]) == []

    def test_quem_ESCREVE_nao_se_menciona_para_si(self, sala):
        """Quem escreveu leu — vale para menção como já valia para mensagem."""
        ids, s = sala["ids"], sala["sala_id"]
        chat.escrever(s, ids["ana"], "@ana eu mesma", [ids["ana"]])
        assert chat.mencoes_nao_lidas(ids["ana"]) == []

    def test_ler_a_sala_zera_a_mencao(self, sala):
        """⚠️ Usa o MESMO `lido_ate` do resto: não há segundo marcador para
        dessincronizar."""
        ids, s = sala["ids"], sala["sala_id"]
        chat.escrever(s, ids["ana"], "@bruno", [ids["bruno"]])
        assert chat.mencoes_nao_lidas(ids["bruno"])
        chat.marcar_lido(s, ids["bruno"])
        assert chat.mencoes_nao_lidas(ids["bruno"]) == []

    def test_apagar_a_mensagem_leva_a_mencao_junto(self, sala):
        """`ON DELETE CASCADE`: menção sem mensagem não significa nada."""
        ids, s = sala["ids"], sala["sala_id"]
        r = chat.escrever(s, ids["ana"], "@bruno", [ids["bruno"]])
        banco.executar("DELETE FROM chat_mensagem WHERE id = %s", (r["mensagem_id"],))
        sobrou = banco.um("SELECT COUNT(*) n FROM chat_mencao WHERE mensagem_id = %s",
                          (r["mensagem_id"],))
        assert sobrou["n"] == 0


class TestTeto:
    def test_o_teto_de_mencoes_e_MEU_e_esta_rotulado(self):
        """🔵 Não há decisão do usuário sobre este número. O teste existe para
        que ele apareça quando alguém for procurar de onde saiu."""
        assert chat.TETO_MENCOES == 20
