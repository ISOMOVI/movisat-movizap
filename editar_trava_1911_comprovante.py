"""A trava de 19/11 do comprovante escolhia o campo POR POSICAO -- 25/11.

Ela fazia `findAll('.modal__caixa--curta input')[0]`, e o primeiro input do
modal passou a ser o `<input type="file">` do anexo: o jsdom recusa com
`InvalidStateError: This input element accepts a filename`.

🚨 NAO E A TRAVA QUE ESTA ERRADA NEM O CODIGO: e a POSICAO como seletor.
Indice de lista nao diz o que se quer; `input.campo` diz. (A classe `campo` e
dos tres campos de texto; o input de arquivo tem classe propria.)
Mesma licao do `M13`: seletor e suposicao minha sobre onde a coisa esta.
"""
import pathlib, shutil, sys
from datetime import datetime

ALVO = pathlib.Path("/home/claude/movizap_painel/frontend/src/"
                    "aba2_padrao_e_servicos_1911.teste.js")
t = ALVO.read_text(encoding="utf-8")

de1 = """    const campos = tela.findAll('.modal__caixa--curta input')
    await campos[0].setValue('recibo_franck_1811.pdf')"""
para1 = """    /* 🚨 `input.campo`, e NAO indice: o primeiro input do modal passou a ser
       o `<input type="file">` do anexo (25/11), que o jsdom recusa receber
       valor. A classe diz o que se quer; a posicao era suposicao. */
    const campos = tela.findAll('.modal__caixa--curta input.campo')
    await campos[0].setValue('recibo_franck_1811.pdf')"""

de2 = """    const depois = tela.findAll('.modal__caixa--curta input')
    expect(depois.length).toBe(3)"""
para2 = """    const depois = tela.findAll('.modal__caixa--curta input.campo')
    expect(depois.length).toBe(3)"""

for de in (de1, de2):
    if t.count(de) != 1:
        print(f"ABORTADO: ancora {t.count(de)}x", file=sys.stderr)
        raise SystemExit(1)
novo = t.replace(de1, para1, 1).replace(de2, para2, 1)
marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
shutil.copy2(ALVO, ALVO.with_suffix(ALVO.suffix + f".bak_{marca}_seletor_por_classe"))
ALVO.write_text(novo, encoding="utf-8")
print("trava de 19/11 passa a achar o campo pela classe, nao pela posicao")
