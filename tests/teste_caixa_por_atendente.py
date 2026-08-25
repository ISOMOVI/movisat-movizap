"""A caixa de e-mail é de quem a conectou — migração 030 (2026-08-25).

🚨 POR QUE ESTE ARQUIVO EXISTE. O usuário avisou em 25/08 que outra pessoa
entraria no painel. Medido antes: os 5 atendentes têm perfil que dá `EML_1.1`
e NENHUMA rota de e-mail filtrava por conta -- o próximo login abriria a caixa
do owner inteira. Não dava erro e não travava o acesso: funcionava, que é o
pior jeito de vazar.

⚠️ O que se prova aqui é a ROTA, não a função. O vazamento morava exatamente
no lugar onde a função estava certa e ninguém perguntava de quem era a caixa.

🚨 Escreve em `email_conta`, `email_mensagem` e `atendente`, tabelas de
PRODUÇÃO. Endereços com prefixo `zz` e login com prefixo `zz`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_caixa_"
ENDERECO = "zz_teste_caixa@movisat.com.br"


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


@pytest.fixture()
def cena():
    """Dois atendentes; só o primeiro tem caixa, com uma mensagem dentro."""
    limpar()
    ids = {}
    for papel in ("dono", "outro"):
        ids[papel] = banco.um(
            """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
               VALUES (%s, %s, %s, 'x', 'atendimento', true) RETURNING id""",
            (f"Teste {papel}", LOGIN + papel,
             f"{LOGIN}{papel}@movisat.com.br"))["id"]
    conta = banco.um(
        """INSERT INTO email_conta (endereco, provedor, ativa, atendente_id)
           VALUES (%s, 'gmail', true, %s) RETURNING id""",
        (ENDERECO, ids["dono"]))["id"]
    msg = banco.um(
        """INSERT INTO email_mensagem (conta_id, id_externo, remetente, assunto)
           VALUES (%s, 'zz-externo-1', 'quem@fora.com', 'assunto secreto')
           RETURNING id""", (conta,))["id"]
    yield {"conta": conta, "mensagem": msg, **ids}
    limpar()


def _cliente(login_sufixo):
    c = TestClient(main.app)
    c.headers.update(
        {"Authorization": f"Bearer {auth.criar_token(LOGIN + login_sufixo)}"})
    return c


class TestCadaUmVeAQueConectou:
    def test_o_dono_ve_a_propria_caixa(self, cena):
        r = _cliente("dono").get("/api/email/caixas")
        assert r.status_code == 200
        assert [c["id"] for c in r.json()["caixas"]] == [cena["conta"]]

    def test_quem_nao_conectou_nao_ve_caixa_nenhuma(self, cena):
        """🚨 O CASO QUE VAZAVA. Lista vazia é resposta legítima -- quem nunca
        conectou vê a tela com o convite, não a caixa do vizinho."""
        r = _cliente("outro").get("/api/email/caixas")
        assert r.json()["caixas"] == []

    def test_a_lista_de_mensagens_do_outro_vem_vazia(self, cena):
        r = _cliente("outro").get("/api/email/mensagens")
        assert r.status_code == 200
        assert r.json()["mensagens"] == []

    def test_o_dono_ve_a_mensagem(self, cena):
        ids = [m["id"] for m in
               _cliente("dono").get("/api/email/mensagens").json()["mensagens"]]
        assert cena["mensagem"] in ids


class TestAdivinharOIdNaoServe:
    """As rotas de AÇÃO recebiam só o id e chamavam o módulo direto."""

    def test_abrir_mensagem_alheia_da_404(self, cena):
        r = _cliente("outro").get(f"/api/email/mensagens/{cena['mensagem']}")
        assert r.status_code == 404

    def test_vincular_mensagem_alheia_da_404(self, cena):
        r = _cliente("outro").post(
            f"/api/email/mensagens/{cena['mensagem']}/vincular",
            json={"cliente_id": 1})
        assert r.status_code == 404

    def test_marcar_lida_alheia_da_404(self, cena):
        r = _cliente("outro").post(
            f"/api/email/mensagens/{cena['mensagem']}/lida", json={})
        assert r.status_code == 404

    def test_pedir_caixa_alheia_pelo_conta_id_da_404(self, cena):
        """404 e não 403: dizer "existe, mas não é sua" já entrega que aquele
        endereço está conectado por alguém."""
        r = _cliente("outro").get(
            f"/api/email/mensagens?conta_id={cena['conta']}")
        assert r.status_code == 404


class TestEnviarNaoPegaAPrimeiraCaixa:
    def test_sem_caixa_nenhuma_recusa_com_explicacao(self, cena):
        """🚨 ANTES ISSO PEGAVA `SELECT ... ativa LIMIT 1` -- ou seja, a caixa
        de OUTRA pessoa, e o cliente responderia para o endereço errado."""
        r = _cliente("outro").post("/api/email/enviar", json={
            "para": "alguem@fora.com", "assunto": "x", "corpo": "y"})
        assert r.status_code == 409
        assert "caixa conectada" in r.json()["detail"]

    def test_enviar_por_caixa_alheia_da_404(self, cena):
        r = _cliente("outro").post("/api/email/enviar", json={
            "para": "alguem@fora.com", "assunto": "x", "corpo": "y",
            "conta_id": cena["conta"]})
        assert r.status_code == 404


class TestDuasPessoasPodemLigarOMesmoEndereco:
    def test_o_mesmo_endereco_em_duas_contas_e_permitido(self, cena):
        """Decisão do usuário em 25/08: "a outra aba deve adicionar outras
        caixas mesmo que sejam iguais também". O UNIQUE de `endereco` saiu; o
        que fica é UNIQUE (atendente_id, endereco)."""
        segunda = banco.um(
            """INSERT INTO email_conta (endereco, provedor, ativa, atendente_id)
               VALUES (%s, 'gmail', true, %s) RETURNING id""",
            (ENDERECO, cena["outro"]))["id"]
        assert segunda != cena["conta"]
        # E cada um continua vendo só a sua linha.
        minhas = _cliente("outro").get("/api/email/caixas").json()["caixas"]
        assert [c["id"] for c in minhas] == [segunda]

    def test_a_mesma_pessoa_nao_liga_a_mesma_caixa_duas_vezes(self, cena):
        import psycopg
        with pytest.raises(psycopg.errors.UniqueViolation):
            banco.executar(
                """INSERT INTO email_conta (endereco, provedor, ativa, atendente_id)
                   VALUES (%s, 'gmail', true, %s)""",
                (ENDERECO, cena["dono"]))
