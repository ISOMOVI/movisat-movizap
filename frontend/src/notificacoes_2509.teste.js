/**
 * @vitest-environment jsdom
 *
 * Notificações, Plano 2 (25/09): a conversa à vista não toca, o balão do
 * Windows ("igual do MSN", nome + trecho) e o convite para ativá-lo.
 *
 * 🚨 MONTA O NOTIFICADOR (`M9`), com um `Notification` falso: o jsdom não tem.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'

import { decidirToque } from './util/regraToque.js'

let respostas
let puts
const empurrados = []

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => Promise.resolve(JSON.parse(JSON.stringify(respostas[rota] || {}))),
    put: (rota, corpo) => { puts.push({ rota, corpo }); return Promise.resolve({ ...corpo, ok: true }) },
  },
  ErroDeApi: class ErroDeApi extends Error {},
}))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: (r) => empurrados.push(r) }),
}))
const sessaoFalsa = vi.hoisted(() => ({ usuario: { owner: false }, telas: [] }))
vi.mock('./estado/sessao.js', () => ({ sessao: sessaoFalsa }))
vi.mock('./util/som.js', async () => {
  const { ref } = await import('vue')
  return {
    TONS: [{ valor: 'classico', rotulo: 'Clássico', ajuda: '' }],
    tocar: vi.fn(() => Promise.resolve(true)),
    somBloqueado: ref(false),
  }
})

import { notificacoes } from './estado/notificacoes.js'
import { adiarConvite, conviteAdiado, mostrarBalao, permissao } from './util/balao.js'
import { tocar } from './util/som.js'
import Notificador from './componentes/Notificador.vue'
import Notificacoes from './telas/Notificacoes.vue'

/* O Notification do navegador, falso: guarda o que foi mostrado. */
let mostrados
function instalarNotification(permissaoInicial = 'granted') {
  mostrados = []
  class NotificationFalso {
    constructor(titulo, opcoes) { this.titulo = titulo; this.opcoes = opcoes; this.fechado = false; mostrados.push(this) }
    close() { this.fechado = true }
  }
  NotificationFalso.permission = permissaoInicial
  NotificationFalso.requestPermission = vi.fn(async () => { NotificationFalso.permission = 'granted'; return 'granted' })
  window.Notification = NotificationFalso
  return NotificationFalso
}

function foco({ escondida, comFoco }) {
  Object.defineProperty(document, 'hidden', { value: escondida, configurable: true })
  document.hasFocus = () => comFoco
}

async function assentar(w, voltas = 5) {
  for (let i = 0; i < voltas; i++) { await new Promise((r) => setTimeout(r, 0)); await w.vm.$nextTick() }
}

const conversa = (id, n = 1) => ({ id, nao_lidas: n, nome: `Cliente ${id}`, trecho: `mensagem ${id}` })
const resposta = (naoLidas, donas = [1, 2, 3]) => ({
  ativa: true, tom: 'classico', volume: 3, abas: { minhas: naoLidas.length, time: 0 },
  donas, assumidas: naoLidas.map((id) => conversa(id)),
})

beforeEach(() => {
  puts = []
  empurrados.length = 0
  tocar.mockClear()
  notificacoes.conversaAberta = null
  try { localStorage.clear() } catch { /* sem armazenamento no ambiente */ }
  respostas = { '/api/eu/notificacoes': resposta([]) }
})
afterEach(() => {
  vi.useRealTimers()
  delete window.Notification
})

// ---- a regra ------------------------------------------------------------

describe('a conversa à vista não toca (🔵 "Só marca lida vista")', () => {
  it('a aberta e à vista não toca; outra conversa toca', () => {
    const antes = { donas: [1, 2], assumidas: [] }
    expect(decidirToque(antes, { donas: [1, 2], assumidas: [conversa(1)] }, 1).tocar).toBe(false)
    expect(decidirToque(antes, { donas: [1, 2], assumidas: [conversa(2)] }, 1))
      .toEqual({ tocar: true, motivo: 'até o teto', conversas: [2] })
  })
})

// ---- o balão ------------------------------------------------------------

describe('o balão do Windows', () => {
  it('mostra nome + trecho, com um balão por conversa (tag), e o clique abre a conversa', () => {
    instalarNotification('granted')
    const aberto = []
    mostrarBalao(conversa(7), (id) => aberto.push(id))
    expect(mostrados[0].titulo).toBe('Nova mensagem · Cliente 7')
    expect(mostrados[0].opcoes).toMatchObject({ body: 'mensagem 7', tag: 'conversa-7' })
    window.focus = () => {}
    mostrados[0].onclick()
    expect(aberto).toEqual([7])
    expect(mostrados[0].fechado).toBe(true)
  })

  it('sem permissão não mostra nada, e sem a API o estado é "indisponivel"', () => {
    instalarNotification('default')
    expect(mostrarBalao(conversa(7), () => {})).toBeNull()
    delete window.Notification
    expect(permissao()).toBe('indisponivel')
  })

  it('"Agora não" some por 7 dias', () => {
    const agora = Date.now()
    adiarConvite(agora)
    expect(conviteAdiado(agora + 6 * 24 * 3600 * 1000)).toBe(true)
    expect(conviteAdiado(agora + 8 * 24 * 3600 * 1000)).toBe(false)
  })
})

// ---- o Notificador ------------------------------------------------------

async function montarEPassar(depois) {
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
  const w = mount(Notificador)
  await assentar(w)                       // 1ª leitura: nunca toca
  respostas['/api/eu/notificacoes'] = depois
  vi.advanceTimersByTime(8000)            // 2ª leitura
  await assentar(w)
  return w
}

describe('Notificador', () => {
  it('fora de foco: toca e mostra o balão; clicar leva à conversa', async () => {
    instalarNotification('granted')
    foco({ escondida: true, comFoco: false })
    await montarEPassar(resposta([2]))
    expect(tocar).toHaveBeenCalled()
    expect(mostrados.map((m) => m.opcoes.tag)).toEqual(['conversa-2'])
    window.focus = () => {}
    mostrados[0].onclick()
    expect(empurrados).toEqual(['/atendimento/2'])
  })

  it('à vista: toca, mas sem balão', async () => {
    instalarNotification('granted')
    foco({ escondida: false, comFoco: true })
    await montarEPassar(resposta([2]))
    expect(tocar).toHaveBeenCalled()
    expect(mostrados).toHaveLength(0)
  })

  it('a conversa aberta à vista não toca', async () => {
    instalarNotification('granted')
    foco({ escondida: false, comFoco: true })
    notificacoes.conversaAberta = 2
    await montarEPassar(resposta([2]))
    expect(tocar).not.toHaveBeenCalled()
  })

  it('o convite aparece enquanto a permissão não foi respondida, e "Agora não" o esconde', async () => {
    instalarNotification('default')
    foco({ escondida: false, comFoco: true })
    const w = mount(Notificador)
    await assentar(w)
    expect(w.text()).toContain('Ativar avisos na tela')
    await w.findAll('button').find((b) => b.text() === 'Agora não').trigger('click')
    expect(w.text()).not.toContain('Ativar avisos na tela')
  })
})

// ---- a CFG_11.1 ---------------------------------------------------------

describe('CFG_11.1 — o aviso no canto da tela', () => {
  it('não ativado: o botão pede a permissão, e a tela passa a dizer "Ativado"', async () => {
    const N = instalarNotification('default')
    const w = mount(Notificacoes)
    await assentar(w)
    await w.findAll('button').find((b) => b.text().includes('Ativar neste computador')).trigger('click')
    await assentar(w)
    expect(N.requestPermission).toHaveBeenCalled()
    expect(w.text()).toContain('Ativado neste computador')
  })

  it('bloqueado: ensina onde liberar', async () => {
    instalarNotification('denied')
    const w = mount(Notificacoes)
    await assentar(w)
    expect(w.text()).toContain('Bloqueado no navegador')
    expect(w.text()).toContain('cadeado')
  })
})
