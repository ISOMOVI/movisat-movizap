"""Testes do vigia dos canais.

O que se protege aqui, e por que cada um existe:

  - 🚨 `_uma_ronda` voltar a ser `async def`. Na primeira versao ela era, e
    `asyncio.to_thread` a rodava na thread devolvendo uma corrotina que
    ninguem aguardava: o vigia subia, logava "ativo" e NAO FAZIA NADA. O
    Python so reclamou com um RuntimeWarning, que nao aparece em producao.
    Este e o teste mais importante do arquivo.

  - Evolution fora do ar gravando 'desconectado' -- queda que nunca houve,
    poluindo justamente o historico que existe para datar quedas.

  - ronda sem mudanca gravando linha igual.
"""
import asyncio
import inspect
import sys

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco, canais, evolution, vigia  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield
    banco.fechar()


@pytest.fixture
def canal_id():
    """🚨 Canal DESCARTAVEL, nunca o de producao.

    A primeira versao destes testes rodou contra o canal `atendimento` real e
    deixou no historico duas transicoes para 'conectado' que nunca
    aconteceram. A tabela existe exatamente para nao mentir sobre quando o
    canal caiu -- e o teste a fez mentir.

    Teste que escreve em tabela de producao precisa da propria linha, e
    precisa levar embora o que criou.
    """
    banco.executar(
        "INSERT INTO canal (nome,tipo,gateway,instancia,modo,ativo) "
        "VALUES ('Teste do vigia','atendimento','evolution','zz-teste-vigia',"
        "'baileys',true) ON CONFLICT DO NOTHING")
    cid = banco.um("SELECT id FROM canal WHERE instancia='zz-teste-vigia'")["id"]
    banco.executar("DELETE FROM canal_evento WHERE canal_id=%s", (cid,))
    yield cid
    banco.executar("DELETE FROM canal_evento WHERE canal_id=%s", (cid,))
    banco.executar("DELETE FROM canal WHERE id=%s", (cid,))


def _eventos(cid):
    return banco.um("SELECT COUNT(*) AS n FROM canal_evento WHERE canal_id=%s",
                    (cid,))["n"]


class TestARondaEhSincrona:
    """Se este teste falhar, o vigia virou enfeite outra vez."""

    def test_uma_ronda_nao_e_corrotina(self):
        assert not inspect.iscoroutinefunction(vigia._uma_ronda), (
            "_uma_ronda voltou a ser async: `asyncio.to_thread` vai devolver "
            "uma corrotina nao aguardada e o vigia nao vai rodar")

    def test_chamar_a_ronda_nao_devolve_corrotina(self, canal_id, monkeypatch):
        monkeypatch.setattr(evolution, "estado", lambda _: "close")
        resultado = vigia._uma_ronda(canal_id)
        assert not asyncio.iscoroutine(resultado)


class TestEvolutionForaDoAr:
    def test_falha_nao_grava_desconectado(self, canal_id, monkeypatch):
        # deixa o ultimo estado diferente de 'desconectado'
        canais.registrar_evento(canal_id, "conectado", "preparo do teste")
        antes = _eventos(canal_id)

        def explodir(_):
            raise evolution.ErroEvolution("Evolution nao respondeu.", 0)
        monkeypatch.setattr(evolution, "estado", explodir)

        vigia._uma_ronda(canal_id)
        assert _eventos(canal_id) == antes, (
            "gravou queda que nunca houve: Evolution fora do ar nao e canal "
            "desconectado")

    def test_falha_repetida_nao_derruba_a_ronda(self, canal_id, monkeypatch):
        def explodir(_):
            raise evolution.ErroEvolution("x", 0)
        monkeypatch.setattr(evolution, "estado", explodir)
        for _ in range(vigia.LIMITE_AVISO + 2):
            vigia._uma_ronda(canal_id)   # nao pode levantar


class TestSoGravaMudanca:
    def test_estado_igual_nao_cria_linha(self, canal_id, monkeypatch):
        monkeypatch.setattr(evolution, "estado", lambda _: "close")
        vigia._uma_ronda(canal_id)   # leva ao estado 'desconectado'
        antes = _eventos(canal_id)
        for _ in range(3):
            vigia._uma_ronda(canal_id)
        assert _eventos(canal_id) == antes

    def test_estado_diferente_cria_uma_linha(self, canal_id, monkeypatch):
        monkeypatch.setattr(evolution, "estado", lambda _: "close")
        vigia._uma_ronda(canal_id)
        antes = _eventos(canal_id)

        monkeypatch.setattr(evolution, "estado", lambda _: "open")
        vigia._uma_ronda(canal_id)
        assert _eventos(canal_id) == antes + 1

        ultimo = banco.um("SELECT estado, motivo FROM canal_evento "
                          "WHERE canal_id=%s ORDER BY em DESC LIMIT 1", (canal_id,))
        assert ultimo["estado"] == "conectado"
        assert "vigia" in (ultimo["motivo"] or "")

        # devolve ao estado real para nao deixar o banco mentindo
        monkeypatch.setattr(evolution, "estado", lambda _: "close")
        vigia._uma_ronda(canal_id)


class TestLaco:
    def test_para_quando_mandam_parar(self, monkeypatch):
        monkeypatch.setattr(evolution, "estado", lambda _: "close")

        async def correr():
            parar = asyncio.Event()
            tarefa = asyncio.create_task(vigia.rodar(parar))
            await asyncio.sleep(0.2)
            parar.set()
            await asyncio.wait_for(tarefa, timeout=5)

        asyncio.run(correr())

    def test_erro_na_ronda_nao_mata_o_laco(self, monkeypatch):
        # vigia que morre em silencio e pior que vigia nenhum
        def explodir():
            raise RuntimeError("falha inesperada")
        monkeypatch.setattr(vigia, "_uma_ronda", explodir)
        monkeypatch.setattr(vigia, "INTERVALO_SEG", 0.05)

        async def correr():
            parar = asyncio.Event()
            tarefa = asyncio.create_task(vigia.rodar(parar))
            await asyncio.sleep(0.2)
            assert not tarefa.done(), "o laco morreu na primeira excecao"
            parar.set()
            await asyncio.wait_for(tarefa, timeout=5)

        asyncio.run(correr())
