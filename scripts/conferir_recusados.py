"""Mostra QUAIS telefones a normalizacao recusou, e por que.

Existe porque "5 erros" nao e informacao: ou sao numeros podres na origem, ou
e bug meu, e a diferenca decide se o lote inteiro pode rodar.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from movizap import harmonit, telefone  # noqa: E402
from movizap.config import silenciar_clientes_http  # noqa: E402

silenciar_clientes_http()

recusados = []
vazios = 0
ok = 0
motivos = Counter()

for _pagina, lista in harmonit.paginar_clientes(limite=400):
    for cliente in lista:
        cp = cliente.get("contatoPrincipal") or {}
        for campo in ("telefone", "telefone2", "celular"):
            parte = cp.get(campo) or {}
            crua = str(parte.get("phone") or "").strip()
            if not crua:
                vazios += 1
                continue
            analise = telefone.de_partes(
                ddi=parte.get("ddi"), ddd=parte.get("ddd"), numero=parte.get("phone"))
            if analise:
                ok += 1
            else:
                motivos[analise.motivo] += 1
                if len(recusados) < 40:
                    recusados.append((cliente.get("id"), campo, parte, analise.motivo))

print(f"ok: {ok}   vazios: {vazios}   recusados: {sum(motivos.values())}")
print("\nmotivos:")
for motivo, n in motivos.most_common():
    print(f"  {n:4}  {motivo}")
print("\nrecusados (ate 40):")
for cid, campo, parte, motivo in recusados:
    print(f"  cliente {cid:>8}  {campo:9}  {parte}  -->  {motivo}")
