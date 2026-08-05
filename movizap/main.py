"""MoviZap — painel de comunicação da Movisat.

Fase 1: esqueleto. Login, registro de telas, barra de status.
Sem banco ainda -- ver `auth.buscar_usuario`.
"""
import logging
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth
from . import ratelimit
from . import telas as registro_telas
from .config import RAIZ, settings, silenciar_clientes_http

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("movizap")

FRONTEND = RAIZ / "frontend" / "dist"


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    silenciar_clientes_http()
    faltando = settings.faltando()
    if faltando:
        # falhar no arranque é melhor que subir sem autenticação
        raise RuntimeError(f"Configuração ausente no .env: {', '.join(faltando)}")
    log.info(
        "MoviZap subindo | ambiente=%s | telas ativas=%d",
        settings.ambiente,
        len(registro_telas.ativas()),
    )
    yield
    log.info("MoviZap encerrando")


app = FastAPI(
    title="MoviZap",
    description="Painel de comunicação da Movisat",
    lifespan=ciclo_de_vida,
    docs_url=None,   # sem doc pública: o painel não é API de terceiros
    redoc_url=None,
)


@app.middleware("http")
async def identificar_requisicao(request: Request, call_next):
    """Dá um id curto a cada requisição e devevolve no header.

    É esse id que aparece na barra de status. No erro, o que se procura no log
    não é a tela -- é *aquela* requisição.
    """
    req_id = secrets.token_hex(2)
    request.state.req_id = req_id
    inicio = time.perf_counter()
    try:
        resposta = await call_next(request)
    except Exception:
        log.exception("req=%s %s %s", req_id, request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno.", "req_id": req_id},
            headers={"X-Request-Id": req_id},
        )
    ms = (time.perf_counter() - inicio) * 1000
    resposta.headers["X-Request-Id"] = req_id
    if ms > 1000 or resposta.status_code >= 400:
        log.info(
            "req=%s %s %s -> %s em %.0fms",
            req_id, request.method, request.url.path, resposta.status_code, ms,
        )
    return resposta


# ---------------------------------------------------------------- sessão

class Credenciais(BaseModel):
    # Teto de tamanho: sem ele, um POST de 10 MB no campo senha vira trabalho
    # de bcrypt em cima de lixo. O bcrypt já ignora além de 72 bytes.
    login: str = Field(min_length=1, max_length=64)
    senha: str = Field(min_length=1, max_length=256)


@app.post("/api/sessao/login")
def login(dados: Credenciais, request: Request):
    """🚨 Rota mais atacada de qualquer painel. Três defesas, nesta ordem:

    1. limite de tentativas ANTES do bcrypt -- senão a própria verificação
       (250ms) vira o custo do ataque, e ele fica de graça para o atacante;
    2. mensagem única, que não entrega se errou o login ou a senha;
    3. teto de tamanho no corpo, acima.
    """
    chave = ratelimit.chave_de(ratelimit.ip_do_cliente(request), dados.login)

    resta = ratelimit.bloqueado_por(chave)
    if resta:
        log.warning("req=%s login bloqueado: %s (%ss restantes)",
                    request.state.req_id, chave, resta)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Muitas tentativas. Tente de novo em {resta // 60 + 1} min.",
        )

    usuario = auth.validar_login(dados.login, dados.senha)
    if not usuario:
        ratelimit.registrar_falha(chave)
        # mensagem única de propósito: não entrega se o erro foi o login ou a senha
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login ou senha inválidos.",
        )

    ratelimit.registrar_sucesso(chave)
    return {
        "token": auth.criar_token(usuario["login"]),
        "expira_em_horas": auth.TOKEN_EXPIRA_HORAS,
        "usuario": {"login": usuario["login"], "nome": usuario["nome"], "owner": usuario["owner"]},
    }


@app.get("/api/sessao/eu")
def eu(usuario: dict = Depends(auth.get_usuario)):
    return {
        "login": usuario["login"],
        "nome": usuario["nome"],
        "owner": usuario["owner"],
        "telas": registro_telas.do_usuario(usuario),
    }


# ---------------------------------------------------------------- telas

@app.get("/api/telas")
def telas_do_usuario(usuario: dict = Depends(auth.get_usuario)):
    """O menu. O frontend não decide o que aparece -- ele desenha o que vem."""
    return registro_telas.do_usuario(usuario)


@app.get("/api/telas/registro")
def registro_completo(usuario: dict = Depends(auth.requer_tela("CFG_9.1"))):
    """CFG_9.1 -- o registro inteiro, inclusive o que ainda não subiu."""
    return {
        "fase_atual": registro_telas.FASE_ATUAL,
        "telas": registro_telas.TELAS,
        "permissoes": sorted(registro_telas.PERMISSOES_VALIDAS),
        "perfis": {p: sorted(registro_telas.permissoes_do_perfil(p)) for p in registro_telas.PERFIS},
    }


# ---------------------------------------------------------------- saúde

@app.get("/api/saude")
def saude(request: Request):
    return {
        "ok": True,
        "app": settings.app_nome,
        "ambiente": settings.ambiente,
        "req_id": request.state.req_id,
        "telas_ativas": len(registro_telas.ativas()),
    }


# ---------------------------------------------------------------- frontend

if FRONTEND.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")

    @app.get("/{caminho:path}")
    def spa(caminho: str):
        """Toda rota que não é /api cai no index -- o roteamento é do Vue."""
        # /api que não casou com rota real NÃO pode virar index.html: o fetch
        # receberia HTML com status 200 e quebraria num JSON.parse longe da
        # causa. 404 em JSON diz a verdade onde o erro nasceu.
        if caminho == "api" or caminho.startswith("api/"):
            raise HTTPException(status_code=404, detail="Rota de API inexistente.")

        # `caminho` vem do cliente. Sem esta trava, "../../.env" seria servido
        # como arquivo estático: resolver e exigir que fique dentro do dist.
        raiz = FRONTEND.resolve()
        arquivo = (FRONTEND / caminho).resolve()
        if caminho and arquivo.is_file() and arquivo.is_relative_to(raiz):
            return FileResponse(arquivo)
        return FileResponse(FRONTEND / "index.html")
