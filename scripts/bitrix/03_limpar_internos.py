"""Tira do extrato as chaves que sao NOSSAS, nao do cliente.

🚨 `supervisao@movisat.com.br` aponta 3 clientes. Um e-mail nosso nao
identifica cliente nenhum -- identifica a Movisat. Deixa-lo na lista faria a
tela sugerir cliente errado para uma mensagem do proprio time.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

ARQ = Path("/home/claude/movizap_bitrix/BITRIX_CHAVES.csv")
NOSSOS_DOM = ("movisat.com.br", "movisat.com")

with ARQ.open(encoding="utf-8-sig", newline="") as f:
    linhas = list(csv.DictReader(f, delimiter=";"))
cab = list(linhas[0].keys())

nossos = [r for r in linhas
          if r["TIPO"] == "email" and any(r["CHAVE"].endswith("@" + d)
                                          for d in NOSSOS_DOM)]
print(f"e-mails do nosso domínio no extrato: {len(nossos)}")
for r in sorted({r["CHAVE"] for r in nossos}):
    quantos = sum(1 for x in nossos if x["CHAVE"] == r)
    print(f"   {r:44} → {quantos} cliente(s)")

# telefones que pertencem à própria Movisat como cliente
movisat = [r for r in linhas if "MOVISAT" in r["CLIENTE_NOME"].upper()]
print(f"\nlinhas cujo CLIENTE é a própria Movisat: {len(movisat)}")
for r in movisat[:8]:
    print(f"   {r['CHAVE']:34} {r['PESSOA'][:24]:24} {r['CLIENTE_NOME'][:30]}")

limpo = [r for r in linhas if r not in nossos and r not in movisat]
print(f"\nlinhas: {len(linhas)} → {len(limpo)}  (saíram {len(linhas)-len(limpo)})")

with ARQ.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cab, delimiter=";")
    w.writeheader()
    w.writerows(limpo)

por_chave = {}
for r in limpo:
    por_chave.setdefault((r["TIPO"], r["CHAVE"]), set()).add(r["CLIENTE_NOME"])
conflito = {k: v for k, v in por_chave.items() if len(v) > 1}
tipos = Counter(r["TIPO"] for r in limpo)
print(f"\nFINAL")
print(f"   telefones : {tipos['telefone']}")
print(f"   e-mails   : {tipos['email']}")
print(f"   empresas  : {len({r['EMPRESA_BITRIX'] for r in limpo})}")
print(f"   clientes  : {len({r['CLIENTE_ID'] for r in limpo})}")
print(f"   chaves com mais de 1 cliente: {len(conflito)}")
for (t, k), v in list(conflito.items())[:6]:
    print(f"      {k} → {sorted(v)[:3]}")
