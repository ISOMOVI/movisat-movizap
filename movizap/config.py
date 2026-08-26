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

    # Entrada pelo Google. Sem estes valores o botão não aparece na tela --
    # botão que não funciona rende chamado.
    google_client_id: str = _ler("MOVIZAP_GOOGLE_CLIENT_ID")
    google_client_secret: str = _ler("MOVIZAP_GOOGLE_CLIENT_SECRET")
    google_redirect: str = _ler(
        "MOVIZAP_GOOGLE_REDIRECT",
        "https://movizap.movisat.com.br/api/auth/google/callback")
    google_dominio: str = _ler("MOVIZAP_GOOGLE_DOMINIO", "movisat.com.br")

    fpsl_base_url: str = _ler("FPSL_BASE_URL", "http://127.0.0.1:8005")

    # ---- banco (migração 001, 2026-08-05) ----
    db_host: str = _ler("MOVIZAP_DB_HOST", "127.0.0.1")
    db_porta: str = _ler("MOVIZAP_DB_PORTA", "5432")
    db_nome: str = _ler("MOVIZAP_DB_NOME", "movizap")
    db_usuario: str = _ler("MOVIZAP_DB_USUARIO", "movizap")
    db_senha: str = _ler("MOVIZAP_DB_SENHA")

    # ---- Evolution (CFG_1.1) ----
    evolution_base_url: str = _ler("EVOLUTION_BASE_URL", "http://localhost:8081")
    evolution_api_key: str = _ler("EVOLUTION_API_KEY")
    evolution_instancia: str = _ler("EVOLUTION_INSTANCIA_ATENDIMENTO", "atendimento")

    # ---- Harmonit (CFG_3.1, 2026-08-06) ----
    # Copiadas do .env do FPSL por script no servidor, nunca por linha de comando.
    harmonit_base_url: str = _ler("HARMONIT_BASE_URL")
    harmonit_client_id: str = _ler("HARMONIT_CLIENT_ID")
    harmonit_secret_id: str = _ler("HARMONIT_SECRET_ID")

    # ---- webhook (passo 4, 2026-08-06) ----
    # 🚨 O endpoint é público: o Evolution roda em container e não alcança o
    # 127.0.0.1 do host, então a chamada entra pelo nginx. Este segredo no
    # caminho da URL é o que o protege.
    webhook_segredo: str = _ler("MOVIZAP_WEBHOOK_SEGREDO")

    # ---- IA (passo 8, 2026-08-26) ----
    # 🚨 SÓ O `movizap/llm/` LÊ ESTES VALORES. `docs/04_Contrato_IA.md`:
    # *"chave lida do .env por um único gateway; nenhum outro módulo sabe que
    # ela existe"*. Chave própria do MoviZap (não a do MoviChat) é o que dá
    # custo discriminado e permite revogar uma sem derrubar as outras.
    #
    # ⚠️ NOME PREFIXADO. `DEEPSEEK_API_KEY` puro colidiria com a variável de
    # ambiente que o MoviChat usa, e uma unidade systemd que exportasse a dele
    # passaria a alimentar este painel sem ninguém pedir.
    deepseek_api_key: str = _ler("MOVIZAP_DEEPSEEK_API_KEY")
    groq_api_key: str = _ler("MOVIZAP_GROQ_API_KEY")
    llm_provider: str = _ler("MOVIZAP_LLM_PROVIDER", "deepseek")
    # `single` = só o principal. `fallback` = o reserva entra se o principal
    # falhar. Fica em `single` porque hoje só há uma chave: com `fallback` e
    # sem a segunda chave, a falha do principal viraria "todos falharam", que
    # é a mesma coisa dita de um jeito mais confuso.
    llm_strategy: str = _ler("MOVIZAP_LLM_STRATEGY", "single")

    # 🚨 SÓ EXISTE DURANTE UMA ROTAÇÃO, e sair é parte do procedimento.
    # Segredo errado devolve 404, e o Evolution trata 404 como falha: trocar o
    # valor e reiniciar criaria uma janela em que todo evento é recusado. Com
    # os dois válidos, as duas URLs respondem enquanto o Evolution é
    # reapontado, e nada se perde. Vazio = nenhuma rotação em curso.
    webhook_segredo_anterior: str = _ler("MOVIZAP_WEBHOOK_SEGREDO_ANTERIOR")

    def dsn(self) -> str:
        """String de conexão do Postgres.

        🚨 Nunca imprimir nem logar: carrega a senha. Para exibir, use
        `dsn_seguro()`.
        """
        return (f"host={self.db_host} port={self.db_porta} dbname={self.db_nome} "
                f"user={self.db_usuario} password={self.db_senha}")

    def dsn_seguro(self) -> str:
        """O mesmo, sem a senha. É este que pode aparecer em log ou tela."""
        return f"{self.db_usuario}@{self.db_host}:{self.db_porta}/{self.db_nome}"

    def faltando(self) -> list[str]:
        """O que impede o app de subir. Falhar cedo é melhor que falhar em uso."""
        obrigatorios = {
            "MOVIZAP_JWT_SECRET": self.jwt_secret,
            "MOVIZAP_ADMIN_LOGIN": self.admin_login,
            "MOVIZAP_ADMIN_SENHA_HASH": self.admin_senha_hash,
            "MOVIZAP_DB_SENHA": self.db_senha,
        }
        return [k for k, v in obrigatorios.items() if not v]

    def avisos(self) -> list[str]:
        """O que não impede subir, mas deixa uma tela sem funcionar.

        Separado de `faltando` de propósito: derrubar o painel inteiro porque
        a CFG_1.1 não vai funcionar seria trocar um problema por um maior.
        """
        avisos = []
        if not self.evolution_api_key:
            avisos.append("EVOLUTION_API_KEY ausente -- a CFG_1.1 não vai conectar")
        if not (self.harmonit_client_id and self.harmonit_secret_id):
            avisos.append("credenciais do Harmonit ausentes -- a CFG_3.1 não vai sincronizar")
        if not self.webhook_segredo:
            avisos.append("MOVIZAP_WEBHOOK_SEGREDO ausente -- o webhook recusa tudo")
        if not (self.deepseek_api_key or self.groq_api_key):
            # ⚠️ AVISO, NÃO FALTA. Sem chave a IA fica indisponível e a CFG_5.1
            # mostra o motivo -- derrubar o painel inteiro por causa disso
            # trocaria um problema por um maior.
            avisos.append("nenhuma chave de modelo no .env -- a IA fica indisponível")
        return avisos


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
