"""Testes da máquina de estados — evento cru vira conversa e mensagem.

🚨 Escreve em `webhook_evento`, `conversa` e `mensagem`, que são tabelas de
produção com conversa REAL de cliente desde 07/08. Cada teste usa telefone e
`id_externo` próprios, com prefixo, e a fixture apaga só o que criou.

⚠️ O telefone de teste é de um DDD que não existe (+55 99 ...): assim nenhum
teste pode casar com a conversa de um cliente de verdade, nem hoje nem quando
a base crescer.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas, webhook  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

MARCA = "zz_teste_conversa_"
FONE = "+5599911110000"
FONE2 = "+5599911110001"
JID = "5599911110000@s.whatsapp.net"


def limpar():
    banco.executar(
        "DELETE FROM mensagem WHERE conversa_id IN "
        "(SELECT id FROM conversa WHERE telefone_e164 IN (%s, %s))", (FONE, FONE2))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 IN (%s, %s)", (FONE, FONE2))
    banco.executar("DELETE FROM webhook_evento WHERE id_externo LIKE %s", (MARCA + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture(autouse=True)
def entre_testes():
    yield
    limpar()


def canal_id():
    linha = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not linha:
        pytest.skip("canal atendimento não cadastrado")
    return linha["id"]


def chegou(sufixo: str, texto: str = "oi", de_mim: bool = False,
           mensagem: dict | None = None):
    """Simula o webhook recebendo uma mensagem e devolve o evento gravado."""
    corpo = {
        "event": "messages.upsert",
        "instance": "atendimento",
        "data": {
            "key": {"id": MARCA + sufixo, "remoteJid": JID, "fromMe": de_mim},
            "message": mensagem if mensagem is not None else {"conversation": texto},
            "messageTimestamp": 1786000000,
        },
    }
    webhook.registrar(corpo)
    return banco.um("SELECT * FROM webhook_evento WHERE id_externo = %s",
                    (MARCA + sufixo,))


class TestEventoViraConversa:
    def test_mensagem_cria_conversa_e_mensagem(self):
        chegou("1", "bom dia")
        conversas.processar_pendentes()

        c = banco.um("SELECT * FROM conversa WHERE telefone_e164 = %s", (FONE,))
        assert c, "não criou a conversa"
        assert c["estado"] == "nova"
        assert c["atendente_id"] is None

        m = banco.um("SELECT * FROM mensagem WHERE conversa_id = %s", (c["id"],))
        assert m["conteudo"] == "bom dia"
        assert m["direcao"] == "entrada"
        assert m["autor"] == "cliente"

    def test_duas_mensagens_do_mesmo_numero_ficam_na_mesma_conversa(self):
        """🚨 `ux_conversa_aberta` é a trava. Sem ela a fala da pessoa
        apareceria partida em duas telas."""
        chegou("1", "primeira")
        chegou("2", "segunda")
        conversas.processar_pendentes()

        assert banco.um("SELECT COUNT(*) AS n FROM conversa WHERE telefone_e164 = %s",
                        (FONE,))["n"] == 1
        c = banco.um("SELECT id FROM conversa WHERE telefone_e164 = %s", (FONE,))
        assert banco.um("SELECT COUNT(*) AS n FROM mensagem WHERE conversa_id = %s",
                        (c["id"],))["n"] == 2

    def test_reprocessar_nao_duplica(self):
        """A idempotência é do banco: rodar de novo depois de corrigir um
        parser não pode duplicar o que já entrou."""
        chegou("1", "unica")
        conversas.processar_pendentes()
        banco.executar("UPDATE webhook_evento SET processado = false "
                       "WHERE id_externo = %s", (MARCA + "1",))
        conversas.processar_pendentes()

        c = banco.um("SELECT id FROM conversa WHERE telefone_e164 = %s", (FONE,))
        assert banco.um("SELECT COUNT(*) AS n FROM mensagem WHERE conversa_id = %s",
                        (c["id"],))["n"] == 1

    def test_minha_propria_mensagem_vira_saida(self):
        chegou("1", "respondi pelo celular", de_mim=True)
        conversas.processar_pendentes()
        m = banco.um(
            "SELECT direcao, autor FROM mensagem WHERE id_externo = %s", (MARCA + "1",))
        assert m["direcao"] == "saida"
        assert m["autor"] == "atendente"

    def test_evento_de_conexao_nao_vira_conversa(self):
        webhook.registrar({"event": "connection.update", "instance": "atendimento",
                           "data": {"state": "open"}})
        antes = banco.um("SELECT COUNT(*) AS n FROM conversa")["n"]
        conversas.processar_pendentes()
        assert banco.um("SELECT COUNT(*) AS n FROM conversa")["n"] == antes

    def test_nada_pendente_fica_para_tras(self):
        chegou("1")
        conversas.processar_pendentes()
        assert banco.um(
            "SELECT processado FROM webhook_evento WHERE id_externo = %s",
            (MARCA + "1",))["processado"] is True


class TestTiposDeMensagem:
    @pytest.mark.parametrize("chave,esperado,texto", [
        ({"imageMessage": {"caption": "olha a foto"}}, "imagem", "olha a foto"),
        ({"audioMessage": {}}, "audio", None),
        ({"documentMessage": {"fileName": "boleto.pdf"}}, "documento", "boleto.pdf"),
        ({"extendedTextMessage": {"text": "com link"}}, "texto", "com link"),
        ({"stickerMessage": {}}, "figurinha", None),
    ])
    def test_tipo_e_legenda(self, chave, esperado, texto):
        tipo, conteudo = conversas._tipo_e_texto(chave)
        assert tipo == esperado
        assert conteudo == texto

    def test_tipo_desconhecido_nao_derruba_e_nao_some(self):
        """⚠️ O WhatsApp inventa tipo novo. A mensagem não pode sumir por isso."""
        tipo, conteudo = conversas._tipo_e_texto({"tipoQueAindaNaoExiste": {}})
        assert tipo == "texto"
        assert "tipoQueAindaNaoExiste" in conteudo


class TestIdentificacao:
    def test_numero_fora_do_cadastro_fica_sem_dono(self):
        """🚨 Medido em 07/08: 8 de 9 números que escreveram não estão no
        cadastro. Não identificado é caso normal, não erro."""
        chegou("1")
        conversas.processar_pendentes()
        c = banco.um("SELECT contato_id FROM conversa WHERE telefone_e164 = %s", (FONE,))
        assert c["contato_id"] is None

    def test_a_conversa_explica_por_que_nao_identificou(self):
        chegou("1")
        conversas.processar_pendentes()
        c = banco.um("SELECT id FROM conversa WHERE telefone_e164 = %s", (FONE,))
        detalhe = conversas.conversa(c["id"])
        assert detalhe["candidatos"] == [], \
            "sem candidato = não é cliente; com vários = número compartilhado"


class TestAssumirEAtomico:
    def test_o_segundo_a_clicar_e_avisado(self):
        """🚨 Sem a trava, dois humanos respondem o mesmo cliente."""
        chegou("1")
        conversas.processar_pendentes()
        c = banco.um("SELECT id FROM conversa WHERE telefone_e164 = %s", (FONE,))

        a = banco.um("SELECT id, nome FROM atendente ORDER BY id LIMIT 1")
        if not a:
            pytest.skip("nenhum atendente cadastrado")
        b = banco.um("SELECT id FROM atendente WHERE id <> %s ORDER BY id LIMIT 1",
                     (a["id"],))
        if not b:
            pytest.skip("é preciso mais de um atendente")

        primeiro = conversas.assumir(c["id"], a["id"])
        segundo = conversas.assumir(c["id"], b["id"])

        assert primeiro["ok"] is True
        assert segundo["ok"] is False
        assert a["nome"] in segundo["motivo"]

    def test_assumir_muda_o_estado_para_humano(self):
        chegou("1")
        conversas.processar_pendentes()
        c = banco.um("SELECT id FROM conversa WHERE telefone_e164 = %s", (FONE,))
        a = banco.um("SELECT id FROM atendente ORDER BY id LIMIT 1")
        if not a:
            pytest.skip("nenhum atendente cadastrado")
        conversas.assumir(c["id"], a["id"])
        assert banco.um("SELECT estado FROM conversa WHERE id = %s",
                        (c["id"],))["estado"] == "humano"


class TestResumo:
    def test_resumo_conta_a_fila_pendente(self):
        """🚨 Fila parada parece "nenhuma mensagem nova". O resumo existe para
        essa diferença aparecer na tela."""
        chegou("1")
        antes = conversas.resumo()
        assert antes["eventos_pendentes"] >= 1
        conversas.processar_pendentes()
        assert conversas.resumo()["eventos_pendentes"] == 0
