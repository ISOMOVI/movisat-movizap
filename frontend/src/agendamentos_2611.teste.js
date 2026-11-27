/**
 * @vitest-environment jsdom
 *
 * `ATD_7.1` em cartões — o selo "Visto" e o "Ir para o card", 26/11.
 *
 * 🔵 As cinco decisões dele desta volta:
 *   1. layout de **cartão por compromisso** (escolhido entre três mockups);
 *   2. *"pode ter um flag de 'Visto' para que o usuário saiba o que já viu e o
 *      que não, pois podem aparecer agendamentos no dia mesmo"* — no banco, por
 *      card e por pessoa;
 *   3. os **dois** caminhos de marcar: botão sem abrir, e ao abrir *"já
 *      confirma e avisa que confirmou também"*;
 *   4. *"o botão no card do agendamento leva para a coluna do clicado em outra
 *      aba, só isso, bem simples mesmo, já atende"*;
 *   5. *"PNL_1.1 tem tela de permissões nas configurações já pronta, deve
 *      seguir a regra dela mesmo"*.
 *
 * 🚨 O QUE UM TESTE CONSEGUE PROVAR, e só isso: que a marcação existe, que o
 * pedido sai com o corpo certo, que o `href` é o esperado e que o botão não
 * aparece sem permissão. **Placar verde não vê layout** (`M9`) — alinhamento,
 * toque de 44px e o selo em celular se provam na tela dele.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const estado = vi.hoisted(() => ({ respostas: {}, posts: [], apagados: [],
                                   navegou: [], erroNoPost: '' }))

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      const chave = Object.keys(estado.respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? estado.respostas[chave] : {})
    },
    post: (rota, corpo) => {
      estado.posts.push({ rota, corpo })
      if (estado.erroNoPost && rota.includes(estado.erroNoPost)) {
        return Promise.reject(new Error('o servidor recusou'))
      }
      return Promise.resolve(estado.respostas[rota]
        || { visto_em: '2026-11-26T08:12:00-03:00',
             visto_automatico: !!corpo?.automatico })
    },
    del: (rota) => {
      estado.apagados.push(rota)
      return Promise.resolve({ visto_em: null, visto_automatico: false })
    },
    put: () => Promise.resolve({}),
  },
  definirToken: () => {},
  temToken: () => true,
  quandoPerderSessao: () => {},
  ErroDeApi: class ErroDeApi extends Error {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, params: {}, meta: {} }),
  useRouter: () => ({
    push: (destino) => { estado.navegou.push(destino) },
    replace: (destino) => { estado.navegou.push(destino) },
  }),
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
}))

import { sessao } from './estado/sessao.js'
import Agendamentos from './telas/Agendamentos.vue'

const hoje = new Date()
const ISO = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}-${String(hoje.getDate()).padStart(2, '0')}`

function compromisso(extra = {}) {
  return {
    id: 7, inicio: `${ISO}T14:30:00`, cliente_nome: 'VELASCO',
    cliente_harmonit_id: '998063', conversa_id: 55, tecnico_nome: 'João',
    endereco: 'Rua X, 123', responsavel_cliente: 'Maria',
    orcamento_numero: 12, estado: 'confirmado',
    ordens: [{ numero_os: 17133, placa: 'FZU5D16' }],
    visto_em: null, visto_automatico: false,
    ...extra,
  }
}

async function montar(lista, telas = []) {
  estado.respostas['/api/agendamentos'] = { agendamentos: lista }
  // 🚨 A PERMISSÃO VEM DO QUE O BACKEND LISTOU, como em produção: o
  // `codigosPermitidos` é derivado de `sessao.telas`, e é ele que a tela lê.
  sessao.telas = telas.map((codigo) => ({ codigo }))
  const tela = mount(Agendamentos)
  await flushPromises()
  return tela
}

async function abrir(tela) {
  await tela.find('.agd__cartao-topo').trigger('click')
  await flushPromises()
}

beforeEach(() => {
  estado.posts = []
  estado.apagados = []
  estado.navegou = []
  estado.erroNoPost = ''
  estado.respostas = {}
  sessao.telas = []
})

describe('o cartão', () => {
  it('nasce fechado, e o cabeçalho é o que abre', async () => {
    const tela = await montar([compromisso()])
    expect(tela.find('.agd__cartao').exists()).toBe(true)
    expect(tela.find('.agd__cartao-corpo').exists()).toBe(false)
    await abrir(tela)
    expect(tela.find('.agd__cartao-corpo').exists()).toBe(true)
  })

  it('fechado diz hora, cliente e estado — o que decide', async () => {
    const tela = await montar([compromisso()])
    const topo = tela.find('.agd__cartao-topo').text()
    expect(topo).toContain('14:30')
    expect(topo).toContain('VELASCO')
    expect(topo).toContain('Confirmado')
  })

  it('aberto revela as cinco ações', async () => {
    const tela = await montar([compromisso()], ['PNL_1.1'])
    await abrir(tela)
    const textos = tela.findAll('button, a').map((n) => n.text())
    for (const acao of ['Reagendar', 'Cancelar', 'Reenviar confirmação',
                        'Abrir conversa']) {
      expect(textos.some((t) => t === acao), `faltou ${acao}`).toBe(true)
    }
    expect(textos.some((t) => t.includes('Ir para o card'))).toBe(true)
  })

  it('abrir um NÃO fecha o irmão — quem confere um confere o outro', async () => {
    const tela = await montar([compromisso(),
                               compromisso({ id: 8, cliente_nome: 'SILVA' })])
    const topos = tela.findAll('.agd__cartao-topo')
    await topos[0].trigger('click')
    await flushPromises()
    await topos[1].trigger('click')
    await flushPromises()
    expect(tela.findAll('.agd__cartao-corpo')).toHaveLength(2)
  })
})

describe('o selo Visto', () => {
  it('🚨 NOVO é a ausência de `visto_em`, e some quando há', async () => {
    const tela = await montar([compromisso()])
    expect(tela.find('.agd__selo-novo').exists()).toBe(true)
    expect(tela.find('.agd__selo-visto').exists()).toBe(false)

    const outra = await montar([compromisso({ visto_em: `${ISO}T08:12:00-03:00` })])
    expect(outra.find('.agd__selo-novo').exists()).toBe(false)
    expect(outra.find('.agd__selo-visto').text()).toContain('Visto')
  })

  it('cancelado não recebe NOVO: não há o que dar ciência', async () => {
    const tela = await montar([compromisso({ estado: 'cancelado' })])
    expect(tela.find('.agd__selo-novo').exists()).toBe(false)
  })

  it('🔵 o botão marca SEM abrir o cartão', async () => {
    const tela = await montar([compromisso()])
    await tela.findAll('button').find((b) => b.text().includes('Marcar como visto'))
      .trigger('click')
    await flushPromises()
    expect(estado.posts).toHaveLength(1)
    expect(estado.posts[0].rota).toBe('/api/agendamentos/7/visto')
    expect(estado.posts[0].corpo).toEqual({ automatico: false })
    expect(tela.find('.agd__cartao-corpo').exists()).toBe(false)
    expect(tela.find('.agd__selo-visto').exists()).toBe(true)
  })

  it('🔵 abrir marca com `automatico` e AVISA que marcou', async () => {
    const tela = await montar([compromisso()])
    await abrir(tela)
    expect(estado.posts).toHaveLength(1)
    expect(estado.posts[0].corpo).toEqual({ automatico: true })
    expect(tela.find('.agd__aviso-visto').text())
      .toContain('Marquei como visto agora')
  })

  it('o aviso traz o Desfazer, e ele chama o DELETE', async () => {
    const tela = await montar([compromisso()])
    await abrir(tela)
    await tela.find('.agd__aviso-visto').find('button').trigger('click')
    await flushPromises()
    expect(estado.apagados).toEqual(['/api/agendamentos/7/visto'])
    expect(tela.find('.agd__selo-novo').exists()).toBe(true)
    expect(tela.find('.agd__aviso-visto').exists()).toBe(false)
  })

  it('⚠️ reabrir um cartão JÁ VISTO não manda pedido nenhum', async () => {
    const tela = await montar([compromisso({ visto_em: `${ISO}T08:12:00-03:00` })])
    await abrir(tela)
    expect(estado.posts).toHaveLength(0)
  })

  it('🚨 pedido que FALHA não marca nada na tela, e diz por extenso', async () => {
    estado.erroNoPost = '/visto'
    const tela = await montar([compromisso()])
    await abrir(tela)
    expect(tela.find('.agd__selo-novo').exists()).toBe(true)
    expect(tela.find('.agd__selo-visto').exists()).toBe(false)
    expect(tela.find('.aviso--erro').text()).toContain('o servidor recusou')
  })

  it('o contador do dia conta os NÃO vistos desta pessoa', async () => {
    const tela = await montar([
      compromisso(),
      compromisso({ id: 8, visto_em: `${ISO}T08:00:00-03:00` }),
      compromisso({ id: 9 }),
    ])
    const titulo = tela.find('.agd__dia-titulo').text()
    expect(titulo).toContain('3 serviços')
    expect(titulo).toContain('2 não vistos')
  })

  it('tudo visto: o contador não desenha "0 não vistos"', async () => {
    const tela = await montar([compromisso({ visto_em: `${ISO}T08:00:00-03:00` })])
    expect(tela.find('.agd__dia-titulo').text()).not.toContain('não visto')
  })
})

describe('Ir para o card', () => {
  it('🚨 é ÂNCORA em aba nova, nunca `window.open`', async () => {
    const tela = await montar([compromisso()], ['PNL_1.1'])
    await abrir(tela)
    const link = tela.findAll('a').find((n) => n.text().includes('Ir para o card'))
    expect(link).toBeTruthy()
    expect(link.attributes('target')).toBe('_blank')
    // Sem `noopener` a aba do painel ganharia `window.opener` e poderia
    // navegar esta.
    expect(link.attributes('rel')).toContain('noopener')
  })

  it('o `href` leva a coluna de Serviço Agendado e a OS', async () => {
    const tela = await montar([compromisso()], ['PNL_1.1'])
    await abrir(tela)
    const link = tela.findAll('a').find((n) => n.text().includes('Ir para o card'))
    expect(link.attributes('href'))
      .toBe('/paineis/operacao?situacao=1316&os=17133')
  })

  it('⚠️ TODAS as OS do compromisso vão na URL, não só a primeira', async () => {
    const tela = await montar([compromisso({
      ordens: [{ numero_os: 17140, placa: 'ABC1D23' },
               { numero_os: 17141, placa: null }],
    })], ['PNL_1.1'])
    await abrir(tela)
    const link = tela.findAll('a').find((n) => n.text().includes('Ir para o card'))
    expect(link.attributes('href')).toContain('os=17140,17141')
  })

  it('🚨 SEM a PNL_1.1 concedida o botão NÃO EXISTE no DOM', async () => {
    // 🔵 *"deve seguir a regra dela mesmo"* (a CFG_15.1). Desenhar para todos
    // levaria 1 dos 9 a uma aba de "Sem permissão" — tela que promete o que
    // não entrega.
    const tela = await montar([compromisso()], ['ATD_7.1'])
    await abrir(tela)
    expect(tela.findAll('a').some((n) => n.text().includes('Ir para o card')))
      .toBe(false)
    // E as outras quatro ações continuam todas lá.
    expect(tela.findAll('button').some((b) => b.text() === 'Reagendar')).toBe(true)
  })

  it('⚠️ compromisso SEM OS não desenha o botão: não há card para onde ir',
     async () => {
    const tela = await montar([compromisso({ ordens: [] })], ['PNL_1.1'])
    await abrir(tela)
    expect(tela.findAll('a').some((n) => n.text().includes('Ir para o card')))
      .toBe(false)
  })
})

describe('o cabeçalho no padrão da casa (G2)', () => {
  it('tem `tela__cabecalho`, ajuda e o chip do código', async () => {
    const tela = await montar([])
    expect(tela.find('.tela__cabecalho').exists()).toBe(true)
    expect(tela.find('.ajuda').exists()).toBe(true)
    expect(tela.find('.chip--codigo').text()).toBe('ATD_7.1')
  })

  it('⚠️ a cobertura NÃO se perdeu ao virar ajuda: o texto continua no DOM',
     async () => {
    const tela = await montar([])
    expect(tela.text()).toContain('agendado por este painel')
    expect(tela.text()).toContain('não entra nesta lista')
  })
})
