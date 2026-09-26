"""Testes das telas de operação — CAD_2.1, CAD_2.2 e CFG_4.1.

🚨 TODO TESTE AQUI ESCREVE EM TABELA DE PRODUÇÃO, e por isso cria a PRÓPRIA
linha e a apaga no fim. Em 06/08 três testes do sync passaram a ler a linha
real da Pastelaria Velasco assim que o banco deixou de estar vazio: a suíte
continuou verde e passou a não provar mais nada. O prefixo `zz_teste_` existe
para essas linhas nunca se confundirem com as 7 reais.

⚠️ Nenhum teste desativa uma linha de produção. `time`, `atendente` e
`classificacao` são apontados por `conversa` e `transferencia`.
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, operacao  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

PREFIXO = "zz_teste_"


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield
    # Limpeza em ordem de dependência: vínculo, jornada, depois as linhas.
    banco.executar(
        "DELETE FROM atendente_time WHERE atendente_id IN "
        "(SELECT id FROM atendente WHERE login LIKE %s)", (PREFIXO + "%",))
    banco.executar(
        "DELETE FROM atendente_jornada WHERE atendente_id IN "
        "(SELECT id FROM atendente WHERE login LIKE %s)", (PREFIXO + "%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (PREFIXO + "%",))
    banco.executar("UPDATE time SET time_transbordo_id = NULL WHERE nome LIKE %s",
                   (PREFIXO + "%",))
    banco.executar("DELETE FROM time WHERE nome LIKE %s", (PREFIXO + "%",))
    banco.executar("DELETE FROM classificacao WHERE nome LIKE %s", (PREFIXO + "%",))
    banco.fechar()


@pytest.fixture
def um_time():
    t = operacao.criar_time(f"{PREFIXO}alfa", "time de teste")
    yield t
    banco.executar("UPDATE time SET time_transbordo_id = NULL WHERE time_transbordo_id = %s",
                   (t["id"],))
    banco.executar("DELETE FROM time WHERE id = %s", (t["id"],))


@pytest.fixture
def um_atendente():
    a = operacao.criar_atendente(f"{PREFIXO}Fulano", f"{PREFIXO}fulano")
    yield a
    banco.executar("DELETE FROM atendente_time WHERE atendente_id = %s", (a["id"],))
    banco.executar("DELETE FROM atendente_jornada WHERE atendente_id = %s", (a["id"],))
    banco.executar("DELETE FROM atendente WHERE id = %s", (a["id"],))


# ------------------------------------------------------------------- times

def test_time_nasce_ativo_e_sem_ninguem(um_time):
    assert um_time["ativo"] is True
    assert um_time["qtd_membros"] == 0


def test_nome_de_time_repetido_e_recusado(um_time):
    with pytest.raises(operacao.DadoInvalido):
        operacao.criar_time(um_time["nome"])


def test_time_nao_transborda_para_si_mesmo(um_time):
    with pytest.raises(operacao.DadoInvalido):
        operacao.atualizar_time(um_time["id"], um_time["nome"], None, um_time["id"])


def test_ciclo_de_transbordo_e_recusado(um_time):
    """🚨 A→B→A não estoura ao gravar: só aparece quando uma conversa real
    entra no laço e nunca chega a um atendente."""
    outro = operacao.criar_time(f"{PREFIXO}beta")
    try:
        operacao.atualizar_time(outro["id"], outro["nome"], None, um_time["id"])
        with pytest.raises(operacao.DadoInvalido):
            operacao.atualizar_time(um_time["id"], um_time["nome"], None, outro["id"])
    finally:
        banco.executar("UPDATE time SET time_transbordo_id = NULL WHERE id = %s",
                       (outro["id"],))
        banco.executar("DELETE FROM time WHERE id = %s", (outro["id"],))


def test_nao_desativa_time_que_e_destino_de_transbordo(um_time):
    outro = operacao.criar_time(f"{PREFIXO}gama", None, um_time["id"])
    try:
        with pytest.raises(operacao.EmUso):
            operacao.atualizar_time(um_time["id"], um_time["nome"], None, None,
                                    ativo=False)
    finally:
        banco.executar("UPDATE time SET time_transbordo_id = NULL WHERE id = %s",
                       (outro["id"],))
        banco.executar("DELETE FROM time WHERE id = %s", (outro["id"],))


def test_alerta_aponta_time_sem_membro(um_time):
    achados = operacao.alertas()
    sem_membro = [a for a in achados if a["titulo"] == "Time sem nenhum atendente"]
    assert sem_membro, "o alerta de time vazio sumiu"
    assert um_time["nome"] in sem_membro[0]["detalhe"]


# -------------------------------------------------------------- atendentes

def test_atendente_nasce_sem_senha_e_nao_entra(um_atendente):
    """🚨 Conta criada e esquecida não é porta aberta: é porta que não existe."""
    from movizap import auth

    assert um_atendente["tem_senha"] is False
    assert auth.validar_login(um_atendente["login"], "qualquer-coisa") is None


def test_senha_definida_passa_a_entrar(um_atendente):
    from movizap import auth

    operacao.definir_senha(um_atendente["id"], "senha-longa-de-teste")
    assert operacao.atendente(um_atendente["id"])["tem_senha"] is True
    usuario = auth.validar_login(um_atendente["login"], "senha-longa-de-teste")
    assert usuario is not None
    assert usuario["owner"] is False
    # perfil padrão é o menor privilégio, não admin
    assert usuario["permissoes"] == ["atendimento"]


def test_senha_curta_e_recusada(um_atendente):
    with pytest.raises(operacao.DadoInvalido):
        operacao.definir_senha(um_atendente["id"], "curta")


def test_login_repetido_e_recusado(um_atendente):
    with pytest.raises(operacao.DadoInvalido):
        operacao.criar_atendente("Outro", um_atendente["login"].upper())


def test_perfil_invalido_e_recusado():
    with pytest.raises(operacao.DadoInvalido):
        operacao.criar_atendente(f"{PREFIXO}X", f"{PREFIXO}x", perfil="chefe")


def test_ninguem_inativa_a_propria_conta(um_atendente):
    with pytest.raises(operacao.EmUso):
        operacao.definir_ativo(um_atendente["id"], False,
                               quem_edita=um_atendente["login"])


# ------------------------------------------- membros pela tela de Times (24/09)

def test_membros_do_time_sao_substituidos_inteiros(um_atendente, um_time):
    """🔵 24/09: a CAD_2.2 grava quem está no time."""
    cheio = operacao.definir_membros(um_time["id"], [um_atendente["id"]])
    assert [m["id"] for m in cheio["membros"]] == [um_atendente["id"]]
    vazio = operacao.definir_membros(um_time["id"], [])
    assert vazio["membros"] == []


def test_membros_nao_apaga_o_vinculo_de_quem_esta_inativo(um_atendente, um_time):
    """⚠️ A tela só lista ativos. Salvar o time não pode derrubar o vínculo
    de um inativo só porque ele não apareceu na lista."""
    operacao.definir_membros(um_time["id"], [um_atendente["id"]])
    banco.executar("UPDATE atendente SET ativo = false WHERE id = %s",
                   (um_atendente["id"],))
    operacao.definir_membros(um_time["id"], [])
    assert banco.um(
        "SELECT 1 AS ok FROM atendente_time WHERE atendente_id = %s AND time_id = %s",
        (um_atendente["id"], um_time["id"]))


# ------------------------------------------- owner invisível para o admin (25/09)

def _o_owner():
    dono = banco.um("SELECT id FROM atendente WHERE owner AND ativo LIMIT 1")
    if not dono:
        pytest.skip("nenhum owner ativo na base")
    return dono["id"]


def test_admin_nao_ve_o_owner_na_lista():
    """🔵 *"owner não deve aparecer para admin, então admin nunca inativará
    owner"*."""
    dono = _o_owner()
    assert dono in [a["id"] for a in operacao.listar_atendentes(ver_owner=True)]
    assert dono not in [a["id"] for a in operacao.listar_atendentes(ver_owner=False)]


def test_admin_nao_ve_o_owner_entre_os_membros(um_time):
    dono = _o_owner()
    banco.executar("INSERT INTO atendente_time (atendente_id, time_id) VALUES (%s, %s)",
                   (dono, um_time["id"]))
    try:
        visto = operacao.time(um_time["id"], ocultar_owner=True)
        assert dono not in [m["id"] for m in visto["membros"]]
        assert dono in [m["id"] for m in operacao.time(um_time["id"])["membros"]]
    finally:
        banco.executar("DELETE FROM atendente_time WHERE atendente_id = %s AND time_id = %s",
                       (dono, um_time["id"]))


def test_salvar_o_time_sem_ver_o_owner_nao_o_tira(um_atendente, um_time):
    """🚨 O admin nunca manda o owner na lista, porque não o vê. Sem
    `preservar_owner`, salvar o time Geral o tiraria de lá em silêncio."""
    dono = _o_owner()
    banco.executar("INSERT INTO atendente_time (atendente_id, time_id) VALUES (%s, %s)",
                   (dono, um_time["id"]))
    try:
        operacao.definir_membros(um_time["id"], [um_atendente["id"]], preservar_owner=True)
        assert banco.um(
            "SELECT 1 AS ok FROM atendente_time WHERE atendente_id = %s AND time_id = %s",
            (dono, um_time["id"]))
    finally:
        banco.executar("DELETE FROM atendente_time WHERE atendente_id = %s AND time_id = %s",
                       (dono, um_time["id"]))


def test_estados_do_cadastro_e_da_minha_conta_sao_os_mesmos():
    """🚨 24/09: a Minha conta oferecia `offline` e o cadastro não o aceitava --
    quem se marcasse offline não podia mais ser editado na CAD_2.1."""
    from movizap.main import ESTADOS_ATENDENTE
    assert set(operacao.ESTADOS) == set(ESTADOS_ATENDENTE)


def test_membros_recusa_atendente_inexistente(um_time):
    with pytest.raises(operacao.DadoInvalido):
        operacao.definir_membros(um_time["id"], [-1])


# ------------------------------------------------ travas do admin (24/09)

class TestTravasDoAdmin:
    """🚨 O admin entra em Atendentes, e a permissão da tela não basta: a
    conta do owner passa de mão trocando o e-mail dela, então editar a linha
    do owner é virar owner."""

    ADMIN = {"login": "zz_admin", "owner": False}
    OWNER = {"login": "zz_owner", "owner": True}

    @staticmethod
    def _id_do_owner():
        return banco.um("SELECT id FROM atendente WHERE owner LIMIT 1")["id"]

    def test_admin_nao_mexe_no_owner(self):
        from fastapi import HTTPException
        from movizap.main import _so_owner_mexe_no_owner
        with pytest.raises(HTTPException) as e:
            _so_owner_mexe_no_owner(self.ADMIN, self._id_do_owner())
        assert e.value.status_code == 403

    def test_admin_mexe_em_quem_nao_e_owner(self, um_atendente):
        from movizap.main import _so_owner_mexe_no_owner
        _so_owner_mexe_no_owner(self.ADMIN, um_atendente["id"])

    def test_owner_mexe_nele_mesmo(self):
        from movizap.main import _so_owner_mexe_no_owner
        _so_owner_mexe_no_owner(self.OWNER, self._id_do_owner())

    def test_admin_nao_cria_admin(self):
        from fastapi import HTTPException
        from movizap.main import _so_owner_da_admin
        with pytest.raises(HTTPException):
            _so_owner_da_admin(self.ADMIN, "admin")

    def test_admin_nao_promove_nem_rebaixa(self, um_atendente):
        from fastapi import HTTPException
        from movizap.main import _so_owner_da_admin
        with pytest.raises(HTTPException):
            _so_owner_da_admin(self.ADMIN, "admin", um_atendente["id"])
        banco.executar("UPDATE atendente SET perfil = 'admin' WHERE id = %s",
                       (um_atendente["id"],))
        with pytest.raises(HTTPException):
            _so_owner_da_admin(self.ADMIN, "atendimento", um_atendente["id"])
        # Editar um admin sem mexer no perfil continua livre.
        _so_owner_da_admin(self.ADMIN, "admin", um_atendente["id"])

    def test_owner_da_e_tira_admin(self, um_atendente):
        from movizap.main import _so_owner_da_admin
        _so_owner_da_admin(self.OWNER, "admin")
        _so_owner_da_admin(self.OWNER, "admin", um_atendente["id"])

    def test_rota_antiga_de_times_do_atendente_saiu(self):
        """Uma porta só para gravar o vínculo: a da CAD_2.2."""
        from fastapi.routing import APIRoute
        from movizap.main import app
        caminhos = {(r.path, m) for r in app.routes if isinstance(r, APIRoute)
                    for m in r.methods}
        assert ("/api/atendentes/{atendente_id}/times", "PUT") not in caminhos
        assert ("/api/times/{time_id}/membros", "PUT") in caminhos


# ----------------------------------------------------------------- jornada

def test_pausa_do_almoco_sao_duas_faixas_no_mesmo_dia(um_atendente):
    """🚨 Não existe campo "pausa": o almoço é o buraco entre duas faixas."""
    atualizado = operacao.definir_jornada(um_atendente["id"], [
        {"dia_semana": 1, "inicio": "08:00", "fim": "12:00"},
        {"dia_semana": 1, "inicio": "13:00", "fim": "18:00"},
    ])
    segunda = [f for f in atualizado["jornada"] if f["dia_semana"] == 1]
    assert len(segunda) == 2


def test_faixas_sobrepostas_sao_recusadas(um_atendente):
    with pytest.raises(operacao.DadoInvalido):
        operacao.definir_jornada(um_atendente["id"], [
            {"dia_semana": 2, "inicio": "08:00", "fim": "12:00"},
            {"dia_semana": 2, "inicio": "10:00", "fim": "14:00"},
        ])


def test_fim_antes_do_inicio_e_recusado(um_atendente):
    with pytest.raises(operacao.DadoInvalido):
        operacao.definir_jornada(um_atendente["id"], [
            {"dia_semana": 3, "inicio": "18:00", "fim": "09:00"},
        ])


def test_em_jornada_responde_pelo_horario(um_atendente):
    # 2026-08-10 é uma segunda-feira.
    operacao.definir_jornada(um_atendente["id"], [
        {"dia_semana": 1, "inicio": "08:00", "fim": "12:00"},
        {"dia_semana": 1, "inicio": "13:00", "fim": "18:00"},
    ])
    assert operacao.em_jornada(um_atendente["id"], datetime(2026, 8, 10, 9, 0))
    # 12:30 é o almoço: está entre as duas faixas, logo FORA
    assert not operacao.em_jornada(um_atendente["id"], datetime(2026, 8, 10, 12, 30))
    assert operacao.em_jornada(um_atendente["id"], datetime(2026, 8, 10, 17, 59))
    # domingo não tem faixa nenhuma
    assert not operacao.em_jornada(um_atendente["id"], datetime(2026, 8, 9, 9, 0))


def test_sem_jornada_conta_como_fora(um_atendente):
    """⚠️ Jornada vazia é "ninguém disse quando", e supor 24h é o jeito de
    criar a transferência fantasma que a regra existe para evitar."""
    assert not operacao.em_jornada(um_atendente["id"], datetime(2026, 8, 10, 9, 0))


# ---------------------------------------------------------- classificações

def test_classificacao_repetida_e_recusada():
    c = operacao.criar_classificacao(f"{PREFIXO}motivo")
    try:
        with pytest.raises(operacao.DadoInvalido):
            operacao.criar_classificacao(f"{PREFIXO}motivo")
    finally:
        banco.executar("DELETE FROM classificacao WHERE id = %s", (c["id"],))


def test_producao_pode_ficar_sem_classificacao_nenhuma():
    """🚨 O oposto do que este teste exigia até 11/08.

    Ele cobrava >= 2 classificações ativas em produção, porque encerrar
    dependia delas. Encerrar deixou de depender: a lista de 9 era invenção
    minha, ninguém a pediu, e nunca houve conversa classificada.

    Agora o que se prova é que a ausência NÃO quebra nada -- porque foi
    exatamente isso que quebrou em produção quando as 9 foram apagadas."""
    ativas = operacao.listar_classificacoes()
    assert isinstance(ativas, list), "listar não pode estourar sem classificação"
