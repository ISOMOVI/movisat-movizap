/**
 * @vitest-environment jsdom
 *
 * Mensagens rápidas (25/09, Plano 3): as variáveis, o botão da conversa e a
 * CFG_12.1.
 *
 * 🔵 *"ao escolher, o texto vai para o campo de digitação, mas pode ser
 * editado ainda"* · *"Owner e admin criam as do tipo 'Padrões'"* · no Chat
 * interno, *"Minhas notas e Formulários"*.
 *
 * 🚨 MONTA AS TELAS (`M9`).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

import { aplicarVariaveis, saudacao } from './util/variaveis.js'

let respostas
let gets
let posts

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      gets.push(rota)
      const chave = Object.keys(respostas).filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? JSON.parse(JSON.stringify(respostas[chave])) : {})
    },
    post: (rota, corpo) => { posts.push({ rota, corpo }); return Promise.resolve({ id: 99, ...corpo }) },
    put: (rota, corpo) => { posts.push({ rota, corpo }); return Promise.resolve({ ...corpo }) },
    del: () => Promise.resolve({ ok: true }),
  },
  ErroDeApi: class ErroDeApi extends Error {},
}))
vi.mock('vue-router', () => ({
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
}))

import BotaoMensagensRapidas from './componentes/BotaoMensagensRapidas.vue'
import MensagensRapidas from './telas/MensagensRapidas.vue'

async function assentar(w, voltas = 5) {
  for (let i = 0; i < voltas; i++) { await new Promise((r) => setTimeout(r, 0)); await w.vm.$nextTick() }
}

const GRUPOS = {
  padrao: [{ id: 1, tipo: 'padrao', apelido: 'Boas-vindas', conteudo: '{saudacao}, {contato}! Aqui é da Movisat.' }],
  nota: [{ id: 2, tipo: 'nota', apelido: 'Encerramento', conteudo: 'Obrigado, {cliente}.' }],
  formulario: [{ id: 3, tipo: 'formulario', apelido: 'Ficha', conteudo: 'https://forms.movisat.com.br/ficha' }],
}

beforeEach(() => {
  gets = []
  posts = []
  respostas = {
    '/api/mensagens-rapidas?': GRUPOS,
    '/api/mensagens-rapidas/gestao': { ...GRUPOS, pode_equipe: false },
  }
})

// ---- as variáveis --------------------------------------------------------

describe('as variáveis', () => {
  const dez = new Date(2026, 8, 25, 10, 0)

  it('troca as três: empresa, pessoa e saudação', () => {
    const r = aplicarVariaveis('{saudacao}, {contato}, da {cliente}.',
      { cliente: 'Pastelaria Velasco', contato: 'João' }, dez)
    expect(r).toEqual({ texto: 'Bom dia, João, da Pastelaria Velasco.', faltando: [] })
  })

  it('a saudação corta às 12h e às 18h', () => {
    expect(saudacao(new Date(2026, 8, 25, 11, 59))).toBe('Bom dia')
    expect(saudacao(new Date(2026, 8, 25, 12, 0))).toBe('Boa tarde')
    expect(saudacao(new Date(2026, 8, 25, 18, 0))).toBe('Boa noite')
  })

  it('sem cadastro, {cliente} fica em branco e volta em "faltando", sem espaço sobrando', () => {
    const r = aplicarVariaveis('Obrigado, {cliente}!', { contato: 'João' }, dez)
    expect(r).toEqual({ texto: 'Obrigado,!', faltando: ['{cliente}'] })
  })
})

// ---- o botão -------------------------------------------------------------

describe('o botão da conversa', () => {
  async function abrirBotao(props = {}) {
    const w = mount(BotaoMensagensRapidas, { props, attachTo: document.body })
    await w.find('.mr__botao').trigger('click')
    await assentar(w)
    return w
  }

  it('abre nos tipos, e escolher manda o texto já preenchido para o campo', async () => {
    const w = await abrirBotao({ onde: 'cliente', dados: { cliente: 'Pastelaria Velasco', contato: 'João' } })
    expect(gets[0]).toBe('/api/mensagens-rapidas?onde=cliente')
    expect(w.findAll('.mr__tipo').map((t) => t.text().replace(/\d+$/, '').trim()))
      .toEqual(['Padrões', 'Minhas notas', 'Formulários'])
    await w.find('.mr__item').trigger('click')
    const [texto] = w.emitted('inserir')[0]
    expect(texto).toMatch(/^(Bom dia|Boa tarde|Boa noite), João! Aqui é da Movisat\.$/)
    expect(w.find('.mr__menu').exists()).toBe(false)
  })

  it('a busca filtra pelo apelido, e Enter escolhe', async () => {
    const w = await abrirBotao({ dados: { cliente: 'X', contato: 'Y' } })
    await w.findAll('.mr__tipo')[1].trigger('click')
    await w.find('.mr__busca').setValue('encerra')
    await w.find('.mr__menu').trigger('keydown', { key: 'Enter' })
    expect(w.emitted('inserir')[0][0]).toBe('Obrigado, X.')
  })

  it('variável sem dado avisa antes de enviar', async () => {
    const w = await abrirBotao({ dados: { contato: 'João' } })
    await w.findAll('.mr__tipo')[1].trigger('click')
    await w.find('.mr__item').trigger('click')
    expect(w.find('.mr__aviso').text()).toContain('Cliente')
  })

  it('no Chat interno pede só o que cabe lá', async () => {
    respostas['/api/mensagens-rapidas?'] = { nota: GRUPOS.nota, formulario: GRUPOS.formulario }
    const w = await abrirBotao({ onde: 'interno' })
    expect(gets[0]).toBe('/api/mensagens-rapidas?onde=interno')
    expect(w.findAll('.mr__tipo')).toHaveLength(2)
  })
})

// ---- a CFG_12.1 ----------------------------------------------------------

describe('CFG_12.1 — Mensagens rápidas', () => {
  it('quem atende vê Padrões só para leitura, e cria as suas notas', async () => {
    const w = mount(MensagensRapidas, { attachTo: document.body })
    await assentar(w)
    expect(w.text()).toContain('Só leitura')
    expect(w.findAll('button').some((b) => b.text().includes('Nova mensagem'))).toBe(false)
    await w.findAll('.abas-mr__aba').find((a) => a.text().startsWith('Minhas notas')).trigger('click')
    expect(w.text()).not.toContain('Só leitura')
    await w.findAll('button').find((b) => b.text().includes('Nova mensagem')).trigger('click')
    await w.vm.$nextTick()
    await w.find('input[maxlength="60"]').setValue('Retorno')
    await w.find('textarea').setValue('Oi ')
    await w.findAll('.variaveis__botoes button').find((b) => b.text().includes('Nome do contato')).trigger('click')
    expect(w.find('.previa__texto').text()).toBe('Oi João')
    await w.findAll('button').find((b) => b.text() === 'Salvar').trigger('click')
    await assentar(w)
    expect(posts[0]).toEqual({ rota: '/api/mensagens-rapidas',
      corpo: { tipo: 'nota', apelido: 'Retorno', conteudo: 'Oi {contato}', ativo: true } })
  })

  it('quem administra a equipe cria Padrões e Formulários (o formulário pede link)', async () => {
    respostas['/api/mensagens-rapidas/gestao'] = { ...GRUPOS, pode_equipe: true }
    const w = mount(MensagensRapidas, { attachTo: document.body })
    await assentar(w)
    await w.findAll('.abas-mr__aba').find((a) => a.text().startsWith('Formulários')).trigger('click')
    await w.findAll('button').find((b) => b.text().includes('Novo formulário')).trigger('click')
    await w.vm.$nextTick()
    expect(w.find('input[type="url"]').exists()).toBe(true)
    expect(w.find('.variaveis').exists()).toBe(false)
  })
})
