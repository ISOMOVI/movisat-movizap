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

# 🚨 A TRAVA DO TÉCNICO (casar pelo e-mail) MORA NO FPSL, e o teste dela mora
# lá: `fpsl_weso/tests/teste_ponte_movizap.py`. Importar aquele pacote daqui
# quebra em `pydantic_settings` -- são dois projetos e dois venvs.

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


def _dia_do_banco(quando):
    """O dia que o BANCO vai reportar para este instante.

    🚨 `do_dia` compara `a.inicio::date`, e o Postgres resolve esse cast no
    fuso da sessão (`America/Sao_Paulo`), não em UTC. Perguntar a data com
    `datetime.now(timezone.utc).date()` fazia este teste reprovar **das 21h à
    meia-noite** -- três horas por dia em que a data UTC já virou e a do banco
    não. Medido em 11/11 às 21:21 BRT (00:21 UTC).

    ⚠️ Não é cálculo de fuso escrito à mão: quem responde é o próprio banco,
    com o mesmo cast que a consulta usa. Se o fuso da sessão mudar, o teste
    acompanha sozinho.
    """
    return banco.um("SELECT %s::timestamptz::date AS d", (quando,))["d"]


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
        # 🚨 O dia vem do BANCO, não de UTC -- ver `_dia_do_banco`.
        no_dia = [x for x in agendamento.do_dia(_dia_do_banco(quando))
                  if x["id"] == a]
        assert len(no_dia) == 1
        assert [o["numero_os"] for o in no_dia[0]["ordens"]] == [997030, 997031]
        # O nome do técnico vem da junção -- a tela não faz segunda chamada.
        assert no_dia[0]["tecnico_nome"].startswith(CLIENTE)

    def test_o_dia_e_o_do_BANCO_e_nao_o_de_UTC(self, base):
        """🚨 A trava que guarda o defeito de 11/11.

        `a.inicio::date` é resolvido no fuso da sessão do Postgres. Entre 21h e
        meia-noite (BRT) a data UTC está um dia à frente, e perguntar em UTC
        devolve lista vazia. Esta trava prova que a consulta e a pergunta usam
        o MESMO calendário -- o do banco.

        ⚠️ Ela não finge um horário: ela confere a identidade que tem de valer
        a qualquer hora, e nas três horas da janela ela reprova se alguém
        voltar a perguntar em UTC.
        """
        quando = datetime.now(timezone.utc) + timedelta(days=11)
        a = _criar(base, [{"numero_os": 997035, "placa": None}], quando=quando)
        dia = _dia_do_banco(quando)
        assert [x["id"] for x in agendamento.do_dia(dia) if x["id"] == a] == [a]
        # E o compromisso está no período que contém esse dia.
        ids = [x["id"] for x in agendamento.do_periodo(dia, dia)]
        assert a in ids, "do_dia e do_periodo têm de concordar sobre o dia"

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
        # 🔵 21/10: o que casa é o TELEFONE do contato (o e-mail do técnico no
        # Harmonit é o telefone dele). O nome vai junto só para a recusa ser
        # legível -- ele NÃO valida nada.
        assert all("tecnico_telefone" in c for c in chamadas)
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
        # ⚠️ ESTA TRAVA MUDOU DE TEXTO EM 11/11, E NÃO DE REGRA. A frase
        # passou a nomear o teto e a dizer quem costuma ser a causa -- antes
        # dizia "o FPSL não respondeu no tempo", culpando a peça errada.
        assert "tempo" in str(e.value)
        assert "20s" in str(e.value), "a frase tem de nomear o teto"
        assert "Harmonit" in str(e.value)

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


class TestCancelarEReagendarNoHarmonit:
    """🔵 Demanda dele, 18/11. 🚨 NENHUM DESTES TESTES FALA COM O HARMONIT.

    O que a medição na Velasco (OS 17105) decidiu, e é o que estes testes
    guardam: o ERP **não tem alteração** de compromisso, o único caminho é o
    `DELETE`, e o `DELETE` leva **o compromisso E a linha do técnico** juntos.
    Logo 🔵 *"apaga, só se a linha for nossa"*.
    """

    def _rastro(self, agendamento_id, numero_os, *, vinculo_criado,
                compromisso=944000, vinculo=1199999):
        """Finge o que a migração 112 guarda quando o agendar dá certo."""
        banco.executar(
            "UPDATE agendamento_os "
            "   SET harmonit_agendamento_id = %s, harmonit_vinculo_id = %s, "
            "       vinculo_criado = %s, harmonit_em = now() "
            " WHERE agendamento_id = %s AND numero_os = %s",
            (compromisso, vinculo, vinculo_criado, agendamento_id, numero_os))

    def _lido(self, agendamento_id, numero_os):
        return banco.um(
            "SELECT harmonit_agendamento_id, harmonit_vinculo_id, "
            "       vinculo_criado FROM agendamento_os "
            " WHERE agendamento_id = %s AND numero_os = %s",
            (agendamento_id, numero_os))

    # -- o rastro ----------------------------------------------------------
    def test_o_agendar_GRAVA_o_vinculo_por_OS(self, base, monkeypatch):
        """🚨 Sem este elo, cancelar não existe: é o campo que diz se apagar é
        seguro. ⚠️ E é POR OS, não por compromisso -- um compromisso do
        MoviZap cobre várias OS e cada uma tem a sua linha lá."""
        def fingir(**k):
            return {"ok": True, "numero_os": k["numero_os"],
                    "agendamento_id": 944100 + k["numero_os"] % 10,
                    "vinculo_id": 1199000 + k["numero_os"] % 10,
                    "vinculo_criado": True}

        monkeypatch.setattr(agendamento.fpsl_ponte, "agendar_tecnico", fingir)
        a = _criar(base, [{"numero_os": 997101, "placa": None},
                          {"numero_os": 997102, "placa": None}])
        agendamento.levar_ao_harmonit(
            a, cfg={"agendamento_escreve_harmonit": "true"})
        um = self._lido(a, 997101)
        dois = self._lido(a, 997102)
        assert um["harmonit_agendamento_id"] == 944101
        assert um["harmonit_vinculo_id"] == 1199001
        assert um["vinculo_criado"] is True
        # 🚨 Ids DIFERENTES por OS: era isto que a coluna de 070 não podia
        # guardar, porque ela é uma só para o compromisso inteiro.
        assert dois["harmonit_agendamento_id"] == 944102
        assert dois["harmonit_vinculo_id"] == 1199002

    def test_recusa_NAO_grava_rastro(self, base, monkeypatch):
        """⚠️ Rastro de escrita que não aconteceu faria cancelar apontar para
        uma linha que não é nossa."""
        monkeypatch.setattr(
            agendamento.fpsl_ponte, "agendar_tecnico",
            lambda **k: {"ok": False, "numero_os": k["numero_os"],
                         "motivo": "recusou (encenado)"})
        a = _criar(base, [{"numero_os": 997110, "placa": None}])
        agendamento.levar_ao_harmonit(
            a, cfg={"agendamento_escreve_harmonit": "true"})
        assert self._lido(a, 997110)["harmonit_vinculo_id"] is None

    # -- cancelar ----------------------------------------------------------
    def test_cancelar_LEVA_AO_ERP_quando_a_linha_e_nossa(self, base,
                                                         monkeypatch):
        chamadas = []

        def fingir(**k):
            chamadas.append(k)
            return {"ok": True, "apagou": True, "numero_os": k["numero_os"]}

        monkeypatch.setattr(agendamento.fpsl_ponte, "cancelar_agendamento",
                            fingir)
        a = _criar(base, [{"numero_os": 997120, "placa": None}])
        self._rastro(a, 997120, vinculo_criado=True)
        assert agendamento.cancelar(
            a, "cliente desmarcou",
            cfg={"agendamento_escreve_harmonit": "true"}) is True
        assert len(chamadas) == 1
        assert chamadas[0]["numero_os"] == 997120
        assert chamadas[0]["vinculo_id"] == 1199999
        assert chamadas[0]["vinculo_criado"] is True
        # 🚨 O rastro é LIMPO: a linha não está mais lá, e deixar o id faria
        # uma segunda tentativa apagar o que já não existe.
        assert self._lido(a, 997120)["harmonit_vinculo_id"] is None
        # ...e o histórico deste lado fica, como sempre foi.
        assert agendamento.por_id(a)["estado"] == "cancelado"
        assert agendamento.por_id(a)["motivo_cancelamento"] == "cliente desmarcou"

    def test_cancelar_com_linha_DE_OUTRO_recusa_e_fica_LEGIVEL(self, base,
                                                               monkeypatch):
        """🔵 *"apaga, só se a linha for nossa"*. ⚠️ E o compromisso continua
        cancelado DESTE lado: o operador já desmarcou com o cliente."""
        monkeypatch.setattr(
            agendamento.fpsl_ponte, "cancelar_agendamento",
            lambda **k: {"ok": False, "apagou": False,
                         "numero_os": k["numero_os"],
                         "causa": "vinculo_nao_e_nosso",
                         "motivo": "a linha nao foi criada por nos"})
        a = _criar(base, [{"numero_os": 997130, "placa": None}])
        self._rastro(a, 997130, vinculo_criado=False)
        assert agendamento.cancelar(
            a, "", cfg={"agendamento_escreve_harmonit": "true"}) is True
        guardado = agendamento.por_id(a)
        assert guardado["estado"] == "cancelado"
        # 🔵 Pendência 4 dele: o motivo aparece DESCRITO, e dizendo em qual OS.
        assert "997130" in guardado["harmonit_erro"]
        assert "não criamos" in guardado["harmonit_erro"]
        # 🚨 E o rastro NÃO é limpo: a linha continua lá no Harmonit.
        assert self._lido(a, 997130)["harmonit_vinculo_id"] == 1199999

    def test_rastro_NULO_conta_como_nao_e_nossa(self, base, monkeypatch):
        """🚨 O caso das linhas que já existiam antes da migração 112: não se
        sabe quem criou, e quem não sabe não apaga."""
        vistos = []
        monkeypatch.setattr(
            agendamento.fpsl_ponte, "cancelar_agendamento",
            lambda **k: vistos.append(k) or {"ok": False, "apagou": False,
                                             "numero_os": k["numero_os"],
                                             "causa": "vinculo_nao_e_nosso",
                                             "motivo": "nao e nossa"})
        a = _criar(base, [{"numero_os": 997140, "placa": None}])
        self._rastro(a, 997140, vinculo_criado=None)
        agendamento.cancelar(a, "", cfg={"agendamento_escreve_harmonit": "true"})
        assert vistos and vistos[0]["vinculo_criado"] is False

    def test_cancelar_DESLIGADO_nao_chama_nada(self, base, monkeypatch):
        def nao_deveria(**k):
            raise AssertionError("chamou o Harmonit com o interruptor desligado")

        monkeypatch.setattr(agendamento.fpsl_ponte, "cancelar_agendamento",
                            nao_deveria)
        a = _criar(base, [{"numero_os": 997150, "placa": None}])
        self._rastro(a, 997150, vinculo_criado=True)
        assert agendamento.cancelar(
            a, "", cfg={"agendamento_escreve_harmonit": "false"}) is True
        assert agendamento.por_id(a)["estado"] == "cancelado"

    def test_cancelar_SEM_RASTRO_nao_chama_nada(self, base, monkeypatch):
        """⚠️ Sem `harmonit_vinculo_id` não há o que apagar lá, e inventar um
        id seria apontar para a linha de outra pessoa."""
        def nao_deveria(**k):
            raise AssertionError("chamou o Harmonit sem saber qual linha")

        monkeypatch.setattr(agendamento.fpsl_ponte, "cancelar_agendamento",
                            nao_deveria)
        a = _criar(base, [{"numero_os": 997160, "placa": None}])
        assert agendamento.cancelar(
            a, "", cfg={"agendamento_escreve_harmonit": "true"}) is True

    # -- reagendar ---------------------------------------------------------
    def test_reagendar_APONTA_O_RASTRO_para_o_compromisso_novo(self, base,
                                                               monkeypatch):
        chamadas = []

        def fingir(**k):
            chamadas.append(k)
            return {"ok": True, "reagendou": True, "apagou_o_antigo": True,
                    "numero_os": k["numero_os"], "agendamento_id": 977000,
                    "vinculo_id": 1177777, "vinculo_criado": True}

        monkeypatch.setattr(agendamento.fpsl_ponte, "reagendar_tecnico",
                            fingir)
        a = _criar(base, [{"numero_os": 997170, "placa": None}])
        self._rastro(a, 997170, vinculo_criado=True)
        nova = datetime.now(timezone.utc) + timedelta(days=9)
        assert agendamento.reagendar(
            a, nova, cfg={"agendamento_escreve_harmonit": "true"}) is True
        # 🚨 Mandou o ANTIGO para apagar e o novo para criar, na mesma chamada.
        assert chamadas[0]["agendamento_id_antigo"] == 944000
        assert chamadas[0]["vinculo_id_antigo"] == 1199999
        guardado = self._lido(a, 997170)
        assert guardado["harmonit_agendamento_id"] == 977000
        assert guardado["harmonit_vinculo_id"] == 1177777
        # ⚠️ E a confirmação foi esquecida, como já era a regra.
        assert agendamento.por_id(a)["estado"] == "aguardando"
        assert agendamento.por_id(a)["confirmado_em"] is None

    def test_antigo_que_NAO_SAIU_fica_dito_e_nao_derruba_o_novo(self, base,
                                                                monkeypatch):
        """🚨 Nunca zero compromisso. A OS fica com dois, e a frase diz qual
        não saiu -- errar para o lado do excesso é recuperável."""
        monkeypatch.setattr(
            agendamento.fpsl_ponte, "reagendar_tecnico",
            lambda **k: {"ok": True, "reagendou": True,
                         "apagou_o_antigo": False,
                         "numero_os": k["numero_os"],
                         "agendamento_id": 977001, "vinculo_id": 1177778,
                         "vinculo_criado": True,
                         "causa_do_antigo": "recusa_do_erp",
                         "motivo": "o antigo (944000) NAO saiu da OS"})
        a = _criar(base, [{"numero_os": 997180, "placa": None}])
        self._rastro(a, 997180, vinculo_criado=True)
        nova = datetime.now(timezone.utc) + timedelta(days=10)
        assert agendamento.reagendar(
            a, nova, cfg={"agendamento_escreve_harmonit": "true"}) is True
        # O rastro aponta o NOVO (é ele que vale para cancelar daqui em diante)
        assert self._lido(a, 997180)["harmonit_agendamento_id"] == 977001
        # ...e o que sobrou está escrito, com a OS.
        erro = agendamento.por_id(a)["harmonit_erro"]
        assert "997180" in erro and "944000" in erro

    def test_reagendar_DESLIGADO_so_muda_a_data_daqui(self, base, monkeypatch):
        def nao_deveria(**k):
            raise AssertionError("chamou o Harmonit com o interruptor desligado")

        monkeypatch.setattr(agendamento.fpsl_ponte, "reagendar_tecnico",
                            nao_deveria)
        a = _criar(base, [{"numero_os": 997190, "placa": None}])
        self._rastro(a, 997190, vinculo_criado=True)
        nova = datetime.now(timezone.utc) + timedelta(days=11)
        assert agendamento.reagendar(
            a, nova, cfg={"agendamento_escreve_harmonit": "false"}) is True
        assert self._lido(a, 997190)["harmonit_agendamento_id"] == 944000

    def test_reagendar_LE_O_RASTRO_ANTES_de_mudar_a_data(self):
        """🚨 Trava por texto, e o que ela guarda é uma ordem que nenhum dublê
        pega: o rastro tem de ser lido ANTES do UPDATE da data. Se fosse
        depois, o reagendar ainda funcionaria -- e é por isso que precisa de
        trava."""
        import inspect
        fonte = inspect.getsource(agendamento.reagendar)
        assert fonte.index("_rastro_no_harmonit") < fonte.index("UPDATE agendamento SET inicio")
