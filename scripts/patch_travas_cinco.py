# -*- coding: utf-8 -*-
"""Atualiza as quatro travas que listavam os paineis do grupo 'Paineis'.

🚨 Nao e afrouxar: as quatro afirmavam um FATO que mudou (eram tres telas, sao
cinco). O que muda e a lista esperada; a intencao de cada trava fica igual, e
duas ganham a razao de terem ficado vermelhas escrita no lugar.

Idempotente, com guard pela linha NOVA.
"""
import pathlib
import sys

RAIZ = pathlib.Path("/home/claude/movizap_painel")
feitos = []


def trocar(arquivo, velho, novo, rotulo, guard):
    p = RAIZ / arquivo
    t = p.read_text(encoding="utf-8")
    if guard in t:
        print(f"  {rotulo}: ja aplicado")
        return
    if t.count(velho) != 1:
        sys.exit(f"{rotulo}: ancora apareceu {t.count(velho)}x")
    p.write_text(t.replace(velho, novo), encoding="utf-8")
    feitos.append(rotulo)
    print(f"  {rotulo}: ok")


OS_CINCO = ('["PNL_1.1", "PNL_1.2", "PNL_1.3", "PNL_1.4", "PNL_1.5"]')

# -------------------------------------------------- tests/teste_menu_grupos.py
trocar(
    "tests/teste_menu_grupos.py",
    '''        # 🔵 05/11: entraram as duas abas do Pos-venda.
        assert dentro == ["PNL_1.1", "PNL_1.2", "PNL_1.3"]''',
    f'''        # 🔵 05/11: entraram as duas abas do Pos-venda.
        # 🔵 06/11: entraram o Financeiro (`PNL_1.4`) e o Contratual
        # (`PNL_1.5`) -- *"conclua e exiba o financeiro no paniel para owner"*
        # e *"gere a mesmta tela do 'Financeiro' para o 'Contratual'"*. Os
        # quatro paineis do `paineis.PAINEIS` passaram a ter tela.
        assert dentro == {OS_CINCO}''',
    "menu_grupos: a lista do grupo",
    "06/11: entraram o Financeiro (`PNL_1.4`) e o Contratual",
)
trocar(
    "tests/teste_menu_grupos.py",
    '''        assert [t["codigo"] for t in itens] == ["PNL_1.1", "PNL_1.2"]
        assert [t["titulo"] for t in itens] == ["Operação", "Pós-venda"]''',
    '''        # 🔵 06/11: QUATRO itens, e cinco telas -- a `PNL_1.3` continua
        # sendo a unica com `aba_de`, porque e a aba de dentro do Pos-venda.
        # O Financeiro e o Contratual sao paineis proprios, com item proprio.
        assert ([t["codigo"] for t in itens]
                == ["PNL_1.1", "PNL_1.2", "PNL_1.4", "PNL_1.5"])
        assert ([t["titulo"] for t in itens]
                == ["Operação", "Pós-venda", "Financeiro", "Contratual"])''',
    "menu_grupos: os itens de menu",
    "QUATRO itens, e cinco telas",
)

# ----------------------------------------------------- tests/teste_paineis.py
trocar(
    "tests/teste_paineis.py",
    '''    assert dentro == ["PNL_1.1", "PNL_1.2", "PNL_1.3"]''',
    f'''    # 🔵 06/11: o Financeiro (`PNL_1.4`, 10 colunas) e o Contratual
    # (`PNL_1.5`, 6) entraram, e com eles os QUATRO paineis declarados em
    # `paineis.PAINEIS` desde 22/10 passaram a ter tela. ⚠️ `COM_TELA` segue
    # sendo so `operacao`, e e certo: ele governa o `quadro()`, que fala com o
    # Harmonit -- os tres novos passam pelo `quadro_da_aba`, que nao fala.
    assert dentro == {OS_CINCO}''',
    "paineis: a lista do grupo",
    "o Financeiro (`PNL_1.4`, 10 colunas) e o Contratual",
)

# --------------------------------------------- tests/teste_permissao_paineis.py
# 🚨 Defeito MEU: `AS_TRES` era uma lista fixa num arquivo cujo assunto e
# justamente "painel novo entra sozinho".
trocar(
    "tests/teste_permissao_paineis.py",
    '''LOGIN = "teste_perm_paineis"
AS_TRES = {"PNL_1.1", "PNL_1.2", "PNL_1.3"}''',
    '''LOGIN = "teste_perm_paineis"


def os_paineis() -> set[str]:
    """As telas de painel, SAINDO DO REGISTRO.

    🚨 Era uma constante `AS_TRES = {"PNL_1.1", "PNL_1.2", "PNL_1.3"}`, e ficou
    vermelha no mesmo dia: o Financeiro (`PNL_1.4`) e o Contratual (`PNL_1.5`)
    entraram horas depois. ⚠️ Num arquivo cujo assunto e *"painel novo entra
    sozinho na aba de permissao"*, lista fixa era o proprio defeito que ele
    cobrava -- obrigava a editar teste a cada painel novo, que e exatamente o
    que o desenho promete nao ser necessario.
    """
    return {t["codigo"] for t in registro_telas.ativas()
            if registro_telas.grupo_da(t) == "Painéis"}''',
    "permissao_paineis: AS_TRES vira funcao",
    "def os_paineis() -> set[str]:",
)

p = RAIZ / "tests/teste_permissao_paineis.py"
t = p.read_text(encoding="utf-8")
if "AS_TRES" in t:
    t = t.replace("AS_TRES", "os_paineis()")
    # A docstring da funcao nova nao pode ter sido tocada.
    t = t.replace('`os_paineis() = {"PNL_1.1"', '`AS_TRES = {"PNL_1.1"')
    p.write_text(t, encoding="utf-8")
    print("  permissao_paineis: usos de AS_TRES trocados")

print("\nconferindo com grep:")
for arquivo in ("tests/teste_menu_grupos.py", "tests/teste_paineis.py",
                "tests/teste_permissao_paineis.py"):
    t = (RAIZ / arquivo).read_text(encoding="utf-8")
    print(f"  {arquivo}: PNL_1.4={t.count('PNL_1.4')} "
          f"PNL_1.5={t.count('PNL_1.5')} AS_TRES={t.count('AS_TRES')}")
