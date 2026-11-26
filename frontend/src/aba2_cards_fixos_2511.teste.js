/*
 * @vitest-environment jsdom
 *
 * OS DOIS CARDS FIXOS DO SEM-TECNICO, na tela — 25/11.
 *
 * Ele: *"'SEM IDENTIFICACAO' como ja tem e 'NAO CADASTRADOS NO HARMONIT' para
 * os sem cadastro - o que nao impede em juntar as demais informacoes
 * corretamente, pois em caso de correcao e atualizacao, o card ja direciona"*.
 *
 * O que estas travas prendem e o DIRECIONAR: nao basta o card existir, ele tem
 * de dizer QUEM foi, senao a pessoa nao sabe o que corrigir. O nome vem por
 * artefato (`tecnico_provisorio`), porque o card e fixo e junta varios.
 *
 * E prendem o que NAO pode aparecer: botao de preparar em card que nao paga.
 * Ele foi explicito -- *"nao conhecidos nao paga isso, e nem sem
 * identificacao"*.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const QUADRO = {
  titulo: 'Serviço dos técnicos',
  desde: '2026-11-16',
  varrido_em: '2026-11-25T19:05:54+00:00',
  escondidos_pela_data: 77,
  abas: [{ codigo_tela: 'PNL_1.4', titulo: 'Financeiro' },
         { codigo_tela: 'PNL_1.6', titulo: 'Serviço dos técnicos' }],
  colunas: [
    {
      chave: 'movimentacao',
      nome: 'Movimentação',
      cards: [
        {
          tecnico_id: null,
          tecnico_nome: 'não cadastrados no Harmonit',
          pode_preparar: false,
          total_pagamento: 89.1,
          total_km: 0,
          artefatos: [{
            id: 90, numero_os: 17133, valor_pagamento: 89.1, valor_km: 0,
            cliente: 'CLIENTE DE CURITIBA', data_os: '18/11/2026 09:00:00',
            tecnico_provisorio: 'Jonas Claudio dos Santos',
            semaforo: 'verde',
          }],
        },
        {
          tecnico_id: null,
          tecnico_nome: 'sem técnico identificado',
          pode_preparar: false,
          total_pagamento: 50,
          total_km: 0,
          artefatos: [{
            id: 91, numero_os: 99001, valor_pagamento: 50, valor_km: 0,
            cliente: 'OUTRO CLIENTE', data_os: '19/11/2026 09:00:00',
            semaforo: 'verde',
          }],
        },
      ],
    },
    { chave: 'preparacao', nome: 'Preparação', cards: [] },
    { chave: 'validacao', nome: 'Validação', cards: [] },
    { chave: 'procfy', nome: 'Procfy', cards: [] },
    { chave: 'enviado', nome: 'Enviado', cards: [] },
  ],
}

vi.mock('./api/cliente.js', () => ({
  api: {
    get: vi.fn(async () => JSON.parse(JSON.stringify(QUADRO))),
    post: vi.fn(async () => ({ ok: true })),
    put: vi.fn(async () => ({ ok: true })),
  },
  ErroDeApi: class extends Error {},
}))

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

const Tela = (await import('./telas/PainelServicoDosTecnicos.vue')).default

let tela
beforeEach(async () => {
  tela = mount(Tela, { attachTo: document.body })
  await flushPromises()
})
afterEach(() => tela && tela.unmount())

describe('os dois cards fixos', () => {
  it('a tela mostra OS DOIS cards, com os nomes dele', () => {
    const texto = tela.text()
    expect(texto).toContain('não cadastrados no Harmonit')
    expect(texto).toContain('sem técnico identificado')
  })

  it('o card novo DIZ QUEM FOI — senão não dá para corrigir nada', () => {
    expect(tela.text()).toContain('Jonas Claudio dos Santos')
  })

  it('o nome provisório aparece COMO PROVISÓRIO, não como técnico do card',
    () => {
      /* O titulo do card e o nome FIXO; o nome da pessoa e por artefato.
         Se o provisorio virasse titulo, o segundo provisorio no mesmo card
         ficaria escondido atras do nome do primeiro. */
      const cards = tela.findAll('.card')
      const oNovo = cards.find((c) => c.text()
        .includes('não cadastrados no Harmonit'))
      expect(oNovo).toBeTruthy()
      expect(oNovo.text()).toContain('provisório')
      expect(oNovo.text()).toContain('Jonas Claudio dos Santos')
    })

  it('NENHUM dos dois oferece preparar — ele foi explícito', async () => {
    for (const nome of ['não cadastrados no Harmonit',
                        'sem técnico identificado']) {
      const cards = tela.findAll('.card')
      const alvo = cards.find((c) => c.text().includes(nome))
      const botoes = alvo.findAll('button')
        .filter((b) => /preparar/i.test(b.text()))
      expect(botoes.length, `${nome} não pode oferecer preparar`).toBe(0)
    }
  })

  it('o card sem provisório NÃO inventa a palavra provisório', () => {
    const cards = tela.findAll('.card')
    const antigo = cards.find((c) => c.text()
      .includes('sem técnico identificado'))
    expect(antigo.text()).not.toContain('provisório')
  })
})
