"""O extrato final: UMA LINHA POR CHAVE (telefone ou e-mail).

A pergunta que este arquivo responde e "chegou este numero -- de quem e?".
Por isso a chave e a primeira coluna e cada linha e uma so chave: telefone em
E164 (mesma forma que o painel guarda) ou e-mail em minuscula.

Entra so o que serve a essa pergunta: chave, pessoa, empresa e o cliente do
Harmonit. Todo o resto do Bitrix fica de fora.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import telefone  # noqa: E402

ORIGEM = Path("/home/claude/movizap_bitrix/BITRIX_CLIENTES_ATIVOS.csv")
DESTINO = Path("/home/claude/movizap_bitrix/BITRIX_CHAVES.csv")

COLS_TEL = ("Telefone de trabalho", "Celular", "Telefone de casa",
            "Outro número de telefone")
COLS_EM = ("Email de trabalho", "E-mail de casa", "Outro e-mail")

with ORIGEM.open(encoding="utf-8-sig", newline="") as f:
    linhas = list(csv.DictReader(f, delimiter=";"))
print(f"contatos lidos: {len(linhas)}")

vistos = set()
saida = []
descartados = 0
for L in linhas:
    pessoa = " ".join(x for x in (L.get("Nome", ""), L.get("Sobrenome", "")) if x).strip()
    base = {
        "PESSOA": pessoa,
        "EMPRESA_BITRIX": L.get("Empresa", "").strip(),
        "CLIENTE_ID": L["CLIENTE_ID"],
        "CLIENTE_NOME": L["CLIENTE_NOME"],
        "CLIENTE_CNPJ": L["CLIENTE_CNPJ"],
        "CLIENTE_QTD": L["CLIENTE_QTD"],
        "VIA": L["VIA"],
        "BITRIX_ID": L.get("ID", ""),
    }
    for col in COLS_TEL:
        for parte in (L.get(col) or "").replace("/", ";").replace(",", ";").split(";"):
            if not parte.strip():
                continue
            a = telefone.analisar(parte)
            if not a:
                descartados += 1
                continue
            chave = ("telefone", a.e164, base["CLIENTE_ID"])
            if chave in vistos:
                continue
            vistos.add(chave)
            saida.append({**base, "CHAVE": a.e164, "TIPO": "telefone",
                          "ORIGEM_CAMPO": col, "BRUTO": parte.strip()})
    for col in COLS_EM:
        for parte in (L.get(col) or "").replace(",", ";").split(";"):
            e = parte.strip().lower()
            if "@" not in e or "." not in e:
                if e:
                    descartados += 1
                continue
            chave = ("email", e, base["CLIENTE_ID"])
            if chave in vistos:
                continue
            vistos.add(chave)
            saida.append({**base, "CHAVE": e, "TIPO": "email",
                          "ORIGEM_CAMPO": col, "BRUTO": parte.strip()})

CAB = ["CHAVE", "TIPO", "PESSOA", "EMPRESA_BITRIX", "CLIENTE_ID", "CLIENTE_NOME",
       "CLIENTE_CNPJ", "CLIENTE_QTD", "VIA", "ORIGEM_CAMPO", "BRUTO", "BITRIX_ID"]
saida.sort(key=lambda r: (r["TIPO"], r["CLIENTE_NOME"], r["CHAVE"]))
with DESTINO.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=CAB, delimiter=";", extrasaction="ignore")
    w.writeheader()
    w.writerows(saida)

tel = [r for r in saida if r["TIPO"] == "telefone"]
em = [r for r in saida if r["TIPO"] == "email"]
print(f"\nlinhas geradas    : {len(saida)}")
print(f"   telefones      : {len(tel)}  ({len({r['CHAVE'] for r in tel})} distintos)")
print(f"   e-mails        : {len(em)}  ({len({r['CHAVE'] for r in em})} distintos)")
print(f"   descartados    : {descartados}  (não viraram telefone/e-mail válido)")
print(f"   empresas       : {len({r['EMPRESA_BITRIX'] for r in saida})}")
print(f"   clientes        : {len({r['CLIENTE_ID'] for r in saida})}")
print(f"\ngravado: {DESTINO}  ({DESTINO.stat().st_size/1024:.0f} KB)")

# 🚨 uma chave que aponta clientes diferentes e o unico caso que a tela nao
# pode resolver sozinha -- precisa aparecer, nao ser escondido.
por_chave = {}
for r in saida:
    por_chave.setdefault((r["TIPO"], r["CHAVE"]), set()).add(r["CLIENTE_NOME"])
conflito = {k: v for k, v in por_chave.items() if len(v) > 1}
print(f"\nchaves que apontam MAIS DE UM cliente: {len(conflito)}")
for (t, k), v in list(conflito.items())[:5]:
    print(f"   {k} → {sorted(v)[:3]}")
