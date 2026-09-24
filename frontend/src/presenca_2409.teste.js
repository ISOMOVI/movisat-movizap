/**
 * @vitest-environment jsdom
 *
 * Presença (24/09): jornada com copiar e duração, afastamento com
 * transferência obrigatória, regra de tempo na Geral, "sempre online" do owner.
 *
 * 🚨 MONTA AS TELAS (`M9`).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

let respostas
let puts
let posts

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      const chave = Object.keys(respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? JSON.parse(JSON.stringify(respostas[chave])) : {})
    },
    put: (rota, corpo) => { puts.push({ rota, corpo }); return Promise.resolve(respostas[rota] || corpo || {}) },
    post: (rota, corpo) => { posts.push({ rota, corpo }); return Promise.resolve({ ok: true, transferidas: 3 }) },
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
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
}))

const sessaoFalsa = vi.hoisted(() => ({ usuario: { owner: true }, telas: [] }))
vi.mock('./estado/sessao.js', () => ({ sessao: sessaoFalsa, sair: () => {} }))

import Atendentes from './telas/Atendentes.vue'
import Geral from './telas/Geral.vue'
import MinhaConta from './telas/MinhaConta.vue'

function pessoa(id, nome, extra = {}) {
  return {
    id, nome, login: nome.toLowerCase(), email: `${nome.toLowerCase()}@x.br`,
    perfil: 'atendimento', estado: 'disponivel', fuso: 'America/Sao_Paulo',
    max_conversas: null, ativo: true, owner: false, tem_senha: false, tem_foto: false,
    transferivel: true, estado_automatico: false, afastamento_motivo: null, afastado_ate: null,
    times: [], jornada: [], tem_jornada: false, em_aberto: 0, concluidas_semana: 0,
    no_horario: true, ...extra,
  }
}

function estadoPadrao() {
  return {
    '/api/atendentes': [
      pessoa(1, 'Ana', {
        em_aberto: 3,
        jornada: [{ dia_semana: 1, inicio: '08:00:00', fim: '12:00:00' }],
        tem_jornada: true,
      }),
      pessoa(2, 'Beto'),
      pessoa(3, 'Caio', { estado: 'offline' }),
    ],
    '/api/config/jornada': { jornada_ativa: false },
    '/api/config/presenca': {
      regra_ligada: false, minutos_ausente: 15, minutos_offline: 60,
      mensagem_ligada: false, mensagem_texto: '',
    },
    '/api/eu/perfil': {
      id: 9, nome: 'Dono', login: 'dono', email: 'dono@x.br', perfil: 'owner',
      estado: 'disponivel', tem_foto: false, max_conversas: null, ativo: true,
      enviar_com_enter: true, estado_automatico: false, sempre_online: false,
      afastamento_motivo: null, afastado_ate: null, tem_jornada: true, regra_de_tempo: true,
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

async function editarAna() {
  const w = mount(Atendentes, { attachTo: document.body })
  await assentar(w)
  await w.findAll('button').find((b) => b.text().includes('Editar')).trigger('click')
  await w.vm.$nextTick()
  return w
}

beforeEach(() => {
  respostas = estadoPadrao()
  puts = []
  posts = []
  sessaoFalsa.usuario.owner = true
  document.body.innerHTML = ''
})

describe('Jornada — duração e copiar', () => {
  it('mostra a duração do dia e da semana', async () => {
    const w = await editarAna()
    expect(w.find('.secao__total').text()).toBe('4h por semana')
    expect(w.findAll('.dia__duracao').map((d) => d.text())[1]).toBe('4h')
    expect(w.findAll('.dia__duracao').map((d) => d.text())[0]).toBe('folga')
  })

  it('copiar segunda para os dias úteis soma 20h na semana', async () => {
    const w = await editarAna()
    await w.findAll('button').find((b) => b.text().includes('Copiar para outros dias')).trigger('click')
    const marcados = w.findAll('.copia__dia input').filter((i) => i.element.checked)
    expect(marcados).toHaveLength(4)
    await w.findAll('.copia button').find((b) => b.text() === 'Copiar').trigger('click')
    expect(w.find('.secao__total').text()).toBe('20h por semana')
  })
})

describe('Afastamento — transferência obrigatória', () => {
  it('com conversas em aberto, só afasta depois de escolher quem recebe', async () => {
    const w = await editarAna()
    await w.findAll('button').find((b) => b.text().includes('Afastar')).trigger('click')
    await w.vm.$nextTick()
    const confirmar = w.findAll('.afastar button').find((b) => b.text().includes('Afastar e transferir 3'))
    expect(confirmar.attributes('disabled')).toBeDefined()
    await w.find('.recebedor input').setValue(true)
    expect(confirmar.attributes('disabled')).toBeUndefined()
    await confirmar.trigger('click')
    await assentar(w)
    expect(posts[0]).toEqual({ rota: '/api/atendentes/1/afastar',
      corpo: { motivo: 'Férias', ate: null, transferir_para: 2 } })
  })

  it('quem está offline não aparece para receber', async () => {
    const w = await editarAna()
    await w.findAll('button').find((b) => b.text().includes('Afastar')).trigger('click')
    await w.vm.$nextTick()
    const nomes = w.findAll('.recebedor__nome').map((n) => n.text())
    expect(nomes).toEqual(['Beto'])
  })
})

describe('Geral — regra de tempo e mensagem', () => {
  it('mensagem ligada com a jornada desligada avisa que não vai sair', async () => {
    const w = mount(Geral)
    await assentar(w)
    const caixas = w.findAll('input[type="checkbox"]')
    await caixas[2].setValue(true)
    expect(w.text()).toContain('a mensagem não sai')
  })

  it('salva as duas coisas num PUT só, com os minutos como número', async () => {
    const w = mount(Geral)
    await assentar(w)
    await w.findAll('input[type="checkbox"]')[1].setValue(true)
    await w.findAll('button').find((b) => b.text().includes('Salvar regras')).trigger('click')
    await assentar(w)
    const put = puts.find((p) => p.rota === '/api/config/presenca')
    expect(put.corpo).toMatchObject({ regra_ligada: true, minutos_ausente: 15, minutos_offline: 60 })
  })
})

describe('Minha conta — sempre online', () => {
  it('aparece para o owner', async () => {
    const w = mount(MinhaConta)
    await assentar(w)
    expect(w.text()).toContain('Sempre online')
  })

  it('não aparece para quem atende, e a frase de "não é deduzido" some com a regra ligada', async () => {
    respostas['/api/eu/perfil'] = { ...respostas['/api/eu/perfil'], perfil: 'atendimento' }
    const w = mount(MinhaConta)
    await assentar(w)
    expect(w.text()).not.toContain('Sempre online')
    expect(w.text()).not.toContain('não é deduzido')
  })
})
