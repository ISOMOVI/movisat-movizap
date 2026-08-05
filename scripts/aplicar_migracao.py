"""Aplica uma migração .sql no banco `movizap`.

Existe para a senha NUNCA passar por `PGPASSWORD=` nem por argumento: a
conexão sai do .env pelo psycopg, igual ao resto do projeto.

  🚨 Em 05/08 a migração 001 foi aplicada com `export PGPASSWORD=$(...)`.
  A senha não apareceu em argv nem no histórico, mas variável de ambiente é
  legível em /proc pelo próprio usuário. Este script fecha esse caminho.

Recusa reaplicar versão que já está em schema_migracao.

Uso:  ./venv/bin/python scripts/aplicar_migracao.py migracoes/002_indices_fk.sql
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")
import psycopg  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")

if len(sys.argv) < 2:
    sys.exit("uso: aplicar_migracao.py <arquivo.sql>")

arquivo = Path(sys.argv[1])
if not arquivo.exists():
    sys.exit(f"nao encontrei {arquivo}")

sql = arquivo.read_text(encoding="utf-8")

m = re.search(r"INSERT INTO schema_migracao.*?VALUES \('(\d+)'", sql, re.S)
if not m:
    sys.exit("a migracao nao registra a propria versao em schema_migracao "
             "-- sem isso nao da para saber o que ja rodou")
versao = m.group(1)

cfg = {}
for l in ENV.read_text(encoding="utf-8").splitlines():
    if "=" in l and not l.strip().startswith("#"):
        k, _, v = l.partition("=")
        cfg[k.strip()] = v.strip()

with psycopg.connect(
    host=cfg["MOVIZAP_DB_HOST"], port=cfg["MOVIZAP_DB_PORTA"],
    dbname=cfg["MOVIZAP_DB_NOME"], user=cfg["MOVIZAP_DB_USUARIO"],
    password=cfg["MOVIZAP_DB_SENHA"],
) as conn:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM schema_migracao WHERE versao=%s", (versao,))
    if cur.fetchone():
        print(f"migracao {versao} JA FOI APLICADA -- nada a fazer")
        sys.exit(0)

    # O proprio arquivo abre BEGIN/COMMIT: ou entra inteiro, ou nada entra.
    cur.execute(sql)
    conn.commit()

    cur.execute("SELECT versao, aplicada_em, descricao FROM schema_migracao "
                "ORDER BY versao")
    print("migracoes aplicadas:")
    for v, quando, desc in cur.fetchall():
        print(f"  {v}  {quando:%Y-%m-%d %H:%M}  {desc}")
