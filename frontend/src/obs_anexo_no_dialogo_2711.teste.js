/*
 * @vitest-environment jsdom
 *
 * ANEXAR NA OBSERVAÇÃO, NO DIÁLOGO COMPARTILHADO — 27/11.
 *
 * Ele, 27/11: *"ja pode colocar o campo de OBS nas mesmas regras dos demais
 * paineis - com anexo, historico"* · *"quem ve usa tudo"*.
 *
 * O QUE A MEDIÇÃO MOSTROU, e muda o pedido: subir arquivo numa observação
 * estava escrito SÓ em `PainelOperacao.vue`. Este diálogo — o que Compras,
 * Contratual, Financeiro e Pós-venda usam — baixava anexo que já existisse e
 * não tinha como anexar. Então "as mesmas regras dos demais painéis" era, até
 * hoje, SEM anexo.
 *
 * ESTE ARQUIVO TOCA QUATRO PAINÉIS DE UMA VEZ, e é o risco de 25/11 (mexer na
 * tela compartilhada mudou quatro painéis sem ele pedir). Por isso há trava
 * para o caminho NOVO e trava para o caminho ANTIGO — salvar observação sem
 * anexo tem de continuar exatamente como era.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const CARD = {
  id: 9001, etapa_id: 7547, cliente: 'Iago Vannucci', cliente_id: null,
  numero_os: null, numero_ordem: null, os_id: null, situacao_id: null,
  formulario: 'Sugestão de compras', slug: 'compras',
  resumo: 'Cabo de rede cat6, 20 metros · Iago Vannucci',
  criada_em: '2026-11-27T14:30:00-03:00', observacoes: 0, anexos: 1,
  placas: [], tecnicos: [], termo: null, termo_a_mao: false, desfecho: null,
}

const estado = vi.hoisted(() => ({
  posts: [],
  uploads: [],
  fichas: 0,
  respostaDoUpload: { ok: true, status: 201, corpo: { id: 77 } },
}))

function ficha() {
  estado.fichas += 1
  return {
    card: { ...CARD },
    chamado: { solicitacao_id: 7001, respostas: [] },
    observacoes: [],
    historico: [],
    etapas: [{ id: 7547, titulo: 'Nova solicitação' }],
  }
}

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (url) => Promise.resolve(
      String(url).includes('/chamado/') ? ficha() : {}),
    post: (url, corpo) => {
      estado.posts.push([url, corpo])
      /* A rota do chamado devolve o `id` da observação criada -- é por ele que
         o anexo sobe, e não pelo primeiro item da lista. */
      return Promise.resolve({ id: 5001, observacoes: [] })
    },
    put: () => Promise.resolve({}),
    del: () => Promise.resolve({}),
  },
  ErroDeApi: class ErroDeApi extends Error {},
  baixarArquivo: () => Promise.resolve(),
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
  estado.posts = []
  estado.uploads = []
  estado.fichas = 0
  estado.respostaDoUpload = { ok: true, status: 201, corpo: { id: 77 } }

  global.fetch = vi.fn((url, opcoes) => {
    estado.uploads.push({ url, opcoes })
    return Promise.resolve({
      ok: estado.respostaDoUpload.ok,
      status: estado.respostaDoUpload.status,
      text: () => Promise.resolve(JSON.stringify(estado.respostaDoUpload.corpo)),
      json: () => Promise.resolve(estado.respostaDoUpload.corpo),
    })
  })
  global.localStorage.setItem('movizap.token', 'fingido')
})

async function abrir() {
  const d = mount(DialogoDeChamado, {
    props: { card: { ...CARD }, aba: 'PNL_1.7' },
  })
  await flushPromises()
  await flushPromises()
  return d
}

function arquivo(nome = 'orcamento.pdf') {
  return new File([new Uint8Array([37, 80, 68, 70])], nome,
                  { type: 'application/pdf' })
}

async function escolher(d, arq) {
  const campo = d.find('input[type="file"]')
  Object.defineProperty(campo.element, 'files', { value: [arq], configurable: true })
  await campo.trigger('change')
  await flushPromises()
}

describe('o controle de anexar', () => {
  it('existe no diálogo, com RÓTULO visível', async () => {
    /* `title` não é rótulo: o balão do navegador demora cerca de um segundo e
       não existe em toque — o erro de 25/08 que escondeu o "Criar grupo". */
    const d = await abrir()
    expect(d.find('input[type="file"]').exists()).toBe(true)
    expect(d.text()).toContain('Anexar')
  })

  it('o arquivo escolhido aparece pelo nome antes de salvar', async () => {
    const d = await abrir()
    await escolher(d, arquivo())
    expect(d.text()).toContain('orcamento.pdf')
  })

  it('e dá para trocar de ideia e tirar o arquivo', async () => {
    const d = await abrir()
    await escolher(d, arquivo())
    await d.find('.obs__tirar').trigger('click')
    await flushPromises()
    expect(d.text()).not.toContain('orcamento.pdf')
  })
})

describe('salvar com anexo', () => {
  it('grava a observação primeiro e sobe o anexo no id DELA', async () => {
    /* O anexo pende de uma observação, então ela vem primeiro. E o id sai da
       RESPOSTA da rota, nunca do primeiro item da lista: neste diálogo a lista
       vem da mais antiga para a mais nova, e `[0]` seria a errada. */
    const d = await abrir()
    await d.find('textarea').setValue('Orçamento conferido na Tecnet.')
    await escolher(d, arquivo())
    await d.find('.obs__salvar').trigger('click')
    await flushPromises()

    expect(estado.posts.length).toBe(1)
    expect(estado.posts[0][0]).toBe('/api/paineis/operacao/chamado/observacao')
    expect(estado.posts[0][1]).toEqual(
      { solicitacao_id: 7001, texto: 'Orçamento conferido na Tecnet.' })

    expect(estado.uploads.length).toBe(1)
    expect(estado.uploads[0].url).toBe('/api/paineis/operacao/observacao/5001/anexo')
  })

  it('sobe por FormData e NÃO põe Content-Type na mão', async () => {
    /* Definir o cabeçalho quebra o upload EM SILÊNCIO: o servidor recebe corpo
       vazio porque o boundary não é o que o navegador montou. */
    const d = await abrir()
    await d.find('textarea').setValue('vai')
    await escolher(d, arquivo())
    await d.find('.obs__salvar').trigger('click')
    await flushPromises()

    const o = estado.uploads[0].opcoes
    expect(o.method).toBe('POST')
    expect(o.body instanceof FormData).toBe(true)
    expect(o.headers['Content-Type']).toBeUndefined()
    expect(o.headers.Authorization).toContain('Bearer')
  })

  it('anexo SEM texto inventa um texto com o nome do arquivo', async () => {
    /* A rota recusa texto vazio (422), e anexo solto não se explica sozinho
       daqui a três meses. É a mesma frase da Operação. */
    const d = await abrir()
    await escolher(d, arquivo())
    await d.find('.obs__salvar').trigger('click')
    await flushPromises()

    expect(estado.posts[0][1].texto).toBe('(anexo) orcamento.pdf')
    expect(estado.uploads.length).toBe(1)
  })

  it('relê a ficha do servidor depois de subir', async () => {
    /* A lista com anexos vem da ficha, nunca remendada na tela. */
    const d = await abrir()
    const antes = estado.fichas
    await d.find('textarea').setValue('vai')
    await escolher(d, arquivo())
    await d.find('.obs__salvar').trigger('click')
    await flushPromises()
    expect(estado.fichas).toBeGreaterThan(antes)
  })

  it('erro no upload aparece NA TELA e não perde o que foi digitado', async () => {
    estado.respostaDoUpload = {
      ok: false, status: 400,
      corpo: { detail: '.exe não é um tipo aceito aqui.' },
    }
    const d = await abrir()
    await d.find('textarea').setValue('texto que não pode sumir')
    await escolher(d, arquivo('virus.exe'))
    await d.find('.obs__salvar').trigger('click')
    await flushPromises()

    expect(d.text()).toContain('não é um tipo aceito aqui')
    expect(d.find('textarea').element.value).toBe('texto que não pode sumir')
  })
})

describe('o caminho ANTIGO continua igual', () => {
  it('sem arquivo, salva a observação e NÃO chama o upload', async () => {
    /* Esta é a trava do risco de 25/11: quatro painéis usam este diálogo, e o
       que já funcionava não pode mudar de comportamento. */
    const d = await abrir()
    /* ⚠️ `await` no setValue: sem ele o `recado` ainda não chegou ao ref
       e o botão está desabilitado no clique -- o teste reprovava por isso, e
       não pelo código. Os outros casos escondiam a falta porque o `escolher`
       logo abaixo já dava o flush. */
    await d.find('textarea').setValue('só texto')
    await d.find('.obs__salvar').trigger('click')
    await flushPromises()

    expect(estado.posts.length).toBe(1)
    expect(estado.posts[0][1].texto).toBe('só texto')
    expect(estado.uploads.length).toBe(0)
  })

  it('sem texto e sem arquivo, não manda nada', async () => {
    const d = await abrir()
    await d.find('.obs__salvar').trigger('click')
    await flushPromises()
    expect(estado.posts.length).toBe(0)
    expect(estado.uploads.length).toBe(0)
  })
})
