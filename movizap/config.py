"""Configuração do MoviZap, lida do .env.

Regra herdada e não negociável: segredo NUNCA entra em linha de comando e
NUNCA é impresso. Aqui ele só é lido; quem precisar exibir usa `mascarar`.
"""
import logging
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_ENV = RAIZ / ".env"


def _carregar_env() -> dict[str, str]:
    """Lê o .env sem depender de biblioteca -- o formato é chave=valor e ponto."""
    valores: dict[str, str] = {}
    if not ARQUIVO_ENV.exists():
        return valores
    for linha in ARQUIVO_ENV.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        valores[chave.strip()] = valor.strip().strip('"').strip("'")
    return valores


_ENV = _carregar_env()


def _ler(chave: str, padrao: str = "") -> str:
    # variável de ambiente ganha do arquivo: é o que permite sobrescrever no
    # systemd sem editar o .env.
    return os.environ.get(chave) or _ENV.get(chave) or padrao


class Settings:
    app_nome: str = _ler("APP_NOME", "MoviZap")
    dominio: str = _ler("DOMINIO", "movizap.movisat.com.br")
    porta: int = int(_ler("PORTA", "8008"))
    ambiente: str = _ler("AMBIENTE", "desenvolvimento")

    jwt_secret: str = _ler("MOVIZAP_JWT_SECRET")
    admin_login: str = _ler("MOVIZAP_ADMIN_LOGIN")
    admin_senha_hash: str = _ler("MOVIZAP_ADMIN_SENHA_HASH")

    fpsl_base_url: str = _ler("FPSL_BASE_URL", "http://127.0.0.1:8005")

    def faltando(self) -> list[str]:
        """O que impede o app de subir. Falhar cedo é melhor que falhar em uso."""
        obrigatorios = {
            "MOVIZAP_JWT_SECRET": self.jwt_secret,
            "MOVIZAP_ADMIN_LOGIN": self.admin_login,
            "MOVIZAP_ADMIN_SENHA_HASH": self.admin_senha_hash,
        }
        return [k for k, v in obrigatorios.items() if not v]


settings = Settings()


def mascarar(valor: str, visivel: int = 4) -> str:
    """Para exibir segredo em tela ou log sem exibir segredo."""
    if not valor:
        return ""
    if len(valor) <= visivel:
        return "*" * len(valor)
    return f"{valor[:3]}...{valor[-visivel:]}"


def silenciar_clientes_http() -> None:
    """🚨 httpx/httpcore/hpack imprimem o header Authorization em DEBUG.

    Foi exatamente assim que a chave da WESO vazou para um log em julho/2026.
    Chamado no arranque, antes de qualquer requisição sair.
    """
    for nome in ("httpx", "httpcore", "hpack", "h2"):
        logging.getLogger(nome).setLevel(logging.WARNING)
