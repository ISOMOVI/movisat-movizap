# -*- coding: utf-8 -*-
"""A fila das passagens: insiste na escrita que o Harmonit ainda não enxergou.

🔵 Decisão dele, 18/11: *"assim op não para de trabalhar e seguimos no
background com a OS"*. O card anda na hora com selo, e esta fila é o
"background".

🚨 O QUE ELA EXISTE PARA RESOLVER, medido na OS 17133. A mesma rota do Harmonit
devolveu 251 às 11:42:47 e 16488 às 11:43:18, sem escrita entre as duas: das
11:17 às 11:42 ela respondia o valor que escrevemos às 09:42. Sete recusas,
todas falsas. Agora o card anda e esta fila insiste até o ERP se acertar.

⚠️ UMA TENTATIVA POR OS, POR PASSADA. Insistir em laço dentro da mesma execução
é o *"só cansa a req"* dele. Quem dá o ritmo é o cron.

Dois caminhos:
  · **sem argumento** — mostra a fila. Nada é escrito.
  · **`--de-verdade`** — escoa a fila e, com `--avisar-whatsapp`, manda a red
    flag das pendências com mais de 🔵 **1 hora** (número dele).

🚨 EM SILÊNCIO QUANDO A FILA ESTÁ VAZIA.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging  # noqa: E402
logging.disable(logging.CRITICAL)

from movizap import banco, passagem  # noqa: E402
from movizap.config import settings  # noqa: E402

DE_VERDADE = "--de-verdade" in sys.argv
AVISAR = "--avisar-whatsapp" in sys.argv

try:
    banco.abrir()
    na_fila = passagem.fila()
except Exception as e:  # noqa: BLE001
    print(f"ALERTA fila das passagens: nao consegui consultar "
          f"({e.__class__.__name__}: {e}).")
    sys.exit(0)

if not na_fila and not DE_VERDADE:
    sys.exit(0)

if not DE_VERDADE:
    print(f"fila das passagens, A SECO: {len(na_fila)} pendencia(s). "
          f"Nada foi escrito.")
    for d in na_fila:
        print(f"  OS {d['numero_os']}: escreveria {d['para_situacao']} "
              f"(ja tentou {d['tentativas']}x, desde {d['pendente_desde']})")
    print("  use --de-verdade para escoar")
    sys.exit(0)

try:
    feito = passagem.escoar_fila()
except Exception as e:  # noqa: BLE001
    print(f"ALERTA fila das passagens: a passada estourou "
          f"({e.__class__.__name__}: {e}).")
    sys.exit(0)

linhas: list[str] = []
if feito["tentadas"]:
    linhas.append(
        f"fila das passagens: {feito['tentadas']} tentada(s), "
        f"{feito['resolvidas']} resolvida(s), {feito['continuam']} "
        f"continuam, {feito['desistiu']} desistencia(s).")

# ------------------------------------------------------------ red flag
velhas = passagem.pendentes_para_a_red_flag()
for d in velhas:
    linhas.append(
        f"ALERTA OS {d['numero_os']}: o card esta em {d['para_situacao']} no "
        f"painel e a OS no Harmonit nao confirmou desde "
        f"{str(d['pendente_desde'])[:16]} ({d['tentativas']} tentativa(s)). "
        f"Ultimo retorno: {d['pendente_erro'] or 'sem motivo informado'}")

if not linhas:
    sys.exit(0)

for linha in linhas:
    print(linha)

if not (AVISAR and velhas):
    sys.exit(0)

numero = (settings.ligacoes_aviso_numero or "").strip()
if not numero:
    print("(MOVIZAP_LIGACOES_AVISO_NUMERO vazio no .env: nada foi enviado.)",
          file=sys.stderr)
    sys.exit(0)

# 🚨 Fala direto com o Evolution, não pela rota do painel: o vigia tem de
# funcionar com o painel fora do ar.
try:
    from movizap import evolution
    evolution.enviar_texto(
        settings.evolution_instancia, numero,
        "MoviZap - Fila de passagens\n\n"
        + "\n".join(x for x in linhas if x.startswith("ALERTA")))
    # ⚠️ Marca DEPOIS de enviar: marcar antes perderia o aviso se o envio
    # falhasse, e ninguém nota a ausência de um aviso.
    passagem.marcar_avisadas([d["id"] for d in velhas])
    print(f"(red flag enviada para {numero[:7]}…)", file=sys.stderr)
except Exception as e:  # noqa: BLE001
    print(f"(nao consegui enviar a red flag: {e.__class__.__name__}: {e})",
          file=sys.stderr)
