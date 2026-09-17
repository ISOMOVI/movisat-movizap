"""Varredura periódica: o que sumiu ou foi para a lixeira no Gmail.

Roda em intervalo maior que o `ler_caixa.py` (a cada 2 min) de propósito:
ninguém precisa saber em 2 minutos que um e-mail foi apagado, e rodar junto
dobraria as chamadas ao Gmail sem ganho nenhum. Ver `gmail.sincronizar_exclusoes`
para a razão de ser varredura e não `history.list`.
"""
import sys

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco, gmail  # noqa: E402

banco.abrir()
try:
    r = gmail.sincronizar_exclusoes()
    print(f"varredura: {r}")
finally:
    banco.fechar()
