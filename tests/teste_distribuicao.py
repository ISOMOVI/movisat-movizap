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


def pessoa(estado="disponivel", painel_ha_min=0, logou_ha_dias=0):
    """🚨 13/11: O CARIMBO DO LOGIN ENTROU NO FIXTURE, no lugar do painel.

    Ate 13/11 a trava da fila era "o painel esta aberto nos ultimos 15 min"
    (`painel_aberto_agora`). 🔵 Decisao dele: *"logado e logado ... o foco e
    evitar enviar conversa para operadora que nao logou hoje"*, porque o
    carimbo do painel prova ABA ABERTA, nao pessoa -- medido no dia: o carimbo
    de quem estava afastada era de um minuto antes, com a maquina ligada.

    `logou_ha_dias=None` e "nunca logou" (coluna nula, o estado de quem nao
    apareceu desde a migracao 109); `1` e "logou ontem", que tambem nao vale --
    o token morre na virada do dia.
    `painel_ha_min` fica porque `painel_aberto_agora` continua existindo e
    continua sendo testada: ela so deixou de mandar na fila.
    """
    _seq[0] += 1
    a = operacao.criar_atendente(f"Zz Dist {_seq[0]}", f"{LOGIN}{_seq[0]}",
                                 f"{LOGIN}{_seq[0]}@teste.invalid")
    banco.executar(
        """UPDATE atendente
              SET estado = %s,
                  painel_visto_em = now() - make_interval(mins => %s),
                  logou_em = CASE WHEN %s::int IS NULL THEN NULL
                                  ELSE now() - make_interval(days => %s::int) END
            WHERE id = %s""",
        (estado, painel_ha_min, logou_ha_dias, logou_ha_dias, a["id"]))
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


def cfg(primeiro, reserva=None, ligada_ha_min=60, minutos=10, *extras):
    """🔵 13/11: a cadeia. `cfg(a, b, 60, 10, c)` poe um terceiro na fila.

    ⚠️ `primeiro_id` e `reserva_id` continuam aqui porque a tela de hoje ainda
    os usa -- e porque e por eles que `config()` monta a ordem quando a lista
    esta vazia, em base vinda de antes da 109.
    """
    marco = datetime.now(timezone.utc) - timedelta(minutes=ligada_ha_min)
    ordem = [x for x in (primeiro, reserva, *extras) if x]
    return {"ligada": True, "ligada_em": marco.isoformat(), "primeiro_id": primeiro,
            "reserva_id": reserva, "ordem": ordem, "minutos": minutos}


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

def test_quem_nao_logou_hoje_sai_da_fila_e_a_conversa_vai_para_a_reserva():
    """🔵 13/11: *"se nao logar, as novas conversas precisam seguir para
    Erika"*. Faltou hoje -- nao logou -- e a fila passa por cima."""
    a = pessoa(logou_ha_dias=1)        # logou ontem, nao hoje
    b = pessoa()                       # logou hoje
    cid = conversa()
    mensagem(cid, 15)
    passar(cfg(a, b), [cid])
    assert dono(cid) == b


def test_as_duas_sem_logar_deixa_na_fila():
    a = pessoa(logou_ha_dias=1)
    b = pessoa(logou_ha_dias=1)
    cid = conversa()
    mensagem(cid, 15)
    r = passar(cfg(a, b), [cid])
    assert dono(cid) is None
    assert r["paradas_sem_destino"] == 1


def test_quem_nunca_logou_nao_recebe():
    """`logou_em IS NULL` conta como NAO LOGOU, e isto e decisao declarada: a
    coluna nasceu na migracao 109. O contrario entregaria conversa a quem nunca
    apareceu -- que e exatamente o que ele viu acontecer."""
    a = pessoa(logou_ha_dias=None)
    b = pessoa()
    cid = conversa()
    mensagem(cid, 15)
    passar(cfg(a, b), [cid])
    assert dono(cid) == b


def test_a_CADEIA_passa_do_segundo_para_o_TERCEIRO():
    """🔵 13/11, DELE: *"se nao logar, as novas conversas precisam seguir para
    Erika, se a mesma logar e se nao, para a Claudia"*.

    🚨 Ate aqui a fila tinha DOIS lugares (`primeiro_id`, `reserva_id`) e
    simplesmente parava quando os dois nao podiam. O terceiro nome nao cabia no
    modelo -- por isso a ordem virou lista na migracao 109.
    """
    a = pessoa(logou_ha_dias=1)
    b = pessoa(logou_ha_dias=1)
    c = pessoa()
    cid = conversa()
    mensagem(cid, 15)
    passar(cfg(a, b, 60, 10, c), [cid])
    assert dono(cid) == c


def test_painel_fechado_NAO_tira_mais_ninguem_da_fila():
    """⚠️ O QUE DEIXOU DE VALER, dito em teste: aba fechada nao barra mais.
    Quem esta logado hoje e disponivel recebe, mesmo com o painel fechado ha
    90 min -- porque a pergunta passou a ser sobre a PESSOA ter entrado no dia,
    nao sobre a aba estar viva neste minuto."""
    a = pessoa(painel_ha_min=90)
    b = pessoa()
    cid = conversa()
    mensagem(cid, 15)
    passar(cfg(a, b), [cid])
    assert dono(cid) == a


def test_a_tela_diz_que_nao_logou_e_nao_que_esta_offline():
    """🚨 `M12`: "parada porque as duas estão offline" e "parada porque
    ninguém logou hoje" não podem sair com a mesma frase.

    🚨 E A LIÇÃO DE COMO ESTE TESTE NASCEU: a primeira versão chamou
    `distribuicao.definir_config`, que grava na `config` DE PRODUÇÃO -- a fila
    real ficou desligada, apontando para estes atendentes de teste, até eu
    restaurar do dump das 02:40. O cabeçalho deste arquivo avisa em maiúsculas,
    e o aviso estava certo. `situacao(cfg=...)` é a porta de teste que faltava.
    """
    a = pessoa(logou_ha_dias=1)
    b = pessoa(logou_ha_dias=1)
    sit = distribuicao.situacao(cfg=cfg(a, b))
    assert sit["parada"] is True
    assert sit["parada_motivo"] == "não logou hoje"
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


def test_nao_ter_logado_nao_impede_transferencia_a_mao():
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
