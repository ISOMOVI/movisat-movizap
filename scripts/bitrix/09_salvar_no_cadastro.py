"""Salva no cadastro os numeros do Bitrix que TEM WhatsApp, na empresa deles.

Um contato por pessoa do Bitrix, ligado ao cliente. O telefone entra com
`tem_whatsapp = true` porque o Evolution ja respondeu -- nao e suposicao.

`origem = 'bitrix'` e `origem_campo = 'bitrix'`: e o que separa esta linha do
cadastro do Harmonit, e o que permite desfazer tudo com um DELETE.

Uso:  salvar.py            simulacao
      salvar.py --aplicar
"""
import csv
import sys

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco  # noqa: E402

ARQ = "/home/claude/movizap_bitrix/BITRIX_CHAVES.csv"
TEM = {"sim", "verificado", "conversa", "wazzup"}
aplicar = "--aplicar" in sys.argv

with open(ARQ, encoding="utf-8-sig", newline="") as f:
    L = list(csv.DictReader(f, delimiter=";"))

banco.abrir()
try:
    antes = {t: banco.um(f"SELECT count(*) n FROM {t}")["n"]
             for t in ("cliente", "contato", "contato_telefone")}
    ja = {r["e164"] for r in banco.varios("SELECT DISTINCT e164 FROM contato_telefone")}
    ativos = {r["id"] for r in banco.varios("SELECT id FROM cliente WHERE ativo")}

    # o que entra: telefone com WhatsApp, ainda fora do cadastro
    entram = []
    for r in L:
        if r["TIPO"] != "telefone" or r["WHATSAPP"] not in TEM:
            continue
        if r["CHAVE"] in ja:
            continue
        for i in r["CLIENTE_ID"].split(" | "):
            if i.strip().isdigit() and int(i) in ativos:
                entram.append((int(i), r))

    pessoas = {(c, r["BITRIX_ID"]) for c, r in entram}
    print(f"telefones com WhatsApp a entrar : {len({r['CHAVE'] for _, r in entram})}")
    print(f"linhas (número × cliente)       : {len(entram)}")
    print(f"contatos a criar                : {len(pessoas)}")
    print(f"clientes que recebem            : {len({c for c, _ in entram})}")

    if not aplicar:
        print("\n(simulação — nada gravado. Use --aplicar.)")
        raise SystemExit(0)

    criados = tel = 0
    with banco.cursor() as cur:
        for cliente_id, r in entram:
            cur.execute(
                """INSERT INTO contato
                     (cliente_id, nome, relacao, origem, bitrix_id, ativo,
                      atualizado_em)
                   VALUES (%s, %s, 'cliente', 'bitrix', %s, true, now())
                   ON CONFLICT (bitrix_id) WHERE bitrix_id IS NOT NULL
                   DO UPDATE SET atualizado_em = now()
                   RETURNING id, (xmax = 0) AS criou""",
                (cliente_id, r["PESSOA"] or r["EMPRESA_BITRIX"] or "(sem nome)",
                 f"{r['BITRIX_ID']}:{cliente_id}"))
            linha = cur.fetchone()
            criados += int(linha["criou"])
            cur.execute(
                """INSERT INTO contato_telefone
                     (contato_id, e164, bruto, origem_campo, principal,
                      tem_whatsapp, verificado_em)
                   VALUES (%s, %s, %s, 'bitrix', false, true, now())
                   ON CONFLICT (contato_id, e164) DO NOTHING""",
                (linha["id"], r["CHAVE"], r["BRUTO"]))
            tel += cur.rowcount

    print(f"\ncontatos criados : {criados}")
    print(f"telefones gravados: {tel}")

    # 🚨 a prova e reler o estado
    print("\n=== RELENDO O BANCO ===")
    for t in ("cliente", "contato", "contato_telefone"):
        d = banco.um(f"SELECT count(*) n FROM {t}")["n"]
        print(f"   {t:18} {antes[t]:6} → {d:6}  ({d - antes[t]:+})")
    print(f"   contatos origem=bitrix : "
          f"{banco.um(chr(83) + 'ELECT count(*) n FROM contato WHERE origem = ' + chr(39) + 'bitrix' + chr(39))['n']}")
    print(f"   telefones origem=bitrix: "
          f"{banco.um('SELECT count(*) n FROM contato_telefone WHERE origem_campo = ' + chr(39) + 'bitrix' + chr(39))['n']}")
    alc = banco.um("""SELECT count(DISTINCT ct.cliente_id) n
                        FROM contato_telefone t JOIN contato ct ON ct.id = t.contato_id
                       WHERE t.tem_whatsapp IS TRUE AND ct.cliente_id IS NOT NULL""")["n"]
    print(f"\n   clientes alcançáveis por WhatsApp: {alc}")
finally:
    banco.fechar()
