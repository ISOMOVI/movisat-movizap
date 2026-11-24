/**
 * @vitest-environment jsdom
 *
 * ===========================================================================
 * A OS NO CARD ABERTO DAS ABAS — 19/11
 * ===========================================================================
 * 🔵 Dele: *"nos cards do financeiro, aba1, faltam trazer os dados das OS para
 * os cards, no menu da direita do card aberto"* · *"igual os cards que são de
 * OS do operacional"*.
 *
 * 🚨 O DEFEITO ERA DE OMISSÃO, o mesmo formato do card cru de 18/11: o
 * diálogo das abas lia só o nosso banco, e a coluna da direita tinha apenas as
 * passagens de etapa. A Operação mostrava quatro temas da OS desde 29/10.
 *
 * ⚠️ E ESTES TESTES OLHAM O TEXTO NA TELA, não a existência do campo no JSON:
 * foi assim que o card cru passou despercebido — o dado estava lá e não era
 * desenhado.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = vi.hoisted(() => ({ card: null, os: null, osFalha: false,
                                   pedidos: [] }))

vi.mock('./api/cliente.js', () => {
  class ErroDeApi extends Error {}
  return {
    api: {
      get: (caminho) => {
        estado.pedidos.push(caminho)
        if (caminho.endsWith('/os')) {
          return estado.osFalha
            ? Promise.reject(new ErroDeApi('não deu para ler a OS 17134'))
            : Promise.resolve(estado.os)
        }
        return Promise.resolve(estado.card)
      },
      post: () => Promise.resolve({}),
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
  useRoute: () => ({ meta: {}, query: {}, params: {} }),
  useRouter: () => ({ push: () => {}, replace: () => {} }),
}))

import DialogoDeChamado from './componentes/DialogoDeChamado.vue'

/* O que a `/chamado/{id}` devolve: o nosso banco, sem nada do ERP. */
const FICHA_DO_CARD = {
  card: { id: 2645, etapa_id: 875, desfecho: null, desfecho_em: null },
  etapas: [{ id: 875, titulo: 'Nova solicitação' },
           { id: 876, titulo: 'Em análise' }],
  observacoes: [],
  historico: [],
  chamado: null,
}

/* O que a `/chamado/{id}/os` devolve: a OS no Harmonit. */
const A_OS = {
  numero_os: 17134,
  descricao: 'Instalar rastreador na UVO 8E01',
  solucao_tecnica: null,
  tem_agendamento: false,
  agendamentos: [],
  chamado: null,
  observacoes: [],
}

/* O card de OS em etapa nossa: `numero_os` cheio, `numero_ordem` NULO. */
function cardDeOS(extra = {}) {
  return { id: 2645, numero_os: 17134, numero_ordem: null, situacao_id: null,
           cliente: 'Zz Pastelaria Velasco', desfecho: null, desfecho_em: null,
           telefone: null, ...extra }
}

async function montar(card) {
  const tela = mount(DialogoDeChamado, { props: { card } })
  await flushPromises()
  await flushPromises()
  return tela
}

beforeEach(() => {
  estado.card = FICHA_DO_CARD
  estado.os = A_OS
  estado.osFalha = false
  estado.pedidos = []
})

describe('a OS no card aberto de uma aba', () => {
  it('pede a ficha da OS PELO CARD, e não por número de fora', async () => {
    await montar(cardDeOS())
    expect(estado.pedidos).toContain('/api/paineis/operacao/chamado/2645/os')
    /* 🚨 Nunca a rota da Operação: ela exige `PNL_1.1`, que quem opera o
       Financeiro pode não ter. */
    expect(estado.pedidos.join(' ')).not.toContain('/api/paineis/operacao/ficha')
  })

  it('mostra os quatro temas e o texto da descrição', async () => {
    const tela = await montar(cardDeOS())
    const texto = tela.text()
    expect(texto).toContain('A OS no Harmonit')
    expect(texto).toContain('OS 17134')
    expect(texto).toContain('Descrição da OS')
    expect(texto).toContain('Solução técnica')
    expect(texto).toContain('Dados do chamado')
    expect(texto).toContain('Agendamento')
    expect(texto).toContain('Instalar rastreador na UVO 8E01')
  })

  it('diz o vazio em vez de deixar a caixa em branco', async () => {
    const tela = await montar(cardDeOS())
    /* A solução técnica é nula na maioria das OS: o resumo tem de DIZER. */
    expect(tela.text()).toContain('sem solução técnica escrita')
  })

  it('o Agendamento nasce apagado quando a OS não tem compromisso', async () => {
    const tela = await montar(cardDeOS())
    const abas = tela.findAll('.temas__aba')
    const agendamento = abas[abas.length - 1]
    expect(agendamento.text()).toContain('Agendamento')
    expect(agendamento.attributes('disabled')).toBeDefined()
    /* 🚨 E DIZ POR QUÊ: botão cinza e calado é o que ele recusou em 18/11. */
    expect(agendamento.text()).toContain('nenhum compromisso nesta OS')
  })

  it('acende o Agendamento quando há compromisso', async () => {
    estado.os = { ...A_OS, tem_agendamento: true,
                  agendamentos: [{ agendamento_id: 930447, nome: 'Franck',
                                   usuario_id: 7493 }] }
    const tela = await montar(cardDeOS())
    const abas = tela.findAll('.temas__aba')
    expect(abas[abas.length - 1].attributes('disabled')).toBeUndefined()
  })

  /* 🔵 23/11, DELE: *"os agendamentos feitos por aqui no Movizap, continuam
     não sendo escritos nas OS, precisamos de um definitivo para isso!"*

     🚨 A MEDIÇÃO CONTRADISSE O SINTOMA: a escrita estava completa (ERP com
     `start 23/11 16:00` e `end 18:00`, técnico 14262). O que esta tela
     mostrava era *"usuário 14262 — compromisso 969544"* — sem nome e sem
     data. Concluir "não foi escrito" era a leitura certa do que a tela
     mostrava: tela que mente por omissão (`M12`).

     ⚠️ A janela vem PRONTA do backend (`janela`), porque o mesmo bloco é
     desenhado em três telas e formatar em três lugares é o gêmeo nascendo
     outra vez. */
  it('🔵 o compromisso diz QUEM e QUANDO, não só o número', async () => {
    estado.os = { ...A_OS, tem_agendamento: true,
                  agendamentos: [{ agendamento_id: 969544, nome: 'Franck',
                                   usuario_id: 14262,
                                   janela: '23/11/2026 16:00 às 18:00' }] }
    const tela = await montar(cardDeOS())
    const abas = tela.findAll('.temas__aba')
    await abas[abas.length - 1].trigger('click')
    const texto = tela.text()
    expect(texto).toContain('Franck')
    expect(texto).toContain('23/11/2026 16:00 às 18:00')
    /* O id continua: é por ele que se confere no ERP. */
    expect(texto).toContain('969544')
    /* 🚨 E o "usuário 14262" NÃO aparece mais: era o sintoma. */
    expect(texto).not.toContain('usuário 14262')
  })

  it('⚠️ compromisso sem janela não inventa data', async () => {
    estado.os = { ...A_OS, tem_agendamento: true,
                  agendamentos: [{ agendamento_id: 969544, nome: 'Franck',
                                   usuario_id: 14262, janela: null }] }
    const tela = await montar(cardDeOS())
    const abas = tela.findAll('.temas__aba')
    await abas[abas.length - 1].trigger('click')
    expect(tela.text()).toContain('969544')
    expect(tela.text()).not.toContain('null')
  })

  it('falha do Harmonit vira ERRO escrito, nunca caixa vazia', async () => {
    estado.osFalha = true
    const tela = await montar(cardDeOS())
    expect(tela.text()).toContain('não deu para ler a OS 17134')
    /* ⚠️ E o card continua de pé: ele é lido do NOSSO banco. */
    expect(tela.text()).toContain('Passagens de etapa')
  })

  it('o chamado de verdade não ganha a caixa nem pede a rota', async () => {
    const tela = await montar(cardDeOS({ numero_os: null }))
    expect(tela.text()).not.toContain('A OS no Harmonit')
    expect(estado.pedidos.join(' ')).not.toContain('/os')
  })
})
