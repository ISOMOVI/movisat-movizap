"""Estrela, não-lida, arquivar e o lote — pedido do usuário em 25/08.

🚨 NADA DISTO PEDIU CONSENTIMENTO NOVO. O escopo concedido é `gmail.modify` +
`gmail.send`; o cabeçalho do `gmail.py` dizia `readonly` e estava errado. Foi
a frase, não a permissão, que atrasou estes recursos.

⚠️ O GMAIL É MOCKADO. Estes testes provam a barreira de caixa, o lote e a
gravação local -- não a API do Google. Chamar o Gmail de verdade num teste
mexeria na caixa de alguém.

🚨 Escreve em `email_conta`, `email_mensagem` e `atendente`, tabelas de
PRODUÇÃO. Endereços e login com prefixo `zz`.
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

LOGIN = "zz_teste_acoes_"
ENDERECO = "zz_teste_acoes@movisat.com.br"


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
    """🚨 Nenhum teste fala com o Gmail. `_mexer_rotulo` é o ponto único por
    onde estrela, não-lida e arquivar passam -- mockar aqui cobre os três."""
    chamadas = []

    def falso(mensagem_id, poe, tira, o_que):
        chamadas.append({"id": mensagem_id, "poe": poe, "tira": tira})
        return {"ok": True}

    monkeypatch.setattr(gmail, "_mexer_rotulo", falso)
    yield chamadas


@pytest.fixture()
def cena():
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
    msgs = []
    for i in range(3):
        msgs.append(banco.um(
            """INSERT INTO email_mensagem (conta_id, id_externo, remetente,
                                           assunto, lida)
               VALUES (%s, %s, 'quem@fora.com', %s, true) RETURNING id""",
            (conta, f"zz-acoes-{i}", f"assunto {i}"))["id"])
    yield {"conta": conta, "msgs": msgs, **ids}
    limpar()


def _cliente(sufixo):
    c = TestClient(main.app)
    c.headers.update(
        {"Authorization": f"Bearer {auth.criar_token(LOGIN + sufixo)}"})
    return c


def _estrela(mensagem_id):
    return banco.um("SELECT estrela FROM email_mensagem WHERE id = %s",
                    (mensagem_id,))["estrela"]


class TestEstrela:
    def test_poe_e_tira(self, cena, sem_google):
        c = _cliente("dono")
        assert c.post(f"/api/email/mensagens/{cena['msgs'][0]}/estrela"
                      "?ligada=true").status_code == 200
        assert _estrela(cena["msgs"][0]) is True
        assert c.post(f"/api/email/mensagens/{cena['msgs'][0]}/estrela"
                      "?ligada=false").status_code == 200
        assert _estrela(cena["msgs"][0]) is False

    def test_manda_o_rotulo_certo_para_o_gmail(self, cena, sem_google):
        _cliente("dono").post(
            f"/api/email/mensagens/{cena['msgs'][0]}/estrela?ligada=true")
        assert sem_google[-1]["poe"] == ["STARRED"]
        assert sem_google[-1]["tira"] == []

    def test_estrelar_mensagem_alheia_da_404(self, cena, sem_google):
        r = _cliente("outro").post(
            f"/api/email/mensagens/{cena['msgs'][0]}/estrela?ligada=true")
        assert r.status_code == 404
        assert sem_google == []


class TestNaoLida:
    def test_devolve_para_nao_lida(self, cena, sem_google):
        """O "volto nisso depois". Sem ele, abrir por engano é irreversível
        pela tela."""
        r = _cliente("dono").post(
            f"/api/email/mensagens/{cena['msgs'][0]}/nao-lida")
        assert r.status_code == 200
        assert banco.um("SELECT lida FROM email_mensagem WHERE id = %s",
                        (cena["msgs"][0],))["lida"] is False
        assert sem_google[-1]["poe"] == ["UNREAD"]


class TestLote:
    def test_aplica_nos_tres(self, cena, sem_google):
        r = _cliente("dono").post("/api/email/lote", json={
            "ids": cena["msgs"], "acao": "estrela"})
        assert r.json()["feitas"] == 3
        assert all(_estrela(m) for m in cena["msgs"])

    def test_id_alheio_no_meio_do_lote_NAO_passa(self, cena, sem_google):
        """🚨 Sem conferir item a item, um id de outra caixa no meio de uma
        lista de ids meus passaria despercebido."""
        outra_conta = banco.um(
            """INSERT INTO email_conta (endereco, provedor, ativa, atendente_id)
               VALUES ('zz_outra@movisat.com.br', 'gmail', true, %s)
               RETURNING id""", (cena["outro"],))["id"]
        alheia = banco.um(
            """INSERT INTO email_mensagem (conta_id, id_externo, assunto)
               VALUES (%s, 'zz-alheia', 'segredo') RETURNING id""",
            (outra_conta,))["id"]

        r = _cliente("dono").post("/api/email/lote", json={
            "ids": cena["msgs"] + [alheia], "acao": "estrela"})
        corpo = r.json()
        assert corpo["feitas"] == 3
        assert corpo["falhas"] == 1
        assert _estrela(alheia) is False

    def test_acao_desconhecida_e_recusada(self, cena):
        r = _cliente("dono").post("/api/email/lote", json={
            "ids": cena["msgs"], "acao": "apagar"})
        assert r.status_code == 400

    def test_lote_vazio_e_recusado(self, cena):
        assert _cliente("dono").post(
            "/api/email/lote", json={"ids": [], "acao": "lida"}).status_code == 400

    def test_lote_acima_do_teto_e_recusado(self, cena):
        r = _cliente("dono").post("/api/email/lote", json={
            "ids": list(range(1, main.TETO_LOTE_EMAIL + 20)), "acao": "lida"})
        assert r.status_code == 400
        assert str(main.TETO_LOTE_EMAIL) in r.json()["detail"]

    def test_uma_falha_nao_derruba_as_outras(self, cena, monkeypatch):
        """🚨 Cada item é uma chamada ao Gmail. Uma falhar não pode fazer as
        outras não acontecerem."""
        chamadas = {"n": 0}

        def as_vezes_falha(mensagem_id, poe, tira, o_que):
            chamadas["n"] += 1
            if chamadas["n"] == 2:
                raise gmail.GmailIndisponivel("caiu")
            return {"ok": True}

        monkeypatch.setattr(gmail, "_mexer_rotulo", as_vezes_falha)
        r = _cliente("dono").post("/api/email/lote", json={
            "ids": cena["msgs"], "acao": "estrela"})
        corpo = r.json()
        assert corpo["feitas"] == 2
        assert corpo["falhas"] == 1


class TestAssinaturaComImagem:
    def test_sobe_e_a_ficha_passa_a_dizer_que_tem(self, cena):
        c = _cliente("dono")
        # PNG mínimo de verdade: 1x1 transparente.
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d494844520000000100000001080600000"
            "01f15c4890000000a49444154789c6300010000050001"
            "0d0a2db40000000049454e44ae426082")
        r = c.post("/api/eu/assinatura/imagem",
                   files={"arquivo": ("logo.png", png, "image/png")})
        assert r.status_code == 200
        assert c.get("/api/eu/assinatura").json()["tem_imagem"] is True

    def test_recusa_o_que_nao_e_imagem(self, cena):
        """Assinatura é logo. PDF ou zip aqui viraria anexo quebrado no
        e-mail de todo mundo."""
        r = _cliente("dono").post(
            "/api/eu/assinatura/imagem",
            files={"arquivo": ("x.pdf", b"%PDF-1.4", "application/pdf")})
        assert r.status_code == 400

    def test_recusa_imagem_grande_demais(self, cena):
        gorda = b"\\x89PNG" + b"0" * (main.TETO_ASSINATURA + 10)
        r = _cliente("dono").post(
            "/api/eu/assinatura/imagem",
            files={"arquivo": ("g.png", gorda, "image/png")})
        assert r.status_code == 400

    def test_tirar_volta_para_o_html(self, cena):
        c = _cliente("dono")
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d494844520000000100000001080600000"
            "01f15c4890000000a49444154789c6300010000050001"
            "0d0a2db40000000049454e44ae426082")
        c.post("/api/eu/assinatura/imagem",
               files={"arquivo": ("logo.png", png, "image/png")})
        assert c.delete("/api/eu/assinatura/imagem").status_code == 200
        assert c.get("/api/eu/assinatura").json()["tem_imagem"] is False
