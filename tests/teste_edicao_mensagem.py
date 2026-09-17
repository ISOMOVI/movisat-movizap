"""A mensagem que o cliente editou (17/09).

🚨 A EDIÇÃO JÁ CHEGAVA E ERA JOGADA FORA. Medido nos 54.544 eventos crus
recebidos desde 18/08: `editedMessage` apareceu 5 vezes, todas casando com
uma mensagem nossa pelo `keyId`. Elas entram por `messages.update` -- o mesmo
evento do tique de entrega --, e o `_atualizar_entrega` só olhava
`data.status`: o texto novo ia para o lixo. Casos reais perdidos nesta base:
"Bom dia" virou "Boa tarde", e um comando SMS de rastreador ganhou "para
ativar ign virtual" que o atendente nunca leu.

🚨 O TEXTO NOVO VEM EM DOIS FORMATOS, e é o que os dois primeiros testes
guardam: `conversation` (2 dos 5 casos reais) e `extendedTextMessage.text`
(os outros 3). Ler só um caminho esvaziaria quase metade das edições -- pior
que não tratar nada, porque apagaria o que estava certo.

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

PREFIXO = "+559995555%"
NUMERO = "+5599955550001"
CHAVE = "zzTESTE_EDICAO_0001"


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
    """Uma conversa com uma mensagem de entrada, pronta para ser editada."""
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
        (conversa["id"], CHAVE, "Bom dia, pode confirmar?"))
    return conversa["id"]


def evento(texto: str, formato: str, chave: str = CHAVE) -> dict:
    """Monta o payload como o Evolution manda, nos dois formatos reais."""
    if formato == "conversation":
        interna = {"conversation": texto, "messageContextInfo": {}}
    else:
        interna = {"extendedTextMessage": {"text": texto}}
    return {"data": {"keyId": chave, "fromMe": False, "status": "SERVER_ACK",
                     "message": {"editedMessage": {"message": interna}}}}


def aplicar(payload: dict) -> str | None:
    with banco.cursor() as cur:
        return conversas._aplicar_edicao(cur, payload)


def ler() -> dict:
    return banco.um(
        "SELECT conteudo, conteudo_original, editada_em, entrega "
        "FROM mensagem WHERE id_externo = %s", (CHAVE,))


class TestEdicaoDeMensagem:

    def test_formato_conversation_troca_o_texto(self, cena):
        """2 dos 5 casos reais vieram assim: texto simples."""
        assert aplicar(evento("Boa tarde, pode confirmar?", "conversation")) \
            == f"edição aplicada ({CHAVE})"
        m = ler()
        assert m["conteudo"] == "Boa tarde, pode confirmar?"
        assert m["editada_em"] is not None

    def test_formato_extended_troca_o_texto(self, cena):
        """Os outros 3 vieram com `extendedTextMessage` -- citação, menção
        ou prévia de link fazem o WhatsApp mudar o formato."""
        assert aplicar(evento("Boa tarde mesmo", "extended")) \
            == f"edição aplicada ({CHAVE})"
        assert ler()["conteudo"] == "Boa tarde mesmo"

    def test_guarda_o_texto_original(self, cena):
        aplicar(evento("versão corrigida", "conversation"))
        assert ler()["conteudo_original"] == "Bom dia, pode confirmar?"

    def test_segunda_edicao_nao_sobrescreve_o_original(self, cena):
        """O original é o de ORIGEM, não a penúltima versão: é ele que diz o
        que estava escrito quando isto virou atendimento."""
        aplicar(evento("segunda versão", "conversation"))
        aplicar(evento("terceira versão", "conversation"))
        m = ler()
        assert m["conteudo"] == "terceira versão"
        assert m["conteudo_original"] == "Bom dia, pode confirmar?"

    def test_nao_rebaixa_o_tique_de_leitura(self, cena):
        """🚨 A REGRESSÃO QUE ISTO EVITA: o evento de edição traz
        `SERVER_ACK`, que o mapa de entrega lê como "enviada". Se a edição
        caísse no caminho de entrega, uma vírgula corrigida pelo cliente
        apagaria o ✓✓ azul de uma mensagem já lida."""
        assert ler()["entrega"] == "lida"
        aplicar(evento("corrigido", "conversation"))
        assert ler()["entrega"] == "lida"

    def test_evento_comum_de_entrega_nao_e_edicao(self, cena):
        """`None` é o sinal de "não é edição, segue tratando entrega". Sem
        isso, todo tique de entrega pararia de ser gravado."""
        comum = {"data": {"keyId": CHAVE, "status": "DELIVERY_ACK"}}
        assert aplicar(comum) is None

    def test_alvo_que_nao_temos_nao_vira_nada(self, cena):
        """Mesma regra da reação: editar mensagem anterior ao painel não
        pode inventar linha nenhuma na conversa."""
        nota = aplicar(evento("oi", "conversation", chave="zzNAO_EXISTE_9999"))
        assert "não temos" in nota
        assert banco.um("SELECT count(*) AS n FROM mensagem "
                        "WHERE id_externo = %s", ("zzNAO_EXISTE_9999",))["n"] == 0

    def test_edicao_sem_texto_reconhecido_nao_esvazia(self, cena):
        """Legenda de mídia ou formato ainda não visto: melhor deixar como
        está do que apagar o que o atendente já leu."""
        vazio = {"data": {"keyId": CHAVE, "status": "SERVER_ACK",
                          "message": {"editedMessage": {"message": {
                              "imageMessage": {"caption": "nova legenda"}}}}}}
        nota = aplicar(vazio)
        assert "sem texto reconhecido" in nota
        assert ler()["conteudo"] == "Bom dia, pode confirmar?"
        assert ler()["editada_em"] is None
