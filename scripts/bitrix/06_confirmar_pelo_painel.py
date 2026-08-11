"""Confirma WhatsApp pelo que o MoviZap JA SABE, antes de perguntar ao Evolution.

Tres fontes de certeza, da mais forte para a mais fraca:

  1. CONVERSA no MoviZap  -- chegou mensagem daquele numero. E prova absoluta:
     nao ha como uma mensagem chegar de um numero que nao existe no WhatsApp.
  2. tem_whatsapp = true  -- o Evolution ja respondeu `exists` alguma vez.
  3. wazzup               -- veio do integrador de WhatsApp do Bitrix.

🚨 Consultar o Evolution custa chamada e rate limit. Perguntar o que ja se
sabe e desperdicio -- e o proprio painel e a fonte mais confiavel das tres.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco  # noqa: E402

ARQ = Path("/home/claude/movizap_bitrix/BITRIX_CHAVES.csv")

with ARQ.open(encoding="utf-8-sig", newline="") as f:
    linhas = list(csv.DictReader(f, delimiter=";"))
cab = list(linhas[0].keys())
tels = [r for r in linhas if r["TIPO"] == "telefone"]

banco.abrir()
try:
    conversas = {r["t"]: r for r in banco.varios(
        """SELECT telefone_e164 t, count(*) n, max(contato_id::text) vinc,
                  max(nome_whatsapp) nome
             FROM conversa WHERE telefone_e164 IS NOT NULL
            GROUP BY telefone_e164""")}
    verificados = {r["e164"] for r in banco.varios(
        "SELECT DISTINCT e164 FROM contato_telefone WHERE tem_whatsapp IS TRUE")}
    negados = {r["e164"] for r in banco.varios(
        "SELECT DISTINCT e164 FROM contato_telefone WHERE tem_whatsapp IS FALSE")}
    no_cadastro = {r["e164"] for r in banco.varios(
        "SELECT DISTINCT e164 FROM contato_telefone")}
    orfas = {r["telefone_e164"] for r in banco.varios(
        "SELECT telefone_e164 FROM conversa WHERE contato_id IS NULL")}
finally:
    banco.fechar()

print("=" * 72)
print("O QUE O MOVIZAP JÁ SABE")
print("=" * 72)
print(f"   números com conversa no painel : {len(conversas)}")
print(f"   com tem_whatsapp = true        : {len(verificados)}")
print(f"   com tem_whatsapp = false       : {len(negados)}")
print(f"   telefones no cadastro          : {len(no_cadastro)}")

conta = Counter()
for r in tels:
    k = r["CHAVE"]
    if k in conversas:
        r["WHATSAPP"] = "conversa"
        conta["conversa no painel (prova absoluta)"] += 1
    elif k in verificados:
        r["WHATSAPP"] = "verificado"
        conta["já verificado pelo Evolution"] += 1
    elif r["WHATSAPP"] == "confirmado":
        r["WHATSAPP"] = "wazzup"
        conta["wazzup (integrador do Bitrix)"] += 1
    elif k in negados:
        r["WHATSAPP"] = "nao"
        conta["🚨 Evolution já disse que NÃO existe"] += 1
    else:
        r["WHATSAPP"] = ""
        conta["desconhecido — precisaria perguntar"] += 1

print("\n" + "=" * 72)
print("RESULTADO SOBRE OS 1.175 TELEFONES DO EXTRATO")
print("=" * 72)
for k, v in conta.most_common():
    print(f"   {v:5}  {k}")
sabidos = sum(v for k, v in conta.items() if "desconhecido" not in k)
print(f"\n   já resolvidos sem perguntar nada: {sabidos}"
      f"  ({100*sabidos/max(len(tels),1):.1f}%)")

# ── o ganho imediato: conversa órfã cujo número está no extrato ──────────
print("\n" + "=" * 72)
print("🎯 CONVERSAS ÓRFÃS QUE O EXTRATO IDENTIFICA AGORA")
print("=" * 72)
mapa = {}
for r in tels:
    mapa.setdefault(r["CHAVE"], []).append(r)
resolvidas = [n for n in orfas if n in mapa]
print(f"   conversas sem vínculo hoje     : {len(orfas)}")
print(f"   cujo número está no extrato    : {len(resolvidas)}")
for n in resolvidas:
    for r in mapa[n][:1]:
        print(f"      {n}  →  {r['CLIENTE_NOME'][:38]}"
              f"  ({r['PESSOA'][:20]}, {r['EMPRESA_BITRIX'][:22]})")

# ── números do extrato que JÁ conversaram, vinculados ou não ────────────
ja_falaram = [r for r in tels if r["CHAVE"] in conversas]
print(f"\n   números do extrato que já conversaram: {len(ja_falaram)}")

with ARQ.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cab, delimiter=";")
    w.writeheader()
    w.writerows(linhas)
print(f"\n   arquivo atualizado: {ARQ}")
