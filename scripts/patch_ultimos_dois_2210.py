"""Os dois ultimos vermelhos -- causas DIFERENTES, e so uma e fixture.

**1. `teste_caixa_por_atendente.py`** -- mesma fixture irreal dos outros: a
mensagem nascia sem rotulo, e com a Entrada exigindo `INBOX` ela virou mensagem
arquivada. Corrige a fixture, nao o filtro.

**2. `teste_gmail_pagina.py`** -- NAO e fixture, e e o mais instrutivo do dia.
O teste le o CODIGO-FONTE do `gmail.py`:

    i = corpo.index("INSERT INTO email_mensagem")
    trecho = corpo[i:i + 1400]

A ancora `"INSERT INTO email_mensagem"` casa tambem com
`"INSERT INTO email_mensagem_marcador"`, e a minha `_espelhar_rotulos` aparece
ANTES do INSERT de importacao no arquivo. O `index()` passou a recortar a
janela errada, e o teste reprovou com a regra que ele defende **intacta**.

🚨 A ANCORA ERA UM PREFIXO DE OUTRO NOME, e isso e o `M15` na forma de teste:
`"INSERT INTO email_mensagem"` nao identifica o INSERT de mensagem -- identifica
qualquer tabela que COMECE com esse nome. A correcao e tornar a ancora exata
(`INSERT INTO email_mensagem (conta_id`), nao afrouxar o que o teste afirma: a
regra que ele guarda (`enviado_em` vem do cabecalho `Date`, senao a caixa
ordena pela data de importacao) continua valendo inteira.
"""
import shutil
import sys

# ---------------------------------------------------------------------------
# 1. a fixture
# ---------------------------------------------------------------------------
CAIXA = "tests/teste_caixa_por_atendente.py"

CAIXA_ANTES = '''    msg = banco.um(
        """INSERT INTO email_mensagem (conta_id, id_externo, remetente, assunto)
           VALUES (%s, 'zz-externo-1', 'quem@fora.com', 'assunto secreto')
           RETURNING id""", (conta,))["id"]'''

CAIXA_DEPOIS = '''    msg = banco.um(
        """INSERT INTO email_mensagem (conta_id, id_externo, remetente, assunto)
           VALUES (%s, 'zz-externo-1', 'quem@fora.com', 'assunto secreto')
           RETURNING id""", (conta,))["id"]
    # 🚨 O `INBOX` É PARTE DE "MENSAGEM NA CAIXA" desde 22/10: a Entrada passou
    # a exigir o rótulo, que é como o Gmail diz onde a mensagem está. Sem ele
    # esta seria uma mensagem ARQUIVADA, e o teste do dono reprovava por
    # fixture irreal -- não por falha da barreira que ele defende.
    rotulo = banco.um(
        """INSERT INTO email_marcador (conta_id, id_externo, nome, natureza)
           VALUES (%s, 'INBOX', 'INBOX', 'sistema')
           ON CONFLICT (conta_id, id_externo)
           DO UPDATE SET nome = email_marcador.nome RETURNING id""",
        (conta,))["id"]
    banco.executar(
        """INSERT INTO email_mensagem_marcador (mensagem_id, marcador_id)
           VALUES (%s, %s) ON CONFLICT DO NOTHING""", (msg, rotulo))'''

# ---------------------------------------------------------------------------
# 2. a ancora ambigua
# ---------------------------------------------------------------------------
PAGINA = "tests/teste_gmail_pagina.py"

PAGINA_ANTES = '''        corpo = FONTE.read_text(encoding="utf-8")
        i = corpo.index("INSERT INTO email_mensagem")
        trecho = corpo[i:i + 1400]'''

PAGINA_DEPOIS = '''        corpo = FONTE.read_text(encoding="utf-8")
        # 🚨 A ÂNCORA TEM DE SER EXATA. Até 22/10 ela era
        # `"INSERT INTO email_mensagem"`, que é PREFIXO de
        # `"INSERT INTO email_mensagem_marcador"` -- e quando o espelho dos
        # rótulos locais entrou no `gmail.py`, o `index()` passou a recortar a
        # janela daquele outro INSERT. O teste reprovou com a regra que ele
        # defende intacta: âncora que é prefixo de outro nome não identifica
        # nada, é a mesma armadilha do `grep` por palavra supos­ta (`M15`).
        i = corpo.index("INSERT INTO email_mensagem (conta_id")
        trecho = corpo[i:i + 1400]'''


def aplicar(caminho, antes, depois, marca):
    texto = open(caminho, encoding="utf-8").read()
    if marca in texto:
        raise SystemExit(f"{caminho}: ja aplicado")
    if texto.count(antes) != 1:
        raise SystemExit(f"FALHOU {caminho}: {texto.count(antes)} ocorrencias")
    shutil.copyfile(caminho, caminho + ".bak_2026-10-22_caixas")
    open(caminho, "w", encoding="utf-8").write(texto.replace(antes, depois, 1))
    print(f"ok  {caminho}")


def main() -> int:
    aplicar(CAIXA, CAIXA_ANTES, CAIXA_DEPOIS, "email_mensagem_marcador")
    aplicar(PAGINA, PAGINA_ANTES, PAGINA_DEPOIS,
            "INSERT INTO email_mensagem (conta_id")
    return 0


if __name__ == "__main__":
    sys.exit(main())
