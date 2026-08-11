"""Testes da fila, da transferência e do encerramento — ATD_1.3 e ATD_5.1.

🚨 O caso central aqui é o balde "sem triagem". Com a IA desligada, TODA
conversa nasce com `time_id` NULL. Uma fila agrupada só por time apareceria
vazia com gente real esperando — e esse é o pior jeito de falhar, porque
parece "nenhuma mensagem nova".

⚠️ Telefone de DDD inexistente (+55 99 …) para nunca casar com conversa real.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

FONE = "+5599922220000"


def limpar():
    banco.executar(
        "DELETE FROM transferencia WHERE conversa_id IN "
        "(SELECT id FROM conversa WHERE telefone_e164 = %s)", (FONE,))
    banco.executar(
        "DELETE FROM mensagem WHERE conversa_id IN "
        "(SELECT id FROM conversa WHERE telefone_e164 = %s)", (FONE,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (FONE,))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture
def uma_conversa():
    canal = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not canal:
        pytest.skip("canal atendimento não cadastrado")
    with banco.cursor() as cur:
        conversa_id = conversas.garantir_conversa(cur, canal["id"], FONE)
    yield conversa_id
    limpar()


class TestFilaMostraQuemEspera:
    def test_conversa_sem_time_cai_no_balde_sem_triagem(self, uma_conversa):
        """🚨 Sem este balde, a tela apareceria vazia com gente esperando."""
        grupos = conversas.fila()
        sem_triagem = [g for g in grupos if g["sem_triagem"]]
        assert len(sem_triagem) == 1
        ids = [c["id"] for c in sem_triagem[0]["conversas"]]
        assert uma_conversa in ids

    def test_o_balde_sem_triagem_vem_primeiro(self, uma_conversa):
        grupos = conversas.fila()
        assert grupos[0]["sem_triagem"] is True

    def test_time_vazio_aparece_com_zero(self, uma_conversa):
        """"0 esperando" é informação: some da tela e ninguém sabe que o time
        existe."""
        nomes = [g["time_nome"] for g in conversas.fila() if not g["sem_triagem"]]
        ativos = [t["nome"] for t in
                  banco.varios("SELECT nome FROM time WHERE ativo")]
        for nome in ativos:
            assert nome in nomes

    def test_quem_tem_dono_sai_da_fila(self, uma_conversa):
        a = banco.um("SELECT id FROM atendente ORDER BY id LIMIT 1")
        if not a:
            pytest.skip("nenhum atendente cadastrado")
        conversas.assumir(uma_conversa, a["id"])
        todas = [c["id"] for g in conversas.fila() for c in g["conversas"]]
        assert uma_conversa not in todas


class TestTransferenciaEATriagemManual:
    def test_transferir_para_time_manda_para_a_fila_daquele_time(self, uma_conversa):
        t = banco.um("SELECT id, nome FROM time WHERE ativo ORDER BY id LIMIT 1")
        r = conversas.transferir(uma_conversa, t["id"], None)
        assert r["ok"] is True

        c = banco.um("SELECT time_id, estado, atendente_id, qtd_transferencias "
                     "FROM conversa WHERE id = %s", (uma_conversa,))
        assert c["time_id"] == t["id"]
        assert c["estado"] == "fila"
        assert c["atendente_id"] is None
        assert c["qtd_transferencias"] == 1

        grupo = [g for g in conversas.fila() if g["time_id"] == t["id"]][0]
        assert uma_conversa in [x["id"] for x in grupo["conversas"]]

    def test_transferencia_deixa_rastro(self, uma_conversa):
        """🚨 `motivo` é vocabulário fechado no banco; o texto livre é o
        `resumo`. Gravar texto em `motivo` levanta CheckViolation — foi como
        isto apareceu em 07/08."""
        t = banco.um("SELECT id FROM time WHERE ativo ORDER BY id LIMIT 1")
        conversas.transferir(uma_conversa, t["id"], None,
                             texto_resumo="cliente quer segunda via")
        rastro = banco.um(
            "SELECT motivo, resumo, para_time_id FROM transferencia "
            "WHERE conversa_id = %s", (uma_conversa,))
        assert rastro["motivo"] == "manual"
        assert rastro["resumo"] == "cliente quer segunda via"
        assert rastro["para_time_id"] == t["id"]

    def test_motivo_fora_do_vocabulario_e_recusado(self, uma_conversa):
        t = banco.um("SELECT id FROM time WHERE ativo ORDER BY id LIMIT 1")
        r = conversas.transferir(uma_conversa, t["id"], None, "porque sim")
        assert r["ok"] is False
        assert "Motivo inválido" in r["motivo"]

    def test_time_inativo_e_recusado(self, uma_conversa):
        r = conversas.transferir(uma_conversa, 999999, None)
        assert r["ok"] is False

    def test_sem_destino_e_recusado(self, uma_conversa):
        r = conversas.transferir(uma_conversa, None, None)
        assert r["ok"] is False

    def test_devolver_tira_o_dono_sem_encerrar(self, uma_conversa):
        a = banco.um("SELECT id FROM atendente ORDER BY id LIMIT 1")
        if not a:
            pytest.skip("nenhum atendente cadastrado")
        conversas.assumir(uma_conversa, a["id"])
        r = conversas.devolver_para_fila(uma_conversa, a["id"])
        assert r["ok"] is True
        c = banco.um("SELECT atendente_id, estado FROM conversa WHERE id = %s",
                     (uma_conversa,))
        assert c["atendente_id"] is None
        assert c["estado"] == "fila"


@pytest.fixture()
def classificacao():
    """Uma classificação SÓ deste teste.

    🚨 Antes daqui os testes liam `SELECT ... FROM classificacao LIMIT 1` — a
    linha de PRODUÇÃO. Quebraram no instante em que a base ficou legitimamente
    sem classificação nenhuma, porque encerrar deixou de exigir em 11/08.
    É a armadilha registrada na metodologia: teste em tabela de produção
    precisa da própria linha.
    """
    ids = {}
    for exige, nome in ((False, "zz_teste_fila_simples"),
                        (True, "zz_teste_fila_com_texto")):
        ids[exige] = banco.um(
            """INSERT INTO classificacao (nome, ordem, exige_comentario, ativo)
               VALUES (%s, 900, %s, true) RETURNING id""", (nome, exige))["id"]
    yield ids
    banco.executar("UPDATE conversa SET classificacao_id = NULL "
                   "WHERE classificacao_id = ANY(%s)", (list(ids.values()),))
    banco.executar("DELETE FROM classificacao WHERE id = ANY(%s)",
                   (list(ids.values()),))


class TestEncerramento:
    def test_encerra_SEM_classificacao(self, uma_conversa):
        """🚨 O comportamento novo de 11/08.

        A obrigatoriedade era CIRCULAR: as 9 classificações existiam porque eu
        as fiz obrigatórias, e eram obrigatórias porque existiam. O escopo
        justificava com "alimenta analytics depois" -- e `REL_1.1` é Fase 3,
        não existe, e nunca houve conversa classificada."""
        assert conversas.encerrar(uma_conversa)["ok"] is True
        linha = banco.um("SELECT estado, classificacao_id FROM conversa "
                         "WHERE id = %s", (uma_conversa,))
        assert linha["estado"] == "resolvida"
        assert linha["classificacao_id"] is None

    def test_classificacao_inexistente_continua_recusada(self, uma_conversa):
        """⚠️ Classificar virou opcional; classificar ERRADO não. Um id que não
        existe faria o histórico apontar para nada."""
        assert conversas.encerrar(uma_conversa, 999999)["ok"] is False

    def test_classificacao_que_exige_comentario_recusa_sem_texto(
            self, uma_conversa, classificacao):
        assert conversas.encerrar(uma_conversa, classificacao[True])["ok"] is False
        assert conversas.encerrar(uma_conversa, classificacao[True],
                                  "foi isso aqui")["ok"] is True

    def test_encerrada_sai_da_fila_e_entra_no_historico(self, uma_conversa,
                                                        classificacao):
        assert conversas.encerrar(uma_conversa, classificacao[False])["ok"] is True

        todas = [x["id"] for g in conversas.fila() for x in g["conversas"]]
        assert uma_conversa not in todas
        assert uma_conversa in [h["id"] for h in conversas.historico()]

    def test_nao_encerra_duas_vezes(self, uma_conversa, classificacao):
        conversas.encerrar(uma_conversa, classificacao[False])
        assert conversas.encerrar(uma_conversa, classificacao[False])["ok"] is False

    def test_encerrar_grava_a_duracao(self, uma_conversa, classificacao):
        conversas.encerrar(uma_conversa, classificacao[False])
        linha = banco.um("SELECT segundos_total, resolvida_em FROM conversa "
                         "WHERE id = %s", (uma_conversa,))
        assert linha["resolvida_em"] is not None
        assert linha["segundos_total"] is not None

    def test_apos_encerrar_um_novo_contato_abre_conversa_nova(self, uma_conversa,
                                                              classificacao):
        """🚨 `ux_conversa_aberta` é parcial (`estado <> 'resolvida'`): a mesma
        pessoa pode voltar a falar e isso é uma conversa NOVA, não a antiga
        reaberta -- senão o histórico juntaria dois assuntos diferentes."""
        conversas.encerrar(uma_conversa, classificacao[False])
        canal = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
        with banco.cursor() as cur:
            nova = conversas.garantir_conversa(cur, canal["id"], FONE)
        assert nova != uma_conversa


class TestHistorico:
    def test_busca_por_telefone_em_qualquer_grafia(self, uma_conversa,
                                                   classificacao):
        conversas.encerrar(uma_conversa, classificacao[False])
        for grafia in (FONE, "99 92222-0000", "5599922220000"):
            achados = [h["id"] for h in conversas.historico(busca=grafia)]
            assert uma_conversa in achados, f"grafia {grafia} não achou"

    def test_conversa_aberta_nao_aparece_no_historico(self, uma_conversa):
        assert uma_conversa not in [h["id"] for h in conversas.historico()]
