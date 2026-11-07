/**
 * @vitest-environment jsdom
 *
 * A PERMISSÃO DOS PAINÉIS — a aba `CFG_15.1` e a porta trancada (06/11).
 *
 * 🔵 Pedido dele: *"em configuração, crie uma aba de permissão para os paineis,
 * ali vou definir quem pode ver o que e por aba tbm, como notará que o pós
 * venda ja possui abas"*.
 *
 * 🚨 **AS QUATRO COISAS QUE ESTE ARQUIVO PRENDE:**
 *
 * 1. **A PORTA TRANCADA, consertada** — conceder só a aba de dentro
 *    (`PNL_1.3`) desenhava a pessoa com tela, rota e permissão e **sem nenhum
 *    item de menu**, porque o item era da `PNL_1.2`. Agora a aba órfã desenha
 *    o próprio item. ⚠️ E a aba COM mãe continua escondida: a regra antiga não
 *    foi afrouxada, foi condicionada.
 * 2. **AS DUAS COLUNAS DO PÓS-VENDA TÊM NOMES DIFERENTES** — no registro as
 *    duas se chamam "Pós-venda"; o nome que as distingue vem do banco
 *    (`aba_titulo`). Sem isso, marcar uma das duas é chute.
 * 3. **NÃO GRAVA NO CLIQUE DA CAIXA** — marcar é dar acesso a dado de cliente.
 *    A linha fica pendente e só o botão grava.
 * 4. **A TELA REDESENHA DO QUE O SERVIDOR DEVOLVEU**, nunca do que mandou.
 *
 * 🚨 Todo teste daqui foi visto VERMELHO antes de ficar verde.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const estado = vi.hoisted(() => ({
  sessao: { nome: 'Iago', telas: [], owner: true },
  rota: { meta: { codigo: 'CFG_15.1' }, query: {}, params: {} },
  respostas: { get: null, put: null },
  enviados: [],
}))

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (url) => {
      if (url.startsWith('/api/config/permissao-paineis')) {
        return Promise.resolve(estado.respostas.get)
      }
      return Promise.resolve({ nao_lidas: 0 })
    },
    put: (url, corpo) => {
      estado.enviados.push({ url, corpo })
      return Promise.resolve(estado.respostas.put || estado.respostas.get)
    },
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

import PermissaoPaineis from './telas/PermissaoPaineis.vue'
import MenuLateral from './componentes/MenuLateral.vue'

/* As três telas de painel como a rota as devolve. 🚨 `PNL_1.2` e `PNL_1.3` com
   o MESMO `titulo` — é o registro de verdade, e é o que torna `aba_titulo`
   indispensável. */
const TELAS = [
  { codigo: 'PNL_1.1', titulo: 'Operação', aba_titulo: 'Operação', rota: '/paineis/operacao', descricao: '', aba_de: null, permissao: 'owner' },
  { codigo: 'PNL_1.2', titulo: 'Pós-venda', aba_titulo: 'Treinamentos', rota: '/paineis/pos-venda', descricao: '', aba_de: null, permissao: 'owner' },
  { codigo: 'PNL_1.3', titulo: 'Pós-venda', aba_titulo: 'Pós-venda', rota: '/paineis/pos-venda/realizado', descricao: '', aba_de: 'PNL_1.2', permissao: 'owner' },
]

function grade(concedidasDaErika = [], detalhe = {}) {
  return {
    grupo: 'Painéis',
    telas: TELAS,
    pessoas: [
      { atendente_id: 121, nome: 'Iago', email: null, perfil: 'owner', owner: true, concedidas: TELAS.map((t) => t.codigo), detalhe: {}, editavel: false },
      { atendente_id: 123, nome: 'Erika', email: null, perfil: 'atendimento', owner: false, concedidas: concedidasDaErika, detalhe, editavel: true },
    ],
  }
}

const STUB_LINK = { props: ['to'], template: '<a><slot /></a>' }

async function montarTela(resposta = grade()) {
  estado.respostas.get = resposta
  const tela = mount(PermissaoPaineis)
  await flushPromises()
  return tela
}

function linhaDa(tela, nome) {
  return tela.findAll('tbody tr').find((l) => l.text().includes(nome))
}

beforeEach(() => {
  estado.enviados = []
  estado.respostas.put = null
})

describe('a grade da aba CFG_15.1', () => {
  it('desenha uma coluna por tela de painel, com o código à vista', async () => {
    const tela = await montarTela()
    const colunas = tela.findAll('thead th.perm__col')
    expect(colunas).toHaveLength(3)
    expect(colunas.map((c) => c.find('.perm__col-codigo').text()))
      .toEqual(['PNL_1.1', 'PNL_1.2', 'PNL_1.3'])
  })

  it('🚨 as duas colunas do Pós-venda NÃO ficam com o mesmo nome', async () => {
    // No registro as duas se chamam "Pós-venda" (correção dele de 05/11: o
    // item de menu é o do painel). O nome da ABA vem do banco.
    const tela = await montarTela()
    const nomes = tela.findAll('thead th.perm__col .perm__col-nome')
      .map((n) => n.text())
    expect(nomes).toEqual(['Operação', 'Treinamentos', 'Pós-venda'])
    expect(new Set(nomes).size).toBe(3)
  })

  it('recua a coluna da aba de dentro, porque a hierarquia é dado', async () => {
    const tela = await montarTela()
    const colunas = tela.findAll('thead th.perm__col')
    expect(colunas[1].classes()).not.toContain('perm__col--aba')
    expect(colunas[2].classes()).toContain('perm__col--aba')
  })

  it('o owner vem marcado e SEM caixa para marcar', async () => {
    // ⚠️ Verdade sem gesto inútil: ele vê tudo por ser owner, e a tela não
    // oferece um clique que não faz nada.
    const tela = await montarTela()
    const caixas = linhaDa(tela, 'Iago').findAll('input[type="checkbox"]')
    expect(caixas).toHaveLength(3)
    caixas.forEach((c) => {
      expect(c.element.checked).toBe(true)
      expect(c.element.disabled).toBe(true)
    })
  })

  it('quem não é owner nasce sem nenhuma marca', async () => {
    const tela = await montarTela()
    const caixas = linhaDa(tela, 'Erika').findAll('input[type="checkbox"]')
    caixas.forEach((c) => {
      expect(c.element.checked).toBe(false)
      expect(c.element.disabled).toBe(false)
    })
  })

  it('mostra quem concedeu e quando, como ESTADO e não como explicação', async () => {
    // ⚠️ Decisão dele de 30/10: tela não leva comentário didático. O que ela
    // escreve é fato -- quem deu, em que dia.
    const tela = await montarTela(grade(['PNL_1.3'], {
      'PNL_1.3': {
        concedida_em: '2026-11-06T09:30:00-03:00',
        concedida_por: 121,
        concedida_por_nome: 'Iago',
      },
    }))
    const origem = linhaDa(tela, 'Erika').findAll('.perm__origem')
    expect(origem).toHaveLength(1)
    expect(origem[0].text()).toContain('Iago')
    expect(origem[0].text()).toContain('06/11')
  })
})

describe('gravar', () => {
  it('🚨 marcar a caixa NÃO grava — a linha fica pendente', async () => {
    const tela = await montarTela()
    const linha = linhaDa(tela, 'Erika')
    await linha.findAll('input[type="checkbox"]')[2].setValue(true)
    expect(estado.enviados).toHaveLength(0)
    expect(linha.classes()).toContain('perm__linha--pendente')
    expect(tela.find('.aviso--atencao').text()).toContain('1 linha alterada')
  })

  it('o botão manda o ESTADO COMPLETO da linha, e não o clique', async () => {
    // 🚨 É isso que faz desmarcar revogar de verdade.
    const tela = await montarTela(grade(['PNL_1.1']))
    const linha = linhaDa(tela, 'Erika')
    const caixas = linha.findAll('input[type="checkbox"]')
    await caixas[0].setValue(false)   // tira PNL_1.1
    await caixas[2].setValue(true)    // põe PNL_1.3
    estado.respostas.put = grade(['PNL_1.3'])
    await linha.find('button.botao').trigger('click')
    await flushPromises()
    expect(estado.enviados).toHaveLength(1)
    expect(estado.enviados[0].corpo.atendente_id).toBe(123)
    expect(estado.enviados[0].corpo.codigos).toEqual(['PNL_1.3'])
  })

  it('lista vazia é gravada — "nenhum painel" não é campo faltando', async () => {
    const tela = await montarTela(grade(['PNL_1.1']))
    const linha = linhaDa(tela, 'Erika')
    await linha.findAll('input[type="checkbox"]')[0].setValue(false)
    estado.respostas.put = grade([])
    await linha.find('button.botao').trigger('click')
    await flushPromises()
    expect(estado.enviados[0].corpo.codigos).toEqual([])
  })

  it('redesenha do que o SERVIDOR devolveu, e não do que mandou', async () => {
    // ⚠️ O servidor devolve algo diferente de propósito: a tela tem de mostrar
    // a resposta. Confiar no próprio palpite é como `M12` começa.
    const tela = await montarTela()
    const linha = linhaDa(tela, 'Erika')
    await linha.findAll('input[type="checkbox"]')[0].setValue(true)
    estado.respostas.put = grade(['PNL_1.2'])
    await linha.find('button.botao').trigger('click')
    await flushPromises()
    const depois = linhaDa(tela, 'Erika').findAll('input[type="checkbox"]')
    expect(depois[0].element.checked).toBe(false)
    expect(depois[1].element.checked).toBe(true)
    // E a linha deixa de estar pendente: o rascunho foi semeado da resposta.
    expect(linhaDa(tela, 'Erika').classes()).not.toContain('perm__linha--pendente')
  })

  it('desfazer volta ao que está gravado, sem chamar a rota', async () => {
    const tela = await montarTela(grade(['PNL_1.1']))
    const linha = linhaDa(tela, 'Erika')
    await linha.findAll('input[type="checkbox"]')[2].setValue(true)
    await linhaDa(tela, 'Erika').find('.perm__desfazer').trigger('click')
    await flushPromises()
    const caixas = linhaDa(tela, 'Erika').findAll('input[type="checkbox"]')
    expect(caixas[0].element.checked).toBe(true)
    expect(caixas[2].element.checked).toBe(false)
    expect(estado.enviados).toHaveLength(0)
  })

  it('a linha do owner não tem botão de gravar', async () => {
    const tela = await montarTela()
    expect(linhaDa(tela, 'Iago').find('button.botao').exists()).toBe(false)
  })
})

describe('🚨 a PORTA TRANCADA, no MenuLateral', () => {
  /* Até 06/11 o menu pulava TODA tela com `aba_de`. Conceder só a `PNL_1.3`
     dava uma pessoa com tela, rota e permissão — e sem item de menu nenhum.
     O 403 nunca aparecia: a tela simplesmente não existia para ela. */
  const PNL_12 = { codigo: 'PNL_1.2', titulo: 'Pós-venda', rota: '/paineis/pos-venda', icone: 'bi-clipboard-check', aba_de: null, grupo: 'Painéis', subgrupo: null }
  const PNL_13 = { codigo: 'PNL_1.3', titulo: 'Pós-venda', rota: '/paineis/pos-venda/realizado', icone: 'bi-clipboard-check', aba_de: 'PNL_1.2', grupo: 'Painéis', subgrupo: null }

  function montarMenu(telas) {
    estado.sessao.telas = telas
    return mount(MenuLateral, { global: { stubs: { RouterLink: STUB_LINK } } })
  }

  function titulos(tela) {
    return tela.findAll('.menu__titulo').map((n) => n.text())
  }

  it('só a aba de dentro concedida: o item APARECE, com a rota dela', () => {
    const tela = montarMenu([PNL_13])
    expect(titulos(tela)).toEqual(['Pós-venda'])
    expect(tela.find('.menu__link').attributes('href') ?? '').toBeDefined()
    // 🚨 O grupo também aparece: sem ele a pessoa não teria onde clicar.
    expect(tela.findAll('.menu__grupo-nome span:first-child').map((n) => n.text()))
      .toEqual(['Painéis'])
  })

  it('as duas concedidas: UM item, o da principal', () => {
    // ⚠️ A regra antiga não foi afrouxada, foi condicionada: com a mãe
    // presente, a aba continua escondida.
    const tela = montarMenu([PNL_12, PNL_13])
    expect(titulos(tela)).toEqual(['Pós-venda'])
  })

  it('só a principal concedida: um item, como sempre foi', () => {
    const tela = montarMenu([PNL_12])
    expect(titulos(tela)).toEqual(['Pós-venda'])
  })
})
