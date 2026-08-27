"""Testes do envio de resposta e da nota interna.

🚨 O EVOLUTION É SUBSTITUÍDO POR MOCK EM TODO TESTE, e isso não é conveniência
de velocidade: teste que envia de verdade manda mensagem de WhatsApp para uma
pessoa real. A fixture `sem_enviar` é `autouse` justamente para não depender de
alguém lembrar de aplicá-la.

⚠️ Telefone de DDD inexistente (+55 99 …) para nunca colidir com conversa real.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas, evolution, webhook  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

FONE = "+5599933330000"
JID = "5599933330000@s.whatsapp.net"
ID_FALSO = "zz_teste_envio_ID_DO_WHATSAPP"


def limpar():
    banco.executar(
        "DELETE FROM mensagem WHERE conversa_id IN "
        "(SELECT id FROM conversa WHERE telefone_e164 = %s)", (FONE,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (FONE,))
    banco.executar("DELETE FROM webhook_evento WHERE id_externo = %s", (ID_FALSO,))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture(autouse=True)
def sem_enviar(monkeypatch):
    """🚨 Nenhum teste fala com o WhatsApp de verdade."""
    enviadas = []

    # ⚠️ A ASSINATURA ACOMPANHA A REAL. `citando` entrou em 25/08, com o
    # responder citando; mock que não aceita o argumento reprova código
    # correto e faz procurar defeito onde não há.
    def falso(instancia, numero, texto, citando=None, mencionados=None):
        enviadas.append({"instancia": instancia, "numero": numero, "texto": texto})
        return {"id_externo": ID_FALSO, "status": "PENDING", "bruto": {}}

    monkeypatch.setattr(evolution, "enviar_texto", falso)
    yield enviadas
    limpar()


@pytest.fixture
def uma_conversa():
    canal = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not canal:
        pytest.skip("canal atendimento não cadastrado")
    with banco.cursor() as cur:
        return conversas.garantir_conversa(cur, canal["id"], FONE)


class TestEnvio:
    def test_manda_para_o_numero_da_conversa(self, uma_conversa, sem_enviar):
        """🚨 O destinatário sai da CONVERSA, nunca do que foi digitado. É esta
        propriedade que impede o painel de virar ferramenta de disparo."""
        r = conversas.responder(uma_conversa, "bom dia", None)
        assert r["ok"] is True
        assert len(sem_enviar) == 1
        assert sem_enviar[0]["numero"] == FONE
        assert sem_enviar[0]["instancia"] == "atendimento"

    def test_grava_a_mensagem_como_saida(self, uma_conversa):
        conversas.responder(uma_conversa, "respondendo", None)
        m = banco.um("SELECT * FROM mensagem WHERE conversa_id = %s", (uma_conversa,))
        assert m["direcao"] == "saida"
        assert m["autor"] == "atendente"
        assert m["conteudo"] == "respondendo"
        assert m["entrega"] == "enviada"
        assert m["id_externo"] == ID_FALSO

    def test_o_eco_do_webhook_nao_duplica(self, uma_conversa):
        """🚨 O ponto mais importante deste arquivo.

        O Evolution devolve a NOSSA mensagem pelo webhook, com `fromMe: true` e
        o mesmo `key.id`. Sem gravar esse id no envio, o eco viraria uma segunda
        mensagem igual na tela do atendente -- e ninguém entenderia por quê.
        """
        conversas.responder(uma_conversa, "só uma vez", None)

        webhook.registrar({
            "event": "messages.upsert",
            "instance": "atendimento",
            "data": {"key": {"id": ID_FALSO, "remoteJid": JID, "fromMe": True},
                     "message": {"conversation": "só uma vez"},
                     "messageTimestamp": 1786000000},
        })
        conversas.processar_pendentes()

        quantas = banco.um(
            "SELECT COUNT(*) AS n FROM mensagem WHERE conversa_id = %s", (uma_conversa,))
        assert quantas["n"] == 1, "o eco do webhook duplicou a mensagem"

    def test_quem_responde_assume_a_conversa(self, uma_conversa):
        a = banco.um("SELECT id FROM atendente ORDER BY id LIMIT 1")
        if not a:
            pytest.skip("nenhum atendente cadastrado")
        conversas.responder(uma_conversa, "assumindo", a["id"])
        c = banco.um("SELECT atendente_id, estado FROM conversa WHERE id = %s",
                     (uma_conversa,))
        assert c["atendente_id"] == a["id"]
        assert c["estado"] == "humano"

    def test_marca_a_primeira_resposta(self, uma_conversa):
        conversas.responder(uma_conversa, "primeira", None)
        c = banco.um("SELECT primeira_resposta_em, segundos_ate_resposta "
                     "FROM conversa WHERE id = %s", (uma_conversa,))
        assert c["primeira_resposta_em"] is not None
        assert c["segundos_ate_resposta"] is not None

    def test_texto_vazio_nao_envia(self, uma_conversa, sem_enviar):
        assert conversas.responder(uma_conversa, "   ", None)["ok"] is False
        assert sem_enviar == [], "chegou a chamar o WhatsApp com texto vazio"

    def test_conversa_encerrada_nao_recebe_resposta(self, uma_conversa, sem_enviar):
        # ⚠️ Encerra sem classificação: virou opcional em 11/08, e ler uma
        # de produção era a armadilha que quebrou 8 testes quando a tabela
        # ficou vazia.
        conversas.encerrar(uma_conversa)
        r = conversas.responder(uma_conversa, "oi?", None)
        assert r["ok"] is False
        assert sem_enviar == []

    def test_falha_do_whatsapp_nao_vira_mensagem_gravada(self, uma_conversa, monkeypatch):
        """⚠️ Envia primeiro, grava depois. O contrário registraria como enviada
        uma mensagem que o WhatsApp recusou -- e o atendente acharia que
        respondeu."""
        def recusa(instancia, numero, texto, citando=None, mencionados=None):
            raise evolution.ErroEvolution("numero nao existe no whatsapp", 400)

        monkeypatch.setattr(evolution, "enviar_texto", recusa)
        r = conversas.responder(uma_conversa, "vai falhar", None)
        assert r["ok"] is False
        assert banco.um("SELECT COUNT(*) AS n FROM mensagem WHERE conversa_id = %s",
                        (uma_conversa,))["n"] == 0


class TestNotaInterna:
    def test_nota_nao_chama_o_whatsapp(self, uma_conversa, sem_enviar):
        r = conversas.anotar(uma_conversa, "cliente ligou antes", None)
        assert r["ok"] is True
        assert sem_enviar == [], "a nota interna saiu para o cliente"

    def test_nota_grava_como_interna(self, uma_conversa):
        conversas.anotar(uma_conversa, "combinado por telefone", None)
        m = banco.um("SELECT direcao, tipo, conteudo FROM mensagem "
                     "WHERE conversa_id = %s", (uma_conversa,))
        assert m["direcao"] == "interna"
        assert m["tipo"] == "nota"

    def test_o_banco_impede_nota_virar_mensagem(self, uma_conversa):
        """⚠️ O CHECK amarra `tipo='nota'` a `direcao='interna'`. É o banco
        impedindo que uma nota vaze como mensagem de saída."""
        import psycopg

        with pytest.raises(psycopg.errors.CheckViolation):
            banco.executar(
                """INSERT INTO mensagem (conversa_id, direcao, autor, tipo,
                                         conteudo, criada_em)
                   VALUES (%s, 'saida', 'atendente', 'nota', 'vazando', now())""",
                (uma_conversa,))

    def test_nota_vazia_e_recusada(self, uma_conversa):
        assert conversas.anotar(uma_conversa, "  ", None)["ok"] is False
