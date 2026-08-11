"""Consolida os contatos no cliente MATRIZ. O nome que vale e o do Harmonit.

Regra do usuario (11/08): quando varios clientes do Harmonit sao o mesmo grupo,
TODOS os contatos vao para a matriz -- e nunca para um marcado [NAO USAR].

Tres criterios de agrupamento, do mais seguro ao mais frouxo:

  A. mesma RAIZ de CNPJ (8 primeiros digitos)  -- matriz e filial pela Receita
  B. mesmo NUCLEO de nome                      -- duplicata do cadastro
  C. um lado marcado [NAO USAR] + duas primeiras palavras iguais

🚨 O criterio C so se aplica a quem esta marcado [NAO USAR]. E o caso MOTO
HELP: 'MOTO HELP ENTREGAS RAPIDAS' e 'MOTO HELP SP LOGISTICA' tem CNPJ de
raizes diferentes e nucleos diferentes -- nenhum criterio automatico os une.
Restringir ao [NAO USAR] mantem o risco baixo: o cliente marcado assim nao
pode receber contato de qualquer jeito, entao redirecionar so pode melhorar.

🚨 DOCUMENTO INVALIDO NAO AGRUPA. `00000000000000` aparece em mais de um
cliente e uniria AGILIS GROUP com CEASA CAMPINAS -- duas empresas sem relacao.
Documento de digito unico nao e documento, e ausencia com cara de dado.
"""
import csv
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco  # noqa: E402

ARQ = Path("/home/claude/movizap_bitrix/BITRIX_CHAVES.csv")
NAO_USAR = re.compile(r"\[N[ÃA]O\s*USAR\]|\(INATIVADO\)|N[ÃA]O\s*USAR", re.I)
RUIDO = re.compile(
    r"\b(LTDA|ME|EPP|EIRELI|S/?A|SA|COMERCIO|COM|INDUSTRIA|IND|E|DE|DA|DO|DOS|"
    r"DAS|LOCACAO|LOCACOES|SOLUCOES|SERVICOS|TRANSPORTES?|MATRIZ|FILIAL|"
    r"GRUPO|CIA|EMPRESA|PF|PJ)\b\.?", re.I)


def nucleo(nome):
    s = "".join(c for c in unicodedata.normalize("NFD", nome or "")
                if unicodedata.category(c) != "Mn")
    s = RUIDO.sub(" ", NAO_USAR.sub(" ", s.upper()))
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", s).split())


def doc_agrupavel(d):
    """Documento que serve para dizer 'e a mesma empresa'."""
    return bool(d) and len(d) == 14 and len(set(d)) > 1


def e_matriz(d):
    return doc_agrupavel(d) and d[8:12] == "0001"


banco.abrir()
try:
    clientes = {r["id"]: r for r in banco.varios(
        "SELECT id, nome, documento FROM cliente WHERE ativo")}
finally:
    banco.fechar()

pai = {i: i for i in clientes}


def achar(x):
    while pai[x] != x:
        pai[x] = pai[pai[x]]
        x = pai[x]
    return x


def unir(a, b):
    ra, rb = achar(a), achar(b)
    if ra != rb:
        pai[max(ra, rb)] = min(ra, rb)


# ── A: raiz de CNPJ ──────────────────────────────────────────────────────
por_raiz = defaultdict(list)
for i, c in clientes.items():
    if doc_agrupavel(c["documento"]):
        por_raiz[c["documento"][:8]].append(i)
# ── B: núcleo de nome ────────────────────────────────────────────────────
por_nucleo = defaultdict(list)
for i, c in clientes.items():
    n = nucleo(c["nome"])
    if n:
        por_nucleo[n].append(i)

for conj in list(por_raiz.values()) + list(por_nucleo.values()):
    for outro in conj[1:]:
        unir(conj[0], outro)

# ── C: [NÃO USAR] + duas primeiras palavras ──────────────────────────────
def prefixo(i, n=2):
    p = nucleo(clientes[i]["nome"]).split()
    return " ".join(p[:n]) if len(p) >= n else None


por_prefixo = defaultdict(list)
for i in clientes:
    p = prefixo(i)
    if p:
        por_prefixo[p].append(i)

criterio_c = []
for i, c in clientes.items():
    if not NAO_USAR.search(c["nome"] or ""):
        continue
    p = prefixo(i)
    if not p:
        continue
    cands = [j for j in por_prefixo[p]
             if j != i and not NAO_USAR.search(clientes[j]["nome"] or "")
             and achar(j) != achar(i)]
    if len(cands) == 1:
        unir(cands[0], i)
        criterio_c.append((i, cands[0]))
    elif len(cands) > 1:
        criterio_c.append((i, cands))

grupos = defaultdict(set)
for i in clientes:
    grupos[achar(i)].add(i)


def escolher(ids):
    cands = [i for i in ids if not NAO_USAR.search(clientes[i]["nome"] or "")]
    if not cands:
        cands = list(ids)
    matrizes = [i for i in cands if e_matriz(clientes[i]["documento"])]
    return min(matrizes) if matrizes else min(cands)


destino = {}
for _, ids in grupos.items():
    alvo = escolher(ids)
    for i in ids:
        destino[i] = alvo

# ── aplica ───────────────────────────────────────────────────────────────
with ARQ.open(encoding="utf-8-sig", newline="") as f:
    linhas = list(csv.DictReader(f, delimiter=";"))
cab = list(linhas[0].keys())

mudou = {}
for r in linhas:
    ids = [int(x) for x in r["CLIENTE_ID"].split(" | ") if x.strip().isdigit()]
    novos = sorted({destino.get(i, i) for i in ids})
    for i in ids:
        if destino.get(i, i) != i:
            mudou[i] = destino[i]
    r["CLIENTE_ID"] = " | ".join(str(i) for i in novos)
    r["CLIENTE_NOME"] = " | ".join(clientes[i]["nome"] for i in novos)
    r["CLIENTE_CNPJ"] = " | ".join(clientes[i]["documento"] or "" for i in novos)
    r["CLIENTE_QTD"] = str(len(novos))

vistos, final = set(), []
for r in linhas:
    k = (r["TIPO"], r["CHAVE"], r["CLIENTE_ID"])
    if k not in vistos:
        vistos.add(k)
        final.append(r)

print("=" * 76)
print("CONSOLIDAÇÕES")
print("=" * 76)
for de, para in sorted(mudou.items()):
    marca = "  🚨 era [NÃO USAR]" if NAO_USAR.search(clientes[de]["nome"] or "") else ""
    print(f"   {de:5} {clientes[de]['nome'][:40]:<40} {clientes[de]['documento'] or '—':<15}")
    print(f"      → {para:5} {clientes[para]['nome'][:40]:<40} "
          f"{clientes[para]['documento'] or '—'}{marca}")

print("\n" + "=" * 76)
print("CRITÉRIO C — [NÃO USAR] redirecionado por prefixo de nome")
print("=" * 76)
for i, alvo in criterio_c:
    if isinstance(alvo, list):
        print(f"   ⚠️ {clientes[i]['nome'][:44]} → {len(alvo)} candidatos, NÃO uni:")
        for j in alvo:
            print(f"        {j} {clientes[j]['nome'][:44]}")
    else:
        print(f"   ✅ {clientes[i]['nome'][:42]}")
        print(f"        → {clientes[alvo]['nome'][:42]} ({clientes[alvo]['documento']})")

nao_usar_restante = [r for r in final if NAO_USAR.search(r["CLIENTE_NOME"])]
print("\n" + "=" * 76)
print("RESULTADO")
print("=" * 76)
print(f"   linhas                 : {len(linhas)} → {len(final)}")
print(f"   clientes redirecionados: {len(mudou)}")
print(f"   clientes citados       : {len({r['CLIENTE_ID'] for r in final})}")
print(f"   🚨 ainda apontam [NÃO USAR]: {len(nao_usar_restante)}")
for r in nao_usar_restante[:5]:
    print(f"      {r['CHAVE']}  {r['CLIENTE_NOME'][:46]}")

with ARQ.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cab, delimiter=";")
    w.writeheader()
    w.writerows(final)
print(f"\n   arquivo: {ARQ}")
