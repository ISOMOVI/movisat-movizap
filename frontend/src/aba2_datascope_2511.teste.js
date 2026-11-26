/*
 * @vitest-environment jsdom
 *
 * A CORRECAO DA SITUACAO NO DATASCOPE, na tela — passo 5, 25/11.
 *
 * Ele: *"sim, aprovado - que tem como base as etapas de validacao que permitem
 * o card do pagamento tecnico avancar"*; e, desde 18/11, *"abre modal antes de
 * escrever"*.
 *
 * O que estas travas prendem, e e o ponto todo: a chamada **escreve em sistema
 * de terceiro**, dispara os webhooks deles e **manda push para o tecnico**.
 * Entao:
 *   · nao se escreve sem passar por uma modal que DIZ isso em texto;
 *   · com o interruptor desligado a tela nao oferece o gesto, ela oferece
 *     LIGAR -- e o aviso fica a vista;
 *   · e o botao so existe na VALIDACAO.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

function quadro(coluna) {
  return {
    titulo: 'Serviço dos técnicos',
    desde: '2026-11-16',
    abas: [{ codigo_tela: 'PNL_1.6', titulo: 'Serviço dos técnicos' }],
    colunas: [
      { chave: 'movimentacao', nome: 'Movimentação',
        cards: coluna === 'movimentacao' ? [card('movimentacao')] : [] },
      { chave: 'preparacao', nome: 'Preparação', cards: [] },
      { chave: 'validacao', nome: 'Validação',
        cards: coluna === 'validacao' ? [card('validacao')] : [] },
      { chave: 'procfy', nome: 'Procfy', cards: [] },
      { chave: 'enviado', nome: 'Enviado', cards: [] },
    ],
  }
}

function card(coluna) {
  return {
    lote_id: 7, coluna: coluna || 'validacao', tecnico_id: 14262, tecnico_nome: 'Franck',
    pode_preparar: false, total_pagamento: 100, total_km: 0,
    artefatos: [{ id: 55, numero_os: 17120, valor_pagamento: 100, valor_km: 0,
                  cliente: 'CLIENTE A', data_os: '18/11/2026 09:00:00',
                  datascope_form_state: 'Finalizado', semaforo: 'verde' }],
  }
}

const estado = { coluna: 'validacao', ligada: false, pedidos: [] }

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (url) => {
      const u = String(url)
      if (u.includes('datascope-escrita')) return Promise.resolve({ ligada: estado.ligada })
      if (u.includes('config-procfy')) {
        return Promise.resolve({ procfy_categoria: '', procfy_conta_bancaria: '',
                                 procfy_modo_pagamento: '', procfy_centro_de_custo: '',
                                 procfy_tags: '' })
      }
      return Promise.resolve(quadro(estado.coluna))
    },
    post: (url, corpo) => { estado.pedidos.push([String(url), corpo]); return Promise.resolve({ ok: true }) },
    put: (url, corpo) => {
      estado.pedidos.push([String(url), corpo])
      if (String(url).includes('datascope-escrita')) estado.ligada = !!corpo.ligada
      return Promise.resolve({ ligada: estado.ligada })
    },
  },
  ErroDeApi: class extends Error {},
}))

vi.mock('./estado/sessao.js', () => ({
  sessao: { nome: 'Iago', owner: true, telas: [] },
  codigosPermitidos: { value: new Set() },
  sair: () => {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ meta: { codigo: 'PNL_1.6', aba: 'PNL_1.6' }, query: {}, params: {} }),
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

const Tela = (await import('./telas/PainelServicoDosTecnicos.vue')).default

let tela
async function abrir(coluna, ligada) {
  estado.coluna = coluna
  estado.ligada = ligada
  estado.pedidos.length = 0
  tela = mount(Tela, { attachTo: document.body })
  await flushPromises()
  await tela.find('.card__abrir').trigger('click')
  await flushPromises()
}
afterEach(() => tela && tela.unmount())

function botaoDoDatascope() {
  return tela.findAll('button').find((b) => /situação no datascope/i.test(b.text()))
}

describe('a correção no DataScope', () => {
  it('na Validação o gesto existe', async () => {
    await abrir('validacao', true)
    expect(botaoDoDatascope()).toBeTruthy()
  })

  it('na Movimentação o gesto NÃO existe', async () => {
    await abrir('movimentacao', true)
    expect(botaoDoDatascope()).toBeFalsy()
  })

  it('NÃO escreve sem modal, e a modal DIZ o que vai acontecer', async () => {
    await abrir('validacao', true)
    await botaoDoDatascope().trigger('click')
    await flushPromises()
    /* Nada foi escrito ainda: o clique abre a modal. */
    expect(estado.pedidos.some(([u]) => u.includes('datascope-aprovar'))).toBe(false)
    const texto = tela.text().toLowerCase()
    expect(texto).toContain('push')
    expect(texto).toContain('webhook')
  })

  it('confirmar manda para a rota certa', async () => {
    await abrir('validacao', true)
    await botaoDoDatascope().trigger('click')
    await flushPromises()
    const confirmar = tela.findAll('button')
      .find((b) => /^corrigir( a)? situação$/i.test(b.text().trim()))
    expect(confirmar, 'precisa haver botão de confirmar').toBeTruthy()
    await confirmar.trigger('click')
    await flushPromises()
    const pedido = estado.pedidos.find(([u]) => u.includes('datascope-aprovar'))
    expect(pedido, 'nenhum POST para datascope-aprovar').toBeTruthy()
    expect(pedido[0]).toContain('/datascope-aprovar/55')
  })

  it('DESLIGADO a tela oferece LIGAR, não corrigir', async () => {
    await abrir('validacao', false)
    await botaoDoDatascope().trigger('click')
    await flushPromises()
    const texto = tela.text().toLowerCase()
    expect(texto).toContain('desligada')
    const ligar = tela.findAll('button').find((b) => /ligar a escrita/i.test(b.text()))
    expect(ligar, 'precisa oferecer ligar').toBeTruthy()
    await ligar.trigger('click')
    await flushPromises()
    const pedido = estado.pedidos.find(([u]) => u.includes('datascope-escrita'))
    expect(pedido).toBeTruthy()
    expect(pedido[1]).toEqual({ ligada: true })
  })
})
