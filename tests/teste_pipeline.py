# -*- coding: utf-8 -*-
r"""O motor das etapas NOSSAS — `movizap/pipeline.py` (05/11).

🔵 Dois pedidos dele que são a mesma coisa: a coluna `Chamados` antes de *Nova
solicitação*, e *"a aba 'Operação' do Movizap é a mesma lógica para os demais"*.

🚨 **A REGRA QUE ESTE ARQUIVO EXISTE PARA PRENDER:** este módulo **nunca fala
com o Harmonit**. Card de pipeline não tem OS — não há `situacaoId` para
gravar, e inventar um seria escrever no ERP sobre uma OS que não existe. O
`passagem.mover` escreve; este **não pode**. A prova é um dublê que **conta as
chamadas** e exige zero.

⚠️ E a outra: **"Virou OS" só marca.** Decisão dele — *"só marca; a OS é pelo
Operação"*. Finalizar não escreve fora, e é isso que torna o botão reversível.

Roda:  venv/bin/python -m pytest tests/teste_pipeline.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from movizap import banco, pipeline  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ABA_TESTE = "zz-TESTE-PIPE"


@pytest.fixture(scope="module", autouse=True)
def banco_aberto():
    banco.abrir()
    yield


@pytest.fixture
def aba():
    """Uma aba de teste com três etapas, apagada no fim.

    ⚠️ Aba PRÓPRIA, e não a `PNL_1.1` de produção: criar card na aba real
    deixaria sujeira no quadro que a operação olha.
    🚨 E o `painel` tem de ser um dos quatro — há CHECK no banco.
    """
    def _apagar():
        banco.executar(
            "DELETE FROM painel_aba WHERE codigo_tela = %s", (ABA_TESTE,))
    _apagar()
    linha = banco.um(
        """INSERT INTO painel_aba (painel, codigo_tela, titulo, ordem)
           VALUES ('operacao', %s, 'zz Teste pipeline', 99) RETURNING id""",
        (ABA_TESTE,))
    etapas = []
    for i, titulo in enumerate(("zz Primeira", "zz Meio", "zz Ultima")):
        e = banco.um(
            """INSERT INTO pipeline_etapa (aba_id, titulo, ordem, final)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (linha["id"], titulo, i, i == 2))
        etapas.append(e["id"])
    yield {"id": linha["id"], "etapas": etapas}
    # 🚨 O CASCADE leva etapa, card e passagem -- conferido na migração 092.
    _apagar()


# ============================================================================
# 🚨 A REGRA CENTRAL: nada chega ao Harmonit
# ============================================================================
class TestNadaChegaAoHarmonit:

    def test_o_modulo_nao_importa_a_ponte(self):
        """🚨 A prova mais forte, e é estática: se o `fpsl_ponte` não está no
        módulo, não há como uma mudança futura escorregar para o ERP sem que
        este teste caia primeiro."""
        import movizap.pipeline as p
        assert not hasattr(p, "fpsl_ponte"), (
            "o pipeline importou a ponte do FPSL -- card sem OS nao tem o que "
            "gravar no ERP")

    def test_mover_e_finalizar_nao_chamam_a_ponte(self, aba, monkeypatch):
        """E a prova dinâmica: um dublê que conta as chamadas, e exige zero."""
        from movizap import fpsl_ponte
        chamadas = []
        for nome in ("gravar_situacao_da_os", "criar_os",
                     "gravar_prioridade_da_os"):
            if hasattr(fpsl_ponte, nome):
                monkeypatch.setattr(
                    fpsl_ponte, nome,
                    lambda *a, **k: chamadas.append(nome) or {"ok": True})

        c = pipeline.criar(aba["id"], aba["etapas"][0])
        pipeline.mover(c["id"], aba["etapas"][1], atendente_id=None)
        pipeline.finalizar(c["id"], "virou_os", atendente_id=None)
        assert chamadas == [], f"o pipeline falou com o ERP: {chamadas}"


# ============================================================================
# O card e o movimento
# ============================================================================
class TestOCard:

    def test_nasce_na_etapa_e_registra_a_primeira_passagem(self, aba):
        c = pipeline.criar(aba["id"], aba["etapas"][0])
        assert c["etapa_id"] == aba["etapas"][0]
        h = pipeline.historico(c["id"])
        assert len(h) == 1
        # ⚠️ `de_etapa` nulo na primeira: o card nasce, não vem de outra.
        assert h[0]["de_etapa"] is None
        assert h[0]["para_etapa"] == aba["etapas"][0]

    def test_mover_grava_de_onde_para_onde_e_quem(self, aba):
        c = pipeline.criar(aba["id"], aba["etapas"][0])
        pipeline.mover(c["id"], aba["etapas"][1], atendente_id=None)
        h = pipeline.historico(c["id"])
        assert len(h) == 2
        assert h[0]["de_etapa"] == aba["etapas"][0]
        assert h[0]["para_etapa"] == aba["etapas"][1]
        assert h[0]["de_titulo"] == "zz Primeira"
        assert h[0]["para_titulo"] == "zz Meio"

    def test_mover_para_a_MESMA_etapa_nao_registra_passagem(self, aba):
        """⚠️ Soltar o card onde ele já está não é movimento — e gravar uma
        passagem ali encheria o log de linhas que não dizem nada."""
        c = pipeline.criar(aba["id"], aba["etapas"][0])
        r = pipeline.mover(c["id"], aba["etapas"][0], atendente_id=None)
        assert r["mudou"] is False
        assert len(pipeline.historico(c["id"])) == 1

    def test_etapa_de_OUTRA_aba_e_recusada(self, aba):
        """🚨 Não é validação de caminho (não existe caminho proibido, decisão
        dele) — é a garantia de que o card não atravessa para a pipeline de
        outro setor, onde ficaria invisível."""
        outra = banco.um(
            """INSERT INTO painel_aba (painel, codigo_tela, titulo, ordem)
               VALUES ('pos_venda', 'zz-OUTRA-PIPE', 'zz outra', 98)
               RETURNING id""")
        try:
            e = banco.um(
                """INSERT INTO pipeline_etapa (aba_id, titulo, ordem)
                   VALUES (%s, 'zz de outra aba', 0) RETURNING id""",
                (outra["id"],))
            c = pipeline.criar(aba["id"], aba["etapas"][0])
            with pytest.raises(DadoInvalido, match="outra aba"):
                pipeline.mover(c["id"], e["id"], atendente_id=None)
        finally:
            banco.executar("DELETE FROM painel_aba WHERE id = %s", (outra["id"],))

    def test_criar_com_etapa_que_nao_e_da_aba_e_recusado(self, aba):
        with pytest.raises(DadoInvalido):
            pipeline.criar(aba["id"], 999999)

    def test_card_inexistente_e_recusado(self, aba):
        with pytest.raises(DadoInvalido, match="não existe"):
            pipeline.mover(999999, aba["etapas"][0], atendente_id=None)


# ============================================================================
# 🚨 Um chamado, UM card
# ============================================================================
class TestUmChamadoUmCard:
    """O envio do formulário é retentável — o cliente pode reenviar. Dois cards
    para o mesmo chamado seriam duas análises da mesma coisa."""

    @pytest.fixture
    def solicitacao(self):
        f = banco.um("SELECT id FROM formulario WHERE slug = 'suporte'")
        s = banco.um(
            """INSERT INTO formulario_solicitacao (formulario_id, valores)
               VALUES (%s, '{}'::jsonb) RETURNING id""", (f["id"],))
        yield s["id"]
        banco.executar("DELETE FROM formulario_solicitacao WHERE id = %s",
                       (s["id"],))

    def test_criar_duas_vezes_devolve_o_MESMO_card(self, aba, solicitacao):
        a = pipeline.criar(aba["id"], aba["etapas"][0],
                           solicitacao_id=solicitacao)
        b = pipeline.criar(aba["id"], aba["etapas"][0],
                           solicitacao_id=solicitacao)
        assert a["id"] == b["id"]
        assert banco.um(
            "SELECT count(*) n FROM pipeline_card WHERE solicitacao_id = %s",
            (solicitacao,))["n"] == 1

    def test_da_solicitacao_acha_o_card(self, aba, solicitacao):
        c = pipeline.criar(aba["id"], aba["etapas"][0],
                           solicitacao_id=solicitacao)
        assert pipeline.da_solicitacao(solicitacao)["id"] == c["id"]

    def test_apagar_a_solicitacao_leva_o_card(self, aba, solicitacao):
        """⚠️ `ON DELETE CASCADE`: card de chamado apagado não fica órfão no
        quadro, apontando para uma solicitação que não existe mais."""
        c = pipeline.criar(aba["id"], aba["etapas"][0],
                           solicitacao_id=solicitacao)
        banco.executar("DELETE FROM formulario_solicitacao WHERE id = %s",
                       (solicitacao,))
        assert banco.um("SELECT count(*) n FROM pipeline_card WHERE id = %s",
                        (c["id"],))["n"] == 0


# ============================================================================
# O desfecho
# ============================================================================
class TestODesfecho:

    def test_os_dois_desfechos_gravam_quem_e_quando(self, aba):
        for desfecho in ("resolvido", "virou_os"):
            c = pipeline.criar(aba["id"], aba["etapas"][0])
            r = pipeline.finalizar(c["id"], desfecho, atendente_id=None)
            assert r["desfecho"] == desfecho
            assert r["desfecho_em"] is not None
            assert r["rotulo"] == pipeline.DESFECHOS[desfecho]

    def test_desfecho_inventado_e_recusado(self, aba):
        c = pipeline.criar(aba["id"], aba["etapas"][0])
        with pytest.raises(DadoInvalido, match="desconhecido"):
            pipeline.finalizar(c["id"], "zz_qualquer", atendente_id=None)

    def test_finalizar_duas_vezes_e_recusado(self, aba):
        """⚠️ A segunda chamada reescreveria o "quando" e apagaria o desfecho
        que alguém registrou."""
        c = pipeline.criar(aba["id"], aba["etapas"][0])
        pipeline.finalizar(c["id"], "resolvido", atendente_id=None)
        with pytest.raises(DadoInvalido, match="já foi finalizado"):
            pipeline.finalizar(c["id"], "virou_os", atendente_id=None)

    def test_card_finalizado_nao_se_move(self, aba):
        """🚨 O desfecho é o fim da linha: mover um arquivado faria o histórico
        mentir sobre quando ele terminou."""
        c = pipeline.criar(aba["id"], aba["etapas"][0])
        pipeline.finalizar(c["id"], "resolvido", atendente_id=None)
        with pytest.raises(DadoInvalido, match="já foi finalizado"):
            pipeline.mover(c["id"], aba["etapas"][1], atendente_id=None)

    def test_reabrir_desfaz_e_NAO_apaga_o_historico(self, aba):
        """🔵 Finalizar só marca, e marca que não se desmarca é porta de mão
        única numa tela de uso diário. ⚠️ Mas a passagem fica: o histórico de
        etapas continua sendo o que aconteceu."""
        c = pipeline.criar(aba["id"], aba["etapas"][0])
        pipeline.mover(c["id"], aba["etapas"][1], atendente_id=None)
        pipeline.finalizar(c["id"], "resolvido", atendente_id=None)
        assert pipeline.reabrir(c["id"], atendente_id=None)["mudou"] is True
        assert pipeline.da_solicitacao and len(pipeline.historico(c["id"])) == 2
        # e agora move de novo
        assert pipeline.mover(c["id"], aba["etapas"][2],
                              atendente_id=None)["mudou"] is True

    def test_reabrir_card_aberto_nao_faz_nada(self, aba):
        c = pipeline.criar(aba["id"], aba["etapas"][0])
        assert pipeline.reabrir(c["id"], atendente_id=None)["mudou"] is False

    def test_o_CHECK_do_banco_exige_data_com_o_desfecho(self, aba):
        """🚨 Desfecho sem data seria arquivo sem quando. Esta é a prova de que
        o banco não aceita, mesmo que o código erre."""
        c = pipeline.criar(aba["id"], aba["etapas"][0])
        with pytest.raises(Exception, match="desfecho_tem_data"):
            banco.executar(
                "UPDATE pipeline_card SET desfecho = 'resolvido' WHERE id = %s",
                (c["id"],))


# ============================================================================
# 🚨 O arquivado vai para o FIM da fila
# ============================================================================
class TestAOrdemDaFila:
    """🔵 *"ele esmaece e fica no fim da fila arquivado com status de
    concluído"*."""

    def test_o_arquivado_vem_depois_dos_abertos(self, aba):
        velho = pipeline.criar(aba["id"], aba["etapas"][0])
        novo = pipeline.criar(aba["id"], aba["etapas"][0])
        # o VELHO é finalizado: sem a regra, ele viria antes (foi criado antes)
        pipeline.finalizar(velho["id"], "resolvido", atendente_id=None)
        ordem = [c["id"] for c in pipeline.cards_da_aba(aba["id"])]
        assert ordem.index(novo["id"]) < ordem.index(velho["id"])

    def test_o_card_traz_a_conta_de_observacoes(self, aba):
        f = banco.um("SELECT id FROM formulario WHERE slug = 'suporte'")
        s = banco.um(
            """INSERT INTO formulario_solicitacao (formulario_id, valores)
               VALUES (%s, '{}'::jsonb) RETURNING id""", (f["id"],))
        try:
            c = pipeline.criar(aba["id"], aba["etapas"][0],
                               solicitacao_id=s["id"])
            banco.executar(
                """INSERT INTO os_observacao (solicitacao_id, texto)
                   VALUES (%s, 'zz recado do chamado')""", (s["id"],))
            achado = next(x for x in pipeline.cards_da_aba(aba["id"])
                          if x["id"] == c["id"])
            assert achado["observacoes"] == 1
            assert achado["formulario"] == "Suporte"
        finally:
            banco.executar("DELETE FROM formulario_solicitacao WHERE id = %s",
                           (s["id"],))


# ============================================================================
# 🚨 A MIGRAÇÃO 093 — a passagem é RETRATO, e foi esta suíte que a pediu
# ============================================================================
class TestOHistoricoEhRetrato:
    """🚨 ESTE BLOCO NASCEU DE UM DEFEITO MEU, achado minutos depois de aplicar
    a 092: `pipeline_passagem` referenciava `pipeline_etapa` com FK **sem
    `ON DELETE`**, e com isso apagar uma aba era IMPOSSÍVEL — o CASCADE da aba
    tentava levar as etapas e a passagem as segurava.

    ⚠️ E o conserto não foi pôr CASCADE: isso apagaria o histórico, e *"deve
    ter o log de quem faz o que SEMPRE"* é condição dele. O padrão é o do
    `orcamento_item.servico` — guardar o **título de então**, sem FK."""

    def test_a_passagem_guarda_o_titulo_de_ENTAO(self, aba):
        c = pipeline.criar(aba["id"], aba["etapas"][0])
        pipeline.mover(c["id"], aba["etapas"][1], atendente_id=None)
        # renomeia a etapa DEPOIS da passagem
        banco.executar("UPDATE pipeline_etapa SET titulo = %s WHERE id = %s",
                       ("zz RENOMEADA", aba["etapas"][1]))
        h = pipeline.historico(c["id"])
        # 🚨 o histórico continua dizendo o que dizia
        assert h[0]["para_titulo"] == "zz Meio"
        assert h[0]["de_titulo"] == "zz Primeira"

    def test_apagar_a_ETAPA_nao_leva_o_historico(self, aba):
        """⚠️ Em produção a etapa se DESATIVA (`ativo`), não se apaga. Mas se
        alguém apagar à mão no banco, o histórico tem de sobreviver."""
        c = pipeline.criar(aba["id"], aba["etapas"][0])
        pipeline.mover(c["id"], aba["etapas"][1], atendente_id=None)
        banco.executar("DELETE FROM pipeline_etapa WHERE id = %s",
                       (aba["etapas"][2],))
        h = pipeline.historico(c["id"])
        assert len(h) == 2
        assert h[0]["para_titulo"] == "zz Meio"

    def test_apagar_a_ABA_funciona_e_leva_o_que_e_dela(self, aba):
        """🚨 ERA EXATAMENTE ISTO QUE FALHAVA: `ForeignKeyViolation` na
        `pipeline_etapa`. É a prova do conserto."""
        c = pipeline.criar(aba["id"], aba["etapas"][0])
        pipeline.mover(c["id"], aba["etapas"][1], atendente_id=None)
        banco.executar("DELETE FROM painel_aba WHERE id = %s", (aba["id"],))
        assert banco.um("SELECT count(*) n FROM pipeline_card WHERE id = %s",
                        (c["id"],))["n"] == 0
        assert banco.um(
            "SELECT count(*) n FROM pipeline_passagem WHERE card_id = %s",
            (c["id"],))["n"] == 0

    def test_nao_ha_MAIS_FK_da_passagem_para_a_etapa(self):
        """A prova estrutural, para o defeito não voltar numa migração futura."""
        fks = banco.varios(
            """SELECT conname FROM pg_constraint
                WHERE conrelid = 'pipeline_passagem'::regclass
                  AND contype = 'f'""")
        nomes = [f["conname"] for f in fks]
        assert not [n for n in nomes if "etapa" in n], nomes
        # e as duas que DEVEM existir continuam
        assert any("card_id" in n for n in nomes)
