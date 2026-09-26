"""Atendentes como controle de RH e o interruptor Ativo/Inativo (25/09).

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
    # ⚠️ ATIVO E COM ORDEM (25/09): `LIMIT 1` sem ordem devolveu o time 7,
    # inativo, e a listagem padrão (só ativos) não o achava.
    um_time = banco.um("SELECT id FROM time WHERE ativo ORDER BY id LIMIT 1")["id"]
    banco.executar(
        "INSERT INTO atendente_time (atendente_id, time_id) VALUES (%s, %s)",
        (quem, um_time))
    conversa = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
           VALUES (%s, %s, 'humano', %s) RETURNING id""",
        (canal["id"], FONE, quem))["id"]
    yield {"quem": quem, "conversa": conversa, "time": um_time}
    limpar()


def colega_disponivel():
    """Quem recebe as conversas de quem fica inativo."""
    return banco.um(
        """INSERT INTO atendente (nome, login, email, perfil, ativo, estado)
           VALUES ('Teste RH Colega', %s, %s, 'atendimento', true, 'disponivel')
           RETURNING id""",
        (LOGIN + "colega", f"{LOGIN}colega@movisat.com.br"))["id"]


class TestInativarPassaAsConversas:
    """🔵 25/09: o interruptor Ativo/Inativo no lugar do "desligar" --
    *"inativo não loga a conta permanece lá"*."""

    def test_com_conversa_aberta_exige_quem_recebe(self, cena):
        """🚨 O DEFEITO DE 07/08: inativo segurando conversa que ninguém vê."""
        with pytest.raises(operacao.DadoInvalido, match="receb"):
            operacao.definir_ativo(cena["quem"], False)
        assert banco.um("SELECT ativo FROM atendente WHERE id = %s",
                        (cena["quem"],))["ativo"] is True

    def test_a_conversa_vai_para_quem_foi_escolhido(self, cena):
        colega = colega_disponivel()
        r = operacao.definir_ativo(cena["quem"], False, transferir_para=colega)
        assert r["ok"] is True and r["transferidas"] == 1
        assert banco.um("SELECT atendente_id FROM conversa WHERE id = %s",
                        (cena["conversa"],))["atendente_id"] == colega

    def test_a_conta_fica_como_estava(self, cena):
        """O antigo desligar apagava senha, `google_sub` e times, e não tinha
        volta. Agora a conta fica, e reativar devolve tudo."""
        banco.executar("UPDATE atendente SET google_sub = 'sub-rh' WHERE id = %s",
                       (cena["quem"],))
        operacao.definir_ativo(cena["quem"], False, transferir_para=colega_disponivel())
        linha = banco.um(
            "SELECT senha_hash, google_sub, email, ativo FROM atendente WHERE id = %s",
            (cena["quem"],))
        assert linha["ativo"] is False
        assert linha["senha_hash"] == "hash-falso" and linha["google_sub"] == "sub-rh"
        assert linha["email"] == f"{LOGIN}sai@movisat.com.br"
        assert banco.um("SELECT count(*) n FROM atendente_time WHERE atendente_id = %s",
                        (cena["quem"],))["n"] == 1

    def test_reativar_devolve_a_conta_offline(self, cena):
        operacao.definir_ativo(cena["quem"], False, transferir_para=colega_disponivel())
        r = operacao.definir_ativo(cena["quem"], True)
        assert r["ativo"] is True
        linha = banco.um("SELECT ativo, estado FROM atendente WHERE id = %s", (cena["quem"],))
        assert linha["ativo"] is True and linha["estado"] == "offline"

    def test_inativo_nao_entra_e_a_sessao_cai(self, cena):
        """A sessão aberta cai na chamada seguinte: `get_usuario` relê `ativo`."""
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials
        from movizap import auth
        token = auth.criar_token(LOGIN + "sai")
        operacao.definir_ativo(cena["quem"], False, transferir_para=colega_disponivel())
        with pytest.raises(HTTPException) as e:
            auth.get_usuario(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
        assert e.value.status_code == 401

    def test_conversa_CONCLUIDA_nao_e_mexida(self, cena):
        conversas.encerrar(cena["conversa"], atendente_id=cena["quem"])
        r = operacao.definir_ativo(cena["quem"], False)
        assert r["ok"] is True and r["transferidas"] == 0

    def test_o_historico_continua_com_o_nome(self, cena):
        """🚨 NADA É APAGADO. `conversa`, `transferencia` e `mensagem` apontam
        para o atendente."""
        conversas.encerrar(cena["conversa"], atendente_id=cena["quem"])
        operacao.definir_ativo(cena["quem"], False)
        achada = [c for c in conversas.historico(busca=FONE)
                  if c["id"] == cena["conversa"]]
        assert achada[0]["atendente_nome"] == "Teste RH"


class TestAsTravasDoInterruptor:
    def test_ninguem_inativa_a_si_mesmo(self, cena):
        with pytest.raises(operacao.EmUso):
            operacao.definir_ativo(cena["quem"], False, quem_edita=LOGIN + "sai")

    def test_repetir_o_mesmo_estado_nao_faz_nada(self, cena):
        conversas.encerrar(cena["conversa"], atendente_id=cena["quem"])
        operacao.definir_ativo(cena["quem"], False)
        assert operacao.definir_ativo(cena["quem"], False)["transferidas"] == 0

    def test_o_ultimo_owner_ativo_nao_e_inativado(self):
        """🔵 *"sistema nunca pode ficar com menos de 1 owner ativo"*.

        🚨 RODA CONTRA O OWNER DE VERDADE (a suíte está em produção). Só roda
        com exatamente um owner ativo -- é aí que a trava tem de segurar -- e,
        se ela falhar, o `finally` devolve a conta na hora."""
        donos = banco.varios("SELECT id FROM atendente WHERE owner AND ativo")
        if len(donos) != 1:
            pytest.skip("o teste só faz sentido com um owner ativo")
        dono = donos[0]["id"]
        try:
            with pytest.raises(operacao.EmUso):
                operacao.definir_ativo(dono, False)
        finally:
            banco.executar("UPDATE atendente SET ativo = true WHERE id = %s", (dono,))
        assert banco.um("SELECT ativo FROM atendente WHERE id = %s", (dono,))["ativo"] is True

    def test_a_edicao_nao_mexe_em_ativo(self):
        """🚨 Pela edição, `ativo = false` pulava tudo o que inativar faz."""
        import inspect
        from movizap.main import AtendenteEntrada
        assert "ativo" not in inspect.signature(operacao.atualizar_atendente).parameters
        assert "ativo" not in AtendenteEntrada.model_fields
        assert "max_conversas" not in AtendenteEntrada.model_fields


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
