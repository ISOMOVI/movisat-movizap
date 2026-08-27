"""MoviZap — painel de comunicação da Movisat.

Fase 1: esqueleto. Login, registro de telas, barra de status.
Sem banco ainda -- ver `auth.buscar_usuario`.
"""
import asyncio
import logging
import pathlib
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import (Depends, FastAPI, File, Form, HTTPException, Request,
                     UploadFile, status)
from fastapi.responses import (FileResponse, JSONResponse, RedirectResponse,
                               Response)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth
from . import banco
from . import bitrix
from . import cadastro
from . import canais as registro_canais
from . import chat
from . import conversas
from . import evolution
from . import agenda as agenda_google
from . import enviar as enviar_email
from . import gmail
from . import google_auth
from . import automacao
from . import ia
from . import inicio as tela_inicial
from . import informativos
from . import midia
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


class MascararSegredoDoCaminho(logging.Filter):
    """Tira o segredo do webhook da linha de acesso ANTES de ela ser escrita.

    🚨 O SEGREDO ESTAVA INDO PARA O DISCO 2.527 VEZES POR DIA. Ele vive no
    CAMINHO da URL -- é assim que o Evolution autentica --, e o uvicorn
    registra a linha de requisição de toda chamada. Medido em 12/08: 2.527
    ocorrências em 24 h no journal do usuário, em texto puro, rotacionado e
    guardado. Não era um vazamento pontual; era um vazamento contínuo.

    ⚠️ ISTO NÃO SUBSTITUI A ROTAÇÃO, e não alcança o `access.log` do nginx,
    que registra a mesma linha e exige root para calar.

    ⚠️ O filtro reescreve `record.args`, não a mensagem já formatada: o
    `uvicorn.access` guarda os campos separados e só os junta na hora de
    escrever. Mexer na mensagem final não pegaria nada.
    """

    PREFIXO = "/api/webhook/evolution/"

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple):
            return True
        limpos = tuple(
            self.PREFIXO + "<segredo>"
            if isinstance(a, str) and a.startswith(self.PREFIXO)
            else a
            for a in args
        )
        if limpos != args:
            record.args = limpos
        return True


# Vale para o logger do uvicorn e para o do gunicorn, conforme quem sobe o
# processo -- registrar nos dois é barato e não depende de lembrar qual é.
for _nome in ("uvicorn.access", "gunicorn.access"):
    logging.getLogger(_nome).addFilter(MascararSegredoDoCaminho())

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
    """Quem está logado, e se ele tem VÍNCULO DE ATENDIMENTO.

    🚨 ENTRAR NO PAINEL E PODER ATENDER SÃO COISAS DIFERENTES. Sem vínculo, o
    que a pessoa escrever é gravado com autor NULL -- ela responde o cliente e
    a conversa não sabe dizer quem respondeu. Até 12/08 isso acontecia calado;
    agora a tela inicial diz o que houve, em vez de deixar a pessoa trabalhar
    e o histórico ficar anônimo.
    """
    return {
        "login": usuario["login"],
        "nome": usuario["nome"],
        "owner": usuario["owner"],
        "email": usuario.get("email"),
        "vinculo_atendimento": _atendente_do_usuario(usuario) is not None,
        "telas": registro_telas.do_usuario(usuario),
    }


# ---------------------------------------------------------------- telas

@app.get("/api/telas")
def telas_do_usuario(usuario: dict = Depends(auth.get_usuario)):
    """O menu. O frontend não decide o que aparece -- ele desenha o que vem."""
    return registro_telas.do_usuario(usuario)


@app.get("/api/automacao")
def ver_automacao(usuario: dict = Depends(auth.requer_tela("CFG_5.1"))):
    """CFG_5.1 — o que roda sozinho, por tipo de contato.

    ⚠️ Vem junto `contatos`: quantas pessoas cada tipo alcança hoje. Sem esse
    número, ligar "cliente" parece inofensivo e atinge 1.750 pessoas.

    🚨 `ia_disponivel` É MEDIDO, NÃO ESCRITO. Foi literal `False` até 25/08
    porque o motor não existia; desde 26/08 ele existe (`movizap/ia.py` +
    `movizap/llm/`) e quem responde é o próprio motor -- `False` com o motivo
    quando falta chave ou versão de prompt publicada. `docs/09`, item 4:
    configuração não afirma o que o código não faz, **e também não nega o que
    ele faz**.
    """
    motor = ia.estado()
    return {"tipos": automacao.listar(),
            "ia_disponivel": motor["disponivel"],
            "ia_motivo": motor.get("motivo"),
            "ia_modelo": motor.get("modelo")}


class AutomacaoEntrada(BaseModel):
    boas_vindas_ligado: bool | None = None
    boas_vindas_texto: str | None = None
    ia_ligada: bool | None = None


@app.put("/api/automacao/{relacao}")
def definir_automacao(relacao: str, dados: AutomacaoEntrada,
                      usuario: dict = Depends(auth.requer_tela("CFG_5.1"))):
    r = automacao.definir(relacao, dados.boas_vindas_ligado,
                          dados.boas_vindas_texto, dados.ia_ligada)
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["motivo"])
    return r


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

def _segredo_de_webhook_vale(recebido: str) -> bool:
    """Confere contra o segredo em vigor e, durante rotação, contra o anterior.

    🚨 `compare_digest` NOS DOIS, e sem atalho. Comparar com `==` vazaria o
    tamanho do prefixo certo pelo tempo de resposta -- num endpoint público,
    que aceita quantas tentativas quiserem fazer.

    ⚠️ AS DUAS COMPARAÇÕES SEMPRE ACONTECEM. Escrever
    `vale(atual) or vale(anterior)` faria o `or` curto-circuitar e o tempo de
    resposta passaria a contar quantos segredos estão ativos. É pouca coisa,
    mas é grátis não vazar.

    ⚠️ Segredo vazio nunca vale: `.env` sem a chave não pode abrir o endpoint.
    """
    atual = bool(settings.webhook_segredo) and secrets.compare_digest(
        recebido, settings.webhook_segredo)
    anterior = bool(settings.webhook_segredo_anterior) and secrets.compare_digest(
        recebido, settings.webhook_segredo_anterior)
    return atual or anterior


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
    if not _segredo_de_webhook_vale(segredo):
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
    """A ficha: cadastro, contatos, telefones, últimas conversas e e-mails.

    ⚠️ A ficha passou a levar a algum lugar (25/08). Antes ela mostrava dados
    e acabava ali -- quem abria um cliente para saber "já falamos com essa
    empresa?" tinha de ir para a caixa de entrada e buscar pelo nome.
    """
    achado = cadastro.ficha_do_cliente(cliente_id)
    if not achado:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return achado


@app.get("/api/contatos")
def listar_contatos(busca: str = "", pagina: int = 1, por_pagina: int = 50,
                    apenas_ativos: bool = False, relacoes: str = "",
                    usuario: dict = Depends(auth.requer_tela("CAD_1.2"))):
    """`relacoes` é a lista de chips separada por vírgula, e combina com a
    busca: procurar "silva" entre os fornecedores é uma pergunta só."""
    escolhidas = [r.strip() for r in relacoes.split(",") if r.strip()]
    return cadastro.listar_contatos(busca, pagina, por_pagina, apenas_ativos,
                                    relacoes=escolhidas or None)


@app.get("/api/contatos/{contato_id}")
def ver_contato(contato_id: int,
                usuario: dict = Depends(auth.requer_tela("CAD_1.2"))):
    achado = cadastro.contato(contato_id)
    if not achado:
        raise HTTPException(status_code=404, detail="Contato não encontrado.")
    return achado


class RelacaoEntrada(BaseModel):
    relacao: str


@app.put("/api/contatos/{contato_id}/relacao")
def definir_relacao_contato(contato_id: int, dados: RelacaoEntrada,
                            usuario: dict = Depends(auth.requer_tela("CAD_1.2"))):
    """O que a pessoa é para a Movisat: cliente, fornecedor, técnico, lead…

    🚨 NÃO EXISTE CHAVE DURA QUE DIGA QUEM É FORNECEDOR -- conferido em 12/08.
    Quem classifica é gente. O sync deixou de escrever este campo na migração
    031: ele casa por número e não opina sobre o que a pessoa é.
    """
    resultado = cadastro.definir_relacao(contato_id, dados.relacao)
    if not resultado["ok"]:
        codigo = 404 if "não encontrado" in resultado["motivo"] else 400
        raise HTTPException(status_code=codigo, detail=resultado["motivo"])
    return resultado


class RelacaoEmLote(BaseModel):
    ids: list[int]
    relacao: str


@app.put("/api/contatos/relacao-em-lote")
def definir_relacao_em_lote(dados: RelacaoEmLote,
                            usuario: dict = Depends(auth.requer_tela("CAD_1.2"))):
    """Marca o tipo de vários contatos de uma vez.

    🚨 SEM LOTE A BASE NUNCA FICA HONESTA. 1.750 dos 1.754 contatos dizem
    "cliente" porque até a migração 031 o sync gravava essa palavra literal --
    e ninguém corrige 1.750 linhas uma a uma. É esta rota que destrava o
    interruptor de automação por tipo: ligar boas-vindas para "cliente" com a
    base como está hoje alcançaria quase todo mundo.
    """
    resultado = cadastro.definir_relacao_em_lote(dados.ids, dados.relacao)
    if not resultado["ok"]:
        raise HTTPException(status_code=400, detail=resultado["motivo"])
    return resultado


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

# 🚨 AS ROTAS LITERAIS DE /api/conversas VÊM ANTES DE {conversa_id}.
# Declarada depois, `/api/conversas/buscar-empresa` casa com o parâmetro e
# o FastAPI tenta ler "buscar-empresa" como inteiro: 422, e a gaveta recebe
# um corpo sem `itens` -- "nenhuma empresa" para toda busca, sem erro à
# vista. É a mesma regra que o roteador do Vue já carrega para
# /atendimento/fila, cometida de novo aqui.
@app.get("/api/conversas/{conversa_id}/empresas")
def empresas_da_conversa(conversa_id: int,
                         usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """As empresas que o telefone desta conversa alcança.

    🚨 Vem por rota própria, e não dentro do detalhe da conversa, porque é
    consulta sob demanda: a maioria das conversas tem uma empresa só, e
    carregar o grupo inteiro em toda abertura seria trabalho por nada.
    """
    return conversas.empresas_do_telefone(conversa_id)


@app.get("/api/conversas/buscar-empresa")
def buscar_empresa_para_vincular(
        termo: str = "",
        usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Procura empresa para vincular ao número, de dentro da conversa.

    🚨 EXISTE PORQUE A PERMISSÃO MUDOU. `/api/clientes` é CAD_1.1, que o perfil
    `atendimento` não tem desde 10/08 -- a gaveta tomaria 403 ao buscar. Esta
    rota devolve só o que a ficha mostra, com teto de 10, e não substitui a
    tela de cadastro.

    ⚠️ Termo com menos de 2 caracteres devolve vazio em vez de a base inteira:
    uma letra casaria com quase tudo e a lista não ajudaria ninguém.
    """
    termo = (termo or "").strip()
    if len(termo) < 2:
        return {"itens": []}
    achados = cadastro.listar_clientes(termo, pagina=1, por_pagina=10)
    return {
        "itens": [
            {"id": c["id"], "nome": c["nome"], "documento": c.get("documento"),
             "ativo": c.get("ativo")}
            for c in achados.get("itens", [])
        ],
        "interpretacao": achados.get("interpretacao"),
    }


@app.get("/api/auth/google/disponivel")
def google_disponivel():
    """A tela pergunta antes de desenhar o botão. Rota pública de propósito:
    é o que a tela de login precisa saber ANTES de haver sessão."""
    return {"disponivel": google_auth.configurado()}


@app.get("/api/auth/google/inicio")
def google_inicio():
    if not google_auth.configurado():
        raise HTTPException(status_code=503,
                            detail="Entrada pelo Google não está configurada.")
    return RedirectResponse(google_auth.url_de_entrada(), status_code=302)


def _caixas_do_usuario(usuario: dict) -> list[dict]:
    """As caixas de e-mail de quem está logado — as que ELE conectou.

    🚨 É A BARREIRA DA EML_1.1, E ELA NÃO EXISTIA. Até 25/08 nenhuma rota de
    e-mail filtrava por conta: qualquer pessoa com a tela abria a caixa do
    owner inteira. Não dava erro nem travava o acesso -- funcionava, que é o
    pior jeito de vazar.

    ⚠️ Devolve LISTA porque a tela tem abas: a pessoa pode ter a caixa dela e
    uma compartilhada (o `sac@`) ao mesmo tempo. Lista vazia é resposta
    legítima -- quem nunca conectou caixa nenhuma vê a tela vazia com o
    convite, não um erro.
    """
    eu = _atendente_do_usuario(usuario)
    if not eu:
        return []
    return banco.varios(
        "SELECT id, endereco, nome_exibicao FROM email_conta "
        " WHERE atendente_id = %s AND ativa ORDER BY id", (eu,))


def _caixa_permitida(usuario: dict, conta_id: int | None) -> list[int]:
    """Os ids que a consulta pode tocar, já validando o `conta_id` pedido.

    🚨 Pedir uma caixa que não é sua devolve 404, não 403: dizer "existe, mas
    não é sua" já entrega que aquele endereço está conectado por alguém.
    """
    minhas = [c["id"] for c in _caixas_do_usuario(usuario)]
    if conta_id is None:
        return minhas
    if conta_id not in minhas:
        raise HTTPException(status_code=404, detail="Caixa não encontrada.")
    return [conta_id]


def _exige_mensagem_minha(usuario: dict, mensagem_id: int) -> None:
    """Barra ação sobre mensagem de caixa que não é de quem pede.

    ⚠️ SEPARADO DA LEITURA de propósito: ler já filtra no WHERE, mas as rotas
    de AÇÃO (vincular, marcar lida, baixar anexo) recebem só o id e chamavam o
    módulo direto. Sem este guarda, bastava adivinhar um número.
    """
    achou = banco.um(
        "SELECT 1 AS ok FROM email_mensagem WHERE id = %s AND conta_id = ANY(%s)",
        (mensagem_id, _caixa_permitida(usuario, None)))
    if not achou:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada.")


@app.get("/api/email/caixas")
def email_caixas(usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    """As abas da tela: uma por caixa que a pessoa conectou."""
    return {"caixas": _caixas_do_usuario(usuario)}


@app.get("/api/email/marcadores")
def email_marcadores(conta_id: int | None = None,
                     usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    contas = _caixa_permitida(usuario, conta_id)
    if not contas:
        return {"marcadores": []}
    return {"marcadores": banco.varios(
        """SELECT m.id, m.id_externo, m.nome, m.natureza,
                  (SELECT count(*) FROM email_mensagem_marcador mm
                    WHERE mm.marcador_id = m.id) AS quantidade
             FROM email_marcador m
            WHERE m.conta_id = ANY(%s)
            ORDER BY m.natureza, m.nome""", (contas,))}


@app.get("/api/email/mensagens")
def email_mensagens(marcador: str = "", busca: str = "", limite: int = 60,
                    conta_id: int | None = None,
                    usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    """A lista da caixa.

    ⚠️ SPAM e TRASH nunca entram: ninguém quer lixeira num painel de
    atendimento, e filtrar na tela deixaria o dado passando pela rede à toa.

    🚨 SÓ AS CAIXAS DE QUEM PEDE. Sem `conta_id`, todas as dele -- nunca as
    dos outros. Ver `_caixas_do_usuario`.
    """
    contas = _caixa_permitida(usuario, conta_id)
    if not contas:
        return {"mensagens": []}
    condicoes = ["NOT e.arquivada", "e.conta_id = ANY(%s)"]
    params: list = [contas]

    # 🚨 O PARÂMETRO EXISTIA E ERA IGNORADO. A tela mandava `?marcador=SENT` e
    # recebia a caixa de entrada -- defeito que parece funcionamento, porque a
    # lista muda de qualquer jeito quando chega mensagem nova.
    if marcador.strip():
        condicoes.append(
            "EXISTS (SELECT 1 FROM email_mensagem_marcador mm "
            "          JOIN email_marcador mk ON mk.id = mm.marcador_id "
            "         WHERE mm.mensagem_id = e.id AND mk.id_externo = %s)")
        params.append(marcador.strip())

    if busca.strip():
        condicoes.append("(e.assunto ILIKE %s OR e.remetente ILIKE %s)")
        params += [f"%{busca.strip()}%"] * 2
    params.append(limite)
    return {"mensagens": banco.varios(
        f"""SELECT e.id, e.remetente, e.remetente_nome, e.assunto, e.enviado_em,
                   e.tem_anexo, e.lida, e.estrela, e.conta_id,
                   c.nome AS cliente_nome
              FROM email_mensagem e
              LEFT JOIN cliente c ON c.id = e.cliente_id
             WHERE {' AND '.join(condicoes)}
             ORDER BY e.enviado_em DESC NULLS LAST
             LIMIT %s""", tuple(params))}


@app.get("/api/email/fio")
def email_fio(thread: str,
              usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    """As mensagens do mesmo fio de conversa.

    🚨 `thread_externa` É COLUNA DESDE A MIGRAÇÃO 014 E NUNCA FOI USADA. Uma
    troca de seis e-mails virava seis linhas idênticas na lista, sem ninguém
    saber que eram a mesma conversa -- e responder a mensagem errada de um fio
    é como se perde contexto com o cliente.

    ⚠️ Escopada pela caixa, como toda rota de e-mail: fio de caixa alheia não
    é fio nenhum.

    ⚠️ ROTA ANTES DE `/{mensagem_id}` DE PROPÓSITO. O FastAPI casa na ordem de
    declaração: depois dela, "fio" seria lido como id e daria 422.
    """
    contas = _caixa_permitida(usuario, None)
    if not contas or not thread.strip():
        return {"mensagens": []}
    return {"mensagens": banco.varios(
        """SELECT id, remetente, remetente_nome, assunto, enviado_em, lida
             FROM email_mensagem
            WHERE thread_externa = %s AND conta_id = ANY(%s)
            ORDER BY enviado_em NULLS LAST""", (thread.strip(), contas))}


@app.get("/api/email/mensagens/{mensagem_id}")
def email_mensagem(mensagem_id: int,
                   usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    # 🚨 A CAIXA ENTRA NO WHERE, não numa conferência depois: mensagem de
    # caixa alheia é "não encontrada", e não "existe mas não é sua".
    linha = banco.um(
        """SELECT e.*, c.nome AS cliente_nome
             FROM email_mensagem e
             LEFT JOIN cliente c ON c.id = e.cliente_id
            WHERE e.id = %s AND e.conta_id = ANY(%s)""",
        (mensagem_id, _caixa_permitida(usuario, None)))
    if not linha:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada.")
    # `bruto` nunca vai para a tela: ela desenha com texto/html.
    linha.pop("bruto", None)
    linha["bitrix"] = (None if linha.get("cliente_id")
                       else bitrix.observacao(email=linha.get("remetente")))
    return linha


class VinculoEmail(BaseModel):
    cliente_id: int


class EmailNovo(BaseModel):
    para: str
    assunto: str
    corpo: str
    # Qual caixa envia. Opcional só quando a pessoa tem uma caixa só.
    conta_id: int | None = None
    responder_a: int | None = None
    cc: str | None = None
    cco: str | None = None
    html: str | None = None
    anexos: list[str] | None = None


class Assinatura(BaseModel):
    html: str = ""


@app.post("/api/email/mensagens/{mensagem_id}/vincular")
def email_vincular(mensagem_id: int, corpo: VinculoEmail,
                   usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    """Diz de quem é o remetente — e o cadastro cresce pelo uso."""
    _exige_mensagem_minha(usuario, mensagem_id)
    r = gmail.vincular(mensagem_id, corpo.cliente_id)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("motivo"))
    return r


@app.post("/api/email/anexo")
async def email_anexo(arquivo: UploadFile = File(...),
                      usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    """Sobe um anexo de rascunho e devolve o ID que o envio vai usar.

    🚨 A tela recebe um ID, nunca um caminho. Se ela mandasse caminho no
    envio, `../../.env` viraria anexo e o e-mail sairia com o segredo dentro.
    """
    try:
        return enviar_email.guardar_anexo(arquivo.filename or "arquivo",
                                          await arquivo.read())
    except enviar_email.EnvioRecusado as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/email/enviar")
def email_enviar(corpo: EmailNovo,
                 usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    """Manda UMA mensagem, do endereço do atendente.

    🚨 E-MAIL ENVIADO NÃO VOLTA. Não existe rota que receba lista de
    destinatários -- disparo é outro produto, com outra decisão, como já vale
    para o WhatsApp.
    """
    # 🚨 O `LIMIT 1` QUE ESTAVA AQUI ERA UMA BOMBA-RELÓGIO. Com uma caixa só
    # ele acertava sempre; com a segunda, TODO e-mail sairia pela primeira --
    # calado, e o destinatário responderia para o endereço errado. Agora a
    # caixa é escolhida, e escolha inválida é 404, nunca "pega a primeira".
    # ⚠️ A CAIXA PEDIDA É CONFERIDA PRIMEIRO. Se a ordem fosse a inversa, quem
    # não tem caixa nenhuma e pedisse a de outro receberia "você não tem caixa
    # conectada" -- uma resposta sobre ELE, quando a pergunta era sobre a caixa
    # alheia. `_caixa_permitida` responde 404, que é o certo: para quem pede,
    # aquela caixa não existe.
    if corpo.conta_id is not None:
        conta_id = _caixa_permitida(usuario, corpo.conta_id)[0]
    else:
        minhas = _caixas_do_usuario(usuario)
        if not minhas:
            raise HTTPException(
                status_code=409,
                detail="Você não tem caixa conectada. Conecte uma em E-mail.")
        if len(minhas) > 1:
            raise HTTPException(
                status_code=400,
                detail="Você tem mais de uma caixa: diga por qual enviar.")
        conta_id = minhas[0]["id"]
    try:
        return enviar_email.enviar(
            conta_id=conta_id, para=corpo.para, assunto=corpo.assunto,
            corpo=corpo.corpo, atendente_id=_atendente_do_usuario(usuario),
            responder_a=corpo.responder_a, cc=corpo.cc, cco=corpo.cco,
            html=corpo.html, anexos=corpo.anexos)
    except enviar_email.EnvioRecusado as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/eu/assinatura")
def ver_assinatura(usuario: dict = Depends(auth.get_usuario)):
    eu = _atendente_do_usuario(usuario)
    if not eu:
        return {"html": ""}
    linha = banco.um(
        "SELECT assinatura_html, assinatura_imagem FROM atendente WHERE id = %s",
        (eu,))
    caminho = (linha or {}).get("assinatura_imagem")
    # ⚠️ CONFERE O DISCO. Coluna apontando para arquivo que sumiu faria a tela
    # dizer "imagem ativa" e o e-mail sair sem ela -- `enviar._assinatura()` já
    # faz a mesma conferência, pela mesma razão.
    tem_imagem = bool(caminho and pathlib.Path(caminho).is_file())
    return {"html": (linha or {}).get("assinatura_html") or "",
            "tem_imagem": tem_imagem,
            "imagem_nome": pathlib.Path(caminho).name if tem_imagem else None}


# ⚠️ Assinatura é imagem pequena por natureza -- logo, não banner. 2 MB já é
# generoso, e o e-mail carrega o arquivo INTEIRO em toda mensagem enviada.
TETO_ASSINATURA = 2 * 1024 * 1024
PASTA_ASSINATURAS = pathlib.Path("/home/claude/movizap_assinaturas")


@app.post("/api/eu/assinatura/imagem")
async def subir_assinatura_imagem(
        arquivo: UploadFile = File(...),
        usuario: dict = Depends(auth.get_usuario)):
    """Sobe a imagem da assinatura de quem está logado.

    🚨 METADE DISTO JÁ EXISTIA E NINGUÉM PODIA USAR. `atendente.assinatura_imagem`
    existe desde a migração 017 e `enviar._assinatura()` já lê a coluna, confere
    o arquivo no disco e embute por CID -- faltava só o caminho para pôr o
    arquivo lá.

    🚨 O CAMINHO NUNCA VEM DA TELA. O nome do arquivo é do usuário e vira só o
    nome-base; o diretório é nosso, por atendente. Se a tela mandasse caminho,
    `../../.env` viraria assinatura -- é a mesma razão pela qual o anexo de
    rascunho devolve um id.

    ⚠️ GUARDA O CAMINHO, NUNCA OS BYTES (decisão da 017): bytes no banco
    engordam backup e dump para sempre.
    """
    eu = _atendente_do_usuario(usuario)
    if not eu:
        raise HTTPException(status_code=409,
                            detail="Sua conta não tem linha em `atendente`.")

    tipo = (arquivo.content_type or "").lower()
    if not tipo.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="A assinatura tem de ser uma imagem (PNG ou JPG).")

    dados = await arquivo.read()
    if not dados:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(dados) > TETO_ASSINATURA:
        raise HTTPException(
            status_code=400,
            detail=f"A imagem passa de {TETO_ASSINATURA // (1024 * 1024)} MB. "
                   f"Assinatura é logo, não banner.")

    seguro = pathlib.Path((arquivo.filename or "assinatura").replace("\\", "/")).name
    pasta = PASTA_ASSINATURAS / str(eu)
    pasta.mkdir(parents=True, exist_ok=True)
    # Uma imagem por pessoa: a anterior sai junto, senão o disco acumula
    # assinatura velha que ninguém vai procurar.
    for antigo in pasta.iterdir():
        antigo.unlink(missing_ok=True)
    caminho = pasta / seguro
    caminho.write_bytes(dados)

    banco.executar(
        "UPDATE atendente SET assinatura_imagem = %s, atualizado_em = now() "
        " WHERE id = %s", (str(caminho), eu))
    return {"ok": True, "nome": seguro, "tamanho": len(dados)}


@app.delete("/api/eu/assinatura/imagem")
def tirar_assinatura_imagem(usuario: dict = Depends(auth.get_usuario)):
    """Volta para a assinatura em HTML."""
    eu = _atendente_do_usuario(usuario)
    if not eu:
        raise HTTPException(status_code=409,
                            detail="Sua conta não tem linha em `atendente`.")
    linha = banco.um("SELECT assinatura_imagem FROM atendente WHERE id = %s",
                     (eu,))
    if linha and linha["assinatura_imagem"]:
        pathlib.Path(linha["assinatura_imagem"]).unlink(missing_ok=True)
    banco.executar(
        "UPDATE atendente SET assinatura_imagem = NULL, atualizado_em = now() "
        " WHERE id = %s", (eu,))
    return {"ok": True}


@app.put("/api/eu/assinatura")
def salvar_assinatura(dados: Assinatura,
                      usuario: dict = Depends(auth.get_usuario)):
    """A assinatura é de quem está logado — ninguém edita a de outro.

    ⚠️ A do Gmail não se aplica a envio por API: ele a insere no compositor da
    web. Sem esta, o e-mail sai pelado.
    """
    eu = _atendente_do_usuario(usuario)
    if not eu:
        raise HTTPException(status_code=409,
                            detail="Sua conta não tem linha em `atendente`.")
    banco.executar(
        "UPDATE atendente SET assinatura_html = %s, atualizado_em = now() "
        " WHERE id = %s", (dados.html or None, eu))
    return {"ok": True}


@app.get("/api/email/mensagens/{mensagem_id}/anexo/{indice}")
def email_baixar_anexo(mensagem_id: int, indice: int,
                       usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    """Baixa um anexo recebido, buscando no Gmail na hora.

    🚨 PASSA PELA API, NÃO POR LINK DIRETO. O anexo é documento de cliente:
    boleto, contrato, foto de avaria. Servir por URL pública deixaria o link
    vazar no histórico do navegador, no print e no grupo de WhatsApp. Aqui vale
    a mesma permissão da tela de e-mail.

    ⚠️ Nada é gravado em disco: os bytes vêm do Google e vão para o navegador.
    """
    _exige_mensagem_minha(usuario, mensagem_id)
    try:
        achado = gmail.anexo(mensagem_id, indice)
    except gmail.GmailIndisponivel as e:
        raise HTTPException(status_code=503, detail=str(e))
    if not achado["ok"]:
        raise HTTPException(status_code=404, detail=achado["motivo"])

    return Response(
        content=achado["dados"],
        media_type=achado["mime"],
        headers={
            # ⚠️ `attachment` com filename entre aspas: nome com espaço vira
            # dois cabeçalhos sem isso, e o arquivo baixa truncado no nome.
            "Content-Disposition":
                f'attachment; filename="{achado["nome"]}"',
        },
    )


@app.post("/api/email/mensagens/{mensagem_id}/lida")
def email_marcar_lida(mensagem_id: int,
                      usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    _exige_mensagem_minha(usuario, mensagem_id)
    try:
        return gmail.marcar_lida(mensagem_id)
    except gmail.GmailIndisponivel as e:
        raise HTTPException(status_code=503, detail=str(e))


class AcaoEmLote(BaseModel):
    ids: list[int]
    # 'lida' | 'nao_lida' | 'estrela' | 'sem_estrela' | 'arquivar' | 'desarquivar'
    acao: str


# ⚠️ Teto do lote: a tela oferece "selecionar tudo", e tudo pode ser a caixa
# inteira. Cada item é uma chamada ao Gmail -- 500 seria meio minuto preso
# numa requisição.
TETO_LOTE_EMAIL = 100

_ACOES_EMAIL = {
    "lida": lambda i: gmail.marcar_lida(i),
    "nao_lida": lambda i: gmail.marcar_nao_lida(i),
    "estrela": lambda i: gmail.estrela(i, True),
    "sem_estrela": lambda i: gmail.estrela(i, False),
    "arquivar": lambda i: gmail.arquivar(i, True),
    "desarquivar": lambda i: gmail.arquivar(i, False),
}


@app.post("/api/email/mensagens/{mensagem_id}/estrela")
def email_estrela(mensagem_id: int, ligada: bool = True,
                  usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    """Põe ou tira a estrela — sem consentimento novo, o escopo já cobre."""
    _exige_mensagem_minha(usuario, mensagem_id)
    try:
        return gmail.estrela(mensagem_id, ligada)
    except gmail.GmailIndisponivel as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/api/email/mensagens/{mensagem_id}/nao-lida")
def email_nao_lida(mensagem_id: int,
                   usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    """O "volto nisso depois". Sem ele, abrir por engano é irreversível."""
    _exige_mensagem_minha(usuario, mensagem_id)
    try:
        return gmail.marcar_nao_lida(mensagem_id)
    except gmail.GmailIndisponivel as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/api/email/lote")
def email_lote(dados: AcaoEmLote,
               usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    """Aplica a mesma ação a várias mensagens — o "selecionar" da tela.

    🚨 UM ERRO NÃO DERRUBA O LOTE. Cada item é uma chamada ao Gmail, e uma
    falhar (token expirado, mensagem apagada do outro lado) não pode fazer as
    outras 40 não acontecerem. A resposta diz quantas foram e quantas não --
    silêncio aqui vira "marquei e não pegou".

    🚨 A DONA DA CAIXA É CONFERIDA ITEM A ITEM. Sem isso, um id alheio no meio
    de uma lista de ids meus passaria despercebido.
    """
    if dados.acao not in _ACOES_EMAIL:
        raise HTTPException(status_code=400,
                            detail=f"Ação desconhecida: {dados.acao!r}.")
    ids = sorted({int(i) for i in (dados.ids or []) if i})
    if not ids:
        raise HTTPException(status_code=400,
                            detail="Nenhuma mensagem selecionada.")
    if len(ids) > TETO_LOTE_EMAIL:
        raise HTTPException(
            status_code=400,
            detail=f"São {len(ids)} mensagens. O lote vai até "
                   f"{TETO_LOTE_EMAIL} por vez.")

    minhas = _caixa_permitida(usuario, None)
    feitas, falhas = 0, 0
    for mensagem_id in ids:
        dona = banco.um(
            "SELECT 1 AS ok FROM email_mensagem "
            " WHERE id = %s AND conta_id = ANY(%s)", (mensagem_id, minhas))
        if not dona:
            falhas += 1
            continue
        try:
            _ACOES_EMAIL[dados.acao](mensagem_id)
            feitas += 1
        except Exception:                                     # noqa: BLE001
            log.exception("lote de e-mail: %s falhou em %s",
                          dados.acao, mensagem_id)
            falhas += 1
    return {"ok": True, "pedidas": len(ids), "feitas": feitas, "falhas": falhas}


@app.post("/api/email/ler")
def email_ler(usuario: dict = Depends(auth.requer_tela("EML_1.1"))):
    """Busca o que ainda não temos. Devolve FLUXO, não estoque."""
    try:
        return gmail.ler()
    except gmail.GmailIndisponivel as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/email/autorizar")
def email_autorizar(usuario: dict = Depends(auth.requer_tela("CFG_1.1"))):
    """Pede consentimento para LER a caixa. Só o owner, e só de propósito."""
    if not google_auth.configurado():
        raise HTTPException(status_code=503, detail="Google não configurado.")
    return {"url": google_auth.url_da_caixa()}


@app.get("/api/auth/google/callback")
def google_callback(code: str = "", state: str = "", error: str = ""):
    """Volta do Google e entrega a sessão à tela.

    🚨 O token vai no FRAGMENTO da URL (`#t=`), não na query. Fragmento não é
    enviado ao servidor nem entra em log de acesso do nginx; a tela o lê e
    limpa a barra de endereços em seguida.
    """
    destino = f"https://{settings.dominio}/login"
    if error or not code:
        return RedirectResponse(f"{destino}#erro=Entrada+cancelada", status_code=302)
    from urllib.parse import quote

    # 🚨 O MESMO callback serve aos dois fluxos -- o Google só aceita uma URI
    # de redirecionamento por cliente. Quem diz qual é o `state`: o de caixa
    # tem tipo próprio, e autorizar caixa NÃO cria sessão.
    if google_auth._e_state_de_caixa(state):
        try:
            caixa = google_auth.conectar_caixa(code, state)
        except google_auth.GoogleRecusado as e:
            return RedirectResponse(f"https://{settings.dominio}/config/canais"
                                    f"#erro={quote(str(e))}", status_code=302)
        return RedirectResponse(f"https://{settings.dominio}/config/canais"
                                f"#ok={quote(caixa['endereco'])}", status_code=302)

    try:
        resultado = google_auth.entrar(code, state)
    except google_auth.GoogleRecusado as e:
        return RedirectResponse(f"{destino}#erro={quote(str(e))}", status_code=302)
    return RedirectResponse(f"{destino}#t={resultado['token']}", status_code=302)


@app.get("/api/agenda/hoje")
def agenda_de_hoje(usuario: dict = Depends(auth.requer_tela("INI_1.1"))):
    """Os compromissos de hoje.

    🚨 ROTA SEPARADA DE PROPÓSITO. Se estivesse dentro de `/api/inicio`, uma
    falha do Google -- ou o escopo ainda não concedido -- derrubaria a tela
    inicial inteira. Assim a agenda some e o resto continua.
    """
    return agenda_google.hoje()


@app.get("/api/inicio")
def estado_inicial(usuario: dict = Depends(auth.requer_tela("INI_1.1"))):
    """INI_1.1 — o que precisa de gente agora, e o que já foi concluído.

    🚨 CANAIS SÓ PARA OWNER. Até 25/08 esta rota devolvia o estado dos canais,
    a fila técnica e o alcance do cadastro para QUALQUER perfil -- enquanto a
    CFG_1.1, que mostra o mesmo, é tela de owner desde sempre. A tela inicial
    era a porta dos fundos da permissão. Quem não é owner recebe, no lugar, a
    explicação do próprio acesso (`configuracao`).
    """
    return tela_inicial.resumo(_atendente_do_usuario(usuario),
                               owner=bool(usuario.get("owner")))


@app.get("/api/conversas/resumo")
def resumo_das_conversas(usuario: dict = Depends(auth.requer_tela("ATD_1.1"))):
    """🚨 `eventos_pendentes` e `eventos_com_erro` vêm junto de propósito. Sem
    eles, uma fila parada parece "nenhuma mensagem nova" — e é assim que se
    descobre tarde demais que o processamento morreu."""
    return conversas.resumo()


@app.get("/api/conversas")
def listar_conversas(estado: str | None = None, sem_dono: bool = False,
                     minhas: bool = False, busca: str = "",
                     relacoes: str = "",
                     usuario: dict = Depends(auth.requer_tela("ATD_1.1"))):
    """A lista da caixa: conversa direta e grupo juntos, como no WhatsApp.

    `relacoes` é a lista de chips separada por vírgula. `sem_cadastro` entra
    junto com os valores de `contato.relacao` e quer dizer outra coisa: a
    conversa sem contato nenhum. Ver `conversas.listar`.
    """
    escolhidas = [r.strip() for r in relacoes.split(",") if r.strip()]
    return conversas.listar(
        estado=estado, sem_dono=sem_dono, busca=busca,
        relacoes=escolhidas or None,
        atendente_id=_atendente_do_usuario(usuario) if minhas else None)


class ConversaNova(BaseModel):
    numero: str
    texto: str
    canal_id: int | None = None


@app.post("/api/conversas/nova")
def iniciar_conversa(dados: ConversaNova,
                     usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """O botão `+`: falar primeiro com quem ainda não escreveu.

    🚨 O CANAL PADRÃO É O DE ATENDIMENTO, por definição (decisão do usuário em
    25/08). O outro canal é o de informativos, e mensagem de atendimento não
    sai por lá.

    ⚠️ Recusa com 409 e um corpo que a tela sabe ler: quando o número não tem
    WhatsApp, vem `sem_whatsapp: true` para a tela mostrar o aviso certo em
    vez de um erro genérico.
    """
    canal_id = dados.canal_id
    if canal_id is None:
        canal = banco.um(
            "SELECT id FROM canal WHERE tipo = 'atendimento' AND ativo "
            " ORDER BY id LIMIT 1")
        if not canal:
            raise HTTPException(status_code=503,
                                detail="Nenhum canal de atendimento ativo.")
        canal_id = canal["id"]

    r = conversas.iniciar_conversa(
        canal_id, dados.numero, dados.texto, _atendente_do_usuario(usuario))
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=r)
    return r


@app.get("/api/midia/{midia_id}")
def baixar_midia(midia_id: int,
                 usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """O arquivo que o cliente mandou.

    🚨 PASSA PELA API, não pelo nginx. Servir a pasta direto deixaria qualquer
    um com o link ver anexo de cliente sem token nenhum -- e o link vaza no
    histórico do navegador, no print, no grupo de WhatsApp. Aqui vale a mesma
    permissão da tela de conversa.

    ⚠️ `Content-Disposition: attachment` é o que faz o botão "baixar" baixar
    em vez de abrir. A tela mostra a imagem por outro caminho (`?ver=1`).
    """
    linha = midia.arquivo(midia_id)
    if not linha:
        raise HTTPException(status_code=404, detail="Mídia não encontrada.")
    return FileResponse(
        linha["caminho"],
        media_type=linha["mime"] or "application/octet-stream",
        filename=midia.nome_para_baixar(linha),
    )


@app.get("/api/midia/{midia_id}/ver")
def ver_midia(midia_id: int,
              usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """A mesma mídia, para aparecer DENTRO da conversa em vez de baixar."""
    linha = midia.arquivo(midia_id)
    if not linha:
        raise HTTPException(status_code=404, detail="Mídia não encontrada.")
    return FileResponse(linha["caminho"],
                        media_type=linha["mime"] or "application/octet-stream")


@app.get("/api/conversas/{conversa_id}")
def ver_conversa(conversa_id: int,
                 usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    achada = conversas.conversa(conversa_id)
    if not achada:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return achada


@app.get("/api/conversas/{conversa_id}/mensagens")
def mensagens_anteriores(conversa_id: int, antes_de: int,
                         limite: int = conversas.JANELA_ANTERIORES,
                         usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """A página anterior de mensagens — o "carregar anteriores" do topo.

    ⚠️ `antes_de` é OBRIGATÓRIO. Sem ele esta rota devolveria a mesma coisa
    que abrir a conversa, e viraria um segundo caminho para o mesmo dado --
    dois caminhos para o mesmo dado é como eles divergem.

    🚨 O teto do `limite` é da ROTA, não da tela. Sem ele, `?limite=999999`
    devolveria a conversa inteira num pedido, que é exatamente o que a
    paginação existe para evitar.
    """
    limite = max(1, min(limite, conversas.JANELA_ANTERIORES))
    anteriores = conversas.mensagens(conversa_id, limite=limite,
                                     antes_de=antes_de)
    topo = anteriores[0]["id"] if anteriores else antes_de
    return {"mensagens": anteriores,
            "tem_anteriores": conversas.tem_anteriores(conversa_id, topo)}


@app.get("/api/conversas/{conversa_id}/buscar")
def buscar_na_conversa(conversa_id: int, termo: str = "",
                       usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Onde, DENTRO desta conversa, alguém disse isso.

    🚨 É OUTRA PERGUNTA QUE A BUSCA DA LISTA. Lá é "com quem eu falei"; aqui é
    "onde ele disse isso". Por isso são duas rotas e dois campos na tela.

    ⚠️ Subiu do navegador para cá em 25/08, junto com a paginação: a busca
    antiga só via o que estava carregado, e com a tela abrindo em 60 ela
    passaria a não achar o que existe.
    """
    achados = conversas.buscar_na_conversa(conversa_id, termo)
    # 🚨 O LIMITE PRECISA APARECER. Devolver 200 acertos calados quando há 400
    # é a mesma mentira por omissão que o teto de 1.000 fazia com as
    # mensagens: quem procura conclui que achou tudo. A tela diz que está
    # vendo os primeiros.
    return {"achados": achados,
            "limitado": len(achados) >= conversas.TETO_ACHADOS_NA_CONVERSA,
            "teto": conversas.TETO_ACHADOS_NA_CONVERSA}


class Vinculo(BaseModel):
    cliente_id: int | None = None
    contato_id: int | None = None


@app.post("/api/conversas/{conversa_id}/vincular")
def vincular_conversa(conversa_id: int, corpo: Vinculo,
                      usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Diz de quem é este número, do painel lateral.

    Fica em ATD_1.2 e não em CAD_1.2 de propósito: quem descobre de quem é o
    número é quem está atendendo, na hora da conversa.
    """
    resultado = conversas.vincular(conversa_id, corpo.cliente_id, corpo.contato_id)
    if not resultado.get("ok"):
        raise HTTPException(status_code=400, detail=resultado.get("motivo"))
    return resultado


@app.post("/api/conversas/{conversa_id}/desvincular")
def desvincular_conversa(conversa_id: int,
                         usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    resultado = conversas.desvincular(conversa_id)
    if not resultado.get("ok"):
        raise HTTPException(status_code=404, detail=resultado.get("motivo"))
    return resultado


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
    # Opcional desde 11/08: encerrar não depende mais de classificar.
    classificacao_id: int | None = None
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


def _exige_estar_na_conversa(conversa_id: int, usuario: dict) -> int:
    """Devolve o id do atendente, ou recusa quem está de fora da conversa.

    🚨 A TRAVA É AQUI, NÃO NO BOTÃO. Esconder a ação na tela não é permissão --
    a rota continua respondendo a quem a chamar direto. A metodologia é
    explícita: "permissão vive no backend, em toda rota".

    ⚠️ 409 e não 403: não é falta de permissão de TELA (quem chegou aqui tem
    `ATD_1.2`), é estado errado -- a pessoa não está nesta conversa. E o texto
    diz o que fazer, porque "proibido" sem saída vira chamado.
    """
    eu = _atendente_do_usuario(usuario)
    if not eu:
        raise HTTPException(
            status_code=409,
            detail="Sua conta não tem vínculo de atendimento. Procure o "
                   "administrador do sistema.")
    if not conversas.esta_na_conversa(conversa_id, eu):
        raise HTTPException(
            status_code=409,
            detail="Você não está nesta conversa. Use Entrar (ou Assumir, se "
                   "ela estiver sem dono) para poder agir.")
    return eu


@app.post("/api/conversas/{conversa_id}/entrar")
def entrar_na_conversa(conversa_id: int,
                       usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Entra como participante numa conversa que já tem dono.

    Não existia caminho para isto: `convidar` chama outra pessoa e `assumir` só
    vale para conversa sem dono. Quem saía não conseguia voltar.
    """
    eu = _atendente_do_usuario(usuario)
    if not eu:
        raise HTTPException(
            status_code=409,
            detail="Sua conta não tem vínculo de atendimento. Procure o "
                   "administrador do sistema.")
    resultado = conversas.entrar(conversa_id, eu)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


class RespostaEntrada(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)
    # Citar uma mensagem DESTA conversa. O backend recusa citar de fora: a
    # chave carrega o `remoteJid` da conversa dela.
    citando_id: int | None = None


@app.post("/api/conversas/{conversa_id}/responder")
def responder_conversa(conversa_id: int, dados: RespostaEntrada,
                       usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Responde o cliente nesta conversa, opcionalmente citando uma mensagem.

    ⚠️ O destinatário não é parâmetro: sai da conversa. Isso não é mais uma
    trava de política -- a regra de "não é caixa de disparo" caiu em 25/08 --,
    é o desenho desta rota. Para falar com quem ainda não escreveu existe
    `/api/conversas/nova`; para repassar, `/api/conversas/encaminhar`.
    """
    eu = _exige_estar_na_conversa(conversa_id, usuario)
    resultado = conversas.responder(conversa_id, dados.texto, eu,
                                    citando_id=dados.citando_id)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.post("/api/conversas/{conversa_id}/arquivo")
async def enviar_arquivo(conversa_id: int,
                         arquivo: UploadFile = File(...),
                         legenda: str = Form(""),
                         interna: bool = Form(False),
                         usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Manda um arquivo para o cliente, ou anexa numa nota interna.

    ⚠️ `interna=true` NÃO envia nada: o arquivo é guardado e vira nota. Os dois
    caminhos existem por decisão do usuário em 12/08 -- eu tinha bloqueado
    anexo em nota por conta própria, e o argumento estava errado.

    🚨 O DESTINATÁRIO NÃO É PARÂMETRO: sai da conversa, como no texto. Não
    existe caminho para escolher para quem enviar, e é isso que impede o painel
    de virar ferramenta de disparo.

    ⚠️ O TETO É CONFERIDO LENDO, não pelo `content-length` que o navegador
    manda -- cabeçalho é o que o cliente diz, não o que ele envia. Lê-se em
    pedaços e para no primeiro byte acima do teto, em vez de carregar 500 MB
    na memória para depois recusar.
    """
    eu = _exige_estar_na_conversa(conversa_id, usuario)

    teto = conversas.TETO_ARQUIVO
    pedacos, total = [], 0
    while True:
        pedaco = await arquivo.read(256 * 1024)
        if not pedaco:
            break
        total += len(pedaco)
        if total > teto:
            raise HTTPException(
                status_code=413,
                detail=f"Arquivo acima de {conversas.TETO_ARQUIVO_MB} MB.")
        pedacos.append(pedaco)
    dados = b"".join(pedacos)

    mime = arquivo.content_type or "application/octet-stream"
    nome = arquivo.filename or "arquivo"
    resultado = (
        conversas.anotar_com_arquivo(conversa_id, dados, mime, nome, legenda, eu)
        if interna
        else conversas.responder_com_arquivo(conversa_id, dados, mime, nome,
                                             legenda, eu))
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.post("/api/conversas/{conversa_id}/nota")
def anotar_conversa(conversa_id: int, dados: RespostaEntrada,
                    usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Nota interna — fica na conversa e nunca sai para o cliente."""
    eu = _exige_estar_na_conversa(conversa_id, usuario)
    resultado = conversas.anotar(conversa_id, dados.texto, eu)
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


class ConviteEntrada(BaseModel):
    atendente_id: int


@app.get("/api/conversas/{conversa_id}/participantes")
def ver_participantes(conversa_id: int,
                      usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Quem acompanha, quem pode ser chamado, e qual é o meu papel aqui.

    ⚠️ `convidaveis` sai daqui e não de `/api/atendentes` porque aquela rota
    exige CAD_2.1 — tela de cadastro, que atendente comum não tem. Aqui vai só
    id e nome, que é o necessário para o seletor.
    """
    eu = _atendente_do_usuario(usuario)
    lista = conversas.participantes(conversa_id)
    conversa_atual = banco.um(
        "SELECT atendente_id FROM conversa WHERE id = %s", (conversa_id,))
    if not conversa_atual:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")

    dentro = {p["atendente_id"] for p in lista}
    if conversa_atual["atendente_id"]:
        dentro.add(conversa_atual["atendente_id"])
    return {
        "participantes": lista,
        "eu": eu,
        "sou_dono": eu is not None and conversa_atual["atendente_id"] == eu,
        "sou_participante": eu in {p["atendente_id"] for p in lista},
        "convidaveis": [
            {"id": a["id"], "nome": a["nome"]}
            for a in banco.varios(
                "SELECT id, nome FROM atendente WHERE ativo ORDER BY nome")
            if a["id"] not in dentro],
    }


@app.post("/api/conversas/{conversa_id}/convidar")
def convidar_para_conversa(conversa_id: int, dados: ConviteEntrada,
                           usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Chama outro atendente para a conversa.

    🚨 Isto NÃO concede acesso — não existe isolamento por conversa: qualquer
    atendente com ATD_1.2 já abre qualquer conversa. O convite faz a conversa
    APARECER NA LISTA de quem foi chamado, e registra quem está junto.
    """
    eu = _exige_estar_na_conversa(conversa_id, usuario)
    resultado = conversas.convidar(conversa_id, dados.atendente_id, eu)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.post("/api/conversas/{conversa_id}/sair")
def sair_da_conversa(conversa_id: int,
                     usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Sai da conversa. Se quem sai é o dono, a posse passa para quem ficou —
    e se não ficou ninguém, a conversa volta para a fila."""
    eu = _atendente_do_usuario(usuario)
    if eu is None:
        raise HTTPException(status_code=409,
                            detail="Seu login não está ligado a um atendente.")
    resultado = conversas.sair(conversa_id, eu)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.post("/api/conversas/{conversa_id}/remover/{atendente_id}")
def remover_da_conversa(conversa_id: int, atendente_id: int,
                        usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Tira alguém da conversa. Só quem responde por ela pode."""
    resultado = conversas.remover(conversa_id, atendente_id,
                                  _atendente_do_usuario(usuario))
    if not resultado["ok"]:
        raise HTTPException(status_code=403, detail=resultado["motivo"])
    return resultado


@app.post("/api/conversas/{conversa_id}/transferir")
def transferir_conversa(conversa_id: int, dados: TransferenciaEntrada,
                        usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Enquanto a IA não existe, ISTO é a triagem — feita por gente."""
    eu = _exige_estar_na_conversa(conversa_id, usuario)
    resultado = conversas.transferir(
        conversa_id, dados.time_id, dados.para_atendente_id, "manual",
        de_atendente_id=eu, texto_resumo=dados.observacao)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.post("/api/conversas/{conversa_id}/devolver")
def devolver_conversa(conversa_id: int,
                      usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    eu = _exige_estar_na_conversa(conversa_id, usuario)
    resultado = conversas.devolver_para_fila(conversa_id, eu)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.post("/api/conversas/{conversa_id}/encerrar")
def encerrar_conversa(conversa_id: int, dados: EncerramentoEntrada,
                      usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Conclui o atendimento. Classificar é OPCIONAL desde 11/08 — a
    obrigatoriedade do escopo item 11 servia a um analytics que não
    existe, com rótulos que ninguém pediu.

    🚨 Exige estar na conversa desde 12/08: concluir atendimento alheio era
    livre para qualquer um com a tela.

    ⚠️ A rota continua `/encerrar` e a tela diz "Concluir atendimento" desde
    25/08. Rótulo é da tela; trocar o caminho derrubaria quem estivesse com o
    painel aberto no meio do deploy, sem ganhar nada."""
    _exige_estar_na_conversa(conversa_id, usuario)
    # 🚨 QUEM CONCLUIU VAI JUNTO. A conversa volta para "sem dono" no
    # fechamento (decisão de 25/08), então `atendente_id` deixa de responder
    # "quem atendeu" -- sem este argumento o desfecho nasceria anônimo.
    resultado = conversas.encerrar(conversa_id, dados.classificacao_id,
                                   dados.comentario,
                                   atendente_id=_atendente_do_usuario(usuario))
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


class ReacaoEntrada(BaseModel):
    mensagem_id: int
    # Vazio TIRA a reação: é assim que o WhatsApp desfaz.
    emoji: str = ""


@app.post("/api/conversas/{conversa_id}/reagir")
def reagir_na_conversa(conversa_id: int, dados: ReacaoEntrada,
                       usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Reage a uma mensagem com um emoji."""
    _exige_estar_na_conversa(conversa_id, usuario)
    r = conversas.reagir(conversa_id, dados.mensagem_id, dados.emoji)
    if not r["ok"]:
        raise HTTPException(status_code=409, detail=r["motivo"])
    return r


@app.post("/api/conversas/{conversa_id}/audio")
async def responder_com_audio(conversa_id: int,
                              arquivo: UploadFile = File(...),
                              usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """O áudio gravado no navegador — mensagem de VOZ, não anexo."""
    _exige_estar_na_conversa(conversa_id, usuario)
    dados = await arquivo.read()
    r = conversas.responder_com_audio(
        conversa_id, dados, _atendente_do_usuario(usuario))
    if not r["ok"]:
        raise HTTPException(status_code=409, detail=r["motivo"])
    return r


# ⚠️ 5 é o limite do próprio WhatsApp por ação de encaminhar. Copiamos o
# número de propósito: é o que a pessoa já conhece do aplicativo.
#
# ⚠️ DECLARADO ANTES DE QUEM USA. Estava depois da rota -- funciona, porque a
# resolução é em tempo de chamada, mas quebraria em silêncio no dia em que
# alguém o usasse como valor padrão de argumento.
TETO_ENCAMINHAR = 5


class EncaminharEntrada(BaseModel):
    mensagem_id: int
    conversas: list[int]


def _conversa_da_mensagem(mensagem_id: int) -> int:
    linha = banco.um("SELECT conversa_id FROM mensagem WHERE id = %s",
                     (mensagem_id,))
    if not linha:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada.")
    return linha["conversa_id"]


@app.post("/api/conversas/encaminhar")
def encaminhar_mensagem(dados: EncaminharEntrada,
                        usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Repassa uma mensagem para outras conversas.

    🚨 A REGRA DE "NÃO É CAIXA DE DISPARO" CAIU em 25/08, por decisão do
    usuário. O que fica no lugar é o teto: encaminhar leva uma mensagem
    EXISTENTE para destinos escolhidos um a um, e a resposta diz quantos
    receberam.
    """
    if len(dados.conversas or []) > TETO_ENCAMINHAR:
        raise HTTPException(
            status_code=400,
            detail=f"São {len(dados.conversas)} destinos. O WhatsApp limita o "
                   f"encaminhar a {TETO_ENCAMINHAR} por vez, e nós também.")
    # 🚨 A ORIGEM TEM DE SER SUA (achado na auditoria de 25/08). Todo caminho
    # que ESCREVE numa conversa passa por `_exige_estar_na_conversa`;
    # encaminhar não passava, e era o único. Sem isto, quem tem a tela repassa
    # qualquer mensagem de qualquer conversa -- inclusive de atendimento
    # alheio -- para até cinco clientes.
    _exige_estar_na_conversa(_conversa_da_mensagem(dados.mensagem_id), usuario)
    r = conversas.encaminhar(dados.mensagem_id, dados.conversas,
                             _atendente_do_usuario(usuario))
    if not r["ok"]:
        raise HTTPException(status_code=409, detail=r["motivo"])
    return r


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


@app.post("/api/atendentes/{atendente_id}/desligar")
def desligar_atendente(atendente_id: int,
                       usuario: dict = Depends(auth.requer_tela("CAD_2.1"))):
    """Desliga e SOLTA o que a pessoa estava segurando.

    🚨 O QUE FALTAVA NÃO ERA O BOTÃO, ERA O EFEITO. Desativar gravava
    `ativo = false` e nada mais: quem saía com 12 conversas abertas deixava
    dono que nunca mais entra, e elas ficavam invisíveis -- não aparecem em
    "sem dono" porque TÊM dono, e ninguém as vê porque o dono não entra.
    """
    r = operacao.desligar(atendente_id, quem_edita=usuario.get("login"))
    if not r["ok"]:
        raise HTTPException(status_code=409, detail=r["motivo"])
    return r


class JornadaAtiva(BaseModel):
    ligada: bool


@app.get("/api/config/jornada")
def ver_jornada_ativa(usuario: dict = Depends(auth.requer_tela("CAD_2.1"))):
    """⚠️ A jornada nasce DESLIGADA: monta-se a escala com calma, e só quando
    o owner ligar ela passa a significar alguma coisa na fila."""
    return {"jornada_ativa": operacao.jornada_ativa()}


@app.put("/api/config/jornada")
def definir_jornada_ativa(dados: JornadaAtiva,
                          usuario: dict = Depends(auth.requer_tela("CAD_2.1"))):
    return operacao.definir_jornada_ativa(dados.ligada)


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

# ══════════════════════════════════════════════════════════════════════════
# ATD_6.1 — chat entre atendentes
#
# 🚨 NADA DAQUI SAI PARA O CLIENTE, e não existe caminho para isso: o módulo
# `chat` não conhece o `evolution`. É conversa interna, em tabelas próprias.
# ══════════════════════════════════════════════════════════════════════════

class ChatTexto(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)


class ChatAbrir(BaseModel):
    atendente_id: int


def _eu_no_chat(usuario: dict) -> int:
    eu = _atendente_do_usuario(usuario)
    if not eu:
        raise HTTPException(
            status_code=409,
            detail="Sua conta não tem vínculo de atendimento. Procure o "
                   "administrador do sistema.")
    return eu


def _minha_sala(sala_id: int, usuario: dict) -> int:
    """🚨 AQUI O ISOLAMENTO É REAL, diferente da conversa de cliente.

    Conversa com cliente é responsabilidade coletiva e qualquer atendente lê.
    Conversa entre duas pessoas não é: ler a alheia não é "colaborar". A rota
    recusa mesmo que a tela não ofereça.
    """
    eu = _eu_no_chat(usuario)
    if not chat.e_membro(sala_id, eu):
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return eu


@app.get("/api/chat/salas")
def chat_salas(usuario: dict = Depends(auth.requer_tela("ATD_6.1"))):
    eu = _eu_no_chat(usuario)
    return {"salas": chat.salas(eu), "contatos": chat.com_quem_falar(eu)}


@app.get("/api/chat/nao-lidas")
def chat_nao_lidas(usuario: dict = Depends(auth.requer_tela("ATD_6.1"))):
    """O selo do menu. Separado das salas porque é chamado em intervalo curto."""
    eu = _atendente_do_usuario(usuario)
    return {"nao_lidas": chat.nao_lidas(eu) if eu else 0}


@app.post("/api/chat/abrir")
def chat_abrir(dados: ChatAbrir,
               usuario: dict = Depends(auth.requer_tela("ATD_6.1"))):
    """Acha ou cria a sala direta com alguém. Idempotente pela chave do par."""
    eu = _eu_no_chat(usuario)
    resultado = chat.abrir_direta(eu, dados.atendente_id)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


class ChatGrupoNovo(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    membros: list[int] = Field(default_factory=list)


class ChatMembroNovo(BaseModel):
    atendente_id: int


@app.post("/api/chat/grupo")
def chat_criar_grupo(dados: ChatGrupoNovo,
                     usuario: dict = Depends(auth.requer_tela("ATD_6.1"))):
    eu = _eu_no_chat(usuario)
    resultado = chat.criar_grupo(dados.nome, eu, dados.membros)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.get("/api/chat/salas/{sala_id}/membros")
def chat_membros(sala_id: int,
                 usuario: dict = Depends(auth.requer_tela("ATD_6.1"))):
    _minha_sala(sala_id, usuario)
    return {"membros": chat.membros(sala_id)}


@app.post("/api/chat/salas/{sala_id}/membros")
def chat_adicionar(sala_id: int, dados: ChatMembroNovo,
                   usuario: dict = Depends(auth.requer_tela("ATD_6.1"))):
    eu = _minha_sala(sala_id, usuario)
    resultado = chat.adicionar_ao_grupo(sala_id, eu, dados.atendente_id)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.post("/api/chat/salas/{sala_id}/sair")
def chat_sair(sala_id: int,
              usuario: dict = Depends(auth.requer_tela("ATD_6.1"))):
    eu = _minha_sala(sala_id, usuario)
    resultado = chat.sair_do_grupo(sala_id, eu)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


@app.get("/api/chat/salas/{sala_id}")
def chat_mensagens(sala_id: int,
                   usuario: dict = Depends(auth.requer_tela("ATD_6.1"))):
    eu = _minha_sala(sala_id, usuario)
    mensagens = chat.mensagens(sala_id, eu)
    # Abrir a sala é ler: marca até a última que veio nesta resposta, e não
    # "até agora" -- o que chegar durante a leitura continua não lido.
    if mensagens:
        chat.marcar_lido(sala_id, eu, mensagens[-1]["id"])
    return {"sala_id": sala_id, "mensagens": mensagens}


@app.post("/api/chat/salas/{sala_id}/escrever")
def chat_escrever(sala_id: int, dados: ChatTexto,
                  usuario: dict = Depends(auth.requer_tela("ATD_6.1"))):
    eu = _minha_sala(sala_id, usuario)
    resultado = chat.escrever(sala_id, eu, dados.texto)
    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado["motivo"])
    return resultado


def _atendente_do_usuario(usuario: dict) -> int | None:
    """O id na tabela `atendente` de quem está logado — o VÍNCULO DE ATENDIMENTO.

    ⚠️ A conta do .env sem linha na tabela (banco fora do ar, instalação nova)
    não tem vínculo. Autor NULL é honesto: melhor "autor desconhecido" do que
    atribuir a mensagem a outra pessoa.

    🚨 SEM E-MAIL, SEM VÍNCULO — regra do usuário em 12/08. O e-mail é o que
    liga a pessoa à conta Google e é por ele que a conta passa de mão; uma
    linha de atendente sem e-mail não identifica ninguém de forma durável.
    Apagar o e-mail de alguém, de propósito ou por engano, tirava o vínculo
    sem tirar o acesso: a pessoa continuava respondendo cliente e tudo saía
    com autor NULL. Agora ela entra, a `INI_1.1` explica o que houve, e nada
    é gravado sem dono.

    ⚠️ Lê a linha pelo `id` que `buscar_usuario` já resolveu, quando há; só
    cai no login quando a identidade veio da porta de emergência.
    """
    if usuario.get("id"):
        linha = banco.um("SELECT id, email FROM atendente WHERE id = %s",
                         (usuario["id"],))
    else:
        linha = banco.um(
            "SELECT id, email FROM atendente WHERE lower(login) = lower(%s)",
            (usuario["login"],))
    if not linha:
        return None
    if not (linha["email"] or "").strip():
        return None
    return linha["id"]


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


# ------------------------------------------------------- IA: a sala de ensaio
#
# 🚨 É O PASSO 3 DA SEQUÊNCIA DE ATIVAÇÃO (`docs/04_Contrato_IA.md`): parear o
# chip, conferir que a mensagem chega, **validar o bot respondendo**, e só
# então ligar o interruptor. Sem este passo, o primeiro erro da IA é em
# público -- que é exatamente o que a decisão de 06/08 existe para evitar.
#
# ⚠️ ENSAIO NÃO ENVIA, NÃO GRAVA E NÃO TRANSFERE. Roda o motor inteiro contra
# uma conversa de verdade e devolve o que ELA TERIA feito. Se ensaiar operasse,
# não seria ensaio.

class EnsaioEntrada(BaseModel):
    conversa_id: int
    # Opcional: a pergunta a fazer POR CIMA do histórico da conversa. Sem ela,
    # ensaia contra a última coisa que o cliente escreveu de verdade.
    texto: str | None = Field(default=None, max_length=4000)


@app.post("/api/ia/ensaio")
def ensaiar_ia(dados: EnsaioEntrada,
               usuario: dict = Depends(auth.requer_tela("CFG_2.1"))):
    r = ia.responder(dados.conversa_id, ensaio=True,
                     texto_de_ensaio=dados.texto)
    if not r.get("texto") and r.get("motivo") not in (None, "ensaio: nada foi enviado"):
        # Motivo com nome, não "nada aconteceu": é o que a tela mostra quando
        # a IA não falaria nesta conversa (grupo, humano assumiu, sem chave).
        raise HTTPException(status_code=409, detail=r["motivo"])
    return r


@app.get("/api/ia/motor")
def estado_do_motor(usuario: dict = Depends(auth.requer_tela("CFG_2.1"))):
    """🚨 A chave sai MASCARADA (`sk-...a3f9`), nunca o valor."""
    return ia.estado()


class CanalIaEntrada(BaseModel):
    ligada: bool


@app.put("/api/canais/{canal_id}/ia")
def ligar_ia_do_canal(canal_id: int, dados: CanalIaEntrada,
                      usuario: dict = Depends(auth.requer_tela("CFG_1.1"))):
    """O ato deliberado. Registra QUEM e QUANDO em `ia_ligada_por`/`_em`."""
    r = registro_canais.ligar_ia(canal_id, dados.ligada, usuario["login"])
    if not r["ok"]:
        raise HTTPException(status_code=409, detail=r["motivo"])
    return r


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
        # 🚨 O `index.html` NÃO PODE SER GUARDADO PELO NAVEGADOR. Medido em
        # 27/08: ele saía com `last-modified` e `etag`, e SEM `Cache-Control`.
        # Sem esse cabeçalho o navegador aplica cache heurístico -- guarda por
        # uma fração do tempo desde a última modificação e serve do disco SEM
        # revalidar. Como o index é quem aponta para o bundle com hash, um
        # index velho prende o usuário numa versão antiga inteira, e a única
        # saída vira `Ctrl+Shift+R`.
        #
        # ⚠️ `no-cache` NÃO É "não guarde": é "guarde, mas pergunte antes de
        # usar". O 304 continua acontecendo e a resposta continua barata -- o
        # que acaba é o navegador decidir sozinho que não precisa perguntar.
        #
        # ⚠️ Os ARQUIVOS de /assets não entram aqui de propósito: eles têm hash
        # no nome, então nome novo é arquivo novo, e cache longo neles é o que
        # faz a página abrir rápido.
        return FileResponse(FRONTEND / "index.html",
                            headers={"Cache-Control": "no-cache"})
