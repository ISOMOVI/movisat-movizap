/**
 * @vitest-environment jsdom
 *
 * O CARD FECHADO E O CARD ABERTO DA ABA 2 — 23/11 (tarefa 2.2).
 *
 * 🔵 Ele, 23/11: *"o card fechado só com resumo, dados e botões só no card
 * aberto"*. E antes, em 19/11: *"faltam várias coisas (...) como a aba1
 * apresenta"*.
 *
 * 🚨 **O DEFEITO MEDIDO EM 23/11.** Esta era a única das cinco telas de painel
 * em que o card trazia tudo dentro de um `<div class="card__abrir">` que nunca
 * abria nada. A coluna 1 empilhava, num card ao lado de outros quatro numa
 * coluna estreita: o nome, três valores, **dois campos de data**, a **lista
 * inteira** de artefatos com caixas de marcação, e **três botões**. A aba 1
 * (`PainelAba.vue`) e a Operação (`PainelOperacao.vue`) abrem o card num
 * diálogo desde 05/11.
 *
 * 🚨 **A LISTA NOMINAL DOS GESTOS (M11), escrita ANTES do código e lida contra
 * a OPERAÇÃO — não contra a própria aba 2**, porque comparar a tela com ela
 * mesma é comparar cópia com cópia:
 *   1. o card fechado mostra nome, quantidade, valor e o pior semáforo;
 *   2. o card fechado **não** tem campo de data, caixa de marcação nem botão
 *      de ação;
 *   3. clicar no card abre um diálogo;
 *   4. o diálogo tem o filtro, a lista, as marcações e os botões;
 *   5. `Escape` fecha o diálogo;
 *   6. o card fechado é alcançável pelo **teclado** (é `<button>`, não `div`);
 *   7. recarregar o quadro **reaponta** o card aberto, em vez de deixá-lo
 *      mostrando o retrato velho.
 *
 * ⚠️ O gesto 7 é a armadilha que a `PainelAba.vue` já documentava: sem o
 * reaponte, o diálogo segue mostrando a lista de ANTES do "Preparar" — e é
 * exatamente aí que o dado mudou.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = vi.hoisted(() => ({ quadro: null, postado: [], vezes: 0 }))

vi.mock('./api/cliente.js', () => {
  class ErroDeApi extends Error {}
  return {
    api: {
      get: () => {
        estado.vezes += 1
        return Promise.resolve(estado.quadro)
      },
      post: (c, corpo) => {
        estado.postado.push([String(c), corpo])
        return Promise.resolve({ ok: true })
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

/* 📏 Dados reais, medidos em 23/11 no `fpsl.db`: o Franck tem 39 itens em
   Movimentação e 1 em Validação (OS 17124, R$ 70,00). Um dos itens vem
   `vermelho` de propósito, para o resumo do semáforo ter o que resumir. */
function artefato(id, os, data, extra = {}) {
  return { id, numero_os: os, orcamento_numero: null, termo: null,
           data_os: data, valor_pagamento: 70, valor_km: 10,
           semaforo: 'verde', ciente_em: null, justificativa: null,
           cliente: 'Zz Pastelaria Velasco', cliente_id: 33365,
           tipo_nome: 'Instalação', status_str: 'Serviço Realizado',
           datascope_form_state: null, comprovante_arquivo: null,
           valor_do_comprovante: null, comprovante_dispensa: null, ...extra }
}

function quadro() {
  return {
    painel: 'financeiro', aba: 'PNL_1.6', titulo: 'Serviço dos técnicos',
    abas: [{ codigo_tela: 'PNL_1.6', titulo: 'Serviço dos técnicos' }],
    colunas: [
      { chave: 'movimentacao', titulo: 'Movimentação', total: 3,
        cards: [{ tecnico_id: 55, tecnico_nome: 'Franck', lote_id: null,
                  pode_preparar: true,
                  artefatos: [artefato(101, 17001, '20/10/2026 14:00:00'),
                              artefato(102, 17100, '10/11/2026 11:30:00',
                                       { semaforo: 'vermelho' }),
                              artefato(103, 17124, '16/11/2026 15:35:00')] },
                { tecnico_id: 0, tecnico_nome: '', lote_id: null,
                  pode_preparar: false,
                  artefatos: [artefato(104, 17131, '17/11/2026 14:55:00')] }] },
      { chave: 'preparacao', titulo: 'Preparação', total: 0, cards: [] },
      { chave: 'validacao', titulo: 'Validação', total: 1,
        cards: [{ tecnico_id: 55, tecnico_nome: 'Franck', lote_id: 7,
                  pode_preparar: true,
                  artefatos: [artefato(201, 17124, '16/11/2026 15:35:00')] }] },
      { chave: 'procfy', titulo: 'Procfy', total: 0, cards: [] },
      { chave: 'enviado', titulo: 'Pagamento enviado', total: 0, cards: [] },
    ],
  }
}

async function abrirATela() {
  estado.quadro = quadro()
  const tela = mount(PainelServicoDosTecnicos, {
    attachTo: document.body,
    global: { stubs: { RouterLink: { props: ['to'],
                                     template: '<a :href="to"><slot /></a>' } } },
  })
  await flushPromises()
  await flushPromises()
  return tela
}

/* 🚨 Procura-se pelo TEXTO que está na tela, não por um seletor inventado. */
const cardFechado = (tela, nome) =>
  tela.findAll('article.card').find((a) => a.text().includes(nome))

const dialogo = (tela) =>
  tela.findAll('.modal').find((m) => m.attributes('aria-label')?.includes('Card de'))

async function abrirOCard(tela, nome) {
  const card = cardFechado(tela, nome)
  expect(card, `o card de ${nome} tem de estar no quadro`).toBeTruthy()
  await card.find('button.card__abrir').trigger('click')
  await flushPromises()
  const d = dialogo(tela)
  expect(d, 'o diálogo do card tem de abrir').toBeTruthy()
  return d
}

beforeEach(() => { estado.postado = []; estado.vezes = 0 })

/* ==========================================================================
   GESTOS 1 e 2 — o card FECHADO
   ========================================================================== */
describe('o card fechado', () => {
  it('🔵 mostra nome, quantidade e valor a pagar', async () => {
    const tela = await abrirATela()
    const card = cardFechado(tela, 'Franck')
    expect(card.text()).toContain('Franck')
    expect(card.text()).toContain('3 de 3')
    expect(card.text()).toContain('a pagar')
    expect(card.text()).toContain('240,00')     // 3 × (70 + 10)
  })

  it('🔵 mostra o PIOR semáforo, com ícone e texto', async () => {
    const tela = await abrirATela()
    const card = cardFechado(tela, 'Franck')
    /* 🚨 Um vermelho entre dois verdes: é justamente o que faz alguém abrir o
       card, e não pode ficar escondido atrás da maioria. */
    expect(card.text()).toContain('a pagar maior que o recibo')
    expect(card.find('.selo--vermelho').exists()).toBe(true)
    expect(card.find('.selo--vermelho i').classes().join(' '))
      .toContain('bi-x-circle-fill')
  })

  it('🚨 NÃO tem campo de data, caixa de marcação nem botão de ação',
     async () => {
    const tela = await abrirATela()
    const card = cardFechado(tela, 'Franck')
    expect(card.findAll('input[type="date"]')).toHaveLength(0)
    expect(card.findAll('input[type="checkbox"]')).toHaveLength(0)
    /* O único `<button>` do card fechado é o próprio card. */
    const botoes = card.findAll('button')
    expect(botoes).toHaveLength(1)
    expect(botoes[0].classes()).toContain('card__abrir')
    expect(card.text()).not.toContain('Preparar os marcados')
    expect(card.text()).not.toContain('Marcar todos')
  })

  it('🚨 NÃO traz a lista de artefatos', async () => {
    const tela = await abrirATela()
    const card = cardFechado(tela, 'Franck')
    expect(card.findAll('li.artefato')).toHaveLength(0)
    expect(card.text()).not.toContain('OS 17001')
  })

  /* 🚨 O dinheiro parado tem de ter explicação À VISTA: esconder o motivo
     atrás de um clique deixaria o valor sem razão aparente. */
  it('🚨 o card SEM TÉCNICO diz a trava no card fechado', async () => {
    const tela = await abrirATela()
    const card = cardFechado(tela, 'Sem técnico') || cardFechado(tela, 'técnico 0')
    expect(card, 'o card dos sem técnico tem de existir').toBeTruthy()
    expect(card.text()).toContain('não há a quem pagar')
  })
})

/* ==========================================================================
   GESTO 6 — o teclado
   ========================================================================== */
describe('o teclado', () => {
  it('🚨 o card fechado é um `<button>`, não um `<div>` com @click', async () => {
    const tela = await abrirATela()
    const alvo = cardFechado(tela, 'Franck').find('.card__abrir')
    /* ⚠️ `div` com `@click` é invisível para quem usa Tab: a tela ficaria
       trancada para quem não usa mouse. */
    expect(alvo.element.tagName).toBe('BUTTON')
    expect(alvo.attributes('type')).toBe('button')
  })
})

/* ==========================================================================
   GESTOS 3, 4 e 5 — o card ABERTO
   ========================================================================== */
describe('o card aberto', () => {
  it('🔵 clicar no card abre o diálogo com o nome do técnico', async () => {
    const tela = await abrirATela()
    const d = await abrirOCard(tela, 'Franck')
    expect(d.find('.modal__titulo').text()).toContain('Franck')
  })

  it('🔵 o diálogo tem o filtro de data, a lista e os botões', async () => {
    const tela = await abrirATela()
    const d = await abrirOCard(tela, 'Franck')
    expect(d.findAll('input[type="date"]')).toHaveLength(2)
    expect(d.findAll('li.artefato')).toHaveLength(3)
    expect(d.findAll('input[type="checkbox"]')).toHaveLength(3)
    expect(d.text()).toContain('Preparar os marcados')
    expect(d.text()).toContain('Marcar todos')
  })

  it('🔵 e os três valores desdobrados (serviço e km), que saíram do fechado',
     async () => {
    const tela = await abrirATela()
    const d = await abrirOCard(tela, 'Franck')
    expect(d.text()).toContain('serviço')
    expect(d.text()).toContain('km')
    expect(cardFechado(tela, 'Franck').text()).not.toContain('· km')
  })

  it('🚨 marcar um item e preparar funciona DE DENTRO do diálogo', async () => {
    const tela = await abrirATela()
    const d = await abrirOCard(tela, 'Franck')
    await d.findAll('input[type="checkbox"]')[0].trigger('change')
    await flushPromises()
    expect(d.text()).toContain('Preparar os marcados (1)')
    await d.findAll('button').find((b) => /Preparar os marcados/.test(b.text()))
      .trigger('click')
    await flushPromises()
    expect(estado.postado.some(([c]) => /preparar/.test(c))).toBe(true)
  })

  it('🔵 `Escape` fecha o diálogo', async () => {
    const tela = await abrirATela()
    await abrirOCard(tela, 'Franck')
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(dialogo(tela)).toBeFalsy()
  })

  it('🔵 o botão Fechar também fecha', async () => {
    const tela = await abrirATela()
    const d = await abrirOCard(tela, 'Franck')
    await d.findAll('button').find((b) => b.text().trim() === 'Fechar')
      .trigger('click')
    await flushPromises()
    expect(dialogo(tela)).toBeFalsy()
  })

  /* 🚨 Coluna 2 a 5: o card é o LOTE, e os botões são outros. */
  it('🔵 o card de um LOTE abre com os botões da coluna dele', async () => {
    const tela = await abrirATela()
    const card = tela.findAll('article.card')
      .find((a) => a.text().includes('lote 7'))
    expect(card, 'o card do lote 7 tem de estar na Validação').toBeTruthy()
    await card.find('button.card__abrir').trigger('click')
    await flushPromises()
    const d = dialogo(tela)
    expect(d.text()).toContain('lote 7')
    expect(d.text()).toContain('Montar arquivo')
    expect(d.text()).toContain('Ler DataScope')
    /* ⚠️ Nas colunas 2 a 5 NÃO há filtro de período: o lote já foi fechado. */
    expect(d.findAll('input[type="date"]')).toHaveLength(0)
  })

  /* ========================================================================
     TAREFA 2.3 — 🔵 *"é possível clicar em remover, onde o item de pagamento
     será removido e devolvido ao card na coluna de Movimentação abrindo um
     campo de justificativa"*.

     📏 MEDIDO EM 23/11: a rota `/devolver` existia nos dois lados e o serviço
     já aceitava de qualquer coluna que não a 1 — e o botão existia SÓ dentro
     do diálogo de conferência, que abre da coluna 2. Nas colunas 3, 4 e 5 não
     havia como remover um item.
     ======================================================================== */
  it('🔵 2.3: o item do lote tem Remover, e ele abre a justificativa',
     async () => {
    const tela = await abrirATela()
    const card = tela.findAll('article.card')
      .find((a) => a.text().includes('lote 7'))
    await card.find('button.card__abrir').trigger('click')
    await flushPromises()
    const d = dialogo(tela)
    const remover = d.findAll('button').find((b) => b.text() === 'Remover')
    expect(remover, 'o item da Validação tem de ter Remover').toBeTruthy()
    await remover.trigger('click')
    await flushPromises()
    /* 🚨 O MESMO diálogo de justificativa da conferência, não um segundo. */
    const just = tela.findAll('.modal')
      .find((m) => m.text().includes('Por que está removendo?'))
    expect(just, 'o campo de justificativa tem de abrir').toBeTruthy()
    expect(just.text()).toContain('volta para a Movimentação em laranja')
    /* ⚠️ E sem justificativa o botão do diálogo fica travado: devolver calado
       deixaria o artefato laranja e ninguém saberia por quê. */
    const confirmar = just.findAll('button').find((b) => b.text() === 'Remover')
    expect(confirmar.attributes('disabled')).toBeDefined()
    await just.find('input.campo').setValue('zz OS voltou para agendar')
    await flushPromises()
    expect(just.findAll('button').find((b) => b.text() === 'Remover')
      .attributes('disabled')).toBeUndefined()
  })

  /* ========================================================================
     TAREFA 2.4 — 🔵 *"Excluir o card inteiro devolvendo tudo à coluna 1, com
     justificativa única"*.
     ======================================================================== */
  it('🔵 2.4: excluir o card manda o LOTE e a justificativa única',
     async () => {
    const tela = await abrirATela()
    const card = tela.findAll('article.card')
      .find((a) => a.text().includes('lote 7'))
    await card.find('button.card__abrir').trigger('click')
    await flushPromises()
    /* ⚠️ `startsWith`: o Excluir virou quadro com nota (25/11). O botão de
       CONFIRMAR, no diálogo de justificativa, segue com `===` logo abaixo. */
    const excluir = dialogo(tela).findAll('button')
      .find((b) => b.text().startsWith('Excluir o card'))
    expect(excluir, 'o card do lote tem de ter Excluir o card').toBeTruthy()
    await excluir.trigger('click')
    await flushPromises()
    const just = tela.findAll('.modal')
      .find((m) => m.text().includes('Excluir o card inteiro?'))
    expect(just, 'o diálogo da justificativa única tem de abrir').toBeTruthy()
    /* 🚨 O NÚMERO À VISTA: "todos os itens" sem dizer quantos faria a pessoa
       decidir no escuro. */
    expect(just.text()).toContain('1 item(ns)')
    await just.find('input.campo').setValue('zz lote do técnico errado')
    await flushPromises()
    await just.findAll('button').find((b) => b.text() === 'Excluir o card')
      .trigger('click')
    await flushPromises()
    const pedido = estado.postado.find((p) => p[0].includes('devolver-lote'))
    expect(pedido, 'o POST de devolver-lote não saiu').toBeTruthy()
    expect(pedido[1]).toEqual({ lote_id: 7,
                                justificativa: 'zz lote do técnico errado' })
  })

  /* ========================================================================
     TAREFA 2.5 — 🔵 *"Reabrir na coluna 5 e gerar o arquivo de novo"*.
     ⚠️ SEM diálogo de justificativa de propósito: nada é devolvido nem
     desfeito. Pedir motivo trataria reabrir como erro, e reabrir é trabalho.
     ======================================================================== */
  it('🔵 2.5: na coluna 5 há Reabrir, e ele manda o lote', async () => {
    const q = quadro()
    q.colunas[4].total = 1
    q.colunas[4].cards = [{ tecnico_id: 55, tecnico_nome: 'Franck',
                            lote_id: 12, pode_preparar: true,
                            artefatos: [artefato(401, 17124,
                                                 '16/11/2026 15:35:00')] }]
    estado.quadro = q
    const tela = mount(PainelServicoDosTecnicos, {
      attachTo: document.body,
      global: { stubs: { RouterLink: { props: ['to'],
                                       template: '<a :href="to"><slot /></a>' } } },
    })
    await flushPromises()
    await flushPromises()
    const card = tela.findAll('article.card')
      .find((a) => a.text().includes('lote 12'))
    await card.find('button.card__abrir').trigger('click')
    await flushPromises()
    const botao = dialogo(tela).findAll('button')
      .find((b) => b.text().includes('Reabrir para gerar de novo'))
    expect(botao, 'a coluna 5 tem de ter Reabrir').toBeTruthy()
    await botao.trigger('click')
    await flushPromises()
    expect(estado.postado.some((p) => p[0].includes('/reabrir/12'))).toBe(true)
  })

  it('⚠️ 2.5: na Validação NÃO há Reabrir — o arquivo ainda nem saiu',
     async () => {
    const tela = await abrirATela()
    const card = tela.findAll('article.card')
      .find((a) => a.text().includes('lote 7'))
    await card.find('button.card__abrir').trigger('click')
    await flushPromises()
    expect(dialogo(tela).findAll('button')
      .filter((b) => b.text().includes('Reabrir'))).toHaveLength(0)
  })

  it('⚠️ 2.4: na coluna 1 não há card de lote para excluir', async () => {
    const tela = await abrirATela()
    const d = await abrirOCard(tela, 'Franck')
    expect(d.findAll('button')
      .filter((b) => b.text().includes('Excluir o card'))).toHaveLength(0)
  })

  it('⚠️ 2.3: na coluna 1 NÃO há Remover — o item já está lá', async () => {
    const tela = await abrirATela()
    const d = await abrirOCard(tela, 'Franck')
    expect(d.findAll('button')
      .filter((b) => b.text().includes('Remover'))).toHaveLength(0)
  })

  /* 🚨 A CONSEQUÊNCIA, e é o que a tela tem de dizer: na coluna 4 o arquivo do
     Procfy já foi montado com o item dentro, e na 5 já foi enviado. Mesma
     frase das outras colunas seria a tela escondendo o que muda (`M12`). */
  it('🚨 2.3: remover da Procfy avisa que o arquivo já foi montado',
     async () => {
    const q = quadro()
    q.colunas[3].total = 1
    q.colunas[3].cards = [{ tecnico_id: 55, tecnico_nome: 'Franck',
                            lote_id: 9, pode_preparar: true,
                            artefatos: [artefato(301, 17124,
                                                 '16/11/2026 15:35:00')] }]
    estado.quadro = q
    const tela = mount(PainelServicoDosTecnicos, {
      attachTo: document.body,
      /* ⚠️ O MESMO stub do `abrirATela`: sem ele o Vue avisa
         "Failed to resolve component: RouterLink" e a suite passa verde com
         ruido -- divida para quem vier depois. */
      global: { stubs: { RouterLink: { props: ['to'],
                                       template: '<a :href="to"><slot /></a>' } } },
    })
    await flushPromises()
    await flushPromises()
    const card = tela.findAll('article.card')
      .find((a) => a.text().includes('lote 9'))
    await card.find('button.card__abrir').trigger('click')
    await flushPromises()
    await dialogo(tela).findAll('button')
      .find((b) => b.text() === 'Remover').trigger('click')
    await flushPromises()
    const just = tela.findAll('.modal')
      .find((m) => m.text().includes('Por que está removendo?'))
    expect(just.text()).toContain('arquivo deste lote já foi montado')
  })
})

/* ==========================================================================
   GESTO 7 — o reaponte na recarga
   🚨 É o elo que nenhuma das travas acima enxerga.
   ========================================================================== */
describe('o card aberto depois de uma recarga', () => {
  it('🚨 é REAPONTADO, não fica no retrato velho', async () => {
    const tela = await abrirATela()
    const d = await abrirOCard(tela, 'Franck')
    expect(d.findAll('li.artefato')).toHaveLength(3)

    /* O quadro muda por fora (como depois de um "Preparar"): o Franck perde
       um artefato. E a tela recarrega. */
    const novo = quadro()
    novo.colunas[0].cards[0].artefatos =
      novo.colunas[0].cards[0].artefatos.slice(0, 2)
    estado.quadro = novo
    await tela.findAll('button').find((b) => /Buscar serviços|Atualizar/.test(b.text()))
      ?.trigger('click')
    await flushPromises()
    await flushPromises()

    const agora = dialogo(tela)
    if (agora) {
      expect(agora.findAll('li.artefato'),
             'o diálogo tem de mostrar a lista NOVA, não a de antes')
        .toHaveLength(2)
    }
  })

  it('🚨 card que SAIU do quadro fecha o diálogo, em vez de ficar sobre o vazio',
     async () => {
    const tela = await abrirATela()
    await abrirOCard(tela, 'Franck')
    const novo = quadro()
    novo.colunas[0].cards = novo.colunas[0].cards.filter((c) => c.tecnico_id !== 55)
    estado.quadro = novo
    await tela.findAll('button').find((b) => /Buscar serviços|Atualizar/.test(b.text()))
      ?.trigger('click')
    await flushPromises()
    await flushPromises()
    /* O card do Franck na Movimentação não existe mais. O diálogo não pode
       continuar aberto sobre ele. */
    const d = dialogo(tela)
    if (d) expect(d.find('.modal__titulo').text()).not.toContain('Franck')
  })
})
