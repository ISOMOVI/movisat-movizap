/**
 * @vitest-environment jsdom
 *
 * A ROLAGEM NAS OUTRAS ABAS, E O NUMERO DA OS NO CARD (11/11).
 *
 * 🔵 **Item 1 dele:** a rolagem com o mouse que a Operação ganhou em 06/11
 * (*"precisamos disso nos paineis, pois o scroll ficou la embaixo"*) nunca
 * chegou às abas. 📏 Medido antes: `grep -c rolo PainelAba.vue` dava **0**,
 * e `PainelOperacao.vue` dava 4.
 *
 * 🔵 **E o card com OS**, que nasceu na migração 106: as OS das situações
 * 15746, 15695 e 16492 saíram das colunas da Operação e passam a nascer
 * nestes painéis — *"deveria ter nascido no painel Financeiro, na etapa
 * correta 'Nova solicitação'"*.
 *
 * 🚨 **A TRAVA DA ROLAGEM OLHA A ESTRUTURA, NÃO O GESTO.** O jsdom **não faz
 * layout**: `scrollWidth` e `clientWidth` são sempre 0, então "arrastar e ver
 * rolar" não prova nada aqui. O que prova é que os dois controles estão na
 * árvore **ligados ao elemento que rola** — que foi exatamente o defeito do
 * card inerte de 09/11, onde 22 travas passaram verdes com a tela morta.
 *
 * 🚨 **E O `ref` NÃO PODE SE CHAMAR `quadro`:** naquela tela `quadro` já é o
 * ref do JSON do painel. Reusar o nome poria o elemento do DOM onde a tela
 * espera os dados, e o quadro inteiro deixaria de desenhar — uma colisão que
 * o Vue não reclama.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const estado = vi.hoisted(() => ({
  sessao: { nome: 'Iago', owner: true, telas: [] },
  rota: { meta: { codigo: 'PNL_1.4', aba: 'PNL_1.4', titulo: 'Financeiro' },
          query: {}, params: {} },
  quadro: null,
}))

vi.mock('./api/cliente.js', () => ({
  api: {
    get: () => Promise.resolve(estado.quadro),
    post: () => Promise.resolve({}),
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
  sessao: estado.sessao,
  codigosPermitidos: { value: new Set() },
  sair: () => {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => estado.rota,
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

import PainelAba from './telas/PainelAba.vue'
import BarraDeRolagem from './componentes/BarraDeRolagem.vue'
import RolagemDaBorda from './componentes/RolagemDaBorda.vue'

const STUB_LINK = { props: ['to'], template: '<a :href="to"><slot /></a>' }

function cardDeOs(id, numeroOs) {
  return {
    id,
    origem: 'chamado',
    etapa_id: 1,
    solicitacao_id: null,
    formulario: null,
    slug: null,
    criada_em: '2026-11-11T12:25:00',
    cliente: 'MICRO CERVEJARIA ARTESANAL SOROCABA',
    cliente_id: null,
    resumo: null,
    anexos: 0,
    numero_os: numeroOs,
    os_id: null,
    numero_ordem: null,
    situacao_id: null,
    observacoes: 0,
    desfecho: null,
  }
}

function quadroComCard(card) {
  return {
    painel: 'financeiro',
    aba: 'PNL_1.4',
    titulo: 'Financeiro',
    abas: [{ codigo_tela: 'PNL_1.4', titulo: 'Financeiro' }],
    colunas: [
      { chave: 'e875', titulo: 'Nova solicitação', situacao_id: null,
        etapa_id: 875, final: false, nota: null,
        cards: card ? [card] : [], total: card ? 1 : 0 },
      { chave: 'e876', titulo: 'INADIMPLENTES', situacao_id: null,
        etapa_id: 876, final: false, nota: null, cards: [], total: 0 },
    ],
    total: card ? 1 : 0,
    pode_mover: true,
    fora_do_quadro: {},
    etapas: [],
    desfechos: [],
  }
}

async function montar(quadro) {
  estado.quadro = quadro
  const tela = mount(PainelAba, {
    global: { stubs: { RouterLink: STUB_LINK } },
  })
  await flushPromises()
  await flushPromises()
  return tela
}

beforeEach(() => {
  estado.quadro = null
})

describe('a rolagem chega as abas (item 1 dele)', () => {
  it('os DOIS controles estao na arvore', async () => {
    const tela = await montar(quadroComCard(null))
    expect(tela.findComponent(BarraDeRolagem).exists()).toBe(true)
    expect(tela.findComponent(RolagemDaBorda).exists()).toBe(true)
  })

  it('os dois recebem O MESMO elemento, e ele e o que rola', async () => {
    /* 🚨 ESTA É A TRAVA QUE IMPORTA. Os componentes na árvore sem a `prop`
       ligada seriam dois controles inertes — e inerte é exatamente o defeito
       que o jsdom não vê. */
    const tela = await montar(quadroComCard(null))
    const barra = tela.findComponent(BarraDeRolagem)
    const borda = tela.findComponent(RolagemDaBorda)
    const rolo = barra.props('rolo')
    expect(rolo).toBeTruthy()
    expect(borda.props('rolo')).toBe(rolo)
    /* ⚠️ E é o elemento com `overflow-x`, não um qualquer: é a classe que o
       estilo da tela declara como rolável. */
    expect(rolo.classList.contains('painel__quadro')).toBe(true)
  })

  it('o elemento que rola tem as COLUNAS dentro', async () => {
    const tela = await montar(quadroComCard(null))
    const rolo = tela.findComponent(BarraDeRolagem).props('rolo')
    expect(rolo.querySelectorAll('.coluna').length).toBe(2)
  })

  it('o casco e `relative`, senao a faixa da borda ancora errado', async () => {
    const tela = await montar(quadroComCard(null))
    expect(tela.find('.painel__casco').exists()).toBe(true)
  })

  it('o quadro continua desenhando: o `ref` nao roubou o nome dos dados',
     async () => {
       /* 🚨 A colisão `quadro` (DOM) × `quadro` (JSON) não daria erro: a tela
          simplesmente ficaria sem colunas. */
       const tela = await montar(quadroComCard(null))
       expect(tela.text()).toContain('Nova solicitação')
       expect(tela.text()).toContain('INADIMPLENTES')
     })
})

describe('o card da OS mostra o NUMERO DA OS (migracao 106)', () => {
  it('escreve "OS 17119", e nao "Card 912"', async () => {
    const tela = await montar(quadroComCard(cardDeOs(912, 17119)))
    const texto = tela.text()
    expect(texto).toContain('OS 17119')
    /* 🚨 O número do card é NOSSO e não serve para procurar nada no Harmonit:
       quem olha a fila precisa do número da OS. */
    expect(texto).not.toContain('Card 912')
  })

  it('card SEM OS continua como estava', async () => {
    const card = cardDeOs(913, null)
    card.formulario = 'Aditivo contratual'
    const tela = await montar(quadroComCard(card))
    expect(tela.text()).toContain('Aditivo contratual')
    expect(tela.text()).not.toContain('OS null')
  })

  it('card sem OS e sem formulario cai no nome do card', async () => {
    const tela = await montar(quadroComCard(cardDeOs(914, null)))
    expect(tela.text()).toContain('Card 914')
  })
})
