"""Limpa as linhas-lixo da edicao cifrada do cliente -- TODAS as conversas.

🔵 Decisao dele em 19/10: *"se for lixo, ja deveria ter sumido"*. O
`backfill_edicao_cifrada.py` fez o mesmo so no numero de teste (3 linhas, 06/10);
este roda na base inteira.

DUAS situacoes, e elas NAO sao a mesma coisa:

  ATRIBUIVEL -- o `webhook_evento` daquela mensagem ainda existe e diz qual
    mensagem foi editada. Entao o original recebe `editada_em` (a marca que a
    tela mostra) e a linha-lixo sai. Nada se perde: a informacao muda de lugar.

  ORFA -- o evento bruto ja foi levado pelo expurgo de 30 dias
    (`expurgar_webhook.py`, 04:35). Nao ha como saber qual mensagem foi editada,
    entao a linha so sai. 🚨 ISTO PERDE INFORMACAO: a linha era o unico
    sinal de que houve uma edicao ali. O que ela dizia, porem, era uma frase
    generica sem apontar nada -- e e por isso que ele a chamou de lixo. Exige
    `--orfas`, para a perda ser escolhida e nao um efeito colateral.

Uso:
  ./venv/bin/python scripts/limpar_lixo_edicao_cifrada.py              # so mostra
  ./venv/bin/python scripts/limpar_lixo_edicao_cifrada.py --aplicar --limite 1
  ./venv/bin/python scripts/limpar_lixo_edicao_cifrada.py --aplicar --orfas

⚠️ A confirmacao e RELER O BANCO, nunca o retorno do comando.
"""
import sys

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco  # noqa: E402
from movizap.conversas import AVISOS  # noqa: E402

APLICAR = "--aplicar" in sys.argv
ORFAS = "--orfas" in sys.argv
LIMITE = None
if "--limite" in sys.argv:
    LIMITE = int(sys.argv[sys.argv.index("--limite") + 1])

AVISO = AVISOS["secretEncryptedMessage"]

banco.abrir()

# Quem aponta para mensagem(id): linha com dependencia NAO se apaga.
fks = banco.varios(
    """SELECT conrelid::regclass::text tabela, a.attname coluna
         FROM pg_constraint c
         JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE c.contype = 'f' AND c.confrelid = 'mensagem'::regclass""")
print("FKs para mensagem:", [(f["tabela"], f["coluna"]) for f in fks])

lixo = banco.varios(
    """SELECT m.id, m.id_externo, m.criada_em, m.conversa_id
         FROM mensagem m WHERE m.conteudo = %s ORDER BY m.id""", (AVISO,))
print(f"linhas-lixo na base: {len(lixo)}")

atribuiveis, orfas, presas = [], [], []
for l in lixo:
    ev = banco.um(
        """SELECT payload FROM webhook_evento
            WHERE id_externo = %s AND evento = 'messages.upsert'
            ORDER BY id LIMIT 1""", (l["id_externo"],))
    dados = ((ev or {}).get("payload") or {}).get("data") or {}
    sec = (dados.get("message") or {}).get("secretEncryptedMessage") or {}
    alvo_id = (sec.get("targetMessageKey") or {}).get("id")
    tipo = sec.get("secretEncType")
    original = banco.um(
        """SELECT id, conversa_id, editada_em, conteudo_original
             FROM mensagem WHERE id_externo = %s""", (alvo_id,)) if alvo_id else None
    deps = []
    for f in fks:
        n = banco.um(f'SELECT count(*) n FROM {f["tabela"]} WHERE {f["coluna"]} = %s',
                     (l["id"],))["n"]
        if n:
            deps.append(f"{f['tabela']}.{f['coluna']}={n}")
    if deps:
        presas.append((l, deps))
    elif (str(tipo) == "2" and original is not None
            and original["conversa_id"] == l["conversa_id"]):
        atribuiveis.append((l, original))
    else:
        orfas.append(l)

print()
print(f"  atribuiveis (marcam o original e saem): {len(atribuiveis)}")
print(f"  orfas (sem evento bruto; so saem, com --orfas): {len(orfas)}")
print(f"  presas por dependencia (NAO se apagam): {len(presas)}")
for l, deps in presas:
    print(f"    lixo id={l['id']} deps={deps}")

plano_at = atribuiveis[:LIMITE] if LIMITE else atribuiveis
plano_or = (orfas[:LIMITE] if LIMITE else orfas) if ORFAS else []

if not APLICAR:
    print()
    print(f"Nada feito. Com --aplicar: {len(plano_at)} atribuivel(is)"
          f" e {len(plano_or)} orfa(s).")
    banco.fechar()
    sys.exit()

with banco.cursor() as cur:
    for l, original in plano_at:
        cur.execute(
            "UPDATE mensagem SET editada_em = COALESCE(editada_em, %s) WHERE id = %s",
            (l["criada_em"], original["id"]))
        assert cur.rowcount == 1, f"original {original['id']} nao atualizado"
        cur.execute("DELETE FROM mensagem WHERE id = %s AND conteudo = %s",
                    (l["id"], AVISO))
        assert cur.rowcount == 1, f"lixo {l['id']} nao apagado"
    for l in plano_or:
        cur.execute("DELETE FROM mensagem WHERE id = %s AND conteudo = %s",
                    (l["id"], AVISO))
        assert cur.rowcount == 1, f"orfa {l['id']} nao apagada"

print()
print(f"aplicado: {len(plano_at)} atribuivel(is), {len(plano_or)} orfa(s)")

# ---------------------------------------------------- releitura (a prova)
for l, original in plano_at:
    o = banco.um("SELECT editada_em, conteudo_original FROM mensagem WHERE id = %s",
                 (original["id"],))
    some = banco.um("SELECT count(*) n FROM mensagem WHERE id = %s", (l["id"],))["n"]
    print(f"  original {original['id']}: editada_em={o['editada_em']} "
          f"texto_novo_ilegivel={o['conteudo_original'] is None} | lixo {l['id']} existe={some}")
for l in plano_or:
    some = banco.um("SELECT count(*) n FROM mensagem WHERE id = %s", (l["id"],))["n"]
    print(f"  orfa {l['id']} existe={some}")

print()
print("sobram na base:",
      banco.um("SELECT count(*) n FROM mensagem WHERE conteudo = %s", (AVISO,))["n"])
banco.fechar()
