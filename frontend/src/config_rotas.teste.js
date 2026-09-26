/**
 * @vitest-environment jsdom
 *
 * Toda rota de /config monta a CASCA de Configurações (25/09).
 *
 * 🚨 O DEFEITO QUE ISTO PRENDE: desde 28/08, Geral e Atalhos (e depois Eventos,
 * Minha conta, Notificações e Mensagens rápidas) montavam a PÁGINA direto.
 * Clicar na aba abria a tela sem a barra de abas, e a pessoa ficava presa.
 * O comentário do roteador dizia o contrário. Achado pelo owner em 25/09:
 * *"não encontrei nas minhas configurações como owner"*.
 */
import { describe, it, expect, vi } from 'vitest'

vi.mock('./api/cliente.js', () => ({
  api: { get: () => Promise.resolve({}), post: () => Promise.resolve({}), put: () => Promise.resolve({}), del: () => Promise.resolve({}) },
  rede: {},
  pedirBlob: () => Promise.resolve(new Blob()),
  definirToken: () => {},
  temToken: () => false,
  quandoPerderSessao: () => {},
  relatarErroDeBotao: () => {},
  ErroDeApi: class ErroDeApi extends Error {},
}))

import { router } from './router/index.js'
import Configuracoes from './telas/Configuracoes.vue'

describe('rotas de /config', () => {
  const doConfig = router.getRoutes().filter((r) => r.path === '/config' || r.path.startsWith('/config/'))

  it('existem as abas pessoais e a nova', () => {
    const caminhos = doConfig.map((r) => r.path)
    for (const c of ['/config/minha-conta', '/config/notificacoes', '/config/mensagens-rapidas', '/config/geral']) {
      expect(caminhos).toContain(c)
    }
  })

  it('todas montam a casca com a barra de abas', () => {
    const soltas = doConfig.filter((r) => r.components.default !== Configuracoes).map((r) => r.path)
    expect(soltas).toEqual([])
  })
})
