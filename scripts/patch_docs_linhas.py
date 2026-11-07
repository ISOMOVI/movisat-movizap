# -*- coding: utf-8 -*-
"""As DUAS linhas de tabela da CFG_15.1 no docs/03 (06/11).

Script separado porque o guard de idempotencia do anterior deu FALSO POSITIVO:
ele comparava a PRIMEIRA linha do bloco novo, que nos dois casos e a linha da
CFG_14.1, que ja existia. As duas insercoes foram puladas em silencio e so a
leitura do arquivo mostrou. Aqui o guard e a propria linha nova.
"""
import pathlib
import sys

P = pathlib.Path("/home/claude/movizap_painel/docs/03_Registro_Telas.md")
t = P.read_text(encoding="utf-8")

PARES = [
    ("| `CFG_14.1` | Vínculo dos técnicos | `/config/vinculo-tecnicos` | `owner` | 1 |",
     "| `CFG_15.1` | Permissão dos painéis | `/config/permissao-paineis` | `owner` | 1 |"),
    ("| `CFG_14.1` Vínculo dos técnicos | `bi-person-vcard` | aba |",
     "| `CFG_15.1` Permissão dos painéis | `bi-shield-lock` | aba |"),
]

feitos = 0
for ancora, nova in PARES:
    if nova in t:
        print("  ja la:", nova[:34])
        continue
    if t.count(ancora) != 1:
        sys.exit(f"ancora apareceu {t.count(ancora)}x: {ancora[:40]}")
    t = t.replace(ancora, ancora + "\n" + nova)
    feitos += 1

P.write_text(t, encoding="utf-8")
print(f"docs/03: {feitos} linha(s) de tabela acrescentada(s)")
