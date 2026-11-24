# -*- coding: utf-8 -*-
"""Tarefa 3.4 — o 502 da ficha passa a deixar rastro no log.

🚨 O DEFEITO, CONFIRMADO EM 23/11: `_ficha_da_os` tem `except Exception` e
levanta `HTTPException(502, ...)` **sem nenhuma linha de log**. Houve 4 casos em
19/11, todos na OS 17137, e nenhum deixou vestígio -- a frase chegou na tela do
operador e morreu ali.

🚨 E É ISSO QUE BLOQUEIA O A10 E O A16. As duas perguntam *"o valor que o ERP
mostra é um que NÓS escrevemos?"*, e para responder é preciso saber **quando a
ponte falhou e com quê**. Sem o log, a investigação depende de alguém estar
olhando a tela na hora.

⚠️ `exc_info=True` de propósito: a frase do `except` guarda `str(e)`, que num
erro de pool do Harmonit é uma linha genérica. O traço é o que diz se foi
`timeout`, pool esgotado ou 500 do ERP -- a distinção que o `18112026.md` §12
usa.
"""
import pathlib

p = pathlib.Path("movizap/main.py")
bruto = p.read_bytes()
CRLF = b"\r\n" in bruto
t = bruto.decode("utf-8").replace("\r\n", "\n")


def troca(velho, novo, rotulo):
    global t
    assert velho in t, "NAO ACHOU (%s)" % rotulo
    assert t.count(velho) == 1, "AMBIGUO %dx (%s)" % (t.count(velho), rotulo)
    t = t.replace(velho, novo, 1)
    print("  ok:", rotulo)


troca('''    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"não deu para ler a OS {numero_os} no Harmonit agora: {e}")''',
      '''    except Exception as e:  # noqa: BLE001
        # 🚨 ESTA LINHA É A TAREFA 3.4, e ela existe porque a falta dela
        # custou uma investigação. Em 19/11 a ficha devolveu 502 quatro
        # vezes, todas na OS 17137, e **nenhuma deixou rastro**: o `except`
        # levantava o 502 direto. A frase chegava na tela do operador e
        # morria ali.
        #
        # ⚠️ E É O QUE DESTRAVA O A10 E O A16: as duas perguntam *"o valor
        # que o ERP mostra é um que NÓS escrevemos?"*, e responder exige
        # saber QUANDO a ponte falhou e COM QUÊ. `exc_info=True` de
        # propósito -- `str(e)` num erro de pool do Harmonit é linha
        # genérica, e o traço é o que separa timeout de pool esgotado e de
        # 500 do ERP.
        log.warning("ficha da OS %s nao veio do Harmonit: %s",
                    numero_os, e, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=f"não deu para ler a OS {numero_os} no Harmonit agora: {e}")''',
      "3.4: o 502 da ficha escreve no log")

saida = t.replace("\n", "\r\n") if CRLF else t
p.write_bytes(saida.encode("utf-8"))
print("gravado:", p, len(saida), "bytes")
