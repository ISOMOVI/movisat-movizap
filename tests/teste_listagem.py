"""Regressão da listagem — escrito ANTES de mexer no `WHERE` dela.

🚨 `listar()` alimenta a caixa de entrada, que é a tela que a operação usa todo
dia. O E4 vai fazer ela incluir conversas onde sou PARTICIPANTE, e isso mexe
justamente no filtro por dono. Estes testes fixam o comportamento atual: se a
mudança quebrar qualquer um, quebrou a tela de quem trabalha.

Roda antes e depois. Antes, tem que passar — senão o teste está errado, não o
código.
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

FONE_DONO = "+5599933330001"
FONE_OUTRO = "+5599933330002"
FONE_ORFA = "+5599933330003"
LOGIN = "zz_reg_listar_"


def limpar():
    for f in (FONE_DONO, FONE_OUTRO, FONE_ORFA):
        banco.executar("DELETE FROM conversa_participante WHERE conversa_id IN "
                       "(SELECT id FROM conversa WHERE telefone_e164 = %s)", (f,))
        banco.executar("DELETE FROM mensagem WHERE conversa_id IN "
                       "(SELECT id FROM conversa WHERE telefone_e164 = %s)", (f,))
        banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (f,))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def cena():
    limpar()
    canal = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not canal:
        pytest.skip("canal atendimento não cadastrado")
    eu = banco.um("""INSERT INTO atendente (nome, login, senha_hash, perfil, ativo)
                     VALUES ('Reg eu', %s, 'x', 'atendimento', true)
                     RETURNING id""", (LOGIN + "eu",))["id"]
    outro = banco.um("""INSERT INTO atendente (nome, login, senha_hash, perfil, ativo)
                        VALUES ('Reg outro', %s, 'x', 'atendimento', true)
                        RETURNING id""", (LOGIN + "outro",))["id"]

    def nova(fone, dono):
        return banco.um(
            """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (canal["id"], fone, "humano" if dono else "nova", dono))["id"]

    dados = {"eu": eu, "outro": outro,
             "minha": nova(FONE_DONO, eu),
             "dele": nova(FONE_OUTRO, outro),
             "orfa": nova(FONE_ORFA, None)}
    yield dados
    limpar()


def ids(linhas):
    return {x["id"] for x in linhas}


def entrada(conversa_id, sufixo):
    """Insere uma mensagem de CLIENTE (`direcao='entrada'`) na conversa."""
    banco.executar(
        """INSERT INTO mensagem (conversa_id, id_externo, direcao, autor,
                                 tipo, conteudo, criada_em)
           VALUES (%s, %s, 'entrada', 'cliente', 'texto', 'oi', now())""",
        (conversa_id, f"{LOGIN}{sufixo}"))


class TestListagemDoDono:
    def test_minhas_conversas_traz_so_as_minhas(self, cena):
        r = ids(conversas.listar(atendente_id=cena["eu"], limite=500))
        assert cena["minha"] in r
        assert cena["dele"] not in r, "vazou conversa de outro atendente"
        assert cena["orfa"] not in r, "conversa sem dono apareceu como minha"

    def test_sem_dono_traz_so_as_orfas(self, cena):
        r = ids(conversas.listar(sem_dono=True, limite=500))
        assert cena["orfa"] in r
        assert cena["minha"] not in r
        assert cena["dele"] not in r

    def test_sem_filtro_traz_todas(self, cena):
        r = ids(conversas.listar(limite=500))
        assert {cena["minha"], cena["dele"], cena["orfa"]} <= r

    def test_filtro_por_estado_continua_valendo(self, cena):
        r = ids(conversas.listar(estado="humano", limite=500))
        assert cena["minha"] in r and cena["dele"] in r
        assert cena["orfa"] not in r

    def test_busca_por_telefone_acha_a_conversa(self, cena):
        r = ids(conversas.listar(busca=FONE_DONO, limite=500))
        assert r == {cena["minha"]}

    def test_dono_e_estado_juntos(self, cena):
        r = ids(conversas.listar(estado="humano", atendente_id=cena["eu"], limite=500))
        assert r == {cena["minha"]}

    def test_a_linha_traz_os_campos_que_a_tela_usa(self, cena):
        linha = next(x for x in conversas.listar(atendente_id=cena["eu"], limite=500)
                     if x["id"] == cena["minha"])
        for campo in ("id", "estado", "telefone_e164", "contato_id", "canal_id",
                      "ultima_atividade_em", "atendente_id", "atendente_nome"):
            assert campo in linha, f"a tela perdeu o campo {campo}"


class TestListagemDoParticipante:
    """O comportamento NOVO do E4: quem foi convidado vê a conversa.

    🚨 Era exatamente para isto que o convite servia. Sem esta parte, a
    migração 021 grava linha que ninguém lê.
    """

    def test_convidado_ve_a_conversa_na_lista_dele(self, cena):
        antes = ids(conversas.listar(atendente_id=cena["outro"], limite=500))
        assert cena["minha"] not in antes

        conversas.convidar(cena["minha"], cena["outro"], cena["eu"])
        depois = ids(conversas.listar(atendente_id=cena["outro"], limite=500))
        assert cena["minha"] in depois, "o convidado não vê a conversa"

    def test_a_linha_diz_que_e_acompanhamento_e_nao_posse(self, cena):
        """Sem este campo a caixa de entrada misturaria 'minha' com 'fui
        chamado', e o atendente não saberia por qual ele responde.

        🚨 `visualizador_id` vai junto com `atendente_id` nas duas chamadas --
        é o que `main.py` faz quando `minhas=True` (o próprio filtro É o
        viewer). Ver `TestNaoLidas`, que testa os dois separados.
        """
        conversas.convidar(cena["minha"], cena["outro"], cena["eu"])

        do_convidado = next(x for x in conversas.listar(
            atendente_id=cena["outro"], visualizador_id=cena["outro"], limite=500)
                            if x["id"] == cena["minha"])
        assert do_convidado["acompanho"] is True
        assert do_convidado["atendente_id"] == cena["eu"], "o dono mudou sozinho"

        do_dono = next(x for x in conversas.listar(
            atendente_id=cena["eu"], visualizador_id=cena["eu"], limite=500)
                       if x["id"] == cena["minha"])
        assert do_dono["acompanho"] is False, "o dono apareceu como acompanhante"

    def test_quem_sai_deixa_de_ver(self, cena):
        conversas.convidar(cena["minha"], cena["outro"], cena["eu"])
        conversas.sair(cena["minha"], cena["outro"])
        assert cena["minha"] not in ids(
            conversas.listar(atendente_id=cena["outro"], limite=500))

    def test_convidar_nao_tira_a_conversa_do_dono(self, cena):
        # Decisão do usuário: convidar não muda quem responde pela conversa.
        conversas.convidar(cena["minha"], cena["outro"], cena["eu"])
        assert cena["minha"] in ids(
            conversas.listar(atendente_id=cena["eu"], limite=500))

    def test_convidar_nao_mexe_na_lista_de_sem_dono(self, cena):
        conversas.convidar(cena["orfa"], cena["outro"], cena["eu"])
        r = ids(conversas.listar(sem_dono=True, limite=500))
        assert cena["orfa"] in r, "a órfã sumiu da fila por causa de um convite"

    def test_sem_atendente_id_o_campo_acompanho_e_falso(self, cena):
        # A listagem geral não tem "eu" — o campo não pode inventar dono.
        conversas.convidar(cena["minha"], cena["outro"], cena["eu"])
        linha = next(x for x in conversas.listar(limite=500)
                     if x["id"] == cena["minha"])
        assert linha["acompanho"] is False

    def test_o_dono_que_herdou_aparece_como_dono_e_nao_participante(self, cena):
        conversas.convidar(cena["minha"], cena["outro"], cena["eu"])
        conversas.sair(cena["minha"], cena["eu"])   # o dono sai, `outro` herda
        linha = next(x for x in conversas.listar(
            atendente_id=cena["outro"], visualizador_id=cena["outro"], limite=500)
                     if x["id"] == cena["minha"])
        assert linha["atendente_id"] == cena["outro"]
        assert linha["acompanho"] is False, "herdou a posse e continuou participante"


class TestNaoLidas:
    """A bolinha de não lidas (migração 042, pedido da Erika em 15/09).

    🚨 O BUG DE 16/09: `main.py` só mandava o viewer (`atendente_id`) para
    `conversas.listar` quando a tela pedia "minhas conversas" (`minhas=True`).
    A Caixa de Entrada ABRE sem esse filtro -- é a fila inteira -- então todo
    mundo via `nao_lidas = 0` sempre, em toda conversa, e a bolinha nunca
    aparecia fora de uma aba que quase ninguém usa como visão principal.

    O conserto separou as duas perguntas: `atendente_id` continua sendo só o
    filtro "minhas"; `visualizador_id` é "quem está olhando" e agora vai
    SEMPRE, seja qual for o filtro. Estes testes travam isso -- e teriam
    pegado o bug se existissem em 15/09.
    """

    def test_sem_visualizador_nao_lidas_vem_zero(self, cena):
        # Não é o bug -- é a honestidade de não saber quem está olhando.
        # O bug estava em `main.py` nunca mandar visualizador nenhum.
        entrada(cena["minha"], "a")
        linha = next(x for x in conversas.listar(limite=500)
                     if x["id"] == cena["minha"])
        assert linha["nao_lidas"] == 0

    def test_com_visualizador_conta_a_mensagem_nao_lida(self, cena):
        entrada(cena["minha"], "b")
        linha = next(x for x in conversas.listar(
            limite=500, visualizador_id=cena["eu"]) if x["id"] == cena["minha"])
        assert linha["nao_lidas"] == 1

    def test_visualizador_conta_mesmo_sem_filtro_minhas(self, cena):
        # A conversa é do "outro" -- "eu" só está de passagem pela fila
        # geral (atendente_id=None), que é exatamente a Caixa de Entrada
        # padrão. Sem isto, a bolinha só existiria dentro de "minhas".
        entrada(cena["dele"], "c")
        linha = next(x for x in conversas.listar(
            limite=500, visualizador_id=cena["eu"]) if x["id"] == cena["dele"])
        assert linha["nao_lidas"] == 1

    def test_marcar_lida_zera_so_pra_quem_leu(self, cena):
        entrada(cena["minha"], "d")
        conversas.marcar_lida(cena["minha"], cena["eu"])
        linha_eu = next(x for x in conversas.listar(
            limite=500, visualizador_id=cena["eu"]) if x["id"] == cena["minha"])
        linha_outro = next(x for x in conversas.listar(
            limite=500, visualizador_id=cena["outro"]) if x["id"] == cena["minha"])
        assert linha_eu["nao_lidas"] == 0
        assert linha_outro["nao_lidas"] == 1, "é por pessoa, não por conversa"


class TestMarcarLidaSoDonoOuParticipante:
    """Decisão do usuário, 16/09: abrir uma conversa vindo de "Todas" ou "Sem
    dono" é ESPIAR a fila, não atender -- e não pode consumir a bolinha de
    ninguém. Só marca como lida quem é dono OU participante, o mesmo critério
    de "aba Minhas".
    """

    def test_quem_nao_e_dono_nem_participante_nao_marca_como_lida(self, cena):
        entrada(cena["minha"], "e")
        # "outro" abre a conversa do "eu" só de passagem pela fila geral.
        antes = conversas.marcar_lida(cena["minha"], cena["outro"])
        assert antes == 0, "marcou lida mesmo sem ser dono nem participante"

        linha_eu = next(x for x in conversas.listar(
            limite=500, visualizador_id=cena["eu"]) if x["id"] == cena["minha"])
        assert linha_eu["nao_lidas"] == 1, (
            "espiar pela fila geral consumiu a bolinha do DONO de verdade")

    def test_dono_marca_normalmente(self, cena):
        entrada(cena["minha"], "f")
        r = conversas.marcar_lida(cena["minha"], cena["eu"])
        assert r > 0
        linha = next(x for x in conversas.listar(
            limite=500, visualizador_id=cena["eu"]) if x["id"] == cena["minha"])
        assert linha["nao_lidas"] == 0

    def test_participante_convidado_tambem_marca(self, cena):
        # Quem foi chamado pra acompanhar TAMBÉM está na "aba Minhas" dele
        # (é a regra de `listar`) -- então abrir e ler conta igual ao dono.
        conversas.convidar(cena["minha"], cena["outro"], cena["eu"])
        entrada(cena["minha"], "g")
        r = conversas.marcar_lida(cena["minha"], cena["outro"])
        assert r > 0
        linha = next(x for x in conversas.listar(
            limite=500, visualizador_id=cena["outro"]) if x["id"] == cena["minha"])
        assert linha["nao_lidas"] == 0

    def test_conversa_sem_dono_ninguem_marca(self, cena):
        # "Sem dono" literalmente não tem quem seja dono -- e "eu" não foi
        # convidado pra ela, então também não é participante.
        entrada(cena["orfa"], "h")
        r = conversas.marcar_lida(cena["orfa"], cena["eu"])
        assert r == 0
