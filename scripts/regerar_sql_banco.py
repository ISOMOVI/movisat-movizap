"""Regera /tmp/criar_movizap.sql a partir da senha que JA esta no .env.

Existe porque a primeira tentativa falhou por permissao: o arquivo era 600 do
usuario `claude`, e `sudo -u postgres psql -f` roda como `postgres`, que nao
consegue le-lo.

🚨 A correcao NAO e afrouxar o arquivo para 644 -- isso deixaria a senha
legivel por qualquer usuario da maquina enquanto durasse. A correcao e o
shell do ROOT abrir o arquivo e entregar por stdin:

    sudo -u postgres psql < /tmp/criar_movizap.sql

Root ja pode ler tudo; o arquivo continua 600 e ninguem mais o le.

Regerar a partir do .env (em vez de sortear outra senha) e o ponto: se
gerasse nova, o banco e o .env ficariam com senhas diferentes.
"""
import sys
from pathlib import Path

ENV = Path("/home/claude/movizap_painel/.env")
SQL = Path("/tmp/criar_movizap.sql")

valores = {}
for linha in ENV.read_text(encoding="utf-8").splitlines():
    if "=" in linha and not linha.strip().startswith("#"):
        k, _, v = linha.partition("=")
        valores[k.strip()] = v.strip()

senha = valores.get("MOVIZAP_DB_SENHA", "")
banco = valores.get("MOVIZAP_DB_NOME", "")
papel = valores.get("MOVIZAP_DB_USUARIO", "")

if not (senha and banco and papel):
    sys.exit("MOVIZAP_DB_* incompleto no .env -- rode preparar_banco.py antes")
if "'" in senha or "\\" in senha:
    sys.exit("senha com caractere que quebraria o SQL -- abortando")

SQL.write_text(f"""\
-- Gerado por regerar_sql_banco.py. CONTEM SENHA: apagar depois de aplicar.
-- Aplicar com:  sudo -u postgres psql < {SQL}
--   (o shell do root abre o arquivo; o postgres le do stdin. Nao usar -f:
--    o postgres nao consegue ler um arquivo 600 do claude.)
CREATE ROLE {papel} LOGIN PASSWORD '{senha}';
CREATE DATABASE {banco} OWNER {papel} ENCODING 'UTF8' TEMPLATE template0;
ALTER ROLE {papel} NOSUPERUSER NOCREATEDB NOCREATEROLE;
""", encoding="utf-8")
SQL.chmod(0o600)

print(f"{SQL} regerado (modo {oct(SQL.stat().st_mode)[-3:]}), senha nao impressa")
print(f"banco={banco}  papel={papel}")
