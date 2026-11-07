# -*- coding: utf-8 -*-
"""O `limpar()` tem de reabrir o pool: o TestClient fecha o banco no caminho."""
import pathlib
import sys

P = pathlib.Path("/home/claude/movizap_painel/tests/teste_permissao_paineis.py")
t = P.read_text(encoding="utf-8")

VELHO = '''def limpar():
    banco.executar('''
NOVO = '''def limpar():
    # 🚨 REABRE O POOL ANTES DE LIMPAR, e não é zelo: o `TestClient`, ao sair do
    # `with`, dispara o `shutdown` do app -- que chama `banco.fechar()`. A
    # fixture `pessoa` é de FUNÇÃO e a `cliente` é de MÓDULO, então a limpeza do
    # último teste do arquivo cai depois do banco já fechado e estoura com
    # *"banco não foi aberto"*. ⚠️ Erro em TEARDOWN é o pior dos dois mundos: o
    # teste passa, o arquivo fica vermelho, e a sobra (uma pessoa com painel
    # concedido) continua no banco de produção. `abrir()` é no-op se já estiver
    # aberto.
    banco.abrir()
    banco.executar('''

if "REABRE O POOL ANTES DE LIMPAR" in t:
    sys.exit("ja aplicado")
if t.count(VELHO) != 1:
    sys.exit(f"ancora apareceu {t.count(VELHO)}x")

P.write_text(t.replace(VELHO, NOVO), encoding="utf-8")
print("teste_permissao_paineis.py: limpar() reabre o pool")
