"""Autenticação e permissão por tela do MoviZap.

Espelha `moviserver/painel/auth.py`, que já está validado em produção:
  - o OWNER é único e enxerga todas as telas;
  - a permissão é aplicada no BACKEND, em toda rota, via `requer_tela`;
  - conta nova nasce sem nenhuma permissão: falha fechado.

⚠️ FASE 1 SEM BANCO. Existe um usuário só, vindo do .env, e ele é o owner.
Quando o `02_Modelo_Dados` for aprovado, a tabela `atendente` assume e este
módulo passa a consultá-la -- `buscar_usuario` é o único ponto que muda.
"""
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from . import telas as registro_telas
from .config import settings

ALGORITMO = "HS256"
TOKEN_EXPIRA_HORAS = 8

bearer = HTTPBearer(auto_error=False)
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(senha: str) -> str:
    return pwd_ctx.hash(senha)


def buscar_usuario(login: str) -> dict | None:
    """Único ponto que conhece a origem dos usuários.

    Hoje: o .env. Depois: a tabela `atendente`. Nada além daqui precisa saber.
    """
    if not settings.admin_login or login != settings.admin_login:
        return None
    return {
        "login": settings.admin_login,
        "nome": "Administrador",
        "senha_hash": settings.admin_senha_hash,
        "owner": True,
        "ativo": True,
        "permissoes": sorted(registro_telas.PERMISSOES_VALIDAS),
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
