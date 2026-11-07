/**
 * @vitest-environment jsdom
 *
 * O menu em grupos e subgrupos, com acordeão — 21/10.
 *
 * 🚨 PRIMEIRO TESTE QUE MONTA O `MenuLateral`. Ele existe desde o começo do
 * painel e nunca foi montado por teste nenhum: toda a navegação do sistema
 * dependia de alguém abrir o navegador. Suíte verde não prova tela (`M9`),
 * mas componente nunca montado não prova nem markup.
 *
 * O que se protege aqui é o que o pedido dele de 19/10 trouxe: grupo e
 * subgrupo vindos do backend, vários grupos abertos ao mesmo tempo, a
 * escolha lembrada por pessoa, o grupo da tela atual sempre aberto, e grupo
 * sem tela visível não desenhado.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

// `vi.mock` é içado para o topo do arquivo: o que a fábrica usa tem de ser
// içado junto, senão o mock roda antes da variável existir.
const estado = vi.hoisted(() => ({
  sessao: { nome: 'Fulano de Tal', telas: [], owner: false },
  rota: { meta: { codigo: 'ATD_1.1' }, query: {}, params: {} },
}))
const sessao = estado.sessao

vi.mock('./api/cliente.js', () => ({
  api: { get: () => Promise.resolve({ nao_lidas: 0 }) },
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

const CATALOGO = [
  { codigo: 'INI_1.1', titulo: 'Início', rota: '/inicio', icone: 'bi-house', aba_de: null, grupo: 'Início', subgrupo: null },
  { codigo: 'ATD_1.1', titulo: 'WhatsApp', rota: '/atendimento', icone: 'bi-chat-dots', aba_de: null, grupo: 'Atendimento', subgrupo: null },
  { codigo: 'ATD_6.1', titulo: 'Chat interno', rota: '/chat', icone: 'bi-chat-left-dots', aba_de: null, grupo: 'Atendimento', subgrupo: null },
  // 🔵 O pedido que abriu o assunto: Ligações DENTRO de Atendimento, sem
  // mudar o código da tela (que é imutável).
  { codigo: 'LIG_1.1', titulo: 'Ligações', rota: '/ligacoes', icone: 'bi-telephone', aba_de: null, grupo: 'Atendimento', subgrupo: null },
  { codigo: 'CAD_1.1', titulo: 'Clientes', rota: '/clientes', icone: 'bi-building', aba_de: null, grupo: 'Cadastro', subgrupo: null },
  // A casca do `/config` e a aba dela. 🚨 06/11: AS DUAS, e não só a aba --
  // a fixture tinha uma aba ÓRFÃ, que o sistema não produz. A `CFG_0.1` é
  // `atendimento`, então quem alcança `CFG_1.1` alcança a casca junto. Com
  // o conserto da porta trancada (aba órfã passa a desenhar o próprio
  // item), a fixture órfã viraria uma regra de mentira. ⚠️ Fixture irreal
  // não se conserta afrouxando o código.
  { codigo: 'CFG_0.1', titulo: 'Configurações', rota: '/config', icone: 'bi-sliders', aba_de: null, grupo: 'Configuração', subgrupo: null },
  // Aba de outra tela: continua na sessão (a guarda de rota usa), e NÃO vira
  // item de menu -- porque a mãe dela veio junto.
  { codigo: 'CFG_1.1', titulo: 'Canais', rota: '/config/canais', icone: 'bi-plug', aba_de: 'CFG_0.1', grupo: 'Configuração', subgrupo: null },
]

// O `MenuLateral` usa `<RouterLink>` como componente GLOBAL (registrado pelo
// plugin do vue-router), não importado -- mockar o módulo não o resolve. Sem
// este stub o Vue monta assim mesmo e só reclama no stderr.
const STUB_LINK = { props: ['to'], template: '<a><slot /></a>' }

function montar(telas = CATALOGO) {
  sessao.telas = telas
  return mount(MenuLateral, { global: { stubs: { RouterLink: STUB_LINK } } })
}

function nomesDosGrupos(tela) {
  return tela.findAll('.menu__grupo-nome span:first-child').map((n) => n.text())
}

function titulosVisiveis(tela) {
  return tela.findAll('.menu__titulo').map((n) => n.text())
}

beforeEach(() => {
  localStorage.clear()
  estado.rota = { meta: { codigo: 'ATD_1.1' }, query: {}, params: {} }
})

describe('grupos vindos do backend', () => {
  it('monta os grupos na ordem em que o backend mandou', () => {
    const tela = montar()
    expect(nomesDosGrupos(tela)).toEqual(['Início', 'Atendimento', 'Cadastro', 'Configuração'])
  })

  it('põe Ligações dentro de Atendimento, sem tocar no código da tela', () => {
    const tela = montar()
    const atendimento = tela.findAll('.menu__grupo')[1]
    expect(atendimento.findAll('.menu__titulo').map((n) => n.text()))
      .toEqual(['WhatsApp', 'Chat interno', 'Ligações'])
  })

  it('não desenha grupo sem nenhuma tela visível', () => {
    // Grupo cujas telas não chegaram NENHUMA: o menu é construído a
    // partir do que veio, nunca de uma lista fixa.
    const tela = montar([CATALOGO[1]])
    expect(nomesDosGrupos(tela)).toEqual(['Atendimento'])
  })

  it('a aba não vira item de menu quando a tela-mãe veio junto', () => {
    // 🚨 06/11: a regra que sobrou do `if (tela.aba_de) continue`. Com a
    // mãe presente -- que é o caso de todas as quinze `CFG_*` --, a aba
    // continua escondida, e o item é o da casca.
    const tela = montar()
    expect(titulosVisiveis(tela)).toContain('Configurações')
    expect(titulosVisiveis(tela)).not.toContain('Canais')
  })

  it('cai no prefixo do código quando a tela vem sem grupo', () => {
    // Backend um passo atrás do `dist` -- acontece no meio da publicação.
    const tela = montar([{ codigo: 'REL_1.1', titulo: 'Relatórios', rota: '/relatorios', icone: 'bi-file', aba_de: null }])
    expect(nomesDosGrupos(tela)).toEqual(['REL'])
  })

  it('desenha o rótulo do subgrupo e recolhe as telas dele', () => {
    const tela = montar([
      { codigo: 'ATD_1.1', titulo: 'WhatsApp', rota: '/atendimento', icone: 'bi-chat', aba_de: null, grupo: 'Painéis', subgrupo: 'Operacional' },
    ])
    expect(tela.find('.menu__sub-nome').text()).toBe('Operacional')
    expect(tela.find('.menu__link--sub').exists()).toBe(true)
  })
})

describe('acordeão', () => {
  it('fecha um grupo ao clicar no nome e some com os itens dele', async () => {
    const tela = montar()
    await tela.findAll('.menu__grupo-nome')[2].trigger('click') // Cadastro
    expect(titulosVisiveis(tela)).not.toContain('Clientes')
    expect(titulosVisiveis(tela)).toContain('WhatsApp')
  })

  it('mantém VÁRIOS grupos abertos ao mesmo tempo (decisão dele)', async () => {
    const tela = montar()
    // Abrir/fechar um não pode mexer no outro.
    await tela.findAll('.menu__grupo-nome')[2].trigger('click')
    expect(titulosVisiveis(tela)).toContain('Início')
    expect(titulosVisiveis(tela)).toContain('WhatsApp')
  })

  it('lembra a escolha por pessoa, no localStorage', async () => {
    const tela = montar()
    await tela.findAll('.menu__grupo-nome')[2].trigger('click')
    expect(JSON.parse(localStorage.getItem('movizap_menu_grupos'))).toEqual(['Cadastro'])

    const outra = montar()
    expect(titulosVisiveis(outra)).not.toContain('Clientes')
  })

  it('reabre ao clicar de novo, e limpa o que estava guardado', async () => {
    const tela = montar()
    const cadastro = tela.findAll('.menu__grupo-nome')[2]
    await cadastro.trigger('click')
    await cadastro.trigger('click')
    expect(titulosVisiveis(tela)).toContain('Clientes')
    expect(JSON.parse(localStorage.getItem('movizap_menu_grupos'))).toEqual([])
  })

  it('🚨 o grupo da tela ABERTA AGORA nasce aberto, mesmo gravado como fechado', () => {
    localStorage.setItem('movizap_menu_grupos', JSON.stringify(['Atendimento', 'Cadastro']))
    const tela = montar()
    // A rota atual é ATD_1.1 -- o grupo dela não pode esconder o item em que
    // a pessoa está.
    expect(titulosVisiveis(tela)).toContain('WhatsApp')
    expect(titulosVisiveis(tela)).not.toContain('Clientes')
  })

  it('grupo novo nasce ABERTO para quem já tinha escolha gravada', () => {
    // Guarda-se o que está fechado: por isso uma entrega nova não nasce
    // escondida para quem usa o painel há mais tempo.
    localStorage.setItem('movizap_menu_grupos', JSON.stringify(['Cadastro']))
    estado.rota = { meta: { codigo: 'INI_1.1' }, query: {}, params: {} }
    expect(titulosVisiveis(montar())).toContain('Ligações')
  })

  it('não quebra quando o localStorage está bloqueado ou estragado', () => {
    localStorage.setItem('movizap_menu_grupos', 'isto não é json')
    expect(titulosVisiveis(montar())).toContain('Clientes')
  })
})
