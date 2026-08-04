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
