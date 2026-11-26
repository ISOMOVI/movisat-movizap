# -*- coding: utf-8 -*-
"""Liga a fonte unica: o import no main.js e o titulo das tres telas."""
import pathlib, shutil, sys
from datetime import datetime

S = pathlib.Path("/home/claude/movizap_painel/frontend/src")
marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")

# 1. o import, logo depois do componentes.css
main = S / "main.js"
t = main.read_text(encoding="utf-8")
de = "import './estilo/componentes.css'\n"
para = ("import './estilo/componentes.css'\n"
        "/* 🚨 A FONTE ÚNICA DO CSS DOS PAINÉIS (25/11). Vem DEPOIS do\n"
        "   componentes.css de propósito: ela é a casa das regras de painel, e\n"
        "   o que estava copiado em quatro `<style scoped>` mora aqui agora. */\n"
        "import './estilo/painel.css'\n")
if t.count(de) != 1:
    sys.exit(f"ABORTADO: ancora do import {t.count(de)}x")
if "estilo/painel.css" in t:
    print("import ja existia")
else:
    shutil.copy2(main, main.with_suffix(f".js.bak_{marca}_painel_css"))
    main.write_text(t.replace(de, para, 1), encoding="utf-8")
    print("import do painel.css gravado no main.js")

# 2. o titulo: a Operacao usa <h1> cru, as abas usam .painel__titulo
css = S / "estilo" / "painel.css"
t = css.read_text(encoding="utf-8")
alvo = """.escala-operacao .painel__titulo {
  margin: 0;
  font-size: var(--txt-lg);
}"""
novo = """.escala-operacao .painel__titulo,
.escala-operacao .painel__identidade h1,
.escala-operacao .cabecalho__identidade h1 {
  /* 🚨 O TÍTULO DAS TRÊS TELAS NO MESMO TAMANHO. A Operação usa `<h1>` cru e
     as abas usam `.painel__titulo`: sem esta linha, uma herdava o `h1` do
     base.css e a outra o token -- e era parte do *"as fontes ainda estão
     erradas entre as abas"*. */
  margin: 0;
  font-size: var(--txt-lg);
}"""
if t.count(alvo) != 1:
    sys.exit(f"ABORTADO: ancora do titulo {t.count(alvo)}x")
css.write_text(t.replace(alvo, novo, 1), encoding="utf-8")
print("titulo unificado nas tres telas")
