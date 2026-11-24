/**
 * @vitest-environment jsdom
 *
 * O FILTRO DE DATA DA ABA 2, PELOS TRÊS MODOS — 23/11 (tarefa 2.6 / 2.1).
 *
 * 🔵 19/11, DEFEITO ACHADO POR ELE USANDO A TELA: *"ao usa o filtro de data na
 * aba2 os cards somem"*. O conserto de 19/11 foi duplo — o evento passou de
 * `input` para `change`, e nasceu o guarda `limiteValido` — mas **ninguém
 * repetiu o gesto depois**. O `231126.md` registrou isso como DÚVIDA DE
 * VALIDAR, e este arquivo é a medição.
 *
 * 📏 A CAUSA MEDIDA EM 19/11: o `<input type="date">` dispara `input` a cada
 * dígito do ano, então digitar 2026 produz a sequência `0002-11-19`,
 * `0020-…`, `0202-…`, `2026-…`. Com `até = 0002-11-19` TODO artefato é maior
 * que o limite e cai fora, e o card esvazia na cara de quem digita.
 *
 * 🚨 **A PERGUNTA QUE ESTE ARQUIVO RESPONDE NÃO É "a comparação está certa".**
 * É *"o card SOME ou ele FICA dizendo que está vazio?"*. Card que some sem
 * dizer por que é o sumiço que ele viu; card que fica com a frase é uma tela
 * que se explica. Lido em 23/11: o `cardsDa` só peneira card vazio **quando há
 * BUSCA DE TEXTO** (`busca.value.trim()`), não quando há filtro de data — logo
 * o card deve FICAR. É isto que se cobra abaixo, por gesto.
 *
 * 📏 Os dados são os do Franck de verdade, medidos em 23/11 no `fpsl.db`: ele
 * tem 39 itens em Movimentação, o mais novo é a OS 17124 de **16/11/2026** e o
 * mais velho vem de **05/08/2026**. A fixture usa quatro deles.
 *
 * ⚠️ A `data_os` é TEXTO `dd/mm/aaaa HH:MM:SS` no banco — não ISO. Foi essa
 * armadilha que deixou o "há 2 dias" sumido em 10 de 10 cards em 05/11, e é
 * por isso que a fixture a escreve no formato torto de propósito.
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

/* Os quatro artefatos do Franck, com a `data_os` no formato TORTO do banco. */
const DO_FRANCK = [
  { id: 101, numero_os: 16900, orcamento_numero: null, termo: null,
    data_os: '05/08/2026 09:00:00', valor_pagamento: 70, valor_km: 0,
    semaforo: 'verde', ciente_em: null, justificativa: null },
  { id: 102, numero_os: 17001, orcamento_numero: null, termo: null,
    data_os: '20/10/2026 14:00:00', valor_pagamento: 70, valor_km: 0,
    semaforo: 'verde', ciente_em: null, justificativa: null },
  { id: 103, numero_os: 17100, orcamento_numero: null, termo: null,
    data_os: '10/11/2026 11:30:00', valor_pagamento: 70, valor_km: 0,
    semaforo: 'verde', ciente_em: null, justificativa: null },
  { id: 104, numero_os: 17124, orcamento_numero: null, termo: null,
    data_os: '16/11/2026 15:35:00', valor_pagamento: 70, valor_km: 0,
    semaforo: 'verde', ciente_em: null, justificativa: null },
]

function quadro() {
  return {
    painel: 'financeiro', aba: 'PNL_1.6', titulo: 'Serviço dos técnicos',
    abas: [{ codigo_tela: 'PNL_1.6', titulo: 'Serviço dos técnicos' }],
    colunas: [
      { chave: 'movimentacao', titulo: 'Movimentação', total: 4,
        cards: [{ tecnico_id: 55, tecnico_nome: 'Franck', lote_id: null,
                  pode_preparar: true, artefatos: DO_FRANCK }] },
      { chave: 'preparacao', titulo: 'Preparação', total: 0, cards: [] },
      { chave: 'validacao', titulo: 'Validação', total: 0, cards: [] },
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
  /* 🚨 **O FILTRO MUDOU DE LUGAR em 23/11** (tarefa 2.2, pedido dele: *"dados e
     botões só no card aberto"*). Os dois campos de data saíram do card fechado
     e foram para o diálogo, então o gesto passou a ter um clique antes: abrir
     o card. Esta função o dá, e é só isso que mudou nestas 10 travas -- o que
     elas medem segue sendo o filtro, não o lugar dele. */
  const fechado = tela.findAll('article.card')
    .find((a) => a.text().includes('Franck'))
  expect(fechado, 'o card do Franck tem de estar no quadro').toBeTruthy()
  await fechado.find('button.card__abrir').trigger('click')
  await flushPromises()
  return tela
}

/* 🚨 **O CARD ABERTO**, que desde 23/11 é onde o filtro mora. Procura-se pelo
   `aria-label` do diálogo, que é o que a tela realmente declara, e o card pelo
   TEXTO -- nunca por um seletor inventado (M13). */
const cardDoFranck = (tela) =>
  tela.findAll('.modal')
    .find((m) => m.attributes('aria-label')?.includes('Card de')) || null

const osVisiveis = (tela) => {
  const card = cardDoFranck(tela)
  if (!card) return null          // null = O CARD SUMIU, que é outra coisa
  return card.findAll('li.artefato').map((li) => li.text())
    .filter((t) => /\d{5}/.test(t))
}

/* 🚨 O GESTO: os dois campos de data do card, na ordem em que a tela os põe
   (`de` primeiro, `ate` depois). Dispara-se `change`, que é o evento que a
   tela escuta desde 19/11 — disparar `input` encenaria a tela ANTIGA. */
async function digitar(tela, campo, valor) {
  const datas = cardDoFranck(tela).findAll('input[type="date"]')
  expect(datas.length, 'o card tem de ter os dois campos de data').toBe(2)
  const alvo = campo === 'de' ? datas[0] : datas[1]
  await alvo.setValue(valor)
  await alvo.trigger('change')
  await flushPromises()
}

beforeEach(() => { estado.postado = [] })

describe('o filtro de data do card, pelos três modos', () => {
  it('📏 sem filtro: os 4 artefatos do Franck aparecem', async () => {
    const tela = await abrirATela()
    expect(osVisiveis(tela)).toHaveLength(4)
  })

  it('🔵 modo 1 — SÓ "de": fica o que é igual ou mais novo', async () => {
    const tela = await abrirATela()
    await digitar(tela, 'de', '2026-11-01')
    const vistos = osVisiveis(tela)
    expect(vistos, 'o card NÃO pode sumir').not.toBeNull()
    expect(vistos).toHaveLength(2)          // 10/11 e 16/11
    expect(vistos.join(' ')).toContain('17100')
    expect(vistos.join(' ')).toContain('17124')
    expect(vistos.join(' ')).not.toContain('16900')
  })

  it('🔵 modo 2 — SÓ "até": fica o que é igual ou mais velho', async () => {
    const tela = await abrirATela()
    await digitar(tela, 'ate', '2026-10-31')
    const vistos = osVisiveis(tela)
    expect(vistos).not.toBeNull()
    expect(vistos).toHaveLength(2)          // 05/08 e 20/10
    expect(vistos.join(' ')).toContain('16900')
    expect(vistos.join(' ')).not.toContain('17124')
  })

  it('🔵 modo 3 — os DOIS: fica só a faixa', async () => {
    const tela = await abrirATela()
    await digitar(tela, 'de', '2026-10-01')
    await digitar(tela, 'ate', '2026-11-11')
    const vistos = osVisiveis(tela)
    expect(vistos).not.toBeNull()
    expect(vistos).toHaveLength(2)          // 20/10 e 10/11
    expect(vistos.join(' ')).toContain('17001')
    expect(vistos.join(' ')).toContain('17100')
  })

  it('🚨 a borda é INCLUSIVA nos dois lados — 16/11 entra num "de" de 16/11',
     async () => {
    const tela = await abrirATela()
    await digitar(tela, 'de', '2026-11-16')
    await digitar(tela, 'ate', '2026-11-16')
    const vistos = osVisiveis(tela)
    expect(vistos).toHaveLength(1)
    expect(vistos.join(' ')).toContain('17124')
  })
})

/* ==========================================================================
   O SUMIÇO — a pergunta de verdade
   ========================================================================== */
describe('quando o filtro esvazia o card', () => {
  it('🚨 o CARD FICA, e DIZ por que está vazio — não some', async () => {
    const tela = await abrirATela()
    await digitar(tela, 'de', '2026-12-01')   // depois de tudo
    const card = cardDoFranck(tela)
    /* 🚨 ESTA é a linha que separa "tela que se explica" de "sumiço". Se o
       card não estiver aqui, o defeito que ele viu em 19/11 continua vivo.
       ⚠️ E agora há DUAS coisas a cobrar, não uma: o diálogo diz que está
       vazio, E o card fechado por trás continua no quadro -- sumir do quadro
       seria o mesmo defeito num lugar novo. */
    expect(card, 'o diálogo NÃO pode desaparecer').toBeTruthy()
    expect(card.text()).toContain('Nenhum artefato à vista com este filtro')
    expect(osVisiveis(tela)).toHaveLength(0)
    expect(tela.findAll('article.card').some((a) => a.text().includes('Franck')),
           'o card fechado do Franck tem de continuar no quadro').toBe(true)
  })

  it('🚨 e limpar o filtro TRAZ os 4 de volta', async () => {
    const tela = await abrirATela()
    await digitar(tela, 'de', '2026-12-01')
    expect(osVisiveis(tela)).toHaveLength(0)
    const limpar = cardDoFranck(tela).findAll('button')
      .find((b) => /limpar/i.test(b.text()))
    expect(limpar, 'o botão de limpar o filtro tem de aparecer').toBeTruthy()
    await limpar.trigger('click')
    await flushPromises()
    expect(osVisiveis(tela)).toHaveLength(4)
  })
})

/* ==========================================================================
   O DEFEITO DE 19/11 — o ano pela metade
   🚨 Estas travas prendem o conserto que JÁ existe. Elas passam hoje; se
   alguém trocar o `change` por `input` no template, ou tirar o
   `limiteValido`, elas reprovam — e era por aí que o sintoma voltava.
   ========================================================================== */
describe('o ano digitado pela metade (o defeito de 19/11)', () => {
  it('🚨 limite com ano implausível é limite que NÃO EXISTE: nada é escondido',
     async () => {
    const tela = await abrirATela()
    /* `0002-11-19` é o que o campo produz no 1º dígito de 2026. */
    await digitar(tela, 'ate', '0002-11-19')
    const vistos = osVisiveis(tela)
    expect(vistos, 'o card não pode sumir').not.toBeNull()
    expect(vistos, 'os 4 continuam à vista').toHaveLength(4)
  })

  it('🚨 e nem `0202` nem `0020` esvaziam o card', async () => {
    for (const torta of ['0020-11-19', '0202-11-19']) {
      const tela = await abrirATela()
      await digitar(tela, 'ate', torta)
      expect(osVisiveis(tela), `com ${torta}`).toHaveLength(4)
    }
  })

  it('🚨 o campo escuta `change`, NÃO `input` — é a 1ª das duas travas de 19/11',
     async () => {
    const tela = await abrirATela()
    const datas = cardDoFranck(tela).findAll('input[type="date"]')
    /* 🚨 **NÃO SE USA `setValue` AQUI.** Medido em 23/11: o `setValue` do
       vue-test-utils dispara `change` por dentro, então ele encenaria o gesto
       COMMITADO e esta trava mediria a ferramenta, não a tela — foi assim que
       ela reprovou na primeira rodada, mostrando 2 de 4 itens.
       ⚠️ Para isolar "digitando, ainda sem commitar" mexe-se no `value` do
       elemento e dispara-se SÓ `input`. É o gesto de quem está no meio do ano. */
    datas[1].element.value = '2026-10-31'
    await datas[1].trigger('input')
    await flushPromises()
    expect(osVisiveis(tela),
           'com só `input` o filtro não vale: a tela espera o valor commitado')
      .toHaveLength(4)
  })
})
