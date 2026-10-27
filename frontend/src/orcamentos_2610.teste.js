/**
 * @vitest-environment jsdom
 *
 * A aba Orçamentos (ORC_1.1, 26/10) ABRE e diz a verdade?
 *
 * 🚨 SUITE VERDE NÃO PROVA QUE A TELA ABRE (`M9`). E aqui há uma segunda coisa
 * a provar: a aba é SÓ DE CONSULTA, e tem de DIZER isso. Aba de grid sem
 * botão de ação parece tela pela metade -- o precedente é o card do `PNL_1.1`,
 * que escreve por que não se arrasta.
 *
 * 🚨 E a terceira: o dinheiro chega ESCRITO do backend. Se um dia alguém puser
 * um `/ 100` aqui, passa a haver duas regras de arredondamento no projeto, e o
 * grid divergiria do PDF.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

let respostas
let gets
let blobs

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      gets.push(rota)
      const chave = Object.keys(respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? respostas[chave] : {})
    },
    post: () => Promise.resolve({ ok: true }),
    put: () => Promise.resolve({ ok: true }),
    del: () => Promise.resolve({ ok: true }),
  },
  pedirBlob: (rota) => {
    blobs.push(rota)
    return Promise.resolve(new Blob(['%PDF-1.4']))
  },
  definirToken: () => {},
  temToken: () => true,
  quandoPerderSessao: () => {},
  ErroDeApi: class ErroDeApi extends Error {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, params: {} }),
  useRouter: () => ({ replace: () => {}, push: () => {} }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('./estado/sessao.js', () => ({
  sessao: { nome: 'Fulano de Tal', telas: [], owner: true },
  sair: () => {},
}))

import Orcamentos from './telas/Orcamentos.vue'

const FILTROS = {
  tecnicos: [{ contato_id: 91041, tecnico: 'Iago Santos do Ó Souza', orcamentos: 3 }],
  atendentes: [{ atendente_id: 121, nome: 'Iago', orcamentos: 3 }],
}

/* Os três orçamentos REAIS de 26/10, com os números que a medição deu. */
const TRES = {
  itens: [
    {
      id: 284, numero: 3, criado_em: '2026-10-23T10:31:04-03:00',
      total_centavos: 17500, total: '175,00',
      tecnico: 'Iago Santos do Ó Souza', atendente: 'Iago',
      ordens_os: [17015, 17016], midia_id: 8610, conversa_id: 12845,
      agendamento: null,
      itens: [
        { ordem: 1, servico: 'KM DESLOCAMENTO', quantidade_texto: '15 km',
          preco_unit: '1,00', valor: '15,00' },
        { ordem: 2, servico: 'PAGAMENTO DE TECNICO', quantidade_texto: '2 un',
          preco_unit: '80,00', valor: '160,00' },
      ],
    },
    {
      id: 103, numero: 2, criado_em: '2026-10-21T15:11:45-03:00',
      total_centavos: 19700, total: '197,00',
      tecnico: 'Iago Santos do Ó Souza', atendente: 'Iago',
      ordens_os: [16991], midia_id: 7905, conversa_id: 12845,
      agendamento: { id: 211, inicio: '2026-10-21T15:11:00-03:00',
                     estado: 'confirmado', cliente_nome: 'Velasco Leite Pastelaria ME' },
      itens: [
        { ordem: 1, servico: 'KM DESLOCAMENTO', quantidade_texto: '77 km',
          preco_unit: '1,00', valor: '77,00' },
        { ordem: 2, servico: 'PAGAMENTO DE TECNICO', quantidade_texto: '1 un',
          preco_unit: '120,00', valor: '120,00' },
      ],
    },
    {
      id: 22, numero: 1, criado_em: '2026-10-21T09:40:03-03:00',
      total_centavos: 25700, total: '257,00',
      tecnico: 'Iago Santos do Ó Souza', atendente: 'Iago',
      ordens_os: [], midia_id: null, conversa_id: 12845, agendamento: null,
      itens: [
        { ordem: 1, servico: 'KM DESLOCAMENTO', quantidade_texto: '77 km',
          preco_unit: '1,00', valor: '77,00' },
      ],
    },
  ],
  total: 3, pagina: 1, por_pagina: 50, paginas: 1,
  soma_centavos: 62900, soma: '629,00',
}

const VAZIO = {
  itens: [], total: 0, pagina: 1, por_pagina: 50, paginas: 1,
  soma_centavos: 0, soma: '0,00',
}

async function montar() {
  const tela = mount(Orcamentos)
  await new Promise((r) => setTimeout(r, 0))
  await tela.vm.$nextTick()
  return tela
}

describe('A aba Orçamentos', () => {
  beforeEach(() => {
    gets = []
    blobs = []
    respostas = { '/api/orcamentos/filtros': FILTROS, '/api/orcamentos': TRES }
    /* ⚠️ O jsdom NÃO implementa `URL.createObjectURL`/`revokeObjectURL` --
       sem estes dois, abrir o PDF cai no `catch` da tela e o teste acusaria
       um defeito que só existe no ambiente de teste. O navegador tem os dois.
       (A tela guarda a url e a solta no `onUnmounted`, e é isso que estes
       dublês deixam exercitar.) */
    URL.createObjectURL = () => 'blob:orcamento-de-teste'
    URL.revokeObjectURL = () => {}
  })

  it('abre e mostra os orçamentos', async () => {
    const tela = await montar()
    const texto = tela.text()
    expect(texto).toContain('Orçamentos')
    expect(texto).toContain('3 orçamentos')
    expect(texto).toContain('Iago Santos do Ó Souza')
  })

  /* 🚨 O que esta aba NÃO faz, escrito. É a entrega, não enfeite. */
  it('diz que é só de consulta, e diz ONDE se emite', async () => {
    const tela = await montar()
    const texto = tela.text()
    expect(texto).toContain('só de consulta')
    expect(texto).toContain('não se edita')
    expect(texto).toContain('conversa do técnico')
  })

  it('não oferece botão de editar, cancelar nem emitir', async () => {
    const tela = await montar()
    const botoes = tela.findAll('button').map((b) => b.text().toLowerCase())
    for (const proibido of ['editar', 'cancelar', 'emitir', 'excluir', 'apagar']) {
      expect(botoes.some((t) => t.includes(proibido))).toBe(false)
    }
  })

  /* 🚨 O dinheiro vem escrito do backend. */
  it('mostra o valor como o backend escreveu, e a soma do filtro', async () => {
    const tela = await montar()
    const texto = tela.text()
    expect(texto).toContain('R$ 175,00')
    expect(texto).toContain('R$ 629,00')
  })

  it('mostra a quantidade com a MESMA frase do PDF', async () => {
    const tela = await montar()
    const texto = tela.text()
    expect(texto).toContain('15 km')
    expect(texto).toContain('2 un')
    /* "15.000 km" é o que sairia se a tela formatasse por conta. */
    expect(texto).not.toContain('15.000 km')
  })

  it('mostra as OS do documento, e "sem OS" quando não há', async () => {
    const tela = await montar()
    const texto = tela.text()
    expect(texto).toContain('17015')
    expect(texto).toContain('17016')
    expect(texto).toContain('sem OS')
  })

  /* "Sem agendamento" é o estado COMUM (1 de 3 em 26/10), não defeito. */
  it('mostra o agendamento quando existe, sem inventar quando não', async () => {
    const tela = await montar()
    const texto = tela.text()
    expect(texto).toContain('confirmado')
    expect(texto).toContain('Velasco Leite Pastelaria ME')
  })

  it('quem não tem PDF diz "sem PDF" em vez de oferecer botão que falha', async () => {
    const tela = await montar()
    expect(tela.text()).toContain('sem PDF')
  })

  it('o PDF sai pela rota de mídia que já existia, não por rota nova', async () => {
    const tela = await montar()
    const abrir = tela.findAll('button').find((b) => b.text().includes('abrir'))
    await abrir.trigger('click')
    await new Promise((r) => setTimeout(r, 0))
    await tela.vm.$nextTick()
    /* 🚨 ESTA É A AFIRMAÇÃO QUE IMPORTA: o PDF vem de `/api/midia/{id}/ver`,
       que já existia e já serve quem tem `ATD_1.2`. Rota nova de PDF seria um
       segundo caminho para o mesmo arquivo. */
    expect(blobs).toContain('/api/midia/8610/ver')
    /* O visor abre DENTRO da tela: nova aba com blob é bloqueada por
       bloqueador de pop-up, e o clique pareceria não fazer nada. */
    expect(tela.find('iframe').exists()).toBe(true)
  })

  it('o estado vazio diz onde o orçamento nasce', async () => {
    respostas = { '/api/orcamentos/filtros': FILTROS, '/api/orcamentos': VAZIO }
    const tela = await montar()
    const texto = tela.text()
    expect(texto).toContain('Nenhum orçamento neste filtro')
    expect(texto).toContain('Agendar')
  })

  it('pede a lista e os seletores, e nada mais', async () => {
    await montar()
    expect(gets.some((r) => r.startsWith('/api/orcamentos?'))).toBe(true)
    expect(gets).toContain('/api/orcamentos/filtros')
  })

  /* ⚠️ Com uma página só, a paginação não aparece -- botão que não leva a
     lugar nenhum é pior que botão nenhum. */
  it('não desenha paginação quando há uma página só', async () => {
    const tela = await montar()
    expect(tela.find('.orc__paginacao').exists()).toBe(false)
  })

  it('desenha paginação quando há mais de uma página', async () => {
    respostas = {
      '/api/orcamentos/filtros': FILTROS,
      '/api/orcamentos': { ...TRES, paginas: 3, total: 120 },
    }
    const tela = await montar()
    expect(tela.find('.orc__paginacao').exists()).toBe(true)
  })
})
