"""A mensagem que SUMIU do Gmail, e o selo que não pode discordar da aba.

🚨 O DEFEITO QUE ISTO DEFENDE, medido em 22/10 na caixa real. A varredura do
Gmail grava TRÊS estados e o filtro das abas conhecia dois: `sumida_do_gmail_em`
não entrava em nenhum `WHERE`. Resultado na conta do owner: a aba "Entrada"
mostrava **73 mensagens que já não existem no Gmail**, 56 delas não lidas, e o
selo do menu dizia **61** onde a verdade eram **5**.

🚨 E O SELO ERROU PORQUE EU COPIEI O FILTRO À MÃO. A regra que eu seguia era a
certa ("a bolinha não pode discordar da aba"), mas a forma de seguir era uma
segunda cópia do `WHERE` -- e cópia divergiu no mesmo dia em que nasceu. Por
isso o teste central deste arquivo não é nenhum dos casos abaixo: é o
`test_o_selo_e_igual_ao_que_a_aba_entrada_mostra`, que compara os DOIS
resultados. Enquanto ele existir, os dois não podem discordar -- nem hoje, nem
na entrega de quem não leu este comentário.

⚠️ "Sumida" NÃO é "na lixeira", e confundir as duas foi o erro. A mensagem pode
ir de ativa a inexistente ENTRE DUAS VARREDURAS (apagada de vez no Gmail, ou
purgada pelos 30 dias) e nunca ser vista na lixeira. Era isso que prendia 73
mensagens na Entrada: a Lixeira olhava só `na_lixeira_desde`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_sumida_"
ENDERECO = "zz_teste_sumida@movisat.com.br"


def _rotular(conta: int, mensagem_id: int, *rotulos: str) -> None:
    """Pendura rótulos do Gmail na mensagem, criando o marcador se faltar.

    🚨 A CAIXA DA MENSAGEM DEPENDE DISTO desde 22/10: `INBOX` manda para a
    Entrada, `SENT` para Enviados, nenhum dos dois para Arquivadas (= está
    arquivada no Gmail). Fixture sem rótulo não representa mensagem de caixa
    de entrada nenhuma -- representa uma mensagem arquivada.
    """
    for rotulo in rotulos:
        mid = banco.um(
            """INSERT INTO email_marcador (conta_id, id_externo, nome, natureza)
               VALUES (%s, %s, %s, 'sistema')
               ON CONFLICT (conta_id, id_externo) DO UPDATE SET nome = EXCLUDED.nome
               RETURNING id""", (conta, rotulo, rotulo))["id"]
        banco.executar(
            """INSERT INTO email_mensagem_marcador (mensagem_id, marcador_id)
               VALUES (%s, %s) ON CONFLICT DO NOTHING""", (mensagem_id, mid))


def limpar():
    banco.executar(
        """DELETE FROM email_mensagem WHERE conta_id IN
           (SELECT id FROM email_conta WHERE endereco LIKE %s)""",
        ("zz_teste_sumida%",))
    banco.executar("DELETE FROM email_conta WHERE endereco LIKE %s",
                   ("zz_teste_sumida%",))
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
    dono = banco.um(
        """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
           VALUES ('Teste sumida', %s, %s, 'x', 'atendimento', true)
           RETURNING id""",
        (LOGIN + "dono", f"{LOGIN}dono@movisat.com.br"))["id"]
    conta = banco.um(
        """INSERT INTO email_conta (endereco, provedor, ativa, atendente_id)
           VALUES (%s, 'gmail', true, %s) RETURNING id""",
        (ENDERECO, dono))["id"]
    yield {"dono": dono, "conta": conta}
    limpar()


def _msg(conta, chave, *, lida=False, arquivada=False,
         lixeira=False, sumida=False, rotulos=("INBOX",)):
    """Uma mensagem num dos estados que a varredura do Gmail produz.

    ⚠️ `rotulos` padrão `("INBOX",)`: desde 22/10 a caixa da mensagem sai do
    rótulo do Gmail, e sem ele a fixture representaria uma mensagem arquivada.
    """
    mid = banco.um(
        """INSERT INTO email_mensagem (conta_id, id_externo, remetente, assunto,
                                       lida, arquivada)
           VALUES (%s, %s, 'quem@fora.com', %s, %s, %s) RETURNING id""",
        (conta, chave, chave, lida, arquivada))["id"]
    if rotulos:
        _rotular(conta, mid, *rotulos)
    if lixeira:
        banco.executar(
            "UPDATE email_mensagem SET na_lixeira_desde = now() WHERE id = %s",
            (mid,))
    if sumida:
        banco.executar(
            "UPDATE email_mensagem SET sumida_do_gmail_em = now() WHERE id = %s",
            (mid,))
    return mid


def _cliente():
    c = TestClient(main.app)
    c.headers.update({"Authorization": f"Bearer {auth.criar_token(LOGIN + 'dono')}"})
    return c


def _ids(caixa):
    r = _cliente().get(f"/api/email/mensagens?caixa={caixa}&limite=500")
    assert r.status_code == 200, r.text
    return {m["id"] for m in r.json()["mensagens"]}


CAIXAS = ("entrada", "enviados", "arquivadas", "lixeira")


def _onde(mensagem_id):
    """Em que caixas esta mensagem aparece. Tem de ser exatamente uma."""
    return [c for c in CAIXAS if mensagem_id in _ids(c)]


def _selo():
    r = _cliente().get("/api/eu/notificacoes")
    assert r.status_code == 200, r.text
    return r.json()["email_nao_lidos"]


class TestASumidaSaiDaEntrada:

    def test_a_sumida_nao_aparece_na_entrada(self, cena):
        """🚨 ERA O DEFEITO: 73 destas estavam na Entrada da caixa real."""
        m = _msg(cena["conta"], "zz-sumida", sumida=True)
        assert m not in _ids("entrada")

    def test_a_sumida_aparece_na_lixeira(self, cena):
        """🔵 Decisão dele (opção 1): vai para a Lixeira, não desaparece.

        Esconder de todas as abas seria perder de vista a ÚNICA cópia que
        existe -- o Gmail já não tem a dele."""
        m = _msg(cena["conta"], "zz-sumida", sumida=True)
        assert m in _ids("lixeira")

    def test_a_sumida_que_passou_pela_lixeira_tambem_cai_na_lixeira(self, cena):
        """Das 266 sumidas da caixa real, 193 tinham as DUAS flags. Essas já
        caíam certo antes -- e têm de continuar caindo, uma vez só."""
        m = _msg(cena["conta"], "zz-sumida", sumida=True, lixeira=True)
        assert m in _ids("lixeira")
        assert m not in _ids("entrada")

    def test_a_sumida_nao_aparece_em_arquivadas(self, cena):
        m = _msg(cena["conta"], "zz-sumida", sumida=True, arquivada=True)
        assert m not in _ids("arquivadas")
        assert m in _ids("lixeira")

    @pytest.mark.parametrize("estado", [
        {"lixeira": True},
        {"sumida": True},
        {"lixeira": True, "sumida": True},
        {"arquivada": True},
        {},
        # 🔵 22/10: os casos que as quatro caixas trouxeram. O penúltimo é a
        # mensagem com os DOIS rótulos (medida: 1 na caixa real) e o último é
        # a sem nenhum (medida: 1 -- o "Alerta de segurança" do Google, que
        # antes não caía em caixa nenhuma).
        {"rotulos": ("SENT",)},
        {"rotulos": ("SENT",), "lixeira": True},
        {"rotulos": ("INBOX", "SENT")},
        {"rotulos": ()},
    ])
    def test_toda_mensagem_cai_em_EXATAMENTE_uma_aba(self, cena, estado):
        """🚨 O SEGUNDO BURACO ERA ESTE, pelo outro lado: a sumida sem
        `na_lixeira_desde` não caía na Lixeira e ficava presa na Entrada.
        Alargar o filtro da Lixeira sem este teste poderia fazê-la aparecer em
        DUAS -- e mensagem em duas abas é a mesma mentira que mensagem em
        nenhuma."""
        m = _msg(cena["conta"], "zz-uma-aba", **estado)
        onde = _onde(m)
        assert len(onde) == 1, \
            f"estado {estado} caiu em {onde}, deveria cair em exatamente uma"


class TestOSeloNaoDiscordaDaAba:

    def test_a_sumida_nao_lida_nao_conta_no_selo(self, cena):
        """🚨 56 destas inflavam o selo: 61 na tela, 5 de verdade."""
        _msg(cena["conta"], "zz-sumida-nao-lida", sumida=True)
        assert _selo() == 0

    def test_o_selo_conta_so_a_nao_lida_viva(self, cena):
        _msg(cena["conta"], "zz-viva-1")
        _msg(cena["conta"], "zz-viva-2")
        _msg(cena["conta"], "zz-sumida", sumida=True)
        _msg(cena["conta"], "zz-lixeira", lixeira=True)
        _msg(cena["conta"], "zz-arquivada", arquivada=True)
        _msg(cena["conta"], "zz-lida", lida=True)
        assert _selo() == 2

    def test_o_selo_e_igual_ao_que_a_aba_entrada_mostra(self, cena):
        """🚨 ESTE É O TESTE QUE IMPORTA, e o único que teria pegado o defeito
        de 22/10 sem alguém desconfiar primeiro.

        Ele não afirma NENHUM filtro: afirma que os dois caminhos dão o mesmo
        número. Filtro novo, estado novo da varredura, coluna nova -- se a
        lista e o contador discordarem, cai aqui, sem que ninguém precise se
        lembrar de atualizar um segundo lugar.

        A cena cobre os cinco estados de propósito: é a combinação, e não cada
        caso, que separa duas implementações do mesmo `WHERE`."""
        _msg(cena["conta"], "zz-viva-1")
        _msg(cena["conta"], "zz-viva-2")
        _msg(cena["conta"], "zz-lida", lida=True)
        _msg(cena["conta"], "zz-sumida", sumida=True)
        _msg(cena["conta"], "zz-sumida-e-lixeira", sumida=True, lixeira=True)
        _msg(cena["conta"], "zz-lixeira", lixeira=True)
        _msg(cena["conta"], "zz-arquivada", arquivada=True)

        r = _cliente().get("/api/email/mensagens?caixa=entrada&limite=500")
        nao_lidas_na_aba = sum(1 for m in r.json()["mensagens"] if not m["lida"])
        assert _selo() == nao_lidas_na_aba


class TestOFiltroEUmSo:

    def test_a_lista_e_o_contador_leem_a_MESMA_constante(self):
        """🚨 O defeito nasceu de uma CÓPIA do `WHERE`, não de um filtro errado.

        Este teste lê o código: a rota da lista tem de chamar
        `filtro_da_caixa`, e o contador tem de interpolar `FILTRO_ENTRADA`.
        Alguém que volte a escrever as condições à mão em qualquer um dos dois
        reprova aqui -- e é o único jeito de defender a CAUSA em vez do
        sintoma."""
        fonte = Path("/home/claude/movizap_painel/movizap/main.py").read_text(
            encoding="utf-8")
        assert "FILTRO_ENTRADA = (" in fonte, "a constante única desapareceu"
        assert "condicoes = [filtro_da_caixa(caixa)" in fonte, \
            "a lista voltou a escrever as condições à mão"
        assert "AND {FILTRO_ENTRADA}" in fonte, \
            "o contador voltou a escrever as condições à mão"

    def test_os_tres_filtros_conhecem_a_sumida(self):
        """A flag que faltava tem de estar nos três -- é o que garante que
        nenhuma aba volte a mostrar o que não existe mais no Gmail."""
        assert "sumida_do_gmail_em" in main.FILTRO_ENTRADA
        assert "sumida_do_gmail_em" in main.FILTRO_ARQUIVADAS
        assert "sumida_do_gmail_em" in main.FILTRO_LIXEIRA


class TestEnviadosEhLugar:
    """🔵 22/10: *"enviadas devem ter seu proprio grupo, igual no Gmail"*.

    🚨 ANTES DISSO "Entrada" EXISTIA EM DOIS CONTROLES -- a aba de caixa e a
    lista de marcadores -- e a tela mandava os dois ao servidor de uma vez
    (`caixa=lixeira&marcador=INBOX`, visto no log). Consequência medida: **11
    mensagens enviadas na lixeira ficavam invisíveis**, porque a Lixeira era
    filtrada pelo rótulo da Entrada. O conserto é de modelo: caixa é LUGAR,
    marcador é ETIQUETA.
    """

    def test_a_enviada_fica_em_Enviados(self, cena):
        m = _msg(cena["conta"], "zz-enviada", rotulos=("SENT",))
        assert _onde(m) == ["enviados"]

    def test_a_enviada_nao_aparece_na_Entrada(self, cena):
        m = _msg(cena["conta"], "zz-enviada", rotulos=("SENT",))
        assert m not in _ids("entrada")

    def test_a_enviada_na_lixeira_aparece_na_LIXEIRA(self, cena):
        """🚨 AS 11 INVISÍVEIS. A Lixeira não pode filtrar pelo rótulo da
        Entrada: o que está na lixeira está na lixeira, venha de onde vier."""
        m = _msg(cena["conta"], "zz-enviada-lixo", rotulos=("SENT",), lixeira=True)
        assert _onde(m) == ["lixeira"]

    def test_a_que_tem_os_DOIS_rotulos_fica_na_Entrada(self, cena):
        """Medido: 1 mensagem na caixa real tem `INBOX` e `SENT`. A Entrada
        ganha, por precedência explícita -- é o que mantém "exatamente uma
        caixa" verdadeiro, e a decisão está escrita no `main.py`."""
        m = _msg(cena["conta"], "zz-ambos", rotulos=("INBOX", "SENT"))
        assert _onde(m) == ["entrada"]

    def test_a_sem_rotulo_nenhum_fica_em_Arquivadas(self, cena):
        """🚨 ESTA É A QUE NÃO PODIA DESAPARECER. Sem `INBOX` e sem `SENT`, a
        mensagem está arquivada no Gmail -- e antes de 22/10 ela não caía em
        caixa nenhuma depois da Entrada passar a exigir `INBOX`. É o mesmo
        defeito das 73 sumidas, que custou a volta anterior deste mesmo dia."""
        m = _msg(cena["conta"], "zz-sem-rotulo", rotulos=())
        assert _onde(m) == ["arquivadas"]

    def test_arquivada_pelo_painel_fica_em_Arquivadas_mesmo_com_INBOX(self, cena):
        """⚠️ Arquivar pelo painel tira o `INBOX` no Gmail, mas NÃO apaga o
        marcador local (só o `UNREAD` é apagado, em `marcar_lida`). Sem a
        nossa coluna `arquivada` tendo precedência no filtro, a mensagem
        arquivada pelo painel voltaria para a Entrada."""
        m = _msg(cena["conta"], "zz-arq-com-inbox",
                 rotulos=("INBOX",), arquivada=True)
        assert _onde(m) == ["arquivadas"]
