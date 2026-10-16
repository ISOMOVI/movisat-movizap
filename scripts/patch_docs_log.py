"""docs/ligacoes.md: o log deixou de ter "zero ambíguo" (15/10, pedido dele).

Idempotente. Uso: ./venv/bin/python scripts/patch_docs_log.py [--conferir]
"""
import sys
from pathlib import Path

ALVO = Path(__file__).resolve().parent.parent / "docs/ligacoes.md"
SO_CONFERIR = "--conferir" in sys.argv

DE = """- **Nada é apagado do PC** nesta fase ("7 dias já pode apagar" fica para depois,
  com a palavra dele).
"""
PARA = DE + """- **O log diz QUANTO HAVIA, não só quanto subiu** (15/10). 🔵 *"o resultado do
  script foi zero por ja não ter novos ou nenhum na pasta? importante deixar no
  log a diferença para evitar falso positivo ou pasta movida ou apagada"*. A
  linha virou `... 0 novas, 0 ja estavam na VPS, 0 gravacoes pendentes |
  historico 28, pasta 19 | batimento ok`:
  - `pasta 19` com `0 novas` é silêncio legítimo;
  - `pasta 0` **depois de o PC já ter enviado gravação** não é silêncio, e sai
    com aviso que nomeia o caminho onde ele procurou: *"pasta de gravacoes SEM
    ARQUIVOS mas este PC ja enviou 19: movida ou apagada?"*. O aviso vai no
    batimento, então o vigia da VPS avisa sozinho;
  - se a leitura falhar antes de contar, aparece `historico ?, pasta ?` --
    zero que não foi medido é mentira.
"""

texto = ALVO.read_text(encoding="utf-8")
if "zero que não foi medido é mentira" in texto:
    print("já estava: nota do log")
elif DE not in texto:
    raise SystemExit("ÂNCORA NÃO ACHADA: garantia do 'nada é apagado'")
else:
    if not SO_CONFERIR:
        ALVO.write_text(texto.replace(DE, PARA), encoding="utf-8")
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: nota do log")
