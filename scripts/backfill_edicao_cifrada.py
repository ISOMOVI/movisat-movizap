"""Backfill cirurgico da edicao cifrada -- SO o numero de teste.

Sem argumento: so mostra. Com --aplicar: marca o original como editado (com a
hora da edicao) e apaga a linha-lixo, numa transacao.
"""
import json
import sys

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco  # noqa: E402
from movizap.conversas import AVISOS  # noqa: E402

TELEFONE = "+5518998116168"
APLICAR = "--aplicar" in sys.argv
AVISO = AVISOS["secretEncryptedMessage"]

banco.abrir()

# Quem aponta para mensagem(id): a linha-lixo nao pode ser apagada se algo
# depende dela.
fks = banco.varios(
    """SELECT conrelid::regclass::text tabela, a.attname coluna
         FROM pg_constraint c
         JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE c.contype = 'f' AND c.confrelid = 'mensagem'::regclass""")
print("FKs para mensagem:", [(f["tabela"], f["coluna"]) for f in fks])

lixo = banco.varios(
    """SELECT m.id, m.id_externo, m.criada_em, m.conversa_id
         FROM mensagem m JOIN conversa c ON c.id = m.conversa_id
        WHERE c.telefone_e164 = %s AND m.conteudo = %s
        ORDER BY m.id""", (TELEFONE, AVISO))
print(f"linhas-lixo no numero de teste: {len(lixo)}")

planos = []
for l in lixo:
    ev = banco.um(
        """SELECT payload FROM webhook_evento
            WHERE id_externo = %s AND evento = 'messages.upsert'
            ORDER BY id LIMIT 1""", (l["id_externo"],))
    sec = (((ev or {}).get("payload") or {}).get("data") or {}) \
        .get("message", {}).get("secretEncryptedMessage") or {}
    alvo_id = (sec.get("targetMessageKey") or {}).get("id")
    tipo = sec.get("secretEncType")
    original = banco.um(
        """SELECT id, conversa_id, LEFT(conteudo, 60) c, editada_em, conteudo_original
             FROM mensagem WHERE id_externo = %s""", (alvo_id,)) if alvo_id else None
    deps = []
    for f in fks:
        n = banco.um(f'SELECT count(*) n FROM {f["tabela"]} WHERE {f["coluna"]} = %s',
                     (l["id"],))["n"]
        if n:
            deps.append(f"{f['tabela']}.{f['coluna']}={n}")
    ok = (str(tipo) == "2" and original is not None
          and original["conversa_id"] == l["conversa_id"] and not deps)
    print(f"  lixo id={l['id']} em={l['criada_em']} encType={tipo} "
          f"-> original={original and original['id']} '{original and original['c']}' "
          f"deps={deps or '-'} {'OK' if ok else 'PULA'}")
    if ok:
        planos.append((l, original))

if not APLICAR:
    print(f"\n{len(planos)} a corrigir. Rode com --aplicar.")
    banco.fechar()
    sys.exit()

with banco.cursor() as cur:
    for l, original in planos:
        cur.execute(
            "UPDATE mensagem SET editada_em = %s WHERE id = %s AND conteudo_original IS NULL",
            (l["criada_em"], original["id"]))
        assert cur.rowcount == 1, f"original {original['id']} nao atualizado"
        cur.execute("DELETE FROM mensagem WHERE id = %s AND conteudo = %s",
                    (l["id"], AVISO))
        assert cur.rowcount == 1, f"lixo {l['id']} nao apagado"
print(f"aplicado em {len(planos)}")

# Releitura do estado (a confirmacao e o banco, nao o retorno do comando)
for l, original in planos:
    o = banco.um("SELECT editada_em, conteudo_original, LEFT(conteudo,60) c FROM mensagem WHERE id = %s",
                 (original["id"],))
    some = banco.um("SELECT count(*) n FROM mensagem WHERE id = %s", (l["id"],))["n"]
    print(f"  original {original['id']}: editada_em={o['editada_em']} "
          f"original_null={o['conteudo_original'] is None} texto='{o['c']}' | lixo {l['id']} existe={some}")
banco.fechar()
