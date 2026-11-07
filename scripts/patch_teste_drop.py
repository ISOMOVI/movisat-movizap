# -*- coding: utf-8 -*-
"""O teste do `drop` era VAZIO: conserta para ser comportamental (06/11).

🚨 `expect(html()).not.toContain('drop')` nunca podia reprovar: no Vue, `@drop`
compila para um OUVINTE, nao para um atributo -- o HTML renderizado jamais
conteria a palavra. O teste passava com e sem o defeito, e a forja de hoje o
denunciou (a ancora "nao bateu" porque eu nem precisava mexer no template para
ele continuar verde).

⚠️ Achado forjando os defeitos, nao lendo o codigo: foi a terceira forja do dia
que mostrou. `fonte nao e comportamento`.
"""
import pathlib
import sys

P = pathlib.Path("/home/claude/movizap_painel/frontend/src/rolagem_0611.teste.js")
t = P.read_text(encoding="utf-8")

if "soltar o card nela e um NAO-EVENTO" in t:
    sys.exit("ja aplicado")

VELHO = """  it('🚨 a faixa NÃO tem `drop` — soltar o card nela não o engole', () => {
    const tela = mount(RolagemDaBorda, { props: { rolo: roloFalso() } })
    const html = tela.find('.borda__faixa--dir').html()
    expect(html).not.toContain('drop')
  })"""

NOVO = """  it('🚨 soltar o card na faixa e um NAO-EVENTO: ela ignora o `drop`', () => {
    /* ⚠️ A PRIMEIRA VERSÃO DESTE TESTE ERA VAZIA, e a forja de hoje a
       denunciou: eu asseverava `expect(html()).not.toContain('drop')`, e no
       Vue `@drop` compila para um OUVINTE, não para um atributo -- o HTML
       renderizado nunca conteria a palavra. O teste passava com e sem o
       defeito.

       🚨 A faixa chama `preventDefault` no `dragover`, e isso a torna uma área
       que ACEITA soltar -- é o preço de o arraste poder rolar. O que ela não
       pode é TRATAR o `drop`: sem tratador, soltar ali não move card nenhum, o
       `dragend` do painel devolve o card, e ele fica onde estava.

       ⚠️ O QUE ESTA TRAVA NÃO PROVA: que a faixa está FORA das colunas. Se ela
       fosse filha de uma `.coluna`, o `drop` subiria por borbulhamento até o
       `soltarNaColuna` daquela coluna e o card mudaria de lugar sozinho. Isso é
       estrutura do `PainelOperacao.vue`, e está no teste de integração. */
    const rolo = roloFalso({ em: 1000 })
    const tela = mount(RolagemDaBorda, { props: { rolo } })
    const faixa = tela.find('.borda__faixa--dir')
    expect(() => faixa.trigger('drop')).not.toThrow()
    vi.advanceTimersByTime(500)
    expect(rolo.scrollLeft).toBe(1000)
  })"""

if t.count(VELHO) != 1:
    sys.exit(f"ancora apareceu {t.count(VELHO)}x")

P.write_text(t.replace(VELHO, NOVO), encoding="utf-8")
print("rolagem_0611.teste.js: o teste do drop virou comportamental")
