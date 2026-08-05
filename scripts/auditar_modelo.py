"""Audita o banco `movizap` CONTRA o documento aprovado.

Nao confere "o banco esta de pe" -- confere se o que esta nele e o que o
usuario aprovou. Duas direcoes:

  campo no DOC e nao no BANCO  -> implementei a menos
  campo no BANCO e nao no DOC  -> implementei a mais, sem aprovacao

O segundo e o que ninguem procura, e e o que vira surpresa.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")
import psycopg  # noqa: E402

DOC = Path("/home/claude/movizap_painel/docs/02_Modelo_Dados.md")
ENV = Path("/home/claude/movizap_painel/.env")

cfg = {}
for l in ENV.read_text(encoding="utf-8").splitlines():
    if "=" in l and not l.strip().startswith("#"):
        k, _, v = l.partition("=")
        cfg[k.strip()] = v.strip()

texto = DOC.read_text(encoding="utf-8")

# Campos citados no doc: `nome` em tabela markdown, ou `a · b · c` em linha
# solta. Deliberadamente generoso -- falso positivo aqui custa uma olhada.
citados = set(re.findall(r"`([a-z][a-z0-9_]{2,})`", texto))

# Ruido conhecido: nomes de tabela, valores de enum, termos do texto.
IGNORAR = {
    "harmonit", "movizap", "evolution", "email", "baileys", "cloud_api",
    "atendimento", "informativo", "cliente", "fornecedor", "parceiro",
    "tecnico", "lead", "assinar", "central_24h", "financeiro", "nova",
    "bot", "fila", "humano", "resolvida", "adiada", "entrada", "saida",
    "interna", "texto", "imagem", "audio", "video", "documento",
    "figurinha", "localizacao", "contato", "sistema", "nota", "pendente",
    "enviada", "entregue", "lida", "falhou", "manual", "inatividade",
    "ia_triagem", "sem_time", "cron", "disponivel", "ausente",
    "nao_perturbe", "desconectado", "aguardando_qr", "pareando",
    "conectado", "caiu", "mensagem", "conversa", "canal", "midia",
    "atendente", "classificacao", "config", "transferencia", "time",
    "prompt_versao", "sync_execucao", "canal_evento", "contato_papel",
    "contato_telefone", "atendente_jornada", "atendente_time",
    "atendente_time_permissao", "schema_migracao", "outro", "telefone",
    "telefone2", "celular", "whatsapp", "data", "lista", "sumario",
    "veiculo", "contrato", "fatura", "activity", "list", "dict",
}
citados -= IGNORAR

with psycopg.connect(
    host=cfg["MOVIZAP_DB_HOST"], port=cfg["MOVIZAP_DB_PORTA"],
    dbname=cfg["MOVIZAP_DB_NOME"], user=cfg["MOVIZAP_DB_USUARIO"],
    password=cfg["MOVIZAP_DB_SENHA"],
) as conn:
    cur = conn.cursor()
    cur.execute("""SELECT table_name, column_name FROM information_schema.columns
                   WHERE table_schema='public' ORDER BY table_name, ordinal_position""")
    colunas = {}
    for t, c in cur.fetchall():
        colunas.setdefault(t, []).append(c)

    no_banco = {c for cols in colunas.values() for c in cols}

    print("== 1. campo citado no DOC que NAO existe no banco ==")
    faltando = sorted(c for c in citados if c not in no_banco)
    if faltando:
        for c in faltando:
            print(f"  ? {c}")
        print("  (alguns podem ser texto do doc, nao campo -- conferir a olho)")
    else:
        print("  nenhum")

    print("\n== 2. campo no BANCO que o DOC nao cita ==")
    print("   🚨 e o que ninguem procura: implementado sem aprovacao")
    extras = sorted(c for c in no_banco if c not in citados and c not in IGNORAR)
    for c in extras:
        onde = [t for t, cols in colunas.items() if c in cols]
        print(f"  + {c:<24} em {', '.join(onde)}")
    if not extras:
        print("  nenhum")

    print("\n== 3. FK sem indice (varredura sequencial na juncao) ==")
    cur.execute("""
        SELECT c.conrelid::regclass::text, a.attname
        FROM pg_constraint c
        JOIN unnest(c.conkey) k(attnum) ON true
        JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum
        WHERE c.contype='f'
          AND NOT EXISTS (
            SELECT 1 FROM pg_index i
            WHERE i.indrelid=c.conrelid AND a.attnum = i.indkey[0])
        ORDER BY 1,2""")
    sem = cur.fetchall()
    for t, col in sem:
        print(f"  - {t}.{col}")
    if not sem:
        print("  nenhuma")

    print("\n== 4. tabela sem PK ==")
    cur.execute("""SELECT t.tablename FROM pg_tables t
                   WHERE t.schemaname='public' AND NOT EXISTS (
                     SELECT 1 FROM pg_constraint c
                     WHERE c.conrelid=(t.schemaname||'.'||t.tablename)::regclass
                       AND c.contype='p')""")
    sem_pk = [r[0] for r in cur.fetchall()]
    print("  " + (", ".join(sem_pk) if sem_pk else "nenhuma"))

    print("\n== 5. coluna NOT NULL sem default em tabela que vai receber INSERT ==")
    cur.execute("""SELECT table_name, column_name FROM information_schema.columns
                   WHERE table_schema='public' AND is_nullable='NO'
                     AND column_default IS NULL
                     AND table_name IN ('conversa','mensagem','contato','cliente')
                   ORDER BY 1,2""")
    for t, c in cur.fetchall():
        print(f"  {t}.{c}  (obrigatorio no INSERT)")

print("\nAuditoria comparou o banco com o documento, nao com a memoria.")
