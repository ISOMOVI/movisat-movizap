"""Auditoria ANTES da migracao 006.

Mede o que a regra nova precisa saber, em vez de supor:

  1. `dataCadastro` vem confiavel? Sem ele nao existe "o mais antigo".
  2. A ordem por dataCadastro e a MESMA que por harmonit_id? Se for, o
     desempate nao importa e a coluna nova e desnecessaria.
  3. Quantos clientes tem [NAO USAR] / (INATIVADO) no nome?
  4. A regra "so o mais antigo fica com o numero" resolve os 44 casos?
  5. Quantos telefones deixariam de ser cadastrados?
"""
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from movizap import banco, harmonit  # noqa: E402
from movizap.config import silenciar_clientes_http  # noqa: E402
from movizap import telefone  # noqa: E402

silenciar_clientes_http()
banco.abrir()

MARCAS = re.compile(r"\[N[ÃA]O\s*USAR\]|\(INATIVADO\)|N[ÃA]O\s*USAR", re.I)

print("Lendo a base inteira do Harmonit...")
brutos = {}
for _p, lista in harmonit.paginar_clientes():
    for c in lista:
        brutos[str(c.get("id"))] = c
print(f"  {len(brutos)} clientes\n")

# ---------------------------------------------------------------- 1) dataCadastro
print("=== 1) dataCadastro vem confiavel? ===")
sem_campo = [k for k, v in brutos.items() if not v.get("dataCadastro")]
sentinela = [k for k, v in brutos.items()
             if str(v.get("dataCadastro") or "").startswith("0001-01-01")]
print(f"  campo ausente/vazio: {len(sem_campo)} de {len(brutos)}")
print(f"  🚨 sentinela 0001-01-01 (o vazio do .NET): {len(sentinela)}")
print(f"  --> SEM data utilizavel: {len(sem_campo) + len(sentinela)}"
      f" ({100*(len(sem_campo)+len(sentinela))/len(brutos):.1f}%)")


def data_de(c):
    """🚨 `0001-01-01T00:00:00` NAO e uma data: e o vazio do .NET.

    Ele parseia sem erro e vira o ano 1, o que faria o registro sem data
    ganhar TODA disputa de "quem e o mais antigo". O sentinela precisa virar
    None aqui, senao a regra inteira fica invertida.
    """
    d = c.get("dataCadastro")
    if not d:
        return None
    try:
        dt = datetime.fromisoformat(str(d).replace("Z", "+00:00"))
    except ValueError:
        return None
    return None if dt.year < 1900 else dt


datas_ok = sum(1 for v in brutos.values() if data_de(v))
print(f"  parseaveis: {datas_ok} de {len(brutos)}")
if datas_ok:
    validas = [data_de(v) for v in brutos.values() if data_de(v)]
    print(f"  da mais antiga {min(validas):%d/%m/%Y} ate {max(validas):%d/%m/%Y}")

# ------------------------------------------- 2) dataCadastro x harmonit_id
print("\n=== 2) ordenar por data da o MESMO que ordenar por id? ===")
print("    Se der o mesmo, a coluna nova nao muda nenhuma decisao.")
com_ambos = [(k, data_de(v)) for k, v in brutos.items() if data_de(v)]
por_data = [k for k, _ in sorted(com_ambos, key=lambda x: (x[1], int(x[0])))]
por_id = [k for k, _ in sorted(com_ambos, key=lambda x: int(x[0]))]
if por_data == por_id:
    print("  IGUAIS -- o harmonit_id ja serve de criterio de antiguidade")
else:
    divergencias = sum(1 for a, b in zip(por_data, por_id) if a != b)
    print(f"  DIFERENTES em {divergencias} posicoes de {len(por_data)}")
    print("  --> a coluna cadastrado_em MUDA decisao. Vale a migracao.")

# ------------------------------------------------------------- 3) marcados
print("\n=== 3) clientes marcados para nao usar ===")
marcados = {k: v for k, v in brutos.items() if MARCAS.search(v.get("nome") or "")}
print(f"  {len(marcados)} clientes com marca no nome")
print(f"  ativos entre eles: {sum(1 for v in marcados.values() if v.get('ativo'))}")
for v in list(marcados.values())[:6]:
    print(f"    {'ativo ' if v.get('ativo') else 'inativo'} {v.get('nome')[:64]}")

# tem telefone? e o telefone deles colide com o de alguem bom?
com_tel = 0
for v in marcados.values():
    cp = v.get("contatoPrincipal") or {}
    if any(str((cp.get(c) or {}).get("phone") or "").strip()
           for c in ("telefone", "telefone2", "celular")):
        com_tel += 1
print(f"  com algum telefone: {com_tel}")

# ------------------------------------------------- 4) e 5) numeros repetidos
print("\n=== 4) a regra 'so o mais antigo' resolve os compartilhados? ===")
donos = defaultdict(list)   # e164 -> [harmonit_id]
for k, v in brutos.items():
    cp = v.get("contatoPrincipal") or {}
    vistos = set()
    for campo in ("telefone", "telefone2", "celular"):
        parte = cp.get(campo) or {}
        if not str(parte.get("phone") or "").strip():
            continue
        a = telefone.de_partes(ddi=parte.get("ddi"), ddd=parte.get("ddd"),
                               numero=parte.get("phone"))
        if a and a.e164 not in vistos:
            vistos.add(a.e164)
            donos[a.e164].append(k)

compartilhados = {e: ks for e, ks in donos.items() if len(ks) > 1}
print(f"  numeros em mais de um cliente: {len(compartilhados)}")
print(f"  clientes envolvidos: {len({k for ks in compartilhados.values() for k in ks})}")

tamanhos = Counter(len(ks) for ks in compartilhados.values())
print(f"  distribuicao (quantos clientes por numero): {dict(sorted(tamanhos.items()))}")

# quantos telefones deixariam de entrar
perdidos = sum(len(ks) - 1 for ks in compartilhados.values())
print(f"\n=== 5) telefones que NAO seriam cadastrados: {perdidos} ===")
print(f"    (de {sum(len(ks) for ks in donos.values())} vinculos telefone-cliente)")

# quantos desses seriam resolvidos so por descartar os marcados
resolvidos_por_marca = 0
ainda_ambiguos = []
for e164, ks in compartilhados.items():
    bons = [k for k in ks if not MARCAS.search(brutos[k].get("nome") or "")]
    if len(bons) <= 1:
        resolvidos_por_marca += 1
    else:
        ainda_ambiguos.append((e164, bons))
print(f"\n  resolvidos so por descartar os [NAO USAR]: {resolvidos_por_marca}")
print(f"  ainda com 2+ clientes bons disputando: {len(ainda_ambiguos)}")

print("\n  os 6 piores casos que sobram:")
for e164, bons in sorted(ainda_ambiguos, key=lambda x: -len(x[1]))[:6]:
    print(f"    {e164} -- {len(bons)} clientes:")
    ordenados = sorted(bons, key=lambda k: (data_de(brutos[k]) or datetime.max, int(k)))
    for k in ordenados[:4]:
        d = data_de(brutos[k])
        quando = f"{d:%d/%m/%Y}" if d else "sem data "
        marca = " <== FICA COM O NUMERO" if k == ordenados[0] else ""
        print(f"       {k:>8} {quando} {brutos[k].get('nome')[:44]}{marca}")

banco.fechar()
