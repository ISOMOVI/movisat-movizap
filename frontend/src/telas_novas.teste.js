/**
 * @vitest-environment jsdom
 *
 * As duas telas de 28/08 ABREM? — CFG_6.1 Atalhos e CFG_7.1 Geral.
 *
 * 🚨 SUITE VERDE NÃO PROVA QUE A TELA ABRE (`M9`). Hoje mesmo, três cortes de
 * texto deixaram markup inválido em três telas com 75 verdes -- porque nenhum
 * teste as montava. Estas duas nasceram hoje e ninguém as tinha montado.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

let respostas
let puts

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      const chave = Object.keys(respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? respostas[chave] : {})
    },
    put: (rota, corpo) => { puts.push({ rota, corpo }); return Promise.resolve(respostas[rota] || {}) },
    post: () => Promise.resolve({ ok: true }),
    del: () => Promise.resolve({ ok: true }),
  },
  pedirBlob: () => Promise.resolve(new Blob()),
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
  sessao: { nome: 'Fulano de Tal', telas: [], owner: false },
  sair: () => {},
}))

import Atalhos from './telas/Atalhos.vue'
import Geral from './telas/Geral.vue'
import MinhaConta from './telas/MinhaConta.vue'

const CATALOGO = [
  { acao: 'proxima', tela: 'Caixa de entrada', padrao: 'j',
    descricao: 'Próxima conversa', perigo: false },
  { acao: 'assumir', tela: 'Caixa de entrada', padrao: 'a',
    descricao: 'Assumir a conversa aberta', perigo: true,
    aviso: 'Assume na hora, sem perguntar.' },
  { acao: 'email_arquivar', tela: 'E-mail', padrao: 'e',
    descricao: 'Arquivar a mensagem aberta', perigo: true,
    aviso: 'Arquiva na hora, sem perguntar.' },
]

function estadoPadrao() {
  return {
    '/api/eu/atalhos': {
      ligados: false,
      teclas: { proxima: 'j', assumir: 'a', email_arquivar: 'e' },
      catalogo: CATALOGO,
    },
    '/api/config/jornada': { jornada_ativa: false },
    '/api/eu/perfil': {
      id: 7, nome: 'Fulano de Tal', login: 'fulano',
      email: 'fulano@movisat.com.br', perfil: 'atendimento',
      estado: 'disponivel', tem_foto: false, fuso: 'America/Sao_Paulo',
      max_conversas: null, ativo: true, enviar_com_enter: false,
      estados_possiveis: ['disponivel', 'ausente', 'nao_perturbe', 'offline'],
    },
  }
}

async function assentar(w, voltas = 5) {
  for (let i = 0; i < voltas; i++) {
    await new Promise((r) => setTimeout(r, 0))
    await w.vm.$nextTick()
  }
}

beforeEach(() => { respostas = estadoPadrao(); puts = [] })

describe('CFG_6.1 — Atalhos', () => {
  it('a tela abre e mostra as ações agrupadas por tela', async () => {
    const w = mount(Atalhos)
    await assentar(w)
    expect(w.text()).toContain('Atalhos de teclado')
    expect(w.text()).toContain('Caixa de entrada')
    expect(w.text()).toContain('E-mail')
    expect(w.text()).toContain('Próxima conversa')
  })

  it('🚨 nasce DESLIGADO e a tela diz isso', async () => {
    const w = mount(Atalhos)
    await assentar(w)
    expect(w.text()).toContain('desligados')
    expect(w.find('input[type="checkbox"]').element.checked).toBe(false)
  })

  it('avisa que há atalhos que agem sem perguntar ANTES de ligar', async () => {
    const w = mount(Atalhos)
    await assentar(w)
    expect(w.text()).toContain('agem sem perguntar')
    expect(w.text()).toContain('age direto')
  })

  it('ligar chama a rota', async () => {
    respostas['/api/eu/atalhos/ligados'] = {
      ligados: true, teclas: { proxima: 'j' }, catalogo: CATALOGO,
    }
    const w = mount(Atalhos)
    await assentar(w)
    await w.find('input[type="checkbox"]').trigger('change')
    await assentar(w)
    expect(puts.some((p) => p.rota.endsWith('/ligados') && p.corpo.ligados === true)).toBe(true)
  })
})

describe('CFG_7.1 — Geral', () => {
  it('a tela abre com os dois interruptores', async () => {
    const w = mount(Geral)
    await assentar(w)
    expect(w.text()).toContain('jornada dos atendentes')
    expect(w.text()).toContain('Pedir nota de 1 a 5')
  })

  it('🚨 a avaliação aparece TRAVADA, dizendo o que falta', async () => {
    const w = mount(Geral)
    await assentar(w)
    const caixas = w.findAll('input[type="checkbox"]')
    const travada = caixas.find((c) => c.attributes('disabled') !== undefined)
    expect(travada).toBeTruthy()
    expect(w.text()).toContain('ainda não existe no atendimento')
  })

  it('a jornada liga pela rota', async () => {
    respostas['/api/config/jornada'] = { jornada_ativa: false }
    const w = mount(Geral)
    await assentar(w)
    const jornada = w.findAll('input[type="checkbox"]')
      .find((c) => c.attributes('disabled') === undefined)
    await jornada.trigger('change')
    await assentar(w)
    expect(puts.some((p) => p.rota === '/api/config/jornada')).toBe(true)
  })
})

/* ==========================================================================
   CFG_10.1 — Minha conta (17/09).

   🚨 MONTA DE VERDADE, porque foi assim que se descobriu, em 28/08, que duas
   telas novas tinham markup quebrado com a suíte inteira verde.
   ========================================================================== */
describe('CFG_10.1 — Minha conta', () => {
  it('abre e mostra os quatro blocos', async () => {
    const w = mount(MinhaConta)
    await assentar(w)
    expect(w.text()).toContain('Como você está')
    expect(w.text()).toContain('Sua foto')
    expect(w.text()).toContain('Como você envia')
    expect(w.text()).toContain('Seus dados')
  })

  it('🚨 mostra o RÓTULO, não o valor do banco', async () => {
    /* `nao_perturbe` é o que o CHECK aceita; quem atende lê "Não perturbe".
       Mostrar nome de coluna na tela foi erro real em outras telas. */
    const w = mount(MinhaConta)
    await assentar(w)
    expect(w.text()).toContain('Não perturbe')
    expect(w.text()).toContain('Fora do expediente')
    expect(w.text()).not.toContain('nao_perturbe')
  })

  it('trocar de estado chama a rota de "eu"', async () => {
    const w = mount(MinhaConta)
    await assentar(w)
    const pausa = w.findAll('button').find((b) => b.text().includes('Em pausa'))
    await pausa.trigger('click')
    await assentar(w)
    const chamada = puts.find((p) => p.rota === '/api/eu/estado')
    expect(chamada).toBeTruthy()
    expect(chamada.corpo).toEqual({ estado: 'ausente' })
  })

  it('sem foto, cai nas iniciais do nome', async () => {
    const w = mount(MinhaConta)
    await assentar(w)
    expect(w.find('img').exists()).toBe(false)
    expect(w.text()).toContain('FT')          // Fulano de Tal
  })

  it('com foto, desenha a imagem do atendente', async () => {
    respostas['/api/eu/perfil'] = { ...estadoPadrao()['/api/eu/perfil'], tem_foto: true }
    const w = mount(MinhaConta)
    await assentar(w)
    const img = w.find('img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toContain('/api/atendentes/7/foto')
  })

  it('o tipo de envio usa a MESMA rota da CFG_6.1', async () => {
    /* Espelho, não cópia: duas portas para o mesmo quarto. */
    const w = mount(MinhaConta)
    await assentar(w)
    await w.find('input[type="checkbox"]').trigger('change')
    await assentar(w)
    expect(puts.some((p) => p.rota === '/api/eu/enviar-com-enter')).toBe(true)
  })
})
