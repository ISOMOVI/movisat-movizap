/**
 * @vitest-environment jsdom
 *
 * A AJUDA DA TELA POR PAINEL — `M12`, 27/11.
 *
 * Ele, 27/11, autorizando: *"Sim, texto por painel"*.
 *
 * O ACHADO, VARRENDO O QUE A TELA DIZ DE SI (`M12`): o balão `?` da
 * `PainelAba.vue` é o MESMO nos cinco painéis e prometia *"Clique nele para
 * abrir a ficha, os recados e o checklist"*. Em Compras o checklist **não
 * existe**: aquelas rotas são chaveadas por `numero_os`, e card de solicitação
 * não tem OS. A tela prometia um recurso impossível naquele painel.
 *
 * E NENHUM TESTE PRENDIA ESSE TEXTO — 0 ocorrências de "Arraste o card" em
 * `tests/` e em `*.teste.js`. É por isso que ele pôde apodrecer: texto sem
 * trava não acusa quando a entrega seguinte o deixa mentindo. Esta é a trava.
 *
 * ESTE ARQUIVO SERVE CINCO TELAS DELE, e foi o erro de 25/11 (mexer na tela
 * compartilhada mudou quatro painéis sem ele pedir). Por isso a defesa é
 * NOMINAL: há uma asserção por painel, e as quatro antigas são medidas
 * **palavra por palavra** contra o texto de hoje.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const estado = vi.hoisted(() => ({
  rota: { meta: { codigo: 'PNL_1.4', aba: 'PNL_1.4', titulo: 'Financeiro' }, query: {}, params: {} },
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
  sessao: { nome: 'Iago', usuario: { owner: true, id: 1 }, owner: true, telas: [] },
  codigosPermitidos: { value: new Set() },
  sair: () => {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => estado.rota,
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

import PainelAba from './telas/PainelAba.vue'

/* 🚨 O TEXTO DE HOJE, COPIADO DO ARQUIVO EM 27/11, palavra por palavra. É esta
   constante que impede os quatro painéis de mudarem de recado sem ele pedir. */
const AJUDA_DE_SEMPRE =
  'Os cards deste painel em colunas, pelas etapas nossas — as que a Movisat '
  + 'definiu, e não as situações do Harmonit. Arraste o card para mudar de '
  + 'etapa: isso grava no nosso banco e registra quem fez. Clique nele para '
  + 'abrir a ficha, os recados e o checklist.'

function quadro(titulo, colunas) {
  return {
    painel: 'x', aba: estado.rota.meta.aba, titulo,
    abas: [{ codigo_tela: estado.rota.meta.aba, titulo }],
    colunas: colunas.map((t, i) => ({
      chave: `e${i}`, titulo: t, situacao_id: null, etapa_id: i + 1,
      final: false, nota: null, cards: [], total: 0,
    })),
    total: 0, pode_mover: true, fora_do_quadro: {},
    etapas: colunas.map((t, i) => ({ id: i + 1, titulo: t })),
    desfechos: [],
  }
}

/* Espaço não conta: o template quebra linha onde cabe, e o que se mede é o
   recado, não a indentação do arquivo. */
function texto(d) {
  return d.find('.ajuda__balao').text().replace(/\s+/g, ' ').trim()
}

async function abrir(codigo, titulo, colunas) {
  estado.rota = { meta: { codigo, aba: codigo, titulo }, query: {}, params: {} }
  estado.quadro = quadro(titulo, colunas)
  const d = mount(PainelAba)
  await flushPromises()
  await flushPromises()
  return d
}

beforeEach(() => {
  estado.quadro = null
})

describe('os quatro painéis antigos não mudam de recado', () => {
  /* 🚨 LISTA NOMINAL, escrita antes do código (`M11`), e não um laço sobre um
     padrão de marcação: varredura por padrão foi o que deixou passar a
     divergência de cabeçalho em 19/11. */
  it('PNL_1.2 Pós-venda: verbatim', async () => {
    const d = await abrir('PNL_1.2', 'Pós-venda', ['Nova', 'Feito'])
    expect(texto(d)).toBe(AJUDA_DE_SEMPRE)
  })

  it('PNL_1.3 Pós-venda / Realizado: verbatim', async () => {
    const d = await abrir('PNL_1.3', 'Pós-venda', ['Nova', 'Feito'])
    expect(texto(d)).toBe(AJUDA_DE_SEMPRE)
  })

  it('PNL_1.4 Financeiro: verbatim', async () => {
    const d = await abrir('PNL_1.4', 'Financeiro', ['Nova solicitação'])
    expect(texto(d)).toBe(AJUDA_DE_SEMPRE)
  })

  it('PNL_1.5 Contratual: verbatim', async () => {
    const d = await abrir('PNL_1.5', 'Contratual', ['Nova solicitação'])
    expect(texto(d)).toBe(AJUDA_DE_SEMPRE)
  })

  it('e uma tela que eu não previ cai no texto de sempre', async () => {
    /* ⚠️ Degrada mostrando o recado genérico, nunca em branco: aba nova dele
       no futuro tem de abrir com ajuda, não com um balão vazio. */
    const d = await abrir('PNL_9.9', 'Painel futuro', ['Uma'])
    expect(texto(d)).toBe(AJUDA_DE_SEMPRE)
  })
})

describe('Compras tem o seu, e ele não promete o impossível', () => {
  it('🚨 NÃO menciona checklist', async () => {
    /* 🚨 O CORAÇÃO DO `M12` AQUI. Checklist é recurso de OS: as rotas são
       chaveadas por `numero_os` + `situacao_id`, e card de Compras nunca tem
       OS. Prometer checklist ali é prometer o que não pode existir. */
    const d = await abrir('PNL_1.7', 'Compras',
                          ['Nova solicitação', 'Em cotação', 'Aprovado', 'Comprado'])
    expect(texto(d)).not.toMatch(/checklist/i)
  })

  it('não é o texto de sempre', async () => {
    const d = await abrir('PNL_1.7', 'Compras',
                          ['Nova solicitação', 'Em cotação', 'Aprovado', 'Comprado'])
    expect(texto(d)).not.toBe(AJUDA_DE_SEMPRE)
  })

  it('diz o que o painel é: sugestão interna, sem OS', async () => {
    const d = await abrir('PNL_1.7', 'Compras',
                          ['Nova solicitação', 'Em cotação', 'Aprovado', 'Comprado'])
    const t = texto(d)
    expect(t).toMatch(/sem OS/i)
    expect(t).toMatch(/chat interno/i)
  })

  it('🔵 e promete mover, que agora é verdade', async () => {
    /* ⚠️ Até a migração 123 Compras tinha UMA coluna, e *"arraste o card"*
       era promessa vazia. Com as quatro, mover existe -- e o recado pode
       dizê-lo. Esta trava é o que amarra o texto ao que a tela faz. */
    const d = await abrir('PNL_1.7', 'Compras',
                          ['Nova solicitação', 'Em cotação', 'Aprovado', 'Comprado'])
    expect(texto(d)).toMatch(/arraste|mover|mude/i)
  })

  it('o balão existe e é alcançável por teclado nos dois casos', async () => {
    /* O `AjudaDaTela` abre no hover E no foco; se o gatilho deixar de ser
       `<button>`, quem usa teclado perde o texto. */
    for (const codigo of ['PNL_1.4', 'PNL_1.7']) {
      const d = await abrir(codigo, 'x', ['Uma'])
      expect(d.find('.ajuda__gatilho').element.tagName).toBe('BUTTON')
      expect(d.find('.ajuda__balao').exists()).toBe(true)
    }
  })
})
