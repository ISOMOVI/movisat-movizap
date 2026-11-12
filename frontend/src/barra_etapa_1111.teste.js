/**
 * @vitest-environment jsdom
 *
 * A BARRA INTERNA DE MUDAR ETAPA NO CARD (11/11).
 *
 * 🔵 **Pedido dele**, no bloco colado em 11/11: *"a barra interna de mudar
 * etapa nos cards dessas etapas"*.
 *
 * 📏 **O que existia, medido:** um `<select>` de 190 px dentro da faixa do
 * card. Ele movia — então isto não é defeito, é o pedido: com as **10 etapas
 * do Financeiro** a sequência ficava escondida atrás de um clique, e não se
 * via onde o card está nela.
 *
 * 🚨 **A TRAVA OLHA A ESTRUTURA, NÃO O GESTO.** O jsdom não faz layout: uma
 * barra que rola sem rolar, ou com `pointer-events: none`, passaria verde —
 * foi exatamente o defeito do card inerte de 09/11, onde 22 travas ficaram
 * verdes com a tela morta. O que se prova aqui é: os passos estão na árvore,
 * a etapa atual **não é botão**, e clicar num passo chama a rota de mover
 * com aquele `etapa_id`.
 *
 * 🚨 **A ETAPA ATUAL NÃO PODE SER DISTINGUIDA SÓ PELA COR** — régua da casa.
 * Ela é `<strong>`, os outros são `<button>`: a diferença é estrutural, chega
 * ao leitor de tela pelo `aria-current` e sobrevive a tema e a daltonismo.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
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

/* As cinco etapas do Contratual, na ordem em que o quadro as devolve. */
const ETAPAS = [
  { id: 881, titulo: 'Nova solicitação' },
  { id: 885, titulo: 'Elaborar contrato' },
  { id: 886, titulo: 'Aguardando assinatura' },
  { id: 887, titulo: 'Assinado' },
]

function fichaCom(etapaAtual, desfecho = null) {
  return {
    card: { id: 1500, etapa_id: etapaAtual, desfecho, desfecho_em: null },
    etapas: ETAPAS,
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

describe('a barra de etapas esta na arvore', () => {
  it('desenha UM passo por etapa, na ordem, numerado', async () => {
    const tela = await montar(fichaCom(885))
    const passos = tela.findAll('.trilha__passo')
    expect(passos.length).toBe(ETAPAS.length)
    expect(passos.map((p) => p.text())).toEqual([
      '1. Nova solicitação', '2. Elaborar contrato',
      '3. Aguardando assinatura', '4. Assinado',
    ])
  })

  it('a etapa atual NAO e botao, e as outras sao', async () => {
    /* 🚨 A trava que impede a volta da distinção só por cor. */
    const tela = await montar(fichaCom(885))
    const atual = tela.find('.trilha__passo--atual')
    expect(atual.exists()).toBe(true)
    expect(atual.element.tagName).toBe('STRONG')
    expect(atual.attributes('aria-current')).toBe('step')
    expect(atual.text()).toBe('2. Elaborar contrato')
    /* Os outros três são botões, e nenhum deles se diz o atual. */
    const botoes = tela.findAll('button.trilha__passo')
    expect(botoes.length).toBe(ETAPAS.length - 1)
    for (const b of botoes) {
      expect(b.classes()).not.toContain('trilha__passo--atual')
      expect(b.attributes('aria-current')).toBeUndefined()
    }
  })

  it('o select de antes SAIU: um controle so para o mesmo ato', async () => {
    /* ⚠️ Dois controles para mover o mesmo card deixariam o estado ambíguo —
       e o que a faixa mostra agora é MEDIDA, não controle. */
    const tela = await montar(fichaCom(881))
    expect(tela.find('.faixa__select').exists()).toBe(false)
    expect(tela.find('.faixa__medida--etapa').text()).toContain(
      'Nova solicitação')
  })
})

describe('clicar num passo move de verdade', () => {
  it('chama a rota de mover com o etapa_id DAQUELE passo', async () => {
    const tela = await montar(fichaCom(881))
    const botoes = tela.findAll('button.trilha__passo')
    /* O primeiro botão é a 2ª etapa — a 1ª é a atual e não é botão. */
    await botoes[0].trigger('click')
    await flushPromises()
    const mover = estado.posts.filter((p) => p.caminho.endsWith('/mover'))
    expect(mover.length).toBe(1)
    expect(mover[0].caminho).toBe('/api/paineis/operacao/chamado/1500/mover')
    expect(mover[0].corpo).toEqual({ para_etapa: 885 })
  })

  it('o `para_etapa` e NUMERO, nunca texto', async () => {
    /* 🚨 O `<select>` entregava `event.target.value`, que é string, e o
       `mover` o convertia. A barra entrega o id direto — se alguém voltar a
       passar texto, a rota recebe `"885"` e o backend recusa. */
    const tela = await montar(fichaCom(881))
    await tela.findAll('button.trilha__passo')[0].trigger('click')
    await flushPromises()
    const mover = estado.posts.find((p) => p.caminho.endsWith('/mover'))
    expect(typeof mover.corpo.para_etapa).toBe('number')
  })

  it('clicar na etapa ATUAL nao pede nada ao servidor', async () => {
    const tela = await montar(fichaCom(885))
    await tela.find('.trilha__passo--atual').trigger('click')
    await flushPromises()
    expect(estado.posts.filter((p) => p.caminho.endsWith('/mover')))
      .toHaveLength(0)
  })
})

describe('card finalizado', () => {
  it('nao mostra a barra: reabrir primeiro e o gesto', async () => {
    /* ⚠️ Mesma régua do `<select>` de antes — oferecer mover e reabrir ao
       mesmo tempo deixaria o estado ambíguo. */
    const tela = await montar(fichaCom(885, 'resolvido'))
    expect(tela.find('.trilha').exists()).toBe(false)
    /* ⚠️ E a faixa continua DIZENDO em que etapa o card parou: esconder a
        barra não pode esconder o fato. */
    expect(tela.find('.faixa__medida--etapa').text()).toContain(
      'Elaborar contrato')
  })
})

describe('uma etapa so', () => {
  it('sem para onde mover, a barra nao aparece', async () => {
    const ficha = fichaCom(881)
    ficha.etapas = [ETAPAS[0]]
    const tela = await montar(ficha)
    expect(tela.find('.trilha').exists()).toBe(false)
    expect(tela.find('.faixa__medida--etapa').text()).toContain(
      'Nova solicitação')
  })
})
