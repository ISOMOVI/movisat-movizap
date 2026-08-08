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


def test_ninguem_desativa_a_propria_conta(um_atendente):
    with pytest.raises(operacao.EmUso):
        operacao.atualizar_atendente(
            um_atendente["id"], um_atendente["nome"], um_atendente["login"],
            None, "atendimento", "disponivel", None, ativo=False,
            quem_edita=um_atendente["login"])


def test_times_do_atendente_sao_substituidos_inteiros(um_atendente, um_time):
    atualizado = operacao.definir_times(um_atendente["id"], [um_time["id"]])
    assert [t["id"] for t in atualizado["times"]] == [um_time["id"]]
    vazio = operacao.definir_times(um_atendente["id"], [])
    assert vazio["times"] == []


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


def test_producao_tem_classificacao_ativa_suficiente():
    """A regra "não desative a última" só se prova com uma só ativa, e não dá
    para deixar a base assim. Aqui se confere a premissa; a regra em si tem
    teste unitário no ramo de erro do módulo."""
    ativas = operacao.listar_classificacoes()
    assert len(ativas) >= 2
    assert any(c["exige_comentario"] for c in ativas), \
        "'Outro' sem comentário obrigatório vira o vale-tudo do analytics"
