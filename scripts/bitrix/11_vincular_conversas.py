"""Item 5: preenche o vinculo das conversas orfas que tem candidato UNICO.

A validacao pedida pelo usuario: so vincula quando ha **um** candidato. Com
dois ou mais, a regra da casa manda mostrar os N e nao escolher -- e continua
valendo.

Alem disso, mostra se o nome do WhatsApp confere com o nome do contato. Nao e
criterio de bloqueio (muita gente usa apelido), mas e evidencia independente
de que o cruzamento acertou, e aparece para conferencia.

Uso: vincular.py [--aplicar]
"""
import re
import sys
import unicodedata

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco, cadastro  # noqa: E402

aplicar = "--aplicar" in sys.argv


def simples(s):
    s = "".join(c for c in unicodedata.normalize("NFD", s or "")
                if unicodedata.category(c) != "Mn").upper()
    return set(re.sub(r"[^A-Z ]", " ", s).split())


banco.abrir()
try:
    orfas = banco.varios(
        "SELECT id, telefone_e164, nome_whatsapp FROM conversa "
        "WHERE contato_id IS NULL AND telefone_e164 IS NOT NULL ORDER BY id")
    unicos, varios_, nenhum = [], [], 0
    for c in orfas:
        cands = cadastro.por_telefone(c["telefone_e164"])
        if not cands:
            nenhum += 1
        elif len(cands) == 1:
            unicos.append((c, cands[0]))
        else:
            varios_.append((c, cands))

    print(f"conversas sem vínculo : {len(orfas)}")
    print(f"   candidato ÚNICO    : {len(unicos)}   ← vinculáveis")
    print(f"   vários candidatos  : {len(varios_)}   ← mostra os N, não escolhe")
    print(f"   nenhum candidato   : {nenhum}\n")

    print("as que serão vinculadas (✓ = nome do WhatsApp confere com o contato):")
    confere = 0
    for c, alvo in unicos:
        bate = bool(simples(c["nome_whatsapp"]) & simples(alvo["nome"]))
        confere += int(bate)
        print(f"   {'✓' if bate else ' '} #{c['id']:4} {c['telefone_e164']:16} "
              f"{(c['nome_whatsapp'] or '—')[:20]:20} → {alvo['nome'][:24]:24} "
              f"| {(alvo['cliente_nome'] or '—')[:28]}")
    print(f"\n   nome do WhatsApp confere em {confere} de {len(unicos)}")

    if varios_:
        print("\n  NÃO vinculadas (mais de um candidato):")
        for c, cands in varios_:
            print(f"     #{c['id']} {c['telefone_e164']} → "
                  f"{[x['nome'][:24] for x in cands]}")

    if not aplicar:
        print("\n(simulação — nada gravado. Use --aplicar.)")
        raise SystemExit(0)

    with banco.cursor() as cur:
        for c, alvo in unicos:
            cur.execute(
                "UPDATE conversa SET contato_id = %s, atualizada_em = now() "
                "WHERE id = %s AND contato_id IS NULL",
                (alvo["id"], c["id"]))

    print("\nRELENDO O BANCO:")
    print("   conversas sem vínculo:",
          banco.um("SELECT count(*) n FROM conversa WHERE contato_id IS NULL")["n"])
    print("   com vínculo          :",
          banco.um("SELECT count(*) n FROM conversa WHERE contato_id IS NOT NULL")["n"])
finally:
    banco.fechar()
