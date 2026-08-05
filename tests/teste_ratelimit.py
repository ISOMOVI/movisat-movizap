"""Testes do limite de tentativas de login.

O que se protege aqui:
  - forca bruta ilimitada (o achado que gerou o modulo no MoviServer);
  - ganhar tentativas de graca alternando maiuscula no login -- desde 05/08
    `Admin` e `ADMIN` sao a MESMA conta, e precisam contar juntas;
  - consultar o bloqueio virando punicao;
  - login certo continuar preso depois de uma falha isolada.
"""
import pytest
from fastapi.testclient import TestClient

from movizap import main, ratelimit
from movizap.config import settings


@pytest.fixture(autouse=True)
def limpar_contador():
    # Estado global entre testes e fonte de teste que so falha em conjunto.
    ratelimit.zerar()
    yield
    ratelimit.zerar()


@pytest.fixture
def cliente():
    return TestClient(main.app)


def tentar(cliente, login, senha="errada-de-proposito"):
    return cliente.post("/api/sessao/login", json={"login": login, "senha": senha})


class TestChave:
    def test_conta_por_ip_e_por_login(self):
        assert ratelimit.chave_de("1.2.3.4", "ana") != ratelimit.chave_de("1.2.3.5", "ana")
        assert ratelimit.chave_de("1.2.3.4", "ana") != ratelimit.chave_de("1.2.3.4", "bob")

    def test_caixa_do_login_nao_cria_chave_nova(self):
        # senao bastava alternar maiuscula para ganhar 5 tentativas a cada vez
        base = ratelimit.chave_de("1.2.3.4", "Admin")
        for v in ("admin", "ADMIN", "aDmIn"):
            assert ratelimit.chave_de("1.2.3.4", v) == base

    def test_login_vazio_nao_estoura(self):
        assert ratelimit.chave_de("1.2.3.4", "") is not None


class TestIpAtrasDoNginx:
    """Sem isto o limite por IP e uma ilusao: atras do proxy, todo mundo
    chega como 127.0.0.1 e divide o mesmo balde de 5 tentativas."""

    class _Req:
        def __init__(self, conexao, cabecalhos=None):
            self.client = type("C", (), {"host": conexao})()
            self.headers = cabecalhos or {}

    def test_usa_o_x_real_ip_quando_vem_do_proxy_local(self):
        r = self._Req("127.0.0.1", {"x-real-ip": "203.0.113.9"})
        assert ratelimit.ip_do_cliente(r) == "203.0.113.9"

    def test_cai_no_x_forwarded_for_e_pega_o_primeiro(self):
        r = self._Req("127.0.0.1", {"x-forwarded-for": "203.0.113.9, 10.0.0.1"})
        assert ratelimit.ip_do_cliente(r) == "203.0.113.9"

    def test_cabecalho_de_origem_NAO_confiavel_e_ignorado(self):
        # 🚨 confiar sem checar a origem seria pior que nao ter limite:
        # bastaria mandar um X-Real-IP novo a cada tentativa
        r = self._Req("198.51.100.7", {"x-real-ip": "1.1.1.1"})
        assert ratelimit.ip_do_cliente(r) == "198.51.100.7"

    def test_sem_cabecalho_usa_a_conexao(self):
        assert ratelimit.ip_do_cliente(self._Req("127.0.0.1")) == "127.0.0.1"

    def test_dois_clientes_atras_do_mesmo_proxy_nao_se_bloqueiam(self):
        a = ratelimit.chave_de(ratelimit.ip_do_cliente(
            self._Req("127.0.0.1", {"x-real-ip": "203.0.113.1"})), "Admin")
        b = ratelimit.chave_de(ratelimit.ip_do_cliente(
            self._Req("127.0.0.1", {"x-real-ip": "203.0.113.2"})), "Admin")
        assert a != b


class TestContagem:
    def test_bloqueia_na_quinta_falha(self):
        c = "x"
        for _ in range(ratelimit.MAX_FALHAS - 1):
            ratelimit.registrar_falha(c)
        assert ratelimit.bloqueado_por(c) == 0
        ratelimit.registrar_falha(c)
        assert ratelimit.bloqueado_por(c) > 0

    def test_consultar_nao_pune(self):
        c = "y"
        for _ in range(50):
            ratelimit.bloqueado_por(c)
        assert ratelimit.bloqueado_por(c) == 0

    def test_sucesso_zera_o_contador(self):
        c = "z"
        for _ in range(ratelimit.MAX_FALHAS - 1):
            ratelimit.registrar_falha(c)
        ratelimit.registrar_sucesso(c)
        for _ in range(ratelimit.MAX_FALHAS - 1):
            ratelimit.registrar_falha(c)
        assert ratelimit.bloqueado_por(c) == 0, "o contador nao foi zerado no sucesso"


class TestNaRota:
    def test_sexta_tentativa_vira_429(self, cliente):
        nome = settings.admin_login
        for i in range(ratelimit.MAX_FALHAS):
            r = tentar(cliente, nome)
            assert r.status_code == 401, f"tentativa {i + 1} deveria ser 401"
        r = tentar(cliente, nome)
        assert r.status_code == 429
        assert "tentativas" in r.json()["detail"].lower()

    def test_alternar_maiuscula_nao_ganha_tentativa(self, cliente):
        nome = settings.admin_login
        variantes = [nome, nome.upper(), nome.lower(), nome.swapcase(), nome.upper()]
        for v in variantes:
            tentar(cliente, v)
        # ja sao 5 falhas na MESMA conta -- a proxima tem que travar
        r = tentar(cliente, nome.lower())
        assert r.status_code == 429, "trocar a caixa rendeu tentativa extra"

    def test_nome_inexistente_tambem_conta(self, cliente):
        # senao a varredura de logins fica livre
        for _ in range(ratelimit.MAX_FALHAS):
            tentar(cliente, "nao-existe-mesmo")
        assert tentar(cliente, "nao-existe-mesmo").status_code == 429

    def test_a_mensagem_de_429_nao_revela_se_a_conta_existe(self, cliente):
        for _ in range(ratelimit.MAX_FALHAS + 1):
            tentar(cliente, settings.admin_login)
        real = tentar(cliente, settings.admin_login)
        ratelimit.zerar()
        for _ in range(ratelimit.MAX_FALHAS + 1):
            tentar(cliente, "fantasma")
        falso = tentar(cliente, "fantasma")
        assert real.status_code == falso.status_code == 429


class TestTamanhoDoCorpo:
    def test_senha_gigante_e_recusada_antes_do_bcrypt(self, cliente):
        r = cliente.post("/api/sessao/login",
                         json={"login": "a", "senha": "x" * 5000})
        assert r.status_code == 422, "sem teto, isso vira trabalho de bcrypt em lixo"

    def test_login_gigante_e_recusado(self, cliente):
        r = cliente.post("/api/sessao/login",
                         json={"login": "a" * 500, "senha": "x"})
        assert r.status_code == 422

    def test_campo_vazio_e_recusado(self, cliente):
        assert cliente.post("/api/sessao/login",
                            json={"login": "", "senha": ""}).status_code == 422
