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
from . import conversas
from . import evolution
from . import informativos
from . import operacao
from . import prompt as prompt_ia
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

    # 🚨 O webhook grava cru e responde 200 rápido; quem interpreta é este
    # laço, lendo a tabela depois. Sem ele a mensagem chega, fica guardada, e
    # não aparece em tela nenhuma -- foi exatamente o estado de 07/08.
    parar_conversas = asyncio.Event()
    tarefa_conversas = asyncio.create_task(conversas.rodar(parar_conversas))

    yield

    parar_vigia.set()
    parar_conversas.set()
    for tarefa in (tarefa_vigia, tarefa_conversas):
        try:
            await asyncio.wait_for(tarefa, timeout=5)
        except asyncio.TimeoutError:
            tarefa.cancel()
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


# ------------------------------------------------ atendimento (ATD_1.1/1.2/1.3)

@app.get("/api/conversas/resumo")
def resumo_das_conversas(usuario: dict = Depends(auth.requer_tela("ATD_1.1"))):
    """🚨 `eventos_pendentes` e `eventos_com_erro` vêm junto de propósito. Sem
    eles, uma fila parada parece "nenhuma mensagem nova" — e é assim que se
    descobre tarde demais que o processamento morreu."""
    return conversas.resumo()


@app.get("/api/conversas")
def listar_conversas(estado: str | None = None, sem_dono: bool = False,
                     minhas: bool = False, busca: str = "",
                     usuario: dict = Depends(auth.requer_tela("ATD_1.1"))):
    return conversas.listar(
        estado=estado, sem_dono=sem_dono, busca=busca,
        atendente_id=_atendente_do_usuario(usuario) if minhas else None)


@app.get("/api/conversas/{conversa_id}")
def ver_conversa(conversa_id: int,
                 usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    achada = conversas.conversa(conversa_id)
    if not achada:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return achada


@app.post("/api/conversas/{conversa_id}/assumir")
def assumir_conversa(conversa_id: int,
                     usuario: dict = Depends(auth.requer_tela("ATD_1.1"))):
    """🚨 Atômico: dois cliques simultâneos, um ganha e o outro é avisado."""
    eu = _atendente_do_usuario(usuario)
    if not eu:
        raise HTTPException(
            status_code=409,
            detail="Sua conta não tem linha em `atendente` -- é a conta do "
                   ".env. Cadastre-se na CAD_2.1 para poder assumir conversa.")
    resultado = conversas.assumir(conversa_id, eu)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


class TransferenciaEntrada(BaseModel):
    time_id: int | None = None
    para_atendente_id: int | None = None
    # ⚠️ `motivo` no banco é vocabulário fechado (CHECK). O que a pessoa
    # escreve é `observacao`, e vai para `transferencia.resumo` -- que é onde o
    # doc manda o resumo da transferência ficar.
    observacao: str | None = Field(default=None, max_length=2000)


class EncerramentoEntrada(BaseModel):
    classificacao_id: int
    comentario: str | None = Field(default=None, max_length=2000)


# ------------------------------------------------------ informativos (ATD_3.1)
#
# 🚨 O canal é irreversível: o que sai daqui alcança cliente de verdade. Nada
# dispara sozinho — o disparo nasce rascunho e só sai por ação explícita.

class DisparoEntrada(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    corpo: str = Field(min_length=1, max_length=4000)
    intervalo_seg: int = Field(default=5, ge=1, le=300)
    teto_por_hora: int = Field(default=200, ge=1, le=2000)


class TesteEntrada(BaseModel):
    telefone: str | None = Field(default=None, max_length=32)


@app.get("/api/informativos/cobertura")
def cobertura_do_informativo(usuario: dict = Depends(auth.requer_tela("ATD_3.1"))):
    """🚨 Medido em 07/08: 369 dos 944 clientes ativos são alcançáveis, e
    **483 estão fora por cadastro incompleto**, não por não usarem WhatsApp.
    Disparar para 369 achando que falou com 944 é o erro que esta tela existe
    para não deixar acontecer."""
    return informativos.cobertura()


@app.get("/api/informativos")
def listar_disparos(usuario: dict = Depends(auth.requer_tela("ATD_3.1"))):
    return informativos.listar()


@app.get("/api/informativos/respostas")
def respostas_do_informativo(usuario: dict = Depends(auth.requer_tela("ATD_3.1"))):
    """Cliente responde boleto. Não vira conversa — mas para de ser invisível."""
    return informativos.respostas_recebidas()


@app.get("/api/informativos/{disparo_id}")
def ver_disparo(disparo_id: int,
                usuario: dict = Depends(auth.requer_tela("ATD_3.1"))):
    achado = informativos.ver(disparo_id)
    if not achado:
        raise HTTPException(status_code=404, detail="Disparo não encontrado.")
    return achado


@app.post("/api/informativos", status_code=201)
def criar_disparo(dados: DisparoEntrada,
                  usuario: dict = Depends(auth.requer_tela("ATD_3.1"))):
    """Cria em RASCUNHO, com a lista de destinos congelada. Não envia nada."""
    return informativos.criar(
        dados.titulo, dados.corpo, criado_por=_atendente_do_usuario(usuario),
        intervalo_seg=dados.intervalo_seg, teto_por_hora=dados.teto_por_hora)


@app.post("/api/informativos/{disparo_id}/teste")
def testar_disparo(disparo_id: int, dados: TesteEntrada,
                   usuario: dict = Depends(auth.requer_tela("ATD_3.1"))):
    """🚨 O "começa com 1" da metodologia. Manda para UM e para."""
    return informativos.enviar_teste(disparo_id, dados.telefone)


@app.post("/api/informativos/{disparo_id}/enviar")
def enviar_disparo(disparo_id: int, quantos: int = 20,
                   usuario: dict = Depends(auth.requer_tela("ATD_3.1"))):
    """Envia o próximo pedaço, respeitando intervalo e teto por hora."""
    return informativos.enviar_lote(disparo_id, quantos)


@app.post("/api/informativos/{disparo_id}/pausar")
def pausar_disparo(disparo_id: int,
                   usuario: dict = Depends(auth.requer_tela("ATD_3.1"))):
    return informativos.pausar(disparo_id)


class RespostaEntrada(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)


@app.post("/api/conversas/{conversa_id}/responder")
def responder_conversa(conversa_id: int, dados: RespostaEntrada,
                       usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """🚨 A ÚNICA rota do sistema que manda mensagem para cliente real.

    O destinatário NÃO é parâmetro: sai da conversa. Não existe caminho para
    escolher para quem enviar, e é isso que impede o painel de virar
    ferramenta de disparo -- que é Fase 2, com decisão própria.
    """
    resultado = conversas.responder(conversa_id, dados.texto,
                                    _atendente_do_usuario(usuario))
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.post("/api/conversas/{conversa_id}/nota")
def anotar_conversa(conversa_id: int, dados: RespostaEntrada,
                    usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Nota interna — fica na conversa e nunca sai para o cliente."""
    resultado = conversas.anotar(conversa_id, dados.texto,
                                 _atendente_do_usuario(usuario))
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.get("/api/fila")
def ver_fila(usuario: dict = Depends(auth.requer_tela("ATD_1.3"))):
    """ATD_1.3 — quem está esperando, por time.

    🚨 O balde "sem triagem" vem primeiro porque a triagem é a IA, que está
    desligada: todas as conversas de hoje têm `time_id` NULL. Agrupar só por
    time faria a tela parecer vazia com gente real esperando.
    """
    return conversas.fila()


@app.post("/api/conversas/{conversa_id}/transferir")
def transferir_conversa(conversa_id: int, dados: TransferenciaEntrada,
                        usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Enquanto a IA não existe, ISTO é a triagem — feita por gente."""
    resultado = conversas.transferir(
        conversa_id, dados.time_id, dados.para_atendente_id, "manual",
        de_atendente_id=_atendente_do_usuario(usuario),
        texto_resumo=dados.observacao)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.post("/api/conversas/{conversa_id}/devolver")
def devolver_conversa(conversa_id: int,
                      usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    resultado = conversas.devolver_para_fila(
        conversa_id, _atendente_do_usuario(usuario))
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.post("/api/conversas/{conversa_id}/encerrar")
def encerrar_conversa(conversa_id: int, dados: EncerramentoEntrada,
                      usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """🚨 Classificar é obrigatório para fechar (escopo, item 11)."""
    resultado = conversas.encerrar(conversa_id, dados.classificacao_id,
                                   dados.comentario)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.get("/api/historico")
def ver_historico(busca: str = "", classificacao_id: int | None = None,
                  usuario: dict = Depends(auth.requer_tela("ATD_5.1"))):
    """ATD_5.1 — conversas encerradas, pesquisáveis por nome ou telefone."""
    return conversas.historico(busca, classificacao_id)


@app.post("/api/conversas/processar")
def processar_agora(usuario: dict = Depends(auth.requer_tela("ATD_1.1"))):
    """O laço já roda a cada 5s; este botão existe para depois de corrigir um
    parser, quando se quer reprocessar sem esperar."""
    return conversas.processar_pendentes()


# ----------------------------------------------- operação (CAD_2.1/2.2, CFG_4.1)
#
# 🚨 Nenhuma rota daqui APAGA. Time, atendente e classificação são apontados
# por `conversa` e `transferencia`: sumir com a linha faz o histórico mentir
# sobre o que aconteceu. O que a tela chama de excluir é `ativo = false`.

@app.exception_handler(operacao.DadoInvalido)
async def _dado_invalido(request: Request, exc: operacao.DadoInvalido):
    """400 com a frase que o usuário lê. A validação mora no módulo, não na
    rota: assim o teste cobre a regra sem subir HTTP."""
    return JSONResponse(status_code=400, content={"detail": str(exc)},
                        headers={"X-Request-Id": getattr(request.state, "req_id", "")})


@app.exception_handler(operacao.EmUso)
async def _em_uso(request: Request, exc: operacao.EmUso):
    return JSONResponse(status_code=409, content={"detail": str(exc)},
                        headers={"X-Request-Id": getattr(request.state, "req_id", "")})


class TimeEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    descricao: str | None = Field(default=None, max_length=1000)
    time_transbordo_id: int | None = None
    ativo: bool = True


class AtendenteEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    login: str = Field(min_length=1, max_length=60)
    email: str | None = Field(default=None, max_length=200)
    perfil: str = "atendimento"
    estado: str = "disponivel"
    max_conversas: int | None = None
    fuso: str = "America/Sao_Paulo"
    ativo: bool = True


class SenhaEntrada(BaseModel):
    # 10 é o mínimo que `operacao.definir_senha` exige; o teto existe pela
    # mesma razão do login: bcrypt em cima de megabyte é trabalho de graça
    # para quem ataca.
    senha: str = Field(min_length=10, max_length=256)


class TimesDoAtendente(BaseModel):
    times: list[int] = []


class FaixaJornada(BaseModel):
    dia_semana: int = Field(ge=0, le=6)
    inicio: str
    fim: str


class JornadaEntrada(BaseModel):
    faixas: list[FaixaJornada] = []


class ClassificacaoEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    exige_comentario: bool = False
    ativo: bool = True
    ordem: int = 0


class PromptEntrada(BaseModel):
    conteudo: str = Field(min_length=50)
    publicar: bool = False


@app.get("/api/operacao/alertas")
def alertas_da_operacao(usuario: dict = Depends(auth.requer_tela("CAD_2.2"))):
    """O que está montado de um jeito que só cobra depois.

    🚨 Três dos sete times vieram do Chatwoot SEM NENHUM MEMBRO. Conversa
    transferida para eles não chega em ninguém, e nada falha para avisar.
    """
    return operacao.alertas()


@app.get("/api/times")
def listar_times(incluir_inativos: bool = False,
                 usuario: dict = Depends(auth.requer_tela("CAD_2.2"))):
    return operacao.listar_times(incluir_inativos)


@app.post("/api/times", status_code=201)
def criar_time(dados: TimeEntrada,
               usuario: dict = Depends(auth.requer_tela("CAD_2.2"))):
    return operacao.criar_time(dados.nome, dados.descricao, dados.time_transbordo_id)


@app.put("/api/times/{time_id}")
def atualizar_time(time_id: int, dados: TimeEntrada,
                   usuario: dict = Depends(auth.requer_tela("CAD_2.2"))):
    return operacao.atualizar_time(time_id, dados.nome, dados.descricao,
                                   dados.time_transbordo_id, dados.ativo)


@app.get("/api/atendentes")
def listar_atendentes(incluir_inativos: bool = False,
                      usuario: dict = Depends(auth.requer_tela("CAD_2.1"))):
    return operacao.listar_atendentes(incluir_inativos)


@app.get("/api/atendentes/{atendente_id}")
def ver_atendente(atendente_id: int,
                  usuario: dict = Depends(auth.requer_tela("CAD_2.1"))):
    achado = operacao.atendente(atendente_id)
    if not achado:
        raise HTTPException(status_code=404, detail="Atendente não encontrado.")
    return achado


@app.post("/api/atendentes", status_code=201)
def criar_atendente(dados: AtendenteEntrada,
                    usuario: dict = Depends(auth.requer_tela("CAD_2.1"))):
    """A conta nasce SEM SENHA e, por isso, sem conseguir entrar.

    ⚠️ `auth.validar_login` recusa `senha_hash IS NULL` antes do bcrypt, então
    conta criada e esquecida não é porta aberta.
    """
    return operacao.criar_atendente(
        dados.nome, dados.login, dados.email, dados.perfil, dados.estado,
        dados.max_conversas, dados.fuso)


@app.put("/api/atendentes/{atendente_id}")
def atualizar_atendente(atendente_id: int, dados: AtendenteEntrada,
                        usuario: dict = Depends(auth.requer_tela("CAD_2.1"))):
    return operacao.atualizar_atendente(
        atendente_id, dados.nome, dados.login, dados.email, dados.perfil,
        dados.estado, dados.max_conversas, dados.ativo, dados.fuso,
        quem_edita=usuario["login"])


@app.post("/api/atendentes/{atendente_id}/senha")
def definir_senha(atendente_id: int, dados: SenhaEntrada,
                  usuario: dict = Depends(auth.requer_tela("CAD_2.1"))):
    return operacao.definir_senha(atendente_id, dados.senha)


@app.put("/api/atendentes/{atendente_id}/times")
def definir_times(atendente_id: int, dados: TimesDoAtendente,
                  usuario: dict = Depends(auth.requer_tela("CAD_2.1"))):
    return operacao.definir_times(atendente_id, dados.times)


@app.put("/api/atendentes/{atendente_id}/jornada")
def definir_jornada(atendente_id: int, dados: JornadaEntrada,
                    usuario: dict = Depends(auth.requer_tela("CAD_2.1"))):
    """🚨 A pausa do almoço é o intervalo ENTRE duas faixas do mesmo dia."""
    return operacao.definir_jornada(
        atendente_id, [f.model_dump() for f in dados.faixas])


@app.get("/api/classificacoes")
def listar_classificacoes(incluir_inativas: bool = False,
                          usuario: dict = Depends(auth.requer_tela("CFG_4.1"))):
    return operacao.listar_classificacoes(incluir_inativas)


@app.post("/api/classificacoes", status_code=201)
def criar_classificacao(dados: ClassificacaoEntrada,
                        usuario: dict = Depends(auth.requer_tela("CFG_4.1"))):
    return operacao.criar_classificacao(dados.nome, dados.exige_comentario,
                                        dados.ordem or None)


@app.put("/api/classificacoes/{classificacao_id}")
def atualizar_classificacao(classificacao_id: int, dados: ClassificacaoEntrada,
                            usuario: dict = Depends(auth.requer_tela("CFG_4.1"))):
    return operacao.atualizar_classificacao(
        classificacao_id, dados.nome, dados.exige_comentario, dados.ativo,
        dados.ordem)


# ------------------------------------------------------------- IA (CFG_2.1)
#
# 🚨 NENHUMA destas rotas fala com modelo nenhum. São texto versionado. O
# motor é o passo 8, e `canal.ia_ligada` continua false nos dois canais.

def _atendente_do_usuario(usuario: dict) -> int | None:
    """O id na tabela `atendente` de quem está logado, quando existe.

    ⚠️ A conta do .env não tem linha na tabela. Autor NULL é honesto: melhor
    "autor desconhecido" do que atribuir a versão a outra pessoa.
    """
    linha = banco.um("SELECT id FROM atendente WHERE lower(login) = lower(%s)",
                     (usuario["login"],))
    return linha["id"] if linha else None


@app.get("/api/ia/prompt")
def estado_do_prompt(usuario: dict = Depends(auth.requer_tela("CFG_2.1"))):
    """🚨 Prompt publicado NÃO significa IA no ar. Quem decide é
    `canal.ia_ligada`, por canal — e vem junto na resposta por isso."""
    return prompt_ia.estado()


@app.get("/api/ia/prompt/sugestao")
def sugestao_de_prompt(usuario: dict = Depends(auth.requer_tela("CFG_2.1"))):
    return {"conteudo": prompt_ia.SUGESTAO_INICIAL}


@app.get("/api/ia/prompt/versoes")
def listar_versoes(usuario: dict = Depends(auth.requer_tela("CFG_2.1"))):
    return prompt_ia.listar()


@app.get("/api/ia/prompt/versoes/{versao_id}")
def ver_versao(versao_id: int,
               usuario: dict = Depends(auth.requer_tela("CFG_2.1"))):
    achado = prompt_ia.ver(versao_id)
    if not achado:
        raise HTTPException(status_code=404, detail="Versão não encontrada.")
    return achado


@app.post("/api/ia/prompt/versoes", status_code=201)
def criar_versao(dados: PromptEntrada,
                 usuario: dict = Depends(auth.requer_tela("CFG_2.1"))):
    try:
        return prompt_ia.criar(dados.conteudo, _atendente_do_usuario(usuario),
                               dados.publicar)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/ia/prompt/versoes/{versao_id}/publicar")
def publicar_versao(versao_id: int,
                    usuario: dict = Depends(auth.requer_tela("CFG_2.1"))):
    """Também é o "voltar para a versão anterior" — publicar a antiga."""
    try:
        return prompt_ia.publicar(versao_id)
    except prompt_ia.SemVersao as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/ia/prompt/montado")
def prompt_montado(versao_id: int | None = None,
                   usuario: dict = Depends(auth.requer_tela("CFG_2.1"))):
    """O texto como a IA receberia, com a camada 5 preenchida do CAD_2.2."""
    try:
        return prompt_ia.montado(versao_id)
    except prompt_ia.SemVersao as e:
        raise HTTPException(status_code=404, detail=str(e))


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
