/*
 * @vitest-environment jsdom
 *
 * O BOTÃO SALVAR DA OBSERVAÇÃO, NUM CARD DE OS — o defeito da Karla, 27/11.
 *
 * Ele: *"verifique o pq o OBS dos cards do financeiro nao esta salvando ao
 * clicar em salvar - reportado por Karla"*.
 *
 * O DEFEITO, E ELE É SILENCIOSO. O `salvarRecado` lia
 * `ficha.chamado.solicitacao_id`. Num card de OS a ficha **não traz `chamado`
 * nenhum** -- o servidor só o monta quando o card tem `solicitacao_id` --,
 * então o `sid` vinha vazio e a função **retornava sem fazer nada**. Nenhum
 * pedido, nenhuma mensagem, nenhum erro no console: o botão parecia morto.
 *
 * MEDIDO: o Financeiro tem 13 cards que são SÓ OS, de 19. O Contratual tem
 * ZERO -- é por isso que o defeito apareceu lá e não aqui, e ficou invisível.
 *
 * É ANTERIOR À MINHA MEXIDA DE HOJE: o backup de antes tem o mesmo
 * `if (!texto || !sid) return`.
 *
 * ESTE ARQUIVO SERVE QUATRO PAINÉIS, então há trava para o caminho de OS
 * (novo) e para o de chamado (que já funcionava e não pode mudar).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

/* O card do Financeiro como o quadro o devolve: OS sim, solicitação NÃO. */
const CARD_DE_OS = {
  id: 4303, etapa_id: 885, solicitacao_id: null,
  numero_os: 17151, numero_ordem: null, os_id: null, situacao_id: null,
  cliente: 'PASTELARIA VELASCO', cliente_id: 257686,
  formulario: null, slug: null, resumo: null,
  criada_em: '2026-11-26T10:00:00-03:00', observacoes: 1, anexos: 0,
  placas: [], tecnicos: [], termo: null, termo_a_mao: false, desfecho: null,
}

const CARD_DE_CHAMADO = {
  ...CARD_DE_OS, id: 4360, numero_os: null, solicitacao_id: 6253,
  formulario: 'Aditivo contratual', slug: 'aditivo',
}

const estado = vi.hoisted(() => ({ posts: [], card: null }))

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (url) => {
      if (!String(url).includes('/chamado/')) return Promise.resolve({})
      const c = estado.card
      return Promise.resolve({
        card: { ...c },
        /* 🚨 O PONTO DO DEFEITO: card de OS NÃO tem `chamado` na ficha. */
        chamado: c.solicitacao_id
          ? { solicitacao_id: c.solicitacao_id, respostas: [], anexos: [] }
          : null,
        observacoes: [],
        historico: [],
        etapas: [{ id: 885, titulo: 'Nova solicitação' }],
      })
    },
    post: (url, corpo) => {
      estado.posts.push([url, corpo])
      /* 🚨 AS DUAS ROTAS DEVOLVEM FORMAS DIFERENTES, e o dublê respeita isso:
         a do chamado devolve `{id, observacoes}`; a da OS devolve
         `{numero_os, observacoes}` -- **sem `id`**. Quem precisa do id do
         recado novo tem de pegar o `[0]` da lista, que vem da mais nova para a
         mais velha (`ORDER BY o.em DESC` nas duas consultas). Um dublê que
         devolvesse `id` nas duas esconderia exatamente o elo que falta. */
      if (String(url).includes('/chamado/')) {
        return Promise.resolve({ id: 5001, observacoes: [] })
      }
      return Promise.resolve({
        numero_os: 17151,
        observacoes: [{ id: 5001, texto: 'o novo', em: '2026-11-27T17:00:00-03:00',
                        quem: 'Karla', anexos: [] }],
      })
    },
    put: () => Promise.resolve({}),
    del: () => Promise.resolve({}),
  },
  ErroDeApi: class ErroDeApi extends Error {},
}))

vi.mock('./estado/sessao.js', () => ({
  sessao: { nome: 'Karla', usuario: { owner: false, id: 7 }, owner: false, telas: [] },
  codigosPermitidos: { value: new Set(['PNL_1.4']) },
  sair: () => {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ meta: {}, query: {}, params: {} }),
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

import DialogoDeChamado from './componentes/DialogoDeChamado.vue'

beforeEach(() => {
  estado.posts = []
  estado.card = CARD_DE_OS
  global.fetch = vi.fn(() => Promise.resolve({
    ok: true, status: 201,
    text: () => Promise.resolve('{"id":77}'),
    json: () => Promise.resolve({ id: 77 }),
  }))
  global.localStorage.setItem('movizap.token', 'fingido')
})

async function abrir(card) {
  estado.card = card
  const d = mount(DialogoDeChamado, {
    props: { card: { ...card }, aba: 'PNL_1.4' },
  })
  await flushPromises()
  await flushPromises()
  return d
}

describe('card de OS: o Salvar precisa salvar', () => {
  it('🚨 clicar em Salvar MANDA o pedido, e não retorna em silêncio', async () => {
    const d = await abrir(CARD_DE_OS)
    await d.find('textarea').setValue('Conferido com o financeiro.')
    await d.find('.obs__salvar').trigger('click')
    await flushPromises()
    expect(estado.posts.length).toBe(1)
  })

  it('manda para a rota da OS, com o numero_os', async () => {
    /* São duas rotas, e a diferença não é estilo: a do chamado grava
       `solicitacao_id` e a da OS grava `numero_os`. O CHECK
       `os_observacao_tem_um_dono` recusa linha sem um dos dois. */
    const d = await abrir(CARD_DE_OS)
    await d.find('textarea').setValue('Conferido com o financeiro.')
    await d.find('.obs__salvar').trigger('click')
    await flushPromises()
    expect(estado.posts[0][0]).toBe('/api/paineis/operacao/observacao')
    expect(estado.posts[0][1]).toEqual(
      { numero_os: 17151, texto: 'Conferido com o financeiro.' })
  })

  it('e o anexo sobe no recado que acabou de nascer', async () => {
    /* A rota da OS devolve a LISTA, não o `id` -- e ela vem da mais nova para
       a mais velha (`ORDER BY o.em DESC`), então o novo é o `[0]`. */
    const d = await abrir(CARD_DE_OS)
    await d.find('textarea').setValue('Nota fiscal em anexo.')
    const campo = d.find('input[type="file"]')
    const arq = new File([new Uint8Array([1, 2, 3])], 'nf.pdf',
                         { type: 'application/pdf' })
    Object.defineProperty(campo.element, 'files', { value: [arq], configurable: true })
    await campo.trigger('change')
    await flushPromises()
    await d.find('.obs__salvar').trigger('click')
    await flushPromises()
    expect(global.fetch).toHaveBeenCalledTimes(1)
    expect(global.fetch.mock.calls[0][0])
      .toBe('/api/paineis/operacao/observacao/5001/anexo')
  })
})

describe('card de chamado: o que já funcionava continua igual', () => {
  it('manda para a rota do chamado, com solicitacao_id', async () => {
    /* 🚨 A trava do risco de 25/11: este diálogo serve quatro painéis, e o
       caminho que já estava certo não pode mudar de rota. */
    const d = await abrir(CARD_DE_CHAMADO)
    await d.find('textarea').setValue('texto do chamado')
    await d.find('.obs__salvar').trigger('click')
    await flushPromises()
    expect(estado.posts[0][0]).toBe('/api/paineis/operacao/chamado/observacao')
    expect(estado.posts[0][1]).toEqual(
      { solicitacao_id: 6253, texto: 'texto do chamado' })
  })
})

describe('e um card sem OS e sem solicitação não tenta nada', () => {
  it('não manda pedido, porque não há dono para o recado', async () => {
    /* ⚠️ O CHECK `os_observacao_tem_um_dono` exige OS **ou** chamado. Um card
       assim não deveria existir, mas se existir a tela não pode mandar um
       pedido que o banco vai recusar. */
    const orfao = { ...CARD_DE_OS, numero_os: null, solicitacao_id: null }
    const d = await abrir(orfao)
    await d.find('textarea').setValue('qualquer coisa')
    await d.find('.obs__salvar').trigger('click')
    await flushPromises()
    expect(estado.posts.length).toBe(0)
  })
})
