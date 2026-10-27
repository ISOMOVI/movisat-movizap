/**
 * @vitest-environment jsdom
 *
 * O calendário único (`CalendarioMes.vue`, 26/10).
 *
 * 🚨 ESTE COMPONENTE SERVE DUAS TELAS — o `ModalAgendar` e a `ATD_7.1`. Antes
 * de hoje a grade estava escrita duas vezes, e as cópias divergiam em quatro
 * medidas que ninguém escolheu (coluna 34px × 36px, altura 30px × 32px, gap
 * 3px × 4px, fundo `--superficie-2` × `--superficie`). Agora um defeito aqui
 * bate nas duas telas de uma vez, e é por isso que ele ganhou teste próprio.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { URL as UrlDoNode, fileURLToPath } from 'node:url'

import CalendarioMes from './componentes/CalendarioMes.vue'

/* ⚠️ O `URL` do jsdom NÃO é o do Node, e nem o `readFileSync` nem o
   `fileURLToPath` aceitam aquele objeto. Os testes `eventos_1510` e
   `ficha_1510` leem fonte do mesmo jeito e funcionam porque rodam em
   `@vitest-environment node` -- este monta componente, então precisa de jsdom
   e tem de pedir o `URL` do Node pelo nome. */
const FONTE = readFileSync(
  fileURLToPath(new UrlDoNode('./componentes/CalendarioMes.vue', import.meta.url)), 'utf8')

/* Um mês conhecido, para a conta dos dias não depender do dia de hoje:
   outubro de 2026 tem 31 dias e começa numa quinta-feira (coluna 4). */
const MES = '2026-10-15'

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-26T10:00:00-03:00'))
})
afterEach(() => vi.useRealTimers())

function montar(props = {}) {
  return mount(CalendarioMes, { props: { mesDe: MES, ...props } })
}

describe('o calendário único', () => {
  it('desenha os dias do mês, e só eles', () => {
    const tela = montar()
    expect(tela.findAll('.cal__dia')).toHaveLength(31)   // outubro
  })

  it('põe vazios antes do dia 1, para o dia cair na coluna certa', () => {
    /* 01/10/2026 é quinta-feira: com D-S-T-Q-Q-S-S, são 4 vazios antes. Sem
       eles o mês inteiro sai deslocado de coluna, que é erro de leitura e não
       de dado. */
    const tela = montar()
    expect(tela.findAll('.cal__vago')).toHaveLength(4)
    expect(tela.findAll('.cal__semana')).toHaveLength(7)
  })

  it('avisa qual dia foi clicado, em AAAA-MM-DD', () => {
    const tela = montar()
    tela.findAll('.cal__dia')[9].trigger('click')   // dia 10
    expect(tela.emitted('escolher')[0]).toEqual(['2026-10-10'])
  })

  it('marca o dia escolhido e o de hoje, que são coisas diferentes', () => {
    const tela = montar({ selecionado: '2026-10-10' })
    const dias = tela.findAll('.cal__dia')
    expect(dias[9].classes()).toContain('cal__dia--ativo')
    expect(dias[25].classes()).toContain('cal__dia--hoje')   // 26/10
    expect(dias[25].classes()).not.toContain('cal__dia--ativo')
  })

  it('só marca dia passado quando a tela pede', () => {
    /* ⚠️ MARCAR NÃO É BARRAR: remarcar serviço que já aconteceu é caso real.
       E a `ATD_7.1` não pede a marca, porque lá o mês é só navegação. */
    expect(montar().findAll('.cal__dia--passado')).toHaveLength(0)
    const comMarca = montar({ marcarPassado: true })
    expect(comMarca.findAll('.cal__dia--passado').length).toBeGreaterThan(20)
    /* E nenhum dia fica desabilitado: a tela avisa, não impede. */
    expect(comMarca.findAll('.cal__dia[disabled]')).toHaveLength(0)
  })

  it('andar de mês troca o rótulo e recalcula os dias', () => {
    const tela = montar()
    expect(tela.find('.cal__rotulo').text().toLowerCase()).toContain('outubro')
    tela.findAll('button')[0].trigger('click')   // mês anterior
    return tela.vm.$nextTick().then(() => {
      expect(tela.find('.cal__rotulo').text().toLowerCase()).toContain('setembro')
      expect(tela.findAll('.cal__dia')).toHaveLength(30)   // setembro
    })
  })

  it('o mês abre em `mesDe`, não sempre no de hoje', () => {
    const tela = mount(CalendarioMes, { props: { mesDe: '2026-12-03' } })
    expect(tela.find('.cal__rotulo').text().toLowerCase()).toContain('dezembro')
  })

  it('a nota da tela aparece junto da grade de que ela fala', () => {
    const tela = mount(CalendarioMes, {
      props: { mesDe: MES },
      slots: { nota: '<p class="minha-nota">o que esta tela precisa dizer</p>' },
    })
    expect(tela.find('.minha-nota').exists()).toBe(true)
  })

  /* 🚨 O que o jsdom não mede: ele não calcula CSS de verdade, então "o toque
     tem 44px" não se prova montando. O que se prova é que o componente usa o
     TOKEN e não escreve medida na mão -- que é a regra do padrão visual, e é
     exatamente o que as duas cópias antigas violavam. */
  it('o toque sai do token, e não há altura de px escrita na mão', () => {
    const estilo = FONTE.split('<style scoped>')[1]
    expect(estilo).toContain('var(--altura-toque)')
    /* `height: 30px` / `32px` / `repeat(7, 34px)` eram as cópias antigas. */
    expect(estilo).not.toMatch(/height:\s*\d+px/)
    expect(estilo).not.toMatch(/repeat\(7,\s*\d+px\)/)
  })

  it('não sabe nada de agendamento: nenhuma marca de "tem serviço"', () => {
    /* ⚠️ A justificativa é da `ATD_7.1` e continua valendo: o que está
       carregado é a semana da âncora, então o mês saberia de uns dias e não de
       outros -- e um mês com pontos em três dias afirmaria que nos outros não
       há nada. */
    /* ⚠️ Mede CÓDIGO, não vocabulário: a palavra "agendamento" aparece nos
       comentários que explicam o componente, e a primeira versão deste teste
       reprovou no próprio texto que diz por que ele não sabe de agendamento.
       Mesmo erro que o guarda-corpo do `window.prompt` cometeu hoje. */
    expect(FONTE).not.toMatch(/api\.(get|post|put|del)/)
    expect(FONTE).not.toMatch(/fetch\(/)
    const template = FONTE.split('<template>')[1].split('</template>')[0]
    /* Nenhuma marca de "tem serviço" na grade -- ver a justificativa acima.
       ⚠️ O padrão era /marca|ponto/ e casava com a prop `marcarPassado`, que é
       legítima: terceira vez hoje que um padrão largo reprova o certo. */
    expect(template).not.toMatch(/servico|serviço/i)
  })
})
