"""Os 44 numeros compartilhados sao UM problema ou DOIS?

  (a) MESMO cliente cadastrado varias vezes -- FAZENDA DA TOCA aparece 3x.
      O numero e dele mesmo. "O mais antigo fica" e a escolha CERTA.

  (b) Empresas DIFERENTES com o mesmo numero -- 8 empresas de energia solar
      dividindo +553837215181. E um terceiro: revendedor, instalador ou
      contador. "O mais antigo fica" e uma escolha ARBITRARIA que vai errar.

Se as duas naturezas existirem em quantidade, a mesma regra nao serve para as
duas -- e e melhor descobrir isso antes da migracao.
"""
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from movizap import harmonit, telefone  # noqa: E402
from movizap.config import silenciar_clientes_http  # noqa: E402

silenciar_clientes_http()

RUIDO = re.compile(
    r"\b(LTDA|ME|EPP|EIRELI|S/?A|SA|COMERCIO|COM|INDUSTRIA|IND|E|DE|DA|DO|DOS|"
    r"DAS|LOCACAO|LOCACOES|SOLUCOES|SERVICOS|TRANSPORTES?|MATRIZ|FILIAL)\b\.?", re.I)


def nucleo(nome: str) -> str:
    n = RUIDO.sub(" ", (nome or "").upper())
    n = re.sub(r"[^A-Z0-9 ]", " ", n)
    return " ".join(n.split())


def parecidos(a: str, b: str) -> bool:
    na, nb = nucleo(a), nucleo(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= 0.72


brutos = {}
for _p, lista in harmonit.paginar_clientes():
    for c in lista:
        brutos[str(c.get("id"))] = c

donos = {}
for k, v in brutos.items():
    cp = v.get("contatoPrincipal") or {}
    for campo in ("telefone", "telefone2", "celular"):
        parte = cp.get(campo) or {}
        if not str(parte.get("phone") or "").strip():
            continue
        a = telefone.de_partes(ddi=parte.get("ddi"), ddd=parte.get("ddd"),
                               numero=parte.get("phone"))
        if a:
            donos.setdefault(a.e164, set()).add(k)

compartilhados = {e: sorted(ks) for e, ks in donos.items() if len(ks) > 1}

mesmo_cliente, empresas_distintas, misto = [], [], []
for e164, ks in compartilhados.items():
    nomes = [brutos[k].get("nome") or "" for k in ks]
    pares = [(i, j) for i in range(len(nomes)) for j in range(i + 1, len(nomes))]
    iguais = sum(1 for i, j in pares if parecidos(nomes[i], nomes[j]))
    if iguais == len(pares):
        mesmo_cliente.append((e164, nomes))
    elif iguais == 0:
        empresas_distintas.append((e164, nomes))
    else:
        misto.append((e164, nomes))

print(f"=== dos {len(compartilhados)} numeros compartilhados ===")
print(f"  (a) MESMO cliente, cadastrado varias vezes : {len(mesmo_cliente)}")
print(f"  (b) empresas TODAS diferentes             : {len(empresas_distintas)}")
print(f"  (c) misto (grupo + terceiro junto)        : {len(misto)}")

for rotulo, grupo in (("(a) MESMO CLIENTE", mesmo_cliente),
                      ("(b) EMPRESAS DIFERENTES", empresas_distintas),
                      ("(c) MISTO", misto)):
    print(f"\n----- {rotulo} -- ate 4 exemplos -----")
    for e164, nomes in grupo[:4]:
        print(f"  {e164}  ({len(nomes)})")
        for n in nomes[:4]:
            print(f"     {n[:58]}")

telefones_a = sum(len(n) - 1 for _e, n in mesmo_cliente)
telefones_b = sum(len(n) - 1 for _e, n in empresas_distintas)
telefones_c = sum(len(n) - 1 for _e, n in misto)
print(f"\n=== vinculos que a regra descartaria, por natureza ===")
print(f"  (a) mesmo cliente      : {telefones_a}  <- descarte CORRETO")
print(f"  (b) empresas distintas : {telefones_b}  <- descarte ARBITRARIO")
print(f"  (c) misto              : {telefones_c}  <- precisa de olho humano")
