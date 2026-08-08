"""Autenticação e permissão por tela do MoviZap.

Espelha `moviserver/painel/auth.py`, que já está validado em produção:
  - o OWNER é único e enxerga todas as telas;
  - a permissão é aplicada no BACKEND, em toda rota, via `requer_tela`;
  - conta nova nasce sem nenhuma permissão: falha fechado.

✅ 07/08: a tabela `atendente` assumiu, como o `02_Modelo_Dados` previa, e
`buscar_usuario` foi mesmo o único ponto que mudou. A conta do .env continua
existindo e continua sendo consultada primeiro -- ela é a saída de emergência
para quando a tabela estiver errada, vazia ou fora do ar.
"""
import logging
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from . import banco
from . import telas as registro_telas
from .config import settings

log = logging.getLogger("movizap.auth")

ALGORITMO = "HS256"
TOKEN_EXPIRA_HORAS = 8

bearer = HTTPBearer(auto_error=False)
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(senha: str) -> str:
    return pwd_ctx.hash(senha)


def buscar_usuario(login: str) -> dict | None:
    """Único ponto que conhece a origem dos usuários.

    Duas origens, nesta ordem: a conta do .env e a tabela `atendente`.

    🚨 A comparação do login IGNORA MAIÚSCULA. Em 05/08 o painel recusou o
    acesso em 1ms -- rápido demais para ter chegado no bcrypt -- porque o nome
    digitado não era idêntico ao gravado. Login é identificador de pessoa, não
    segredo: quem protege é a senha. Exigir a caixa exata só rende chamado.

    🚨 A CONTA DO .env É CONSULTADA PRIMEIRO, E NÃO MUDOU NADA NELA. Foi assim
    de propósito: a tabela `atendente` passou a ser fonte em 07/08, e um erro
    nessa consulta não pode tirar o dono de dentro do próprio painel. Se o
    banco cair, o owner ainda entra.

    ⚠️ Quem vem da tabela e está com `senha_hash` NULL não entra -- e é o
    estado em que os 4 atendentes importados do Chatwoot nasceram.
    `validar_login` barra isso antes do bcrypt.
    """
    # ⚠️ 07/08: `.strip()` nos quatro painéis. A caixa já era ignorada aqui
    # desde 05/08, mas ` iago` com espaço -- que gerenciador de senha e
    # copiar-colar produzem sozinhos -- ainda recusava sem chegar no bcrypt.
    login = (login or "").strip()

    if settings.admin_login and login.casefold() == settings.admin_login.casefold():
        return {
            "login": settings.admin_login,
            "nome": "Administrador",
            "senha_hash": settings.admin_senha_hash,
            "owner": True,
            "ativo": True,
            "permissoes": sorted(registro_telas.PERMISSOES_VALIDAS),
        }

    # 🚨 Banco fora do ar NÃO pode virar 500 na tela de login. Sem este
    # try, um login desconhecido com o pool fechado levantava RuntimeError e
    # o usuário via "erro interno" onde a resposta certa é "login ou senha
    # inválidos". Falha fechado: sem banco, só a conta do .env entra.
    try:
        linha = banco.um(
            """SELECT id, login, nome, senha_hash, ativo, owner, perfil
                 FROM atendente WHERE lower(login) = lower(%s)""",
            (login,),
        )
    except (psycopg.Error, RuntimeError) as e:
        log.error("busca de usuário sem banco (%s): só a conta do .env entra",
                  e.__class__.__name__)
        return None
    if not linha:
        return None
    return {
        "id": linha["id"],
        "login": linha["login"],
        "nome": linha["nome"],
        "senha_hash": linha["senha_hash"],
        "owner": linha["owner"],
        "ativo": linha["ativo"],
        # Conta nova nasce sem nada: perfil desconhecido devolve conjunto
        # vazio, e conjunto vazio é menu vazio. Falha fechado.
        "permissoes": sorted(registro_telas.permissoes_do_perfil(linha["perfil"])),
    }


def validar_login(login: str, senha: str) -> dict | None:
    usuario = buscar_usuario(login)
    if not usuario or not usuario["ativo"]:
        return None
    if not usuario["senha_hash"]:
        return None
    if not pwd_ctx.verify(senha, usuario["senha_hash"]):
        return None
    return usuario


def criar_token(login: str) -> str:
    payload = {
        "sub": login,
        "tipo": "movizap",
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRA_HORAS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITMO)


def get_usuario(
    credenciais: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    nao_autorizado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessão inválida ou expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credenciais is None:
        raise nao_autorizado
    try:
        payload = jwt.decode(
            credenciais.credentials, settings.jwt_secret, algorithms=[ALGORITMO]
        )
    except JWTError:
        raise nao_autorizado
    login = payload.get("sub")
    if not login or payload.get("tipo") != "movizap":
        raise nao_autorizado
    usuario = buscar_usuario(login)
    if not usuario or not usuario["ativo"]:
        raise nao_autorizado
    return usuario


def requer_tela(codigo: str):
    """Dependency de rota. O código é validado no import, não em uso.

    Assim, código de tela errado derruba o arranque -- e não vira 403 silencioso
    três semanas depois.
    """
    registro_telas.por_codigo(codigo)  # estoura já no import se não existir

    def _verificar(usuario: dict = Depends(get_usuario)) -> dict:
        if not registro_telas.pode_acessar(usuario, codigo):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sem permissão para {codigo}.",
            )
        return usuario

    return _verificar
