"""Item 4: o e-mail do Bitrix entra na ficha do contato que ja existe.

So preenche quem esta VAZIO. Nunca sobrescreve e-mail do Harmonit -- aquele
veio do cadastro oficial, este veio de um CRM que esta saindo.

`email_origem = 'bitrix'` diz de onde veio cada endereco.

Uso: salvar_emails.py [--aplicar]
"""
import csv
import sys

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco  # noqa: E402

ARQ = "/home/claude/movizap_bitrix/BITRIX_CHAVES.csv"
aplicar = "--aplicar" in sys.argv

with open(ARQ, encoding="utf-8-sig", newline="") as f:
    L = [r for r in csv.DictReader(f, delimiter=";") if r["TIPO"] == "email"]

banco.abrir()
try:
    antes = banco.um("SELECT count(*) n FROM contato WHERE email IS NOT NULL "
                     "AND email <> ''")["n"]
    ja = set()
    for q in ("SELECT lower(email) e FROM cliente WHERE email <> ''",
              "SELECT lower(email) e FROM contato WHERE email <> ''"):
        ja |= {r["e"] for r in banco.varios(q)}

    # o contato do Bitrix é a pessoa; casa pelo bitrix_id que gravamos
    por_bitrix = {r["bitrix_id"]: r for r in banco.varios(
        "SELECT id, bitrix_id, cliente_id, email FROM contato "
        "WHERE origem = 'bitrix' AND bitrix_id IS NOT NULL")}

    encaixam, novos_contatos, ja_tinha = [], 0, 0
    for r in L:
        if r["CHAVE"] in ja:
            ja_tinha += 1
            continue
        for cid in r["CLIENTE_ID"].split(" | "):
            if not cid.strip().isdigit():
                continue
            alvo = por_bitrix.get(f"{r['BITRIX_ID']}:{cid}")
            if alvo and not alvo["email"]:
                encaixam.append((alvo["id"], r["CHAVE"]))
            elif not alvo:
                novos_contatos += 1

    # 🚨 um contato só tem UMA coluna de e-mail: com dois endereços para a
    # mesma pessoa, fica o primeiro e o resto não entra. Dizer isso é melhor
    # do que escolher em silêncio.
    vistos, unico = set(), []
    descartados = 0
    for cid, em in encaixam:
        if cid in vistos:
            descartados += 1
            continue
        vistos.add(cid)
        unico.append((cid, em))

    print(f"e-mails no extrato              : {len(L)}")
    print(f"já existem no cadastro          : {ja_tinha}")
    print(f"encaixam em contato existente   : {len(encaixam)}")
    print(f"   → graváveis (1 por contato)  : {len(unico)}")
    print(f"   → 2º e-mail da mesma pessoa  : {descartados}  (não cabem: 1 coluna)")
    print(f"pessoas sem contato criado      : {novos_contatos}"
          "   (só tinham e-mail, não entraram com telefone)")

    if not aplicar:
        print("\n(simulação — nada gravado. Use --aplicar.)")
        raise SystemExit(0)

    with banco.cursor() as cur:
        for cid, em in unico:
            cur.execute(
                "UPDATE contato SET email = %s, email_origem = 'bitrix', "
                "atualizado_em = now() WHERE id = %s AND coalesce(email,'') = ''",
                (em, cid))

    print("\nRELENDO O BANCO:")
    dep = banco.um("SELECT count(*) n FROM contato WHERE email IS NOT NULL "
                   "AND email <> ''")["n"]
    print(f"   contatos com e-mail: {antes} → {dep}  ({dep - antes:+})")
    print(f"   email_origem='bitrix': "
          f"{banco.um(chr(83)+chr(69)+'LECT count(*) n FROM contato WHERE email_origem=%s', ('bitrix',))['n']}")
    print(f"   contatos do Harmonit com e-mail alterado hoje: "
          f"{banco.um('SELECT count(*) n FROM contato WHERE origem=%s AND email_origem=%s', ('harmonit','bitrix'))['n']}"
          "  (tem que ser 0)")
finally:
    banco.fechar()
