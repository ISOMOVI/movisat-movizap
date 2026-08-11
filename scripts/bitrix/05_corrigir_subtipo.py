"""SUBTIPO tem que descrever a CHAVE, nao o bruto de onde ela veio.

Os 8 numeros restaurados para +55 continuaram rotulados 'internacional' -- o
rotulo vinha do bruto, que era `+19981227491`. Rotulo que contradiz o dado ao
lado dele e pior que rotulo nenhum: alguem filtra por 'internacional' e perde
oito clientes brasileiros.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import telefone  # noqa: E402

ARQ = Path("/home/claude/movizap_bitrix/BITRIX_CHAVES.csv")
with ARQ.open(encoding="utf-8-sig", newline="") as f:
    linhas = list(csv.DictReader(f, delimiter=";"))
cab = list(linhas[0].keys())

mudou = 0
for r in linhas:
    if r["TIPO"] != "telefone":
        continue
    a = telefone.analisar(r["CHAVE"])
    novo = a.tipo if a else r["SUBTIPO"]
    if novo != r["SUBTIPO"]:
        mudou += 1
    r["SUBTIPO"] = novo

with ARQ.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cab, delimiter=";")
    w.writeheader()
    w.writerows(linhas)

s = Counter(r["SUBTIPO"] for r in linhas if r["TIPO"] == "telefone")
print(f"subtipos corrigidos: {mudou}")
print("telefones por subtipo:")
for k, v in s.most_common():
    print(f"   {v:5}  {k}")
e = Counter(r["SUBTIPO"] for r in linhas if r["TIPO"] == "email")
print("e-mails por subtipo:")
for k, v in e.most_common():
    print(f"   {v:5}  {k}")
