# -*- coding: utf-8 -*-
"""Normaliza um retrato de esquema, para o diff medir MUDANCA e nao RENDER.

🚨 O ACHADO DE 27/11 QUE ESTE ARQUIVO EXISTE PARA RESOLVER. Copia restaurada
NAO sai byte a byte igual a producao, mesmo sem mudanca nenhuma: o `pg_dump`
imprime o MESMO `CHECK ... = ANY (ARRAY[...])` de duas formas, dependendo de
como a expressao foi armazenada --

  producao (constraint ORIGINAL):
    ANY ((ARRAY['a'::character varying, 'b'::character varying])::text[])
  copia (constraint RE-ANALISADA a partir do texto do dump):
    ANY (ARRAY[('a'::character varying)::text, ('b'::character varying)::text])

As duas aceitam exatamente os mesmos valores. A diferenca e de ONDE o `::text`
mora na arvore de expressao, e ela apareceu em 8 CHECK que eu nunca toquei --
26 das 32 linhas do primeiro diff. Sem esta normalizacao eu teria lido 26
linhas de ruido como achado, ou pior: teria dito *"so olhei as 4 linhas que me
interessavam"*, que e escolher o que medir depois de ver o resultado.

⚠️ O `\\restrict`/`\\unrestrict` do pg_dump moderno traz um token ALEATORIO por
execucao: duas linhas que diferem sempre, inclusive comparando um banco consigo
mesmo.

⚠️ A forma canonica e feia de ler de proposito -- ela existe para o `diff`, nao
para gente. Quem quer ler a mudanca le o diff CRU; este serve para responder
*"sobrou alguma diferenca que nao e render?"*.

Uso:  norm.py < entrada.sql > saida.txt
"""
import re
import sys

TOKEN = re.compile(r"^\\(un)?restrict\s+\S+\s*$")


def norma(linha: str) -> str:
    if TOKEN.match(linha.strip()):
        return ""
    t = linha
    # 1. Os casts nao mudam o que o CHECK aceita; so onde o parser os pos.
    t = t.replace("::character varying", "").replace("::text", "")
    # 2. Espacos a um so, para o resto das regras serem previsiveis.
    t = re.sub(r"\s+", " ", t).strip()
    # 3. `(ARRAY[` e `ARRAY[` sao a mesma coisa depois do passo 1.
    t = t.replace("(ARRAY[", "ARRAY[")
    # 4. Espaco junto a pontuacao de lista nao significa nada.
    t = re.sub(r"\s*([\[\],])\s*", r"\1", t)
    # 5. O `[]` orfao que sobra da forma `(ARRAY[...])::text[]` depois do
    #    passo 1 -- e o fecha-parenteses que o acompanhava.
    t = t.replace("])[]", "]").replace("]()", "]").replace("][]", "]")
    # 6. Parenteses de agrupamento tambem nao mudam o significado aqui: as
    #    duas formas diferem exatamente neles.
    t = t.replace("(", "").replace(")", "")
    return t.strip()


if __name__ == "__main__":
    for linha in sys.stdin:
        print(norma(linha))
