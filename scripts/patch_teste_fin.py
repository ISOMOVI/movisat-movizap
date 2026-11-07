# -*- coding: utf-8 -*-
"""O teste do Financeiro fixava a lista INTEIRA de paineis e quebrou no quinto.

🚨 Ironia medida: o teste existia para provar que "painel novo entra sozinho" na
aba de permissao -- e era ele que impedia painel novo de entrar sem editar
teste. A asseveracao certa e "o Financeiro esta la, na ordem do REGISTRO", nao
"a lista e exatamente esta".
"""
import pathlib
import sys

P = pathlib.Path("/home/claude/movizap_painel/tests/teste_painel_financeiro.py")
t = P.read_text(encoding="utf-8")

VELHO = '''    assert CODIGO in permissao_paineis.codigos_concediveis()
    grade = permissao_paineis.grade()
    codigos = [t["codigo"] for t in grade["telas"]]
    assert codigos == ["PNL_1.1", "PNL_1.2", "PNL_1.3", "PNL_1.4"]'''

NOVO = '''    assert CODIGO in permissao_paineis.codigos_concediveis()
    grade = permissao_paineis.grade()
    codigos = [t["codigo"] for t in grade["telas"]]
    assert CODIGO in codigos
    # 🚨 NÃO FIXA A LISTA INTEIRA, e isto é conserto de um defeito meu de hoje:
    # a primeira versão asseverava `== ["PNL_1.1", ..., "PNL_1.4"]` e ficou
    # vermelha meia hora depois, quando o Contratual (`PNL_1.5`) entrou. Um
    # teste que existe para provar que *"painel novo entra sozinho"* não pode
    # ser justamente o que obriga a editar teste quando um painel novo entra.
    # ⚠️ A asseveração certa é a ORDEM DO REGISTRO, que é o contrato real.
    do_registro = [t["codigo"] for t in registro_telas.ativas()
                   if registro_telas.grupo_da(t) == "Painéis"]
    assert codigos == do_registro'''

if "NÃO FIXA A LISTA INTEIRA" in t:
    sys.exit("ja aplicado")
if t.count(VELHO) != 1:
    sys.exit(f"ancora apareceu {t.count(VELHO)}x")

P.write_text(t.replace(VELHO, NOVO), encoding="utf-8")
print("teste_painel_financeiro.py: a asseveracao passou a ser a ordem do registro")
