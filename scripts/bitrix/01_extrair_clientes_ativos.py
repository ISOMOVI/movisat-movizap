"""Extrai do arquivo do Bitrix SO os contatos de empresas que sao cliente ATIVO.

O arquivo original (35 MB, 242 colunas, 14.222 linhas) passa a nao ser mais
usado: este extrato o substitui para todo o trabalho seguinte.

O que ele leva:
  · TODAS as colunas do original que tenham ao menos um valor no subconjunto
    (as 100% vazias saem -- coluna sem nenhum dado nao e dado);
  · 5 colunas novas no inicio, com o resultado do cruzamento.

Saida: CSV UTF-8 com BOM e separador ';' -- abre direto no Excel em pt-BR.
"""
import csv
import html
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco  # noqa: E402

ORIGEM = Path("/home/claude/movizap_bitrix/contatos_1786390654427556319.xls")
DESTINO = Path("/home/claude/movizap_bitrix/BITRIX_CLIENTES_ATIVOS.csv")

_TAG = re.compile(r"<[^>]*>")
_CELULA = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_LINHA = re.compile(r"<tr[^>]*>")
MARCAS = re.compile(r"\[N[ÃA]O\s*USAR\]|\(INATIVADO\)|\(MATRIZ\)|\(FILIAL\)", re.I)
RUIDO = re.compile(
    r"\b(LTDA|ME|EPP|EIRELI|S/?A|SA|COMERCIO|COM|INDUSTRIA|IND|E|DE|DA|DO|DOS|"
    r"DAS|LOCACAO|LOCACOES|SOLUCOES|SERVICOS|TRANSPORTES?|MATRIZ|FILIAL|"
    r"GRUPO|CIA|EMPRESA|PF|PJ)\b\.?", re.I)


def celulas(linha):
    return [html.unescape(_TAG.sub("", c)).strip() for c in _CELULA.findall(linha)]


def nucleo(nome):
    s = "".join(c for c in unicodedata.normalize("NFD", nome or "")
                if unicodedata.category(c) != "Mn")
    s = RUIDO.sub(" ", MARCAS.sub(" ", s.upper()))
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", s).split())


banco.abrir()
try:
    clientes = {r["id"]: r for r in banco.varios(
        "SELECT id, nome, nome_fantasia, documento FROM cliente WHERE ativo")}
    por_nucleo = defaultdict(set)
    for c in clientes.values():
        for campo in (c["nome"], c["nome_fantasia"]):
            n = nucleo(campo)
            if n:
                por_nucleo[n].add(c["id"])

    contatos = banco.varios(
        "SELECT id, id_externo, empresa_nome, empresa_id_externo FROM bitrix_contato")

    via_nome = {}
    for b in contatos:
        alvo = por_nucleo.get(nucleo(b["empresa_nome"]))
        if alvo:
            via_nome[b["id_externo"]] = alvo

    grupo = defaultdict(set)
    for b in contatos:
        if b["empresa_id_externo"]:
            grupo[b["empresa_id_externo"]].add(b["id_externo"])
    grupo_alvo = {}
    for gid, membros in grupo.items():
        alvos = set()
        for m in membros:
            alvos |= via_nome.get(m, set())
        if alvos:
            grupo_alvo[gid] = alvos

    alvo_de, via_de = dict(via_nome), {k: "nome" for k in via_nome}
    for b in contatos:
        g = b["empresa_id_externo"]
        if g and g in grupo_alvo and b["id_externo"] not in alvo_de:
            alvo_de[b["id_externo"]] = grupo_alvo[g]
            via_de[b["id_externo"]] = "grupo"
finally:
    banco.fechar()

print(f"contatos a extrair: {len(alvo_de)}")

bruto = ORIGEM.read_text(encoding="utf-8", errors="replace")
partes = _LINHA.split(bruto)[1:]
cab = celulas(partes[0])
i_id = cab.index("ID")

linhas = []
for p in partes[1:]:
    c = celulas(p)
    if len(c) < len(cab) // 2 or i_id >= len(c):
        continue
    if c[i_id].strip() in alvo_de:
        linhas.append(c)

print(f"linhas encontradas no arquivo: {len(linhas)}")

# colunas que têm ao menos um valor NESTE subconjunto
uteis = [i for i in range(len(cab))
         if any(i < len(L) and L[i].strip() for L in linhas)]
print(f"colunas: {len(cab)} no original → {len(uteis)} com dado neste extrato")

NOVAS = ["CLIENTE_ID", "CLIENTE_NOME", "CLIENTE_CNPJ", "CLIENTE_QTD", "VIA"]
with DESTINO.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    w.writerow(NOVAS + [cab[i] for i in uteis])
    for L in linhas:
        ids = sorted(alvo_de[L[i_id].strip()])
        w.writerow([
            " | ".join(str(i) for i in ids),
            " | ".join(clientes[i]["nome"] for i in ids),
            " | ".join(clientes[i]["documento"] or "" for i in ids),
            len(ids),
            via_de[L[i_id].strip()],
        ] + [L[i] if i < len(L) else "" for i in uteis])

print(f"\ngravado: {DESTINO}")
print(f"tamanho: {DESTINO.stat().st_size/1024/1024:.1f} MB")

# ── o que foi parar dentro ────────────────────────────────────────────────
def col(nome):
    return cab.index(nome) if nome in cab else None


for nome in ("Banco", "Agência", "Conta", "PIX", "RG", "CPF", "CNPJ"):
    i = col(nome)
    if i is not None and i in uteis:
        q = sum(1 for L in linhas if i < len(L) and L[i].strip())
        if q:
            print(f"   ⚠️ coluna '{nome}' vem com {q} valores")
