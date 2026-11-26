/**
 * @vitest-environment jsdom
 *
 * A UX APROVADA DA ABA 2 — 25/11. 🔵 *"Todo proposto está ótimo - pode seguir"*.
 *
 * 🚨 **A TRAVA QUE ELE PEDIU, e é a que importa mais:** o `Fechar` passou a
 * morar DENTRO dos dois braços do diálogo (o da Movimentação e o dos lotes).
 * Isso é duas cópias do mesmo botão, e o risco que ele cria é claro: no dia em
 * que nascer um terceiro braço sem ele, o diálogo fica **sem porta de saída**.
 * Então a trava abre o card em **cada** coluna e exige um `Fechar` que
 * realmente feche.
 *
 * 🚨 **GESTO, NÃO ATRIBUTO** (`M17` linha 2, `feedback_trava_de_atributo_nao_e_trava_de_gesto`):
 * o `Fechar` é **clicado** e o diálogo tem de desaparecer; os quadros são lidos
 * pelo TEXTO que aparece na tela, não por seletor inventado.
 *
 * ⚠️ O que esta trava NÃO alcança: aparência. O jsdom não faz layout — a grade
 * de larguras iguais e a cor do acento se provam no `conferir_css_publicado.mjs`
 * (11ª conferência) e com ele abrindo a tela.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = vi.hoisted(() => ({ quadro: null, postado: [] }))

vi.mock('./api/cliente.js', () => {
  class ErroDeApi extends Error {}
  return {
    api: {
      get: () => Promise.resolve(estado.quadro),
      post: (c, corpo) => {
        estado.postado.push([String(c), corpo])
        return Promise.resolve({ ok: true, semaforo: 'verde' })
      },
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

function artefato(id, os, extra = {}) {
  return { id, numero_os: os, orcamento_numero: null, termo: '8952',
           data_os: '18/11/2026 09:00:00', valor_pagamento: 70, valor_km: 10,
           semaforo: 'verde', ciente_em: null, justificativa: null,
           cliente: 'Zz Pastelaria Velasco', cliente_id: 33365,
           tipo_nome: 'Instalação', status_str: 'Serviço Realizado',
           datascope_form_state: null, comprovante_arquivo: null,
           valor_do_comprovante: null, comprovante_dispensa: null, ...extra }
}

function quadro() {
  const card = (tid, nome, lote, arts) => ({
    tecnico_id: tid, tecnico_nome: nome, lote_id: lote,
    pode_preparar: tid > 0, artefatos: arts,
  })
  return {
    painel: 'financeiro', aba: 'PNL_1.6', titulo: 'Serviço dos técnicos',
    abas: [{ codigo_tela: 'PNL_1.6', titulo: 'Serviço dos técnicos' }],
    artefatos: 4, desde: '2026-11-16', escondidos_pela_data: 77,
    varrido_em: new Date().toISOString(),
    colunas: [
      { chave: 'movimentacao', titulo: 'Movimentação', total: 1,
        cards: [card(55, 'Franck', null, [artefato(101, 17124)])] },
      { chave: 'preparacao', titulo: 'Preparação', total: 1,
        cards: [card(55, 'Franck', 7, [artefato(102, 17126)])] },
      { chave: 'validacao', titulo: 'Validação', total: 1,
        cards: [card(55, 'Franck', 8, [artefato(103, 17135)])] },
      { chave: 'procfy', titulo: 'Procfy', total: 1,
        cards: [card(55, 'Franck', 9, [artefato(104, 17137)])] },
      { chave: 'enviado', titulo: 'Pagamento enviado', total: 1,
        cards: [card(55, 'Franck', 10, [artefato(105, 17139)])] },
    ],
  }
}

async function abrirATela() {
  estado.quadro = quadro()
  const tela = mount(PainelServicoDosTecnicos, { attachTo: document.body })
  await flushPromises()
  await flushPromises()
  return tela
}

const dialogoDoCard = (tela) =>
  tela.findAll('.modal').find(
    (m) => m.attributes('aria-label')?.includes('Card de'))

async function abrirOCardDa(tela, titulo) {
  const coluna = tela.findAll('.coluna').find((c) => c.text().includes(titulo))
  expect(coluna, `a coluna ${titulo} tem de estar no quadro`).toBeTruthy()
  await coluna.find('button.card__abrir').trigger('click')
  await flushPromises()
  const d = dialogoDoCard(tela)
  expect(d, `o card da coluna ${titulo} tem de abrir`).toBeTruthy()
  return d
}

beforeEach(() => { estado.postado = [] })

/* ==========================================================================
   1. O TOPO — a ajuda e os controles
   ========================================================================== */
describe('o topo', () => {
  it('tem o balão de ajuda, e ele diz o que a tela faz', async () => {
    const tela = await abrirATela()
    const topo = tela.find('.painel__topo')
    const gatilho = topo.find('.ajuda__gatilho')
    expect(gatilho.exists(), 'o gatilho da ajuda tem de estar no topo').toBe(true)
    /* 🚨 Rótulo para quem não vê o ícone: o `?` sozinho não diz nada. */
    expect(gatilho.attributes('aria-label')).toBeTruthy()
    const balao = topo.find('.ajuda__balao')
    expect(balao.text()).toContain('05:10')
    expect(balao.text()).toContain('16/11')
  })

  it('a busca e os dois ordenadores ficam no topo, não numa linha solta', async () => {
    const tela = await abrirATela()
    const topo = tela.find('.painel__topo')
    expect(topo.find('input[type="search"]').exists()).toBe(true)
    expect(topo.findAll('select').length).toBe(2)
  })

  it('a identidade e os controles são dois blocos', async () => {
    const tela = await abrirATela()
    /* ⚠️ O `h1` é o nome do PAINEL ("Financeiro"), não o da aba: o nome da aba
       aparece na tira logo abaixo, e repeti-lo aqui seria dizer duas vezes —
       está escrito no comentário da própria tela. O que esta trava mede é o
       ARRANJO: título e ajuda juntos num bloco, controles no outro. */
    const identidade = tela.find('.painel__identidade')
    expect(identidade.exists()).toBe(true)
    expect(identidade.find('h1').text().length).toBeGreaterThan(0)
    expect(identidade.find('.ajuda__gatilho').exists(),
           'a ajuda tem de ficar junto do título, não entre os controles')
      .toBe(true)
    expect(tela.find('.painel__medidas input[type="search"]').exists()).toBe(true)
  })
})

/* ==========================================================================
   2. O CARD FECHADO — o nome do técnico como identificador
   ========================================================================== */
describe('o card fechado', () => {
  it('o nome do técnico usa a classe de identificador', async () => {
    const tela = await abrirATela()
    const nome = tela.find('.card__tecnico')
    expect(nome.exists(), 'o nome do técnico tem de ter destaque próprio').toBe(true)
    expect(nome.text()).toContain('Franck')
    /* ⚠️ A classe antiga não pode sobrar: duas regras para a mesma coisa é
       como uma delas envelhece sem ninguém ver. */
    expect(tela.html()).not.toContain('class="card__cliente"')
  })
})

/* ==========================================================================
   3. OS QUADROS DE AÇÃO
   ========================================================================== */
describe('os quadros de ação', () => {
  it('a Validação separa conferir, fechar e desfazer — e diz o que cada um faz',
     async () => {
    const tela = await abrirATela()
    const d = await abrirOCardDa(tela, 'Validação')
    const texto = d.text()
    expect(texto).toContain('Conferir')
    expect(texto).toContain('Fechar o pagamento')
    expect(texto).toContain('Desfazer')
    /* A nota de cada ação é o que ele pediu: *"informações sobre cada"*. */
    expect(texto).toContain('Não move nada')
    expect(texto).toContain('sem comprovante nem dispensa fica para trás')
    expect(texto).toContain('Devolve todos os artefatos à Movimentação')
    /* Toda ação tem nome E nota — quadro sem nota é o botão de antes. */
    const quadros = d.findAll('.acao')
    expect(quadros.length).toBeGreaterThanOrEqual(4)
    for (const q of quadros) {
      expect(q.find('.acao__nome').exists()).toBe(true)
      expect(q.find('.acao__nota').text().length).toBeGreaterThan(10)
    }
  })

  it('a Movimentação só mostra escolher e preparar — sem Excluir o card',
     async () => {
    const tela = await abrirATela()
    const d = await abrirOCardDa(tela, 'Movimentação')
    expect(d.text()).toContain('Escolher o que vai pagar')
    expect(d.text()).toContain('Preparar os marcados')
    /* 🔵 Na coluna 1 o card é o técnico, permanente: não há lote a excluir. */
    expect(d.text()).not.toContain('Excluir o card')
  })

  it('Preparar nasce desabilitado e DIZ que está, sem nada marcado', async () => {
    const tela = await abrirATela()
    const d = await abrirOCardDa(tela, 'Movimentação')
    const preparar = d.findAll('.acao').find(
      (a) => a.text().includes('Preparar os marcados'))
    expect(preparar.attributes('disabled')).toBeDefined()
  })

  it('a ação principal de cada coluna é UMA', async () => {
    const tela = await abrirATela()
    for (const coluna of ['Preparação', 'Validação', 'Procfy']) {
      const d = await abrirOCardDa(tela, coluna)
      expect(d.findAll('.acao--principal').length,
             `${coluna} tem de ter uma ação principal só`).toBe(1)
      await d.findAll('button').find((b) => b.text() === 'Fechar').trigger('click')
      await flushPromises()
    }
  })
})

/* ==========================================================================
   4. O RODAPÉ — a trava que ele pediu
   ========================================================================== */
describe('o rodapé numa faixa só', () => {
  it('TODO braço do diálogo tem um Fechar que FECHA', async () => {
    /* 🚨 Esta é a trava do risco que o arranjo novo cria: o `Fechar` está
       duplicado nos dois braços, e braço sem ele é diálogo sem saída. */
    const tela = await abrirATela()
    for (const coluna of ['Movimentação', 'Preparação', 'Validação', 'Procfy',
                          'Pagamento enviado']) {
      const d = await abrirOCardDa(tela, coluna)
      const rodape = d.find('.card__rodape')
      expect(rodape.exists(), `${coluna} sem rodapé`).toBe(true)
      const fechar = rodape.findAll('button').find((b) => b.text() === 'Fechar')
      expect(fechar, `${coluna} sem Fechar no rodapé`).toBeTruthy()
      await fechar.trigger('click')
      await flushPromises()
      expect(dialogoDoCard(tela), `o Fechar de ${coluna} não fechou`).toBeFalsy()
    }
  })

  it('o Fechar não é mais a ação de maior peso', async () => {
    const tela = await abrirATela()
    const d = await abrirOCardDa(tela, 'Validação')
    const fechar = d.findAll('button').find((b) => b.text() === 'Fechar')
    expect(fechar.classes()).toContain('botao--fantasma')
  })

  it('o rodapé diz a regra do lote, não só os botões', async () => {
    const tela = await abrirATela()
    const d = await abrirOCardDa(tela, 'Validação')
    expect(d.find('.card__rodape').text())
      .toContain('comprovante ou dispensa')
  })
})
