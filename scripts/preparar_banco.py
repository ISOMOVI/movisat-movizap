"""Prepara a criacao do banco `movizap`: gera a senha e escreve os arquivos.

NAO cria nada sozinho -- so produz:
  1. /tmp/criar_movizap.sql  (modo 600)  para o postgres rodar como superusuario
  2. as linhas de conexao no .env do MoviZap (modo 600)

🚨 A senha e gerada aqui e NUNCA passa por linha de comando nem e impressa.
Por isso o SQL vai num ARQUIVO: `psql -c "CREATE ROLE ... PASSWORD 'x'"`
deixaria a senha no `ps`, no historico do shell e no log do sudo.

Uso:  ./venv/bin/python preparar_banco.py
"""
import secrets
import string
import sys
from pathlib import Path

ENV = Path("/home/claude/movizap_painel/.env")
SQL = Path("/tmp/criar_movizap.sql")

BANCO = "movizap"
PAPEL = "movizap"

if not ENV.exists():
    sys.exit(f"{ENV} nao existe -- abortando")

texto = ENV.read_text(encoding="utf-8")
if "MOVIZAP_DB_SENHA=" in texto:
    sys.exit("o .env ja tem MOVIZAP_DB_SENHA -- nao vou sobrescrever. "
             "Apague a linha antes se for intencional.")

# Sem aspas, barra invertida nem cifrao: eles atrapalham em SQL, em .env e em
# string de conexao, e o ganho de entropia nao compensa o risco de erro.
alfabeto = string.ascii_letters + string.digits + "-_.~"
senha = "".join(secrets.choice(alfabeto) for _ in range(40))

SQL.write_text(f"""\
-- Gerado por preparar_banco.py. Contem senha: apagar depois de aplicar.
CREATE ROLE {PAPEL} LOGIN PASSWORD '{senha}';
CREATE DATABASE {BANCO} OWNER {PAPEL} ENCODING 'UTF8' LC_COLLATE 'pt_BR.UTF-8'
    LC_CTYPE 'pt_BR.UTF-8' TEMPLATE template0;
-- O papel nao precisa criar banco nem outro papel.
ALTER ROLE {PAPEL} NOSUPERUSER NOCREATEDB NOCREATEROLE;
""", encoding="utf-8")
SQL.chmod(0o600)

novo = texto.rstrip("\n") + f"""

# ---- banco (migracao 001, 2026-08-05) ----
MOVIZAP_DB_HOST=127.0.0.1
MOVIZAP_DB_PORTA=5432
MOVIZAP_DB_NOME={BANCO}
MOVIZAP_DB_USUARIO={PAPEL}
MOVIZAP_DB_SENHA={senha}
"""

# validar ANTES de gravar
falhas = []
if "MOVIZAP_JWT_SECRET=" not in novo:
    falhas.append("o segredo do JWT sumiu")
if "MOVIZAP_ADMIN_SENHA_HASH=" not in novo:
    falhas.append("o hash do admin sumiu")
if novo.count("MOVIZAP_DB_SENHA=") != 1:
    falhas.append("a senha do banco entrou zero ou mais de uma vez")
if len(novo) <= len(texto):
    falhas.append("o .env encolheu")

if falhas:
    SQL.unlink(missing_ok=True)
    print("NAO GRAVEI:")
    for f in falhas:
        print(f"  - {f}")
    sys.exit(1)

ENV.write_text(novo, encoding="utf-8")
ENV.chmod(0o600)

print(f"SQL para o superusuario : {SQL} (modo {oct(SQL.stat().st_mode)[-3:]})")
print(f".env atualizado         : modo {oct(ENV.stat().st_mode)[-3:]}")
print("senha gerada com 40 caracteres, nao impressa")
print()
print("Proximo passo (como root):")
print(f"  sudo -u postgres psql -f {SQL}")
print(f"  rm -f {SQL}")
