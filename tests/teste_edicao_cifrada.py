"""A edição do CLIENTE chega cifrada — 06/10.

🚨 O QUE ISTO DEFENDE: a edição de cliente NUNCA chega legível. A Evolution
entrega `messages.upsert` com `secretEncryptedMessage` (`secretEncType` 2) e o
`targetMessageKey.id` da mensagem editada. Medido em 06/10: 94 eventos desde
07/08, os 94 com alvo e os 94 com o original no banco — e cada um virava uma
mensagem-lixo "[mensagem cifrada...]" logo abaixo do texto editado, enquanto o
original seguia sem marca de edição.

🚨 E DEFENDE A TELA DE MENTIR: a marca é só `editada_em`. `conteudo` fica como
estava e `conteudo_original` fica NULL — é o NULL que diz "a versão nova não
pôde ser lida". Se alguém "completar" isso copiando o conteúdo para
`conteudo_original`, a tela mostraria "antes: X" igual ao texto do balão.

🚨 Escreve em `conversa` e `mensagem`, tabelas de PRODUÇÃO. Telefone de DDD
inexistente; tudo apagado no fim.
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

PREFIXO = "+559995558%"
NUMERO = "+5599955580001"
JID = "5599955580001@s.whatsapp.net"
ALVO = "zz-cifrada-alvo-1"


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
    banco.fechar()


@pytest.fixture()
def cena():
    """Uma conversa com uma mensagem do cliente, que é a editada."""
    limpar()
    canal = banco.um(
        "SELECT id, instancia FROM canal WHERE tipo = 'atendimento' AND ativo LIMIT 1")
    if not canal:
        pytest.skip("nenhum canal de atendimento ativo")
    cid = banco.um(
        """INSERT INTO conversa (canal_id, tipo, telefone_e164, estado)
           VALUES (%s, 'direta', %s, 'nova') RETURNING id""",
        (canal["id"], NUMERO))["id"]
    mid = banco.um(
        """INSERT INTO mensagem (conversa_id, id_externo, direcao, autor, tipo,
                                 conteudo, criada_em)
           VALUES (%s, %s, 'entrada', 'cliente', 'texto', 'Teste sem editar', now())
           RETURNING id""", (cid, ALVO))["id"]
    yield {"canal": canal, "conversa": cid, "mensagem": mid}
    limpar()


def evento(canal, alvo=ALVO, enc_type=2, com_alvo=True, sufixo="1"):
    """Estrutura do evento 115503 (06/10), medida — não inventada."""
    sec = {"encIv": {"0": 109, "1": 3}, "encPayload": {"0": 175, "1": 26},
           "secretEncType": enc_type}
    if com_alvo:
        sec["targetMessageKey"] = {"id": alvo, "fromMe": True,
                                   "remoteJid": "113005069135920@lid"}
    eid = f"zz-cifrada-evt-{sufixo}"
    return {
        "id": 0, "canal_id": canal["id"], "instancia": canal["instancia"],
        "evento": "messages.upsert", "id_externo": eid, "telefone": NUMERO,
        "payload": {"data": {
            "key": {"id": eid, "fromMe": False, "remoteJid": JID,
                    "remoteJidAlt": JID, "addressingMode": "lid"},
            "messageTimestamp": 1791327091,
            "message": {"messageContextInfo": {}, "secretEncryptedMessage": sec},
        }},
    }


def processar(ev):
    with banco.cursor() as cur:
        return conversas._gravar_mensagem(cur, ev, ev["payload"], [])


def mensagens(conversa_id):
    return banco.um("SELECT count(*) n FROM mensagem WHERE conversa_id = %s",
                    (conversa_id,))["n"]


def alvo(mensagem_id):
    return banco.um(
        "SELECT conteudo, conteudo_original, editada_em FROM mensagem WHERE id = %s",
        (mensagem_id,))


class TestEdicaoCifradaNaoViraMensagem:
    def test_nao_cria_linha_no_historico(self, cena):
        """🚨 O DEFEITO: 94 linhas "[mensagem cifrada...]" em conversas reais."""
        antes = mensagens(cena["conversa"])
        nota = processar(evento(cena["canal"]))
        assert mensagens(cena["conversa"]) == antes, "a edição virou mensagem"
        assert "edição cifrada" in nota

    def test_marca_a_original_como_editada(self, cena):
        processar(evento(cena["canal"]))
        assert alvo(cena["mensagem"])["editada_em"] is not None

    def test_nao_inventa_texto_novo(self, cena):
        """🚨 conteudo intacto e conteudo_original NULL: é o sinal que a tela
        usa para dizer que a versão nova não pôde ser lida."""
        processar(evento(cena["canal"]))
        m = alvo(cena["mensagem"])
        assert m["conteudo"] == "Teste sem editar"
        assert m["conteudo_original"] is None

    def test_alvo_que_nao_temos_nao_vira_nada(self, cena):
        antes = mensagens(cena["conversa"])
        nota = processar(evento(cena["canal"], alvo="zz-nao-existe"))
        assert mensagens(cena["conversa"]) == antes
        assert "sem original" in nota


class TestOAvisoContinuaOndeNaoEEdicao:
    def test_sem_alvo_continua_aviso(self, cena):
        """Sem `targetMessageKey` não sabemos o que é — segue o aviso de 17/09."""
        antes = mensagens(cena["conversa"])
        processar(evento(cena["canal"], com_alvo=False, sufixo="2"))
        assert mensagens(cena["conversa"]) == antes + 1
        assert alvo(cena["mensagem"])["editada_em"] is None

    def test_outro_tipo_de_cifra_continua_aviso(self, cena):
        """`secretEncType` 1 é edição de EVENTO (agenda), não de mensagem."""
        antes = mensagens(cena["conversa"])
        processar(evento(cena["canal"], enc_type=1, sufixo="3"))
        assert mensagens(cena["conversa"]) == antes + 1
        assert alvo(cena["mensagem"])["editada_em"] is None
