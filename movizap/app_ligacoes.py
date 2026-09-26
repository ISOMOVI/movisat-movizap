"""O app do agente de ligações: porta própria, separada do painel (Plano 5.1, 25/09).

🔵 *"talvez usar uma porta para o serviço? ... uma saída segura que poderia ter
o nginx específico para não misturar outro?"* e, nas decisões: processo
próprio, e certificado de cliente por PC (há PC fora do escritório).

    PC (agente) --HTTPS + certificado do PC--> nginx ligacoesmicrosip
        --(só /agente/, cota própria)--> 127.0.0.1:8010 (ESTE app) --> banco

Expõe SÓ as duas rotas do agente. Reiniciar o painel (8008) não interrompe um
envio, e um lote atrasado não disputa a cota nem os workers da equipe.

🚨 DUAS PROVAS, DO MESMO AGENTE: a chave (`X-Agente-Chave`) e o certificado
que o nginx validou e repassa em `X-Cliente-Cert` (`$ssl_client_escaped_cert`,
PEM codificado em URL). O nginx sobrescreve o cabeçalho: o PC não consegue
forjá-lo. E o app só escuta em 127.0.0.1.
"""
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from . import banco, ligacoes
from .operacao import DadoInvalido

log = logging.getLogger("movizap.app_ligacoes")


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    banco.abrir()
    yield
    banco.fechar()


app = FastAPI(title="MoviZap Ligações (agente)", lifespan=ciclo_de_vida,
              docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(DadoInvalido)
async def _dado_invalido(_request: Request, e: DadoInvalido):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=400, content={"detail": str(e)})


class BatimentoEntrada(BaseModel):
    pc: str | None = Field(default=None, max_length=100)
    versao: str | None = Field(default=None, max_length=20)
    pendentes: int | None = None
    erro: str | None = Field(default=None, max_length=500)
    aviso: str | None = Field(default=None, max_length=500)


def _agente(request: Request) -> dict:
    try:
        return ligacoes.agente_da_chave(request.headers.get("X-Agente-Chave"),
                                        request.headers.get("X-Cliente-Cert"),
                                        exigir_cert=True)
    except ligacoes.ChaveInvalida as e:
        log.warning("agente recusado (%s) de %s", e, _ip(request))
        raise HTTPException(status_code=401, detail=str(e)) from e


def _ip(request: Request) -> str | None:
    return request.headers.get("X-Real-IP") or (request.client.host if request.client else None)


@app.get("/saude")
def saude():
    """Só local (o nginx não repassa nada fora de /agente/)."""
    banco.um("SELECT 1 AS ok")
    return {"ok": True}


@app.post("/agente/batimento")
def batimento(dados: BatimentoEntrada, request: Request):
    """Toda passada do agente bate aqui, mesmo sem nada a enviar: é o que
    prova que o PC está vivo (o alerta de mais de 1 dia sem contato)."""
    return ligacoes.batimento(_agente(request), dados.pc, dados.versao, dados.pendentes,
                              dados.erro, ip=_ip(request), aviso=dados.aviso)


@app.post("/agente/enviar")
async def enviar(request: Request, dados: str = Form(...),
                 arquivo: UploadFile | None = File(None)):
    """Uma ligação do histórico e, se houver, UMA gravação dela. Idempotente:
    reenviar devolve "já tinha" e o mesmo hash."""
    agente = _agente(request)
    try:
        meta = json.loads(dados)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="`dados` não é JSON.") from e
    conteudo = nome = None
    if arquivo is not None:
        pedacos, total = [], 0
        while True:
            pedaco = await arquivo.read(256 * 1024)
            if not pedaco:
                break
            total += len(pedaco)
            if total > ligacoes.TETO:
                raise HTTPException(status_code=413,
                                    detail=f"Gravação acima de {ligacoes.TETO_MB} MB.")
            pedacos.append(pedaco)
        conteudo, nome = b"".join(pedacos), arquivo.filename
    return ligacoes.registrar(agente, meta, conteudo, nome, meta.get("pc"))
