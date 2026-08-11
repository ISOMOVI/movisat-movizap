"""Pergunta ao Evolution quais numeros do extrato existem no WhatsApp.

Irmao do `verificar_whatsapp.py`, que le do cadastro -- este le do CSV, porque
os numeros do Bitrix ainda NAO estao no cadastro (e nao vao entrar sozinhos).

🚨 AS TRES LICOES DO IRMAO MAIS VELHO, TODAS VALEM AQUI:

  1. NUMERO REPETIDO NO MESMO LOTE derruba o lote inteiro com HTTP 400
     `numbers contains duplicate item` -- e o sintoma engana, parece limite de
     chamadas. Agrupa por numero distinto antes de perguntar.
  2. FALHA DE REDE NAO VIRA 'nao'. Fica desconhecido para a proxima rodada.
     Gravar 'nao' por timeout silenciaria o cliente para sempre.
  3. RITMO, NAO RAJADA. 20 por chamada, 2s entre lotes -- o mesmo ritmo que ja
     rodou sobre 1.152 telefones sem derrubar o chip.

Grava a cada lote: se cair no meio, o que ja foi perguntado esta salvo.

Uso:
    verificar_extrato.py                      # simulacao
    verificar_extrato.py --limite 40 --aplicar
    verificar_extrato.py --aplicar
"""
import argparse
import csv
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import evolution  # noqa: E402

ARQ = Path("/home/claude/movizap_bitrix/BITRIX_CHAVES.csv")
INSTANCIA = "atendimento"
LOTE = 20
INTERVALO = 2.0


def carregar():
    with ARQ.open(encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    return linhas, list(linhas[0].keys())


def gravar(linhas, cab):
    tmp = ARQ.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cab, delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    tmp.replace(ARQ)          # troca atômica: nunca deixa o CSV pela metade


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--aplicar", action="store_true")
    p.add_argument("--limite", type=int, default=None)
    p.add_argument("--lote", type=int, default=LOTE)
    p.add_argument("--intervalo", type=float, default=INTERVALO)
    args = p.parse_args()

    linhas, cab = carregar()
    if "VERIFICADO_EM" not in cab:
        cab = cab + ["VERIFICADO_EM"]
        for r in linhas:
            r["VERIFICADO_EM"] = ""

    tels = [r for r in linhas if r["TIPO"] == "telefone"]
    pend = [r for r in tels if not r["WHATSAPP"]]

    # 🚨 agrupa por número: o mesmo número pode estar em várias linhas
    por_num = {}
    for r in pend:
        por_num.setdefault(r["CHAVE"], []).append(r)
    distintos = sorted(por_num)
    if args.limite:
        distintos = distintos[:args.limite]

    print(f"telefones no extrato   : {len(tels)}")
    print(f"já com status          : {len(tels) - len(pend)}")
    print(f"sem status             : {len(pend)} linhas → {len(por_num)} números distintos")
    print(f"nesta rodada           : {len(distintos)}")
    print(f"ritmo                  : {args.lote} por chamada, {args.intervalo}s "
          f"entre lotes → ~{len(distintos)/args.lote*args.intervalo/60:.1f} min\n")

    if not args.aplicar:
        print("(simulação — nada foi consultado nem gravado. Use --aplicar.)")
        return 0

    sim = nao = mudo = falha = 0
    agora = time.strftime("%Y-%m-%d %H:%M")
    for i in range(0, len(distintos), args.lote):
        pedaco = distintos[i:i + args.lote]
        numeros = [n.lstrip("+") for n in pedaco]
        try:
            resp = evolution._pedir(
                "POST", f"/chat/whatsappNumbers/{INSTANCIA}", {"numbers": numeros})
        except Exception as e:                       # noqa: BLE001
            # ⚠️ NÃO vira 'nao'. Fica em branco para a próxima rodada.
            falha += len(pedaco)
            print(f"  lote {i//args.lote+1}: FALHOU — {e}")
            time.sleep(args.intervalo)
            continue

        achados = {str(r.get("number") or "").lstrip("+"): r for r in (resp or [])}
        for num in pedaco:
            a = achados.get(num.lstrip("+"))
            if a is None:
                mudo += 1          # o Evolution não falou deste: não se inventa
                continue
            existe = bool(a.get("exists"))
            sim += int(existe)
            nao += int(not existe)
            for r in por_num[num]:
                r["WHATSAPP"] = "sim" if existe else "nao"
                r["VERIFICADO_EM"] = agora

        gravar(linhas, cab)        # salva a cada lote
        print(f"  lote {i//args.lote+1:3}/{(len(distintos)-1)//args.lote+1}: "
              f"{len(pedaco):2} números · acumulado {sim} com, {nao} sem")
        time.sleep(args.intervalo)

    print(f"\nRESULTADO DESTA RODADA")
    print(f"   existem no WhatsApp : {sim}")
    print(f"   não existem         : {nao}")
    print(f"   Evolution não falou : {mudo}")
    print(f"   falha de consulta   : {falha}  (continuam sem status)")

    # 🚨 a prova é reler o arquivo, não confiar no contador do laço
    linhas2, _ = carregar()
    c = Counter(r["WHATSAPP"] or "(sem status)"
                for r in linhas2 if r["TIPO"] == "telefone")
    print("\nRELENDO O ARQUIVO:")
    for k, v in c.most_common():
        print(f"   {v:5}  {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
