"""MoviZap — painel de comunicação da Movisat.

Fase 1: esqueleto. Login, registro de telas, barra de status.
Sem banco ainda -- ver `auth.buscar_usuario`.
"""
import asyncio
import logging
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth
from . import banco
from . import cadastro
from . import canais as registro_canais
from . import evolution
from . import ratelimit
from . import sync as sync_harmonit
from . import telas as registro_telas
from . import vigia
from . import webhook as registro_webhook
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
    banco.abrir()
    for aviso in settings.avisos():
        # não derruba: a CFG_1.1 sem Evolution é uma tela quebrada, não um
        # painel quebrado
        log.warning("%s", aviso)
    log.info(
        "MoviZap subindo | ambiente=%s | telas ativas=%d | banco=%s",
        settings.ambiente,
        len(registro_telas.ativas()),
        settings.dsn_seguro(),   # sem a senha
    )
    # 🚨 O vigia existe porque `canal_evento` só era escrito quando alguém
    # abria a CFG_1.1 -- e essa tabela responde "desde quando parou de chegar
    # mensagem?". Histórico que só avança quando observado não é histórico.
    parar_vigia = asyncio.Event()
    tarefa_vigia = asyncio.create_task(vigia.rodar(parar_vigia))

    yield

    parar_vigia.set()
    try:
        await asyncio.wait_for(tarefa_vigia, timeout=5)
    except asyncio.TimeoutError:
        tarefa_vigia.cancel()
    banco.fechar()
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


# ---------------------------------------------------------------- canais

@app.get("/api/canais")
def listar_canais(usuario: dict = Depends(auth.requer_tela("CFG_1.1"))):
    """CFG_1.1 — os canais do banco com o estado ao vivo do Evolution.

    O banco diz o que EXISTE; o Evolution diz o que está ACONTECENDO. Guardar
    estado no banco e confiar nele é como se descobre três dias depois que
    parou de chegar mensagem.
    """
    return registro_canais.listar()


@app.get("/api/canais/{canal_id}/eventos")
def eventos_do_canal(canal_id: int,
                     usuario: dict = Depends(auth.requer_tela("CFG_1.1"))):
    """O histórico que responde 'desde quando parou de chegar mensagem?'."""
    if not registro_canais.por_id(canal_id):
        raise HTTPException(status_code=404, detail="Canal não encontrado.")
    return registro_canais.eventos(canal_id)


@app.post("/api/canais/{canal_id}/conectar")
def conectar_canal(canal_id: int, request: Request,
                   usuario: dict = Depends(auth.requer_tela("CFG_1.1"))):
    """Pede um QR novo. O do Baileys expira em ~60s — a tela chama de novo."""
    try:
        return registro_canais.conectar(canal_id, usuario["login"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except evolution.ErroEvolution as e:
        log.warning("req=%s conectar canal %s: %s",
                    request.state.req_id, canal_id, e)
        raise HTTPException(status_code=502, detail=f"Evolution: {e}")


@app.post("/api/canais/{canal_id}/confirmar")
def confirmar_canal(canal_id: int, request: Request,
                    usuario: dict = Depends(auth.requer_tela("CFG_1.1"))):
    """A tela viu que conectou. É AQUI que as settings da Fase 1 entram."""
    try:
        return {"settings": registro_canais.confirmar_pareamento(
            canal_id, usuario["login"])}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except evolution.ErroEvolution as e:
        log.warning("req=%s confirmar canal %s: %s",
                    request.state.req_id, canal_id, e)
        raise HTTPException(status_code=502, detail=f"Evolution: {e}")


@app.post("/api/canais/{canal_id}/desconectar")
def desconectar_canal(canal_id: int, request: Request,
                      usuario: dict = Depends(auth.requer_tela("CFG_1.1"))):
    try:
        registro_canais.desconectar(canal_id, usuario["login"])
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except evolution.ErroEvolution as e:
        log.warning("req=%s desconectar canal %s: %s",
                    request.state.req_id, canal_id, e)
        raise HTTPException(status_code=502, detail=f"Evolution: {e}")


# ---------------------------------------------------------------- webhook

@app.post("/api/webhook/evolution/{segredo}")
async def receber_webhook(segredo: str, request: Request):
    """O Evolution empurra os eventos aqui. SEM sessão -- quem chama é máquina.

    🚨 Este endpoint é PÚBLICO. O Evolution roda em container e não alcança o
    `127.0.0.1` do host, então a chamada entra pelo nginx. O que o protege é o
    `segredo` no caminho, de 43 caracteres, que sai do `.env`.

    🚨 Responder 200 rápido é a regra número um do projeto. Se demorar, o
    Evolution considera falha e reenvia -- e o problema piora sozinho. Aqui só
    se grava o corpo cru; interpretar é outro passo, lendo da tabela.

    🚨 E responde 200 mesmo quando algo dá errado do nosso lado. Devolver 500
    faria o Evolution reenviar a mesma mensagem indefinidamente contra um
    sistema que já falhou nela. O erro fica no log, com o req_id.
    """
    if not settings.webhook_segredo or not secrets.compare_digest(
            segredo, settings.webhook_segredo):
        # 404 e não 403: quem errou o segredo não precisa saber que acertou a rota.
        raise HTTPException(status_code=404, detail="Não encontrado.")

    try:
        corpo = await request.json()
    except Exception:
        corpo = {"corpo_ilegivel": (await request.body()).decode(
            "utf-8", "replace")[:4000]}

    try:
        # `def` normal numa thread: o banco é bloqueante, e a regra do
        # `asyncio.to_thread` com `async def` já custou caro neste projeto.
        return await asyncio.to_thread(registro_webhook.registrar, corpo)
    except Exception as e:
        log.exception("req=%s webhook falhou ao gravar", request.state.req_id)
        return {"ok": False, "erro": type(e).__name__}


@app.get("/api/webhook/eventos")
def eventos_do_webhook(limite: int = 20,
                       usuario: dict = Depends(auth.requer_tela("CFG_1.1"))):
    """Os últimos eventos, para conferir o formato real depois do pareamento."""
    return {"resumo": registro_webhook.resumo(),
            "eventos": registro_webhook.ultimos(limite)}


@app.get("/api/webhook/eventos/{evento_id}")
def payload_do_webhook(evento_id: int,
                       usuario: dict = Depends(auth.requer_tela("CFG_1.1"))):
    """O corpo cru de um evento. É o que se lê depois da primeira mensagem
    real, para saber se o formato bate com o que os parsers supõem."""
    achado = registro_webhook.payload(evento_id)
    if not achado:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    return achado


# ------------------------------------------------------ cadastro (CAD_1.1/1.2)

@app.get("/api/clientes")
def listar_clientes(busca: str = "", pagina: int = 1, por_pagina: int = 50,
                    apenas_ativos: bool = False,
                    usuario: dict = Depends(auth.requer_tela("CAD_1.1"))):
    """CAD_1.1 — os clientes, com busca que entende telefone.

    🚨 A busca não é por igualdade do que foi digitado. `18 99811-6168`,
    `(18) 9811-6168` e `5518998116168` acham a mesma pessoa, porque o termo
    passa pelo normalizador antes de virar consulta. A interpretação volta
    junto na resposta: quem procurou um telefone precisa saber se foi isso que
    o sistema entendeu.
    """
    return cadastro.listar_clientes(busca, pagina, por_pagina, apenas_ativos)


@app.get("/api/clientes/{cliente_id}")
def ver_cliente(cliente_id: int,
                usuario: dict = Depends(auth.requer_tela("CAD_1.1"))):
    achado = cadastro.cliente(cliente_id)
    if not achado:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return achado


@app.get("/api/contatos")
def listar_contatos(busca: str = "", pagina: int = 1, por_pagina: int = 50,
                    apenas_ativos: bool = False,
                    usuario: dict = Depends(auth.requer_tela("CAD_1.2"))):
    return cadastro.listar_contatos(busca, pagina, por_pagina, apenas_ativos)


@app.get("/api/contatos/{contato_id}")
def ver_contato(contato_id: int,
                usuario: dict = Depends(auth.requer_tela("CAD_1.2"))):
    achado = cadastro.contato(contato_id)
    if not achado:
        raise HTTPException(status_code=404, detail="Contato não encontrado.")
    return achado


@app.get("/api/contatos/por-telefone/{numero}")
def contatos_por_telefone(numero: str,
                          usuario: dict = Depends(auth.requer_tela("CAD_1.2"))):
    """Quem responde por um número. É o que o webhook vai usar no passo 4.

    ⚠️ Devolve LISTA. Dez números da base estão em mais de um contato -- um
    deles em oito -- porque são centrais de empresa repetidas no cadastro de
    cada filial. Escolher um arbitrariamente aqui esconderia a ambiguidade de
    quem vai atender.
    """
    return cadastro.por_telefone(numero)


# ---------------------------------------------------------------- sync (CFG_3.1)

@app.get("/api/sync")
def estado_do_sync(usuario: dict = Depends(auth.requer_tela("CFG_3.1"))):
    """CFG_3.1 — o que o banco tem, quando foi a última leitura, e se a API está de pé.

    🚨 As três coisas são perguntas diferentes. "1.050 clientes" não diz nada
    sobre o Harmonit estar respondendo, e é assim que se descobre tarde demais
    que a base parou de atualizar há uma semana.
    """
    return sync_harmonit.resumo()


@app.post("/api/sync/agora")
async def sincronizar_agora(request: Request,
                            usuario: dict = Depends(auth.requer_tela("CFG_3.1"))):
    """O botão "sincronizar agora" do escopo, item 3.

    🚨 `asyncio.to_thread` recebe uma função NORMAL. Com `async def` ele roda a
    corrotina dentro da thread, ninguém a aguarda, e o único sinal é um
    `RuntimeWarning` invisível em produção. `sync_harmonit.executar` é `def`
    de propósito, e é o que torna isso seguro.

    ⚠️ `atendente_id` vai None: o cadastro de atendentes é a CAD_2.1, que ainda
    não existe. A coluna tem FK, então gravar um id inventado quebraria.
    """
    try:
        resultado = await asyncio.to_thread(
            sync_harmonit.executar, "manual", None, None, None)
    except sync_harmonit.SyncJaEmAndamento as e:
        raise HTTPException(status_code=409, detail=str(e))

    if resultado.get("erro"):
        log.warning("req=%s sync manual terminou com erro: %s",
                    request.state.req_id, resultado["erro"])
    return resultado


# ---------------------------------------------------------------- saúde

@app.get("/api/saude")
def saude(request: Request):
    return {
        "ok": True,
        "app": settings.app_nome,
        "ambiente": settings.ambiente,
        "req_id": request.state.req_id,
        "telas_ativas": len(registro_telas.ativas()),
        "banco": banco.saude(),
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
