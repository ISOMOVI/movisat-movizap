"""Patch da auditoria: cinco textos que passaram a mentir quando o grupo
"Painéis" ganhou tela.

🚨 `M12` — TELA (E COMENTÁRIO) QUE MENTE É DEFEITO. Cada um destes textos era
verdadeiro quando foi escrito, em 19, 21 e 22/10: *"Painéis › Operacional
nasce vazio"*. Desde a `PNL_1.1`, o grupo tem tela e o subgrupo não existe
mais. Quem lê o comentário hoje aprende errado, e quem escreve o próximo
painel procura um subgrupo que saiu.

⚠️ O `docs/06` NÃO entra aqui: ele é diário, e entrada datada descreve o que
era verdade naquele dia -- a seção de 22/10 corrige as anteriores. O que se
conserta é o que afirma o PRESENTE: o registro, o código e o `docs/03`.
"""
import sys
from pathlib import Path

RAIZ = Path("/home/claude/movizap_painel")


def trocar(caminho, velho, novo, marca):
    t = caminho.read_text(encoding="utf-8")
    if marca in t:
        print(f"{caminho.name}: {marca!r} ja estava")
        return
    if t.count(velho) != 1:
        sys.exit(f"{caminho.name}: ancora de {marca!r} aparece {t.count(velho)}x")
    caminho.write_text(t.replace(velho, novo, 1), encoding="utf-8")
    print(f"{caminho.name}: {marca!r} corrigido")


TELAS = RAIZ / "movizap" / "telas.py"

# 1) o cabeçalho de GRUPOS
trocar(TELAS,
       """# 🔵 19/10, decisão dele: o menu abre em "grupos e subgrupos", e
# **Painéis › Operacional nasce vazio** -- o grupo é criado aqui e só aparece
# na tela quando tiver a primeira tela dentro. É o `MenuLateral` que não
# desenha grupo sem item visível; esta lista só declara que ele existe.""",
       """# 🔵 19/10, decisão dele: o menu abre em "grupos e subgrupos", e um grupo
# pode ser criado aqui VAZIO -- ele só aparece na tela quando tiver a primeira
# tela dentro. É o `MenuLateral` que não desenha grupo sem item visível; esta
# lista só declara que ele existe.
#
# ⚠️ ATÉ 22/10 O EXEMPLO DISSO ERA "Painéis › Operacional". Não é mais: o
# grupo "Painéis" ganhou a `PNL_1.1` e o subgrupo saiu (ver abaixo). Quem
# ficou vazio e declarado é o **"E-mail"**, desde que o item do e-mail passou
# a morar dentro de "Atendimento" -- por decisão dele, no mesmo dia.""",
       "ATÉ 22/10 O EXEMPLO DISSO ERA")

# 2) o comentário da EML_1.1
trocar(TELAS,
       """        # ⚠️ O grupo "E-mail" continua declarado em GRUPOS e fica VAZIO. O
        # MenuLateral não desenha grupo sem tela visível, então ele some da
        # tela sozinho -- igual a "Painéis › Operacional".""",
       """        # ⚠️ O grupo "E-mail" continua declarado em GRUPOS e fica VAZIO. O
        # MenuLateral não desenha grupo sem tela visível, então ele some da
        # tela sozinho. 🚨 Hoje ele é o ÚNICO assim: "Painéis" era o outro
        # exemplo e ganhou tela em 22/10 (a `PNL_1.1`).""",
       'é o ÚNICO assim')

# 3) o comentário da FRM_1.1, que dizia que Painéis continuava vazio
trocar(TELAS,
       """        # ⚠️ O GRUPO E "Atendimento" DE PROPOSITO, e nao "Paineis": os quatro
        # paineis por situacao da OS sao a Etapa 3, e ate eles existirem o
        # grupo "Paineis" continua vazio -- o MenuLateral nao desenha grupo
        # sem tela visivel.""",
       """        # ⚠️ O GRUPO E "Atendimento" DE PROPOSITO, e nao "Paineis": esta tela e
        # a CAIXA do que chega (ler, mudar estado, baixar anexo), e painel e
        # outra coisa -- fila que se movimenta pela situacao da OS.
        #
        # 🚨 22/10, fim do dia: o grupo "Paineis" DEIXOU de estar vazio -- a
        # `PNL_1.1` (Operacao) entrou nele. Esta tela continua em
        # "Atendimento", e e decisao, nao sobra.""",
       "DEIXOU de estar vazio")

# 4) docs/03 — o registro afirma o presente
trocar(RAIZ / "docs" / "03_Registro_Telas.md",
       """🚨 **Grupo sem nenhuma tela visível não é desenhado.** É o que deixa
**Painéis › Operacional** existir declarado e nascer vazio (decisão dele),
sem mentir na tela. Vale igual para permissão: quem não tem nenhuma tela do
grupo não vê o grupo.""",
       """🚨 **Grupo sem nenhuma tela visível não é desenhado.** É o que deixa um grupo
existir declarado e nascer vazio (decisão dele) sem mentir na tela. Vale igual
para permissão: quem não tem nenhuma tela do grupo não vê o grupo.

⚠️ **O exemplo mudou em 22/10.** Era "Painéis › Operacional"; o grupo
**Painéis** ganhou a `PNL_1.1` (Operação) e o subgrupo "Operacional" **saiu**
— ele nunca teve tela, e o painel chama-se "Operação". Hoje o grupo declarado
e vazio é o **"E-mail"**, porque o item do e-mail mora dentro de
"Atendimento".""",
       "O exemplo mudou em 22/10")

# 5) os dois comentários do MenuLateral
MENU = RAIZ / "frontend" / "src" / "componentes" / "MenuLateral.vue"
trocar(MENU,
       """    🚨 GRUPO SEM NENHUMA TELA VISÍVEL NÃO É DESENHADO -- e é isso que deixa
    "Painéis › Operacional" existir no registro sem mentir na tela. Vale""",
       """    🚨 GRUPO SEM NENHUMA TELA VISÍVEL NÃO É DESENHADO -- e é isso que deixa
    um grupo existir no registro sem mentir na tela. ⚠️ O exemplo era
    "Painéis › Operacional"; desde 22/10 "Painéis" tem tela (a `PNL_1.1`) e o
    grupo declarado e vazio é o "E-mail". Vale""",
       'desde 22/10 "Painéis" tem tela')

trocar(MENU,
       """/* O subgrupo só ganha rótulo quando tem nome. Hoje nenhuma tela usa -- a
   estrutura existe porque "Painéis › Operacional" já está declarado no
   registro e nasce vazio por decisão dele. */""",
       """/* O subgrupo só ganha rótulo quando tem nome. 🚨 Hoje NENHUMA tela usa, e
   nenhum grupo declara subgrupo: o único que declarava era "Painéis ›
   Operacional", e o subgrupo saiu em 22/10 quando o painel da Operação entrou
   como ITEM do grupo. A estrutura fica porque o menu em dois níveis é decisão
   dele (19/10) e o próximo subgrupo entra sem código novo. */""",
       "o subgrupo saiu em 22/10")
