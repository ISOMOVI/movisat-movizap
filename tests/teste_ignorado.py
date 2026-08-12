"""Descartar de propósito NÃO é falhar — o contador precisa separar (07/08).

🚨 POR QUE ESTE ARQUIVO EXISTE

`webhook.registrar` gravava o motivo do descarte no campo `erro`, e
`conversas.resumo()` conta `erro IS NOT NULL` como falha. O painel acusava 16
erros num sistema em que nada tinha falhado.

É a MESMA lição da metodologia §3 -- "resposta vazia não é falha, separar
ok/vazio/erro, sem isso o painel acusa 76% de falha num sistema saudável" --
cometida de novo, num lugar diferente. Por isso virou teste: lição que só
mora em doc volta a acontecer.

⚠️ Alarme falso não é incômodo. É o que faz alguém parar de olhar o painel --
e aí o erro de verdade chega e fica no meio dos falsos.
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

MARCA = "zz_teste_ignorado_"


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield
    banco.executar("DELETE FROM webhook_evento WHERE id_externo LIKE %s", (MARCA + "%",))
    banco.fechar()


@pytest.fixture(autouse=True)
def limpar():
    yield
    banco.executar("DELETE FROM webhook_evento WHERE id_externo LIKE %s", (MARCA + "%",))


def chegou(instancia: str, sufixo: str, jid: str = "5599955550000@s.whatsapp.net"):
    webhook.registrar({
        "event": "messages.upsert",
        "instance": instancia,
        "data": {"key": {"id": MARCA + sufixo, "remoteJid": jid, "fromMe": False},
                 "message": {"conversation": "oi"},
                 "messageTimestamp": 1786000000},
    })
    return banco.um("SELECT * FROM webhook_evento WHERE id_externo = %s",
                    (MARCA + sufixo,))


class TestDescarteNaoEhFalha:
    def test_informativo_vai_para_motivo_ignorado(self):
        linha = chegou("informativos", "1")
        assert linha["motivo_ignorado"] is not None
        assert linha["erro"] is None, "descarte de propósito não pode virar erro"
        assert linha["processado"] is True

    def test_grupo_NAO_e_mais_descartado(self):
        """🚨 A REGRA MUDOU EM 12/08 (migração 027) e este teste guardava a
        antiga. Grupo era descartado no webhook porque "a Fase 1 não atende
        grupo"; agora ele é gravado como qualquer evento, e o que impede a
        enxurrada é a conversa nascer com `atender = false`, fora da caixa.

        Descartar no webhook e filtrar na tela são coisas diferentes: o que
        foi descartado não existe, e não dava para mudar de ideia depois.
        """
        linha = chegou("atendimento", "2", jid="123456789@g.us")
        assert linha["motivo_ignorado"] is None, \
            "grupo voltou a ser descartado no webhook"
        assert linha["erro"] is None

    def test_grupo_no_canal_INFORMATIVO_continua_descartado(self):
        """⚠️ O informativo é disparo, não conversa. Um grupo virando
        atendimento ali seria resposta num canal que ninguém lê."""
        linha = chegou("informativos", "2g", jid="123456789@g.us")
        assert linha["motivo_ignorado"] is not None
        assert linha["erro"] is None

    def test_mensagem_normal_nao_marca_nada(self):
        linha = chegou("atendimento", "3")
        assert linha["motivo_ignorado"] is None
        assert linha["erro"] is None

    def test_contador_de_erro_ignora_os_descartados(self):
        """🚨 O teste que reproduz o defeito: 16 descartes viravam 16 erros."""
        antes = conversas.resumo()["eventos_com_erro"]
        chegou("informativos", "1")
        chegou("informativos", "2g", jid="123456789@g.us")
        depois = conversas.resumo()
        assert depois["eventos_com_erro"] == antes, \
            "descarte de propósito voltou a contar como falha"
        assert depois["eventos_ignorados"] >= 2

    def test_o_banco_impede_ser_as_duas_coisas(self):
        """As duas colunas são exclusivas por CHECK: não dá para um evento ser
        descartado de propósito E ter falhado."""
        import psycopg

        linha = chegou("atendimento", "3")
        with pytest.raises(psycopg.errors.CheckViolation):
            banco.executar(
                "UPDATE webhook_evento SET motivo_ignorado = 'x', erro = 'y' "
                "WHERE id = %s", (linha["id"],))

    def test_falha_de_verdade_continua_contando(self):
        linha = chegou("atendimento", "3")
        banco.executar("UPDATE webhook_evento SET erro = %s WHERE id = %s",
                       ("ValueError: formato inesperado", linha["id"]))
        assert conversas.resumo()["eventos_com_erro"] >= 1
