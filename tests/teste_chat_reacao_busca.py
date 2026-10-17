"""ATD_6.1 — reagir e buscar no Chat interno. 🔵 16/10, "como do externo".

A Caixa reage desde 034/036 e busca dentro da conversa desde 25/08; o Chat
interno não tinha nenhuma das duas.

🚨 Escreve em `chat_sala`, `chat_membro`, `chat_mensagem`, `chat_reacao` e
`atendente`, que são tabelas de PRODUÇÃO. Logins com prefixo `zz`, e a fixture
apaga só o que criou (mesmo desenho do `teste_chat.py`).
"""
import re
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

TELAS = Path("/home/claude/movizap_painel/frontend/src/telas")
LOGIN = "zz_teste_reacao_"
JOINHA, CORACAO, RISO = chat.REACOES[0], chat.REACOES[1], chat.REACOES[2]


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
def gente():
    limpar()
    ids = {}
    for n in ("ana", "bruno", "carla"):
        ids[n] = banco.um(
            """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
               VALUES (%s, %s, %s, 'x', 'atendimento', true) RETURNING id""",
            (f"Teste {n}", LOGIN + n, f"{LOGIN}{n}@movisat.com.br"))["id"]
    yield ids
    limpar()


@pytest.fixture()
def sala(gente):
    """Sala direta ana × bruno, com uma mensagem da ana. A carla fica de fora."""
    s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
    m = chat.escrever(s, gente["ana"], "bom dia, zzpalavra do teste")["mensagem_id"]
    return {"id": s, "msg": m}


def _msg(sala_id, eu, mensagem_id):
    return next(m for m in chat.mensagens(sala_id, eu) if m["id"] == mensagem_id)


class TestReagir:
    def test_reage_e_quem_le_ve_com_NOME(self, gente, sala):
        assert chat.reagir(sala["id"], sala["msg"], gente["bruno"], JOINHA)["ok"]

        da_ana = _msg(sala["id"], gente["ana"], sala["msg"])
        assert da_ana["reacoes"] == [
            {"emoji": JOINHA, "n": 1, "minha": False, "nomes": ["Teste bruno"]}]
        assert da_ana["minha_reacao"] is None

        do_bruno = _msg(sala["id"], gente["bruno"], sala["msg"])
        assert do_bruno["reacoes"][0]["minha"] is True
        assert do_bruno["minha_reacao"] == JOINHA

    def test_reagir_de_novo_TROCA_em_vez_de_somar(self, gente, sala):
        """🚨 Uma por pessoa: a chave (mensagem, atendente) é a trava."""
        chat.reagir(sala["id"], sala["msg"], gente["bruno"], JOINHA)
        chat.reagir(sala["id"], sala["msg"], gente["bruno"], CORACAO)
        m = _msg(sala["id"], gente["ana"], sala["msg"])
        assert [r["emoji"] for r in m["reacoes"]] == [CORACAO]
        assert banco.um("SELECT count(*) AS n FROM chat_reacao WHERE mensagem_id = %s",
                        (sala["msg"],))["n"] == 1

    def test_emoji_VAZIO_tira(self, gente, sala):
        chat.reagir(sala["id"], sala["msg"], gente["bruno"], JOINHA)
        r = chat.reagir(sala["id"], sala["msg"], gente["bruno"], "")
        assert r == {"ok": True, "mensagem_id": sala["msg"], "reacao": None}
        assert _msg(sala["id"], gente["ana"], sala["msg"])["reacoes"] == []

    def test_agrupa_por_emoji_do_mais_usado_para_o_menos(self, gente):
        g = chat.criar_grupo("zz grupo de reacao", gente["ana"],
                             [gente["bruno"], gente["carla"]])["sala_id"]
        m = chat.escrever(g, gente["ana"], "zz mensagem do grupo")["mensagem_id"]
        chat.reagir(g, m, gente["bruno"], RISO)
        chat.reagir(g, m, gente["ana"], JOINHA)
        chat.reagir(g, m, gente["carla"], JOINHA)
        r = _msg(g, gente["ana"], m)["reacoes"]
        assert [(x["emoji"], x["n"]) for x in r] == [(JOINHA, 2), (RISO, 1)]
        assert sorted(r[0]["nomes"]) == ["Teste ana", "Teste carla"]

    def test_pode_reagir_a_PROPRIA_mensagem(self, gente, sala):
        assert chat.reagir(sala["id"], sala["msg"], gente["ana"], JOINHA)["ok"]

    @pytest.mark.parametrize("fora", ["\U0001F525", "oi", "👍👍"])
    def test_emoji_FORA_da_lista_recusa(self, gente, sala, fora):
        """Sem a lista fechada a rota viraria um segundo campo de texto."""
        r = chat.reagir(sala["id"], sala["msg"], gente["bruno"], fora)
        assert r["ok"] is False
        assert "lista" in r["motivo"]

    def test_quem_NAO_esta_na_sala_nao_reage(self, gente, sala):
        r = chat.reagir(sala["id"], sala["msg"], gente["carla"], JOINHA)
        assert r["ok"] is False

    def test_mensagem_de_OUTRA_sala_recusa(self, gente, sala):
        outra = chat.abrir_direta(gente["ana"], gente["carla"])["sala_id"]
        r = chat.reagir(outra, sala["msg"], gente["ana"], JOINHA)
        assert r["ok"] is False
        assert "nesta sala" in r["motivo"]

    def test_mensagem_APAGADA_nao_recebe_reacao(self, gente, sala):
        chat.apagar_propria(sala["id"], sala["msg"], gente["ana"])
        r = chat.reagir(sala["id"], sala["msg"], gente["bruno"], JOINHA)
        assert r["ok"] is False
        assert "apagada" in r["motivo"]

    def test_reacao_some_da_apagada_para_quem_NAO_e_owner(self, gente, sala,
                                                         monkeypatch):
        """Mesma regra do texto (05/10): o conteúdo some, a reação some junto."""
        chat.reagir(sala["id"], sala["msg"], gente["bruno"], JOINHA)
        chat.apagar_propria(sala["id"], sala["msg"], gente["ana"])

        monkeypatch.setattr(chat, "_eh_owner", lambda _id: False)
        assert _msg(sala["id"], gente["bruno"], sala["msg"])["reacoes"] == []
        monkeypatch.setattr(chat, "_eh_owner", lambda _id: True)
        assert len(_msg(sala["id"], gente["bruno"], sala["msg"])["reacoes"]) == 1

    def test_reagir_NAO_vira_nao_lida(self, gente, sala):
        """Reação não é mensagem: não acende selo, não mexe em `lido_ate`."""
        chat.marcar_lido(sala["id"], gente["ana"])
        antes = chat.nao_lidas(gente["ana"])
        chat.reagir(sala["id"], sala["msg"], gente["bruno"], JOINHA)
        assert chat.nao_lidas(gente["ana"]) == antes

    def test_as_tres_listas_de_emoji_sao_IGUAIS(self):
        """🚨 Caixa, Chat interno e backend: se uma divergir, a tela oferece
        um emoji que a rota recusa -- ou a Caixa e o Chat reagem diferente."""
        for arquivo in ("CaixaDeEntrada.vue", "ChatInterno.vue"):
            fonte = (TELAS / arquivo).read_text(encoding="utf-8")
            achada = re.search(r"const REACOES = \[([^\]]*)\]", fonte)
            assert achada, f"{arquivo} sem const REACOES"
            assert tuple(re.findall(r"'([^']+)'", achada.group(1))) == chat.REACOES, arquivo


class TestBuscar:
    def test_acha_e_devolve_a_POSICAO(self, gente, sala):
        r = chat.buscar(sala["id"], gente["bruno"], "ZZPALAVRA")
        assert r["ok"] is True
        assert [a["id"] for a in r["achados"]] == [sala["msg"]]
        assert r["limitado"] is False

    def test_termo_vazio_nao_devolve_a_sala_inteira(self, gente, sala):
        assert chat.buscar(sala["id"], gente["ana"], "   ")["achados"] == []

    def test_quem_NAO_esta_na_sala_nao_busca(self, gente, sala):
        assert chat.buscar(sala["id"], gente["carla"], "zzpalavra")["ok"] is False

    def test_acha_o_que_esta_FORA_da_janela_carregada(self, gente, sala):
        """🚨 Por isso roda no servidor: a tela só tem as mais recentes."""
        for i in range(3):
            chat.escrever(sala["id"], gente["bruno"], f"zz ruido {i}")
        janela = chat.mensagens(sala["id"], gente["ana"], limite=2)
        assert sala["msg"] not in [m["id"] for m in janela]
        achados = chat.buscar(sala["id"], gente["ana"], "zzpalavra")["achados"]
        assert [a["id"] for a in achados] == [sala["msg"]]

    def test_ordem_da_sala_e_teto_DECLARADO(self, gente, sala):
        for i in range(3):
            chat.escrever(sala["id"], gente["bruno"], f"zzrepetido {i}")
        tudo = chat.buscar(sala["id"], gente["ana"], "zzrepetido")["achados"]
        assert [a["id"] for a in tudo] == sorted(a["id"] for a in tudo)
        cortado = chat.buscar(sala["id"], gente["ana"], "zzrepetido", limite=2)
        assert len(cortado["achados"]) == 2
        assert cortado["limitado"] is True

    def test_APAGADA_nao_e_achada_por_quem_nao_e_owner(self, gente, sala,
                                                       monkeypatch):
        """Achar a posição de um balão vazio entregaria o que ali dizia."""
        chat.apagar_propria(sala["id"], sala["msg"], gente["ana"])
        monkeypatch.setattr(chat, "_eh_owner", lambda _id: False)
        assert chat.buscar(sala["id"], gente["bruno"], "zzpalavra")["achados"] == []
        monkeypatch.setattr(chat, "_eh_owner", lambda _id: True)
        assert len(chat.buscar(sala["id"], gente["bruno"], "zzpalavra")["achados"]) == 1
