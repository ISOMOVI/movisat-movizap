/**
 * @vitest-environment jsdom
 *
 * O BOTÃO "SOLICITAR" NO CHAT INTERNO — 27/11.
 *
 * 🔵 Ele, 27/11: *"sera somente interno, talvez um botao de acao no chat
 * interno? para forms internos igual no chat com clientes"*.
 *
 * 🚨 **O QUE JÁ EXISTIA NO CHAT INTERNO NÃO ERA ISTO.** O tipo `formulario`
 * das mensagens rápidas é validado como **URL** (*"O formulário é um link:
 * comece com https://"*) e só cola um endereço no campo de texto. Ele não abre
 * formulário nenhum dentro do MoviZap. Essa era a distância entre o que havia
 * e o que ele pediu, e é o que este componente fecha.
 *
 * 🚨 **GESTO, NÃO FUNÇÃO** (`M17` linha 2): toda asserção aqui é `trigger` e
 * `text()`. Já me aconteceu de ler a lógica, achá-la correta, e o defeito
 * estar no `<input>`.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const estado = vi.hoisted(() => ({
  gets: [],
  posts: [],
  lista: [],
  definicao: null,
  respostaDoEnvio: { ok: true, corpo: {} },
  erroNoGet: null,
}))

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (url) => {
      estado.gets.push(url)
      if (estado.erroNoGet) return Promise.reject(estado.erroNoGet)
      if (url === '/api/interno/formularios') return Promise.resolve(estado.lista)
      return Promise.resolve(estado.definicao)
    },
    post: () => Promise.resolve({}),
    put: () => Promise.resolve({}),
    del: () => Promise.resolve({}),
  },
  definirToken: () => {},
  temToken: () => true,
  quandoPerderSessao: () => {},
  relatarErroDeBotao: () => {},
  ErroDeApi: class ErroDeApi extends Error {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ meta: {}, query: {}, params: {} }),
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

import BotaoFormularioInterno from './componentes/BotaoFormularioInterno.vue'

const LISTA = [
  { slug: 'compras', titulo: 'Sugestão de compras', setor: 'Administrativo',
    botao: 'Enviar sugestão' },
]

/* A definição como `GET /api/interno/formulario/compras` a devolve -- copiada
   da rota em 27/11, inclusive os nomes reais dos campos. */
const DEFINICAO = {
  slug: 'compras', titulo: 'Sugestão de compras', setor: 'Administrativo',
  botao: 'Enviar sugestão', descricao: null, formato: 'classico',
  etapas: null, busca_cliente: false,
  campos: [
    { nome: 'SUGESTAO', rotulo: 'Justificativa', tipo: 'text',
      obrigatorio: true, multiplo: false, visivel: true, opcoes: null,
      ajuda: 'O que precisa ser comprado e para quê.', validacao: null,
      fantasma: null, linhas: 5, fonte: null },
    { nome: 'ANEXO', rotulo: 'Anexo', tipo: 'file',
      obrigatorio: false, multiplo: false, visivel: true, opcoes: null,
      ajuda: 'Orçamento, foto ou print, se tiver.', validacao: null,
      fantasma: null, linhas: null, fonte: null },
    { nome: 'CONTACT_NAME', rotulo: 'Solicitante', tipo: 'string',
      obrigatorio: true, multiplo: false, visivel: true, opcoes: null,
      ajuda: 'Vem de quem está logado.', validacao: null,
      fantasma: null, linhas: null, fonte: null },
  ],
  regras: [],
  solicitante: 'Iago Vannucci',
}

beforeEach(() => {
  estado.gets = []
  estado.posts = []
  estado.lista = LISTA
  estado.definicao = DEFINICAO
  estado.erroNoGet = null
  estado.respostaDoEnvio = { ok: true, corpo: { ok: true, id: 7001, card_id: 9001, painel: 'compras' } }

  global.fetch = vi.fn((url, opcoes) => {
    estado.posts.push({ url, opcoes })
    return Promise.resolve({
      ok: estado.respostaDoEnvio.ok,
      status: estado.respostaDoEnvio.ok ? 201 : 400,
      json: () => Promise.resolve(estado.respostaDoEnvio.corpo),
    })
  })
  global.localStorage.setItem('movizap.token', 'fingido')
})

async function abrirMenu(d) {
  await d.find('button').trigger('click')
  await flushPromises()
  return d
}

async function abrirModal(d) {
  await abrirMenu(d)
  await d.find('.bfi__item').trigger('click')
  await flushPromises()
  return d
}

describe('o botão', () => {
  it('🚨 tem RÓTULO VISÍVEL, não só title', () => {
    /* 🚨 `title` não é rótulo: o balão do navegador demora cerca de um segundo
       e não existe em toque. Foi esse o erro de 25/08 que escondeu o "Criar
       grupo" desta mesma tela, e a regra está escrita três linhas acima do
       lugar onde este botão entra. */
    const d = mount(BotaoFormularioInterno)
    expect(d.find('button').text()).toContain('Solicitar')
  })

  it('usa a variante de botão que existe', () => {
    /* 🚨 `botao--fraco` foi usado por meses sem nunca ter sido declarado, e
       todo botão caía no `.botao` base. É a conferência 11 do build. */
    const d = mount(BotaoFormularioInterno)
    const classe = d.find('button').attributes('class')
    expect(classe).toContain('botao--contorno')
    expect(classe).not.toContain('botao--fraco')
  })
})

describe('a lista', () => {
  it('vem da rota INTERNA, não da de formulários', async () => {
    /* 🚨 `/api/formularios` pede `FRM_1.1`, que é owner -- a porta trancada de
       sempre. A rota interna pede `ATD_6.1`. */
    const d = await abrirMenu(mount(BotaoFormularioInterno))
    expect(estado.gets).toContain('/api/interno/formularios')
    expect(estado.gets.some((u) => u === '/api/formularios')).toBe(false)
  })

  it('mostra o título do formulário', async () => {
    const d = await abrirMenu(mount(BotaoFormularioInterno))
    expect(d.text()).toContain('Sugestão de compras')
  })

  it('lista vazia DIZ que está vazia, e não fica em branco', async () => {
    /* 🚨 Hoje é o caso real: o `COMPRAS` nasce desligado, e quem liga é ele.
       Menu que abre em branco parece defeito. */
    estado.lista = []
    const d = await abrirMenu(mount(BotaoFormularioInterno))
    expect(d.text()).toContain('Nenhum formulário interno')
  })

  it('erro ao ler aparece NA TELA, não só no console', async () => {
    estado.erroNoGet = new Error('caiu')
    const d = await abrirMenu(mount(BotaoFormularioInterno))
    expect(d.find('.aviso--erro').exists()).toBe(true)
  })
})

describe('o modal', () => {
  it('abre com os campos da definição', async () => {
    const d = await abrirModal(mount(BotaoFormularioInterno))
    expect(d.find('.modal').exists()).toBe(true)
    expect(d.text()).toContain('Justificativa')
    expect(d.text()).toContain('Anexo')
  })

  it('🚨 o solicitante vem preenchido e TRAVADO', async () => {
    /* 🚨 Quem pede não digita o próprio nome -- e não dá para digitar o de
       outro. A trava de verdade é a da rota, que injeta o nome da sessão antes
       do `validar`; esta aqui é só a tela não convidar ao engano. */
    const d = await abrirModal(mount(BotaoFormularioInterno))
    const campos = d.findComponent({ name: 'CamposDoFormulario' })
    expect(campos.props('travados')).toContain('CONTACT_NAME')
    expect(campos.props('valores').CONTACT_NAME).toBe('Iago Vannucci')
  })

  it('usa o rótulo de botão que o banco diz', async () => {
    const d = await abrirModal(mount(BotaoFormularioInterno))
    expect(d.find('.bfi__enviar').text()).toContain('Enviar sugestão')
  })
})

describe('o envio', () => {
  it('vai para a rota interna, por multipart', async () => {
    /* ⚠️ Não passa pelo `api.post`, que serializa JSON: anexo vai por
       `FormData`, e aí o navegador monta o boundary sozinho. Definir o
       `Content-Type` na mão quebra o upload EM SILÊNCIO. */
    const d = await abrirModal(mount(BotaoFormularioInterno))
    const campos = d.findComponent({ name: 'CamposDoFormulario' })
    campos.props('valores').SUGESTAO = 'Cabo de rede cat6, 20 metros'
    await d.find('.bfi__enviar').trigger('click')
    await flushPromises()

    expect(estado.posts.length).toBe(1)
    expect(estado.posts[0].url).toBe('/api/interno/formulario/compras')
    expect(estado.posts[0].opcoes.method).toBe('POST')
    expect(estado.posts[0].opcoes.body instanceof FormData).toBe(true)
    expect(estado.posts[0].opcoes.headers['Content-Type']).toBeUndefined()
  })

  it('🚨 erro do servidor aparece NA TELA', async () => {
    estado.respostaDoEnvio = {
      ok: false, corpo: { detail: 'Justificativa: preencha este campo.' },
    }
    const d = await abrirModal(mount(BotaoFormularioInterno))
    await d.find('.bfi__enviar').trigger('click')
    await flushPromises()
    expect(d.text()).toContain('Justificativa: preencha este campo.')
    expect(d.find('.modal').exists()).toBe(true)
  })

  it('🚨 depois de enviar, DIZ qual card nasceu e em que painel', async () => {
    /* 🚨 Senão a pessoa envia e não tem como saber se a sugestão chegou a
       algum lugar -- e `M12` vale para o silêncio também. */
    const d = await abrirModal(mount(BotaoFormularioInterno))
    const campos = d.findComponent({ name: 'CamposDoFormulario' })
    campos.props('valores').SUGESTAO = 'Cabo de rede'
    await d.find('.bfi__enviar').trigger('click')
    await flushPromises()
    expect(d.text()).toMatch(/Compras/)
    expect(d.text()).toContain('9001')
  })

  it('🚨 NÃO manda mensagem nenhuma na sala: oferece a linha', async () => {
    /* 🚨 A regra do `BotaoFormulario` da Caixa, por extenso lá: *"ESTE BOTÃO
       NÃO MANDA MENSAGEM NENHUMA"* -- quem manda é a pessoa. Aqui o modal
       emite `inserir`, e o compositor é que escreve. */
    const d = await abrirModal(mount(BotaoFormularioInterno))
    const campos = d.findComponent({ name: 'CamposDoFormulario' })
    campos.props('valores').SUGESTAO = 'Cabo de rede'
    await d.find('.bfi__enviar').trigger('click')
    await flushPromises()
    const inseridos = d.emitted('inserir') || []
    expect(inseridos.length).toBe(1)
    expect(inseridos[0][0]).toContain('Sugestão de compras')
  })
})
