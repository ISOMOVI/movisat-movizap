"""A mensagem que o cliente apagou para todos (17/09).

🚨 PROVADO CONTRA O MUNDO REAL, e só depois de três medições que diziam o
contrário. O evento não chegava por DOIS motivos somados: `MESSAGES_DELETE`
não estava assinado no webhook do Evolution e -- mesmo depois de assinar -- o
que NÓS apagamos não é ecoado de volta (exercitado duas vezes: o REVOKE
acontece, ele confirmou no celular, e o webhook não recebe nada). O que
destravou foi o teste dele: 3 "Oi" do próprio celular para o número do painel,
e o terceiro apagado. Chegou 6 segundos depois.

🚨 O ID DO ALVO VEM EM `data.id`, e é o TERCEIRO lugar do mesmo provedor:
upsert usa `data.key.id`, update usa `data.keyId`, delete usa `data.id`. É o
que o primeiro teste aqui prende -- errar o alvo não dá erro nenhum, porque
`UPDATE` sem linha não é falha.

⚠️ Telefone de DDD inexistente (+55 99 …) para nunca colidir com número real.
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

PREFIXO = "+559996666%"
NUMERO = "+5599966660001"
CHAVE = "zzTESTE_EXCLUSAO_0001"


def limpar():
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 LIKE %s", (PREFIXO,))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()


@pytest.fixture
def cena():
    limpar()
    canal = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not canal:
        pytest.skip("canal atendimento não cadastrado")
    conversa = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado)
           VALUES (%s, %s, 'humano') RETURNING id""", (canal["id"], NUMERO))
    banco.executar(
        """INSERT INTO mensagem
               (conversa_id, id_externo, direcao, autor, tipo, conteudo,
                entrega, criada_em)
           VALUES (%s, %s, 'entrada', 'cliente', 'texto', %s, 'lida', now())""",
        (conversa["id"], CHAVE, "Oi"))
    return conversa["id"]


def evento(chave: str = CHAVE, onde: str = "id") -> dict:
    """O formato real do `messages.delete`, medido em 17/09."""
    if onde == "id":
        return {"data": {"id": chave, "fromMe": False, "status": "DELETED",
                         "remoteJidAlt": NUMERO.lstrip("+") + "@s.whatsapp.net"}}
    if onde == "key":
        return {"data": {"key": {"id": chave}, "status": "DELETED"}}
    return {"data": {"keyId": chave, "status": "DELETED"}}


def aplicar(payload: dict) -> str:
    with banco.cursor() as cur:
        return conversas._aplicar_exclusao(cur, payload)


def ler() -> dict:
    return banco.um(
        "SELECT conteudo, apagada_em FROM mensagem WHERE id_externo = %s",
        (CHAVE,))


class TestExclusaoDeMensagem:

    def test_o_id_vem_em_data_id(self, cena):
        """🚨 O TERCEIRO LUGAR. Se o handler procurasse só onde o upsert e o
        update põem, não acharia nada -- e `UPDATE` sem linha não é erro."""
        assert aplicar(evento()) == f"exclusão aplicada ({CHAVE})"
        assert ler()["apagada_em"] is not None

    def test_o_texto_nao_e_destruido(self, cena):
        """O atendente AGIU sobre o que leu. Apagar o registro faria a
        conversa mentir sobre o que foi dito."""
        aplicar(evento())
        assert ler()["conteudo"] == "Oi"

    def test_aceita_os_outros_dois_formatos(self, cena):
        """Guarda para o dia em que o provedor mudar de lugar de novo."""
        assert "aplicada" in aplicar(evento(onde="key"))
        assert ler()["apagada_em"] is not None

    def test_apagar_duas_vezes_nao_remarca(self, cena):
        """Reentrega é esperada. A segunda não pode mexer no `apagada_em`, ou
        a hora passaria a ser a da reentrega, não a do apagamento."""
        aplicar(evento())
        primeira = ler()["apagada_em"]
        nota = aplicar(evento())
        assert "já marcada" in nota
        assert ler()["apagada_em"] == primeira

    def test_alvo_que_nao_temos_nao_vira_nada(self, cena):
        nota = aplicar(evento(chave="zzNAO_EXISTE_8888"))
        assert "não temos" in nota

    def test_evento_sem_id_nao_quebra(self, cena):
        assert "sem id" in aplicar({"data": {"status": "DELETED"}})
        assert ler()["apagada_em"] is None
