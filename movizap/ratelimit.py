"""Limite de tentativas de login. Igual nos quatro paineis.

Origem: `moviserver/ratelimit.py`, de um achado de auditoria em 2026-07-28 --
`/api/login` aceitava tentativas ilimitadas, 12 em 2,8 s. Em 2026-08-05 a
auditoria dos quatro paineis mostrou que so o MoviServer tinha a trava.

Tres correcoes que o original nao tinha:

  1. a chave usa `casefold` no login: senao bastava alternar maiuscula para
     ganhar 5 tentativas a cada variante;

  2. `ip_do_cliente` le o X-Real-IP quando -- e SOMENTE quando -- a conexao
     vem do proxy local. Atras do nginx `request.client.host` e sempre
     127.0.0.1, e sem isso o limite vira um balde so para o mundo inteiro: o
     primeiro atacante a estourar tranca todos os usuarios junto;

  3. 🚨 o contador vive em SQLITE, nao em memoria. O MoviChat roda com
     `--workers 2`: com contador em memoria cada worker conta separado, e o
     limite de 5 vira 10 -- foi medido em 05/08, 6 tentativas seguidas nao
     bloquearam nada. SQLite serializa a escrita entre processos e resolve
     sem depender de Redis.

Efeito colateral aceito: o bloqueio agora SOBREVIVE ao restart do servico.
Antes, reiniciar zerava tudo -- o que so ajudava o atacante, ja que ele nao
controla o restart. Para destravar de proposito existe `zerar()`.
"""
import os
import sqlite3
import time
from pathlib import Path

JANELA_SEG = 300      # 5 min de memoria para as falhas
MAX_FALHAS = 5        # falhas na janela antes de travar
BLOQUEIO_SEG = 300    # quanto tempo fica travado depois de estourar

# So estes enderecos podem falar em nome de outro cliente. Os servicos
# escutam apenas em 127.0.0.1, entao o nginx e o unico caminho de entrada.
PROXIES_CONFIAVEIS = {"127.0.0.1", "::1"}

# Fica ao lado do modulo, um por projeto. Nao guarda nada sensivel: so a
# chave (ip|login) e carimbos de tempo.
ARQUIVO = Path(os.environ.get("RATELIMIT_DB") or (Path(__file__).resolve().parent / "ratelimit.db"))


def _conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(ARQUIVO, timeout=5, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")   # leitura nao trava escrita
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("CREATE TABLE IF NOT EXISTS falhas (chave TEXT, quando REAL)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_falhas ON falhas (chave)")
    conn.execute("CREATE TABLE IF NOT EXISTS travas (chave TEXT PRIMARY KEY, ate REAL)")
    # 🔵 22/10: os formularios publicos precisam contar ENVIOS, nao falhas --
    # envio e sucesso, e sucesso nenhum bloqueia aqui. Tabela separada para que
    # a conta de um nunca mexa na trava do outro.
    conn.execute("CREATE TABLE IF NOT EXISTS eventos (chave TEXT, quando REAL)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_eventos ON eventos (chave)")
    return conn


def ip_do_cliente(request) -> str:
    """O IP de verdade, atras do nginx.

    🚨 Confiar no cabecalho SEM checar a origem e pior que nao ter limite:
    quem manda um X-Forwarded-For novo a cada tentativa ganha tentativas
    infinitas. Por isso so se aceita o cabecalho vindo do proxy local.
    """
    conexao = request.client.host if request.client else "?"
    if conexao not in PROXIES_CONFIAVEIS:
        return conexao
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return conexao


def chave_de(ip: str, login: str) -> str:
    """Conta por IP E por conta.

    So por IP puniria um escritorio inteiro atras de um NAT por causa de uma
    pessoa. So por conta deixaria um atacante distribuido passar.
    """
    return f"{ip}|{(login or '').casefold()}"


def bloqueado_por(chave: str) -> int:
    """Segundos restantes de bloqueio; 0 se liberado.

    Nao registra nada: consultar nao pode punir.
    """
    try:
        with _conectar() as conn:
            linha = conn.execute(
                "SELECT ate FROM travas WHERE chave = ?", (chave,)
            ).fetchone()
    except sqlite3.Error:
        # 🚨 Falha do contador NAO pode virar porta fechada para todo mundo.
        # Liberar aqui e a escolha certa: o pior caso e ficar sem limite por
        # alguns instantes; o outro pior caso e o painel inteiro fora do ar.
        return 0
    if not linha:
        return 0
    resta = int(linha[0] - time.time())
    return resta if resta > 0 else 0


def registrar_falha(chave: str) -> None:
    agora = time.time()
    try:
        with _conectar() as conn:
            conn.execute("DELETE FROM falhas WHERE quando < ?", (agora - JANELA_SEG,))
            conn.execute("INSERT INTO falhas (chave, quando) VALUES (?, ?)", (chave, agora))
            n = conn.execute(
                "SELECT COUNT(*) FROM falhas WHERE chave = ?", (chave,)
            ).fetchone()[0]
            if n >= MAX_FALHAS:
                conn.execute(
                    "INSERT OR REPLACE INTO travas (chave, ate) VALUES (?, ?)",
                    (chave, agora + BLOQUEIO_SEG),
                )
                conn.execute("DELETE FROM falhas WHERE chave = ?", (chave,))
    except sqlite3.Error:
        pass   # ver o comentario em bloqueado_por


def registrar_sucesso(chave: str) -> None:
    try:
        with _conectar() as conn:
            conn.execute("DELETE FROM falhas WHERE chave = ?", (chave,))
            conn.execute("DELETE FROM travas WHERE chave = ?", (chave,))
    except sqlite3.Error:
        pass


def zerar() -> None:
    """Destrava tudo. Usado em teste e para soltar alguem preso por engano."""
    try:
        with _conectar() as conn:
            conn.execute("DELETE FROM falhas")
            conn.execute("DELETE FROM travas")
    except sqlite3.Error:
        pass

# ----------------------------------------------------------------------------
# Eventos: contar o que ACONTECEU, sem bloquear nada
# ----------------------------------------------------------------------------
# 🔵 22/10, para o envio publico de formulario. 🚨 DELIBERADAMENTE SEPARADO DAS
# FALHAS DE LOGIN: aqui nada trava. Quem passa do teto so ganha um desafio a
# mais no caminho -- decisao dele: *"captcha no final pode se legal, mas tbm
# usam pelo cel então não pode virar entrave de processo"*.
JANELA_EVENTOS_SEG = 3600


def registrar_evento(chave: str) -> None:
    """Mais um envio desta chave, agora."""
    try:
        with _conectar() as conn:
            agora = time.time()
            conn.execute("INSERT INTO eventos (chave, quando) VALUES (?, ?)",
                         (chave, agora))
            # Limpeza no caminho, como nas falhas: sem cron e sem crescer.
            conn.execute("DELETE FROM eventos WHERE quando < ?",
                         (agora - JANELA_EVENTOS_SEG * 24,))
    except sqlite3.Error:
        pass   # ver o comentario em bloqueado_por: contador fora do ar nao fecha porta


def quantos_eventos(chave: str, janela_seg: int = JANELA_EVENTOS_SEG) -> int:
    """Quantos eventos desta chave na janela. 🚨 Contar nunca registra."""
    try:
        with _conectar() as conn:
            linha = conn.execute(
                "SELECT count(*) FROM eventos WHERE chave = ? AND quando > ?",
                (chave, time.time() - janela_seg)).fetchone()
            return int(linha[0]) if linha else 0
    except sqlite3.Error:
        # ⚠️ Na dúvida, NÃO exige desafio: o banco de contagem fora do ar não
        # pode impedir um cliente de pedir suporte. É a mesma escolha de
        # `bloqueado_por`, e pelo mesmo motivo.
        return 0
