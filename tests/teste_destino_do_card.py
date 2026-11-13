# -*- coding: utf-8 -*-
"""As filas da Operação em relação aos outros painéis (migração 106, 11/11).

🔵 **Duas frases dele, e as duas são a mesma ideia:**

  · *"não é nesse financeiro que deve nascer, essas etapas finais do OP devem
    ser excluídas e deveria ter nascido no painel Financeiro, na etapa correta
    'Nova solicitação'"*;
  · *"fiz teste com form de aditivo e não abriu card no contratual como foi
    pedido"*.

📏 **O que a medição achou antes de escrever:**

  · a OS **17119** (ressarcimento, termo 8947) nasceu na situação **15746** e
    apareceu na coluna *Financeiro* do painel da **Operação**. `os_passagem`
    tem **zero** linhas para 15746/15695/16492: ela **nasceu** ali, ninguém a
    moveu — e eu era o suspeito;
  · o envio de aditivo dele gerou a solicitação **3437** e **nenhum card**,
    porque o portão do card era `PROBLEMA_POR_FORMULARIO`, com **um** slug.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from movizap import banco, formularios, paineis, pipeline  # noqa: E402

REENDERECADAS = (15746, 15695, 16492)


@pytest.fixture(autouse=True)
def base():
    banco.abrir()
    yield


class TestAsTresSairamDaOperacao:
    def test_a_lista_tem_quatorze_situacoes(self):
        """🚨 Eram 17; as três do fim saíram. ⚠️ O número fica aqui porque é
        ele que denuncia uma coluna que volta sem ninguém pedir."""
        assert len(paineis.SITUACOES) == 14

    def test_nenhuma_das_tres_e_coluna_da_operacao(self):
        ids = {sid for sid, _ in paineis.SITUACOES}
        assert ids.isdisjoint(REENDERECADAS)
        nomes = {nome for _, nome in paineis.SITUACOES}
        assert "Financeiro" not in nomes
        assert "Pós venda" not in nomes
        assert "Contratual" not in nomes

    def test_elas_estao_declaradas_como_REENDERECADAS(self):
        """🚨 Tirar sem declarar seria apagar: é esta tupla que faz a OS ser
        contada como *noutro painel* em vez de *fora do quadro*."""
        assert set(paineis.SITUACOES_REENDERECADAS) == set(REENDERECADAS)


class TestCadaUmaTemDESTINO:
    """🚨 A TRAVA QUE IMPORTA MAIS: situação que sai das 17 **sem** etapa de
    destino faz a OS desaparecer de TODAS as telas. É o M12 na sua forma mais
    cara, e nenhuma suíte reclamaria — o card simplesmente não estaria lá."""

    def test_toda_situacao_reenderecada_tem_etapa_que_a_recebe(self):
        destinos = {e["recebe_situacao"]
                    for e in pipeline.etapas_que_recebem()}
        faltam = sorted(set(REENDERECADAS) - destinos)
        assert faltam == [], f"situacao sem destino: {faltam}"

    def test_a_financeira_vai_para_NOVA_SOLICITACAO_do_Financeiro(self):
        """🔵 A frase dele nomeia a etapa: *"na etapa correta 'Nova
        solicitação'"*."""
        d = {e["recebe_situacao"]: e for e in pipeline.etapas_que_recebem()}
        assert d[15746]["codigo_tela"] == "PNL_1.4"
        assert d[15746]["titulo"] == "Nova solicitação"

    def test_a_de_pos_venda_vai_para_NOVA_SOLICITACAO_do_Pos_venda(self):
        d = {e["recebe_situacao"]: e for e in pipeline.etapas_que_recebem()}
        assert d[15695]["codigo_tela"] == "PNL_1.3"
        assert d[15695]["titulo"] == "Nova solicitação"

    def test_a_contratual_vai_para_a_PRIMEIRA_etapa_do_Contratual(self):
        """🔴 ESTA É A QUE ESPERA ELE: o Contratual **não tem** "Nova
        solicitação" — as seis colunas que ele escreveu começam em *Elaborar
        contrato*. Inventar uma coluna ali seria mexer numa lista dele, então
        a OS vai para a primeira. ⚠️ Se ele criar a "Nova solicitação" no
        Contratual, esta trava muda de alvo — e é esse o sinal de que a
        decisão foi tomada."""
        d = {e["recebe_situacao"]: e for e in pipeline.etapas_que_recebem()}
        assert d[16492]["codigo_tela"] == "PNL_1.5"
        primeira = banco.um(
            """SELECT e.id FROM pipeline_etapa e JOIN painel_aba a
                      ON a.id = e.aba_id
                WHERE a.codigo_tela = 'PNL_1.5' AND e.ativo
                ORDER BY e.ordem, e.id LIMIT 1""")
        assert d[16492]["id"] == primeira["id"]

    def test_uma_situacao_nao_pode_ter_DOIS_destinos(self):
        """🚨 O índice único é quem garante. Sem ele a mesma OS nasceria em
        dois painéis e ninguém saberia qual é o certo."""
        existe = banco.um(
            """SELECT 1 FROM pg_indexes
                WHERE indexname = 'idx_pipeline_etapa_recebe_unica'""")
        assert existe, "o indice unico da situacao nao existe"
        recebidas = [e["recebe_situacao"]
                     for e in pipeline.etapas_que_recebem()]
        assert len(recebidas) == len(set(recebidas))


class TestOFormularioDizOndeOCardNasce:
    def test_o_aditivo_tem_destino_no_CONTRATUAL(self):
        """🔵 *"fiz teste com form de aditivo e não abriu card no contratual
        como foi pedido"*."""
        d = formularios.etapa_de_destino("aditivo")
        assert d is not None, "o aditivo continua sem destino"
        assert d["painel"] == "contratual"
        assert d["codigo_tela"] == "PNL_1.5"

    def test_o_suporte_continua_indo_para_CHAMADOS(self):
        """⚠️ A exceção nomeada: o Suporte vai para a etapa nossa da Operação,
        como desde 29/10. A regra derivada acerta sozinha porque `Chamados` é
        a primeira etapa daquele painel."""
        d = formularios.etapa_de_destino("suporte")
        assert d["codigo_tela"] == "PNL_1.1"
        assert d["titulo"] == "Chamados"

    def test_as_duas_PESQUISAS_vao_para_Pos_venda_e_nao_Treinamentos(self):
        """🚨 O EMPATE QUE A REGRA DERIVADA ERROU: o painel Pós-venda tem duas
        abas, e *"a primeira por ordem"* entregava CES e NPS na fila de
        **Treinamentos**. Pesquisa não é treinamento. ⚠️ Derivação com empate
        precisa de desempate nomeado, não do acaso da `ordem`."""
        for codigo in ("ces", "nps"):
            d = formularios.etapa_de_destino(codigo)
            assert d["codigo_tela"] == "PNL_1.3", codigo

    def test_o_CONTATO_e_o_IDEIAS_vao_para_a_fila_do_Pos_venda(self):
        """🚨 ESTA TRAVA FOI INVERTIDA EM 12/11, e a inversão é o registro de
        uma decisão dele, não um conserto.

        Até 11/11 ela afirmava o contrário -- *"`None` não é defeito: o
        Contato e o IDEIAS não têm fila, e inventar uma os colocaria numa
        coluna que ninguém olha"*. 🔵 Em 12/11 ele decidiu: *"pode gerar card
        para Pós-venda"* e, sobre a etapa, *"isso, nova solicitação"*. A
        migração 108 é quem mudou o banco.

        ⚠️ Inverti em vez de apagar: sem trava, o destino podia voltar a ser
        nulo por descuido e ninguém veria -- o envio entraria na lista de
        Solicitações e não nasceria card em painel nenhum.
        """
        for codigo in ("contato", "ideias-sugestoes"):
            d = formularios.etapa_de_destino(codigo)
            assert d is not None, codigo
            assert d["codigo_tela"] == "PNL_1.3", codigo
            assert d["titulo"] == "Nova solicitação", codigo

    def test_o_IDEIAS_tem_destino_mesmo_DESLIGADO(self):
        """⚠️ Destino e interruptor são coisas separadas, e confundi-los seria
        o defeito: o `ideias-sugestoes` está `ativo = false` até ele ligar, e
        isso NÃO pode apagar o destino. Se apagasse, ligar o formulário um dia
        o faria nascer sem fila outra vez."""
        linha = banco.um(
            "SELECT ativo, painel, etapa_destino_id FROM formulario "
            " WHERE slug = %s", ("ideias-sugestoes",))
        assert linha["ativo"] is False, (
            "ligar o formulario e ato dele; se ja esta ligado, atualize esta trava")
        assert linha["painel"] == "pos_venda"
        assert linha["etapa_destino_id"] is not None

    def test_todo_formulario_COM_painel_tem_destino(self):
        """🚨 A trava simétrica: formulário com painel e sem destino é uma
        solicitação que chega e não entra em fila nenhuma — e o cliente já leu
        *"recebemos"*."""
        sem = []
        for r in banco.varios(
                """SELECT slug, painel FROM formulario
                    WHERE painel IS NOT NULL"""):
            if formularios.etapa_de_destino(r["slug"]) is None:
                sem.append(r["slug"])
        assert sem == [], f"formulario com painel e sem destino: {sem}"

    def test_destino_em_etapa_DESLIGADA_nao_conta(self):
        """⚠️ Nascer invisível é pior que não nascer: card em etapa desligada
        fica em `fora_do_quadro`, e ninguém o procura lá."""
        etapa = banco.um(
            """SELECT e.id FROM pipeline_etapa e JOIN formulario f
                      ON f.etapa_destino_id = e.id
                WHERE f.slug = 'aditivo'""")
        banco.executar("UPDATE pipeline_etapa SET ativo = false WHERE id = %s",
                       (etapa["id"],))
        try:
            assert formularios.etapa_de_destino("aditivo") is None
        finally:
            banco.executar(
                "UPDATE pipeline_etapa SET ativo = true WHERE id = %s",
                (etapa["id"],))
        assert formularios.etapa_de_destino("aditivo") is not None


class TestSemearNaoDuplicaNemRESSUSCITA:
    def _limpar(self, numero):
        banco.executar("DELETE FROM pipeline_card WHERE numero_os = %s",
                       (numero,))

    def test_semear_duas_vezes_cria_UM_card(self):
        """🚨 Duas pessoas abrindo o painel ao mesmo tempo é o caso comum."""
        numero = 999001
        self._limpar(numero)
        try:
            os_falsa = [{"numero_os": numero, "situacao_id": 15746,
                         "cliente_id": None}]
            assert pipeline.semear_os(os_falsa) == 1
            assert pipeline.semear_os(os_falsa) == 0
            quantos = banco.um(
                "SELECT count(*) c FROM pipeline_card WHERE numero_os = %s",
                (numero,))["c"]
            assert quantos == 1
        finally:
            self._limpar(numero)

    def test_card_JA_FINALIZADO_nao_renasce(self):
        """🚨 O índice único só vale para `desfecho IS NULL`: sem a guarda
        extra, uma OS já tratada voltaria a nascer a cada leitura da ponte --
        e a fila nunca esvaziaria."""
        numero = 999002
        self._limpar(numero)
        try:
            os_falsa = [{"numero_os": numero, "situacao_id": 15746,
                         "cliente_id": None}]
            pipeline.semear_os(os_falsa)
            banco.executar(
                """UPDATE pipeline_card SET desfecho = 'resolvido',
                          desfecho_em = now() WHERE numero_os = %s""",
                (numero,))
            assert pipeline.semear_os(os_falsa) == 0
            assert banco.um(
                "SELECT count(*) c FROM pipeline_card WHERE numero_os = %s",
                (numero,))["c"] == 1
        finally:
            self._limpar(numero)

    def test_situacao_SEM_destino_nao_semeia_nada(self):
        numero = 999003
        self._limpar(numero)
        try:
            assert pipeline.semear_os(
                [{"numero_os": numero, "situacao_id": 1316,
                  "cliente_id": None}]) == 0
        finally:
            self._limpar(numero)


class TestOQuadroDizAVERDADE:
    def test_OS_reenderecada_e_NOUTRO_PAINEL_e_nao_fora_do_quadro(self):
        """🚨 TELA QUE MENTE É DEFEITO (M12). `fora_do_quadro` avisa *"há OS
        que nenhuma coluna mostra"*; estas estão em outro painel, por decisão
        dele. Foi o primeiro efeito que a medição mostrou depois de tirar as
        três colunas, e o número estava certo pelo motivo errado."""
        q = paineis.quadro("operacao")
        assert "noutro_painel" in q["fora_do_quadro"]
        colunas = {c["titulo"] for c in q["colunas"]}
        assert "Financeiro" not in colunas

    def test_o_card_da_OS_mostra_o_NUMERO_DA_OS(self):
        """🚨 O card dizia *"Card 912"* -- um número NOSSO, que não serve para
        procurar nada no Harmonit. ⚠️ A chave é `numero_os` e **não**
        `numero_ordem`: é o `numero_ordem` nulo que mantém o card
        não-arrastável, e reusá-lo ligaria o arrasto para o ERP numa aba cujo
        mover escreve só no nosso banco."""
        numero = 999004
        banco.executar("DELETE FROM pipeline_card WHERE numero_os = %s",
                       (numero,))
        try:
            pipeline.semear_os([{"numero_os": numero, "situacao_id": 15746,
                                 "cliente_id": None}])
            q = paineis.quadro_da_aba("PNL_1.4")
            achado = [k for c in q["colunas"] for k in c["cards"]
                      if k.get("numero_os") == numero]
            assert len(achado) == 1, "o card nao apareceu com o numero da OS"
            assert achado[0]["numero_ordem"] is None
        finally:
            banco.executar("DELETE FROM pipeline_card WHERE numero_os = %s",
                           (numero,))


# ===========================================================================
# 🔵 12/11, dele sobre os formularios virarem card em todas as pipelines:
#     *"estao ok, mas nao percamos o rastreio desse dado"*.
#
# O rastreio e a cadeia  card -> solicitacao -> formulario  (pelo
# `pipeline_card.solicitacao_id`) ou, para card nascido de OS, o
# `pipeline_card.numero_os`. Um card sem nenhum dos dois e um card que
# ninguem sabe de onde veio -- e, pior, que ninguem sabe a quem responder.
#
# 🚨 NAO HA RESTRICAO NO BANCO que impeca isso: as duas colunas sao
# anulaveis, porque card de chamado nasce sem OS e card de OS nasce sem
# solicitacao. Quem guarda a regra "pelo menos um dos dois" e esta trava.
# ===========================================================================
class TestORastreioDaOrigemNaoSePerde:
    def test_todo_card_sabe_de_onde_veio(self):
        orfaos = banco.varios(
            """SELECT id, aba_id, etapa_id, criado_em
                 FROM pipeline_card
                WHERE solicitacao_id IS NULL
                  AND numero_os IS NULL
                ORDER BY id""")
        assert not orfaos, (
            "card sem origem: nem solicitacao nem OS -- "
            + ", ".join(str(c["id"]) for c in orfaos))

    def test_a_cadeia_ate_o_formulario_fecha(self):
        """Card com `solicitacao_id` tem de chegar a um formulario de verdade.

        ⚠️ Nao basta a coluna estar preenchida: se a solicitacao apontar para
        formulario apagado, o card continua "com origem" e a origem nao diz
        nada.
        """
        quebrados = banco.varios(
            """SELECT c.id
                 FROM pipeline_card c
                 LEFT JOIN formulario_solicitacao s ON s.id = c.solicitacao_id
                 LEFT JOIN formulario f ON f.id = s.formulario_id
                WHERE c.solicitacao_id IS NOT NULL
                  AND f.id IS NULL
                ORDER BY c.id""")
        assert not quebrados, (
            "card aponta para solicitacao que nao chega a formulario: "
            + ", ".join(str(c["id"]) for c in quebrados))

    def test_TODO_formulario_tem_para_onde_mandar_o_card(self):
        """🔵 12/11: *"a ideia e que os formularios virem cards em todas as
        pipelines e nao os mesmo"*.

        📏 Ate a migracao 108, `contato` e `ideias-sugestoes` tinham `painel` e
        `etapa_destino_id` NULOS: o envio entrava na lista de Solicitacoes e
        nao nascia card em painel nenhum. Esta trava e o que impede um
        formulario novo de nascer com o mesmo buraco.
        """
        sem_destino = banco.varios(
            """SELECT slug FROM formulario
                WHERE painel IS NULL OR etapa_destino_id IS NULL
                ORDER BY slug""")
        assert not sem_destino, (
            "formulario sem destino de card: "
            + ", ".join(f["slug"] for f in sem_destino))

    def test_o_destino_de_cada_formulario_e_uma_etapa_QUE_EXISTE(self):
        """Apontar para etapa apagada e pior que nao apontar: o envio tenta
        criar card, falha dentro do `try` que protege o cliente, e o card
        simplesmente nao nasce -- sem erro em lugar nenhum."""
        soltos = banco.varios(
            """SELECT f.slug, f.etapa_destino_id
                 FROM formulario f
                 LEFT JOIN pipeline_etapa e ON e.id = f.etapa_destino_id
                                           AND e.ativo
                WHERE f.etapa_destino_id IS NOT NULL
                  AND e.id IS NULL
                ORDER BY f.slug""")
        assert not soltos, (
            "formulario aponta para etapa inexistente ou desativada: "
            + ", ".join(f"{f['slug']}->{f['etapa_destino_id']}" for f in soltos))
