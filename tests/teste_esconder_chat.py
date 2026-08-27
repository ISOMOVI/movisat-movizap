"""Esconder conversa do chat interno — migração 038, 27/08.

Pedido dele: *"Canal interno -> botão de excluir conversa"*, numa tela que ele
mandou desenhar como a caixa de entrada do WhatsApp.

🚨 "EXCLUIR" AQUI TIRA DA MINHA LISTA, NÃO APAGA PARA O OUTRO — e é isso que
estas travas defendem. Apagar a sala levaria junto o histórico de quem não
pediu nada e não tem como desfazer: conversa interna é prova de combinado,
quem disse o quê sobre um atendimento.

⚠️ E VOLTA SOZINHA na próxima mensagem, como no WhatsApp. Esconder não pode
virar um jeito de deixar de receber recado da equipe — que seria o defeito
silencioso desta funcionalidade: a pessoa some da conversa e ninguém sabe.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, chat  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_esconder_"


def limpar():
    alvo = """(SELECT sala_id FROM chat_membro WHERE atendente_id IN
                 (SELECT id FROM atendente WHERE login LIKE %s)
               UNION
               SELECT sala_id FROM chat_mensagem WHERE atendente_id IN
                 (SELECT id FROM atendente WHERE login LIKE %s))"""
    banco.executar(f"DELETE FROM chat_sala WHERE id IN {alvo}",
                   (LOGIN + "%", LOGIN + "%"))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def dois():
    limpar()
    ids = {}
    for n in ("ana", "bruno", "carla"):
        ids[n] = banco.um(
            """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
               VALUES (%s, %s, %s, 'x', 'atendimento', true) RETURNING id""",
            (f"Teste {n}", LOGIN + n, f"{LOGIN}{n}@movisat.com.br"))["id"]
    sala = chat.abrir_direta(ids["ana"], ids["bruno"])["sala_id"]
    chat.escrever(sala, ids["ana"], "oi")
    yield {"ids": ids, "sala": sala}
    limpar()


def _ve(quem_id, sala_id) -> bool:
    return any(s["id"] == sala_id for s in chat.salas(quem_id))


class TestEscondeSoParaMim:
    def test_some_da_minha_lista(self, dois):
        ids, sala = dois["ids"], dois["sala"]
        assert _ve(ids["ana"], sala)
        chat.esconder(sala, ids["ana"])
        assert not _ve(ids["ana"], sala)

    def test_a_outra_pessoa_continua_vendo(self, dois):
        """🚨 O CORAÇÃO DISTO. Se esta afirmação cair, "excluir" virou
        "apagar para os dois" e ninguém pediu isso."""
        ids, sala = dois["ids"], dois["sala"]
        chat.esconder(sala, ids["ana"])
        assert _ve(ids["bruno"], sala)

    def test_nenhuma_mensagem_e_apagada(self, dois):
        ids, sala = dois["ids"], dois["sala"]
        antes = len(chat.mensagens(sala, ids["bruno"]))
        chat.esconder(sala, ids["ana"])
        assert len(chat.mensagens(sala, ids["bruno"])) == antes
        # e continuam lá para quem escondeu, quando ele voltar
        assert len(chat.mensagens(sala, ids["ana"])) == antes

    def test_a_sala_continua_existindo(self, dois):
        ids, sala = dois["ids"], dois["sala"]
        chat.esconder(sala, ids["ana"])
        assert banco.um("SELECT id FROM chat_sala WHERE id = %s", (sala,))

    def test_quem_nao_e_membro_nao_esconde(self, dois):
        """⚠️ A primeira versão deste teste criava um grupo de UMA pessoa, e
        `criar_grupo` recusa -- com razão: *"um grupo precisa de mais
        alguém"*. O teste é que estava errado, não o sistema."""
        ids = dois["ids"]
        outra = chat.abrir_direta(ids["bruno"], ids["carla"])["sala_id"]
        r = chat.esconder(outra, ids["ana"])
        assert r["ok"] is False


class TestVoltaSozinha:
    def test_mensagem_nova_traz_a_conversa_de_volta(self, dois):
        """⚠️ O DEFEITO QUE ISTO IMPEDE: esconder virar um jeito de deixar de
        receber recado da equipe, em silêncio."""
        ids, sala = dois["ids"], dois["sala"]
        chat.esconder(sala, ids["ana"])
        assert not _ve(ids["ana"], sala)
        chat.escrever(sala, ids["bruno"], "voltei")
        assert _ve(ids["ana"], sala)

    def test_a_mensagem_que_volta_conta_como_nao_lida(self, dois):
        ids, sala = dois["ids"], dois["sala"]
        chat.esconder(sala, ids["ana"])
        chat.escrever(sala, ids["bruno"], "urgente")
        linha = next(s for s in chat.salas(ids["ana"]) if s["id"] == sala)
        assert linha["nao_lidas"] >= 1

    def test_esconder_de_novo_funciona(self, dois):
        ids, sala = dois["ids"], dois["sala"]
        chat.esconder(sala, ids["ana"])
        chat.escrever(sala, ids["bruno"], "de novo")
        assert _ve(ids["ana"], sala)
        chat.esconder(sala, ids["ana"])
        assert not _ve(ids["ana"], sala)

    def test_mostrar_desfaz_na_hora(self, dois):
        """Abrir a conversa pelo endereço chama isto: quem voltou está dizendo
        que quer a conversa de volta."""
        ids, sala = dois["ids"], dois["sala"]
        chat.esconder(sala, ids["ana"])
        chat.mostrar(sala, ids["ana"])
        assert _ve(ids["ana"], sala)

    def test_sala_sem_mensagem_escondida_continua_escondida(self, dois):
        """⚠️ Sem o `COALESCE`, a comparação com NULL não seria verdadeira nem
        falsa, e a sala vazia voltaria sozinha sem ninguém ter escrito."""
        ids = dois["ids"]
        vazia = chat.criar_grupo("zz grupo vazio", ids["ana"], [ids["bruno"]])["sala_id"]
        chat.esconder(vazia, ids["ana"])
        assert not _ve(ids["ana"], vazia)


class TestABarraDeDistincao:
    """🚨 O pedido dele foi de desenho e a razão é de risco: quanto mais esta
    tela se parecer com a caixa de entrada, mais fácil escrever para o colega
    achando que é o cliente."""

    def _tela(self) -> str:
        return Path("/home/claude/movizap_painel/frontend/src/telas/"
                    "ChatInterno.vue").read_text(encoding="utf-8")

    def test_a_barra_existe_e_diz_que_o_cliente_nao_ve(self):
        fonte = self._tela()
        assert 'class="barra-interna"' in fonte
        assert "chega ao cliente" in fonte

    def test_a_barra_e_a_primeira_coisa_da_tela(self):
        """Aviso depois do conteúdo avisa quem já rolou -- ou seja, quem já
        estava escrevendo."""
        fonte = self._tela()
        i_barra = fonte.index('class="barra-interna"')
        i_cabecalho = fonte.index('class="tela__cabecalho"')
        assert i_barra < i_cabecalho

    def test_o_botao_de_excluir_nao_promete_apagar_para_todos(self):
        """⚠️ "Excluir conversa" sem mais nada faria parecer que apaga para os
        dois. O rótulo tem de dizer que é a MINHA lista."""
        fonte = self._tela()
        assert "Tirar esta conversa da minha lista" in fonte
