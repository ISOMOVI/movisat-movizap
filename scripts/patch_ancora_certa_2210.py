"""Conserta a ancora que eu escolhi errado -- e medindo, nao chutando.

Eu troquei `"INSERT INTO email_mensagem"` por
`"INSERT INTO email_mensagem (conta_id"`, supondo a formatacao. O INSERT real
quebra a linha antes das colunas:

    \"\"\"INSERT INTO email_mensagem
         (conta_id, id_externo, thread_externa, remetente,

Ou seja: eu consertei uma ancora suposta com outra ancora suposta. A ancora
exata e o nome da tabela seguido de QUEBRA DE LINHA -- e o que distingue
`email_mensagem` de `email_mensagem_marcador` sem depender de como as colunas
estao formatadas hoje.
"""
import shutil
import sys

ALVO = "tests/teste_gmail_pagina.py"

ANTES = '''        # 🚨 A ÂNCORA TEM DE SER EXATA. Até 22/10 ela era
        # `"INSERT INTO email_mensagem"`, que é PREFIXO de
        # `"INSERT INTO email_mensagem_marcador"` -- e quando o espelho dos
        # rótulos locais entrou no `gmail.py`, o `index()` passou a recortar a
        # janela daquele outro INSERT. O teste reprovou com a regra que ele
        # defende intacta: âncora que é prefixo de outro nome não identifica
        # nada, é a mesma armadilha do `grep` por palavra supos­ta (`M15`).
        i = corpo.index("INSERT INTO email_mensagem (conta_id")
        trecho = corpo[i:i + 1400]'''

DEPOIS = '''        # 🚨 A ÂNCORA TEM DE SER EXATA. Até 22/10 ela era
        # `"INSERT INTO email_mensagem"`, que é PREFIXO de
        # `"INSERT INTO email_mensagem_marcador"` -- e quando o espelho dos
        # rótulos locais entrou no `gmail.py`, o `index()` passou a recortar a
        # janela daquele outro INSERT. O teste reprovou com a regra que ele
        # defende intacta: âncora que é prefixo de outro nome não identifica
        # nada, é a mesma armadilha do `grep` por palavra suposta (`M15`).
        #
        # ⚠️ E a primeira correção que eu tentei foi
        # `"INSERT INTO email_mensagem (conta_id"` -- âncora suposta trocada
        # por outra âncora suposta, porque o INSERT real quebra a linha antes
        # das colunas. O que distingue a tabela sem depender da formatação de
        # hoje é o nome seguido de QUEBRA DE LINHA.
        i = corpo.index("INSERT INTO email_mensagem\\n")
        trecho = corpo[i:i + 1400]'''


def main() -> int:
    texto = open(ALVO, encoding="utf-8").read()
    if texto.count(ANTES) != 1:
        raise SystemExit(f"ancora com {texto.count(ANTES)} ocorrencias")
    shutil.copyfile(ALVO, ALVO + ".bak_2026-10-22_ancora")
    open(ALVO, "w", encoding="utf-8").write(texto.replace(ANTES, DEPOIS, 1))
    print(f"ok  {ALVO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
