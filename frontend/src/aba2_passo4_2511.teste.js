/*
 * @vitest-environment jsdom
 *
 * PASSO 4 NA TELA — o orcamento demonstrado e as cinco chaves do Procfy.
 *
 * Ele: *"orcamento nao e impedimento e apenas vinculo demonstrado para
 * operador auditar em tela"*.
 *
 * Auditar e COMPARAR, e por isso a trava exige o TOTAL do orcamento ao lado do
 * numero: so o numero obriga a abrir outra tela para saber quanto era. E exige
 * que *"sem orcamento"* **deixe de ter cara de erro** -- alerta para algo que
 * nao impede e a tela exagerando a gravidade (`M12`).
 *
 * E as cinco chaves: elas sao lidas pelo gerador do arquivo e, ate hoje,
 * NENHUMA rota as escrevia. Coluna sem tela e dado inalcancavel.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const QUADRO = {
  titulo: 'Serviço dos técnicos',
  desde: '2026-11-16',
  varrido_em: '2026-11-25T19:05:54+00:00',
  escondidos_pela_data: 77,
  abas: [{ codigo_tela: 'PNL_1.6', titulo: 'Serviço dos técnicos' }],
  colunas: [
    {
      chave: 'movimentacao', nome: 'Movimentação',
      cards: [{
        tecnico_id: 14262, tecnico_nome: 'Franck', pode_preparar: true,
        total_pagamento: 180, total_km: 0,
        artefatos: [
          { id: 1, numero_os: 17015, valor_pagamento: 180, valor_km: 0,
            cliente: 'CLIENTE A', data_os: '18/11/2026 09:00:00',
            orcamento_numero: 3, orcamento_total: 175, semaforo: 'verde' },
          { id: 2, numero_os: 17099, valor_pagamento: 90, valor_km: 0,
            cliente: 'CLIENTE B', data_os: '19/11/2026 09:00:00',
            orcamento_numero: null, sem_orcamento: true, semaforo: 'verde' },
        ],
      }],
    },
    { chave: 'preparacao', nome: 'Preparação', cards: [] },
    { chave: 'validacao', nome: 'Validação', cards: [] },
    { chave: 'procfy', nome: 'Procfy', cards: [] },
    { chave: 'enviado', nome: 'Enviado', cards: [] },
  ],
}

const estado = { enviado: [], config: {
  procfy_categoria: '', procfy_conta_bancaria: '', procfy_modo_pagamento: '',
  procfy_centro_de_custo: '', procfy_tags: '' } }

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (url) => Promise.resolve(
      String(url).includes('config-procfy')
        ? { ...estado.config }
        : JSON.parse(JSON.stringify(QUADRO))),
    post: (url, corpo) => { estado.enviado.push([url, corpo]); return Promise.resolve({ ok: true }) },
    put: (url, corpo) => {
      estado.enviado.push([url, corpo])
      Object.assign(estado.config, corpo)
      return Promise.resolve({ ...estado.config })
    },
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
  estado.enviado.length = 0
  tela = mount(Tela, { attachTo: document.body })
  await flushPromises()
  await tela.find('.card__abrir').trigger('click')
  await flushPromises()
})
afterEach(() => tela && tela.unmount())

describe('o orçamento demonstrado (4a)', () => {
  it('mostra o TOTAL do orçamento ao lado do número', () => {
    const texto = tela.text().replace(/\s+/g, ' ')
    expect(texto).toContain('Orç 3')
    /* 175,00 é o total do orçamento 3, e 180,00 é o que se vai pagar: é
       exatamente a comparação que ele quer poder fazer na tela. */
    expect(texto).toContain('175,00')
  })

  it('"sem orçamento" NÃO tem mais cara de erro', () => {
    const sem = tela.findAll('.artefato__orcamento--sem')
    expect(sem.length).toBe(1)
    /* O ícone de alerta sai: não impede nada, então não é alarme. */
    expect(sem[0].find('i.bi-exclamation-circle').exists()).toBe(false)
    expect(sem[0].text()).toContain('sem orçamento')
  })
})

describe('as cinco chaves do Procfy (4b)', () => {
  it('a tela tem os CINCO campos', async () => {
    const campos = ['procfy_categoria', 'procfy_conta_bancaria',
                    'procfy_modo_pagamento', 'procfy_centro_de_custo',
                    'procfy_tags']
    for (const c of campos) {
      expect(tela.find(`input.campo--${c.replace(/_/g, '-')}`).exists(), c)
        .toBe(true)
    }
  })

  it('salvar manda as chaves para a rota certa', async () => {
    await tela.find('input.campo--procfy-categoria').setValue('Serviços')
    const botao = tela.findAll('button')
      .find((b) => /salvar as colunas/i.test(b.text()))
    expect(botao, 'precisa haver botão de salvar as colunas').toBeTruthy()
    await botao.trigger('click')
    await flushPromises()
    const pedido = estado.enviado.find(([u]) => String(u).includes('config-procfy'))
    expect(pedido, 'nenhum PUT para config-procfy').toBeTruthy()
    expect(pedido[1].procfy_categoria).toBe('Serviços')
  })

  it('a tela DIZ que as vazias saem em branco no arquivo', () => {
    /* Decisão dele de 18/11: o arquivo sai mesmo em branco. Então a tela não
       pode sugerir que falta algo obrigatório -- tem de dizer o que acontece. */
    expect(tela.text().toLowerCase()).toContain('em branco')
  })
})
