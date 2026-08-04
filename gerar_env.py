"""Gera o .env do MoviZap sem que a senha passe por linha de comando.

Lê a senha de um arquivo temporário (modo 600), grava só o HASH no .env e
apaga o temporário. Nada de segredo é impresso -- só a confirmação.

Uso:  ./venv/bin/python gerar_env.py /tmp/pw
"""
import os
import secrets
import sys
from pathlib import Path

from passlib.context import CryptContext

RAIZ = Path(__file__).resolve().parent
ENV = RAIZ / ".env"

if len(sys.argv) < 2:
    sys.exit("uso: gerar_env.py <arquivo_com_a_senha>")

arquivo_senha = Path(sys.argv[1])
if not arquivo_senha.exists():
    sys.exit(f"não encontrei {arquivo_senha}")

if ENV.exists():
    sys.exit(f"{ENV} já existe -- não vou sobrescrever. Apague antes se for intencional.")

senha = arquivo_senha.read_text(encoding="utf-8").strip()
if not senha:
    sys.exit("arquivo da senha está vazio")

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

conteudo = f"""# MoviZap -- gerado automaticamente. NUNCA versionar.
APP_NOME=MoviZap
DOMINIO=movizap.movisat.com.br
PORTA=8008
AMBIENTE=desenvolvimento

MOVIZAP_JWT_SECRET={secrets.token_urlsafe(48)}
MOVIZAP_ADMIN_LOGIN=movizap
MOVIZAP_ADMIN_SENHA_HASH={pwd_ctx.hash(senha)}

FPSL_BASE_URL=http://127.0.0.1:8005
"""

# grava com 600 desde o nascimento, não depois -- não existe janela aberta
fd = os.open(ENV, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as f:
    f.write(conteudo)

# destrói o temporário: sobrescreve antes de remover
tamanho = arquivo_senha.stat().st_size
with open(arquivo_senha, "wb") as f:
    f.write(b"\x00" * tamanho)
arquivo_senha.unlink()

print(f".env criado com modo {oct(ENV.stat().st_mode)[-3:]}")
print(f"arquivo temporário da senha destruído: {arquivo_senha}")
print("nenhum segredo foi impresso")
