/**
 * @vitest-environment jsdom
 *
 * ===========================================================================
 * O BOTÃO DO FORMULÁRIO NA CONVERSA — travas de NÃO-ACONTECIMENTO
 * ===========================================================================
 * 🔵 12/11, dele: *"5 ok pode seguir"*.
 *
 * 🚨 TRAVA DE TELA OLHA ESTRUTURA, NÃO GESTO. O jsdom não faz layout, e um
 * botão morto passa verde -- foi o card inerte de 09/11, com 22 travas verdes
 * sobre tela morta, e foi a aba Checklist de hoje, com 19 travas verdes sobre
 * uma rota que dava 500. Então o que estas travas medem é o que NÃO pode
 * acontecer, que é onde o teste ingênuo falha:
 *
 *   · escolher um formulário NÃO pode enviar mensagem ao cliente;
 *   · o link que entra no campo NÃO pode conter dado do cliente;
 *   · sem conversa aberta, o botão NÃO pode estar clicável.
 * ===========================================================================
 */
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import BotaoFormulario from './componentes/BotaoFormulario.vue'

/* O que o servidor devolve, com a forma real da rota (conferida em 12/11). */
const RESPOSTA = {
  formularios: [
    { slug: 'suporte', titulo: 'Suporte', setor: 'Suporte' },
    { slug: 'rescisao', titulo: 'Rescisão contratual', setor: 'Contratual' },
  ],
  convites: [],
}

const CLIENTE = {
  nome: 'Fulano de Tal',
  cnpj: '12585917000184',
  telefone: '+5519974140416',
  email: 'fulano@exemplo.com.br',
}

const chamadas = { get: [], post: [] }
let urlDoConvite = 'https://forms.movisat.com.br/f/suporte?c=xr56q7SMabc'

vi.mock('./api/cliente.js', () => ({
  ErroDeApi: class ErroDeApi extends Error {},
  api: {
    get: async (rota) => {
      chamadas.get.push(rota)
      return RESPOSTA
    },
    post: async (rota, corpo) => {
      chamadas.post.push({ rota, corpo })
      return {
        bilhete: 'xr56q7SMabc',
        slug: corpo.slug,
        url: urlDoConvite,
        expira_em: '2026-11-19T12:00:00-03:00',
      }
    },
  },
}))

async function abrirMenu(w) {
  await w.find('button').trigger('click')
  await new Promise((r) => setTimeout(r, 0))
  await w.vm.$nextTick()
}

describe('o botão do formulário na conversa', () => {
  beforeEach(() => {
    chamadas.get = []
    chamadas.post = []
    urlDoConvite = 'https://forms.movisat.com.br/f/suporte?c=xr56q7SMabc'
  })

  it('sem conversa aberta, o botão nasce DESABILITADO', () => {
    const w = mount(BotaoFormulario, { props: { conversaId: null } })
    expect(w.find('button').attributes('disabled')).toBeDefined()
  })

  it('abre lendo a rota DA CONVERSA, não a de owner', async () => {
    const w = mount(BotaoFormulario, { props: { conversaId: 77 } })
    await abrirMenu(w)
    expect(chamadas.get).toHaveLength(1)
    expect(chamadas.get[0]).toContain('/api/conversas/77/links-de-formulario')
    /* 🚨 `/api/formularios` pede FRM_1.1, que é owner: nove de dez atendentes
       veriam lista vazia. Se alguém "simplificar" para lá, esta trava cai. */
    expect(chamadas.get[0]).not.toBe('/api/formularios')
  })

  it('mostra os formulários ativos pelo título', async () => {
    const w = mount(BotaoFormulario, { props: { conversaId: 77 } })
    await abrirMenu(w)
    const texto = w.text()
    expect(texto).toContain('Suporte')
    expect(texto).toContain('Rescisão contratual')
  })

  it('DIZ, antes do clique, que o link vence e que os dados não viajam',
    async () => {
      const w = mount(BotaoFormulario, { props: { conversaId: 77 } })
      await abrirMenu(w)
      const texto = w.text()
      expect(texto).toContain('7 dias')
      expect(texto.toLowerCase()).toContain('não viajam')
    })

  it('escolher ESCREVE NO CAMPO e NÃO envia nada', async () => {
    const w = mount(BotaoFormulario, { props: { conversaId: 77 } })
    await abrirMenu(w)
    const itens = w.findAll('.bf__item')
    expect(itens.length).toBe(2)
    await itens[0].trigger('click')
    await new Promise((r) => setTimeout(r, 0))

    /* o que ACONTECE: emite o link para o campo de resposta */
    expect(w.emitted('inserir')).toBeTruthy()
    expect(w.emitted('inserir')[0][0]).toBe(urlDoConvite)

    /* 🚨 o que NÃO acontece: nenhuma chamada de envio de mensagem. Um POST
       para /mensagens ou /enviar aqui seria uma mensagem ao cliente sem
       ninguém ter clicado em enviar -- e mensagem ao cliente não se desfaz. */
    const rotas = chamadas.post.map((c) => c.rota)
    expect(rotas).toEqual(['/api/conversas/77/link-de-formulario'])
    expect(rotas.some((r) => /mensagem|enviar|whatsapp/i.test(r))).toBe(false)
  })

  it('o link que vai para o campo NÃO carrega dado do cliente', async () => {
    const w = mount(BotaoFormulario, { props: { conversaId: 77 } })
    await abrirMenu(w)
    await w.findAll('.bf__item')[0].trigger('click')
    await new Promise((r) => setTimeout(r, 0))

    const link = w.emitted('inserir')[0][0]
    for (const valor of Object.values(CLIENTE)) {
      expect(link).not.toContain(valor)
      expect(link).not.toContain(encodeURIComponent(valor))
    }
    /* e nem os pedaços: só o sobrenome, só o DDD+número */
    expect(link).not.toContain('Fulano')
    expect(link).not.toContain('19974140416')
  })

  it('um formulário DESLIGADO devolve a frase do servidor, não some calado',
    async () => {
      const { api, ErroDeApi } = await import('./api/cliente.js')
      const original = api.post
      api.post = async () => {
        throw new ErroDeApi('Este formulário não está publicado agora.')
      }
      const w = mount(BotaoFormulario, { props: { conversaId: 77 } })
      await abrirMenu(w)
      await w.findAll('.bf__item')[0].trigger('click')
      await new Promise((r) => setTimeout(r, 0))
      expect(w.text()).toContain('não está publicado')
      expect(w.emitted('inserir')).toBeFalsy()
      api.post = original
    })
})
