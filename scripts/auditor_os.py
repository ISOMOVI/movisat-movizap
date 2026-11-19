# -*- coding: utf-8 -*-
"""O auditor: levanta a divergência entre a coluna do card e a OS do Harmonit.

🔵 Desenho dele, 18/11: dois agentes, e **este não escreve no ERP**.

Três caminhos, o mesmo texto:

  · **sem argumento** — imprime o resumo. É o modo a seco, e é como ele tem de
    ser exercitado antes de entrar no cron.
  · **`--fechar`** — relê o que o escritor mexeu e fecha as linhas. 🚨 Quem diz
    que ficou bom é a releitura, nunca o escritor.
  · **`--avisar-whatsapp`** — além de imprimir, manda a red flag para o número
    de `MOVIZAP_LIGACOES_AVISO_NUMERO`. 🔵 Mesmo número do informativo das
    ligações, escolha dele.

🚨 EM SILÊNCIO QUANDO ESTÁ TUDO EM DIA: nenhuma linha impressa e nenhuma
mensagem enviada. É a regra herdada do `agentes_mudos.py`, e é o que faz o
aviso ser lido -- *"aviso que aparece todo dia vira aviso que ninguém lê"*.

⚠️ `atraso` e `nao_confirmada` NUNCA viram aviso. São o ERP respondendo
devagar, não trabalho para alguém: foi exatamente isso que produziu as 7
recusas falsas na OS 17133, em 18/11.

🔵 Hora: **03:00**, escolha dele. ⚠️ E não é por ser a janela ociosa -- medido
em 18/11, a madrugada tem 171 chamadas por hora, todas as horas, porque a
varredura do FPSL roda 24h. O critério é a hora com menos GENTE trabalhando.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging  # noqa: E402
logging.disable(logging.CRITICAL)  # o log do pool não pode sujar a saída

from movizap import auditoria_os, banco  # noqa: E402
from movizap.config import settings  # noqa: E402

AVISAR = "--avisar-whatsapp" in sys.argv
FECHAR = "--fechar" in sys.argv

try:
    banco.abrir()
    if FECHAR:
        resultado = auditoria_os.fechar_relendo()
    else:
        resultado = auditoria_os.auditar()
except Exception as e:  # noqa: BLE001
    # 🚨 Falha do próprio vigia FALA, sempre. Vigia que morre calado é pior que
    # vigia nenhum: ninguém nota a ausência de um aviso.
    print(f"ALERTA auditoria de OS: nao consegui rodar "
          f"({e.__class__.__name__}: {e}).")
    sys.exit(0)

linhas: list[str] = []

if FECHAR:
    if resultado["ainda_diferentes"]:
        linhas.append(
            f"ALERTA auditoria de OS: {resultado['ainda_diferentes']} OS "
            f"continuam diferentes depois da reescrita.")
else:
    for d in auditoria_os.abertas():
        linhas.append(
            f"ESCRITA PERDIDA OS {d['numero_os']}: o painel diz "
            f"{d['coluna_nossa']}, o Harmonit ainda diz "
            f"{d['situacao_do_erp']}, e esse valor e NOSSO de antes -- a "
            f"escrita nao chegou. Vai para o escritor.")

a_avisar = auditoria_os.para_a_red_flag()
for d in a_avisar:
    if d["veredito"] == "mudou_no_erp":
        # 🚨 INFORMACAO, NAO TRABALHO. Alguem mexeu na OS dentro do Harmonit, e
        # o ERP e quem esta certo: o card e que estava atras. Reescrever aqui
        # desfaria o trabalho dessa pessoa -- foi o que o ensaio a seco de
        # 18/11 mostrou nas OS 17054 e 17114.
        linhas.append(
            f"AVISO OS {d['numero_os']}: alguem mudou a situacao dentro do "
            f"Harmonit ({d['situacao_do_erp']}); o painel estava em "
            f"{d['coluna_nossa']}. Nada foi reescrito -- o card segue o ERP.")
        continue
    linhas.append(
        f"ALERTA OS {d['numero_os']}: nao consegui acertar a situacao "
        f"({d['coluna_nossa']} x {d['situacao_do_erp']}) em "
        f"{d['tentativas']} tentativa(s), {d['grupos']} grupo(s). "
        f"Ultimo retorno: {d['ultimo_erro'] or 'sem motivo informado'}")

# 🚨 O resumo da rodada só aparece quando HÁ o que dizer. Imprimir "0
# divergências" todas as noites é o jeito mais rápido de ninguém mais ler.
if not linhas:
    sys.exit(0)

if not FECHAR:
    linhas.append(
        f"(rodada: {resultado['lidas']} leitura(s), "
        f"{resultado['iguais']} iguais, "
        f"{resultado['escritas_perdidas']} escrita(s) perdida(s), "
        f"{resultado['mudou_no_erp']} mudada(s) no ERP, "
        f"{resultado['atrasos']} atraso(s) de leitura, "
        f"{resultado['ja_aceito']} ja aceita(s) antes, "
        f"{resultado['nao_confirmadas']} nao confirmada(s), "
        f"{resultado['sem_leitura']} sem leitura)")

for linha in linhas:
    print(linha)

if not AVISAR:
    sys.exit(0)

# ------------------------------------------------------------ red flag
numero = (settings.ligacoes_aviso_numero or "").strip()
if not numero:
    print("(MOVIZAP_LIGACOES_AVISO_NUMERO vazio no .env: nada foi enviado.)",
          file=sys.stderr)
    sys.exit(0)

# 🚨 Fala direto com o Evolution, NÃO pela rota do painel: o vigia tem de
# funcionar inclusive com o painel fora do ar -- e painel fora do ar é um dos
# motivos de a situação da OS ficar para trás.
try:
    from movizap import evolution
    evolution.enviar_texto(settings.evolution_instancia, numero,
                           "MoviZap - Auditoria de OS\n\n" + "\n".join(linhas))
    print(f"(red flag enviada para {numero[:7]}…)", file=sys.stderr)
except Exception as e:  # noqa: BLE001
    # Falhar aqui não pode esconder o alerta: ele já foi impresso acima.
    print(f"(nao consegui enviar a red flag: {e.__class__.__name__}: {e})",
          file=sys.stderr)
