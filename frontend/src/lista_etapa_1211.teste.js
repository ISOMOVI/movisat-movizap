/**
 * @vitest-environment jsdom
 *
 * ===========================================================================
 * A LISTA DE ETAPAS NO CARD — substitui `barra_etapa_1111.teste.js`
 * ===========================================================================
 * 🔵 12/11, dele: *"pode ocultar essa barra ou transformá-la em lista, como no
 * OP"* e, escolhendo entre as duas opções, *"A"*.
 *
 * 🚨 O REGISTRO DA TROCA FICA AQUI, para ninguém reconstruir a barra achando
 * que a lista foi descuido. A barra de passos numerados nasceu em 11/11 de um
 * pedido dele e resolvia algo real: mostrava a SEQUÊNCIA, e com as 10 etapas
 * do Financeiro dava para ver em que ponto dela o card estava.
 * 📏 O custo medido foi maior: 177 caracteres de título contra ~860px de
 * diálogo deixam 6 ou 7 letras por passo, e ele leu "1. Nova s…" na tela.
 *
 * ⚠️ O QUE SE PERDE, e está dito: a sequência. A lista diz onde o card está e
 * para onde pode ir, não em que ponto da fila isso fica.
 * ⚠️ O QUE SE GANHA: nome inteiro de toda etapa, zero rolagem, e um controle
 * nativo que funciona em tela de toque — onde "parar o mouse" não existe e a
 * reticência não tinha como ser lida.
 *
 * As travas são as mesmas PERGUNTAS que a barra respondia, feitas à lista.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const estado = vi.hoisted(() => ({
  ficha: null,
  posts: [],
}))

vi.mock('./api/cliente.js', () => ({
  api: {
    get: () => Promise.resolve(estado.ficha),
    post: (caminho, corpo) => {
      estado.posts.push({ caminho, corpo })
      return Promise.resolve({})
    },
    put: () => Promise.resolve({}),
    del: () => Promise.resolve({}),
  },
  definirToken: () => {},
  temToken: () => true,
  quandoPerderSessao: () => {},
  relatarErroDeBotao: () => {},
  ErroDeApi: class ErroDeApi extends Error {},
}))

vi.mock('./estado/sessao.js', () => ({
  sessao: { nome: 'Iago', owner: true, telas: [] },
  codigosPermitidos: { value: new Set() },
  sair: () => {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ meta: {}, query: {}, params: {} }),
  useRouter: () => ({ push: () => {}, replace: () => {} }),
}))

import DialogoDeChamado from './componentes/DialogoDeChamado.vue'

/* As quatro etapas do Contratual, na ordem em que o quadro as devolve. */
const ETAPAS = [
  { id: 881, titulo: 'Nova solicitação' },
  { id: 885, titulo: 'Elaborar contrato' },
  { id: 886, titulo: 'Aguardando assinatura' },
  { id: 887, titulo: 'Assinado' },
]

function fichaCom(etapaAtual, desfecho = null, etapas = ETAPAS) {
  return {
    card: { id: 1500, etapa_id: etapaAtual, desfecho, desfecho_em: null },
    etapas,
    observacoes: [],
    historico: [],
    chamado: null,
  }
}

async function montar(ficha) {
  estado.ficha = ficha
  const tela = mount(DialogoDeChamado, {
    props: { card: { id: 1500, desfecho: ficha.card.desfecho,
                     desfecho_em: null, telefone: null } },
  })
  await flushPromises()
  await flushPromises()
  return tela
}

beforeEach(() => {
  estado.posts = []
  estado.ficha = null
})

describe('a lista de etapas está na faixa', () => {
  it('desenha UMA opção por etapa, na ordem, com o nome inteiro', async () => {
    const tela = await montar(fichaCom(885))
    const opcoes = tela.findAll('.faixa__select option')
    expect(opcoes).toHaveLength(ETAPAS.length)
    expect(opcoes.map((o) => o.text().trim()))
      .toEqual(ETAPAS.map((e) => e.titulo))
    /* 🚨 Nome INTEIRO é o ponto da troca: "Aguardando assinatura" não pode
       voltar cortado como vinha na barra. */
    expect(tela.text()).toContain('Aguardando assinatura')
  })

  it('a barra de passos de 11/11 NÃO está mais na árvore', async () => {
    const tela = await montar(fichaCom(885))
    expect(tela.find('.trilha').exists()).toBe(false)
    expect(tela.findAll('.trilha__passo')).toHaveLength(0)
  })

  it('a opção marcada é a etapa ATUAL do card', async () => {
    const tela = await montar(fichaCom(886))
    expect(tela.find('.faixa__select').element.value).toBe('886')
  })
})

describe('escolher na lista move de verdade', () => {
  it('chama a rota de mover com a etapa escolhida', async () => {
    const tela = await montar(fichaCom(885))
    const sel = tela.find('.faixa__select')
    sel.element.value = '886'
    await sel.trigger('change')
    await flushPromises()
    expect(estado.posts).toHaveLength(1)
    expect(estado.posts[0].caminho).toContain('/mover')
  })

  it('o destino é NÚMERO, nunca texto', async () => {
    /* 🚨 O valor de um `<option>` chega como STRING do DOM. Mandar "886" em
       vez de 886 o servidor recusa — a trava veio da barra para a lista
       porque o defeito é o mesmo em qualquer controle. */
    const tela = await montar(fichaCom(885))
    const sel = tela.find('.faixa__select')
    sel.element.value = '886'
    await sel.trigger('change')
    await flushPromises()
    const corpo = estado.posts[0].corpo || {}
    const destino = corpo.para_etapa ?? corpo.etapa_id ?? corpo.etapa
    expect(typeof destino).toBe('number')
    expect(destino).toBe(886)
  })
})

describe('quando NÃO se pode mover', () => {
  it('card finalizado não mostra a lista, mas DIZ a etapa', async () => {
    /* ⚠️ Reabrir primeiro é o gesto. E a faixa continua sendo medida: sumir
       com o nome da etapa deixaria o card sem dizer onde parou. */
    const tela = await montar(fichaCom(887, 'resolvido'))
    expect(tela.find('.faixa__select').exists()).toBe(false)
    expect(tela.text()).toContain('Assinado')
  })

  it('com uma etapa só, não há lista', async () => {
    const tela = await montar(fichaCom(881, null, [ETAPAS[0]]))
    expect(tela.find('.faixa__select').exists()).toBe(false)
    expect(tela.text()).toContain('Nova solicitação')
  })
})
