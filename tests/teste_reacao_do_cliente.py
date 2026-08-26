"""A reação do CLIENTE — migração 036.

🚨 O QUE ISTO DEFENDE NÃO É A REAÇÃO APARECER: É ELA NÃO VIRAR MENSAGEM.
Até 26/08 cada reação gravava uma linha `[reactionMessage — tipo ainda não
tratado]` no meio da conversa, para o atendente ler. Foram **161** delas em
conversas reais. O defeito não era a reação faltar; era ela virar lixo visível.

🚨 E DEFENDE O GRUPO. Medido nas 161: 64 em grupo (40%). Com uma coluna só, o
último que reagisse apagaria os outros **em silêncio** — e silêncio é o defeito
que este projeto mais paga.

🚨 Escreve em `conversa`, `mensagem` e `mensagem_reacao`, tabelas de PRODUÇÃO.
Telefone de DDD inexistente; tudo apagado no fim.
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

PREFIXO = "+559995557%"
NUMERO = "+5599955570001"
GRUPO = "zz-reacao-grupo@g.us"
ALVO = "zz-reacao-alvo-1"


def limpar():
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s
                                       OR grupo_jid = %s)""", (PREFIXO, GRUPO))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 LIKE %s "
                   "   OR grupo_jid = %s", (PREFIXO, GRUPO))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def cena():
    """Uma conversa de grupo com uma mensagem nossa, que é o alvo."""
    limpar()
    canal = banco.um(
        "SELECT id, instancia FROM canal WHERE tipo = 'atendimento' AND ativo LIMIT 1")
    if not canal:
        pytest.skip("nenhum canal de atendimento ativo")
    cid = banco.um(
        """INSERT INTO conversa (canal_id, tipo, grupo_jid, estado)
           VALUES (%s, 'grupo', %s, 'nova') RETURNING id""",
        (canal["id"], GRUPO))["id"]
    mid = banco.um(
        """INSERT INTO mensagem (conversa_id, id_externo, direcao, autor, tipo,
                                 conteudo, criada_em)
           VALUES (%s, %s, 'saida', 'atendente', 'texto', 'bom dia', now())
           RETURNING id""", (cid, ALVO))["id"]
    yield {"canal": canal, "conversa": cid, "mensagem": mid}
    limpar()


def evento(canal, emoji, quem="111@lid", de_mim=False, alvo=ALVO, nome=None):
    """O formato REAL, copiado de um evento medido em 26/08 — não inventado."""
    return {
        "id": 0, "canal_id": canal["id"], "instancia": canal["instancia"],
        "evento": "messages.upsert", "id_externo": f"zz-evt-{emoji}-{quem}",
        "telefone": None,
        "payload": {"data": {
            "key": {"remoteJid": GRUPO, "fromMe": de_mim, "participant": quem,
                    "id": f"zz-evt-{emoji}-{quem}"},
            "pushName": nome,
            "messageTimestamp": 1787000000,
            "message": {"reactionMessage": {
                "key": {"id": alvo, "fromMe": True, "remoteJid": GRUPO},
                "text": emoji}},
        }},
    }


def processar(ev):
    with banco.cursor() as cur:
        return conversas._gravar_mensagem(cur, ev, ev["payload"], [])


def reacoes(mensagem_id):
    return banco.varios(
        "SELECT quem, quem_nome, emoji FROM mensagem_reacao "
        " WHERE mensagem_id = %s ORDER BY quem", (mensagem_id,))


def mensagens(conversa_id):
    return banco.um("SELECT count(*) n FROM mensagem WHERE conversa_id = %s",
                    (conversa_id,))["n"]


class TestReacaoNaoViraMensagem:
    def test_reacao_nao_cria_linha_no_historico(self, cena):
        """🚨 O DEFEITO QUE ISTO CONSERTA: 161 linhas
        `[reactionMessage — tipo ainda não tratado]` em conversas reais."""
        antes = mensagens(cena["conversa"])
        nota = processar(evento(cena["canal"], "👍"))
        assert mensagens(cena["conversa"]) == antes, \
            "a reação virou mensagem de novo"
        assert "reação" in nota

    def test_a_reacao_fica_na_mensagem_reagida(self, cena):
        processar(evento(cena["canal"], "👍"))
        assert reacoes(cena["mensagem"]) == [
            {"quem": "111@lid", "quem_nome": None, "emoji": "👍"}]

    def test_guarda_o_nome_de_quem_reagiu_em_grupo(self, cena):
        processar(evento(cena["canal"], "🙏", nome="Fulano"))
        assert reacoes(cena["mensagem"])[0]["quem_nome"] == "Fulano"


class TestOGrupoNaoPerdeNinguem:
    def test_tres_pessoas_tres_linhas(self, cena):
        """🚨 A RAZÃO DE SER TABELA. Com uma coluna, o terceiro apagaria os
        dois primeiros e ninguém saberia."""
        for quem in ("111@lid", "222@lid", "333@lid"):
            processar(evento(cena["canal"], "👍", quem=quem))
        assert len(reacoes(cena["mensagem"])) == 3

    def test_a_mesma_pessoa_reagindo_de_novo_TROCA(self, cena):
        processar(evento(cena["canal"], "👍", quem="111@lid"))
        processar(evento(cena["canal"], "❤️", quem="111@lid"))
        assert reacoes(cena["mensagem"]) == [
            {"quem": "111@lid", "quem_nome": None, "emoji": "❤️"}]


class TestRemocao:
    def test_emoji_vazio_APAGA_a_linha(self, cena):
        """No WhatsApp não existe "remover": existe reagir com nada."""
        processar(evento(cena["canal"], "👍", quem="111@lid"))
        processar(evento(cena["canal"], "", quem="111@lid"))
        assert reacoes(cena["mensagem"]) == []

    def test_remover_a_minha_nao_tira_a_dos_outros(self, cena):
        processar(evento(cena["canal"], "👍", quem="111@lid"))
        processar(evento(cena["canal"], "👍", quem="222@lid"))
        processar(evento(cena["canal"], "", quem="111@lid"))
        assert [r["quem"] for r in reacoes(cena["mensagem"])] == ["222@lid"]


class TestQuemReagiu:
    def test_reacao_NOSSA_e_do_key_de_fora(self, cena):
        """🚨 O `reactionMessage.key` aponta para a mensagem REAGIDA. Usar o
        `fromMe` dele diria de quem é a MENSAGEM, não de quem é a REAÇÃO — e
        toda reação nossa a uma mensagem do cliente ficaria marcada como dele.
        A cena tem exatamente essa armadilha: o alvo é `fromMe: True`."""
        processar(evento(cena["canal"], "👍", de_mim=True))
        assert reacoes(cena["mensagem"])[0]["quem"] == "nos"

    def test_reacao_do_cliente_nao_vira_nossa(self, cena):
        processar(evento(cena["canal"], "👍", de_mim=False, quem="444@lid"))
        assert reacoes(cena["mensagem"])[0]["quem"] == "444@lid"


class TestAlvoDesconhecido:
    def test_reagir_a_mensagem_que_nao_temos_nao_cria_nada(self, cena):
        """A pessoa pode reagir a mensagem anterior ao painel. Antes isso
        virava mensagem falsa; agora não vira nada — que é o que o atendente
        veria de qualquer jeito, já que a mensagem reagida também não está lá."""
        antes = mensagens(cena["conversa"])
        nota = processar(evento(cena["canal"], "👍", alvo="nao-existe"))
        assert mensagens(cena["conversa"]) == antes
        assert reacoes(cena["mensagem"]) == []
        assert "não temos" in nota


class TestATelaRecebeOCampo:
    def test_a_consulta_da_tela_traz_reacoes_agrupadas(self, cena):
        """⚠️ CAMPO QUE A TELA DESENHA TEM DE VIR NA CONSULTA QUE ELA PEDE —
        a lição do `estrela` no e-mail, que aparecia vazia com a rota
        respondendo 200."""
        processar(evento(cena["canal"], "👍", quem="111@lid"))
        processar(evento(cena["canal"], "👍", quem="222@lid"))
        processar(evento(cena["canal"], "🙏", quem="333@lid"))
        linhas = conversas.mensagens(cena["conversa"])
        alvo = next(m for m in linhas if m["id"] == cena["mensagem"])
        assert "reacoes" in alvo, "a tela desenha `reacoes` e a consulta não traz"
        por_emoji = {r["emoji"]: r for r in alvo["reacoes"]}
        assert por_emoji["👍"]["n"] == 2
        assert por_emoji["🙏"]["n"] == 1
        assert all(r["nosso"] is False for r in alvo["reacoes"])

    def test_o_campo_nosso_acende_o_botao(self, cena):
        processar(evento(cena["canal"], "👍", de_mim=True))
        alvo = next(m for m in conversas.mensagens(cena["conversa"])
                    if m["id"] == cena["mensagem"])
        assert alvo["reacoes"][0]["nosso"] is True

    def test_mensagem_sem_reacao_nao_inventa_lista(self, cena):
        alvo = next(m for m in conversas.mensagens(cena["conversa"])
                    if m["id"] == cena["mensagem"])
        assert not alvo["reacoes"]


def test_a_coluna_antiga_nao_existe_mais():
    """🚨 DUAS VERDADES SOBRE A MESMA COISA É O QUE O `docs/02` PROÍBE. Se a
    coluna voltasse, metade do código escreveria num lugar e a tela leria o
    outro — com tudo respondendo 200."""
    assert banco.um(
        """SELECT count(*) n FROM information_schema.columns
            WHERE table_name = 'mensagem' AND column_name = 'reacao'""")["n"] == 0
