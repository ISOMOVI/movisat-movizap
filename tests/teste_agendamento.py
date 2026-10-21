"""Agendamento de serviço e a ponte com o FPSL — 21/10 (migração 069).

🚨 ESCREVE EM TABELAS DE PRODUÇÃO (`agendamento`, `agendamento_os`,
`orcamento`, `cliente`, `contato`, `conversa`, `atendente`), como o resto da
suíte. Tudo com marca própria (`Zz Teste Agendamento`, `harmonit_id` 9777xx,
OS 99xxxx) e tudo apagado no fim.

🚨 E NÃO ESCREVE NA `config`. A configuração da numeração chega por parâmetro,
nunca pela função que grava: foi um teste meu chamando `definir_config` que
desligou a distribuição por nove minutos em 19/10.

O que estes testes guardam:
  · uma OS não entra em dois compromissos ativos -- e cancelar devolve a OS;
  · cancelar PRESERVA o histórico (nada é apagado);
  · confirmar exige o nome de quem acompanha o técnico;
  · reagendar ESQUECE a confirmação (confirmação é de uma data, não do
    compromisso);
  · a sugestão de endereço é a do último uso daquele cliente;
  · 🚨 FPSL fora do ar devolve ERRO LEGÍVEL, nunca lista vazia -- vazio faria
    a tela dizer "este cliente não tem OS" e o operador agendaria por cima de
    serviço existente;
  · "em aberto" inclui `status_str` NULO (37 das 572 OS na base);
  · o cruzamento OS <-> cliente é pelo `harmonit_id`, que é TEXT aqui e INT
    no FPSL.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import agendamento, banco, fpsl_ponte, operacao  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

CLIENTE = "Zz Teste Agendamento"
LOGIN = "zz_teste_agd_"
# `harmonit_id` fora da faixa real (os de verdade têm 5 a 7 dígitos e existem
# no Harmonit); estes não casam com cliente nenhum.
HARMONIT_A = "97770001"
HARMONIT_B = "97770002"
# OS 99xxxx não existe na base do FPSL -- medido: os números reais vão até 17 mil.
OS_UM, OS_DOIS, OS_TRES = 997001, 997002, 997003


def limpar():
    banco.executar(
        """DELETE FROM agendamento_os WHERE agendamento_id IN
            (SELECT id FROM agendamento WHERE cliente_harmonit_id = ANY(%s))""",
        ([HARMONIT_A, HARMONIT_B],))
    banco.executar("DELETE FROM agendamento WHERE cliente_harmonit_id = ANY(%s)",
                   ([HARMONIT_A, HARMONIT_B],))
    banco.executar(
        """DELETE FROM orcamento WHERE criado_por IN
            (SELECT id FROM atendente WHERE login LIKE %s)""", (LOGIN + "%",))
    # 🚨 A CONVERSA SAI ANTES DO CONTATO, e pelo NOME DO CONTATO -- não pelo
    # cliente. O técnico é contato SEM cliente por desenho (07/10), então
    # limpar "conversas dos contatos daquele cliente" não alcança a dele, e o
    # DELETE do contato quebra na chave estrangeira. Achado por teste.
    banco.executar(
        """DELETE FROM conversa WHERE contato_id IN
            (SELECT id FROM contato WHERE nome LIKE %s)""", (CLIENTE + "%",))
    banco.executar(
        """DELETE FROM contato WHERE cliente_id IN
            (SELECT id FROM cliente WHERE nome LIKE %s)""", (CLIENTE + "%",))
    banco.executar("DELETE FROM contato WHERE nome LIKE %s", (CLIENTE + "%",))
    banco.executar("DELETE FROM cliente WHERE nome LIKE %s", (CLIENTE + "%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()

    pessoa = operacao.criar_atendente("Zz Agendamento", LOGIN + "1",
                                      LOGIN + "1@teste.invalid")
    with banco.cursor() as cur:
        # Cliente COM cadastro aqui e com `harmonit_id` -- a chave da ponte.
        cur.execute("""INSERT INTO cliente (nome, ativo, origem, harmonit_id)
                       VALUES (%s, true, 'movizap', %s) RETURNING id""",
                    (CLIENTE + " A", HARMONIT_A))
        cliente_a = cur.fetchone()["id"]
        # O técnico: contato SEM cliente, como é por desenho (07/10).
        cur.execute("""INSERT INTO contato (nome, relacao, origem, ativo)
                       VALUES (%s, 'tecnico', 'movizap', true) RETURNING id""",
                    (CLIENTE + " Tecnico",))
        tecnico = cur.fetchone()["id"]
        # `canal_id` é NOT NULL -- conversa sem canal não existe no produto.
        cur.execute("SELECT id FROM canal WHERE instancia = 'atendimento'")
        canal = cur.fetchone()
        if not canal:
            pytest.skip("canal atendimento não cadastrado")
        cur.execute("""INSERT INTO conversa (canal_id, contato_id, telefone_e164,
                                             estado, ultima_atividade_em, criada_em)
                       VALUES (%s, %s, %s, 'humano', now(), now()) RETURNING id""",
                    (canal["id"], tecnico, "+5518977779999"))
        conversa = cur.fetchone()["id"]

    yield {"atendente": pessoa["id"], "tecnico": tecnico,
           "conversa": conversa, "cliente_a": cliente_a}
    limpar()


def _criar(base, ordens, quando=None, cliente=HARMONIT_A, endereco="Rua Um, 100"):
    return agendamento.criar(
        conversa_id=base["conversa"],
        tecnico_contato_id=base["tecnico"],
        cliente_harmonit_id=cliente,
        cliente_nome=CLIENTE + " A",
        inicio=quando or (datetime.now(timezone.utc) + timedelta(days=1)),
        endereco=endereco,
        ordens=ordens,
        criado_por=base["atendente"],
    )


class TestUmaOsUmCompromisso:
    def test_a_mesma_os_nao_entra_em_dois_compromissos_ativos(self, base):
        _criar(base, [{"numero_os": OS_UM, "placa": "ABC1D23"}])
        with pytest.raises(agendamento.OsJaAgendada) as e:
            _criar(base, [{"numero_os": OS_UM, "placa": "ABC1D23"}])
        # A mensagem diz QUAL OS -- "já agendada" sem o número manda o
        # operador procurar nas outras.
        assert str(OS_UM) in str(e.value)

    def test_cancelar_devolve_a_os(self, base):
        a = _criar(base, [{"numero_os": OS_DOIS, "placa": None}])
        assert agendamento.os_ja_agendadas([OS_DOIS]) == [OS_DOIS]
        assert agendamento.cancelar(a, "cliente pediu outro dia")
        assert agendamento.os_ja_agendadas([OS_DOIS]) == []
        # E dá para agendar de novo, que é o ponto do cancelamento.
        _criar(base, [{"numero_os": OS_DOIS, "placa": None}])

    def test_cancelar_preserva_o_historico(self, base):
        a = _criar(base, [{"numero_os": OS_TRES, "placa": "XYZ9W87"}])
        agendamento.cancelar(a, "equipe sem técnico no dia")
        guardado = agendamento.por_id(a)
        assert guardado is not None, "cancelar não pode apagar o compromisso"
        assert guardado["estado"] == "cancelado"
        assert guardado["motivo_cancelamento"] == "equipe sem técnico no dia"
        assert guardado["cancelado_em"] is not None
        # As OS continuam penduradas: é o histórico do que foi cancelado.
        assert [o["numero_os"] for o in guardado["ordens"]] == [OS_TRES]

    def test_compromisso_sem_os_nao_e_compromisso(self, base):
        with pytest.raises(ValueError):
            _criar(base, [])


class TestConfirmacao:
    def test_confirmar_exige_quem_acompanha_o_tecnico(self, base):
        a = _criar(base, [{"numero_os": 997010, "placa": None}])
        with pytest.raises(ValueError):
            agendamento.confirmar(a, "   ")
        assert agendamento.por_id(a)["estado"] == "aguardando"

    def test_confirmar_grava_o_responsavel_e_a_hora(self, base):
        a = _criar(base, [{"numero_os": 997011, "placa": None}])
        assert agendamento.confirmar(a, "Dona Maria")
        guardado = agendamento.por_id(a)
        assert guardado["estado"] == "confirmado"
        assert guardado["responsavel_cliente"] == "Dona Maria"
        assert guardado["confirmado_em"] is not None

    def test_reagendar_esquece_a_confirmacao(self, base):
        """🚨 Confirmação é de uma DATA, não do compromisso."""
        a = _criar(base, [{"numero_os": 997012, "placa": None}])
        agendamento.confirmar(a, "Seu José")
        outro_dia = datetime.now(timezone.utc) + timedelta(days=5)
        assert agendamento.reagendar(a, outro_dia)
        guardado = agendamento.por_id(a)
        assert guardado["estado"] == "aguardando"
        assert guardado["responsavel_cliente"] is None
        assert guardado["confirmado_em"] is None

    def test_aguardando_do_cliente_so_traz_o_que_espera(self, base):
        esperando = _criar(base, [{"numero_os": 997013, "placa": None}])
        ja = _criar(base, [{"numero_os": 997014, "placa": None}])
        agendamento.confirmar(ja, "Alguém")
        ids = [a["id"] for a in agendamento.aguardando_do_cliente(HARMONIT_A)]
        assert esperando in ids
        assert ja not in ids


class TestEnderecoEConsulta:
    def test_sugestao_de_endereco_e_a_do_ultimo_uso(self, base):
        _criar(base, [{"numero_os": 997020, "placa": None}],
               cliente=HARMONIT_B, endereco="Avenida Antiga, 1")
        _criar(base, [{"numero_os": 997021, "placa": None}],
               cliente=HARMONIT_B, endereco="Travessa Nova, 2")
        assert agendamento.ultimo_endereco(HARMONIT_B) == "Travessa Nova, 2"

    def test_cliente_sem_agendamento_nao_tem_sugestao(self):
        assert agendamento.ultimo_endereco("97779999") is None

    def test_o_dia_traz_as_os_de_cada_compromisso(self, base):
        quando = datetime.now(timezone.utc) + timedelta(days=9)
        a = _criar(base, [{"numero_os": 997030, "placa": "AAA1A11"},
                          {"numero_os": 997031, "placa": "BBB2B22"}],
                   quando=quando)
        no_dia = [x for x in agendamento.do_dia(quando.date()) if x["id"] == a]
        assert len(no_dia) == 1
        assert [o["numero_os"] for o in no_dia[0]["ordens"]] == [997030, 997031]
        # O nome do técnico vem da junção -- a tela não faz segunda chamada.
        assert no_dia[0]["tecnico_nome"].startswith(CLIENTE)

    def test_o_periodo_cobre_o_carrossel_da_semana(self, base):
        hoje = datetime.now(timezone.utc)
        a = _criar(base, [{"numero_os": 997040, "placa": None}],
                   quando=hoje + timedelta(days=3))
        ids = [x["id"] for x in agendamento.do_periodo(
            (hoje - timedelta(days=1)).date(), (hoje + timedelta(days=5)).date())]
        assert a in ids


class TestEscritaNoHarmonit:
    """🔵 Ligada por decisão dele em 21/10, depois do relatório da OS 16991.

    🚨 NENHUM DESTES TESTES FALA COM O HARMONIT. O que se protege é o
    comportamento do lado de cá: a recusa não derruba o compromisso, o rastro
    fica legível, e o interruptor chega por parâmetro — nunca lendo nem
    escrevendo na `config` de produção.
    """

    def test_desligado_nao_chama_nada(self, base, monkeypatch):
        def nao_deveria(**kwargs):
            raise AssertionError("chamou o Harmonit com o interruptor desligado")

        monkeypatch.setattr(agendamento.fpsl_ponte, "agendar_tecnico", nao_deveria)
        a = _criar(base, [{"numero_os": 997050, "placa": None}])
        r = agendamento.levar_ao_harmonit(
            a, cfg={"agendamento_escreve_harmonit": "false"})
        assert r == {"ligado": False, "resultados": []}

    def test_a_config_chega_por_PARAMETRO(self, base):
        """🚨 A régua de 19/10: teste não lê nem escreve a config real."""
        assert agendamento.escreve_no_harmonit(
            cfg={"agendamento_escreve_harmonit": "true"}) is True
        assert agendamento.escreve_no_harmonit(
            cfg={"agendamento_escreve_harmonit": "false"}) is False
        assert agendamento.escreve_no_harmonit(cfg={}) is False

    def test_uma_chamada_POR_OS(self, base, monkeypatch):
        """Do lado de lá cada OS tem o seu técnico e o seu compromisso."""
        chamadas = []

        def fingir(**kwargs):
            chamadas.append(kwargs)
            return {"ok": True, "numero_os": kwargs["numero_os"],
                    "agendamento_id": 900000 + len(chamadas)}

        monkeypatch.setattr(agendamento.fpsl_ponte, "agendar_tecnico", fingir)
        a = _criar(base, [{"numero_os": 997060, "placa": None},
                          {"numero_os": 997061, "placa": None}])
        r = agendamento.levar_ao_harmonit(
            a, cfg={"agendamento_escreve_harmonit": "true"})
        assert r["quantas_foram"] == 2
        assert sorted(c["numero_os"] for c in chamadas) == [997060, 997061]
        # O nome do técnico vai junto: é o único elo com o usuário do Harmonit.
        assert all("tecnico_nome" in c for c in chamadas)

    def test_recusa_do_harmonit_NAO_derruba_o_compromisso(self, base, monkeypatch):
        """🚨 O MoviZap é o dono (decisão 7 dele)."""
        monkeypatch.setattr(
            agendamento.fpsl_ponte, "agendar_tecnico",
            lambda **k: {"ok": False, "numero_os": k["numero_os"],
                         "motivo": "TecnicoJaAgendado"})
        a = _criar(base, [{"numero_os": 997070, "placa": None}])
        r = agendamento.levar_ao_harmonit(
            a, cfg={"agendamento_escreve_harmonit": "true"})
        assert r["quantas_foram"] == 0
        guardado = agendamento.por_id(a)
        # O compromisso continua de pé...
        assert guardado["estado"] == "aguardando"
        # ...e o motivo fica GRAVADO, dizendo em qual OS.
        assert "997070" in guardado["harmonit_erro"]
        assert "TecnicoJaAgendado" in guardado["harmonit_erro"]
        assert guardado["harmonit_agendamento_id"] is None
        assert guardado["harmonit_em"] is None

    def test_sucesso_grava_o_id_e_a_hora(self, base, monkeypatch):
        monkeypatch.setattr(
            agendamento.fpsl_ponte, "agendar_tecnico",
            lambda **k: {"ok": True, "numero_os": k["numero_os"],
                         "agendamento_id": 944780})
        a = _criar(base, [{"numero_os": 997080, "placa": None}])
        agendamento.levar_ao_harmonit(
            a, cfg={"agendamento_escreve_harmonit": "true"})
        guardado = agendamento.por_id(a)
        assert guardado["harmonit_agendamento_id"] == 944780
        assert guardado["harmonit_em"] is not None
        assert guardado["harmonit_erro"] is None

    def test_ponte_fora_do_ar_vira_MOTIVO_e_nao_excecao(self, monkeypatch):
        """🚨 Agendar não pode estourar porque o FPSL caiu.

        Aqui a diferença com a LEITURA é de propósito: ler devolvendo lista
        vazia mentiria ("este cliente não tem OS"), então a leitura estoura.
        Escrever não tem esse risco -- o compromisso já está gravado aqui --,
        e o que interessa é registrar o motivo.
        """
        import httpx

        def cai(*a, **k):
            raise httpx.ConnectError("sem rota")

        monkeypatch.setattr(fpsl_ponte.httpx, "post", cai)
        r = fpsl_ponte.agendar_tecnico(
            numero_os=16991, inicio=datetime.now(timezone.utc), tecnico_nome="X")
        assert r["ok"] is False
        assert "FPSL" in r["motivo"]


class TestPonteComOFpsl:
    def test_fpsl_fora_do_ar_estoura_em_vez_de_devolver_vazio(self, monkeypatch):
        """🚨 O teste que justifica o módulo existir."""
        import httpx

        def cai(*a, **k):
            raise httpx.ConnectError("sem rota")

        monkeypatch.setattr(fpsl_ponte.httpx, "get", cai)
        with pytest.raises(fpsl_ponte.FpslIndisponivel):
            fpsl_ponte.os_do_cliente("998063")
        with pytest.raises(fpsl_ponte.FpslIndisponivel):
            fpsl_ponte.clientes_com_os()

    def test_timeout_tambem_estoura(self, monkeypatch):
        import httpx

        def demora(*a, **k):
            raise httpx.TimeoutException("demorou")

        monkeypatch.setattr(fpsl_ponte.httpx, "get", demora)
        with pytest.raises(fpsl_ponte.FpslIndisponivel) as e:
            fpsl_ponte.os_do_cliente("998063")
        assert "tempo" in str(e.value)

    def test_chave_recusada_diz_o_que_conferir(self, monkeypatch):
        monkeypatch.setattr(
            fpsl_ponte.httpx, "get",
            lambda *a, **k: httpx_resposta(401))
        with pytest.raises(fpsl_ponte.FpslIndisponivel) as e:
            fpsl_ponte.clientes_com_os()
        assert ".env" in str(e.value)

    def test_ponte_desligada_nao_finge_resposta(self, monkeypatch):
        monkeypatch.setattr(fpsl_ponte.settings, "ponte_fpsl_segredo", "")
        assert fpsl_ponte.configurada() is False
        with pytest.raises(fpsl_ponte.FpslIndisponivel):
            fpsl_ponte.clientes_com_os()

    def test_cliente_sem_harmonit_id_e_ausencia_de_vinculo(self, monkeypatch):
        """Não é falha de ponte: é cliente que não existe no Harmonit."""
        def nao_deveria_chamar(*a, **k):
            raise AssertionError("não devia ter ido à rede")

        monkeypatch.setattr(fpsl_ponte.httpx, "get", nao_deveria_chamar)
        assert fpsl_ponte.os_do_cliente(None) == []
        assert fpsl_ponte.os_do_cliente("") == []

    def test_a_contagem_volta_com_a_chave_em_TEXTO(self, monkeypatch):
        """O FPSL manda int; o `cliente.harmonit_id` deste lado é text."""
        monkeypatch.setattr(
            fpsl_ponte.httpx, "get",
            lambda *a, **k: httpx_resposta(
                200, {"clientes": [{"cliente_id": 998063, "quantas": 17}]}))
        assert fpsl_ponte.clientes_com_os() == {"998063": 17}


def httpx_resposta(codigo: int, corpo: dict | None = None):
    """Uma resposta do httpx montada à mão, sem rede."""
    import httpx
    return httpx.Response(codigo, json=corpo if corpo is not None else {})


class TestPonteAoVivo:
    """🚨 ESTES FALAM COM O FPSL DE VERDADE, em 127.0.0.1. Leitura só.

    Base: a Pastelaria Velasco, cliente Harmonit **998063** — a empresa de
    teste oficial, 18 OS medidas em 21/10.
    """

    def test_a_velasco_tem_os_em_aberto(self):
        try:
            lista = fpsl_ponte.os_do_cliente("998063", meses=12)
        except fpsl_ponte.FpslIndisponivel as e:
            pytest.skip(f"FPSL fora do ar agora: {e}")
        assert lista, "a Velasco tinha 17 OS abertas em 21/10"
        uma = lista[0]
        assert {"numero_os", "tipo", "status_str", "sem_situacao",
                "data_previsao", "veiculos"} <= set(uma)

    def test_status_nulo_entra_na_lista_como_sem_situacao(self):
        """⚠️ Nulo NÃO é finalizado: 37 das 572 OS da base estão assim."""
        try:
            contagem = fpsl_ponte.clientes_com_os(meses=60)
        except fpsl_ponte.FpslIndisponivel as e:
            pytest.skip(f"FPSL fora do ar agora: {e}")
        assert contagem, "a base tinha 96 clientes com OS aberta em 6 meses"
        # Alguma OS da base tem de vir marcada como sem situação -- se o filtro
        # voltar a usar `status_str <> 'Finalizado'` sozinho, elas somem.
        achou = False
        for harmonit_id in list(contagem)[:12]:
            for o in fpsl_ponte.os_do_cliente(harmonit_id, meses=60):
                achou = achou or o["sem_situacao"]
        assert achou, "nenhuma OS sem situação voltou -- o filtro sumiu com as nulas"
