"""Outros contatos da empresa: a lista do modal da ficha (Bloco 6, 15/10).

🚨 Escreve em `cliente`, `contato`, `contato_telefone`, `contato_papel`,
`atendente` e `conversa`, tabelas de PRODUÇÃO. Cliente `Zz Teste Outros`,
login `zz_teste_outros_` e números `+55189777710xx`; tudo apagado no fim.

O que estes testes guardam:
  · CADA TELEFONE É UMA LINHA -- contato com dois números dá duas linhas;
  · contato SEM telefone aparece mesmo assim, com `e164` nulo: esconder quem
    não tem número faria a lista afirmar "a empresa tem 2 contatos" onde ela
    tem 3;
  · `tem_whatsapp` tem TRÊS valores, e `false` não se confunde com `None`;
  · o contato DESTA conversa vem marcado e primeiro;
  · lista vazia vem com `motivo` -- "sem_cadastro" não é "empresa sem outro
    contato";
  · a rota é `ATD_1.2`: quem atende entra, e é o ponto todo de ela existir
    (a rota de cadastro é `CAD_1.1` e daria 403).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_outros_"
CLIENTE = "Zz Teste Outros"
NUM_ATUAL = "+5518977771001"      # o número da conversa, do contato A
NUM_SEGUNDO_DE_A = "+5518977771002"  # o MESMO contato A, outro número
NUM_SEM_WHATS = "+5518977771003"  # contato B, tem_whatsapp = false
NUM_NAO_VERIFICADO = "+5518977771004"  # contato B, tem_whatsapp = NULL
NUM_AVULSO = "+5518977771009"     # conversa sem cadastro nenhum
TODOS = [NUM_ATUAL, NUM_SEGUNDO_DE_A, NUM_SEM_WHATS, NUM_NAO_VERIFICADO, NUM_AVULSO]


def limpar():
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = ANY(%s)", (TODOS,))
    banco.executar("""DELETE FROM contato_papel WHERE contato_id IN
                       (SELECT id FROM contato WHERE nome LIKE %s)""", (CLIENTE + "%",))
    banco.executar("""DELETE FROM contato_telefone WHERE contato_id IN
                       (SELECT id FROM contato WHERE nome LIKE %s)""", (CLIENTE + "%",))
    banco.executar("DELETE FROM contato WHERE nome LIKE %s", (CLIENTE + "%",))
    banco.executar("DELETE FROM cliente WHERE nome LIKE %s", (CLIENTE + "%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def cena():
    banco.abrir()
    limpar()
    with banco.cursor() as cur:
        cur.execute("""INSERT INTO cliente (nome, nome_fantasia, ativo, origem)
                       VALUES (%s, 'Zz Fantasia', true, 'movizap') RETURNING id""",
                    (CLIENTE + " SA",))
        cliente_id = cur.fetchone()["id"]

        def pessoa(nome):
            cur.execute("""INSERT INTO contato (cliente_id, nome, origem, ativo)
                           VALUES (%s, %s, 'movizap', true) RETURNING id""",
                        (cliente_id, nome))
            return cur.fetchone()["id"]

        a = pessoa(CLIENTE + " A")
        b = pessoa(CLIENTE + " B")
        c = pessoa(CLIENTE + " C sem telefone")

        def fone(contato_id, e164, principal=False, whats=None):
            cur.execute("""INSERT INTO contato_telefone
                             (contato_id, e164, bruto, principal, tem_whatsapp)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (contato_id, e164, e164, principal, whats))

        fone(a, NUM_ATUAL, principal=True, whats=True)
        fone(a, NUM_SEGUNDO_DE_A, whats=True)
        fone(b, NUM_SEM_WHATS, principal=True, whats=False)
        fone(b, NUM_NAO_VERIFICADO, whats=None)
        cur.execute("INSERT INTO contato_papel (contato_id, papel) VALUES (%s, %s)",
                    (b, "financeiro"))

        canal = banco.um("SELECT id FROM canal ORDER BY id LIMIT 1")
        cur.execute("""INSERT INTO conversa (canal_id, telefone_e164, contato_id, estado)
                       VALUES (%s, %s, %s, 'nova') RETURNING id""",
                    (canal["id"], NUM_ATUAL, a))
        conversa_a = cur.fetchone()["id"]
        cur.execute("""INSERT INTO conversa (canal_id, telefone_e164, estado)
                       VALUES (%s, %s, 'nova') RETURNING id""",
                    (canal["id"], NUM_AVULSO))
        conversa_sem_cadastro = cur.fetchone()["id"]

    yield {"cliente_id": cliente_id, "a": a, "b": b, "c": c,
           "conversa_a": conversa_a, "sem_cadastro": conversa_sem_cadastro,
           "canal": canal["id"]}

    limpar()
    banco.fechar()


# ------------------------------------------------------------- a consulta

def test_a_empresa_vem_identificada(cena):
    r = conversas.contatos_da_empresa(cena["conversa_a"])
    assert r["motivo"] is None
    assert r["cliente"]["id"] == cena["cliente_id"]
    assert r["cliente"]["nome"] == CLIENTE + " SA"
    assert r["cliente"]["nome_fantasia"] == "Zz Fantasia"


def test_cada_telefone_e_uma_linha(cena):
    r = conversas.contatos_da_empresa(cena["conversa_a"])
    # 2 (contato A) + 2 (contato B) + 1 (contato C, sem telefone) = 5
    assert len(r["contatos"]) == 5
    de_a = [l for l in r["contatos"] if l["contato_id"] == cena["a"]]
    assert sorted(l["e164"] for l in de_a) == sorted([NUM_ATUAL, NUM_SEGUNDO_DE_A])


def test_contato_sem_telefone_aparece_com_e164_nulo(cena):
    r = conversas.contatos_da_empresa(cena["conversa_a"])
    linha = [l for l in r["contatos"] if l["contato_id"] == cena["c"]]
    assert len(linha) == 1, "contato sem telefone desapareceu da lista"
    assert linha[0]["e164"] is None and linha[0]["telefone_id"] is None
    assert linha[0]["tem_whatsapp"] is None


def test_tem_whatsapp_tem_tres_valores(cena):
    r = conversas.contatos_da_empresa(cena["conversa_a"])
    por_numero = {l["e164"]: l["tem_whatsapp"] for l in r["contatos"]}
    assert por_numero[NUM_ATUAL] is True
    assert por_numero[NUM_SEM_WHATS] is False, "conferido e nao tem"
    assert por_numero[NUM_NAO_VERIFICADO] is None, "nunca conferido nao e 'nao tem'"


def test_o_contato_desta_conversa_vem_marcado_e_primeiro(cena):
    r = conversas.contatos_da_empresa(cena["conversa_a"])
    assert r["contatos"][0]["contato_id"] == cena["a"]
    assert r["contatos"][0]["este_contato"] is True
    assert r["contatos"][0]["e164"] == NUM_ATUAL, "o principal antes do outro"
    # E o telefone exato desta conversa, marcado — é o que a tela chama "este".
    assert r["contatos"][0]["esta_conversa"] is True
    assert [l["esta_conversa"] for l in r["contatos"]].count(True) == 1
    assert all(l["este_contato"] is False
               for l in r["contatos"] if l["contato_id"] != cena["a"])


def test_o_papel_vem_junto(cena):
    r = conversas.contatos_da_empresa(cena["conversa_a"])
    de_b = [l for l in r["contatos"] if l["contato_id"] == cena["b"]]
    assert all(l["papeis"] == ["financeiro"] for l in de_b)


def test_conversa_sem_cadastro_diz_o_motivo(cena):
    r = conversas.contatos_da_empresa(cena["sem_cadastro"])
    assert r["contatos"] == [] and r["cliente"] is None
    assert r["motivo"] == "sem_cadastro", "vazio sem motivo faz a tela adivinhar"


def test_contato_sem_empresa_diz_o_motivo(cena):
    """Contato solto (sem `cliente_id`) não tem empresa de onde tirar outros
    contatos — e isso não é a mesma coisa que número sem cadastro."""
    with banco.cursor() as cur:
        cur.execute("""INSERT INTO contato (nome, origem, ativo)
                       VALUES (%s, 'movizap', true) RETURNING id""",
                    (CLIENTE + " solto",))
        solto = cur.fetchone()["id"]
        cur.execute("""INSERT INTO conversa (canal_id, telefone_e164, contato_id, estado)
                       VALUES (%s, %s, %s, 'nova') RETURNING id""",
                    (cena["canal"], NUM_SEGUNDO_DE_A, solto))
        conversa = cur.fetchone()["id"]
    try:
        r = conversas.contatos_da_empresa(conversa)
        assert r["motivo"] == "contato_sem_empresa" and r["contatos"] == []
    finally:
        banco.executar("DELETE FROM conversa WHERE id = %s", (conversa,))
        banco.executar("DELETE FROM contato WHERE id = %s", (solto,))


def test_conversa_inexistente_nao_estoura():
    r = conversas.contatos_da_empresa(999999999)
    assert r["motivo"] == "conversa_inexistente" and r["contatos"] == []


# ----------------------------------------------------------------- a rota

class TestARota:
    """`GET /api/conversas/{id}/contatos-da-empresa` — `ATD_1.2`.

    🚨 Quem ATENDE tem de entrar: é o motivo de esta rota existir em vez de a
    gaveta chamar `/api/clientes/{id}`, que é `CAD_1.1` e daria 403.
    """

    @pytest.fixture(autouse=True)
    def api(self, cena):
        from fastapi.testclient import TestClient

        from movizap import auth, main
        banco.executar(
            """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
               VALUES ('Zz Outros Atd', %s, %s, 'x', 'atendimento', true)
               ON CONFLICT DO NOTHING""",
            (LOGIN + "atd", LOGIN + "atd@teste.invalid"))
        self.c = TestClient(main.app)
        self.c.headers.update(
            {"Authorization": f"Bearer {auth.criar_token(LOGIN + 'atd')}"})
        self.cena = cena
        yield

    def test_quem_atende_entra_e_ve_a_lista(self):
        r = self.c.get(f"/api/conversas/{self.cena['conversa_a']}/contatos-da-empresa")
        assert r.status_code == 200, r.text
        assert len(r.json()["contatos"]) == 5

    def test_conversa_sem_cadastro_responde_200_com_motivo(self):
        r = self.c.get(f"/api/conversas/{self.cena['sem_cadastro']}/contatos-da-empresa")
        assert r.status_code == 200 and r.json()["motivo"] == "sem_cadastro"

    def test_conversa_que_nao_existe_da_404(self):
        assert self.c.get(
            "/api/conversas/999999999/contatos-da-empresa").status_code == 404

    def test_sem_token_nao_entra(self):
        from fastapi.testclient import TestClient

        from movizap import main
        r = TestClient(main.app).get(
            f"/api/conversas/{self.cena['conversa_a']}/contatos-da-empresa")
        assert r.status_code == 401
