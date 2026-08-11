"""Testes de participantes na conversa — convidar, sair e herdar a posse.

🚨 Escreve em `conversa`, `conversa_participante`, `transferencia` e
`atendente`, que são tabelas de PRODUÇÃO. Segue a mesma disciplina do
`teste_conversas.py`: telefone de DDD inexistente (+55 99 ...), atendentes com
login marcado, e a fixture apaga só o que criou.

⚠️ Os atendentes são criados pelo teste em vez de reusar os 4 reais. A lição é
de 06/08: fixture que usa linha de produção passa com o banco vazio e começa a
ler dado real assim que a base cresce.
"""
import sys
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

FONE = "+5599922220000"
LOGIN = "zz_teste_part_"


def limpar():
    banco.executar(
        """DELETE FROM conversa_participante WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (FONE,))
    banco.executar(
        """DELETE FROM transferencia WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (FONE,))
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (FONE,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (FONE,))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def cena():
    """Uma conversa com dono e três atendentes só deste teste."""
    limpar()
    canal = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not canal:
        pytest.skip("canal atendimento não cadastrado")

    ids = []
    for n in ("dono", "primeiro", "segundo"):
        ids.append(banco.um(
            """INSERT INTO atendente (nome, login, senha_hash, perfil, ativo)
               VALUES (%s, %s, 'x', 'atendimento', true) RETURNING id""",
            (f"Teste {n}", LOGIN + n))["id"])

    conversa = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
           VALUES (%s, %s, 'humano', %s) RETURNING id""",
        (canal["id"], FONE, ids[0]))["id"]
    yield {"conversa": conversa, "dono": ids[0], "a": ids[1], "b": ids[2]}
    limpar()


def dono_de(conversa_id):
    return banco.um("SELECT atendente_id FROM conversa WHERE id = %s",
                    (conversa_id,))["atendente_id"]


class TestConvidar:
    def test_convida_e_aparece_na_lista(self, cena):
        r = conversas.convidar(cena["conversa"], cena["a"], cena["dono"])
        assert r["ok"] is True
        assert [p["atendente_id"] for p in
                conversas.participantes(cena["conversa"])] == [cena["a"]]

    def test_convite_repetido_nao_duplica(self, cena):
        # Conflito esperado se ignora — metodologia §1, a mesma regra do webhook.
        conversas.convidar(cena["conversa"], cena["a"], cena["dono"])
        conversas.convidar(cena["conversa"], cena["a"], cena["dono"])
        assert len(conversas.participantes(cena["conversa"])) == 1

    def test_convite_repetido_NAO_reordena_a_fila_de_heranca(self, cena):
        """🚨 O defeito que este teste pegou em 11/08, antes de ir para a tela.

        `entrou_em` é a fila de herança da posse. O `ON CONFLICT` reescrevia
        `entrou_em = now()` sempre, então reconvidar quem JÁ ESTAVA dentro o
        jogava para o fim da fila — e a posse ia para a pessoa errada, sem
        nada ter acontecido de verdade.
        """
        conversas.convidar(cena["conversa"], cena["a"], cena["dono"])
        conversas.convidar(cena["conversa"], cena["b"], cena["dono"])
        conversas.convidar(cena["conversa"], cena["a"], cena["dono"])  # repetido

        ordem = [p["atendente_id"] for p in conversas.participantes(cena["conversa"])]
        assert ordem == [cena["a"], cena["b"]], "o convite repetido reordenou a fila"

        conversas.sair(cena["conversa"], cena["dono"])
        assert dono_de(cena["conversa"]) == cena["a"], "herdou a pessoa errada"

    def test_nao_convida_quem_ja_e_o_dono(self, cena):
        # Ficar nos dois lugares faria a saída dele ser resolvida duas vezes.
        r = conversas.convidar(cena["conversa"], cena["dono"], cena["dono"])
        assert r["ok"] is False

    def test_nao_convida_atendente_inativo(self, cena):
        banco.executar("UPDATE atendente SET ativo = false WHERE id = %s",
                       (cena["a"],))
        assert conversas.convidar(cena["conversa"], cena["a"], cena["dono"])["ok"] is False

    def test_conversa_inexistente(self, cena):
        assert conversas.convidar(99999999, cena["a"], cena["dono"])["ok"] is False


class TestSair:
    def test_participante_sai_e_o_dono_nao_muda(self, cena):
        conversas.convidar(cena["conversa"], cena["a"], cena["dono"])
        r = conversas.sair(cena["conversa"], cena["a"])
        assert r["ok"] is True and r["novo_dono"] is None
        assert dono_de(cena["conversa"]) == cena["dono"]
        assert conversas.participantes(cena["conversa"]) == []

    def test_dono_sai_e_quem_entrou_primeiro_herda(self, cena):
        """A regra do usuário, 11/08: 'em caso de sair, passa o dono para o
        outro que ficou'."""
        conversas.convidar(cena["conversa"], cena["a"], cena["dono"])
        conversas.convidar(cena["conversa"], cena["b"], cena["dono"])
        r = conversas.sair(cena["conversa"], cena["dono"])
        assert r["novo_dono"] == cena["a"]
        assert dono_de(cena["conversa"]) == cena["a"]

    def test_quem_herda_deixa_de_ser_participante(self, cena):
        # Senão a próxima saída dele seria tratada duas vezes.
        conversas.convidar(cena["conversa"], cena["a"], cena["dono"])
        conversas.sair(cena["conversa"], cena["dono"])
        assert [p["atendente_id"] for p in
                conversas.participantes(cena["conversa"])] == []

    def test_dono_sai_sem_ninguem_volta_para_a_fila(self, cena):
        r = conversas.sair(cena["conversa"], cena["dono"])
        assert r["para_fila"] is True
        assert dono_de(cena["conversa"]) is None
        assert banco.um("SELECT estado FROM conversa WHERE id = %s",
                        (cena["conversa"],))["estado"] == "fila"

    def test_a_troca_de_dono_fica_registrada(self, cena):
        """Sem registro, 'por que esta conversa mudou de dono?' fica sem
        resposta. E o motivo é `saida_do_dono`, não `manual`: quem passou a
        posse foi o sistema (migração 022)."""
        conversas.convidar(cena["conversa"], cena["a"], cena["dono"])
        conversas.sair(cena["conversa"], cena["dono"])
        t = banco.um("SELECT motivo, de_atendente_id, para_atendente_id "
                     "FROM transferencia WHERE conversa_id = %s", (cena["conversa"],))
        assert t["motivo"] == "saida_do_dono"
        assert t["de_atendente_id"] == cena["dono"]
        assert t["para_atendente_id"] == cena["a"]

    def test_herdeiro_inativo_e_pulado(self, cena):
        # Passar a posse para quem está inativo esconderia a conversa de todos.
        conversas.convidar(cena["conversa"], cena["a"], cena["dono"])
        conversas.convidar(cena["conversa"], cena["b"], cena["dono"])
        banco.executar("UPDATE atendente SET ativo = false WHERE id = %s",
                       (cena["a"],))
        assert conversas.sair(cena["conversa"], cena["dono"])["novo_dono"] == cena["b"]

    def test_quem_nao_esta_na_conversa_nao_sai(self, cena):
        assert conversas.sair(cena["conversa"], cena["a"])["ok"] is False


class TestRemover:
    def test_o_dono_remove(self, cena):
        conversas.convidar(cena["conversa"], cena["a"], cena["dono"])
        assert conversas.remover(cena["conversa"], cena["a"], cena["dono"])["ok"] is True
        assert conversas.participantes(cena["conversa"]) == []

    def test_quem_nao_e_dono_nao_remove(self, cena):
        conversas.convidar(cena["conversa"], cena["a"], cena["dono"])
        conversas.convidar(cena["conversa"], cena["b"], cena["dono"])
        assert conversas.remover(cena["conversa"], cena["a"], cena["b"])["ok"] is False

    def test_o_dono_nao_se_remove_por_aqui(self, cena):
        # `sair` é quem resolve a herança; `remover` não saberia para quem passar.
        assert conversas.remover(cena["conversa"], cena["dono"],
                                 cena["dono"])["ok"] is False


class TestOBancoSegura:
    def test_saida_antes_da_entrada_e_impossivel(self, cena):
        """CHECK é contrato: a participação negativa não pode existir nem por
        UPDATE torto nem por relógio errado."""
        conversas.convidar(cena["conversa"], cena["a"], cena["dono"])
        with pytest.raises(psycopg.errors.CheckViolation):
            banco.executar(
                """UPDATE conversa_participante
                      SET saiu_em = entrou_em - interval '1 hour'
                    WHERE conversa_id = %s AND atendente_id = %s""",
                (cena["conversa"], cena["a"]))
