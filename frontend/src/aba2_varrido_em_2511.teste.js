/**
 * @vitest-environment jsdom
 *
 * A LINHA QUE DIZ QUANDO A ABA 2 OLHOU — 25/11 (tarefa 1.4, `M12`).
 *
 * 🚨 **O DEFEITO.** A tela diz *"serviço a partir de 16/11/2026"* e não diz
 * **quando** varreu. Com a varredura virando cron das 05:10, um quadro de seis
 * dias atrás tem a mesma cara de um varrido hoje — e a docstring da
 * `varrer_servicos` já afirmava *"a automática roda de madrugada"* sem que ela
 * existisse. Tela que mente é defeito (`M12`), e o conserto é dizer a hora.
 *
 * 🚨 **GESTO, NÃO FUNÇÃO** (`M17`, linha 2): em 19/11 a lógica do filtro de
 * data estava correta e o defeito estava no `<input type="date">`. Então aqui
 * se lê o **TEXTO que a tela mostra**, com o quadro que a ponte devolve.
 *
 * ⚠️ **SEM HORA FIXA E SEM FUSO CHUTADO.** O carimbo é ISO em UTC e a tela
 * mostra no fuso de quem olha; o esperado é montado do MESMO `Date`, nunca de
 * uma string escrita à mão — foi fuso que deixou a suíte vermelha em 11/11.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = vi.hoisted(() => ({ quadro: null, vezes: 0 }))

vi.mock('./api/cliente.js', () => {
  class ErroDeApi extends Error {}
  return {
    api: {
      get: () => { estado.vezes += 1; return Promise.resolve(estado.quadro) },
      post: () => Promise.resolve({ ok: true }),
      put: () => Promise.resolve({}),
      del: () => Promise.resolve({}),
    },
    definirToken: () => {},
    temToken: () => true,
    quandoPerderSessao: () => {},
    relatarErroDeBotao: () => {},
    ErroDeApi,
  }
})

vi.mock('./estado/sessao.js', () => ({
  sessao: { nome: 'Iago', owner: true, telas: [] },
  codigosPermitidos: { value: new Set() },
  sair: () => {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ meta: { codigo: 'PNL_1.6', aba: 'PNL_1.6' },
                     query: {}, params: {} }),
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

import PainelServicoDosTecnicos from './telas/PainelServicoDosTecnicos.vue'

function quadro(extra = {}) {
  return {
    painel: 'financeiro', aba: 'PNL_1.6', titulo: 'Serviço dos técnicos',
    abas: [{ codigo_tela: 'PNL_1.6', titulo: 'Serviço dos técnicos' }],
    artefatos: 11, desde: '2026-11-16', escondidos_pela_data: 77,
    colunas: [
      { chave: 'movimentacao', titulo: 'Movimentação', total: 0, cards: [] },
      { chave: 'preparacao', titulo: 'Preparação', total: 0, cards: [] },
      { chave: 'validacao', titulo: 'Validação', total: 0, cards: [] },
      { chave: 'procfy', titulo: 'Procfy', total: 0, cards: [] },
      { chave: 'enviado', titulo: 'Pagamento enviado', total: 0, cards: [] },
    ],
    ...extra,
  }
}

async function abrirATela(extra) {
  estado.quadro = quadro(extra)
  const tela = mount(PainelServicoDosTecnicos, { attachTo: document.body })
  await flushPromises()
  await flushPromises()
  return tela
}

/* A linha do corte, achada pelo TEXTO — não por seletor inventado. */
const linhaDoCorte = (tela) =>
  tela.findAll('p').find((p) => p.text().includes('serviço a partir de'))

/* O esperado sai do mesmo `Date` que a tela recebe: nada de fuso chutado. */
const horaLocal = (iso) => {
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2, '0')}:`
    + `${String(d.getMinutes()).padStart(2, '0')}`
}
const diaLocal = (iso) => {
  const d = new Date(iso)
  return `${String(d.getDate()).padStart(2, '0')}/`
    + `${String(d.getMonth() + 1).padStart(2, '0')}`
}

beforeEach(() => { estado.vezes = 0 })

describe('a tela diz quando varreu', () => {
  it('mostra a hora do carimbo de hoje, ao lado do corte', async () => {
    const agora = new Date(Date.now() - 90 * 60 * 1000).toISOString()
    const tela = await abrirATela({ varrido_em: agora })
    const linha = linhaDoCorte(tela)
    expect(linha, 'a linha do corte tem de existir').toBeTruthy()
    const texto = linha.text()
    expect(texto).toContain('varrido')
    expect(texto).toContain('hoje')
    expect(texto).toContain(horaLocal(agora))
  })

  it('carimbo de outro dia vem com a data, e não com "hoje"', async () => {
    const antes = new Date(Date.now() - 6 * 24 * 60 * 60 * 1000).toISOString()
    const tela = await abrirATela({ varrido_em: antes })
    const texto = linhaDoCorte(tela).text()
    expect(texto).toContain('varrido')
    expect(texto).toContain(diaLocal(antes))
    expect(texto).toContain(horaLocal(antes))
    expect(texto).not.toContain('hoje')
  })

  it('nunca varrido não inventa hora nenhuma', async () => {
    /* ⚠️ A linha do corte continua; o que não aparece é a parte da hora. É a
       régua do campo: nunca varrido não é erro, é não ter o que afirmar. */
    const tela = await abrirATela({ varrido_em: '' })
    const texto = linhaDoCorte(tela).text()
    expect(texto).toContain('serviço a partir de')
    expect(texto).not.toContain('varrido')
  })

  it('carimbo torto não derruba a tela nem escreve "Invalid Date"', async () => {
    const tela = await abrirATela({ varrido_em: 'ontem de manhã' })
    const texto = linhaDoCorte(tela).text()
    expect(texto).toContain('serviço a partir de')
    expect(texto).not.toContain('Invalid')
    expect(texto).not.toContain('NaN')
  })
})
