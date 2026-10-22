"""Fase 1, parte 3: o doc do registro e os testes que guardam o que mudou.

O doc e o TERCEIRO LUGAR (telas.py, router/index.js, 03_Registro_Telas.md) e
dois testes o conferem linha a linha -- `test_doc_conhece_todas_as_telas` e
`test_doc_traz_a_PERMISSAO_e_a_FASE_certas`. Mudar a permissao no codigo sem
mudar o doc deixa o doc mentindo, que foi exatamente o buraco de 12/08.
"""
import shutil
import sys

# (arquivo, antes, depois, quantas ocorrencias esperadas)
TROCAS = [
    # ---- doc: a tabela de telas (tem teste) ----
    ("docs/03_Registro_Telas.md",
     "| `ATD_1.1` | Caixa de entrada | `/atendimento` | `atendimento` | 1 |",
     "| `ATD_1.1` | WhatsApp | `/atendimento` | `atendimento` | 1 |", 1),
    ("docs/03_Registro_Telas.md",
     "| `ATD_1.3` | Fila | `/atendimento/fila` | `atendimento` | 1 |",
     "| `ATD_1.3` | Fila | `/atendimento/fila` | `equipe` | 1 |", 1),
    ("docs/03_Registro_Telas.md",
     "| `ATD_5.1` | Histórico | `/atendimento/historico` | `atendimento` | 1 |",
     "| `ATD_5.1` | Histórico | `/atendimento/historico` | `equipe` | 1 |", 1),
    # ---- doc: a tabela de icones ----
    ("docs/03_Registro_Telas.md",
     "| `ATD_1.1` Caixa de entrada | `bi-chat-dots` | menu |",
     "| `ATD_1.1` WhatsApp | `bi-chat-dots` | menu |", 1),
    # ---- o teste do titulo ----
    ("tests/teste_telas.py",
     'assert telas.por_codigo("ATD_1.1")["titulo"] == "Caixa de entrada"',
     'assert telas.por_codigo("ATD_1.1")["titulo"] == "WhatsApp"', 1),
]

# O teste do admin monta o esperado a partir de `permissao == "atendimento"`.
# Fila e Historico sairam dessa permissao, mas o admin CONTINUA vendo as duas
# (ele tem `equipe`) -- entao as duas precisam entrar no esperado de forma
# explicita, ou o conjunto fechado reprova por uma mudanca que foi pedida.
ADMIN_ANTES = '''        esperado = de_atendimento | {"CAD_2.1", "CAD_2.2", "CFG_10.1", "CFG_11.1",
                                     "CFG_12.1"}'''
ADMIN_DEPOIS = '''        # 🔵 22/10: a Fila e o Histórico passaram de `atendimento` para
        # `equipe` (*"Itens Fila, Histórico não só aparecem para Admin e
        # Owner"*). O admin continua vendo as duas, porque tem `equipe` -- mas
        # elas deixaram de entrar por `de_atendimento`, e por isso vêm
        # nomeadas aqui. O conjunto segue FECHADO: é esta linha que tem de
        # mudar quando a decisão dele mudar, não o assert.
        esperado = de_atendimento | {"ATD_1.3", "ATD_5.1",
                                     "CAD_2.1", "CAD_2.2", "CFG_10.1", "CFG_11.1",
                                     "CFG_12.1"}'''


def aplicar(caminho, antes, depois, esperadas):
    texto = open(caminho, encoding="utf-8").read()
    achadas = texto.count(antes)
    if achadas != esperadas:
        return f"FALHOU {caminho}: {achadas} ocorrencia(s), esperava {esperadas} -- {antes[:60]!r}"
    bak = caminho + ".bak_2026-10-22_atendimento"
    try:
        open(bak, "x", encoding="utf-8").write(texto)
    except FileExistsError:
        pass
    open(caminho, "w", encoding="utf-8").write(texto.replace(antes, depois, esperadas))
    return f"ok  {caminho}: {antes[:58]!r}"


def main() -> int:
    erros = []
    for caminho, antes, depois, n in TROCAS:
        r = aplicar(caminho, antes, depois, n)
        print(r)
        if r.startswith("FALHOU"):
            erros.append(r)
    r = aplicar("tests/teste_telas.py", ADMIN_ANTES, ADMIN_DEPOIS, 1)
    print(r)
    if r.startswith("FALHOU"):
        erros.append(r)
    if erros:
        print("\n--- NAO aplicado por inteiro ---")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
