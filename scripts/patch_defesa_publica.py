"""Patch: as defesas do envio público de formulário.

Mexe em três arquivos, e cada um por um motivo:

  · `movizap/config.py`      -- o segredo próprio dos tokens do formulário;
  · `movizap/ratelimit.py`   -- contar ENVIOS por IP (hoje só conta FALHAS de
                                login), reaproveitando o mesmo SQLite;
  · `.env`                   -- o segredo, gerado aqui e nunca impresso.

Rodar duas vezes não duplica nada (cada emenda confere se já está lá).
"""
import re
import secrets
import sys
from pathlib import Path

RAIZ = Path("/home/claude/movizap_painel")


def emendar(caminho: Path, ancora: str, novo: str, marca: str) -> str:
    texto = caminho.read_text(encoding="utf-8")
    if marca in texto:
        return f"{caminho.name}: ja estava"
    if ancora not in texto:
        sys.exit(f"{caminho.name}: NAO achei a ancora -- nada foi escrito")
    caminho.write_text(texto.replace(ancora, novo, 1), encoding="utf-8")
    return f"{caminho.name}: emendado"


# ----------------------------------------------------------------- config.py
CONFIG = RAIZ / "movizap" / "config.py"
ANCORA_CFG = '    ligacoes_senha_segredo: str = _ler("MOVIZAP_LIGACOES_SENHA_SEGREDO")'
NOVO_CFG = ANCORA_CFG + '''

    # ---- formulários públicos (Etapa 1, 22/10) ----
    # 🚨 SEGREDO PRÓPRIO, como o das senhas de ramal: nunca o `jwt_secret`.
    # Ele assina dois tokens que saem para a internet -- a abertura do
    # formulário (para medir o tempo de preenchimento) e o desafio -- e
    # nenhum dos dois é credencial de ninguém. Separar limita o estrago se um
    # deles for analisado por quem recebeu o link.
    #
    # ⚠️ VAZIO NÃO DERRUBA O PAINEL: `movizap/formularios.py` deriva um
    # segredo do `jwt_secret` e avisa no log. Formulário público é recurso
    # novo, e recurso novo não pode impedir o serviço de subir.
    formularios_segredo: str = _ler("MOVIZAP_FORMULARIOS_SEGREDO", "")'''
print(emendar(CONFIG, ANCORA_CFG, NOVO_CFG, "MOVIZAP_FORMULARIOS_SEGREDO"))

# -------------------------------------------------------------- ratelimit.py
RATE = RAIZ / "movizap" / "ratelimit.py"
ANCORA_RATE = '''    conn.execute("CREATE TABLE IF NOT EXISTS travas (chave TEXT PRIMARY KEY, ate REAL)")
    return conn'''
NOVO_RATE = '''    conn.execute("CREATE TABLE IF NOT EXISTS travas (chave TEXT PRIMARY KEY, ate REAL)")
    # 🔵 22/10: os formularios publicos precisam contar ENVIOS, nao falhas --
    # envio e sucesso, e sucesso nenhum bloqueia aqui. Tabela separada para que
    # a conta de um nunca mexa na trava do outro.
    conn.execute("CREATE TABLE IF NOT EXISTS eventos (chave TEXT, quando REAL)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_eventos ON eventos (chave)")
    return conn'''
print(emendar(RATE, ANCORA_RATE, NOVO_RATE, "CREATE TABLE IF NOT EXISTS eventos"))

FIM_RATE = '''

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
'''
texto = RATE.read_text(encoding="utf-8")
if "def quantos_eventos" in texto:
    print("ratelimit.py: funcoes de evento ja estavam")
else:
    RATE.write_text(texto.rstrip("\n") + FIM_RATE, encoding="utf-8")
    print("ratelimit.py: funcoes de evento no fim do arquivo")

# ⚠️ O MODULO NAO TEM LOGGER, E E DE PROPOSITO: ele e o mesmo nos quatro
# paineis e engole falha do SQLite com `pass` (ver `bloqueado_por`). A emenda
# segue essa regra, entao nada aqui pode citar `log.` -- um `log.exception`
# colocado por engano só estouraria DENTRO do `except`, onde ninguém ve.
texto = RATE.read_text(encoding="utf-8")
if "import time" not in texto:
    sys.exit("ratelimit.py: falta 'import time' -- emenda incompleta")
if "log." in texto:
    sys.exit("ratelimit.py: a emenda citou `log.` e o modulo nao tem logger")

# --------------------------------------------------------------------- .env
ENV = RAIZ / ".env"
texto = ENV.read_text(encoding="utf-8")
if "MOVIZAP_FORMULARIOS_SEGREDO" in texto:
    print(".env: ja tinha o segredo")
else:
    ENV.write_text(
        texto.rstrip("\n")
        + "\n\n# ---- formularios publicos (Etapa 1, 2026-10-22) ----\n"
        + "# Assina a abertura do formulario e o desafio. NAO e credencial.\n"
        + f"MOVIZAP_FORMULARIOS_SEGREDO={secrets.token_hex(32)}\n",
        encoding="utf-8")
    print(".env: segredo gerado (nao impresso)")

# A prova: reler o estado, nunca o retorno da escrita.
sys.path.insert(0, str(RAIZ))
from movizap.config import settings  # noqa: E402

print("settings.formularios_segredo tem", len(settings.formularios_segredo),
      "caracteres")
