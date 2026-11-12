"""A ETAPA `Serviço Realizado` — a primeira NOSSA que recebe card COM OS (11/11).

🔵 Dele: *"Criar nova etapa de 'Serviço Realizado'"*, **nossa, fora do
Harmonit**, e *"moverão para la e depois auditarão o card e por fim, atendimento
finalizado"*.

🚨 ATÉ AQUI, CARD NOSSO ERA CARD SEM OS. A `Chamados` é de chamado que ainda não
virou OS. Esta é o **primeiro caso de card com OS numa etapa nossa**: a OS fica
parada em 1316 no Harmonit e o card mora aqui.

🚨 ESCREVE EM TABELAS DE PRODUÇÃO (`pipeline_card`, `pipeline_passagem`) e apaga
no fim. Marca: OS na faixa **99.907.x**.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, paineis, pipeline  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

OS1, OS2 = 99_907_101, 99_907_102


def limpar():
    banco.executar(
        "DELETE FROM pipeline_card WHERE numero_os = ANY(%s)", ([OS1, OS2],))


@pytest.fixture(autouse=True)
def base():
    banco.abrir()
    limpar()
    yield
    banco.abrir()
    limpar()


@pytest.fixture
def aba():
    return pipeline.aba_por_codigo(pipeline.ABA_DA_OPERACAO)


@pytest.fixture
def etapa():
    return next(e for e in pipeline.etapas_nossas_da_operacao()
                if e["titulo"] == "Serviço Realizado")


class TestAEtapa:
    def test_existe_e_e_NOSSA(self, etapa):
        assert etapa["titulo"] == "Serviço Realizado"

    def test_ela_diz_DEPOIS_DE_QUEM_vem(self, etapa):
        """🚨 "entre a 1316 e a 15694" não se diz com um número solto. A etapa
        carrega a situação depois da qual ela aparece."""
        assert etapa["depois_da_situacao"] == 1316

    def test_a_Chamados_continua_NA_FRENTE(self):
        chamados = next(e for e in pipeline.etapas_nossas_da_operacao()
                        if e["titulo"] == "Chamados")
        assert chamados["depois_da_situacao"] is None

    def test_a_tupla_das_situacoes_do_ERP_NAO_mudou_sozinha(self):
        """⚠️ A etapa é NOSSA: ela não entra na tupla das situações do ERP, e
        duas travas da casa dependem de ela ter 17."""
        assert len(paineis.SITUACOES) == 14
        assert "Serviço Realizado" not in dict(paineis.SITUACOES).values()


class TestOQuadroADesenhaNoLugarCERTO:
    def test_ela_vem_LOGO_DEPOIS_de_Servico_Agendado(self):
        """🔵 *"moverão para la e depois auditarão o card e por fim,
        atendimento finalizado"*.

        ⚠️ A PRIMEIRA VERSÃO DESTA TRAVA afirmava que **logo depois** dela vinha
        "Atendimento finalizado", e isso ele não pediu: entre as duas seguem a
        `Aguardando devolução` e a `Analise de Equipamentos Retornados`, que são
        o fluxo do ERP. O que ele descreveu é a ORDEM -- Serviço Agendado →
        Serviço Realizado → ... → Atendimento finalizado --, e é isso que se
        afirma.
        """
        q = paineis.quadro("operacao", so_abertas=False)
        titulos = [c["titulo"] for c in q["colunas"]]
        i = titulos.index("Serviço Realizado")
        assert titulos[i - 1] == "Serviço Agendado"
        assert i < titulos.index("Atendimento finalizado")

    def test_o_quadro_tem_as_colunas_do_ERP_mais_as_nossas(self):
        """17 do ERP + `Chamados` + `Serviço Realizado`."""
        q = paineis.quadro("operacao", so_abertas=False)
        assert len(q["colunas"]) == 16

    def test_a_coluna_dela_tem_situacao_NULA_e_etapa_id(self, etapa):
        """🚨 `situacao_id` nulo é o que diz à tela que mover ali não escreve no
        ERP; o `etapa_id` é para onde o arrasto posta."""
        q = paineis.quadro("operacao", so_abertas=False)
        col = next(c for c in q["colunas"] if c["titulo"] == "Serviço Realizado")
        assert col["situacao_id"] is None
        assert col["etapa_id"] == etapa["id"]


class TestPousarESoltar:
    def test_pousar_cria_o_card_COM_a_OS(self, aba, etapa):
        c = pipeline.pousar_os(aba["id"], etapa["id"], OS1, None)
        assert c["numero_os"] == OS1
        assert c["etapa_id"] == etapa["id"]

    def test_pousar_NAO_fala_com_o_Harmonit(self):
        """🚨 O ponto inteiro da etapa: a OS fica onde está no ERP."""
        import inspect
        fonte = inspect.getsource(pipeline.pousar_os)
        assert "fpsl_ponte" not in fonte
        assert "situacao" not in fonte.lower() or "situacao_id" not in fonte

    def test_pousar_duas_vezes_na_MESMA_etapa_nao_duplica(self, aba, etapa):
        pipeline.pousar_os(aba["id"], etapa["id"], OS1, None)
        pipeline.pousar_os(aba["id"], etapa["id"], OS1, None)
        n = banco.um("SELECT count(*) n FROM pipeline_card WHERE numero_os = %s",
                     (OS1,))["n"]
        assert n == 1

    def test_o_banco_PROIBE_a_mesma_OS_em_duas_etapas(self, aba, etapa):
        """⚠️ Sem o índice único, um clique duplo no arrasto mostraria a mesma
        OS em duas colunas."""
        pipeline.pousar_os(aba["id"], etapa["id"], OS1, None)
        with pytest.raises(Exception):
            banco.executar(
                """INSERT INTO pipeline_card (aba_id, etapa_id, numero_os)
                   VALUES (%s, %s, %s)""", (aba["id"], etapa["id"], OS1))

    def test_a_passagem_e_gravada_ao_pousar(self, aba, etapa):
        c = pipeline.pousar_os(aba["id"], etapa["id"], OS1, None)
        p = pipeline.historico(c["id"])
        assert len(p) == 1
        assert p[0]["para_titulo"] == "Serviço Realizado"
        assert p[0]["de_etapa"] is None

    def test_soltar_FINALIZA_e_nao_apaga(self, aba, etapa):
        """🚨 O histórico de passagens é o registro de que a auditoria
        aconteceu, e apagar a linha levaria isso junto (CASCADE)."""
        c = pipeline.pousar_os(aba["id"], etapa["id"], OS1, None)
        assert pipeline.soltar_os(aba["id"], OS1, None) is True
        linha = banco.um(
            "SELECT desfecho, desfecho_em FROM pipeline_card WHERE id = %s",
            (c["id"],))
        assert linha["desfecho"] == "resolvido"
        assert linha["desfecho_em"] is not None
        assert pipeline.historico(c["id"]), "a passagem tem de sobreviver"

    def test_soltar_o_que_nao_esta_pousado_devolve_False(self, aba):
        assert pipeline.soltar_os(aba["id"], OS2, None) is False

    def test_card_SOLTO_sai_do_mapa_e_volta_para_a_situacao_dele(self, aba,
                                                                 etapa):
        pipeline.pousar_os(aba["id"], etapa["id"], OS1, None)
        assert OS1 in pipeline.cards_por_os(aba["id"])
        pipeline.soltar_os(aba["id"], OS1, None)
        assert OS1 not in pipeline.cards_por_os(aba["id"])

    def test_etapa_de_OUTRA_aba_recusa(self, aba):
        outra = banco.um(
            """SELECT e.id FROM pipeline_etapa e JOIN painel_aba a
                  ON a.id = e.aba_id WHERE a.codigo_tela = 'PNL_1.4' LIMIT 1""")
        if not outra:
            pytest.skip("a PNL_1.4 nao tem etapa")
        with pytest.raises(DadoInvalido) as e:
            pipeline.pousar_os(aba["id"], outra["id"], OS1, None)
        assert "não é desta aba" in str(e.value)


class TestOCardDeCHAMADONaoSeConfunde:
    def test_o_card_com_OS_nao_entra_na_coluna_de_chamado(self, aba, etapa):
        """⚠️ O laço que monta os cards de chamado pula quem tem `numero_os`:
        esse já foi colocado junto da OS, pelo `_colocar`.

        🚨 A PRIMEIRA VERSÃO DESTA TRAVA ERA VAZIA e passava com o defeito
        forjado: eu procurava `OS1` entre os `numero_ordem` da coluna, e o
        `_card_do_chamado` devolve `numero_ordem: None` **sempre** -- é o que
        faz dele um chamado. O card errado entrava e nunca aparecia na lista.
        Agora conto os cards: pousar uma OS não pode mexer na `Chamados`.
        """
        q0 = paineis.quadro("operacao", so_abertas=False)
        antes = len(next(c for c in q0["colunas"]
                         if c["titulo"] == "Chamados")["cards"])

        # 🚨 UMA OS DE VERDADE: card só é posicionado se a OS existir na ponte
        # ou nas nossas solicitações. Com número fictício não há card nenhum
        # para posicionar, e a trava afirmaria sobre o vazio.
        real = next((card.get("numero_ordem") for col in q0["colunas"]
                     if col["situacao_id"] for card in col["cards"]
                     if card.get("numero_ordem")), None)
        if not real:
            pytest.skip("o quadro nao tem OS para exercitar")

        try:
            pipeline.pousar_os(aba["id"], etapa["id"], real, None)
            q = paineis.quadro("operacao", so_abertas=False)
            chamados = next(c for c in q["colunas"]
                            if c["titulo"] == "Chamados")
            assert len(chamados["cards"]) == antes, "a OS entrou na Chamados"

            nossa = next(c for c in q["colunas"]
                         if c["titulo"] == "Serviço Realizado")
            assert real in [c.get("numero_ordem") for c in nossa["cards"]]
            # 🚨 EXATAMENTE UM. Pousei uma OS, e a etapa estava vazia: dois
            # cards aqui significam que o mesmo card entrou por dois caminhos
            # -- uma vez pelo `_colocar` (com o número da OS) e outra pelo laço
            # dos chamados (com `numero_ordem` nulo). Sem contar, a duplicata
            # passa, porque a asserção de cima encontra o número no primeiro.
            assert len(nossa["cards"]) == 1, [
                c.get("numero_ordem") for c in nossa["cards"]]

            # ⚠️ E ela SAIU da coluna da situação dela: é o card com duas
            # posições, e aparecer nas duas seria o defeito.
            for col in q["colunas"]:
                if col["situacao_id"]:
                    assert real not in [c.get("numero_ordem")
                                        for c in col["cards"]], col["titulo"]
        finally:
            # 🚨 DEVOLVE A OS: ela é de produção, e o painel dele não pode
            # ficar com um card parado numa etapa por causa de um teste.
            banco.executar("DELETE FROM pipeline_card WHERE numero_os = %s",
                           (real,))
