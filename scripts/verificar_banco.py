"""Confere o banco `movizap` contra o modelo aprovado, lendo o catalogo.

Nao confia no retorno do psql: le pg_catalog e afirma o que existe.
A senha sai do .env pelo proprio modulo de config -- nunca de argumento nem
de variavel de ambiente exportada no shell.
"""
import sys
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")
import psycopg  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
cfg = {}
for l in ENV.read_text(encoding="utf-8").splitlines():
    if "=" in l and not l.strip().startswith("#"):
        k, _, v = l.partition("=")
        cfg[k.strip()] = v.strip()

TABELAS = [
    "cliente", "contato", "contato_papel", "contato_telefone",
    "atendente", "atendente_jornada", "time", "atendente_time",
    "atendente_time_permissao", "classificacao", "config",
    "canal", "canal_evento", "conversa", "transferencia",
    "midia", "mensagem", "prompt_versao", "sync_execucao",
    "schema_migracao",
]

falhas = []

with psycopg.connect(
    host=cfg["MOVIZAP_DB_HOST"], port=cfg["MOVIZAP_DB_PORTA"],
    dbname=cfg["MOVIZAP_DB_NOME"], user=cfg["MOVIZAP_DB_USUARIO"],
    password=cfg["MOVIZAP_DB_SENHA"],
) as conn:
    cur = conn.cursor()

    print("== 1. tabelas ==")
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    existem = {r[0] for r in cur.fetchall()}
    faltando = [t for t in TABELAS if t not in existem]
    sobrando = existem - set(TABELAS)
    print(f"  {len(existem)} tabela(s); esperadas {len(TABELAS)}")
    if faltando:
        print(f"  FALTANDO: {faltando}"); falhas.append("tabelas faltando")
    if sobrando:
        print(f"  inesperadas: {sorted(sobrando)}")

    print("\n== 2. os indices que NAO sao opcionais ==")
    criticos = {
        "ux_mensagem_id_externo": "idempotencia do webhook",
        "ix_telefone_e164": "lookup de toda mensagem que chega",
        "ux_conversa_aberta": "uma conversa aberta por telefone",
        "ix_conversa_fila": "a fila e a tela mais aberta do dia",
        "ix_mensagem_conversa": "rolagem do historico",
        "ix_conversa_inatividade": "varredura do repasse",
        "ux_atendente_login": "Admin e admin sao a MESMA conta",
    }
    cur.execute("SELECT indexname FROM pg_indexes WHERE schemaname='public'")
    idx = {r[0] for r in cur.fetchall()}
    for nome, porque in criticos.items():
        ok = nome in idx
        print(f"  [{'OK  ' if ok else 'FALHA'}] {nome:<26} {porque}")
        if not ok:
            falhas.append(f"indice {nome}")

    print("\n== 3. travas que o modelo exige ==")
    provas = [
        ("nota interna nao pode ser 'saida'",
         "INSERT INTO conversa (canal_id,telefone_e164) VALUES (1,'x')", None),
    ]
    # (a) CHECK da nota interna
    cur.execute("""SELECT COUNT(*) FROM pg_constraint
                   WHERE conname='ck_nota_e_interna'""")
    ok = cur.fetchone()[0] == 1
    print(f"  [{'OK  ' if ok else 'FALHA'}] ck_nota_e_interna  (nota nunca sai para o cliente)")
    if not ok:
        falhas.append("check da nota interna")

    # (b) avaliacao so aceita 1..5
    cur.execute("""SELECT pg_get_constraintdef(oid) FROM pg_constraint
                   WHERE conrelid='conversa'::regclass AND contype='c'""")
    defs = " ".join(r[0] for r in cur.fetchall())
    ok = "avaliacao" in defs and "1" in defs and "5" in defs
    print(f"  [{'OK  ' if ok else 'FALHA'}] avaliacao entre 1 e 5")
    if not ok:
        falhas.append("check da avaliacao")

    # (c) UNIQUE parcial da conversa aberta
    cur.execute("""SELECT indexdef FROM pg_indexes
                   WHERE indexname='ux_conversa_aberta'""")
    linha = cur.fetchone()
    ok = bool(linha) and "resolvida" in linha[0] and "UNIQUE" in linha[0]
    print(f"  [{'OK  ' if ok else 'FALHA'}] conversa aberta e unica por telefone+canal")
    if not ok:
        falhas.append("unique parcial da conversa")

    print("\n== 4. semente ==")
    for tabela, esperado in (("time", 7), ("classificacao", 9), ("config", 5)):
        cur.execute(f"SELECT COUNT(*) FROM {tabela}")
        n = cur.fetchone()[0]
        ok = n == esperado
        print(f"  [{'OK  ' if ok else 'FALHA'}] {tabela:<15} {n} linha(s), esperado {esperado}")
        if not ok:
            falhas.append(f"semente de {tabela}")

    cur.execute("SELECT nome FROM time ORDER BY id")
    print("     times:", ", ".join(r[0] for r in cur.fetchall()))
    cur.execute("SELECT nome FROM classificacao WHERE exige_comentario")
    print("     exige comentario:", ", ".join(r[0] for r in cur.fetchall()))

    print("\n== 5. migracao registrada ==")
    cur.execute("SELECT versao, descricao FROM schema_migracao ORDER BY versao")
    for v, d in cur.fetchall():
        print(f"  {v}  {d}")

    print("\n== 6. o papel nao tem privilegio a mais ==")
    cur.execute("SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles "
                "WHERE rolname=current_user")
    s, cdb, crole = cur.fetchone()
    ok = not (s or cdb or crole)
    print(f"  [{'OK  ' if ok else 'FALHA'}] super={s} createdb={cdb} createrole={crole}")
    if not ok:
        falhas.append("privilegio excessivo")

print()
if falhas:
    print("!! " + "; ".join(falhas))
    sys.exit(1)
print("Banco conferido contra o catalogo, nao contra o retorno do psql.")
