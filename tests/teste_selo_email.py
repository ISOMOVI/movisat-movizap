"""O contador de e-mail não lido que alimenta o selo do menu -- 22/10.

🔵 Pedido dele: *"a quantidade de notificações que aparece no 'Chat interno'
deve aparecer tbm na aba 'Whatsapp' (...) conforme notificações da aba
'Minhas' e o mesmo para 'e-mail's' (não lidos) e na Aba "Atendimento', quando
fechada informar a soma dos 3"*.

🚨 O QUE ESTE TESTE DEFENDE É O FILTRO, NÃO A SOMA. O número sai de
`/api/eu/notificacoes`, e ele tem de contar PELA MESMA RÉGUA da aba "Entrada"
da EML_1.1 -- fora o arquivado, fora a lixeira. Selo que conta arquivada
manda a pessoa abrir a tela para procurar uma mensagem que a tela não mostra:
é a `M12` (tela que mente) pelo caminho do número em vez do texto. A mesma
regra que o `abas.minhas` segue desde 24/09, e por isso ela foi escolhida.

⚠️ A rota NÃO exige a EML_1.1 -- é a pessoa olhando para si, como o
`/api/eu/perfil`. Quem nunca conectou caixa precisa receber 0, não 403 nem
erro: é isso que o `test_quem_nao_tem_caixa_recebe_zero` prova. Sem ele, o
contador derrubaria o Notificador (que roda em TODA tela) para os atendentes
sem e-mail, e o selo do WhatsApp e do Chat interno iriam junto.
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

LOGIN = "zz_teste_selo_email_"
ENDERECO = "zz_teste_selo_email@movisat.com.br"


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
        ("zz_teste_selo_%",))
    banco.executar("DELETE FROM email_conta WHERE endereco LIKE %s",
                   ("zz_teste_selo_%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


def _atendente(sufixo: str) -> int:
    return banco.um(
        """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
           VALUES ('Teste selo', %s, %s, 'x', 'atendimento', true) RETURNING id""",
        (LOGIN + sufixo, f"{LOGIN}{sufixo}@movisat.com.br"))["id"]


def _mensagem(conta: int, chave: str, rotulos=("INBOX",), **campos) -> int:
    """Uma mensagem na caixa. Por padrão NÃO lida, na entrada, com `INBOX`.

    🚨 O `INBOX` NO PADRÃO NÃO É DETALHE. Desde 22/10 a Entrada exige esse
    rótulo: é a verdade do Gmail sobre onde a mensagem está, e foi a falta
    dela no filtro que fez o selo contar uma mensagem já arquivada no Gmail
    (dizia 1 onde o Gmail dizia 0). Fixture sem rótulo não é mensagem de
    caixa de entrada -- é mensagem arquivada, e os testes daqui falariam por
    motivo errado.
    """
    dados = {"lida": False, "arquivada": False, "na_lixeira_desde": None}
    dados.update(campos)
    mid = banco.um(
        """INSERT INTO email_mensagem (conta_id, id_externo, remetente, assunto,
                                       lida, arquivada, na_lixeira_desde)
           VALUES (%s, %s, 'quem@fora.com', 'assunto', %s, %s, %s)
           RETURNING id""",
        (conta, chave, dados["lida"], dados["arquivada"],
         dados["na_lixeira_desde"]))["id"]
    if rotulos:
        _rotular(conta, mid, *rotulos)
    return mid


@pytest.fixture()
def cena():
    limpar()
    dono = _atendente("dono")
    conta = banco.um(
        """INSERT INTO email_conta (endereco, provedor, ativa, atendente_id)
           VALUES (%s, 'gmail', true, %s) RETURNING id""",
        (ENDERECO, dono))["id"]
    yield {"dono": dono, "conta": conta}
    limpar()


def _cliente(sufixo="dono"):
    c = TestClient(main.app)
    c.headers.update(
        {"Authorization": f"Bearer {auth.criar_token(LOGIN + sufixo)}"})
    return c


def _contador(sufixo="dono") -> int:
    r = _cliente(sufixo).get("/api/eu/notificacoes")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert "email_nao_lidos" in corpo, \
        "a rota parou de devolver o contador -- o selo do menu fica em branco"
    return corpo["email_nao_lidos"]


class TestOContadorDoSelo:

    def test_conta_as_nao_lidas_da_entrada(self, cena):
        _mensagem(cena["conta"], "zz-selo-1")
        _mensagem(cena["conta"], "zz-selo-2")
        assert _contador() == 2

    def test_nao_conta_a_lida(self, cena):
        _mensagem(cena["conta"], "zz-selo-lida", lida=True)
        assert _contador() == 0

    def test_nao_conta_a_arquivada(self, cena):
        """🚨 A aba "Entrada" não mostra arquivada desde 17/09. O selo tem de
        concordar com a aba -- senão manda procurar o que a tela esconde."""
        _mensagem(cena["conta"], "zz-selo-arq", arquivada=True)
        assert _contador() == 0

    def test_nao_conta_a_da_lixeira(self, cena):
        """Mesma razão da arquivada: `na_lixeira_desde` sai da aba Entrada."""
        _mensagem(cena["conta"], "zz-selo-lixo", na_lixeira_desde="now()")
        banco.executar(
            "UPDATE email_mensagem SET na_lixeira_desde = now() WHERE id_externo = %s",
            ("zz-selo-lixo",))
        assert _contador() == 0

    def test_a_soma_ignora_lida_arquivada_e_lixeira_de_uma_vez(self, cena):
        """A cena realista: cinco mensagens, só duas valem o selo."""
        _mensagem(cena["conta"], "zz-selo-a")
        _mensagem(cena["conta"], "zz-selo-b")
        _mensagem(cena["conta"], "zz-selo-c", lida=True)
        _mensagem(cena["conta"], "zz-selo-d", arquivada=True)
        e = _mensagem(cena["conta"], "zz-selo-e")
        banco.executar(
            "UPDATE email_mensagem SET na_lixeira_desde = now() WHERE id = %s", (e,))
        assert _contador() == 2


class TestAPortaNaoFecha:

    def test_quem_nao_tem_caixa_recebe_zero(self, cena):
        """🚨 A rota roda em TODA tela, para TODO atendente -- inclusive quem
        não tem e-mail nenhum. Zero é resposta; erro aqui apagaria também o
        selo do WhatsApp e o do Chat interno, que vêm na mesma resposta."""
        _atendente("sem_caixa")
        _mensagem(cena["conta"], "zz-selo-do-outro")
        assert _contador("sem_caixa") == 0

    def test_nao_conta_a_caixa_de_outra_pessoa(self, cena):
        """A barreira da EML_1.1 (que não existia até 25/08) vale no contador
        também: o número é das caixas DESTA pessoa, nunca de todas."""
        outro = _atendente("outro")
        conta_outro = banco.um(
            """INSERT INTO email_conta (endereco, provedor, ativa, atendente_id)
               VALUES ('zz_teste_selo_outro@movisat.com.br', 'gmail', true, %s)
               RETURNING id""", (outro,))["id"]
        _mensagem(conta_outro, "zz-selo-outro-1")
        _mensagem(conta_outro, "zz-selo-outro-2")
        _mensagem(cena["conta"], "zz-selo-meu")
        assert _contador() == 1
        assert _contador("outro") == 2

    def test_caixa_inativa_nao_conta(self, cena):
        """`_caixas_do_usuario` filtra por `ativa`; o contador faz o mesmo."""
        _mensagem(cena["conta"], "zz-selo-inativa")
        banco.executar("UPDATE email_conta SET ativa = false WHERE id = %s",
                       (cena["conta"],))
        assert _contador() == 0


class TestOsTresSelosVemJuntos:

    def test_a_resposta_traz_as_tres_contas_do_menu(self, cena):
        """🔵 22/10: o cabeçalho fechado de "Atendimento" soma os três. Os três
        números têm de sair da MESMA resposta -- era isso ou um terceiro ritmo
        de polling no navegador, e o `MenuLateral` já tinha dois."""
        corpo = _cliente().get("/api/eu/notificacoes").json()
        assert "email_nao_lidos" in corpo
        assert "abas" in corpo and "minhas" in corpo["abas"]


class TestOSeloEhSoDaENTRADA:
    """🔵 22/10, segunda correção: *"siga com a 2"* -- a Entrada e o selo
    passam a exigir o rótulo `INBOX`, que é o que o Gmail usa para dizer "está
    na caixa de entrada". Antes disso o selo contava o que o Gmail já tinha
    arquivado."""

    def test_sem_rotulo_INBOX_nao_conta(self, cena):
        """🚨 ERA O DEFEITO RESTANTE, e era UMA mensagem na caixa real: um
        "Alerta de segurança" do Google, não lido desde 22/04 e **arquivado no
        Gmail** (sem `INBOX` desde a importação). O selo dizia 1, o Gmail 0."""
        _mensagem(cena["conta"], "zz-sem-inbox", rotulos=())
        assert _contador() == 0

    def test_a_enviada_nao_conta(self, cena):
        """Enviada é lugar próprio desde 22/10, e nunca foi "não lida da
        caixa de entrada" -- mesmo que o Gmail a marque como não lida."""
        _mensagem(cena["conta"], "zz-enviada", rotulos=("SENT",))
        assert _contador() == 0

    def test_com_INBOX_conta(self, cena):
        _mensagem(cena["conta"], "zz-na-caixa", rotulos=("INBOX",))
        assert _contador() == 1
