/**
 * @vitest-environment jsdom
 *
 * O PAINEL DE COMPRAS (`PNL_1.7`) — a `PainelAba` com outro `meta.aba`, 27/11.
 *
 * 🔵 Ele, 27/11: *"proponha um novo de compras, sem vinculo de OS somente por
 * formularios"*, *"nao precisa propor colunas alem da primeira: nova
 * solicitacoes"*, *"sera somente interno"*, e *"nao mexa nos outros, apenas
 * tenha o padrao de layout, card fechado, card aberto, css"*.
 *
 * 🚨 **NENHUM `.vue` DE PAINEL NASCEU, E ESTA TRAVA É O QUE PROVA.** Ela monta
 * a `PainelAba` de sempre com `meta.aba = 'PNL_1.7'` e cobra que a tela
 * desenhe o painel de Compras. Se alguém um dia criar um `PainelCompras.vue`,
 * esta trava continua passando — mas a de baixo, a do componente importado,
 * cai. Em 25/11 EDITAR a `PainelAba` mexeu em quatro painéis dele sem pedir;
 * reusá-la sem tocar nela é o contrário disso.
 *
 * 🚨 **O QUADRO DAQUI É O DE PRODUÇÃO, copiado em 27/11** de
 * `paineis.quadro_da_aba('PNL_1.7')` e de um card real do Contratual (4360) —
 * e não um objeto que eu inventei com a forma que me daria verde.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const estado = vi.hoisted(() => ({
  sessao: { nome: 'Iago', owner: true, telas: [] },
  rota: { meta: { codigo: 'PNL_1.7', aba: 'PNL_1.7' }, query: {}, params: {} },
  quadro: null,
  pedidos: [],
}))

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (url) => { estado.pedidos.push(url); return Promise.resolve(estado.quadro) },
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
  codigosPermitidos: { value: new Set(['PNL_1.7']) },
  sair: () => {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => estado.rota,
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

import PainelAba from './telas/PainelAba.vue'

/* O card como `paineis._card_do_chamado` o devolve para uma solicitação sem
   OS. 🚨 Os quatro nulos (`numero_os`, `os_id`, `numero_ordem`, `situacao_id`)
   são FIXOS no servidor, e são eles que mantêm o card fora do ERP. */
const CARD = {
  id: 9001, origem: 'chamado', etapa_id: 7547, solicitacao_id: 7001,
  formulario: 'Sugestão de compras', slug: 'compras',
  criada_em: '2026-11-27T14:30:00-03:00', estado: null,
  cliente: 'Iago Vannucci', cliente_id: null,
  resumo: 'Cabo de rede cat6, 20 metros, para o rack da sala 2 · Iago Vannucci',
  anexos: 1,
  numero_os: null, os_id: null, numero_ordem: null,
  situacao_id: null, situacao_em: null,
  tipo_nome: null, status_str: null, finalizada: null,
  placas: [], tecnicos: [], visto_em: null,
  etapa_desde: '2026-11-27T14:30:00-03:00',
  prazo: null, observacoes: 0, prioridade: null, prioridade_nome: null,
  termo: null, termo_a_mao: false, termo_por_nome: null, termo_em: null,
  desfecho: null, desfecho_em: null, desfecho_rotulo: null, desfecho_por: null,
  telefone: null,
}

function quadro(cards) {
  return {
    painel: 'compras', aba: 'PNL_1.7', titulo: 'Compras',
    abas: [{ codigo_tela: 'PNL_1.7', titulo: 'Compras' }],
    colunas: [{
      chave: 'e7547', titulo: 'Nova solicitação', situacao_id: null,
      etapa_id: 7547, final: false, nota: null,
      cards, total: cards.length,
    }],
    total: cards.length,
    pode_mover: true,
    fora_do_quadro: {},
    etapas: [{ id: 7547, titulo: 'Nova solicitação' }],
    desfechos: [],
  }
}

async function montar() {
  const d = mount(PainelAba)
  await flushPromises()
  await flushPromises()
  return d
}

beforeEach(() => {
  estado.pedidos = []
  estado.quadro = quadro([])
  estado.rota = { meta: { codigo: 'PNL_1.7', aba: 'PNL_1.7' }, query: {}, params: {} }
})

describe('o painel vem da rota, não de uma tela nova', () => {
  it('busca a aba PNL_1.7 e não outra', async () => {
    await montar()
    expect(estado.pedidos.some((u) => u.includes('/api/paineis/aba/PNL_1.7')))
      .toBe(true)
  })

  it('mostra o título Compras', async () => {
    const d = await montar()
    expect(d.text()).toContain('Compras')
  })
})

describe('a coluna única', () => {
  it('é UMA, e chama Nova solicitação', async () => {
    const d = await montar()
    const colunas = d.findAll('.coluna')
    expect(colunas.length).toBe(1)
    expect(colunas[0].text()).toContain('Nova solicitação')
  })

  it('vazia diz "Vazia.", e é o certo no primeiro dia', async () => {
    const d = await montar()
    expect(d.text()).toContain('Vazia.')
  })

  it('🚨 busca que não casa diz a OUTRA frase, não "Vazia."', async () => {
    /* 🚨 Os dois vazios são distintos de propósito (`M12`): dizer "Vazia."
       quando a busca escondeu tudo é a tela mentindo — a coluna TEM card. */
    estado.quadro = quadro([CARD])
    const d = await montar()
    const busca = d.find('.controles__busca input')
    await busca.setValue('zzz-nada-casa-com-isto')
    await flushPromises()
    expect(d.text()).toContain('casa com a busca')
    expect(d.text()).not.toContain('Vazia.')
  })
})

describe('o card fechado — padrão herdado, sem OS', () => {
  it('🚨 mostra o SOLICITANTE, e nunca "fora do nosso cadastro"', async () => {
    /* 🚨 A TRAVA MAIS IMPORTANTE DO ARQUIVO. `paineis._nome_do_chamado` lê só
       `COMPANY_TITLE` e `CONTACT_NAME`; Compras não tem cliente, tem quem
       pediu. Com os dois vazios o card escreveria literalmente
       `cliente ?, fora do nosso cadastro` — tela que mente (`M12`). É por
       isso que o campo do formulário se chama `CONTACT_NAME`, e nenhuma linha
       de `paineis.py` ou `CorpoDoCard.vue` precisou mudar. */
    estado.quadro = quadro([CARD])
    const d = await montar()
    expect(d.text()).toContain('Iago Vannucci')
    expect(d.text()).not.toContain('fora do nosso cadastro')
  })

  it('🚨 identifica-se pelo FORMULÁRIO, nunca por um número de OS', async () => {
    /* ⚠️ Chamado não tem número de OS e a tela não inventa um. Se um dia
       `numero_os` chegar preenchido aqui, o card ganharia o botão "OS ..." e
       o arrasto para o ERP — o oposto do *"sem vinculo de OS"* dele. */
    estado.quadro = quadro([CARD])
    const d = await montar()
    const ident = d.find('.card__os')
    expect(ident.text()).toBe('Sugestão de compras')
    expect(d.text()).not.toMatch(/\bOS \d/)
  })

  it('mostra o resumo, que é a justificativa', async () => {
    /* 🚨 O resumo lidera com a sugestão, e isso custou uma medição: `valores`
       é `jsonb`, que ordena a chave por TAMANHO. Com o nome `JUSTIFICATIVA`
       (13) o `CONTACT_NAME` (12) passava na frente e o resumo repetia o nome
       que já é o título. O campo virou `SUGESTAO` (8) por causa disso — ver
       `docs/02_Modelo_Dados.md`, migração 122. */
    estado.quadro = quadro([CARD])
    const d = await montar()
    const resumo = d.find('.card__resumo')
    expect(resumo.text().startsWith('Cabo de rede cat6')).toBe(true)
  })

  it('não oferece situação do ERP para mover', async () => {
    /* ⚠️ O único `<select>` da tela é o ordenador do topo. O de mover
       situação é da `PainelOperacao`, e card sem `situacao_id` não o ganha. */
    estado.quadro = quadro([CARD])
    const d = await montar()
    const selects = d.findAll('select')
    expect(selects.length).toBe(1)
    expect(d.find('.controles__ordem').exists()).toBe(true)
  })
})
