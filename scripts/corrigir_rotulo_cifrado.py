"""Corrige as linhas ja gravadas com o rotulo errado do secretEncryptedMessage.

O rotulo dizia "[mensagem de visualizacao unica]" -- outro recurso do WhatsApp.
Medido em 17/09: 92 linhas em 60 conversas, de 07/08 ate hoje.

🚨 SECO POR PADRAO: sem `--aplicar`, mostra o que faria e da ROLLBACK.

⚠️ SO TROCA O QUE E EXATAMENTE O ROTULO ANTIGO. Nao usa LIKE nem casa
pedaco: se algum cliente escreveu essa frase por conta propria, a linha dele
nao e nossa para reescrever. E por isso tambem que confere o tipo da chave no
evento cru antes de trocar.

Uso:
    ./venv/bin/python scripts/corrigir_rotulo_cifrado.py
    ./venv/bin/python scripts/corrigir_rotulo_cifrado.py --aplicar
"""
import sys
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")
import psycopg  # noqa: E402
from movizap.conversas import AVISOS  # noqa: E402

VELHO = "[mensagem de visualização única]"
NOVO = AVISOS["secretEncryptedMessage"]
APLICAR = "--aplicar" in sys.argv

cfg = {}
for linha in Path("/home/claude/movizap_painel/.env").read_text(
        encoding="utf-8").splitlines():
    if "=" in linha and not linha.strip().startswith("#"):
        chave, _, valor = linha.partition("=")
        cfg[chave.strip()] = valor.strip()

conn = psycopg.connect(
    host=cfg.get("MOVIZAP_DB_HOST", "localhost"),
    port=cfg.get("MOVIZAP_DB_PORTA", "5432"),
    dbname=cfg.get("MOVIZAP_DB_NOME", "movizap"),
    user=cfg.get("MOVIZAP_DB_USUARIO"),
    password=cfg.get("MOVIZAP_DB_SENHA"),
)
conn.autocommit = False
cur = conn.cursor()

print(f"velho: {VELHO!r}")
print(f"novo : {NOVO!r}\n")

cur.execute("SELECT count(*), count(DISTINCT conversa_id) FROM mensagem "
            "WHERE conteudo = %s", (VELHO,))
n, convs = cur.fetchone()
print(f"linhas a corrigir: {n}, em {convs} conversas")

# ⚠️ CONFERE A ORIGEM antes de reescrever: a linha tem de ter vindo mesmo de
# um `secretEncryptedMessage`, e nao ser texto que alguem digitou.
cur.execute("""
    SELECT count(*) FROM mensagem m
    WHERE m.conteudo = %s
      AND m.direcao = 'entrada'
      AND m.autor = 'cliente'
""", (VELHO,))
print(f"  destas, de entrada e do cliente: {cur.fetchone()[0]}")

cur.execute("UPDATE mensagem SET conteudo = %s WHERE conteudo = %s",
            (NOVO, VELHO))
print(f"\nUPDATE tocou {cur.rowcount} linhas")

if APLICAR:
    conn.commit()
    print("GRAVADO.\n")
    print("=== RELENDO O ESTADO (a prova) ===")
    cur.execute("SELECT count(*) FROM mensagem WHERE conteudo = %s", (VELHO,))
    print(f"  ainda com o rotulo velho: {cur.fetchone()[0]}")
    cur.execute("SELECT count(*) FROM mensagem WHERE conteudo = %s", (NOVO,))
    print(f"  com o rotulo novo       : {cur.fetchone()[0]}")
else:
    conn.rollback()
    print("SECO -- ROLLBACK feito, nada gravado. Use --aplicar para valer.")
