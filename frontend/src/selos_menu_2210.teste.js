/**
 * @vitest-environment jsdom
 *
 * Os três selos do menu e a soma no grupo fechado — 22/10.
 *
 * 🔵 Pedido dele: *"a quantidade de notificações que aparece no 'Chat
 * interno' deve aparecer tbm na aba 'Whatsapp' (...) conforme notificações da
 * aba 'Minhas' e o mesmo para 'e-mail's' (não lidos) e na Aba "Atendimento',
 * quando fechada informar a soma dos 3"*.
 *
 * 🚨 ISTO É DOM, NÃO LAYOUT. O `M9` continua valendo: nenhum teste aqui vê o
 * selo caber nos 18px do item, nem a cor, nem se ele cobre o rótulo. O que se
 * prova é o que o pedido dele pode perder calado numa entrega futura: o selo
 * existir nos três lugares, a soma ser dos três, e o zero não desenhar nada.
 *
 * ⚠️ O selo do Chat interno já era testado por caminho nenhum — ele nasceu em
 * 15/09 e só o `menu_grupos_2110` chegou a montar este componente, para
 * outra coisa. Então estes testes cobrem os três, não só os dois novos.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

const estado = vi.hoisted(() => ({
  sessao: { nome: 'Fulano de Tal', telas: [], owner: false },
  rota: { meta: { codigo: 'ATD_1.1' }, query: {}, params: {} },
  chat: { nao_lidas: 0, mencoes: [] },
}))
const sessao = estado.sessao

/* O Chat interno mantém chamada própria (`nao-lidas` e `mencoes` exigem a
   ATD_6.1 e a menção tem conta separada, a que muda a cor). Os outros dois
   saem do estado que o Notificador preenche — por isso só este é mock de
   rede. */
vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) =>
      Promise.resolve(
        rota.includes('mencoes') ? estado.chat.mencoes : { nao_lidas: estado.chat.nao_lidas },
      ),
  },
  definirToken: () => {},
  temToken: () => true,
  quandoPerderSessao: () => {},
  ErroDeApi: class ErroDeApi extends Error {},
}))

vi.mock('./estado/sessao.js', () => ({
  sessao: estado.sessao,
  sair: () => {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => estado.rota,
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
}))

import MenuLateral from './componentes/MenuLateral.vue'
import { notificacoes } from './estado/notificacoes.js'

const CATALOGO = [
  { codigo: 'ATD_1.1', titulo: 'WhatsApp', rota: '/atendimento', icone: 'bi-chat-dots', aba_de: null, grupo: 'Atendimento', subgrupo: null },
  { codigo: 'ATD_6.1', titulo: 'Chat interno', rota: '/chat', icone: 'bi-chat-left-dots', aba_de: null, grupo: 'Atendimento', subgrupo: null },
  { codigo: 'EML_1.1', titulo: 'E-mail', rota: '/email', icone: 'bi-envelope', aba_de: null, grupo: 'Atendimento', subgrupo: null },
  { codigo: 'LIG_1.1', titulo: 'Ligações', rota: '/ligacoes', icone: 'bi-telephone', aba_de: null, grupo: 'Atendimento', subgrupo: null },
]

async function montar() {
  const tela = mount(MenuLateral)
  // duas voltas: a chamada do chat é assíncrona e o selo depende dela
  await Promise.resolve()
  await tela.vm.$nextTick()
  await Promise.resolve()
  await tela.vm.$nextTick()
  return tela
}

/** O selo de um item, pelo rótulo dele. `null` quando não há selo. */
function seloDe(tela, titulo) {
  const item = tela
    .findAll('.menu__link')
    .find((n) => n.find('.menu__titulo').text() === titulo)
  if (!item) throw new Error(`não achei o item ${titulo} no menu`)
  const selo = item.find('.menu__selo')
  return selo.exists() ? selo.text() : null
}

function seloDoGrupo(tela) {
  const s = tela.find('.menu__selo--grupo')
  return s.exists() ? s.text() : null
}

beforeEach(() => {
  sessao.telas = CATALOGO
  sessao.owner = false
  estado.rota = { meta: { codigo: 'ATD_1.1' }, query: {}, params: {} }
  estado.chat = { nao_lidas: 0, mencoes: [] }
  notificacoes.abas = { minhas: 0, time: 0 }
  notificacoes.email_nao_lidos = 0
  localStorage.clear()
})

describe('o selo de cada um dos três', () => {
  it('o WhatsApp mostra o número da aba Minhas', async () => {
    notificacoes.abas = { minhas: 4, time: 9 }
    const tela = await montar()
    expect(seloDe(tela, 'WhatsApp')).toBe('4')
  })

  it('🚨 o WhatsApp NÃO mostra o número do Time', async () => {
    /* *"conforme notificações da aba 'Minhas'"* — e só. Somar o time faria o
       selo discordar da aba que a pessoa abre em seguida. */
    notificacoes.abas = { minhas: 0, time: 7 }
    const tela = await montar()
    expect(seloDe(tela, 'WhatsApp')).toBe(null)
  })

  it('o E-mail mostra os não lidos da entrada', async () => {
    notificacoes.email_nao_lidos = 61
    const tela = await montar()
    expect(seloDe(tela, 'E-mail')).toBe('61')
  })

  it('o Chat interno continua com o selo dele', async () => {
    estado.chat = { nao_lidas: 3, mencoes: [] }
    const tela = await montar()
    expect(seloDe(tela, 'Chat interno')).toBe('3')
  })

  it('zero não desenha selo em nenhum dos três', async () => {
    const tela = await montar()
    expect(seloDe(tela, 'WhatsApp')).toBe(null)
    expect(seloDe(tela, 'Chat interno')).toBe(null)
    expect(seloDe(tela, 'E-mail')).toBe(null)
  })

  it('tela sem selo não ganha um — Ligações fica limpa', async () => {
    notificacoes.abas = { minhas: 4, time: 0 }
    notificacoes.email_nao_lidos = 2
    estado.chat = { nao_lidas: 1, mencoes: [] }
    const tela = await montar()
    expect(seloDe(tela, 'Ligações')).toBe(null)
  })

  it('acima de 99 vira 99+, e o número real fica no title', async () => {
    notificacoes.email_nao_lidos = 240
    const tela = await montar()
    expect(seloDe(tela, 'E-mail')).toBe('99+')
    const item = tela
      .findAll('.menu__link')
      .find((n) => n.find('.menu__titulo').text() === 'E-mail')
    expect(item.find('.menu__selo').attributes('title')).toContain('240')
  })
})

describe('o grupo fechado soma os três', () => {
  async function fechado(valores) {
    Object.assign(notificacoes, valores.notificacoes || {})
    estado.chat = valores.chat || { nao_lidas: 0, mencoes: [] }
    /* 🚨 O grupo da tela ATUAL nasce sempre aberto (menu que esconde onde a
       pessoa está é o mesmo defeito do rótulo que mente). Para fechar
       "Atendimento" é preciso estar FORA dele. */
    estado.rota = { meta: { codigo: 'LIG_9.9' }, query: {}, params: {} }
    localStorage.setItem('movizap_menu_grupos', JSON.stringify(['Atendimento']))
    return await montar()
  }

  it('mostra a soma dos três quando fechado', async () => {
    const tela = await fechado({
      notificacoes: { abas: { minhas: 4, time: 0 }, email_nao_lidos: 2 },
      chat: { nao_lidas: 3, mencoes: [] },
    })
    expect(seloDoGrupo(tela)).toBe('9')
  })

  it('a soma ignora a parcela zerada, mas continua somando as outras', async () => {
    const tela = await fechado({
      notificacoes: { abas: { minhas: 0, time: 0 }, email_nao_lidos: 5 },
      chat: { nao_lidas: 2, mencoes: [] },
    })
    expect(seloDoGrupo(tela)).toBe('7')
  })

  it('os três em zero não desenham selo no cabeçalho', async () => {
    const tela = await fechado({
      notificacoes: { abas: { minhas: 0, time: 0 }, email_nao_lidos: 0 },
    })
    expect(seloDoGrupo(tela)).toBe(null)
  })

  it('o title do cabeçalho diz de onde vem cada parcela', async () => {
    /* 🚨 "9" sozinho não diz onde olhar, e o grupo está fechado: o item que
       explicaria está escondido. O title é a única saída. */
    const tela = await fechado({
      notificacoes: { abas: { minhas: 4, time: 0 }, email_nao_lidos: 2 },
      chat: { nao_lidas: 3, mencoes: [] },
    })
    const title = tela.find('.menu__selo--grupo').attributes('title')
    expect(title).toContain('WhatsApp')
    expect(title).toContain('chat interno')
    expect(title).toContain('e-mail')
  })

  it('com o grupo ABERTO o cabeçalho não leva selo — os itens levam', async () => {
    notificacoes.abas = { minhas: 4, time: 0 }
    notificacoes.email_nao_lidos = 2
    estado.chat = { nao_lidas: 3, mencoes: [] }
    const tela = await montar()
    expect(seloDoGrupo(tela)).toBe(null)
    expect(seloDe(tela, 'WhatsApp')).toBe('4')
  })
})

describe('a cor da menção', () => {
  it('só o Chat interno fica vermelho quando te chamaram pelo nome', async () => {
    /* 🚨 A menção é do chat. Pintar o selo do WhatsApp ou do e-mail de
       "menção" diria que alguém te chamou lá, e ninguém chamou. */
    estado.chat = { nao_lidas: 5, mencoes: [{ quantas: 2 }] }
    notificacoes.abas = { minhas: 4, time: 0 }
    notificacoes.email_nao_lidos = 2
    const tela = await montar()
    const selo = (titulo) =>
      tela
        .findAll('.menu__link')
        .find((n) => n.find('.menu__titulo').text() === titulo)
        .find('.menu__selo')
    expect(selo('Chat interno').classes()).toContain('menu__selo--mencao')
    expect(selo('WhatsApp').classes()).not.toContain('menu__selo--mencao')
    expect(selo('E-mail').classes()).not.toContain('menu__selo--mencao')
  })
})
