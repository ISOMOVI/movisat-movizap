"""Trata as chaves do extrato. Regenera o CSV -- o original se refaz do zero.

Seis tratamentos, do que muda resultado ao que so rotula:

  1. '+DDNNNNNNNNN' sem o 55 -> +55DD...   (8 numeros lidos como EUA/Russia)
  2. 'NNN@whatsapp.wazzup' -> telefone     (28 numeros com WhatsApp PROVADO)
  3. marca fixo x movel                     (fixo nao recebe WhatsApp)
  4. marca o nono digito que NOS chutamos   (20 -- e palpite, nao dado)
  5. marca e-mail gratuito                  (273 -- nao prova vinculo com empresa)
  6. tira automatico e dominio com erro     (noreply, gmial.com)
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import telefone  # noqa: E402

ARQ = Path("/home/claude/movizap_bitrix/BITRIX_CHAVES.csv")
DDD = {11,12,13,14,15,16,17,18,19,21,22,24,27,28,31,32,33,34,35,37,38,41,42,43,
       44,45,46,47,48,49,51,53,54,55,61,62,63,64,65,66,67,68,69,71,73,74,75,77,
       79,81,82,83,84,85,86,87,88,89,91,92,93,94,95,96,97,98,99}
GRATUITO = {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com.br", "yahoo.com",
            "bol.com.br", "uol.com.br", "terra.com.br", "live.com", "icloud.com",
            "msn.com", "aol.com", "ig.com.br", "globo.com", "r7.com",
            "hotmail.com.br", "outlook.com.br", "yahoo.com.mx", "gmail.com.br"}
GENERICO = ("noreply", "no-reply", "nao-responda", "naoresponda", "postmaster",
            "mailer-daemon")
TYPO = ("gmial.com", "gmail.con", "gmai.com", "hotmai.com", "hotmail.con",
        "outlook.con", "yahoo.con")

with ARQ.open(encoding="utf-8-sig", newline="") as f:
    linhas = list(csv.DictReader(f, delimiter=";"))
antes = len(linhas)
conta = Counter()
saida = []

for r in linhas:
    r = dict(r)
    r.setdefault("SUBTIPO", "")
    r.setdefault("INFERIDO", "")
    r.setdefault("WHATSAPP", "")

    # ── 2. wazzup: o "e-mail" é o número ──────────────────────────────────
    if r["TIPO"] == "email" and r["CHAVE"].endswith("@whatsapp.wazzup"):
        num = r["CHAVE"].split("@")[0]
        a = telefone.analisar("+" + num if not num.startswith("+") else num)
        if a:
            r["TIPO"] = "telefone"
            r["CHAVE"] = a.e164
            r["ORIGEM_CAMPO"] = "wazzup"
            r["SUBTIPO"] = a.tipo
            r["WHATSAPP"] = "confirmado"   # veio do integrador de WhatsApp
            conta["wazzup → telefone"] += 1
        else:
            conta["wazzup ilegível (descartado)"] += 1
            continue

    if r["TIPO"] == "telefone":
        d = re.sub(r"\D", "", r["CHAVE"])
        # ── 1. faltou o 55 ────────────────────────────────────────────────
        if not d.startswith("55") and len(d) in (10, 11) and int(d[:2]) in DDD:
            a = telefone.analisar("+55" + d)
            if a:
                r["CHAVE"] = a.e164
                conta["+55 restaurado"] += 1
        # ── 3 e 4. subtipo e nono dígito ─────────────────────────────────
        a = telefone.analisar(r["BRUTO"])
        if a and not r["SUBTIPO"]:
            r["SUBTIPO"] = a.tipo
            if getattr(a, "nono_digito_acrescentado", False):
                r["INFERIDO"] = "nono_digito"
                conta["nono dígito inferido (marcado)"] += 1
        if r["SUBTIPO"] == "fixo":
            conta["fixo (marcado)"] += 1

    elif r["TIPO"] == "email":
        dom = r["CHAVE"].rsplit("@", 1)[-1]
        # ── 6. fora ───────────────────────────────────────────────────────
        if any(g in r["CHAVE"] for g in GENERICO):
            conta["automático (removido)"] += 1
            continue
        if dom in TYPO:
            conta["domínio com erro (removido)"] += 1
            continue
        # ── 5. força ─────────────────────────────────────────────────────
        r["SUBTIPO"] = "gratuito" if dom in GRATUITO else "corporativo"
        conta[f"e-mail {r['SUBTIPO']}"] += 1

    saida.append(r)

# dedup: o wazzup pode ter virado um número que já estava lá
vistos, final = set(), []
for r in saida:
    k = (r["TIPO"], r["CHAVE"], r["CLIENTE_ID"])
    if k in vistos:
        conta["duplicata após tratamento"] += 1
        # 🚨 nao descarta a marca de WhatsApp confirmado ao remover a copia
        for a in final:
            if (a["TIPO"], a["CHAVE"], a["CLIENTE_ID"]) == k and r["WHATSAPP"]:
                a["WHATSAPP"] = r["WHATSAPP"]
                a["ORIGEM_CAMPO"] = a["ORIGEM_CAMPO"] + "+wazzup"
        continue
    vistos.add(k)
    final.append(r)

CAB = ["CHAVE", "TIPO", "SUBTIPO", "WHATSAPP", "INFERIDO", "PESSOA",
       "EMPRESA_BITRIX", "CLIENTE_ID", "CLIENTE_NOME", "CLIENTE_CNPJ",
       "CLIENTE_QTD", "VIA", "ORIGEM_CAMPO", "BRUTO", "BITRIX_ID"]
final.sort(key=lambda r: (r["TIPO"], r["CLIENTE_NOME"], r["CHAVE"]))
with ARQ.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=CAB, delimiter=";", extrasaction="ignore")
    w.writeheader()
    w.writerows(final)

print("TRATAMENTOS APLICADOS")
for k, v in conta.most_common():
    print(f"   {v:5}  {k}")

t = Counter(r["TIPO"] for r in final)
s = Counter(r["SUBTIPO"] for r in final)
print(f"\nlinhas: {antes} → {len(final)}")
print(f"   telefones : {t['telefone']}  "
      f"(móvel {s['movel']} · fixo {s['fixo']} · internacional {s['internacional']})")
print(f"   e-mails   : {t['email']}  "
      f"(corporativo {s['corporativo']} · gratuito {s['gratuito']})")
print(f"   com WhatsApp CONFIRMADO : "
      f"{sum(1 for r in final if r['WHATSAPP'])}")
print(f"   com nono dígito inferido: "
      f"{sum(1 for r in final if r['INFERIDO'])}")
print(f"   clientes  : {len({r['CLIENTE_ID'] for r in final})}")
print(f"   empresas  : {len({r['EMPRESA_BITRIX'] for r in final})}")

restam = [r for r in final if r["TIPO"] == "telefone"
          and not re.sub(r"\D", "", r["CHAVE"]).startswith("55")]
print(f"\n   telefones ainda fora do padrão +55: {len(restam)}")
for r in restam[:5]:
    print(f"      {r['CHAVE']}  {r['CLIENTE_NOME'][:30]}")
