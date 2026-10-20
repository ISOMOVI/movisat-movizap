"""Distribuição automática da fila — 24/09 (ver `movizap/distribuicao.py`).

🚨 NENHUM TESTE LIGA A DISTRIBUIÇÃO NO BANCO. A suíte roda em produção e o laço
do serviço lê a mesma `config`: ligá-la aqui mandaria conversas REAIS para
alguém. A passada é chamada com `forcar=True`, `cfg=` montada no teste e
`somente=` as conversas do teste.

🚨 Escreve em `atendente`, `conversa`, `mensagem`, `transferencia`. Logins
`zz_teste_dist_`, telefones de DDD inexistente; tudo apagado no fim.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas, distribuicao, operacao  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_dist_"
FONE = "+559995557%"
GRUPO = "zz-dist-%@g.us"


def limpar():
    ids = "(SELECT id FROM conversa WHERE telefone_e164 LIKE %s OR grupo_jid LIKE %s)"
    for tabela in ("mensagem", "transferencia", "conversa_participante"):
        banco.executar(f"DELETE FROM {tabela} WHERE conversa_id IN {ids}", (FONE, GRUPO))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 LIKE %s OR grupo_jid LIKE %s",
                   (FONE, GRUPO))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


_seq = [0]


def pessoa(estado="disponivel", painel_ha_min=0):
    """🚨 19/10: O CARIMBO DO PAINEL ENTROU NO FIXTURE, e sem ele cinco
    testes deste arquivo reprovariam -- não por defeito, por omissão do
    cenário. Desde 19/10 a distribuição automática só entrega a quem está com
    o painel aberto (`presenca.painel_aberto_agora`), e `painel_visto_em NULL`
    conta como fechado. Atendente criado agora nasce com NULL, então "pessoa
    disponível" sem carimbo não é mais uma pessoa que recebe.

    `painel_ha_min` existe para o caso contrário: quem fechou o painel.
    """
    _seq[0] += 1
    a = operacao.criar_atendente(f"Zz Dist {_seq[0]}", f"{LOGIN}{_seq[0]}",
                                 f"{LOGIN}{_seq[0]}@teste.invalid")
    banco.executar(
        """UPDATE atendente
              SET estado = %s,
                  painel_visto_em = now() - make_interval(mins => %s)
            WHERE id = %s""", (estado, painel_ha_min, a["id"]))
    return a["id"]


def conversa(tipo="direta", time_id=None):
    _seq[0] += 1
    canal = banco.um("SELECT id FROM canal WHERE tipo = 'atendimento' AND ativo LIMIT 1")
    if not canal:
        pytest.skip("nenhum canal de atendimento ativo")
    # Grupo não tem telefone: a identidade é o jid (`ck_conversa_identidade`).
    fone = None if tipo == "grupo" else f"+55999555700{_seq[0]:02d}"
    jid = f"zz-dist-{_seq[0]}@g.us" if tipo == "grupo" else None
    return banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, grupo_jid, estado, tipo, time_id)
           VALUES (%s, %s, %s, 'nova', %s, %s) RETURNING id""",
        (canal["id"], fone, jid, tipo, time_id))["id"]


def mensagem(cid, ha_min, direcao="entrada"):
    _seq[0] += 1
    banco.executar(
        """INSERT INTO mensagem (conversa_id, id_externo, direcao, autor, tipo, conteudo, criada_em)
           VALUES (%s, %s, %s, %s, 'texto', 'oi', now() - make_interval(mins => %s))""",
        (cid, f"zz-dist-{_seq[0]}", direcao,
         "cliente" if direcao == "entrada" else "atendente", ha_min))


def cfg(primeiro, reserva=None, ligada_ha_min=60, minutos=10):
    marco = datetime.now(timezone.utc) - timedelta(minutes=ligada_ha_min)
    return {"ligada": True, "ligada_em": marco.isoformat(), "primeiro_id": primeiro,
            "reserva_id": reserva, "minutos": minutos}


def dono(cid):
    return banco.um("SELECT atendente_id FROM conversa WHERE id = %s", (cid,))["atendente_id"]


def passar(c, ids):
    return distribuicao.distribuir(forcar=True, somente=ids, cfg=c)


def test_parada_ha_10_min_vai_para_o_primeiro_com_nota_do_sistema():
    a = pessoa()
    cid = conversa()
    mensagem(cid, 15)
    r = passar(cfg(a), [cid])
    assert r["distribuidas"] == [cid] and dono(cid) == a
    nota = banco.um("SELECT autor, conteudo FROM mensagem WHERE conversa_id = %s "
                    "AND tipo = 'nota'", (cid,))
    assert nota["autor"] == "sistema" and "10 min" in nota["conteudo"]
    assert banco.um("SELECT motivo FROM transferencia WHERE conversa_id = %s",
                    (cid,))["motivo"] == "inatividade"


def test_antes_dos_10_min_nao_vai():
    a = pessoa()
    cid = conversa()
    mensagem(cid, 5)
    assert passar(cfg(a), [cid])["distribuidas"] == []


def test_conta_da_primeira_mensagem_que_espera_nao_da_ultima():
    a = pessoa()
    cid = conversa()
    mensagem(cid, 12)
    mensagem(cid, 2)
    assert passar(cfg(a), [cid])["distribuidas"] == [cid]


def test_resposta_nossa_zera_a_espera():
    a = pessoa()
    cid = conversa()
    mensagem(cid, 30)
    mensagem(cid, 20, direcao="saida")
    mensagem(cid, 4)
    assert passar(cfg(a), [cid])["distribuidas"] == []


def test_1a_o_que_ja_estava_parado_ao_ligar_nao_entra():
    a = pessoa()
    cid = conversa()
    mensagem(cid, 90)          # antes do marco (ligada há 60 min)
    assert passar(cfg(a), [cid])["distribuidas"] == []


def test_3_conversa_com_time_nao_vai():
    a = pessoa()
    time = banco.um("SELECT id FROM time WHERE ativo LIMIT 1")
    if not time:
        pytest.skip("nenhum time ativo")
    cid = conversa(time_id=time["id"])
    mensagem(cid, 15)
    assert passar(cfg(a), [cid])["distribuidas"] == []


def test_grupo_nao_vai():
    a = pessoa()
    cid = conversa(tipo="grupo")
    mensagem(cid, 15)
    assert passar(cfg(a), [cid])["distribuidas"] == []


def test_4a_primeiro_offline_vai_para_a_reserva():
    a = pessoa("offline")
    b = pessoa()
    cid = conversa()
    mensagem(cid, 15)
    passar(cfg(a, b), [cid])
    assert dono(cid) == b


def test_4a_as_duas_offline_fica_na_fila():
    a = pessoa("offline")
    b = pessoa("offline")
    cid = conversa()
    mensagem(cid, 15)
    r = passar(cfg(a, b), [cid])
    assert r["paradas_sem_destino"] == 1 and dono(cid) is None


def test_quem_assumiu_no_mesmo_segundo_ganha():
    """A trava da corrida: o UPDATE só passa se ainda não houver dono."""
    a = pessoa()
    quem_assumiu = pessoa()
    cid = conversa()
    banco.executar("UPDATE conversa SET atendente_id = %s WHERE id = %s", (quem_assumiu, cid))
    r = conversas.transferir(cid, None, a, "inatividade", so_se_sem_dono=True)
    assert r["ok"] is False and dono(cid) == quem_assumiu


# ------------------------------------------ a trava de fila do painel (19/10)
#
# 🔵 Decisão dele: *"dentro da jornada cadastrada, impossível ficar fora do
# expediente"* -- e, respondendo à consequência, que **quem está com o painel
# fechado para de receber distribuição automática**, continuando a aceitar
# transferência à mão.
#
# 🚨 O que estes testes defendem é a SEPARAÇÃO. Sem ela, o `offline` de 60 min
# era o que tirava alguém da fila -- e, como ele deixou de existir dentro da
# jornada, a fila entregaria conversa das 08h às 18h a quem foi embora às 15h.

def test_painel_fechado_sai_da_fila_e_a_conversa_vai_para_a_reserva():
    a = pessoa(painel_ha_min=90)       # foi embora e fechou o painel
    b = pessoa()                       # painel aberto agora
    cid = conversa()
    mensagem(cid, 15)
    passar(cfg(a, b), [cid])
    assert dono(cid) == b


def test_as_duas_com_painel_fechado_deixa_na_fila():
    a = pessoa(painel_ha_min=90)
    b = pessoa(painel_ha_min=90)
    cid = conversa()
    mensagem(cid, 15)
    r = passar(cfg(a, b), [cid])
    assert dono(cid) is None
    assert r["paradas_sem_destino"] == 1


def test_quem_nunca_abriu_o_painel_nao_recebe():
    """`painel_visto_em IS NULL` conta como fechado, e isto é decisão
    declarada: a coluna nasceu em 19/10. O contrário entregaria conversa a quem
    nunca apareceu."""
    a = pessoa()
    banco.executar("UPDATE atendente SET painel_visto_em = NULL WHERE id = %s", (a,))
    b = pessoa()
    cid = conversa()
    mensagem(cid, 15)
    passar(cfg(a, b), [cid])
    assert dono(cid) == b


def test_a_tela_diz_painel_fechado_e_nao_offline():
    """🚨 `M12`: "parada porque as duas estão offline" e "parada porque
    ninguém está com o painel aberto" não podem sair com a mesma frase.

    🚨 E A LIÇÃO DE COMO ESTE TESTE NASCEU: a primeira versão chamou
    `distribuicao.definir_config`, que grava na `config` DE PRODUÇÃO -- a fila
    real ficou desligada, apontando para estes atendentes de teste, até eu
    restaurar do dump das 02:40. O cabeçalho deste arquivo avisa em maiúsculas,
    e o aviso estava certo. `situacao(cfg=...)` é a porta de teste que faltava.
    """
    a = pessoa(painel_ha_min=90)
    b = pessoa(painel_ha_min=90)
    sit = distribuicao.situacao(cfg=cfg(a, b))
    assert sit["parada"] is True
    assert sit["parada_motivo"] == "painel fechado"
    assert sit["primeiro_disponivel"] is False


def test_a_tela_diz_offline_quando_o_motivo_e_offline():
    a = pessoa("offline")
    b = pessoa("offline")
    sit = distribuicao.situacao(cfg=cfg(a, b))
    assert sit["parada"] is True
    assert "offline" in sit["parada_motivo"].lower()


def test_nenhum_teste_deste_arquivo_escreve_na_config_real():
    """🚨 A trava que faltava, escrita depois do estrago: se algum teste daqui
    voltar a chamar `definir_config`, este teste acusa -- comparando o retrato
    da configuração real antes e depois de uma passada completa."""
    chaves = ("distribuicao_ligada", "distribuicao_primeiro",
              "distribuicao_reserva", "distribuicao_minutos",
              "distribuicao_ligada_em")
    antes = {k: banco.um("SELECT valor FROM config WHERE chave = %s", (k,)) for k in chaves}
    a = pessoa()
    cid = conversa()
    mensagem(cid, 15)
    passar(cfg(a), [cid])
    distribuicao.situacao(cfg=cfg(a))
    depois = {k: banco.um("SELECT valor FROM config WHERE chave = %s", (k,)) for k in chaves}
    assert antes == depois, "um teste escreveu na configuração real da distribuição"


def test_painel_fechado_nao_impede_transferencia_a_mao():
    """A trava é **só** da fila. Transferência à mão passa por
    `conversas.transferir`, que olha offline e afastamento -- nunca o painel."""
    a = pessoa(painel_ha_min=600)
    cid = conversa()
    r = conversas.transferir(cid, None, a, "manual")
    assert r["ok"] is True and dono(cid) == a


def test_nao_liga_sem_escolher_quem_recebe():
    with pytest.raises(operacao.DadoInvalido):
        distribuicao.definir_config(True, None, None, 10)


def test_reserva_nao_pode_ser_o_primeiro():
    a = pessoa()
    with pytest.raises(operacao.DadoInvalido):
        distribuicao.definir_config(False, a, a, 10)
