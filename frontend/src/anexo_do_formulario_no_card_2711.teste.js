/*
 * @vitest-environment jsdom
 *
 * O ANEXO DO FORMULÁRIO, DENTRO DO CARD ABERTO — 27/11.
 *
 * Ele, 27/11: *"quem ve usa tudo"* · *"pode subir tudo"*.
 *
 * O QUE A MEDIÇÃO MOSTROU: a ficha do chamado já trazia `chamado.anexos` --
 * os arquivos que a pessoa anexou no formulário --, e o diálogo NÃO os
 * desenhava. O orçamento chegava ao servidor, ficava em `formulario_arquivo`,
 * aparecia na tela de Solicitações, e no card não havia sinal dele.
 *
 * E A PORTA: a rota que serve o arquivo exigia `FRM_1.1`, que é owner. Agora
 * vale `FRM_1.1` OU a tela da aba do card -- senão este botão daria 403 a quem
 * tem o painel.
 *
 * ESTE ARQUIVO TOCA QUATRO PAINÉIS (o diálogo é compartilhado), então há trava
 * para o caso COM anexo e para o caso SEM: card sem anexo não pode ganhar um
 * cabeçalho com nada embaixo, que é o que parece defeito.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const CARD = {
  id: 9001, etapa_id: 7547, cliente: 'Iago Vannucci', cliente_id: null,
  numero_os: null, numero_ordem: null, os_id: null, situacao_id: null,
  formulario: 'Sugestão de compras', slug: 'compras',
  resumo: 'Cabo de rede cat6 · Iago Vannucci',
  criada_em: '2026-11-27T14:30:00-03:00', observacoes: 0, anexos: 1,
  placas: [], tecnicos: [], termo: null, termo_a_mao: false, desfecho: null,
}

const estado = vi.hoisted(() => ({ baixados: [], anexos: [] }))

vi.mock('./util/baixar.js', () => ({
  baixarArquivo: (rota, nome) => {
    estado.baixados.push({ rota, nome })
    return Promise.resolve()
  },
}))

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (url) => Promise.resolve(
      String(url).includes('/chamado/')
        ? {
            card: { ...CARD },
            chamado: {
              solicitacao_id: 7001,
              formulario: 'Sugestão de compras',
              respostas: [
                { nome: 'SUGESTAO', rotulo: 'Justificativa',
                  valor: 'Cabo de rede cat6, 20 metros' },
              ],
              anexos: estado.anexos,
            },
            observacoes: [],
            historico: [],
            etapas: [{ id: 7547, titulo: 'Nova solicitação' }],
          }
        : {}),
    post: () => Promise.resolve({ id: 1, observacoes: [] }),
    put: () => Promise.resolve({}),
    del: () => Promise.resolve({}),
  },
  ErroDeApi: class ErroDeApi extends Error {},
}))

vi.mock('./estado/sessao.js', () => ({
  sessao: { nome: 'Iago', usuario: { owner: true, id: 1 }, owner: true, telas: [] },
  codigosPermitidos: { value: new Set(['PNL_1.7']) },
  sair: () => {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ meta: {}, query: {}, params: {} }),
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

import DialogoDeChamado from './componentes/DialogoDeChamado.vue'

beforeEach(() => {
  estado.baixados = []
  estado.anexos = [
    { id: 321, campo: 'ANEXO', nome_original: 'orcamento-tecnet.pdf',
      bytes: 184320, mime: 'application/pdf' },
  ]
})

async function abrir() {
  const d = mount(DialogoDeChamado, {
    props: { card: { ...CARD }, aba: 'PNL_1.7' },
  })
  await flushPromises()
  await flushPromises()
  return d
}

describe('o anexo do formulário aparece no card aberto', () => {
  it('mostra o nome do arquivo que a pessoa anexou', async () => {
    const d = await abrir()
    expect(d.text()).toContain('orcamento-tecnet.pdf')
  })

  it('e diz o tamanho, para quem decide se vale abrir', async () => {
    const d = await abrir()
    expect(d.text()).toMatch(/180 KB|184 KB|0,2 MB|180,0 KB/)
  })

  it('baixa pela rota da SOLICITAÇÃO, não pela do recado', async () => {
    /* São duas pastas e duas rotas diferentes: `formulario_arquivo` (o que a
       pessoa anexou no envio) e `os_observacao_arquivo` (o que alguém juntou
       numa observação). Trocar uma pela outra dá 404. */
    const d = await abrir()
    await d.find('.anexo__baixar').trigger('click')
    await flushPromises()
    expect(estado.baixados.length).toBe(1)
    expect(estado.baixados[0].rota)
      .toBe('/api/solicitacoes/7001/arquivo/321')
    expect(estado.baixados[0].nome).toBe('orcamento-tecnet.pdf')
  })

  it('usa o helper compartilhado de baixar, e não um link cru', async () => {
    /* O `util/baixar.js` existe porque o mesmo defeito apareceu em três telas:
       `<a href>` cru não leva o cabeçalho de sessão, e o 401 abria uma aba em
       branco em silêncio. */
    const d = await abrir()
    expect(d.find('.anexo__baixar').element.tagName).toBe('BUTTON')
    expect(d.find('.anexo__baixar').attributes('href')).toBeUndefined()
  })

  it('vários anexos saem todos, cada um com o seu id', async () => {
    estado.anexos = [
      { id: 321, campo: 'ANEXO', nome_original: 'orcamento-a.pdf', bytes: 1024, mime: 'application/pdf' },
      { id: 322, campo: 'ANEXO', nome_original: 'orcamento-b.pdf', bytes: 2048, mime: 'application/pdf' },
    ]
    const d = await abrir()
    const botoes = d.findAll('.anexo__baixar')
    expect(botoes.length).toBe(2)
    await botoes[1].trigger('click')
    await flushPromises()
    expect(estado.baixados[0].rota).toBe('/api/solicitacoes/7001/arquivo/322')
  })
})

describe('sem anexo, a tela não promete nada', () => {
  it('não desenha a seção de anexos', async () => {
    /* A caixa "A OS no Harmonit" já ensinou isto neste mesmo arquivo: um
       cabeçalho com nada embaixo é o que parece defeito. */
    estado.anexos = []
    const d = await abrir()
    expect(d.find('.anexo__baixar').exists()).toBe(false)
    expect(d.text()).not.toContain('Anexos do formulário')
  })
})
