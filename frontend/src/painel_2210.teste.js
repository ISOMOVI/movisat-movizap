/**
 * @vitest-environment jsdom
 *
 * O painel da Operação (PNL_1.1), opção A — 22/10.
 *
 * 🔵 Escolha dele entre três mockups: *"vamos de A somente para a Operação
 * por enquanto"*.
 *
 * 🚨 ISTO É DOM, NÃO LAYOUT. O `M9` continua valendo: nenhum teste aqui vê 13
 * colunas caberem na tela, nem a cor, nem se rola bem no celular. O que se
 * prova é o que uma entrega futura pode perder calada:
 *
 *   · a coluna "Sem situação" EXISTIR -- ela nasceu de 164 OS reais que não
 *     estão em nenhuma das 11 situações, e perdê-la esconde dado;
 *   · coluna vazia nascer COLAPSADA, e as duas primeiras nunca colapsarem;
 *   · NÃO haver gesto de arrastar enquanto a escrita no Harmonit não existe --
 *     e a tela DIZER por quê;
 *   · a situação crua (0) aparecer no card em vez de um rótulo inventado.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const estado = vi.hoisted(() => ({ quadro: null, empurrado: [] }))

vi.mock('./api/cliente.js', () => ({
  api: { get: () => Promise.resolve(estado.quadro) },
  ErroDeApi: class ErroDeApi extends Error {},
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: (destino) => estado.empurrado.push(destino) }),
  useRoute: () => ({ query: {} }),
}))

import PainelOperacao from './telas/PainelOperacao.vue'

const SITUACOES = [38, 251, 677, 890, 1316, 15694, 15695, 15696, 15746, 15747, 15797]

function quadro({ cards = {}, podeMover = false } = {}) {
  const colunas = [
    { chave: 'sem_os', titulo: 'Sem OS', situacao_id: null, nota: 'ainda não virou OS', cards: cards.sem_os || [] },
    { chave: 'sem_situacao', titulo: 'Sem situação', situacao_id: null, nota: 'tem OS, situação 0 ou nula', cards: cards.sem_situacao || [] },
    ...SITUACOES.map((sid) => ({
      chave: `s${sid}`, titulo: `Situação ${sid}`, situacao_id: sid, nota: null,
      cards: cards[`s${sid}`] || [],
    })),
  ]
  for (const coluna of colunas) coluna.total = coluna.cards.length
  return {
    painel: 'operacao',
    titulo: 'Operação',
    formularios: [
      { codigo: 'SUPORTE', titulo: 'Suporte', campos: 13, ativo: true },
      { codigo: 'CREDENCIAMENTO', titulo: 'Credenciamento', campos: 34, ativo: true },
    ],
    colunas,
    total: colunas.reduce((soma, c) => soma + c.total, 0),
    pode_mover: podeMover,
    porque_nao_move: 'Mover o card vai escrever a situação na OS do Harmonit, e essa rota ainda não existe.',
  }
}

const card = (extra = {}) => ({
  id: 7, formulario: 'Suporte', slug: 'suporte', criada_em: '2026-10-22T14:02:00-03:00',
  estado: 'nova', cliente: 'Cliente de exemplo', resumo: 'zz · prova',
  anexos: 0, os_id: null, numero_ordem: null, situacao_id: null, situacao_em: null,
  ...extra,
})

async function abrir(dados) {
  estado.quadro = dados
  const tela = mount(PainelOperacao)
  await flushPromises()
  return tela
}

beforeEach(() => {
  estado.empurrado = []
})

describe('as colunas', () => {
  it('sao as 11 situacoes mais Sem OS e Sem situacao', async () => {
    const tela = await abrir(quadro())
    expect(tela.findAll('.coluna')).toHaveLength(13)
    const titulos = tela.findAll('.coluna__titulo').map((n) => n.text())
    expect(titulos[0]).toContain('Sem OS')
    expect(titulos[1]).toContain('Sem situação')
  })

  it('🚨 a coluna Sem situacao existe mesmo vazia -- 164 OS reais moram nela', async () => {
    const tela = await abrir(quadro())
    const coluna = tela.find('.coluna--sem-situacao')
    expect(coluna.exists()).toBe(true)
    // Aberta: o corpo com a nota aparece, mesmo sem card.
    expect(coluna.text()).toContain('tem OS, situação 0 ou nula')
  })

  it('coluna vazia nasce colapsada e a com card nasce aberta', async () => {
    const tela = await abrir(quadro({ cards: { s15746: [card({ id: 9, os_id: 1, situacao_id: 15746 })] } }))
    const colunas = tela.findAll('.coluna')
    const comCard = colunas.find((c) => c.text().includes('Situação 15746'))
    const vazia = colunas.find((c) => c.text().includes('Situação 251'))
    expect(comCard.classes()).not.toContain('coluna--fechada')
    expect(vazia.classes()).toContain('coluna--fechada')
    // 🚨 Colapsada mostra o CONTADOR: ninguém precisa abrir para saber que é zero.
    expect(vazia.find('.coluna__conta').text()).toBe('0')
  })

  it('as duas primeiras nao tem botao de colapsar', async () => {
    const tela = await abrir(quadro())
    const fixas = tela.findAll('.coluna__botao--fixo')
    expect(fixas).toHaveLength(2)
  })

  it('clicar no cabecalho abre e fecha uma coluna vazia', async () => {
    const tela = await abrir(quadro())
    const vazia = tela.findAll('.coluna').find((c) => c.text().includes('Situação 251'))
    await vazia.find('.coluna__botao').trigger('click')
    expect(vazia.classes()).not.toContain('coluna--fechada')
    expect(vazia.text()).toContain('situação 251 no Harmonit')
  })
})

describe('mover o card', () => {
  it('🚨 nao existe gesto de arrastar enquanto a escrita no Harmonit nao existe', async () => {
    const tela = await abrir(quadro({ cards: { sem_os: [card()] } }))
    expect(tela.html()).not.toContain('draggable')
  })

  it('e a tela DIZ por que, em vez de ficar calada', async () => {
    const tela = await abrir(quadro({ cards: { sem_os: [card()] } }))
    expect(tela.text()).toContain('escrever a situação na OS do Harmonit')
  })
})

describe('o card', () => {
  it('leva a solicitacao e a OS, com a situacao CRUA', async () => {
    const tela = await abrir(quadro({
      cards: { sem_situacao: [card({ id: 12, os_id: 555, numero_ordem: '17042', situacao_id: 0 })] },
    }))
    const texto = tela.find('.card__abrir').text()
    expect(texto).toContain('Suporte')
    expect(texto).toContain('Cliente de exemplo')
    expect(texto).toContain('OS 17042')
    // 🚨 Zero é um valor que existe em 127 OS: aparece como 0, não como "—".
    expect(texto).toContain('situação 0')
  })

  it('OS sem situacao lida diz isso, e nao finge um numero', async () => {
    const tela = await abrir(quadro({
      cards: { sem_situacao: [card({ id: 13, os_id: 556, situacao_id: null })] },
    }))
    expect(tela.find('.card__abrir').text()).toContain('situação nunca lida')
  })

  it('o estado vem escrito, nao so na cor', async () => {
    const tela = await abrir(quadro({ cards: { sem_os: [card({ estado: 'em_andamento' })] } }))
    expect(tela.find('.etiqueta').text()).toBe('Em andamento')
  })

  it('clicar manda para a ficha na FRM_1.1', async () => {
    const tela = await abrir(quadro({ cards: { sem_os: [card({ id: 42 })] } }))
    await tela.find('.card__abrir').trigger('click')
    expect(estado.empurrado).toEqual([
      { path: '/solicitacoes', query: { solicitacao: 42 } },
    ])
  })
})

describe('painel vazio', () => {
  it('diz que o estado certo e vazio, em vez de parecer quebrado', async () => {
    const tela = await abrir(quadro())
    expect(tela.text()).toContain('Nenhuma solicitação da Operação chegou ainda')
    // E mostra de quais formulários ele é feito, com a contagem de campos.
    expect(tela.text()).toContain('Credenciamento')
    expect(tela.text()).toContain('34 campos')
  })
})
