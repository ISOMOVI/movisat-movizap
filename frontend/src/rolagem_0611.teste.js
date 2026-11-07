/**
 * @vitest-environment jsdom
 *
 * A ROLAGEM HORIZONTAL DO QUADRO — a barra no alto e a faixa da borda (06/11).
 *
 * 🔵 Ele: *"sabe quando deixamos o mouse a direita e esquerda sobre 'botões' e a
 * tela se desloca suavemente para o lado? precisamos disso nos paineis, pois o
 * scroll ficou la embaixo"* · *"pode ser uma barra fina tbm, o mouse ficando
 * parado ou o scrol ficando na tela tbm resolve"* · *"Ok go"* · *"pode ligar a
 * rolagem horizontal via mouse sobreposto"*.
 *
 * 🚨 **AS CINCO REGRAS QUE ESTE ARQUIVO PRENDE:**
 *
 * 1. **NADA É DESENHADO SE NÃO HÁ PARA ONDE ROLAR.** `scrollWidth <=
 *    clientWidth` e nem a barra nem as faixas existem. Controle morto é o
 *    precedente do `ModalAgendar`.
 * 2. **CADA LADO DESAPARECE NO SEU FIM** — a faixa esquerda em `scrollLeft 0`,
 *    a direita no fim do curso.
 * 3. 🚨 **ARRASTE ROLA, e por `dragover`.** Durante um arraste HTML5 o
 *    navegador **não** emite `mousemove`. Uma versão que só escutasse o mouse
 *    funcionaria no uso normal e falharia no caso que mais importa — arrastar um
 *    card para uma coluna fora da tela, que hoje é impossível.
 * 4. 🚨 **A FAIXA NÃO RECEBE `drop`.** Soltar o card nela tem de devolvê-lo,
 *    não sumir com ele.
 * 5. **A PAUSA ANTES DE ROLAR COM O PONTEIRO** (*"o mouse ficando parado"*): o
 *    menu fica à esquerda do conteúdo, e todo caminho até ele cruza a faixa
 *    esquerda. Sem a pausa, ir ao menu rolaria o quadro. ⚠️ No arraste **não
 *    há pausa**.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'

import BarraDeRolagem from './componentes/BarraDeRolagem.vue'
import RolagemDaBorda from './componentes/RolagemDaBorda.vue'

/* Um rolo de mentira com as três medidas que importam. 🚨 `scrollWidth` e
   `clientWidth` não são escritos em jsdom, então o dublê é um objeto com as
   mesmas chaves — e é honesto: os dois componentes só leem essas três e
   escrevem `scrollLeft`. */
function roloFalso({ conteudo = 6500, visivel = 1650, em = 0 } = {}) {
  /* 🚨 O DUBLÊ LIMITA o `scrollLeft`, porque elemento de verdade limita. Um
     objeto literal aceitaria `scrollLeft = 99999` e o teste "para no fim"
     mediria um número que o navegador nunca produz. ⚠️ Dublê que não espelha a
     plataforma faz todo o arquivo medir uma ficção -- é a regra de
     `duplo se põe na borda`, e foi este teste que a cobrou. */
  let em_ = em
  const teto = Math.max(0, conteudo - visivel)
  return {
    scrollWidth: conteudo,
    clientWidth: visivel,
    get scrollLeft() { return em_ },
    set scrollLeft(v) { em_ = Math.max(0, Math.min(teto, v)) },
    firstElementChild: null,
    addEventListener() {},
    removeEventListener() {},
    getBoundingClientRect: () => ({
      left: 0, right: visivel, width: visivel, top: 0, bottom: 800, height: 800,
    }),
  }
}

/* A caixa da faixa, para o cálculo da força. */
const caixaDaFaixa = (esq, dir) => ({
  left: esq, right: dir, width: dir - esq, top: 0, bottom: 800, height: 800,
})

function eventoNaFaixa(x, esq, dir) {
  return {
    clientX: x,
    preventDefault() {},
    currentTarget: { getBoundingClientRect: () => caixaDaFaixa(esq, dir) },
  }
}

beforeEach(() => {
  vi.useFakeTimers()
  // rAF determinístico: cada quadro avança 16ms.
  let agora = 0
  vi.stubGlobal('requestAnimationFrame', (fn) => {
    agora += 16
    return setTimeout(() => fn(agora), 0)
  })
  vi.stubGlobal('cancelAnimationFrame', (id) => clearTimeout(id))
  vi.stubGlobal('ResizeObserver', class {
    observe() {}
    disconnect() {}
  })
  window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('a barra grudada no alto', () => {
  it('🚨 não é desenhada quando o quadro cabe na tela', () => {
    const tela = mount(BarraDeRolagem, {
      props: { rolo: roloFalso({ conteudo: 1200, visivel: 1650 }) },
    })
    expect(tela.find('.barrarolo').exists()).toBe(false)
  })

  it('é desenhada quando transborda, com `role="scrollbar"`', () => {
    const tela = mount(BarraDeRolagem, { props: { rolo: roloFalso() } })
    const trilho = tela.find('[role="scrollbar"]')
    expect(trilho.exists()).toBe(true)
    expect(trilho.attributes('aria-orientation')).toBe('horizontal')
    expect(trilho.attributes('aria-valuenow')).toBe('0')
  })

  it('o polegar tem piso de 8% — proporcional seria impossível de pegar', () => {
    // 1650 de 6500 = 25%; mas num quadro muito largo o proporcional sumiria.
    const tela = mount(BarraDeRolagem, {
      props: { rolo: roloFalso({ conteudo: 60000, visivel: 1650 }) },
    })
    const largura = tela.find('.barrarolo__polegar').element.style.width
    expect(parseFloat(largura)).toBeGreaterThanOrEqual(8)
  })

  it('o polegar nunca passa da borda direita', () => {
    const rolo = roloFalso({ em: 6500 - 1650 })
    const tela = mount(BarraDeRolagem, { props: { rolo } })
    const el = tela.find('.barrarolo__polegar').element
    const esq = parseFloat(el.style.left)
    const larg = parseFloat(el.style.width)
    expect(esq + larg).toBeLessThanOrEqual(100.01)
  })

  it('a seta do teclado anda UMA coluna', () => {
    const rolo = roloFalso()
    const tela = mount(BarraDeRolagem, { props: { rolo } })
    tela.find('[role="scrollbar"]').trigger('keydown', { key: 'ArrowRight' })
    expect(rolo.scrollLeft).toBe(376)
  })

  it('`End` vai ao fim e `Home` volta ao começo, sem passar do curso', () => {
    const rolo = roloFalso()
    const tela = mount(BarraDeRolagem, { props: { rolo } })
    const trilho = tela.find('[role="scrollbar"]')
    trilho.trigger('keydown', { key: 'End' })
    expect(rolo.scrollLeft).toBe(6500 - 1650)
    trilho.trigger('keydown', { key: 'Home' })
    expect(rolo.scrollLeft).toBe(0)
  })

  it('tecla que não é de rolagem não mexe no quadro', () => {
    const rolo = roloFalso({ em: 500 })
    const tela = mount(BarraDeRolagem, { props: { rolo } })
    tela.find('[role="scrollbar"]').trigger('keydown', { key: 'a' })
    expect(rolo.scrollLeft).toBe(500)
  })
})

describe('a faixa da borda', () => {
  it('🚨 não existe quando o quadro cabe na tela', () => {
    const tela = mount(RolagemDaBorda, {
      props: { rolo: roloFalso({ conteudo: 1200, visivel: 1650 }) },
    })
    expect(tela.find('.borda').exists()).toBe(false)
  })

  it('no começo só a da DIREITA aparece', () => {
    const tela = mount(RolagemDaBorda, { props: { rolo: roloFalso({ em: 0 }) } })
    expect(tela.find('.borda__faixa--esq').exists()).toBe(false)
    expect(tela.find('.borda__faixa--dir').exists()).toBe(true)
  })

  it('no fim só a da ESQUERDA aparece', () => {
    const tela = mount(RolagemDaBorda, {
      props: { rolo: roloFalso({ em: 6500 - 1650 }) },
    })
    expect(tela.find('.borda__faixa--esq').exists()).toBe(true)
    expect(tela.find('.borda__faixa--dir').exists()).toBe(false)
  })

  it('no meio as duas aparecem', () => {
    const tela = mount(RolagemDaBorda, {
      props: { rolo: roloFalso({ em: 2000 }) },
    })
    expect(tela.find('.borda__faixa--esq').exists()).toBe(true)
    expect(tela.find('.borda__faixa--dir').exists()).toBe(true)
  })

  it('🚨 o ponteiro sobreposto rola — DEPOIS da pausa, nunca antes', () => {
    const rolo = roloFalso()
    const tela = mount(RolagemDaBorda, { props: { rolo } })
    const faixa = tela.find('.borda__faixa--dir')
    faixa.element.getBoundingClientRect = () => caixaDaFaixa(1602, 1650)
    faixa.trigger('pointerenter', { clientX: 1620 })

    // ⚠️ ANTES da pausa, nada se moveu: é o que impede rolagem acidental de
    // quem só está passando a caminho do menu.
    vi.advanceTimersByTime(100)
    expect(rolo.scrollLeft).toBe(0)

    vi.advanceTimersByTime(60 + 64)
    expect(rolo.scrollLeft).toBeGreaterThan(0)
  })

  it('sair da faixa PARA a rolagem', () => {
    const rolo = roloFalso()
    const tela = mount(RolagemDaBorda, { props: { rolo } })
    const faixa = tela.find('.borda__faixa--dir')
    faixa.trigger('pointerenter', { clientX: 1620 })
    vi.advanceTimersByTime(300)
    const andou = rolo.scrollLeft
    expect(andou).toBeGreaterThan(0)
    faixa.trigger('pointerleave')
    vi.advanceTimersByTime(500)
    expect(rolo.scrollLeft).toBe(andou)
  })

  it('🚨 ARRASTE rola, por `dragover`, e SEM pausa', () => {
    // A trava mais importante: o arraste HTML5 não emite `mousemove`. Uma
    // versão que só escutasse o mouse passaria em todos os testes acima e
    // falharia exatamente aqui.
    const rolo = roloFalso()
    const tela = mount(RolagemDaBorda, { props: { rolo } })
    const faixa = tela.find('.borda__faixa--dir')
    faixa.element.getBoundingClientRect = () => caixaDaFaixa(1602, 1650)
    faixa.trigger('dragover', { clientX: 1620 })
    // Sem pausa: o primeiro quadro de animação já anda.
    vi.advanceTimersByTime(48)
    expect(rolo.scrollLeft).toBeGreaterThan(0)
  })

  it('🚨 soltar o card na faixa e um NAO-EVENTO: ela ignora o `drop`', () => {
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
  })

  it('o clique anda uma coluna, sem esperar pausa', () => {
    const rolo = roloFalso()
    const tela = mount(RolagemDaBorda, { props: { rolo } })
    tela.find('.borda__faixa--dir').trigger('pointerdown', { clientX: 1620 })
    expect(rolo.scrollLeft).toBe(376)
  })

  it('para sozinha ao chegar no fim, e a faixa desaparece', async () => {
    const rolo = roloFalso({ conteudo: 2000, visivel: 1650, em: 300 })
    const tela = mount(RolagemDaBorda, { props: { rolo } })
    const faixa = tela.find('.borda__faixa--dir')
    faixa.element.getBoundingClientRect = () => caixaDaFaixa(1602, 1650)
    faixa.trigger('pointerenter', { clientX: 1649 })
    vi.advanceTimersByTime(3000)
    expect(rolo.scrollLeft).toBe(350)
    await tela.vm.$nextTick()
    expect(tela.find('.borda__faixa--dir').exists()).toBe(false)
  })

  it('as duas faixas têm rótulo para leitor de tela', () => {
    const tela = mount(RolagemDaBorda, {
      props: { rolo: roloFalso({ em: 2000 }), rotulo: 'quadro' },
    })
    expect(tela.find('.borda__faixa--esq').attributes('aria-label'))
      .toBe('Rolar o quadro para a esquerda')
    expect(tela.find('.borda__faixa--dir').attributes('aria-label'))
      .toBe('Rolar o quadro para a direita')
  })

  it('com `prefers-reduced-motion` o ponteiro PULA, e nada rola sozinho', () => {
    // ⚠️ Rolagem contínua é o que essa preferência existe para evitar.
    window.matchMedia = (q) => ({
      matches: q.includes('reduced-motion'),
      addEventListener() {}, removeEventListener() {},
    })
    const rolo = roloFalso()
    const tela = mount(RolagemDaBorda, { props: { rolo } })
    tela.find('.borda__faixa--dir').trigger('pointerenter', { clientX: 1620 })
    expect(rolo.scrollLeft).toBe(376)
    vi.advanceTimersByTime(2000)
    expect(rolo.scrollLeft).toBe(376)
  })
})
