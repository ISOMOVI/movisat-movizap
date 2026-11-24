/**
 * @vitest-environment jsdom
 *
 * A ABA 2 DIZ O CORTE DE DATA — 23/11 (tarefa 2.3).
 *
 * 🔵 D6 dele, 23/11: *"use 16/11/2026 de inicio para o financeiro, não mexa na
 * data do OP"* · 🔵 D7: os anteriores se **escondem, não se apagam**.
 *
 * 🚨 **O QUE ESTA TELA TEM DE DIZER, E POR QUE É `M12`.** Medido em 23/11 no
 * `fpsl.db`: o corte de 16/11 leva a contagem de **79 artefatos para 2** —
 * sobram a OS 17124 (Franck, em Validação) e a OS 17131 (sem técnico, em
 * Movimentação). Uma tela que abrisse com 2 cards onde havia 79, calada, seria
 * a tela mentindo por omissão. Foi assim que o "sumiço" de 19/11 pareceu
 * defeito quando era filtro.
 *
 * 🚨 **E É UMA SAÍDA DELIBERADA DO PADRÃO DA OPERAÇÃO.** Medido em 23/11: a
 * `PainelOperacao.vue` **não mostra nem deixa mudar** a data dela — a classe
 * `.painel__desde` existe no CSS dela e **nenhum template a usa**, é regra
 * morta. Copiar isso aqui seria copiar o defeito.
 *
 * ⚠️ **A DATA NÃO SE MUDA PELA TELA**, e aí o padrão da Operação vale: ela é do
 * owner e se muda pela rota (`PUT /api/paineis/servico-dos-tecnicos/desde`,
 * 403 para quem não é owner). Pôr um campo aqui o daria às três pessoas que
 * têm a `PNL_1.6` — Aline, Erika e Karla, desde 19/11.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = vi.hoisted(() => ({ quadro: null }))

vi.mock('./api/cliente.js', () => {
  class ErroDeApi extends Error {}
  return {
    api: {
      get: () => Promise.resolve(estado.quadro),
      post: () => Promise.resolve({ ok: true }),
      put: () => Promise.resolve({ ok: true }),
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

/* 📏 O retrato de 23/11 depois do corte: 2 artefatos à vista, 77 escondidos. */
function quadro(extra = {}) {
  return {
    painel: 'financeiro', aba: 'PNL_1.6', titulo: 'Serviço dos técnicos',
    abas: [{ codigo_tela: 'PNL_1.6', titulo: 'Serviço dos técnicos' }],
    artefatos: 2,
    desde: '2026-11-16',
    escondidos_pela_data: 77,
    colunas: [
      { chave: 'movimentacao', titulo: 'Movimentação', total: 1,
        cards: [{ tecnico_id: 0, tecnico_nome: '', lote_id: null,
                  pode_preparar: false,
                  artefatos: [{ id: 104, numero_os: 17131,
                                orcamento_numero: null, termo: null,
                                data_os: '17/11/2026 14:55:00',
                                valor_pagamento: 211.9, valor_km: 0,
                                semaforo: 'verde', ciente_em: null,
                                justificativa: null, cliente: null,
                                cliente_id: 30839 }] }] },
      { chave: 'preparacao', titulo: 'Preparação', total: 0, cards: [] },
      { chave: 'validacao', titulo: 'Validação', total: 1,
        cards: [{ tecnico_id: 55, tecnico_nome: 'Franck', lote_id: 7,
                  pode_preparar: true,
                  artefatos: [{ id: 201, numero_os: 17124,
                                orcamento_numero: null, termo: null,
                                data_os: '16/11/2026 15:35:00',
                                valor_pagamento: 70, valor_km: 0,
                                semaforo: 'verde', ciente_em: null,
                                justificativa: null, cliente: 'Zz Velasco',
                                cliente_id: 33365 }] }] },
      { chave: 'procfy', titulo: 'Procfy', total: 0, cards: [] },
      { chave: 'enviado', titulo: 'Pagamento enviado', total: 0, cards: [] },
    ],
    ...extra,
  }
}

async function abrirATela(q) {
  estado.quadro = q || quadro()
  const tela = mount(PainelServicoDosTecnicos, {
    attachTo: document.body,
    global: { stubs: { RouterLink: { props: ['to'],
                                     template: '<a :href="to"><slot /></a>' } } },
  })
  await flushPromises()
  await flushPromises()
  return tela
}

const linhaDoCorte = (tela) => tela.find('.painel__desde')

beforeEach(() => { estado.quadro = null })

describe('a linha do corte de data', () => {
  it('🔵 D6: diz a data, em dd/mm/aa', async () => {
    const tela = await abrirATela()
    expect(linhaDoCorte(tela).exists()).toBe(true)
    expect(linhaDoCorte(tela).text()).toContain('serviço a partir de')
    /* ⚠️ 16/11/26, e não `2026-11-16`: a tela fala a língua de quem lê. */
    expect(linhaDoCorte(tela).text()).toContain('16/11/26')
  })

  it('🚨 M12: diz QUANTOS ficaram fora, e que eles seguem no banco',
     async () => {
    const tela = await abrirATela()
    const texto = linhaDoCorte(tela).text()
    expect(texto).toContain('77')
    expect(texto).toContain('artefatos anteriores')
    /* 🚨 "escondido" e "apagado" são coisas diferentes, e a decisão dele foi
       esconder. A tela tem de dizer qual das duas é. */
    expect(texto).toContain('seguem no banco')
  })

  it('🚨 o singular é singular — 1 artefato não vira "artefatos"', async () => {
    const tela = await abrirATela(quadro({ escondidos_pela_data: 1 }))
    expect(linhaDoCorte(tela).text()).toContain('1 artefato anterior')
    expect(linhaDoCorte(tela).text()).not.toContain('artefatos anteriores')
  })

  it('🔵 sem nada escondido, diz só a data — sem frase inútil', async () => {
    const tela = await abrirATela(quadro({ escondidos_pela_data: 0 }))
    const texto = linhaDoCorte(tela).text()
    expect(texto).toContain('16/11/26')
    expect(texto).not.toContain('fora de vista')
    expect(texto).not.toContain('seguem no banco')
  })

  it('🚨 servidor que não manda a data: a linha NÃO aparece, e a tela não quebra',
     async () => {
    /* ⚠️ Inventar uma data aqui seria pior que não mostrar nenhuma: a tela
       afirmaria um corte que o servidor não confirmou. */
    const q = quadro()
    delete q.desde
    delete q.escondidos_pela_data
    const tela = await abrirATela(q)
    expect(linhaDoCorte(tela).exists()).toBe(false)
    /* E o quadro continua desenhado. */
    expect(tela.findAll('article.card').length).toBeGreaterThan(0)
  })

  it('🚨 a data do corte NÃO é editável na tela — ela é do owner, pela rota',
     async () => {
    const tela = await abrirATela()
    const linha = linhaDoCorte(tela)
    expect(linha.findAll('input')).toHaveLength(0)
    expect(linha.findAll('button')).toHaveLength(0)
  })

  it('🔵 e o quadro continua desenhando os 2 que sobraram', async () => {
    const tela = await abrirATela()
    const cards = tela.findAll('article.card')
    expect(cards).toHaveLength(2)
    expect(tela.text()).toContain('Franck')
    expect(tela.text()).toContain('lote 7')
  })
})
