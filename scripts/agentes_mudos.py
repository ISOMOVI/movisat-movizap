"""O vigia dos agentes de ligação: PC mudo, PC com aviso, certificado vencendo.

🔵 *"se ficar mais 1 dia sem comunicar com VPS, tenhamos um alerta pelo meu
shell, inicialmente"* (18/09) e, em 15/10, *"Rotina da VPS verifica se os
envios estão sendo feito corretamente"*.

Dois caminhos, o mesmo texto:

  · **sem argumento** — imprime. É o gancho `SessionStart` do Claude Code, que
    roda isto por ssh ao abrir a sessão e põe a saída na minha mão.
  · **`--avisar-whatsapp`** — além de imprimir, manda UMA mensagem para o
    número de `MOVIZAP_LIGACOES_AVISO_NUMERO`. É o cron da VPS (08:10 e 18:10),
    e é o que faz o alerta existir **mesmo que ninguém abra sessão** -- antes
    de 15/10 o gatilho era só a minha sessão, e com 8 operadores isso não se
    sustenta.

🚨 EM SILÊNCIO QUANDO ESTÁ TUDO EM DIA: nenhuma linha impressa e nenhuma
mensagem enviada. Aviso que aparece todo dia vira aviso que ninguém lê.

⚠️ Por que NÃO existe alerta de "ramal revogado sem substituto": a revogação
acontece junto do alistamento do PC novo (`ligacoes.gerar_chave` revoga e cria
na mesma transação), e fora disso só à mão, quando alguém sai da empresa --
avisar nesse caso seria cobrar a reinstalação de quem foi embora.
"""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging  # noqa: E402
logging.disable(logging.CRITICAL)  # o log do pool não pode sujar a saída

from movizap import banco, ligacoes  # noqa: E402
from movizap.config import settings  # noqa: E402

AVISAR = "--avisar-whatsapp" in sys.argv
# 🔵 15/10: com `--resumo`, "tudo em dia" também fala -- uma linha dizendo
# quantos PCs estão enviando. Sem a bandeira, o comportamento é o de antes:
# silêncio total quando não há nada errado.
RESUMO = "--resumo" in sys.argv
br = ZoneInfo("America/Sao_Paulo")

try:
    banco.abrir()
    mudos = ligacoes.agentes_mudos()
    avisos = ligacoes.agentes_com_aviso()
    vencendo = ligacoes.certs_vencendo()
except Exception as e:  # noqa: BLE001
    print(f"ALERTA MoviZap Ligações: não consegui consultar os agentes ({e.__class__.__name__}).")
    sys.exit(0)

linhas: list[str] = []

# PC que fala, mas trouxe erro ou aviso (gravação desligada, arquivo pulado...).
for m in avisos:
    texto = " | ".join(x for x in (m["ultimo_erro"], m["ultimo_aviso"]) if x)
    linhas.append(f"AVISO MoviZap Ligações: ramal {m['ramal']} ({m['operador']}), "
                  f"PC {m['ultimo_pc'] or '?'}: {texto}")

# Certificado do PC vencendo: vencido, o nginx recusa e o PC fica mudo.
for m in vencendo:
    linhas.append(f"AVISO MoviZap Ligações: o certificado do ramal {m['ramal']} "
                  f"({m['operador']}) vence em "
                  f"{m['cert_validade'].astimezone(br):%d/%m/%Y}: alistar o PC de novo.")

if mudos:
    linhas.append(f"ALERTA MoviZap Ligações: {len(mudos)} PC(s) sem falar com a VPS há mais de "
                  f"{ligacoes.HORAS_MUDO} h (as gravações deles não estão tendo backup):")
    for m in mudos:
        if m["ultimo_contato_em"]:
            desde = m["ultimo_contato_em"].astimezone(br)
            horas = (datetime.now(br) - desde).total_seconds() / 3600
            quando = f"último contato {desde:%d/%m %H:%M} ({horas:.0f} h atrás)"
        else:
            quando = f"NUNCA falou (chave criada em {m['criado_em'].astimezone(br):%d/%m %H:%M})"
        extra = f" | último erro: {m['ultimo_erro']}" if m["ultimo_erro"] else ""
        linhas.append(f"  - ramal {m['ramal']} ({m['operador']}), "
                      f"PC {m['ultimo_pc'] or '?'}: {quando}{extra}")

if not linhas:
    if not RESUMO:
        # 🚨 O SILÊNCIO É A REGRA. Sem `--resumo`, nada errado = nada dito, que
        # é o que faz um alerta ser alerta.
        sys.exit(0)
    # 🔵 15/10: o resumo de "está tudo em dia". Ele diz o NÚMERO, não um
    # "tudo ok": a frase que não conta nada não distingue vigia funcionando de
    # vigia olhando para uma base vazia.
    try:
        vivos = ligacoes.agentes_vivos_resumo()
    except Exception as e:  # noqa: BLE001
        print(f"ALERTA MoviZap Ligações: não consegui montar o resumo "
              f"({e.__class__.__name__}).")
        sys.exit(0)
    linhas.append(
        f"MoviZap Ligações, {datetime.now(br):%d/%m}: tudo em dia. "
        f"{vivos['com_agente']} PC(s) enviando, "
        f"{vivos['ligacoes_hoje']} ligação(ões) hoje"
        + (f", {vivos['sem_agente']} atendente(s) ainda sem agente."
           if vivos["sem_agente"] else "."))

for linha in linhas:
    print(linha)

if not AVISAR:
    sys.exit(0)

# ------------------------------------------------------------ aviso por WhatsApp
numero = (settings.ligacoes_aviso_numero or "").strip()
if not numero:
    print("(MOVIZAP_LIGACOES_AVISO_NUMERO vazio no .env: nada foi enviado.)", file=sys.stderr)
    sys.exit(0)

# 🚨 Fala direto com o Evolution, não pela rota do painel: o vigia tem de
# funcionar inclusive quando o painel está fora do ar -- que é justamente um
# dos motivos de um PC parecer mudo.
try:
    from movizap import evolution
    texto = "MoviZap - Backup de Ligações\n\n" + "\n".join(linhas)
    evolution.enviar_texto(settings.evolution_instancia, numero, texto)
    print(f"(aviso enviado para {numero[:7]}…)", file=sys.stderr)
except Exception as e:  # noqa: BLE001
    # Falhar aqui não pode esconder o alerta: ele já foi impresso acima.
    print(f"(não consegui enviar o aviso por WhatsApp: {e.__class__.__name__}: {e})",
          file=sys.stderr)
