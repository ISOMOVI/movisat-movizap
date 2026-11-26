"""Mata a mentira da docstring da `varrer_servicos` — `M12`, 25/11.

A frase *"A automática roda de madrugada"* era falsa desde 19/11: não existia
cron nenhum. Agora existe, e a docstring passa a dizer a HORA e por que é essa
hora — texto que afirma comportamento tem de ser conferido quando o
comportamento muda.
"""
import pathlib
import shutil
import sys
from datetime import datetime

ALVO = pathlib.Path("/home/claude/movizap_painel/movizap/main.py")

DE = '''    """A varredura à mão. 🔵 A automática roda de madrugada.'''

PARA = '''    """A varredura à mão. A automática roda às **05:10**, no cron do FPSL
    (`scripts/varrer_pagamento.py`, 25/11).

    🚨 O HORÁRIO NÃO É ESCOLHA ESTÉTICA: a varredura lê `os_historico`, que o
    cache WESO escreve às 04:15 e o Harmonit às 04:50. Antes disso ela varreria
    o cache de ONTEM; em cima, disputaria escrita no mesmo SQLite.'''


def main() -> int:
    texto = ALVO.read_text(encoding="utf-8")
    vezes = texto.count(DE)
    if vezes != 1:
        print(f"ABORTADO: a ancora aparece {vezes} vezes. Nada gravado.",
              file=sys.stderr)
        return 1
    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    shutil.copy2(ALVO, ALVO.with_suffix(ALVO.suffix + f".bak_{marca}_docstring"))
    ALVO.write_text(texto.replace(DE, PARA, 1), encoding="utf-8")
    print("docstring corrigida")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
