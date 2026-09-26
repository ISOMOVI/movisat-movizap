/**
 * @vitest-environment jsdom
 *
 * Notificações (24/09): a regra de QUANDO toca, e a tela CFG_11.1.
 *
 * 🔵 *"se a pessoa como ela tiver 20 conversas, só vai tocar 4 vezes. Se tiver
 * 2, vai tocar 2"* · *"ou entrar uma nova, dai toca uma vez só e para"* ·
 * *"só aparece ao Owner"*.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

import { decidirToque, TETO } from './util/regraToque.js'

let respostas
let puts

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => Promise.resolve(JSON.parse(JSON.stringify(respostas[rota] || {}))),
    put: (rota, corpo) => { puts.push({ rota, corpo }); return Promise.resolve({ ...corpo, ok: true, notificacao_ativa: corpo.ativa }) },
  },
  ErroDeApi: class ErroDeApi extends Error {},
}))

const sessaoFalsa = vi.hoisted(() => ({ usuario: { owner: false }, telas: [] }))
vi.mock('./estado/sessao.js', () => ({ sessao: sessaoFalsa }))
vi.mock('./util/som.js', async () => {
  const { ref } = await import('vue')
  return {
    TONS: [{ valor: 'classico', rotulo: 'Clássico', ajuda: '' }, { valor: 'sino', rotulo: 'Sino', ajuda: '' }],
    tocar: vi.fn(() => Promise.resolve(true)),
    somBloqueado: ref(false),
  }
})

import Notificacoes from './telas/Notificacoes.vue'

// ---- a regra -------------------------------------------------------------

const lida = (id) => ({ id, nao_lidas: 0 })
const naoLida = (id, n = 1) => ({ id, nao_lidas: n })
const estado = (donas, naoLidas) => ({ donas, assumidas: naoLidas.map((id) => naoLida(id)) })

describe('regra do toque', () => {
  it('a primeira leitura depois de abrir o painel NUNCA toca (senão todo F5 tocaria)', () => {
    expect(decidirToque(null, estado([1, 2], [1, 2])).tocar).toBe(false)
  })

  it('com 2 conversas, cada uma que recebe mensagem toca: "se tiver 2, vai tocar 2"', () => {
    const a = estado([1, 2], [])
    const b = estado([1, 2], [1])
    const c = estado([1, 2], [1, 2])
    expect(decidirToque(a, b).tocar).toBe(true)
    expect(decidirToque(b, c).tocar).toBe(true)
  })

  it('mensagem nova numa conversa que JÁ estava não lida não toca de novo', () => {
    const a = { donas: [1], assumidas: [naoLida(1, 1)] }
    const b = { donas: [1], assumidas: [naoLida(1, 3)] }
    expect(decidirToque(a, b).tocar).toBe(false)
  })

  it(`com 20 conversas, toca até ${TETO} e depois fica só o número`, () => {
    const donas = Array.from({ length: 20 }, (_, i) => i + 1)
    let antes = estado(donas, [])
    let toques = 0
    for (let i = 1; i <= 20; i++) {
      const depois = estado(donas, donas.slice(0, i))
      if (decidirToque(antes, depois).tocar) toques++
      antes = depois
    }
    expect(toques).toBe(TETO)
  })

  it('acima do teto, conversa NOVA para mim toca uma vez: "entrar uma nova, dai toca uma vez só"', () => {
    const cinco = [1, 2, 3, 4, 5]
    const antes = estado(cinco, cinco)
    const depois = estado([...cinco, 99], [...cinco, 99])
    expect(decidirToque(antes, depois))
      .toEqual({ tocar: true, motivo: 'conversa nova acima do teto', conversas: [99] })
    // e na leitura seguinte ela já é "minha": não toca de novo
    expect(decidirToque(depois, depois).tocar).toBe(false)
  })

  it('conversa lida voltando a ter mensagem, lida por lida', () => {
    expect(decidirToque({ donas: [7], assumidas: [lida(7)] }, estado([7], [7])).tocar).toBe(true)
  })
})

// ---- a tela -------------------------------------------------------------

async function assentar(w) {
  for (let i = 0; i < 5; i++) { await new Promise((r) => setTimeout(r, 0)); await w.vm.$nextTick() }
}

beforeEach(() => {
  puts = []
  sessaoFalsa.usuario.owner = false
  respostas = {
    '/api/eu/notificacoes': { ativa: true, tom: 'classico', volume: 3, abas: { minhas: 0, time: 0 }, assumidas: [], donas: [] },
    '/api/notificacoes/equipe': [{ id: 5, nome: 'Ana', perfil: 'atendimento', notificacao_ativa: true }],
  }
})

describe('CFG_11.1 — Notificações', () => {
  it('quem atende escolhe tom e volume, e NÃO vê o bloco do owner', async () => {
    const w = mount(Notificacoes)
    await assentar(w)
    expect(w.text()).toContain('Seu som')
    expect(w.text()).not.toContain('Quem recebe notificação')
    await w.findAll('.nivel')[4].trigger('click')
    await assentar(w)
    expect(puts[0]).toEqual({ rota: '/api/eu/notificacao', corpo: { tom: 'classico', volume: 5 } })
  })

  it('o volume vai de 1 a 5, sem mudo', async () => {
    const w = mount(Notificacoes)
    await assentar(w)
    expect(w.findAll('.nivel').map((b) => b.text())).toEqual(['1', '2', '3', '4', '5'])
  })

  it('piscar a aba aparece marcado e travado', async () => {
    const w = mount(Notificacoes)
    await assentar(w)
    const fixo = w.find('.fixo input')
    expect(fixo.element.checked).toBe(true)
    expect(fixo.attributes('disabled')).toBeDefined()
  })

  it('o owner vê quem recebe e desliga alguém', async () => {
    sessaoFalsa.usuario.owner = true
    const w = mount(Notificacoes)
    await assentar(w)
    expect(w.text()).toContain('Quem recebe notificação')
    await w.find('.equipe input').trigger('change')
    await assentar(w)
    expect(puts[0]).toEqual({ rota: '/api/atendentes/5/notificacao', corpo: { ativa: false } })
  })

  it('desligada pelo owner, a própria pessoa é avisada', async () => {
    respostas['/api/eu/notificacoes'].ativa = false
    const w = mount(Notificacoes)
    await assentar(w)
    expect(w.text()).toContain('desligadas')
    expect(w.text()).not.toContain('owner')
  })
})
