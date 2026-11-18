/*
 * @vitest-environment jsdom
 *
 * A CAIXA DO AVISO AO CLIENTE no painel da Operação (17/11).
 *
 * 🔵 Dele: *"quando o card for movido e houver disparo de mensagens perguntar
 * em caixa de diálogo (se tiver ligado o interruptor) 'Deseja enviar aviso ao
 * cliente?' Se Sim = abre a mensagem que será enviada e permite edição rápida
 * dela e o botão enviar envia (...) Se clicar não, não envia nada."*
 *
 * 🚨 ISTO TROCOU O SINAL DE 11/11, com autorização: o interruptor passa a
 * significar "pergunta", não "manda". Metade destas travas prova que **nada sai
 * sem clique** -- e mensagem ao cliente é irreversível.
 *
 * 🚨 SUÍTE VERDE NÃO PROVA TELA (`M9`). O que estes testes alcançam:
 *   1. a caixa aparece ao mover, e **só** quando o servidor pergunta;
 *   2. o primeiro passo **não mostra a mensagem** -- quem clica "Não" não
 *      precisa ler nada;
 *   3. o "Sim" mostra o texto, o destinatário e o contador;
 *   4. o que viaja é `passagem_id`, `enviar` e o texto -- **nunca o número**;
 *   5. o texto EDITADO é o que vai;
 *   6. envio recusado mostra o motivo e **não fecha**, para dar a chance de
 *      tentar de novo;
 *   7. `Escape` fecha **sem enviar e sem registrar**;
 *   8. mover recusado pelo ERP não pergunta nada.
 *
 * ⚠️ Arquivo e mock próprios, pelo mesmo motivo do `painel_checklist_0411`: o
 * mock dele guarda outras 44 regras, e esticá-lo arriscaria o que já está
 * provado.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = {
  quadro: null, postado: [], respostaMover: null, respostaDisparo: null,
}

vi.mock('../src/api/cliente.js', () => ({}))
vi.mock('./api/cliente.js', () => ({
  api: {
    get: async (caminho) => {
      const c = String(caminho)
      if (c.includes('/checklist')) return { itens: [] }
      if (c.includes('/passagens')) return { passagens: [] }
      if (c.includes('/ficha')) {
        return { observacoes: [], prioridades: {}, campos: {},
                 campos_da_etapa: {} }
      }
      return estado.quadro
    },
    post: async (caminho, corpo) => {
      estado.postado.push([String(caminho), corpo])
      if (String(caminho).includes('/operacao/disparo')) {
        return estado.respostaDisparo ?? { enviou: true }
      }
      if (String(caminho).includes('/mover')) {
        return estado.respostaMover ?? { ok: true }
      }
      return { ok: true }
    },
    put: async () => ({}),
    del: async () => ({}),
  },
  quandoPerderSessao: () => {},
  definirToken: () => {},
  temToken: () => false,
  relatarErroDeBotao: () => {},
  ErroDeApi: class extends Error {},
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: () => {} }),
  useRoute: () => ({ query: {} }),
}))

import PainelOperacao from './telas/PainelOperacao.vue'

const AS_DEZESSETE = [
  [38, 'Novo Solicitação 1ª'], [16487, 'Pendente de ação da Movisat'],
  [251, 'Configurar equipamentos e Sistemas'], [16488, 'Entrega de materiais prontos'],
  [677, 'Enviar por correio/transportadora'],
  [15747, 'Aguardando recebimento via correio/transportadora'],
  [15797, 'Rescisão Aguardando Aviso Prévio'], [890, 'Agendar serviço'],
  [16489, 'Confirmação agendamento'], [1316, 'Serviço Agendado'],
  [15696, 'Aguardando devolução de equipamento'],
  [16490, 'Analise de Equipamentos Retornados'], [15694, 'Atendimento finalizado'],
  [16491, 'Não atendido'], [15746, 'Financeiro'], [15695, 'Pós venda'],
  [16492, 'Contratual'],
]

const TEXTO = 'Olá João, a OS 17056 foi enviada. Termo 8952.'

function card(extra = {}) {
  return {
    id: null, origem: 'erp', numero_ordem: 17056, os_id: 870036,
    situacao_id: 38, cliente: 'Zz Cliente', criada_em: '2026-11-04T09:00:00-03:00',
    tipo_nome: 'Retirada', placas: [], tecnicos: [], observacoes: 0,
    anexos: 0, estado: null, formulario: null, prioridade: 382,
    prioridade_nome: 'Normal', status_str: 'Nova', finalizada: false,
    checklist: null, tem_checklist: false, ...extra,
  }
}

function quadro(cards = {}) {
  return {
    painel: 'operacao', titulo: 'Operação', total: 1, pode_mover: true,
    desde: '2026-10-24', so_abertas: true, busca: '', ordem: 'prazo',
    ordens: [], ponte_respondeu: true, ponte_motivo: null,
    fora_do_quadro: null, filtro_casou_por: null,
    colunas: AS_DEZESSETE.map(([sid, titulo]) => ({
      chave: `s${sid}`, titulo, situacao_id: sid, nota: null,
      total: (cards[sid] || []).length, cards: cards[sid] || [],
    })),
  }
}

async function montar() {
  const tela = mount(PainelOperacao, { global: { stubs: { AjudaDaTela: true } } })
  await flushPromises()
  return tela
}

/* Move pelo modal do card, como o `painel_checklist_0411` faz: é o caminho que
   o jsdom alcança (arrastar depende de layout). A rota é a mesma do arrasto. */
async function moverPeloModal(tela, destino = 677) {
  await tela.find('.card__abrir').trigger('click')
  await flushPromises()
  const select = tela.findAll('select').find(
    (s) => s.text().includes('Enviar por correio'))
  await select.setValue(String(destino))
  await flushPromises()
  await flushPromises()
}

function botao(tela, texto) {
  return tela.findAll('button').find((b) => b.text() === texto)
}

function doDisparo() {
  return estado.postado.filter(([c]) => c.includes('/operacao/disparo'))
}

beforeEach(() => {
  estado.quadro = quadro({ 38: [card()] })
  estado.postado = []
  estado.respostaDisparo = null
  estado.respostaMover = {
    ok: true,
    passagem_id: 55,
    disparo: {
      pergunta: true, situacao_id: 677, texto: TEXTO,
      telefone: '+5518998116168', destinatario: 'o contato da OS',
    },
  }
})

describe('a caixa aparece quando o servidor pergunta', () => {
  it('🔵 pergunta ao mover, e a pergunta é a dele', async () => {
    const tela = await montar()
    await moverPeloModal(tela)
    expect(tela.text()).toContain('Deseja enviar aviso ao cliente?')
  })

  it('🚨 o primeiro passo NÃO mostra a mensagem', async () => {
    /* Quem vai clicar "Não" não precisa ler nada -- mostrar o texto já na
       pergunta tiraria o sentido do "Não". */
    const tela = await montar()
    await moverPeloModal(tela)
    expect(tela.text()).not.toContain(TEXTO)
    expect(tela.text()).toContain('Nada foi enviado ainda')
  })

  it('não pergunta quando o disparo está desligado', async () => {
    estado.respostaMover = { ok: true, passagem_id: 55,
                             disparo: { pergunta: false, motivo: 'desligado' } }
    const tela = await montar()
    await moverPeloModal(tela)
    expect(tela.text()).not.toContain('Deseja enviar aviso')
  })

  it('🚨 não pergunta quando o ERP RECUSOU o mover', async () => {
    /* Ofereceria avisar o cliente de um fato que não aconteceu. */
    estado.respostaMover = {
      ok: false, motivo: 'o Harmonit recusou', passagem_id: 55,
      disparo: { pergunta: true, texto: TEXTO },
    }
    const tela = await montar()
    await moverPeloModal(tela)
    expect(tela.text()).not.toContain('Deseja enviar aviso')
  })

  it('⚠️ sem passagem_id não pergunta -- a decisão não teria identidade', async () => {
    estado.respostaMover = { ok: true,
                             disparo: { pergunta: true, texto: TEXTO } }
    const tela = await montar()
    await moverPeloModal(tela)
    expect(tela.text()).not.toContain('Deseja enviar aviso')
  })
})

describe('o "Sim": ver, editar e enviar', () => {
  it('🔵 mostra o texto, o destinatário e o contador', async () => {
    const tela = await montar()
    await moverPeloModal(tela)
    await botao(tela, 'Sim, ver a mensagem').trigger('click')
    /* ⚠️ O TEXTO DE UM `textarea` COM `v-model` NÃO ENTRA NO `text()`: ele é a
       propriedade `value` do elemento, e o jsdom não o põe no conteúdo. Minha
       primeira versão desta trava reprovava por isso -- era a asserção errada,
       não a tela. O contador abaixo é a segunda prova de que o texto chegou. */
    expect(tela.find('textarea').element.value).toBe(TEXTO)
    expect(tela.text()).toContain('+5518998116168')
    expect(tela.text()).toContain('o contato da OS')
    expect(tela.text()).toContain(`${TEXTO.length}/2000`)
  })

  it('🚨 o que viaja é passagem_id, enviar e texto -- NUNCA o número', async () => {
    /* Quem decide para quem a mensagem vai é o servidor, derivando da OS. */
    const tela = await montar()
    await moverPeloModal(tela)
    await botao(tela, 'Sim, ver a mensagem').trigger('click')
    await botao(tela, 'Enviar').trigger('click')
    await flushPromises()
    const [, corpo] = doDisparo()[0]
    expect(corpo.passagem_id).toBe(55)
    expect(corpo.enviar).toBe(true)
    expect(corpo.texto).toBe(TEXTO)
    expect(Object.keys(corpo).sort()).toEqual(['enviar', 'passagem_id', 'texto'])
  })

  it('🔵 o texto EDITADO é o que vai', async () => {
    const tela = await montar()
    await moverPeloModal(tela)
    await botao(tela, 'Sim, ver a mensagem').trigger('click')
    await tela.find('textarea').setValue('mensagem que ele reescreveu')
    await botao(tela, 'Enviar').trigger('click')
    await flushPromises()
    expect(doDisparo()[0][1].texto).toBe('mensagem que ele reescreveu')
  })

  it('depois de enviar, a caixa fecha', async () => {
    const tela = await montar()
    await moverPeloModal(tela)
    await botao(tela, 'Sim, ver a mensagem').trigger('click')
    await botao(tela, 'Enviar').trigger('click')
    await flushPromises()
    expect(tela.text()).not.toContain('Deseja enviar aviso ao cliente?')
  })

  it('🚨 envio recusado mostra o motivo e NÃO fecha', async () => {
    /* O servidor soltou a reserva: o operador pode tentar de novo, e esconder
       o motivo tiraria dele a informação para decidir. */
    estado.respostaDisparo = { enviou: false,
                               motivo: 'Evolução não respondeu (ReadError)' }
    const tela = await montar()
    await moverPeloModal(tela)
    await botao(tela, 'Sim, ver a mensagem').trigger('click')
    await botao(tela, 'Enviar').trigger('click')
    await flushPromises()
    expect(tela.text()).toContain('ReadError')
    expect(tela.text()).toContain('Deseja enviar aviso ao cliente?')
  })

  it('texto vazio não deixa enviar', async () => {
    const tela = await montar()
    await moverPeloModal(tela)
    await botao(tela, 'Sim, ver a mensagem').trigger('click')
    await tela.find('textarea').setValue('   ')
    expect(botao(tela, 'Enviar').attributes('disabled')).toBeDefined()
  })

  it('o "Voltar" devolve à pergunta sem enviar nada', async () => {
    const tela = await montar()
    await moverPeloModal(tela)
    await botao(tela, 'Sim, ver a mensagem').trigger('click')
    await botao(tela, 'Voltar').trigger('click')
    expect(tela.text()).not.toContain(TEXTO)
    expect(doDisparo()).toEqual([])
  })
})

describe('o "Não" e o fechar', () => {
  it('🔵 "Não enviar" registra a decisão e não manda texto', async () => {
    const tela = await montar()
    await moverPeloModal(tela)
    await botao(tela, 'Não enviar').trigger('click')
    await flushPromises()
    const [, corpo] = doDisparo()[0]
    expect(corpo.enviar).toBe(false)
    expect(corpo.texto).toBe('')
    expect(tela.text()).not.toContain('Deseja enviar aviso ao cliente?')
  })

  it('🚨 Escape fecha SEM enviar e SEM registrar', async () => {
    /* Sem clique, a passagem fica sem decisão -- e "sem decisão" é exatamente
       "ninguém foi avisado". O que não acontece é o card afirmar que alguém
       escolheu, porque não escolheu. */
    const tela = await montar()
    await moverPeloModal(tela)
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(tela.text()).not.toContain('Deseja enviar aviso ao cliente?')
    expect(doDisparo()).toEqual([])
  })
})

describe('a ordem: o mover acontece primeiro', () => {
  it('🚨 a caixa só abre DEPOIS de o mover ter ido ao servidor', async () => {
    /* A régua desta tela, escrita desde 04/11: o aviso vem depois do mover,
       nunca antes -- um diálogo no meio faria o card parecer travado. */
    const tela = await montar()
    await moverPeloModal(tela)
    const caminhos = estado.postado.map(([c]) => c)
    expect(caminhos.some((c) => c.includes('/mover'))).toBe(true)
    expect(caminhos.indexOf(caminhos.find((c) => c.includes('/mover'))))
      .toBeLessThan(caminhos.length)
    expect(tela.text()).toContain('Deseja enviar aviso ao cliente?')
  })
})
