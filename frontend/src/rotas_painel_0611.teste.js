/**
 * @vitest-environment jsdom
 *
 * TODA ROTA QUE MONTA A `PainelAba` TEM DE LEVAR `meta.aba` — 06/11.
 *
 * 🚨 **O DEFEITO QUE ISTO PRENDE, e que foi ELE quem achou:** *"não estão
 * aparecendo as colunas de 'financeiro' e ' contratual'"*. As duas rotas novas
 * (`PNL_1.4` e `PNL_1.5`) subiram com `meta: { codigo, titulo }` e **sem
 * `meta.aba`** — eu copiei a forma do `meta` das rotas de `/config`, que não
 * têm `aba`, em vez das duas do Pós-venda, que têm.
 *
 * O `PainelAba.vue` descobre qual aba carregar em `rota.meta?.aba || ''`. Sem
 * o campo, `codigo` ficava **vazio** e a tela pedia `/api/paineis/aba/` sem
 * código nenhum. ⚠️ **E tudo o mais estava certo:** entrada no registro, item
 * de menu, rota, permissão, 200 na API quando chamada com o código, 10 e 6
 * colunas no banco, 2227 testes verdes. O elo que faltava era o **quarto**:
 * quem devolve → quem grava → quem lê → **quem diz à tela o que ler**.
 *
 * 🚨 **A TRAVA É ESTRUTURAL, e tinha de ser:** ela não cita `PNL_1.4` nem
 * `PNL_1.5`. Varre o roteador e cobra o campo de **toda** rota que monta a
 * `PainelAba` — assim o próximo painel (Cobrança, se ele mandar) não pode
 * repetir o mesmo esquecimento. Uma trava que citasse os dois códigos teria
 * ficado verde no dia seguinte e sido inútil.
 */
import { describe, it, expect, vi } from 'vitest'

vi.mock('./api/cliente.js', () => ({
  api: {
    get: () => Promise.resolve({}),
    post: () => Promise.resolve({}),
    put: () => Promise.resolve({}),
    del: () => Promise.resolve({}),
  },
  rede: {},
  pedirBlob: () => Promise.resolve(new Blob()),
  definirToken: () => {},
  temToken: () => false,
  quandoPerderSessao: () => {},
  relatarErroDeBotao: () => {},
  ErroDeApi: class ErroDeApi extends Error {},
}))

import { router } from './router/index.js'
import PainelAba from './telas/PainelAba.vue'

const daPainelAba = () =>
  router.getRoutes().filter((r) => r.components?.default === PainelAba)

describe('as rotas que montam a PainelAba', () => {
  it('são mais de uma — se o filtro quebrar, o resto passaria vazio', () => {
    expect(daPainelAba().length).toBeGreaterThan(1)
  })

  it('🚨 TODAS levam `meta.aba`, sem exceção', () => {
    const sem = daPainelAba()
      .filter((r) => !r.meta?.aba)
      .map((r) => `${r.path} (${r.meta?.codigo || 'sem codigo'})`)
    expect(sem).toEqual([])
  })

  it('🚨 `meta.aba` é IGUAL a `meta.codigo` em todas', () => {
    // ⚠️ Os dois existirem não basta: `aba` apontando para outra tela faria a
    // pessoa abrir o Financeiro e ver as colunas do Contratual -- permissão de
    // uma tela mostrando o conteúdo de outra, que é pior que tela vazia.
    const divergem = daPainelAba()
      .filter((r) => r.meta.aba !== r.meta.codigo)
      .map((r) => `${r.path}: aba=${r.meta.aba} codigo=${r.meta.codigo}`)
    expect(divergem).toEqual([])
  })

  it('todas levam `largo: true` — o kanban usa a largura cheia', () => {
    // ⚠️ Não é enfeite: o Financeiro tem DEZ colunas, e sem isso o quadro
    // ficaria apertado na coluna de conteúdo.
    const estreitas = daPainelAba()
      .filter((r) => !r.meta?.largo)
      .map((r) => r.path)
    expect(estreitas).toEqual([])
  })

  it('o `name` da rota é o código da tela, como no resto do roteador', () => {
    const fora = daPainelAba()
      .filter((r) => r.name !== r.meta.codigo)
      .map((r) => `${r.path}: name=${String(r.name)}`)
    expect(fora).toEqual([])
  })

  it('cada painel tem rota própria — nenhuma duplicada', () => {
    const codigos = daPainelAba().map((r) => r.meta.codigo)
    expect(codigos.length).toBe(new Set(codigos).size)
  })
})
