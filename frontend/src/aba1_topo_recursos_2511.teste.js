/**
 * @vitest-environment jsdom
 *
 * O TOPO DA ABA 1 GANHA AJUDA, BUSCA E ORDENADOR — 25/11 (o G2).
 *
 * 🔵 Ele: *"faltam recursos no topo da aba1 tbm"* e *"1b igual para ambas"*.
 * 📏 Medido antes: a Operação tinha os três desde 05/11; esta tela, **nenhum**.
 *
 * 🚨 **ESTA TELA SERVE QUATRO PAINÉIS** (`PNL_1.2` a `PNL_1.5`). Então a trava
 * cobra que o texto da ajuda **não cite painel nenhum** — foi exatamente o
 * defeito que ele achou em 06/11, quando a lista de abas escrita em código fez
 * o Pós-venda aparecer dentro do Financeiro.
 *
 * 🚨 **GESTO, NÃO ATRIBUTO:** a busca é **digitada** e o que se mede é quantos
 * cards sobram na tela; o ordenador é **trocado** e o que se mede é a ordem dos
 * nomes. Trava que só vê o `<input>` existir não veria a peneira errada.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = vi.hoisted(() => ({
  sessao: { nome: 'Iago', owner: true, telas: [] },
  rota: { meta: { codigo: 'PNL_1.4', aba: 'PNL_1.4' }, query: {}, params: {} },
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

/* 📏 Três cards com dados reais de forma: cliente, OS, termo e placa. */
const CARDS = [
  { id: 1, cliente: 'Zz Pastelaria Velasco', numero_os: 17124, termo: '8952',
    placas: [{ placa: 'ABC1D23' }], tipo_nome: 'Instalação',
    criada_em: '2026-11-20T10:00:00Z', etapa_desde: '2026-11-24T10:00:00Z' },
  { id: 2, cliente: 'Movisat Teste', numero_os: 17130, termo: '8960',
    placas: [{ placa: 'XYZ9W88' }], tipo_nome: 'Manutenção',
    criada_em: '2026-11-23T10:00:00Z', etapa_desde: '2026-11-18T10:00:00Z' },
  { id: 3, cliente: 'Alfa Transportes', numero_os: 17140, termo: '8971',
    placas: [], tipo_nome: 'Retirada',
    criada_em: '2026-11-10T10:00:00Z', etapa_desde: null },
]

function quadro() {
  return {
    painel: 'financeiro', aba: 'PNL_1.4', titulo: 'Financeiro',
    total: CARDS.length,
    abas: [{ codigo_tela: 'PNL_1.4', titulo: 'Financeiro' }],
    colunas: [
      { chave: 'nova', titulo: 'Nova', etapa_id: 1, total: 2,
        cards: [CARDS[0], CARDS[1]] },
      { chave: 'andamento', titulo: 'Em andamento', etapa_id: 2, total: 1,
        cards: [CARDS[2]] },
      { chave: 'feito', titulo: 'Feito', etapa_id: 3, total: 0, cards: [] },
    ],
  }
}

async function abrirATela() {
  estado.quadro = quadro()
  const tela = mount(PainelAba, { attachTo: document.body })
  await flushPromises()
  await flushPromises()
  return tela
}

const cardsNaTela = (tela) => tela.findAll('article.card')
const caixaDeBusca = (tela) => tela.find('.painel__topo input[type="search"]')

beforeEach(() => {
  estado.rota = { meta: { codigo: 'PNL_1.4', aba: 'PNL_1.4' },
                  query: {}, params: {} }
})

describe('a ajuda no topo', () => {
  it('existe, com rótulo, junto do título', async () => {
    const tela = await abrirATela()
    const identidade = tela.find('.painel__identidade')
    expect(identidade.exists()).toBe(true)
    expect(identidade.find('h1').text()).toBe('Financeiro')
    const gatilho = identidade.find('.ajuda__gatilho')
    expect(gatilho.exists(), 'a ajuda tem de estar junto do título').toBe(true)
    expect(gatilho.attributes('aria-label')).toBeTruthy()
  })

  it('o texto NÃO cita painel nenhum — a tela serve quatro', async () => {
    const tela = await abrirATela()
    const texto = tela.find('.ajuda__balao').text()
    expect(texto.length).toBeGreaterThan(40)
    for (const nome of ['Financeiro', 'Pós-venda', 'Pos-venda', 'Contratual']) {
      expect(texto, `a ajuda cita "${nome}" e apareceria nos outros painéis`)
        .not.toContain(nome)
    }
    /* O que ela tem de dizer: de que são as colunas e o que o arrasto faz. */
    expect(texto).toContain('etapas')
    expect(texto).toContain('Arraste')
  })
})

describe('a busca', () => {
  it('peneira os cards pelo que o card mostra', async () => {
    const tela = await abrirATela()
    expect(cardsNaTela(tela).length).toBe(3)

    await caixaDeBusca(tela).setValue('velasco')
    expect(cardsNaTela(tela).length).toBe(1)
    expect(cardsNaTela(tela)[0].text()).toContain('Velasco')

    /* Por OS, por termo e por placa — os identificadores com que se cruza papel. */
    await caixaDeBusca(tela).setValue('17140')
    expect(cardsNaTela(tela).length).toBe(1)
    await caixaDeBusca(tela).setValue('8960')
    expect(cardsNaTela(tela).length).toBe(1)
    await caixaDeBusca(tela).setValue('xyz9w88')
    expect(cardsNaTela(tela).length).toBe(1)

    await caixaDeBusca(tela).setValue('')
    expect(cardsNaTela(tela).length).toBe(3)
  })

  it('a contagem DIZ o que a busca escondeu', async () => {
    const tela = await abrirATela()
    const pilula = () => tela.find('.painel__medidas .pilula').text()
    expect(pilula()).toContain('3')
    await caixaDeBusca(tela).setValue('velasco')
    /* 🚨 "1 de 3", nunca "1 card": contagem que cai sem explicação é a tela
       mentindo por omissão. */
    expect(pilula().replace(/\s+/g, ' ')).toContain('1 de 3')
  })

  it('coluna peneirada NÃO diz "Vazia."', async () => {
    const tela = await abrirATela()
    await caixaDeBusca(tela).setValue('velasco')
    const texto = tela.text()
    /* A coluna "Em andamento" tem 1 card que não casa. */
    expect(texto).toContain('nenhum casa com a busca')
    /* E a coluna "Feito", que é vazia de verdade, continua dizendo Vazia. */
    expect(texto).toContain('Vazia.')
  })

  it('busca que não casa com nada não derruba a tela', async () => {
    const tela = await abrirATela()
    await caixaDeBusca(tela).setValue('zzzz-nao-existe')
    expect(cardsNaTela(tela).length).toBe(0)
    expect(tela.text()).toContain('nenhum casa com a busca')
  })
})

describe('o ordenador', () => {
  it('nasce na ordem do SERVIDOR — nada muda sem alguém pedir', async () => {
    const tela = await abrirATela()
    const select = tela.find('.painel__medidas select')
    expect(select.exists()).toBe(true)
    expect(select.element.value).toBe('servidor')
    expect(select.findAll('option').length).toBe(4)
    const nomes = cardsNaTela(tela).map((c) => c.text())
    expect(nomes[0]).toContain('Velasco')
    expect(nomes[1]).toContain('Movisat')
  })

  it('"cliente A–Z" reordena dentro da coluna', async () => {
    const tela = await abrirATela()
    await tela.find('.painel__medidas select').setValue('cliente')
    const nomes = cardsNaTela(tela).map((c) => c.text())
    /* Dentro da coluna 1: Movisat vem antes de Zz. */
    expect(nomes[0]).toContain('Movisat')
    expect(nomes[1]).toContain('Velasco')
  })

  it('"mais recentes" usa a data de criação', async () => {
    const tela = await abrirATela()
    await tela.find('.painel__medidas select').setValue('recentes')
    const nomes = cardsNaTela(tela).map((c) => c.text())
    expect(nomes[0]).toContain('Movisat')
  })

  it('card SEM passagem registrada vai para o FIM em "parado"', async () => {
    /* 🚨 "não medido" não é "parado há mais tempo" — a régua da Operação. */
    const tela = await abrirATela()
    await tela.find('.painel__medidas select').setValue('parado')
    const todos = cardsNaTela(tela).map((c) => c.text())
    /* O card 3 (sem `etapa_desde`) é o único da coluna 2, então o que se mede
       é a coluna 1: Movisat (18/11) antes de Velasco (24/11). */
    expect(todos[0]).toContain('Movisat')
    expect(todos[1]).toContain('Velasco')
  })

  it('ordenar NÃO mexe no array do quadro', async () => {
    /* ⚠️ `sort` ordena no lugar: sem a cópia, a fonte seria embaralhada a cada
       desenho e a "ordem do servidor" deixaria de existir. */
    const tela = await abrirATela()
    await tela.find('.painel__medidas select').setValue('cliente')
    await tela.find('.painel__medidas select').setValue('servidor')
    const nomes = cardsNaTela(tela).map((c) => c.text())
    expect(nomes[0]).toContain('Velasco')
  })
})
