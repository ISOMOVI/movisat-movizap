"""Excluir, restaurar e a varredura de exclusão do Gmail -- 17/09.

🔵 Pedido dele: "não temos lixeira também no movizap? não deveria se
espelhado o uso?" -- e resolve de quebra a lacuna que a mesma pergunta
achou: "arquivada" existe desde a 014 e nunca teve tela própria.

🚨 O GMAIL É MOCKADO, mesma regra do teste_email_acoes.py: `_mexer_rotulo`
é o ponto único por onde estrela, não-lida, arquivar, excluir e restaurar
passam -- mockar aqui cobre os cinco sem falar com a rede.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, gmail, main  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_lixeira_"
ENDERECO = "zz_teste_lixeira@movisat.com.br"


def limpar():
    banco.executar(
        """DELETE FROM email_mensagem WHERE conta_id IN
           (SELECT id FROM email_conta WHERE endereco LIKE %s)""", ("zz_%",))
    banco.executar("DELETE FROM email_conta WHERE endereco LIKE %s", ("zz_%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture(autouse=True)
def sem_google(monkeypatch):
    chamadas = []

    def falso(mensagem_id, poe, tira, o_que):
        chamadas.append({"id": mensagem_id, "poe": poe, "tira": tira, "o_que": o_que})
        return {"ok": True}

    monkeypatch.setattr(gmail, "_mexer_rotulo", falso)
    yield chamadas


@pytest.fixture()
def cena():
    limpar()
    dono = banco.um(
        """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
           VALUES ('Teste', %s, %s, 'x', 'atendimento', true) RETURNING id""",
        (LOGIN + "dono", f"{LOGIN}dono@movisat.com.br"))["id"]
    conta = banco.um(
        """INSERT INTO email_conta (endereco, provedor, ativa, atendente_id)
           VALUES (%s, 'gmail', true, %s) RETURNING id""",
        (ENDERECO, dono))["id"]
    msg = banco.um(
        """INSERT INTO email_mensagem (conta_id, id_externo, remetente,
                                       assunto, lida, arquivada)
           VALUES (%s, 'zz-lixeira-1', 'quem@fora.com', 'assunto', true, false)
           RETURNING id""", (conta,))["id"]
    yield {"conta": conta, "msg": msg, "dono": dono}
    limpar()


def _cliente():
    c = TestClient(main.app)
    c.headers.update(
        {"Authorization": f"Bearer {auth.criar_token(LOGIN + 'dono')}"})
    return c


class TestExcluir:

    def test_manda_para_a_lixeira_no_gmail_tambem(self, cena, sem_google):
        r = _cliente().post(f"/api/email/mensagens/{cena['msg']}/excluir")
        assert r.status_code == 200
        assert sem_google[-1]["poe"] == ["TRASH"]
        assert sem_google[-1]["tira"] == ["INBOX"]

    def test_marca_na_lixeira_desde(self, cena, sem_google):
        _cliente().post(f"/api/email/mensagens/{cena['msg']}/excluir")
        linha = banco.um(
            "SELECT na_lixeira_desde FROM email_mensagem WHERE id = %s",
            (cena["msg"],))
        assert linha["na_lixeira_desde"] is not None

    def test_some_da_aba_entrada(self, cena, sem_google):
        _cliente().post(f"/api/email/mensagens/{cena['msg']}/excluir")
        r = _cliente().get("/api/email/mensagens?caixa=entrada")
        assert cena["msg"] not in {m["id"] for m in r.json()["mensagens"]}

    def test_aparece_na_aba_lixeira(self, cena, sem_google):
        _cliente().post(f"/api/email/mensagens/{cena['msg']}/excluir")
        r = _cliente().get("/api/email/mensagens?caixa=lixeira")
        assert cena["msg"] in {m["id"] for m in r.json()["mensagens"]}


class TestRestaurar:

    def test_devolve_para_o_inbox_no_gmail(self, cena, sem_google):
        """🚨 O `untrash` SOZINHO NÃO DEVOLVE O INBOX -- medido ao vivo em
        17/09. Sem este `poe=["INBOX"]` explícito, restaurar deixaria a
        mensagem invisível em toda tela do Gmail, mesmo sem ter sido apagada."""
        banco.executar(
            "UPDATE email_mensagem SET na_lixeira_desde = now() WHERE id = %s",
            (cena["msg"],))
        r = _cliente().post(f"/api/email/mensagens/{cena['msg']}/restaurar")
        assert r.status_code == 200
        assert sem_google[-1]["poe"] == ["INBOX"]
        assert sem_google[-1]["tira"] == ["TRASH"]

    def test_some_da_lixeira_e_volta_para_entrada(self, cena, sem_google):
        banco.executar(
            "UPDATE email_mensagem SET na_lixeira_desde = now() WHERE id = %s",
            (cena["msg"],))
        _cliente().post(f"/api/email/mensagens/{cena['msg']}/restaurar")
        entrada = {m["id"] for m in
                  _cliente().get("/api/email/mensagens?caixa=entrada")
                  .json()["mensagens"]}
        lixeira = {m["id"] for m in
                  _cliente().get("/api/email/mensagens?caixa=lixeira")
                  .json()["mensagens"]}
        assert cena["msg"] in entrada
        assert cena["msg"] not in lixeira


class TestAbaArquivadas:
    """🚨 A LACUNA QUE A MESMA PERGUNTA ACHOU. `arquivada` existe desde a
    014 e nunca teve tela para ver de novo -- só sumia."""

    def test_arquivada_tem_aba_propria_agora(self, cena):
        banco.executar(
            "UPDATE email_mensagem SET arquivada = true WHERE id = %s",
            (cena["msg"],))
        entrada = {m["id"] for m in
                  _cliente().get("/api/email/mensagens?caixa=entrada")
                  .json()["mensagens"]}
        arquivadas = {m["id"] for m in
                     _cliente().get("/api/email/mensagens?caixa=arquivadas")
                     .json()["mensagens"]}
        assert cena["msg"] not in entrada
        assert cena["msg"] in arquivadas

    def test_arquivada_e_na_lixeira_ao_mesmo_tempo_so_conta_como_lixeira(self, cena):
        """Não pode aparecer nas duas abas: se o Gmail a mandou para a
        lixeira, ela é lixeira, mesmo que também tenha sido arquivada antes."""
        banco.executar(
            "UPDATE email_mensagem SET arquivada = true, na_lixeira_desde = now() "
            " WHERE id = %s", (cena["msg"],))
        arquivadas = {m["id"] for m in
                     _cliente().get("/api/email/mensagens?caixa=arquivadas")
                     .json()["mensagens"]}
        lixeira = {m["id"] for m in
                  _cliente().get("/api/email/mensagens?caixa=lixeira")
                  .json()["mensagens"]}
        assert cena["msg"] not in arquivadas
        assert cena["msg"] in lixeira


class TestSincronizarExclusoes:
    """A varredura em si -- `sincronizar_exclusoes`, com o Gmail mockado
    aqui por dentro (não pelo `_mexer_rotulo`, que é só para as ações)."""

    def _mockar_listagem(self, monkeypatch, sem_lixeira: set, com_lixeira: set):
        def falso_pedir(cliente, caminho, **params):
            if caminho == "/messages":
                ids = com_lixeira if params.get("includeSpamTrash") else sem_lixeira
                return {"messages": [{"id": i} for i in ids]}
            return {}
        monkeypatch.setattr(gmail, "_pedir", falso_pedir)
        monkeypatch.setattr(gmail, "_token_de_acesso", lambda conta: "x")

    def test_mensagem_que_sumiu_das_duas_listas_vira_sumida(self, cena, monkeypatch):
        self._mockar_listagem(monkeypatch, sem_lixeira=set(), com_lixeira=set())
        r = gmail.sincronizar_exclusoes(cena["conta"])
        assert r["sumidas_de_vez"] == 1
        linha = banco.um(
            "SELECT sumida_do_gmail_em FROM email_mensagem WHERE id = %s",
            (cena["msg"],))
        assert linha["sumida_do_gmail_em"] is not None

    def test_mensagem_so_na_lista_com_lixeira_vira_na_lixeira(self, cena, monkeypatch):
        self._mockar_listagem(monkeypatch, sem_lixeira=set(),
                              com_lixeira={"zz-lixeira-1"})
        r = gmail.sincronizar_exclusoes(cena["conta"])
        assert r["foram_para_lixeira"] == 1
        linha = banco.um(
            "SELECT na_lixeira_desde FROM email_mensagem WHERE id = %s",
            (cena["msg"],))
        assert linha["na_lixeira_desde"] is not None

    def test_restauracao_direto_no_gmail_chega_ao_painel(self, cena, monkeypatch):
        """Alguém restaura pelo APP do Gmail, sem passar pelo nosso botão --
        a varredura tem de perceber sozinha na próxima rodada."""
        banco.executar(
            "UPDATE email_mensagem SET na_lixeira_desde = now() WHERE id = %s",
            (cena["msg"],))
        self._mockar_listagem(monkeypatch, sem_lixeira={"zz-lixeira-1"},
                              com_lixeira={"zz-lixeira-1"})
        r = gmail.sincronizar_exclusoes(cena["conta"])
        assert r["restauradas"] == 1
        linha = banco.um(
            "SELECT na_lixeira_desde FROM email_mensagem WHERE id = %s",
            (cena["msg"],))
        assert linha["na_lixeira_desde"] is None

    def test_mensagem_ativa_nao_gera_ruido(self, cena, monkeypatch):
        """Idempotência: rodar contra o estado normal não deve tocar em nada."""
        self._mockar_listagem(monkeypatch, sem_lixeira={"zz-lixeira-1"},
                              com_lixeira={"zz-lixeira-1"})
        r = gmail.sincronizar_exclusoes(cena["conta"])
        assert r == {"contas": 1, "foram_para_lixeira": 0,
                     "restauradas": 0, "sumidas_de_vez": 0}
