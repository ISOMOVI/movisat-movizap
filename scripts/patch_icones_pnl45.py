# -*- coding: utf-8 -*-
"""As duas linhas de icone da PNL_1.4 e PNL_1.5 no docs/03. Idempotente."""
import pathlib
import sys

P = pathlib.Path("/home/claude/movizap_painel/docs/03_Registro_Telas.md")
t = P.read_text(encoding="utf-8")

ANCORA = "| `PNL_1.1` Operação | `bi-kanban` | menu (grupo Painéis) |"
NOVAS = [
    "| `PNL_1.4` Financeiro | `bi-cash-coin` | menu (grupo Painéis) |",
    "| `PNL_1.5` Contratual | `bi-file-earmark-text` | menu (grupo Painéis) |",
]

if NOVAS[0] in t:
    sys.exit("ja aplicado")
if t.count(ANCORA) != 1:
    sys.exit(f"ancora apareceu {t.count(ANCORA)}x")

P.write_text(t.replace(ANCORA, ANCORA + "\n" + "\n".join(NOVAS)),
             encoding="utf-8")

t = P.read_text(encoding="utf-8")
print("docs/03: bi-cash-coin =", t.count("bi-cash-coin"),
      "| bi-file-earmark-text =", t.count("bi-file-earmark-text"))
