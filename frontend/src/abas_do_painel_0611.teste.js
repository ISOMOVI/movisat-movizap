/**
 * @vitest-environment jsdom
 *
 * A TIRA DE ABAS É DO PAINEL — o defeito que ELE viu na tela (06/11).
 *
 * 🔵 Ele: *"os itens do pós venda estão aparecendo dentro do financeiro e
 * contratual. qual a dificuldade em natê-los separados?"* · e o desenho: *"o
 * financeiro tera suas proprias abas, mas por agora só 1, o mesmo para o
 * contratual, só o pós venda ja temos as duas pipelines em abas"*.
 *
 * 🚨 **O DEFEITO.** A `PainelAba.vue` declarava `AS_ABAS = [PNL_1.2, PNL_1.3]`
 * em código e filtrava só por **permissão**. Reusei a tela nos dois painéis
 * novos: quem é owner tem as duas abas do Pós-venda, então a tira delas
 * aparecia **dentro** do Financeiro e do Contratual. ⚠️ Não era permissão
 * errada — era a lista **não ter dono**.
 *
 * 🚨 **A TRAVA NÃO CITA "o Financeiro tem uma aba".** Ela monta a tela com o
 * que o servidor devolve e cobra que a tira mostre **exatamente** as abas
 * daquele quadro. No dia em que ele criar a segunda aba do Financeiro, nada
 * aqui muda — foi o erro que eu cometi hoje com a lista fixa de painéis.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const estado = vi.hoisted(() => ({
  sessao: { nome: 'Iago', owner: true, telas: [] },
  rota: { meta: { codigo: 'PNL_1.4', aba: 'PNL_1.4' }, query: {}, params: {} },
  quadro: null,
}))

vi.mock('./api/cliente.js', () => ({
  api: {
    get: () => Promise.resolve(estado.quadro),
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

vi.mock('./estado/sessao.js', () => ({
  sessao: estado.sessao,
  codigosPermitidos: { value: new Set() },
  sair: () => {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => estado.rota,
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

import PainelAba from './telas/PainelAba.vue'

/* O registro como o `/api/telas` o devolve ao owner. 🚨 `PNL_1.2` e `PNL_1.3`
   com o MESMO título — é o registro de verdade, e é por isso que o título da
   tira vem do banco. */
const TELAS = [
  { codigo: 'PNL_1.2', titulo: 'Pós-venda', rota: '/paineis/pos-venda', aba_de: null, grupo: 'Painéis' },
  { codigo: 'PNL_1.3', titulo: 'Pós-venda', rota: '/paineis/pos-venda/realizado', aba_de: 'PNL_1.2', grupo: 'Painéis' },
  { codigo: 'PNL_1.4', titulo: 'Financeiro', rota: '/paineis/financeiro', aba_de: null, grupo: 'Painéis' },
  { codigo: 'PNL_1.5', titulo: 'Contratual', rota: '/paineis/contratual', aba_de: null, grupo: 'Painéis' },
]

function quadroDe(painel, aba, titulo, abas, colunas) {
  return {
    painel,
    aba,
    titulo,
    abas,
    colunas: colunas.map((t, i) => ({
      chave: `e${i}`, titulo: t, situacao_id: null, etapa_id: i + 1,
      final: false, nota: null, cards: [], total: 0,
    })),
    total: 0,
    pode_mover: true,
    fora_do_quadro: {},
    etapas: [],
    desfechos: [],
  }
}

const FINANCEIRO = quadroDe('financeiro', 'PNL_1.4', 'Financeiro',
  [{ codigo_tela: 'PNL_1.4', titulo: 'Financeiro' }],
  ['Nova solicitação', 'Contratos assinados', 'INADIMPLENTES'])

const CONTRATUAL = quadroDe('contratual', 'PNL_1.5', 'Contratual',
  [{ codigo_tela: 'PNL_1.5', titulo: 'Contratual' }],
  ['Elaborar contrato', 'Assinado'])

const POS_VENDA = quadroDe('pos_venda', 'PNL_1.2', 'Treinamentos',
  [{ codigo_tela: 'PNL_1.2', titulo: 'Treinamentos' },
   { codigo_tela: 'PNL_1.3', titulo: 'Pós-venda' }],
  ['Solicitação', 'Entregue'])

/* ⚠️ O `RouterLink` e componente GLOBAL (registrado pelo plugin do
   vue-router), nao importado: mockar o modulo NAO o resolve. Sem este stub o
   Vue monta assim mesmo, so reclama no stderr, e o `href` vem `undefined` --
   exatamente o que aconteceu na primeira rodada deste arquivo. O
   `menu_grupos_2110.teste.js` ja documentava isto desde 21/10. */
const STUB_LINK = { props: ['to'], template: '<a :href="to"><slot /></a>' }

async function montar(quadro, codigo) {
  estado.quadro = quadro
  estado.rota = { meta: { codigo, aba: codigo }, query: {}, params: {} }
  const tela = mount(PainelAba, {
    global: { stubs: { RouterLink: STUB_LINK } },
  })
  await flushPromises()
  return tela
}

const tira = (tela) => tela.find('nav.abas')
const nomesDaTira = (tela) =>
  tela.findAll('nav.abas .abas__item').map((n) => n.text())

beforeEach(() => {
  estado.sessao.telas = TELAS
})

describe('a tira de abas', () => {
  it('🚨 NÃO aparece no Financeiro — foi o defeito que ele viu', async () => {
    const tela = await montar(FINANCEIRO, 'PNL_1.4')
    expect(tira(tela).exists()).toBe(false)
    // ⚠️ E o nome das abas do Pós-venda não está em NENHUM lugar da tela:
    // a asseveração acima passaria se a tira mudasse de classe.
    expect(tela.text()).not.toContain('Treinamentos')
  })

  it('🚨 NÃO aparece no Contratual', async () => {
    const tela = await montar(CONTRATUAL, 'PNL_1.5')
    expect(tira(tela).exists()).toBe(false)
    expect(tela.text()).not.toContain('Treinamentos')
  })

  it('aparece no Pós-venda, com as DUAS abas dele', async () => {
    const tela = await montar(POS_VENDA, 'PNL_1.2')
    expect(tira(tela).exists()).toBe(true)
    expect(nomesDaTira(tela)).toEqual(['Treinamentos', 'Pós-venda'])
  })

  it('mostra exatamente as abas que o SERVIDOR mandou, nem uma a mais', async () => {
    // 🚨 A trava que não envelhece: se o Financeiro ganhar uma segunda aba, o
    // servidor manda duas e a tira mostra duas -- sem editar este teste.
    const comDuas = quadroDe('financeiro', 'PNL_1.4', 'Financeiro',
      [{ codigo_tela: 'PNL_1.4', titulo: 'Financeiro' },
       { codigo_tela: 'PNL_1.5', titulo: 'Segunda aba' }],
      ['Nova solicitação'])
    const tela = await montar(comDuas, 'PNL_1.4')
    expect(nomesDaTira(tela)).toEqual(['Financeiro', 'Segunda aba'])
  })

  it('a aba que a pessoa NÃO alcança cai fora da tira', async () => {
    // ⚠️ A permissão continua valendo, e de graça: a tira resolve a rota pelo
    // `sessao.telas`, e aba que não está lá não tem para onde apontar.
    // 🔵 É o caso dele: *"a Erika, apenas a aba 3"*.
    estado.sessao.telas = TELAS.filter((t) => t.codigo !== 'PNL_1.3')
    const tela = await montar(POS_VENDA, 'PNL_1.2')
    expect(tira(tela).exists()).toBe(false)
  })

  it('o link de cada aba sai do REGISTRO, não de uma rota escrita na tela', async () => {
    const tela = await montar(POS_VENDA, 'PNL_1.2')
    const hrefs = tela.findAll('nav.abas .abas__item')
      .map((n) => n.attributes('href'))
    expect(hrefs).toEqual(['/paineis/pos-venda', '/paineis/pos-venda/realizado'])
  })

  it('marca a aba atual, e só ela', async () => {
    const tela = await montar(POS_VENDA, 'PNL_1.2')
    const atuais = tela.findAll('nav.abas .abas__item--atual').map((n) => n.text())
    expect(atuais).toEqual(['Treinamentos'])
  })

  it('o rótulo do `nav` é o do painel aberto, e não fixo no Pós-venda', async () => {
    // ⚠️ Com a tela servindo cinco abas de três painéis, "Abas do Pós-venda"
    // seria a tela mentindo para quem usa leitor de tela.
    const tela = await montar(POS_VENDA, 'PNL_1.2')
    expect(tira(tela).attributes('aria-label')).toBe('Abas de Treinamentos')
  })

  it('as colunas do quadro são as que o servidor mandou', async () => {
    // Guarda contra o conserto da tira ter quebrado o resto da tela.
    const tela = await montar(FINANCEIRO, 'PNL_1.4')
    expect(tela.findAll('.coluna').length).toBe(3)
    expect(tela.text()).toContain('INADIMPLENTES')
  })
})
