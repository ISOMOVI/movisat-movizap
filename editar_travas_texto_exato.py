# -*- coding: utf-8 -*-
"""Quatro travas antigas achavam o botão por TEXTO EXATO — 25/11.

🚨 **NÃO É O CÓDIGO QUE ESTÁ ERRADO.** As ações do card viraram quadros com
nome **e** nota (aprovado por ele hoje), então `b.text()` deixou de ser
`"Ver prévia"` e passou a ser `"Ver prévia Mostra o que vai para o Procfy…"`.
Quatro travas comparavam com `===` e ficaram vermelhas num comportamento certo.

🚨 A LIÇÃO, que é a mesma do seletor por posição de 19/11: **igualdade de texto
inteiro é uma aposta sobre a forma**, não sobre o gesto. O que a trava quer
dizer é *"o botão cujo nome é X"* — então ela passa a medir o começo do texto
(`startsWith`) ou a presença dele (`includes`), e continua reprovando se o
botão desaparecer.

⚠️ O botão de CONFIRMAR dentro do diálogo de justificativa **continua com
`===`**: ele não é quadro, e afrouxar ali esconderia o dia em que ele virasse.
"""
import pathlib
import shutil
import sys
from datetime import datetime

RAIZ = pathlib.Path("/home/claude/movizap_painel/frontend/src")

TROCAS = {
    "aba2_padrao_e_servicos_1911.teste.js": [
        ("o contador do Preparar no Franck",
         """    expect(franck.findAll('button').map((b) => b.text())
      .find((x) => x.startsWith('Preparar os marcados')))
      .toBe('Preparar os marcados (1)')""",
         """    /* ⚠️ `toContain`, e não `toBe`: o quadro traz nome E nota (25/11), então
       o texto do botão continua COMEÇANDO pelo nome, mas não é só ele. */
    expect(franck.findAll('button').map((b) => b.text())
      .find((x) => x.startsWith('Preparar os marcados')))
      .toContain('Preparar os marcados (1)')"""),

        ("o contador do Preparar no Pedro",
         """    expect(pedro.findAll('button').map((b) => b.text())
      .find((x) => x.startsWith('Preparar os marcados')))
      .toBe('Preparar os marcados (0)')""",
         """    expect(pedro.findAll('button').map((b) => b.text())
      .find((x) => x.startsWith('Preparar os marcados')))
      .toContain('Preparar os marcados (0)')"""),

        ("o contador do Preparar na volta",
         """    expect(devolta.findAll('button').map((b) => b.text())
      .find((x) => x.startsWith('Preparar os marcados')))
      .toBe('Preparar os marcados (1)')""",
         """    expect(devolta.findAll('button').map((b) => b.text())
      .find((x) => x.startsWith('Preparar os marcados')))
      .toContain('Preparar os marcados (1)')"""),

        ("o gesto da prévia",
         """    await tela.findAll('button').find((b) => b.text() === 'Ver prévia')
      .trigger('click')""",
         """    await tela.findAll('button')
      .find((b) => b.text().startsWith('Ver prévia'))
      .trigger('click')"""),

        ("o gesto do DataScope",
         """    await tela.findAll('button').find((b) => b.text() === 'Ler DataScope')
      .trigger('click')""",
         """    await tela.findAll('button')
      .find((b) => b.text().startsWith('Ler DataScope'))
      .trigger('click')"""),
    ],
    "aba2_card_aberto_2311.teste.js": [
        ("o Excluir do card do lote",
         """    const excluir = dialogo(tela).findAll('button')
      .find((b) => b.text() === 'Excluir o card')""",
         """    /* ⚠️ `startsWith`: o Excluir virou quadro com nota (25/11). O botão de
       CONFIRMAR, no diálogo de justificativa, segue com `===` logo abaixo. */
    const excluir = dialogo(tela).findAll('button')
      .find((b) => b.text().startsWith('Excluir o card'))"""),

        ("a ausência do Excluir na coluna 1",
         """    expect(d.findAll('button').filter((b) => b.text() === 'Excluir o card'))
      .toHaveLength(0)""",
         """    expect(d.findAll('button')
      .filter((b) => b.text().includes('Excluir o card'))).toHaveLength(0)"""),

        ("a ausência do Remover na coluna 1",
         """    expect(d.findAll('button').filter((b) => b.text() === 'Remover'))
      .toHaveLength(0)""",
         """    expect(d.findAll('button')
      .filter((b) => b.text().includes('Remover'))).toHaveLength(0)"""),
    ],
}


def main() -> int:
    ruim = False
    for arquivo, pares in TROCAS.items():
        texto = (RAIZ / arquivo).read_text(encoding="utf-8")
        for rotulo, de, _para in pares:
            if texto.count(de) != 1:
                print(f"ABORTADO em {arquivo} / '{rotulo}': "
                      f"{texto.count(de)} ocorrencias.", file=sys.stderr)
                ruim = True
    if ruim:
        print("NADA FOI GRAVADO.", file=sys.stderr)
        return 1

    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    for arquivo, pares in TROCAS.items():
        alvo = RAIZ / arquivo
        texto = alvo.read_text(encoding="utf-8")
        novo = texto
        for _r, de, para in pares:
            novo = novo.replace(de, para, 1)
        shutil.copy2(alvo, alvo.with_suffix(alvo.suffix + f".bak_{marca}_texto_exato"))
        alvo.write_text(novo, encoding="utf-8")
        print(f"{arquivo}: {len(pares)} trocas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
