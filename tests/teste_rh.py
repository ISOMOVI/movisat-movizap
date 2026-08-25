"""Atendentes como controle de RH e o desligamento que solta as conversas.

🚨 O QUE FALTAVA NÃO ERA O BOTÃO, ERA O EFEITO. Desativar gravava
`ativo = false` e nada mais: quem saía da empresa com conversas abertas
deixava dono que nunca mais entra, e elas ficavam INVISÍVEIS -- não aparecem
em "sem dono" porque TÊM dono, e ninguém as vê porque o dono não entra.

🚨 Escreve em `atendente`, `conversa` e `config`, tabelas de PRODUÇÃO.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas, operacao  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

PREFIXO = "+559997777%"
FONE = "+5599977770001"
LOGIN = "zz_teste_rh_"


def limpar():
    banco.executar(
        """DELETE FROM conversa_participante WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar(
        """DELETE FROM transferencia WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 LIKE %s", (PREFIXO,))
    banco.executar(
        """DELETE FROM atendente_time WHERE atendente_id IN
           (SELECT id FROM atendente WHERE login LIKE %s)""", (LOGIN + "%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    antes = operacao.jornada_ativa()
    limpar()
    yield
    limpar()
    operacao.definir_jornada_ativa(antes)
    banco.fechar()


@pytest.fixture()
def cena():
    limpar()
    canal = banco.um(
        "SELECT id FROM canal WHERE tipo = 'atendimento' AND ativo LIMIT 1")
    if not canal:
        pytest.skip("nenhum canal de atendimento ativo")
    quem = banco.um(
        """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
           VALUES ('Teste RH', %s, %s, 'hash-falso', 'atendimento', true)
           RETURNING id""",
        (LOGIN + "sai", f"{LOGIN}sai@movisat.com.br"))["id"]
    um_time = banco.um("SELECT id FROM time LIMIT 1")["id"]
    banco.executar(
        "INSERT INTO atendente_time (atendente_id, time_id) VALUES (%s, %s)",
        (quem, um_time))
    conversa = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
           VALUES (%s, %s, 'humano', %s) RETURNING id""",
        (canal["id"], FONE, quem))["id"]
    yield {"quem": quem, "conversa": conversa, "time": um_time}
    limpar()


class TestDesligarSoltaOQueEstavaPreso:
    def test_a_conversa_volta_para_a_fila(self, cena):
        """🚨 O DEFEITO QUE ISTO CONSERTA. Sem soltar, a conversa fica com dono
        que nunca mais entra -- e não aparece em "sem dono" porque TEM dono."""
        r = operacao.desligar(cena["quem"])
        assert r["ok"] is True
        assert r["conversas_soltas"] == 1
        linha = banco.um("SELECT atendente_id, estado FROM conversa WHERE id = %s",
                         (cena["conversa"],))
        assert linha["atendente_id"] is None
        assert linha["estado"] == "fila"

    def test_a_conversa_solta_APARECE_em_sem_dono(self, cena):
        operacao.desligar(cena["quem"])
        achadas = [c["id"] for c in conversas.listar(sem_dono=True, limite=500)]
        assert cena["conversa"] in achadas

    def test_a_senha_e_revogada(self, cena):
        """Conta sem senha não entra: `validar_login` barra antes do bcrypt.
        É a porta fechando junto com o crachá."""
        operacao.desligar(cena["quem"])
        linha = banco.um(
            "SELECT senha_hash, google_sub, ativo FROM atendente WHERE id = %s",
            (cena["quem"],))
        assert linha["senha_hash"] is None
        assert linha["google_sub"] is None
        assert linha["ativo"] is False

    def test_sai_dos_times(self, cena):
        operacao.desligar(cena["quem"])
        assert banco.um(
            "SELECT count(*) n FROM atendente_time WHERE atendente_id = %s",
            (cena["quem"],))["n"] == 0

    def test_conversa_CONCLUIDA_nao_e_mexida(self, cena):
        """Ela já não tem dono e já saiu da fila: soltar de novo mudaria o
        histórico sem motivo."""
        conversas.encerrar(cena["conversa"], atendente_id=cena["quem"])
        r = operacao.desligar(cena["quem"])
        assert r["conversas_soltas"] == 0

    def test_o_historico_continua_com_o_nome(self, cena):
        """🚨 NADA É APAGADO. `conversa`, `transferencia` e `mensagem` apontam
        para o atendente."""
        conversas.encerrar(cena["conversa"], atendente_id=cena["quem"])
        operacao.desligar(cena["quem"])
        achada = [c for c in conversas.historico(busca=FONE)
                  if c["id"] == cena["conversa"]]
        assert achada[0]["atendente_nome"] == "Teste RH"


class TestOQueNaoSeDesliga:
    def test_o_owner_nao_e_desligado(self, cena):
        dono = banco.um("SELECT id FROM atendente WHERE owner AND ativo LIMIT 1")
        r = operacao.desligar(dono["id"])
        assert r["ok"] is False
        assert "owner" in r["motivo"].lower()

    def test_ninguem_desliga_a_si_mesmo(self, cena):
        r = operacao.desligar(cena["quem"], quem_edita=LOGIN + "sai")
        assert r["ok"] is False

    def test_desligar_duas_vezes_e_recusado(self, cena):
        operacao.desligar(cena["quem"])
        assert operacao.desligar(cena["quem"])["ok"] is False


class TestONumeroDeRH:
    def test_a_listagem_traz_o_que_a_tela_desenha(self, cena):
        """Regra prendida depois do defeito da estrela: campo que a tela
        desenha tem de vir na consulta que a tela pede."""
        eu = next(a for a in operacao.listar_atendentes()
                  if a["id"] == cena["quem"])
        for campo in ("em_aberto", "concluidas_semana", "no_horario",
                      "tem_jornada"):
            assert campo in eu, campo

    def test_conta_a_conversa_em_aberto(self, cena):
        eu = next(a for a in operacao.listar_atendentes()
                  if a["id"] == cena["quem"])
        assert eu["em_aberto"] == 1

    def test_conta_a_concluida_da_semana(self, cena):
        conversas.encerrar(cena["conversa"], atendente_id=cena["quem"])
        eu = next(a for a in operacao.listar_atendentes()
                  if a["id"] == cena["quem"])
        assert eu["concluidas_semana"] == 1
        assert eu["em_aberto"] == 0

    def test_sem_jornada_e_diferente_de_fora_do_horario(self, cena):
        """🚨 Sem a distinção, quem nunca cadastrou escala aparece como se
        estivesse fora do expediente -- e isso lê como defeito."""
        eu = next(a for a in operacao.listar_atendentes()
                  if a["id"] == cena["quem"])
        assert eu["tem_jornada"] is False
        assert eu["no_horario"] is False


class TestOInterruptorDaJornada:
    def test_liga_e_desliga(self, cena):
        operacao.definir_jornada_ativa(True)
        assert operacao.jornada_ativa() is True
        operacao.definir_jornada_ativa(False)
        assert operacao.jornada_ativa() is False


class TestTimesTrazemAFila:
    def test_a_listagem_traz_na_fila_e_quem_ve(self, cena):
        t = next(x for x in operacao.listar_times() if x["id"] == cena["time"])
        assert "na_fila" in t
        # ⚠️ Lista vazia aqui significa que TODO MUNDO vê: padrão permissivo.
        assert isinstance(t["quem_ve"], list)
