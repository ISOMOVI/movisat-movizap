""""Visto por" na nota interna (Bloco 12, 15/10).

🚨 Escreve em `atendente`, `conversa`, `mensagem` e `nota_leitura`, tabelas de
PRODUÇÃO. Login `zz_teste_vp_` e número `+5518977773001`; tudo apagado no fim.

O que estes testes guardam:
  · "visto" é por PESSOA e por NOTA, e a hora é a da PRIMEIRA vez -- a mesma
    nota reaparecendo na tela não vira "a última vez em que rolou por aqui";
  · só nota, e só nota DESTA conversa: a tela manda os ids, e id que vem do
    navegador não se obedece;
  · 🚨 NOTA ANTERIOR AO CORTE NÃO É CARIMBADA e vem com
    `leitura_rastreada = False` -- é o que permite à tela dizer "sem registro
    antes de 15/10" em vez de "ninguém viu", que seria falso sobre o passado;
  · sem vínculo de atendimento não há quem carimbar, e isso responde 0, não
    erro: quem só lê não pode ver mensagem de falha.
"""
import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas, operacao  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_vp_"
NUMERO = "+5518977773001"
OUTRO_NUMERO = "+5518977773002"


def limpar():
    banco.executar("""DELETE FROM nota_leitura WHERE mensagem_id IN
                       (SELECT id FROM mensagem WHERE conversa_id IN
                         (SELECT id FROM conversa WHERE telefone_e164 = ANY(%s)))""",
                   ([NUMERO, OUTRO_NUMERO],))
    banco.executar("""DELETE FROM mensagem WHERE conversa_id IN
                       (SELECT id FROM conversa WHERE telefone_e164 = ANY(%s))""",
                   ([NUMERO, OUTRO_NUMERO],))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = ANY(%s)",
                   ([NUMERO, OUTRO_NUMERO],))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def cena():
    banco.abrir()
    limpar()
    um = operacao.criar_atendente("Zz Visto Um", LOGIN + "1", LOGIN + "1@teste.invalid")
    dois = operacao.criar_atendente("Zz Visto Dois", LOGIN + "2", LOGIN + "2@teste.invalid")
    canal = banco.um("SELECT id FROM canal ORDER BY id LIMIT 1")
    conversa = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado)
           VALUES (%s, %s, 'nova') RETURNING id""", (canal["id"], NUMERO))["id"]
    outra = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado)
           VALUES (%s, %s, 'nova') RETURNING id""",
        (canal["id"], OUTRO_NUMERO))["id"]

    nota = conversas.anotar(conversa, "nota de hoje", um["id"])["mensagem_id"]
    nota_da_outra = conversas.anotar(outra, "nota de outra conversa",
                                     um["id"])["mensagem_id"]
    # Uma mensagem de SAÍDA, que não é nota: não deve aceitar carimbo.
    saida = banco.um(
        """INSERT INTO mensagem (conversa_id, direcao, autor, tipo, conteudo,
                                 criada_em)
           VALUES (%s, 'saida', 'atendente', 'texto', 'oi', now())
           RETURNING id""", (conversa,))["id"]
    # E uma nota ANTERIOR ao corte, para o caso do passado.
    antiga = banco.um(
        """INSERT INTO mensagem (conversa_id, direcao, autor, tipo, conteudo,
                                 atendente_id, criada_em)
           VALUES (%s, 'interna', 'atendente', 'nota', 'nota de setembro', %s, %s)
           RETURNING id""",
        (conversa, um["id"],
         conversas.LEITURA_DE_NOTA_DESDE - timedelta(days=20)))["id"]

    yield {"um": um["id"], "dois": dois["id"], "conversa": conversa,
           "outra": outra, "nota": nota, "nota_da_outra": nota_da_outra,
           "saida": saida, "antiga": antiga}
    limpar()
    banco.fechar()


def quem_viu(mensagem_id):
    return banco.varios(
        """SELECT atendente_id, visto_em FROM nota_leitura
            WHERE mensagem_id = %s ORDER BY visto_em""", (mensagem_id,))


# ------------------------------------------------------------- o carimbo

def test_carimba_por_pessoa(cena):
    assert conversas.marcar_notas_vistas(
        cena["conversa"], [cena["nota"]], cena["um"]) == 1
    assert conversas.marcar_notas_vistas(
        cena["conversa"], [cena["nota"]], cena["dois"]) == 1
    assert len(quem_viu(cena["nota"])) == 2


def test_a_hora_e_a_da_primeira_vez(cena):
    """A mesma nota reaparecendo na tela não muda o carimbo -- senão ele passa
    a dizer "a última vez em que rolou por aqui", que é outra coisa."""
    conversas.marcar_notas_vistas(cena["conversa"], [cena["nota"]], cena["um"])
    antes = quem_viu(cena["nota"])
    assert conversas.marcar_notas_vistas(
        cena["conversa"], [cena["nota"]], cena["um"]) == 0, "carimbou de novo"
    assert quem_viu(cena["nota"]) == antes


def test_nota_de_outra_conversa_nao_e_carimbada(cena):
    """Os ids vêm do NAVEGADOR. Obedecer sem conferir deixaria qualquer pessoa
    carimbar nota de conversa que ela não abriu."""
    assert conversas.marcar_notas_vistas(
        cena["conversa"], [cena["nota_da_outra"]], cena["um"]) == 0
    assert quem_viu(cena["nota_da_outra"]) == []


def test_mensagem_que_nao_e_nota_nao_e_carimbada(cena):
    assert conversas.marcar_notas_vistas(
        cena["conversa"], [cena["saida"]], cena["um"]) == 0


def test_nota_anterior_ao_corte_nao_e_carimbada(cena):
    """🚨 O passado não se carimba: quem viu aquela nota em setembro não foi
    registrado, e inventar um "visto" agora seria pior que não ter."""
    assert conversas.marcar_notas_vistas(
        cena["conversa"], [cena["antiga"]], cena["um"]) == 0
    assert quem_viu(cena["antiga"]) == []


def test_sem_vinculo_de_atendimento_nao_estoura(cena):
    assert conversas.marcar_notas_vistas(cena["conversa"], [cena["nota"]], None) == 0
    assert conversas.marcar_notas_vistas(cena["conversa"], [], cena["um"]) == 0


# ------------------------------------------------- o que a tela recebe

def test_a_tela_recebe_quem_viu_com_nome_e_hora(cena):
    conversas.marcar_notas_vistas(cena["conversa"], [cena["nota"]], cena["um"])
    linhas = conversas.mensagens(cena["conversa"])
    nota = [m for m in linhas if m["id"] == cena["nota"]][0]
    assert nota["leitura_rastreada"] is True
    assert nota["vistos"], "a nota de hoje veio sem ninguém, e alguém viu"
    assert any(v["nome"] == "Zz Visto Um" for v in nota["vistos"])
    assert all("visto_em" in v for v in nota["vistos"])


def test_nota_antiga_diz_que_nao_havia_registro(cena):
    """🚨 É O PONTO INTEIRO DO `leitura_rastreada`: lista vazia numa nota de
    setembro significa "não havia registro", nunca "ninguém viu"."""
    linhas = conversas.mensagens(cena["conversa"])
    antiga = [m for m in linhas if m["id"] == cena["antiga"]][0]
    assert antiga["leitura_rastreada"] is False
    assert antiga["vistos"] == []


def test_mensagem_comum_nao_carrega_visto(cena):
    linhas = conversas.mensagens(cena["conversa"])
    saida = [m for m in linhas if m["id"] == cena["saida"]][0]
    assert saida["vistos"] == []
    assert saida["leitura_rastreada"] is False


# ----------------------------------------------------------------- a rota

class TestARota:
    @pytest.fixture(autouse=True)
    def api(self, cena):
        from fastapi.testclient import TestClient

        from movizap import auth, main
        banco.executar(
            """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
               VALUES ('Zz Visto Rota', %s, %s, 'x', 'atendimento', true)
               ON CONFLICT DO NOTHING""",
            (LOGIN + "rota", LOGIN + "rota@teste.invalid"))
        self.c = TestClient(main.app)
        self.c.headers.update(
            {"Authorization": f"Bearer {auth.criar_token(LOGIN + 'rota')}"})
        self.cena = cena
        yield

    def test_quem_atende_marca(self):
        r = self.c.post(f"/api/conversas/{self.cena['conversa']}/notas/vistas",
                        json={"ids": [self.cena["nota"]]})
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True

    def test_sem_token_nao_entra(self):
        from fastapi.testclient import TestClient

        from movizap import main
        r = TestClient(main.app).post(
            f"/api/conversas/{self.cena['conversa']}/notas/vistas",
            json={"ids": [1]})
        assert r.status_code == 401
