"""Testes de autenticação e da barreira de permissão nas rotas.

O que se protege aqui:
  - rota sem token respondendo dado;
  - token de outro sistema sendo aceito;
  - `requer_tela` com código inexistente virando 403 silencioso em vez de
    derrubar o arranque.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from movizap import auth, telas
from movizap.config import settings


class TestSenha:
    def test_hash_nao_e_a_senha(self):
        h = auth.hash_senha("Segredo123!")
        assert h != "Segredo123!"
        assert h.startswith("$2")  # bcrypt

    def test_hash_confere(self):
        h = auth.hash_senha("Segredo123!")
        assert auth.pwd_ctx.verify("Segredo123!", h)

    def test_hash_rejeita_senha_errada(self):
        h = auth.hash_senha("Segredo123!")
        assert not auth.pwd_ctx.verify("segredo123!", h)

    def test_hashes_da_mesma_senha_sao_diferentes(self):
        # sal aleatório: dois hashes iguais denunciariam ausência de sal
        assert auth.hash_senha("igual") != auth.hash_senha("igual")


class TestToken:
    def test_ida_e_volta(self):
        token = auth.criar_token("movizap")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[auth.ALGORITMO])
        assert payload["sub"] == "movizap"
        assert payload["tipo"] == "movizap"

    def test_token_de_outro_sistema_e_recusado(self):
        # o campo `tipo` existe para isso: token do MoviServer não vale aqui
        alheio = jwt.encode(
            {
                "sub": "movizap",
                "tipo": "moviserver",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            settings.jwt_secret,
            algorithm=auth.ALGORITMO,
        )
        app = FastAPI()

        @app.get("/x")
        def _(u: dict = Depends(auth.get_usuario)):
            return u

        r = TestClient(app).get("/x", headers={"Authorization": f"Bearer {alheio}"})
        assert r.status_code == 401

    def test_token_expirado_e_recusado(self):
        vencido = jwt.encode(
            {
                "sub": "movizap",
                "tipo": "movizap",
                "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
            },
            settings.jwt_secret,
            algorithm=auth.ALGORITMO,
        )
        app = FastAPI()

        @app.get("/x")
        def _(u: dict = Depends(auth.get_usuario)):
            return u

        r = TestClient(app).get("/x", headers={"Authorization": f"Bearer {vencido}"})
        assert r.status_code == 401

    def test_token_assinado_com_outra_chave_e_recusado(self):
        forjado = jwt.encode(
            {
                "sub": "movizap",
                "tipo": "movizap",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            "chave-errada",
            algorithm=auth.ALGORITMO,
        )
        app = FastAPI()

        @app.get("/x")
        def _(u: dict = Depends(auth.get_usuario)):
            return u

        r = TestClient(app).get("/x", headers={"Authorization": f"Bearer {forjado}"})
        assert r.status_code == 401


class TestRequerTela:
    def test_codigo_inexistente_estoura_no_import_da_rota(self):
        # o valor disso é falhar no arranque, não virar 403 três semanas depois
        with pytest.raises(telas.CodigoDeTelaInvalido):
            auth.requer_tela("XXX_9.9")

    def test_rota_protegida_sem_token_da_401(self):
        app = FastAPI()

        @app.get("/protegida")
        def _(u: dict = Depends(auth.requer_tela("CAD_1.1"))):
            return {"ok": True}

        assert TestClient(app).get("/protegida").status_code == 401


class TestBuscaDeUsuario:
    def test_login_desconhecido_nao_existe(self):
        assert auth.buscar_usuario("ninguem") is None

    def test_senha_errada_nao_autentica(self):
        assert auth.validar_login(settings.admin_login, "errada") is None

    def test_login_desconhecido_nao_autentica(self):
        assert auth.validar_login("ninguem", "qualquer") is None


class TestLoginIgnoraCaixa:
    """05/08: o painel recusou o acesso em 1ms.

    Rápido demais para ter chegado no bcrypt -- a verificação leva dezenas de
    milissegundos. O nome digitado não era idêntico ao gravado, só na caixa.
    Login identifica a pessoa; quem protege é a senha.

    Os testes não fixam o nome: leem do .env. Trocar o login do painel não
    pode exigir mexer em teste.
    """

    def test_encontra_o_usuario_em_qualquer_caixa(self):
        nome = settings.admin_login
        for variante in (nome, nome.upper(), nome.lower(), nome.swapcase()):
            assert auth.buscar_usuario(variante) is not None, f"recusou {variante!r}"

    def test_devolve_sempre_o_login_canonico(self):
        # O token e a auditoria usam este valor. Se ele variasse conforme o
        # que foi digitado, a mesma pessoa viraria duas no log.
        u = auth.buscar_usuario(settings.admin_login.upper())
        assert u["login"] == settings.admin_login

    def test_nome_diferente_continua_recusado(self):
        assert auth.buscar_usuario(settings.admin_login + "x") is None
        assert auth.buscar_usuario("") is None

    def test_ignorar_caixa_no_nome_nao_afrouxa_a_senha(self):
        # a senha continua sensível à caixa -- é ela que protege
        h = auth.hash_senha("Segredo123!")
        assert not auth.pwd_ctx.verify("segredo123!", h)
        assert not auth.pwd_ctx.verify("SEGREDO123!", h)


class TestSessaoDoDia:
    """🔵 15/10 — o token vale até a VIRADA DO DIA, no fuso do escritório.

    O que estes testes guardam:
      · a virada é a de São Paulo, não a de UTC (em UTC ela cairia às 21h de
        Brasília, em plena tarde de trabalho);
      · o PISO de 2 horas: quem entra às 23:30 não cai às 00:00;
      · o piso não rouba dia de quem tem folga de sobra;
      · a expiração que a tela recebe é a MESMA que o token obedece.
    """

    FUSO = auth.FUSO_DO_DIA

    def quando(self, ano, mes, dia, hora, minuto=0):
        return datetime(ano, mes, dia, hora, minuto, tzinfo=self.FUSO)

    def test_entrou_de_manha_vale_ate_a_meia_noite_do_mesmo_dia(self):
        fim = auth.expira_na_virada(self.quando(2026, 10, 15, 8)).astimezone(self.FUSO)
        assert (fim.year, fim.month, fim.day, fim.hour) == (2026, 10, 16, 0)

    def test_a_virada_e_a_de_sao_paulo_e_nao_a_de_utc(self):
        fim = auth.expira_na_virada(self.quando(2026, 10, 15, 8))
        # 00:00 de Brasília é 03:00 UTC. Se fosse a virada de UTC, quem entrou
        # de manhã cairia às 21h de Brasília -- no meio da tarde.
        assert fim.utcoffset().total_seconds() == 0, "a conta sai em UTC"
        assert fim.hour == 3

    def test_quem_entra_colado_na_virada_nao_cai_em_meia_hora(self):
        fim = auth.expira_na_virada(self.quando(2026, 10, 15, 23, 30)).astimezone(self.FUSO)
        assert (fim.month, fim.day, fim.hour) == (10, 17, 0), "o piso de 2h falhou"

    def test_duas_horas_exatas_ainda_valem_o_mesmo_dia(self):
        """O piso é "menos de 2 horas". Às 22:00 em ponto sobram 2 horas
        cheias, e o turno termina na virada desta noite."""
        fim = auth.expira_na_virada(self.quando(2026, 10, 15, 22)).astimezone(self.FUSO)
        assert (fim.month, fim.day) == (10, 16)

    def test_o_piso_nao_rouba_dia_de_quem_tem_folga(self):
        fim = auth.expira_na_virada(self.quando(2026, 10, 15, 21, 59)).astimezone(self.FUSO)
        assert (fim.month, fim.day) == (10, 16)

    def test_o_token_obedece_a_mesma_hora_que_a_tela_recebe(self):
        token, expira = auth.criar_token_e_expiracao("movizap")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[auth.ALGORITMO])
        assert payload["exp"] == int(expira.timestamp())
        # E é no futuro: token nascendo vencido derrubaria todo mundo.
        assert expira > datetime.now(timezone.utc)

    def test_criar_token_continua_devolvendo_so_o_texto(self):
        """`criar_token` é chamado em dois lugares (senha e Google) e em vários
        testes: a assinatura não mudou."""
        assert isinstance(auth.criar_token("movizau"), str)

    def test_get_usuario_carrega_a_expiracao_do_token_validado(self):
        app = FastAPI()

        @app.get("/x")
        def _(u: dict = Depends(auth.get_usuario)):
            return {"exp": u.get("token_exp")}

        token, expira = auth.criar_token_e_expiracao(settings.admin_login)
        r = TestClient(app).get("/x", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        assert r.json()["exp"] == int(expira.timestamp())
