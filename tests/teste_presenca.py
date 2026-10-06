"""Presença — status por tempo, offline não recebe, afastamento, fim de expediente.

🔵 Pedidos dele em 24/09 (ver `movizap/presenca.py`).

🚨 NENHUM TESTE LIGA A REGRA NO BANCO. A suíte roda em produção e o laço do
serviço lê a mesma `config`: ligar a regra aqui mandaria atendentes REAIS para
offline no minuto seguinte. A régua é passada com `forcar=True` e `somente=`
as linhas do teste, e a config é trocada só dentro do processo (monkeypatch).

🚨 Escreve em `atendente`, `conversa`, `transferencia` e `mensagem`. Logins
`zz_teste_pres_`, telefones de DDD inexistente; tudo apagado no fim.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import automacao, banco, conversas, evolution, operacao, presenca  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_pres_"
FONE = "+559995556%"


def limpar():
    ids = "(SELECT id FROM conversa WHERE telefone_e164 LIKE %s)"
    banco.executar(f"DELETE FROM mensagem WHERE conversa_id IN {ids}", (FONE,))
    banco.executar(f"DELETE FROM transferencia WHERE conversa_id IN {ids}", (FONE,))
    banco.executar(f"DELETE FROM conversa_participante WHERE conversa_id IN {ids}", (FONE,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 LIKE %s", (FONE,))
    banco.executar(
        "DELETE FROM atendente_jornada WHERE atendente_id IN "
        "(SELECT id FROM atendente WHERE login LIKE %s)", (LOGIN + "%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture(autouse=True)
def sem_enviar(monkeypatch):
    """🚨 Nenhum teste manda mensagem de verdade."""
    enviadas = []

    def falso(instancia, numero, texto, citando=None, mencionados=None):
        enviadas.append({"numero": numero, "texto": texto})
        return {"id_externo": f"zz-pres-{len(enviadas)}", "status": "PENDING", "bruto": {}}

    monkeypatch.setattr(evolution, "enviar_texto", falso)
    yield enviadas


def config_falsa(monkeypatch, **extra):
    cfg = {"regra_ligada": True, "minutos_ausente": 15, "minutos_offline": 60,
           "mensagem_ligada": False, "mensagem_texto": ""}
    cfg.update(extra)
    monkeypatch.setattr(presenca, "config", lambda: dict(cfg))
    return cfg


_seq = [0]


def novo_atendente(parado_ha_min=None, estado="disponivel", automatico=False):
    _seq[0] += 1
    a = operacao.criar_atendente(f"Zz Pres {_seq[0]}", f"{LOGIN}{_seq[0]}",
                                 f"{LOGIN}{_seq[0]}@teste.invalid")
    banco.executar(
        """UPDATE atendente SET estado = %s, estado_automatico = %s,
                  ultima_acao_em = CASE WHEN %s::int IS NULL THEN NULL
                                        ELSE now() - make_interval(mins => %s::int) END
            WHERE id = %s""",
        (estado, automatico, parado_ha_min, parado_ha_min, a["id"]))
    return a["id"]


def estado_de(aid):
    return banco.um("SELECT estado, estado_automatico, afastamento_motivo "
                    "FROM atendente WHERE id = %s", (aid,))


def nova_conversa(dono=None, n=[0]):
    n[0] += 1
    canal = banco.um("SELECT id FROM canal WHERE tipo = 'atendimento' AND ativo LIMIT 1")
    if not canal:
        pytest.skip("nenhum canal de atendimento ativo")
    return banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (canal["id"], f"+55999555600{n[0]:02d}", "humano" if dono else "nova", dono))["id"]


# ------------------------------------------------------------ a regra de tempo

class TestRegraDeTempo:
    def test_15_min_parado_vira_ausente_e_1h_vira_offline(self, monkeypatch):
        config_falsa(monkeypatch)
        ativo = novo_atendente(parado_ha_min=5)
        parado = novo_atendente(parado_ha_min=20)
        sumido = novo_atendente(parado_ha_min=120)
        r = presenca.aplicar_regra(forcar=True, somente=[ativo, parado, sumido])
        assert estado_de(ativo)["estado"] == "disponivel"
        assert estado_de(parado)["estado"] == "ausente"
        assert estado_de(sumido)["estado"] == "offline"
        assert set(r["ausentes"]) == {parado} and set(r["offline"]) == {sumido}
        assert estado_de(parado)["estado_automatico"] is True

    def test_regra_desligada_nao_mexe_em_ninguem(self, monkeypatch):
        config_falsa(monkeypatch, regra_ligada=False)
        sumido = novo_atendente(parado_ha_min=120)
        presenca.aplicar_regra(somente=[sumido])
        assert estado_de(sumido)["estado"] == "disponivel"

    def test_quem_nunca_agiu_nao_cai(self, monkeypatch):
        """NULL = sem ponto de partida. Não é 'parado desde sempre'."""
        config_falsa(monkeypatch)
        novo = novo_atendente(parado_ha_min=None)
        presenca.aplicar_regra(forcar=True, somente=[novo])
        assert estado_de(novo)["estado"] == "disponivel"

    def test_acao_desfaz_o_que_a_regra_fez(self):
        aid = novo_atendente(parado_ha_min=30, estado="ausente", automatico=True)
        presenca.registrar_acao(aid)
        assert estado_de(aid)["estado"] == "disponivel"

    def test_acao_nao_desfaz_o_que_a_pessoa_escolheu(self):
        aid = novo_atendente(parado_ha_min=30, estado="ausente", automatico=False)
        presenca.registrar_acao(aid)
        assert estado_de(aid)["estado"] == "ausente"

    def test_escolher_disponivel_conta_como_acao(self, monkeypatch):
        config_falsa(monkeypatch)
        aid = novo_atendente(parado_ha_min=300, estado="offline", automatico=True)
        presenca.definir_estado_manual(aid, "disponivel")
        presenca.aplicar_regra(forcar=True, somente=[aid])
        assert estado_de(aid)["estado"] == "disponivel"

    def test_offline_tem_de_ser_maior_que_ausente(self):
        with pytest.raises(operacao.DadoInvalido):
            presenca.definir_config(False, 60, 15, False, "")

    def test_mensagem_ligada_sem_texto_e_recusada(self):
        with pytest.raises(operacao.DadoInvalido):
            presenca.definir_config(False, 15, 60, True, "   ")


def test_sempre_online_e_so_do_owner():
    import psycopg
    aid = novo_atendente()
    with pytest.raises(psycopg.errors.CheckViolation):
        presenca.definir_sempre_online(aid, True)


# ------------------------------------------------------------ offline não recebe

class TestOfflineNaoRecebe:
    def test_transferir_para_offline_e_recusado_com_a_frase_dele(self):
        dono = novo_atendente()
        destino = novo_atendente(estado="offline")
        cid = nova_conversa(dono)
        r = conversas.transferir(cid, None, destino, "manual", de_atendente_id=dono)
        assert r == {"ok": False, "motivo": presenca.MENSAGEM_OFFLINE}
        assert presenca.MENSAGEM_OFFLINE == (
            "O atendente escolhido está offline e não poderá continuar o atendimento.")

    def test_transferir_para_disponivel_passa(self):
        dono = novo_atendente()
        destino = novo_atendente()
        cid = nova_conversa(dono)
        assert conversas.transferir(cid, None, destino, "manual", de_atendente_id=dono)["ok"]


# ------------------------------------------------------------ afastamento

def dias(aid, n):
    """Hoje + n no fuso da pessoa -- a mesma régua que `presenca` usa."""
    return presenca._hoje_de(aid) + timedelta(days=n)


class TestAfastamento:
    def test_com_conversa_aberta_exige_destino(self):
        aid = novo_atendente()
        nova_conversa(aid)
        with pytest.raises(operacao.DadoInvalido):
            presenca.afastar(aid, "Férias", dias(aid, 1), None)
        assert estado_de(aid)["estado"] == "disponivel"

    def test_afastar_transfere_tudo_e_deixa_offline(self):
        aid = novo_atendente()
        colega = novo_atendente()
        c1, c2 = nova_conversa(aid), nova_conversa(aid)
        r = presenca.afastar(aid, "Férias", dias(aid, 1), colega)
        assert r == {"ok": True, "agendado": False, "transferidas": 2}
        donos = {x["atendente_id"] for x in banco.varios(
            "SELECT atendente_id FROM conversa WHERE id = ANY(%s)", ([c1, c2],))}
        assert donos == {colega}
        assert estado_de(aid)["estado"] == "offline"
        assert estado_de(aid)["afastamento_motivo"] == "Férias"

    def test_nao_transfere_para_quem_esta_offline(self):
        aid = novo_atendente()
        fora = novo_atendente(estado="offline")
        nova_conversa(aid)
        with pytest.raises(operacao.DadoInvalido):
            presenca.afastar(aid, "Licença", dias(aid, 1), fora)

    def test_retornar_volta_disponivel(self):
        aid = novo_atendente()
        presenca.afastar(aid, "Férias", dias(aid, 1), None)
        presenca.retornar(aid)
        e = estado_de(aid)
        assert e["estado"] == "disponivel" and e["afastamento_motivo"] is None

    # 🔵 25/09: *"um calendário já indica a saída e a volta, daí volta"*.
    def test_a_volta_e_obrigatoria(self):
        aid = novo_atendente()
        with pytest.raises(operacao.DadoInvalido, match="volta"):
            presenca.afastar(aid, "Férias", None, None)

    def test_a_volta_vem_depois_da_saida(self):
        aid = novo_atendente()
        with pytest.raises(operacao.DadoInvalido, match="depois"):
            presenca.afastar(aid, "Férias", dias(aid, 0), None)

    def test_saida_no_passado_e_recusada(self):
        aid = novo_atendente()
        with pytest.raises(operacao.DadoInvalido):
            presenca.afastar(aid, "Férias", dias(aid, 3), None, de=dias(aid, -1))


class TestAfastamentoMarcado:
    """🔵 25/09: as conversas passam ao substituto *"no dia da saída"*."""

    def test_marcar_nao_afasta_hoje(self):
        """🚨 O PORQUÊ DAS COLUNAS `afasta_*`: gravado em `afastamento_motivo`,
        o afastamento da semana que vem afastaria a pessoa agora."""
        aid, colega = novo_atendente(), novo_atendente()
        r = presenca.afastar(aid, "Férias", dias(aid, 5), colega, de=dias(aid, 2))
        assert r["agendado"] is True
        e = estado_de(aid)
        assert e["estado"] == "disponivel" and e["afastamento_motivo"] is None
        assert presenca.pode_receber(aid) == (True, "")
        assert banco.um("SELECT afasta_em FROM atendente WHERE id = %s",
                        (aid,))["afasta_em"] == dias(aid, 2)

    def test_marcar_exige_substituto(self):
        aid = novo_atendente()
        with pytest.raises(operacao.DadoInvalido, match="receber"):
            presenca.afastar(aid, "Férias", dias(aid, 5), None, de=dias(aid, 2))

    def _chegou_o_dia(self, aid):
        banco.executar("UPDATE atendente SET afasta_em = %s WHERE id = %s",
                       (dias(aid, 0), aid))
        return presenca.aplicar_afastamentos(somente=[aid])

    def test_no_dia_da_saida_transfere_ao_substituto(self):
        aid, colega = novo_atendente(), novo_atendente()
        presenca.afastar(aid, "Férias", dias(aid, 5), colega, de=dias(aid, 2))
        cid = nova_conversa(aid)
        r = self._chegou_o_dia(aid)
        assert r["iniciados"] == [aid]
        assert banco.um("SELECT atendente_id FROM conversa WHERE id = %s",
                        (cid,))["atendente_id"] == colega
        linha = banco.um("SELECT estado, afastamento_motivo, afastado_ate, afasta_em "
                         "FROM atendente WHERE id = %s", (aid,))
        assert linha["estado"] == "offline" and linha["afastamento_motivo"] == "Férias"
        assert linha["afastado_ate"] == dias(aid, 5) and linha["afasta_em"] is None

    def test_substituto_offline_no_dia_manda_para_a_fila(self):
        aid, colega = novo_atendente(), novo_atendente()
        presenca.afastar(aid, "Férias", dias(aid, 5), colega, de=dias(aid, 2))
        cid = nova_conversa(aid)
        banco.executar("UPDATE atendente SET estado = 'offline' WHERE id = %s", (colega,))
        self._chegou_o_dia(aid)
        conversa = banco.um("SELECT atendente_id, estado FROM conversa WHERE id = %s", (cid,))
        assert conversa["atendente_id"] is None and conversa["estado"] == "fila"
        nota = banco.um("SELECT conteudo FROM mensagem WHERE conversa_id = %s "
                        "AND tipo = 'nota' AND autor = 'sistema'", (cid,))
        assert nota and "afastamento" in nota["conteudo"]

    def test_no_dia_da_volta_encerra_e_fica_offline(self):
        aid = novo_atendente()
        presenca.afastar(aid, "Férias", dias(aid, 1), None)
        banco.executar("UPDATE atendente SET afastado_ate = %s WHERE id = %s",
                       (dias(aid, 0), aid))
        r = presenca.aplicar_afastamentos(somente=[aid])
        assert r["encerrados"] == [aid]
        e = estado_de(aid)
        assert e["afastamento_motivo"] is None and e["estado"] == "offline"


class TestAfastadoNaBarra:
    """🔵 25/09: barra travada; a volta é pela Minha conta."""

    def test_afastado_nao_escolhe_estado(self):
        aid = novo_atendente()
        presenca.afastar(aid, "Férias", dias(aid, 3), None)
        with pytest.raises(operacao.DadoInvalido, match="Minha conta"):
            presenca.definir_estado_manual(aid, "disponivel")
        assert estado_de(aid)["afastamento_motivo"] == "Férias"

    def test_volta_para_ontem_encerra(self):
        """*"ela loga e vai na configuração dela e coloca o dia de ontem"*."""
        aid = novo_atendente()
        presenca.afastar(aid, "Férias", dias(aid, 3), None)
        assert presenca.definir_minha_volta(aid, dias(aid, -1))["encerrado"] is True
        e = estado_de(aid)
        assert e["afastamento_motivo"] is None and e["estado"] == "disponivel"

    def test_volta_mais_tarde_so_muda_a_data(self):
        aid = novo_atendente()
        presenca.afastar(aid, "Férias", dias(aid, 3), None)
        presenca.definir_minha_volta(aid, dias(aid, 10))
        assert banco.um("SELECT afastado_ate FROM atendente WHERE id = %s",
                        (aid,))["afastado_ate"] == dias(aid, 10)

    def test_marcado_com_volta_hoje_e_cancelado(self):
        aid, colega = novo_atendente(), novo_atendente()
        presenca.afastar(aid, "Férias", dias(aid, 5), colega, de=dias(aid, 2))
        presenca.definir_minha_volta(aid, dias(aid, 0))
        assert banco.um("SELECT afasta_em FROM atendente WHERE id = %s",
                        (aid,))["afasta_em"] is None

    def test_quem_nao_esta_afastado_e_recusado(self):
        aid = novo_atendente()
        with pytest.raises(operacao.DadoInvalido):
            presenca.definir_minha_volta(aid, dias(aid, 1))


# ------------------------------------------------------ jornada controla estado

def _dar_jornada(aid, dia_semana, inicio="08:00", fim="18:00"):
    banco.executar(
        "INSERT INTO atendente_jornada (atendente_id, dia_semana, inicio, fim) "
        "VALUES (%s, %s, %s, %s)", (aid, dia_semana, inicio, fim))


# 2026-10-05 é uma SEGUNDA. Em São Paulo (UTC-3): 11:00Z = 08:00 (início),
# 21:00Z = 18:00 (fim), 15:00Z = 12:00 (meio do turno). DOW de segunda = 1.
_UTC = timezone.utc
_SEG = 1
_INICIO_Z = datetime(2026, 10, 5, 11, 0, tzinfo=_UTC)
_MEIO_Z = datetime(2026, 10, 5, 15, 0, tzinfo=_UTC)
_FIM_Z = datetime(2026, 10, 5, 21, 0, tzinfo=_UTC)
_UM_MIN = timedelta(minutes=1)


class TestJornadaControlaEstado:
    """🔵 05/10: o estado vira pelas bordas da jornada -- disponível no início,
    offline no fim -- e SÓ nas bordas (no meio não toca)."""

    def test_o_inicio_do_turno_poe_disponivel_e_zera_o_relogio(self):
        # Entrou a noite offline/parado; ao cruzar as 08:00, volta disponível.
        aid = novo_atendente(parado_ha_min=600, estado="offline", automatico=True)
        _dar_jornada(aid, _SEG)
        r = presenca.aplicar_jornada(agora=_INICIO_Z, desde=_INICIO_Z - _UM_MIN,
                                     forcar=True, somente=[aid])
        assert aid in r["ligados"]
        assert estado_de(aid)["estado"] == "disponivel"
        # Relógio zerado: a inatividade logo depois NÃO o derruba.
        r2 = presenca.aplicar_regra(agora=_INICIO_Z, forcar=True, somente=[aid])
        assert aid not in r2["offline"] and aid not in r2["ausentes"]

    def test_o_fim_do_turno_poe_offline(self):
        aid = novo_atendente(estado="disponivel")
        _dar_jornada(aid, _SEG)
        r = presenca.aplicar_jornada(agora=_FIM_Z, desde=_FIM_Z - _UM_MIN,
                                     forcar=True, somente=[aid])
        assert aid in r["deslogados"]
        assert estado_de(aid)["estado"] == "offline"

    def test_no_meio_do_turno_nao_toca_na_escolha_manual(self):
        aid = novo_atendente(estado="nao_perturbe")
        _dar_jornada(aid, _SEG)
        r = presenca.aplicar_jornada(agora=_MEIO_Z, desde=_MEIO_Z - _UM_MIN,
                                     forcar=True, somente=[aid])
        assert r["ligados"] == [] and r["deslogados"] == []
        assert estado_de(aid)["estado"] == "nao_perturbe"

    def test_owner_sempre_online_nao_cai_no_fim(self):
        aid = novo_atendente(estado="disponivel")
        # `owner` é coluna gerada de `perfil = 'owner'`; não se escreve direto.
        banco.executar("UPDATE atendente SET perfil = 'owner', sempre_online = true "
                       "WHERE id = %s", (aid,))
        _dar_jornada(aid, _SEG)
        r = presenca.aplicar_jornada(agora=_FIM_Z, desde=_FIM_Z - _UM_MIN,
                                     forcar=True, somente=[aid])
        assert aid not in r["deslogados"]
        assert estado_de(aid)["estado"] == "disponivel"

    def test_sem_jornada_no_dia_nao_muda_nada(self):
        # Jornada só de TERÇA (DOW 2); na segunda, nenhuma borda.
        aid = novo_atendente(estado="disponivel")
        _dar_jornada(aid, 2)
        r = presenca.aplicar_jornada(agora=_INICIO_Z, desde=_INICIO_Z - _UM_MIN,
                                     forcar=True, somente=[aid])
        assert r["ligados"] == [] and r["deslogados"] == []

    def test_em_jornada_agora_pega_so_quem_tem_turno_cobrindo_agora(self):
        """🔵 05/10: o conjunto, em uma consulta, que a Caixa e o chat usam para
        o rótulo do offline ("Ausente" dentro do turno)."""
        from movizap import operacao
        dentro = novo_atendente()
        fora = novo_atendente()
        for d in range(7):  # turno cobrindo qualquer dia/hora
            _dar_jornada(dentro, d, "00:00", "23:59")
        r = operacao.em_jornada_agora([dentro, fora])
        assert dentro in r
        assert fora not in r
        assert operacao.em_jornada_agora([]) == set()

    def test_desligada_nao_faz_nada(self, monkeypatch):
        # Config monkeypatchado (independe do estado real da produção, que a
        # Fase 2 liga): sem `forcar` e desligada, a régua não mexe.
        config_falsa(monkeypatch, jornada_controla_estado=False)
        aid = novo_atendente(estado="offline", automatico=True)
        _dar_jornada(aid, _SEG)
        r = presenca.aplicar_jornada(agora=_INICIO_Z, desde=_INICIO_Z - _UM_MIN,
                                     somente=[aid])
        assert r["ligada"] is False
        assert estado_de(aid)["estado"] == "offline"


# ------------------------------------------------------------ fim de expediente

class TestFimDeExpediente:
    def _preparar(self, monkeypatch, dono_com_jornada=True):
        config_falsa(monkeypatch, mensagem_ligada=True, mensagem_texto="Encerramos por hoje.")
        monkeypatch.setattr(operacao, "jornada_ativa", lambda: True)
        dono = novo_atendente()
        if dono_com_jornada:
            # Um dia que não é hoje: agora, com certeza, fora da jornada.
            hoje = (datetime.now(timezone(timedelta(hours=-3))).weekday() + 1) % 7
            operacao.definir_jornada(dono, [{"dia_semana": (hoje + 3) % 7,
                                             "inicio": "08:00", "fim": "18:00"}])
        return dono

    def test_desligada_nao_manda(self, monkeypatch, sem_enviar):
        config_falsa(monkeypatch)
        cid = nova_conversa(novo_atendente())
        assert automacao.fora_do_expediente(cid)["enviou"] is False
        assert sem_enviar == []

    def test_fora_da_jornada_manda_uma_vez(self, monkeypatch, sem_enviar):
        cid = nova_conversa(self._preparar(monkeypatch))
        assert automacao.fora_do_expediente(cid)["enviou"] is True
        assert automacao.fora_do_expediente(cid) == {"enviou": False, "motivo": "ja avisada"}
        assert [m["texto"] for m in sem_enviar] == ["Encerramos por hoje."]

    def test_conversa_sem_dono_nao_recebe(self, monkeypatch, sem_enviar):
        self._preparar(monkeypatch)
        cid = nova_conversa(None)
        assert automacao.fora_do_expediente(cid)["motivo"] == "sem dono"

    def test_dono_sem_jornada_nao_recebe(self, monkeypatch, sem_enviar):
        cid = nova_conversa(self._preparar(monkeypatch, dono_com_jornada=False))
        assert automacao.fora_do_expediente(cid)["motivo"] == "dono sem jornada"


# ------------------------------------------------------------ o fuso da jornada

def test_em_jornada_usa_o_fuso_da_pessoa():
    """🚨 Até 24/09 comparava a hora UTC com a jornada local: 10:00 de
    Brasília (13:00 UTC) contava como fora de 08:00-12:00."""
    aid = novo_atendente()
    operacao.definir_jornada(aid, [{"dia_semana": 4, "inicio": "08:00", "fim": "12:00"}])
    quinta_10h_brasilia = datetime(2026, 9, 24, 13, 0, tzinfo=timezone.utc)
    assert operacao.em_jornada(aid, quinta_10h_brasilia) is True
    quinta_13h_brasilia = datetime(2026, 9, 24, 16, 0, tzinfo=timezone.utc)
    assert operacao.em_jornada(aid, quinta_13h_brasilia) is False


# ------------------------------------------------------------ achados da auditoria (24/09)

class TestAchadosDaAuditoria:
    def test_quem_esta_offline_nao_herda_a_conversa(self):
        """Herdar é receber: o dono sai e quem estava offline não fica com ela."""
        dono = novo_atendente()
        fora = novo_atendente(estado="offline")
        presente = novo_atendente()
        cid = nova_conversa(dono)
        banco.executar(
            "INSERT INTO conversa_participante (conversa_id, atendente_id, entrou_em) "
            "VALUES (%s, %s, now() - interval '2 hours'), (%s, %s, now() - interval '1 hour')",
            (cid, fora, cid, presente))
        r = conversas.sair(cid, dono)
        assert r["novo_dono"] == presente

    def test_ninguem_disponivel_para_herdar_volta_para_a_fila(self):
        dono = novo_atendente()
        fora = novo_atendente(estado="offline")
        cid = nova_conversa(dono)
        banco.executar(
            "INSERT INTO conversa_participante (conversa_id, atendente_id) VALUES (%s, %s)",
            (cid, fora))
        assert conversas.sair(cid, dono)["para_fila"] is True

    def test_email_repetido_e_recusado_com_frase(self):
        _seq[0] += 1
        email = f"{LOGIN}dup{_seq[0]}@teste.invalid"
        operacao.criar_atendente("Zz Dup A", f"{LOGIN}dupa{_seq[0]}", email)
        with pytest.raises(operacao.DadoInvalido, match="e-mail"):
            operacao.criar_atendente("Zz Dup B", f"{LOGIN}dupb{_seq[0]}", email.upper())
