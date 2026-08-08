"""Testes do webhook — escritos DEPOIS de ver o payload real, em 07/08.

🚨 Os dois casos aqui não vieram da documentação do Evolution 2.3.7: vieram do
corpo que ele mandou de verdade quando o chip foi pareado. É exatamente para
isso que a `webhook_evento` guarda o payload cru.

⚠️ O teste que grava usa `id_externo` próprio e apaga no fim: `webhook_evento`
é tabela de produção e a numeração dela conta a história real do canal.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, webhook  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

MARCA = "zz_teste_webhook_"


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield
    banco.executar("DELETE FROM webhook_evento WHERE id_externo LIKE %s", (MARCA + "%",))
    banco.fechar()


class TestChaveDeApiNaoFicaGuardada:
    """🚨 O Evolution manda a própria apikey dentro do corpo. Guardar o payload
    cru não pode significar guardar credencial: ela iria para o banco, para os
    backups e para qualquer exportação, para sempre."""

    def test_a_apikey_vira_marcador(self):
        limpo = webhook._sem_segredo({"apikey": "segredo-de-verdade", "event": "x"})
        assert limpo["apikey"] == webhook.MARCADOR
        assert limpo["event"] == "x"

    def test_o_corpo_original_nao_e_alterado(self):
        original = {"apikey": "segredo-de-verdade"}
        webhook._sem_segredo(original)
        assert original["apikey"] == "segredo-de-verdade", \
            "mexer no dict recebido faria o chamador perder o dado sem saber"

    def test_corpo_sem_apikey_passa_intacto(self):
        corpo = {"event": "connection.update"}
        assert webhook._sem_segredo(corpo) is corpo

    def test_gravado_no_banco_ja_vai_sem_a_chave(self):
        corpo = {
            "event": "messages.upsert",
            "instance": "atendimento",
            "apikey": "NAO-PODE-FICAR-GRAVADA",
            "data": {"key": {"id": MARCA + "1",
                             "remoteJid": "5518998116168@s.whatsapp.net",
                             "fromMe": False}},
        }
        webhook.registrar(corpo)
        linha = banco.um(
            "SELECT payload FROM webhook_evento WHERE id_externo = %s", (MARCA + "1",))
        assert linha, "não gravou"
        assert linha["payload"]["apikey"] == webhook.MARCADOR
        assert "NAO-PODE-FICAR-GRAVADA" not in str(linha["payload"])


class TestEnderecamentoLid:
    """🚨 As mensagens reais vieram com `addressingMode: "lid"`, que não existe
    na doc do 2.3.7. Nesse modo o `remoteJid` pode ser um id interno `@lid`,
    que NÃO é telefone -- o telefone vem no `remoteJidAlt`."""

    def test_lid_usa_o_alternativo(self):
        jid = webhook._jid_do_cliente({
            "remoteJid": "199384756473827@lid",
            "remoteJidAlt": "5518998116168@s.whatsapp.net",
        })
        assert jid == "5518998116168@s.whatsapp.net"

    def test_sem_lid_usa_o_principal(self):
        jid = webhook._jid_do_cliente({
            "remoteJid": "5518998116168@s.whatsapp.net",
            "remoteJidAlt": "199384756473827@lid",
        })
        assert jid == "5518998116168@s.whatsapp.net"

    def test_lid_sem_alternativo_nao_inventa(self):
        """Sem o alternativo não há telefone: devolver o `@lid` e deixar o
        normalizador recusar é melhor que fingir que achou alguém."""
        assert webhook._jid_do_cliente({"remoteJid": "199384756473827@lid"}) \
            == "199384756473827@lid"

    def test_chave_ausente_nao_estoura(self):
        assert webhook._jid_do_cliente({}) == ""
        assert webhook._jid_do_cliente(None) == ""

    def test_telefone_do_lid_e_normalizado_ao_gravar(self):
        corpo = {
            "event": "messages.upsert",
            "instance": "atendimento",
            "data": {"key": {"id": MARCA + "2",
                             "remoteJid": "199384756473827@lid",
                             "remoteJidAlt": "5518998116168@s.whatsapp.net",
                             "fromMe": False}},
        }
        webhook.registrar(corpo)
        linha = banco.um(
            "SELECT telefone FROM webhook_evento WHERE id_externo = %s", (MARCA + "2",))
        assert linha["telefone"] == "+5518998116168"
