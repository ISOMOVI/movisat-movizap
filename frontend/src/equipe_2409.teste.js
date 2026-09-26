/**
 * @vitest-environment jsdom
 *
 * Atendentes, Times e Minha conta — a rodada de 24/09.
 *
 * 🔵 Pedidos dele: o Editar abre um modal que PERGUNTA antes de descartar
 * ("Descartar" / "Continuar editando"), com "Salvar" e "Cancelar alterações"
 * no fim; e-mail só para owner e admin; login só para o owner; nome
 * editável por todos na Minha conta; os times se vinculam na tela de Times.
 *
 * 🚨 MONTA AS TELAS (`M9`): suíte verde sem montar não prova que abrem.
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
      return Promise.resolve(chave ? respostas[chave] : {})
    },
    put: (rota, corpo) => { puts.push({ rota, corpo }); return Promise.resolve(respostas[rota] || { id: 1, nome: 'X' }) },
    post: (rota, corpo) => { posts.push({ rota, corpo }); return Promise.resolve({ id: 99, nome: corpo?.nome || 'X' }) },
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

const sessaoFalsa = vi.hoisted(() => ({ usuario: { owner: false }, telas: [] }))
vi.mock('./estado/sessao.js', () => ({ sessao: sessaoFalsa, sair: () => {} }))

import ModalEdicao from './componentes/ModalEdicao.vue'
import Atendentes from './telas/Atendentes.vue'
import Times from './telas/Times.vue'
import MinhaConta from './telas/MinhaConta.vue'

const ANA = {
  id: 1, nome: 'Ana Souza', login: 'ana', email: 'ana@movisat.com.br',
  perfil: 'atendimento', estado: 'disponivel', fuso: 'America/Sao_Paulo',
  max_conversas: null, ativo: true, owner: false, tem_senha: false, tem_foto: false,
  times: [{ id: 10, nome: 'Suporte' }], jornada: [], tem_jornada: false,
  em_aberto: 3, concluidas_semana: 12, no_horario: true,
}
const DONO = { ...ANA, id: 2, nome: 'Dono', login: 'dono', perfil: 'owner', owner: true, times: [] }

function estadoPadrao() {
  return {
    '/api/atendentes': [ANA, DONO],
    '/api/config/jornada': { jornada_ativa: false },
    '/api/times': [{
      id: 10, nome: 'Suporte', descricao: 'Dúvidas', ativo: true,
      time_transbordo_id: null, transbordo_nome: null, qtd_membros: 1,
      membros: [{ id: 1, nome: 'Ana Souza', ativo: true, transferivel: true }],
      na_fila: 2, quem_ve: [],
    }],
    '/api/operacao/alertas': [],
    '/api/eu/perfil': {
      id: 1, nome: 'Ana Souza', login: 'ana', email: 'ana@movisat.com.br',
      perfil: 'atendimento', estado: 'disponivel', tem_foto: false,
      max_conversas: null, ativo: true, enviar_com_enter: true,
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

beforeEach(() => {
  respostas = estadoPadrao()
  puts = []
  posts = []
  sessaoFalsa.usuario.owner = false
  document.body.innerHTML = ''
})

// ------------------------------------------------------------ o modal

describe('ModalEdicao — pergunta antes de jogar fora', () => {
  function montar(sujo) {
    return mount(ModalEdicao, { props: { titulo: 'Editar', sujo }, attachTo: document.body })
  }
  function clicarNoFundo(w) {
    const fundo = w.find('.modal')
    fundo.trigger('mousedown')
    fundo.trigger('click')
  }

  it('sem mudança, clicar fora fecha direto', async () => {
    const w = montar(false)
    clicarNoFundo(w)
    expect(w.emitted('fechar')).toHaveLength(1)
    expect(w.text()).not.toContain('Descartar as alterações?')
  })

  it('com mudança, clicar fora PERGUNTA, com os dois botões pedidos', async () => {
    const w = montar(true)
    clicarNoFundo(w)
    await w.vm.$nextTick()
    expect(w.emitted('fechar')).toBeUndefined()
    const botoes = w.findAll('.edicao__pergunta button').map((b) => b.text())
    expect(botoes).toEqual(['Descartar', 'Continuar editando'])
  })

  it('"Continuar editando" volta ao formulário; "Descartar" fecha', async () => {
    const w = montar(true)
    clicarNoFundo(w)
    await w.vm.$nextTick()
    await w.findAll('.edicao__pergunta button')[1].trigger('click')
    expect(w.find('.edicao__pergunta').exists()).toBe(false)
    expect(w.emitted('fechar')).toBeUndefined()
    clicarNoFundo(w)
    await w.vm.$nextTick()
    await w.findAll('.edicao__pergunta button')[0].trigger('click')
    expect(w.emitted('fechar')).toHaveLength(1)
  })

  it('arrastar uma seleção de dentro para fora NÃO conta como clique fora', async () => {
    const w = montar(true)
    await w.find('.edicao__caixa').trigger('mousedown')
    await w.find('.modal').trigger('click')
    expect(w.find('.edicao__pergunta').exists()).toBe(false)
  })

  it('o rodapé tem "Salvar" e "Cancelar alterações", nessa ordem', () => {
    const w = montar(false)
    expect(w.findAll('.edicao__rodape button').map((b) => b.text()))
      .toEqual(['Salvar', 'Cancelar alterações'])
  })

  it('"Cancelar alterações" fecha sem perguntar, mesmo com mudança', async () => {
    const w = montar(true)
    await w.findAll('.edicao__rodape button')[1].trigger('click')
    expect(w.emitted('fechar')).toHaveLength(1)
  })
})

// ------------------------------------------------------------ Atendentes

describe('CAD_2.1 — Atendentes', () => {
  async function abrirEdicaoDaAna(w) {
    const editar = w.findAll('button').find((b) => b.text().includes('Editar'))
    await editar.trigger('click')
    await w.vm.$nextTick()
  }

  it('abre, e o Editar abre o MODAL (não um cartão no meio da tela)', async () => {
    const w = mount(Atendentes, { attachTo: document.body })
    await assentar(w)
    expect(w.text()).toContain('Ana Souza')
    await abrirEdicaoDaAna(w)
    expect(w.find('[role="dialog"]').exists()).toBe(true)
  })

  it('para o admin: sem Login, com E-mail, e o perfil sem owner nem admin', async () => {
    const w = mount(Atendentes, { attachTo: document.body })
    await assentar(w)
    expect(w.findAll('.pessoa__linha.mono')).toHaveLength(0)
    await abrirEdicaoDaAna(w)
    const rotulos = w.findAll('.edicao__corpo .campo__rotulo').map((r) => r.text())
    expect(rotulos).toContain('E-mail')
    expect(rotulos).not.toContain('Login')
    const opcoes = w.findAll('.edicao__corpo select').at(0).findAll('option').map((o) => o.attributes('value'))
    expect(opcoes).toEqual(['atendimento', 'cadastro'])
  })

  it('para o owner: com Login, e o perfil oferece admin mas não owner', async () => {
    sessaoFalsa.usuario.owner = true
    const w = mount(Atendentes, { attachTo: document.body })
    await assentar(w)
    await abrirEdicaoDaAna(w)
    const rotulos = w.findAll('.edicao__corpo .campo__rotulo').map((r) => r.text())
    expect(rotulos).toContain('Login')
    const opcoes = w.findAll('.edicao__corpo select').at(0).findAll('option').map((o) => o.attributes('value'))
    expect(opcoes).toEqual(['admin', 'atendimento', 'cadastro'])
  })

  it('o admin não tem Editar na linha do owner', async () => {
    const w = mount(Atendentes, { attachTo: document.body })
    await assentar(w)
    const editar = w.findAll('button').filter((b) => b.text().includes('Editar'))
    expect(editar).toHaveLength(1)
  })

  it('os times aparecem só para leitura: nenhuma caixinha de time no modal', async () => {
    const w = mount(Atendentes, { attachTo: document.body })
    await assentar(w)
    await abrirEdicaoDaAna(w)
    expect(w.find('.edicao__corpo').text()).toContain('Suporte')
    // 25/09: o interruptor Ativo/Inativo é `role="switch"`, não caixinha de time.
    expect(w.findAll('.edicao__corpo input[type="checkbox"]:not([role="switch"])')).toHaveLength(0)
  })

  it('conta nova criada pelo admin nasce com o login igual ao e-mail', async () => {
    const w = mount(Atendentes, { attachTo: document.body })
    await assentar(w)
    await w.findAll('button').find((b) => b.text().includes('Novo atendente')).trigger('click')
    await w.vm.$nextTick()
    const [nome, email] = w.findAll('.edicao__corpo input')
    await nome.setValue('Beto')
    await email.setValue('beto@movisat.com.br')
    await w.findAll('.edicao__rodape button')[0].trigger('click')
    await assentar(w)
    expect(posts[0].corpo.login).toBe('beto@movisat.com.br')
  })

  it('"sem senha" não vira aviso: quem tem e-mail entra pelo Google', async () => {
    const w = mount(Atendentes, { attachTo: document.body })
    await assentar(w)
    expect(w.text()).not.toContain('sem senha')
    expect(w.text()).toContain('Google')
  })
})

// ------------------------------------------------------------ Times

describe('CAD_2.2 — Times', () => {
  it('o Editar abre o modal com os atendentes marcados, e salvar grava os membros', async () => {
    respostas['/api/times/10'] = { id: 10, nome: 'Suporte' }
    const w = mount(Times, { attachTo: document.body })
    await assentar(w)
    await w.findAll('button').find((b) => b.text().includes('Editar')).trigger('click')
    await w.vm.$nextTick()
    const caixas = w.findAll('.membros input[type="checkbox"]')
    expect(caixas).toHaveLength(2)
    expect(caixas[0].element.checked).toBe(true)
    await caixas[1].setValue(true)
    await w.findAll('.edicao__rodape button')[0].trigger('click')
    await assentar(w)
    const membros = puts.find((p) => p.rota === '/api/times/10/membros')
    expect(membros.corpo.atendentes.sort()).toEqual([1, 2])
  })
})

// ------------------------------------------------------------ Minha conta

describe('CFG_10.1 — Minha conta', () => {
  it('atendimento edita o nome e NÃO vê e-mail nem login', async () => {
    const w = mount(MinhaConta)
    await assentar(w)
    const texto = w.text()
    expect(texto).not.toContain('ana@movisat.com.br')
    expect(w.findAll('dt').map((d) => d.text())).not.toContain('Login')
    expect(w.findAll('dt').map((d) => d.text())).not.toContain('E-mail')
    const campo = w.find('.conta__nome input')
    await campo.setValue('Ana S.')
    await w.find('.conta__nome').trigger('submit')
    await assentar(w)
    expect(puts.find((p) => p.rota === '/api/eu/nome').corpo).toEqual({ nome: 'Ana S.' })
  })

  it('admin vê o e-mail, mas não o login', async () => {
    respostas['/api/eu/perfil'] = { ...respostas['/api/eu/perfil'], perfil: 'admin' }
    const w = mount(MinhaConta)
    await assentar(w)
    const dts = w.findAll('dt').map((d) => d.text())
    expect(dts).toContain('E-mail')
    expect(dts).not.toContain('Login')
  })
})
