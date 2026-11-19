# -*- coding: utf-8 -*-
"""O escritor: só reescreve o que o auditor marcou. 🔵 Desenho dele, 18/11.

*"disparar por outro que só vai reescrever, daí guardar os logs juntos para
evitar perca e depois devolve ao primeiro para validar e passar verde. Assim
podemos ter intervalo de escrita e tolerância maior de erros, pois não estarão
usando o pool."*

🔵 **3 grupos de 3 tentativas, 5 minutos entre os grupos** — números dele.

🚨 ESTE AGENTE NÃO DECIDE NADA. A lista vem de `auditoria_os.abertas()`, e ele
não olha o ERP para escolher: se olhasse, voltaria a ser um agente só, e a
separação existe justamente para a escrita acontecer longe da leitura.

🚨 E NÃO DIZ QUE DEU CERTO. Quem fecha é o auditor, com
`auditor_os.py --fechar`. A prova é a releitura, nunca o retorno da escrita --
a mesma regra de toda a ponte, e a única que sobrevive a um ERP que responde
atrasado (OS 17133, 18/11: a mesma rota devolveu dois valores em 31 segundos).

⚠️ **UMA RODADA PODE LEVAR ATÉ 10 MINUTOS** (dois intervalos de 5 min entre os
três grupos). Isso é desenho, não lentidão: é o *"intervalo que dê para o pool
recuperar"* que ele pediu. Quem chama isto no cron tem de contar com o tempo.

🚨 **`--de-verdade` É OBRIGATÓRIO PARA ESCREVER.** Sem a bandeira, só mostra o
que faria. Agente que escreve no ERP por rodar sem argumento é agente que
escreve por acidente -- e aqui o acidente é a OS de um cliente.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging  # noqa: E402
logging.disable(logging.CRITICAL)

from movizap import auditoria_os, banco  # noqa: E402

DE_VERDADE = "--de-verdade" in sys.argv

try:
    banco.abrir()
    pendentes = auditoria_os.abertas()
except Exception as e:  # noqa: BLE001
    print(f"ALERTA escritor de OS: nao consegui consultar a lista "
          f"({e.__class__.__name__}: {e}).")
    sys.exit(0)

if not pendentes:
    # 🚨 Silêncio: nada a fazer não é notícia.
    sys.exit(0)

if not DE_VERDADE:
    print(f"escritor de OS, A SECO: {len(pendentes)} linha(s) na lista do "
          f"auditor. Nada foi escrito.")
    for d in pendentes:
        print(f"  OS {d['numero_os']}: escreveria {d['coluna_nossa']} "
              f"(o Harmonit esta em {d['situacao_do_erp']})")
    print("  use --de-verdade para escrever")
    sys.exit(0)

try:
    feito = auditoria_os.escrever()
except Exception as e:  # noqa: BLE001
    print(f"ALERTA escritor de OS: a rodada estourou "
          f"({e.__class__.__name__}: {e}).")
    sys.exit(0)

print(f"escritor de OS: {feito['linhas']} linha(s), "
      f"{feito['escritas']} escrita(s) aceita(s), "
      f"{feito['desistiu']} desistencia(s), "
      f"{feito['grupos_usados']} grupo(s) usado(s).")
# ⚠️ E a palavra final não é minha: o auditor relê.
print("  agora rode: auditor_os.py --fechar   (a prova e a releitura)")
