/**
 * @vitest-environment jsdom
 *
 * O ANEXO DO COMPROVANTE, PELO GESTO — 25/11 (tarefa 2.4).
 *
 * 🔵 Dele, 18/11: *"haverá campo para que em cada 1 dos artefatos de pagamento
 * seja inserido anexo que comprove o pagamento. **Após o envio do anexo, abre o
 * campo que pede o valor inserido no documento**."*
 * 🔵 24/11: o anexo é **do MoviZap, no padrão da observação da Operação**, e é
 * **anexo completo — não só PDF**.
 *
 * 🚨 **GESTO, NÃO FUNÇÃO** (`M17`, linha 2). O que esta tela já mostrou duas
 * vezes é que a lógica pode estar certa e o gesto quebrado: em 19/11 o filtro
 * de data estava correto e o defeito estava no `<input type="date">`. Então
 * aqui se **dispara o `change` do input de arquivo** e se lê o que a tela
 * passou a mostrar.
 *
 * 🚨 **A ARMADILHA ESPECÍFICA DESTE BOTÃO:** em `<script setup>` o `$refs` não
 * é exposto, então `@click="$refs.x.click()"` abriria o seletor **nunca** — e
 * nenhuma trava de atributo pegaria isso, porque o atributo estaria lá. A
 * terceira trava clica no botão de verdade.
 *
 * ⚠️ O `fetch` é dublê: o que se mede é a tela, não a rede. A rota de verdade
 * tem trava própria por HTTP (`tests/teste_rota_anexo_do_comprovante.py`).
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = vi.hoisted(() => ({ quadro: null, postado: [] }))

vi.mock('./api/cliente.js', () => {
  class ErroDeApi extends Error {}
  return {
    api: {
      get: () => Promise.resolve(estado.quadro),
      post: (c, corpo) => {
        estado.postado.push([String(c), corpo])
        return Promise.resolve({ ok: true, semaforo: 'verde' })
      },
      put: () => Promise.resolve({}),
      del: () => Promise.resolve({}),
    },
    definirToken: () => {},
    temToken: () => true,
    quandoPerderSessao: () => {},
    relatarErroDeBotao: () => {},
    ErroDeApi,
  }
})

vi.mock('./estado/sessao.js', () => ({
  sessao: { nome: 'Iago', owner: true, telas: [] },
  codigosPermitidos: { value: new Set() },
  sair: () => {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ meta: { codigo: 'PNL_1.6', aba: 'PNL_1.6' },
                     query: {}, params: {} }),
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

import PainelServicoDosTecnicos from './telas/PainelServicoDosTecnicos.vue'

const ARTEFATO = 4242

function artefato(extra = {}) {
  return { id: ARTEFATO, numero_os: 17124, orcamento_numero: null,
           termo: '8952', data_os: '18/11/2026 09:00:00', valor_pagamento: 70,
           valor_km: 10, semaforo: 'amarelo', ciente_em: '2026-11-24T10:00:00Z',
           justificativa: null, cliente: 'Zz Pastelaria Velasco',
           cliente_id: 33365, tipo_nome: 'Instalação',
           status_str: 'Serviço Realizado', datascope_form_state: null,
           comprovante_arquivo: null, valor_do_comprovante: null,
           comprovante_dispensa: null, ...extra }
}

function quadro(extra = {}) {
  return {
    painel: 'financeiro', aba: 'PNL_1.6', titulo: 'Serviço dos técnicos',
    abas: [{ codigo_tela: 'PNL_1.6', titulo: 'Serviço dos técnicos' }],
    artefatos: 1, desde: '2026-11-16', escondidos_pela_data: 0,
    colunas: [
      { chave: 'movimentacao', titulo: 'Movimentação', total: 0, cards: [] },
      { chave: 'preparacao', titulo: 'Preparação', total: 0, cards: [] },
      { chave: 'validacao', titulo: 'Validação', total: 1,
        cards: [{ tecnico_id: 55, tecnico_nome: 'Franck', lote_id: 7,
                  pode_preparar: true, artefatos: [artefato(extra)] }] },
      { chave: 'procfy', titulo: 'Procfy', total: 0, cards: [] },
      { chave: 'enviado', titulo: 'Pagamento enviado', total: 0, cards: [] },
    ],
  }
}

async function abrirATela(extra) {
  estado.quadro = quadro(extra)
  const tela = mount(PainelServicoDosTecnicos, { attachTo: document.body })
  await flushPromises()
  await flushPromises()
  return tela
}

const cardFechado = (tela, nome) =>
  tela.findAll('article.card').find((a) => a.text().includes(nome))

async function abrirOModalDoComprovante(tela) {
  const card = cardFechado(tela, 'Franck')
  expect(card, 'o card do Franck tem de estar no quadro').toBeTruthy()
  await card.find('button.card__abrir').trigger('click')
  await flushPromises()
  const botao = tela.findAll('button').find(
    (b) => b.text().includes('Comprovante') || b.text().includes('comprovante'))
  expect(botao, 'o botão do comprovante tem de existir no card aberto').toBeTruthy()
  await botao.trigger('click')
  await flushPromises()
  const modal = tela.findAll('.modal').find(
    (m) => m.text().includes('Comprovante da OS'))
  expect(modal, 'o modal do comprovante tem de abrir').toBeTruthy()
  return modal
}

/* O dublê do upload: devolve o que a rota devolve de verdade (201). */
function fetchQueAceita() {
  return vi.fn(() => Promise.resolve({
    ok: true,
    text: () => Promise.resolve(JSON.stringify({
      ok: true, id: 91, nome_original: 'recibo franck.pdf', bytes: 2048,
      referencia: 'anexo:91',
    })),
  }))
}

function fetchQueRecusa(frase) {
  return vi.fn(() => Promise.resolve({
    ok: false, status: 400,
    text: () => Promise.resolve(JSON.stringify({ detail: frase })),
  }))
}

async function escolherArquivo(modal, nome = 'recibo franck.pdf') {
  const entrada = modal.find('input[type="file"]')
  expect(entrada.exists(), 'o input de arquivo tem de existir no DOM').toBe(true)
  const arquivo = new File([new Uint8Array([1, 2, 3])], nome,
                           { type: 'application/pdf' })
  Object.defineProperty(entrada.element, 'files', { value: [arquivo],
                                                    configurable: true })
  await entrada.trigger('change')
  await flushPromises()
}

beforeEach(() => {
  estado.postado = []
  globalThis.localStorage.setItem('movizap.token', 'zz-token')
})

describe('o anexo do comprovante', () => {
  it('o campo do valor NÃO existe antes do anexo', async () => {
    const tela = await abrirATela()
    const modal = await abrirOModalDoComprovante(tela)
    expect(modal.text()).not.toContain('Valor que está no documento')
  })

  it('anexar abre o campo do valor e mostra nome e tamanho', async () => {
    globalThis.fetch = fetchQueAceita()
    const tela = await abrirATela()
    const modal = await abrirOModalDoComprovante(tela)
    await escolherArquivo(modal)

    /* 🚨 O upload foi para a rota do anexo, com `FormData` — não JSON. */
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    const [url, opcoes] = globalThis.fetch.mock.calls[0]
    expect(String(url)).toBe(
      `/api/paineis/servico-dos-tecnicos/anexo/${ARTEFATO}`)
    expect(opcoes.method).toBe('POST')
    expect(opcoes.body).toBeInstanceOf(FormData)
    /* ⚠️ Nada de `Content-Type` à mão: o boundary é do navegador. */
    expect(Object.keys(opcoes.headers)).toEqual(['Authorization'])

    /* 🔵 *"Após o envio do anexo, abre o campo que pede o valor"*. */
    expect(modal.text()).toContain('Valor que está no documento')
    expect(modal.text()).toContain('recibo franck.pdf')
    expect(modal.text()).toContain('2 KB')
    /* A referência é o que vai para o FPSL — nunca o caminho, nunca os bytes. */
    expect(modal.find('input.campo').element.value).toBe('anexo:91')
  })

  it('o botão de anexar abre o seletor de arquivo de verdade', async () => {
    /* 🚨 A trava do `$refs`: com `@click="$refs.x.click()"` em `<script
       setup>` este clique não chamaria nada, e o atributo estaria lá. */
    globalThis.fetch = fetchQueAceita()
    const tela = await abrirATela()
    const modal = await abrirOModalDoComprovante(tela)
    const entrada = modal.find('input[type="file"]')
    const abriu = vi.fn()
    entrada.element.click = abriu
    const botao = modal.findAll('button').find(
      (b) => b.text().includes('Anexar comprovante'))
    expect(botao, 'o botão "Anexar comprovante" tem de existir').toBeTruthy()
    await botao.trigger('click')
    expect(abriu).toHaveBeenCalledTimes(1)
  })

  it('recusa do servidor aparece COM A FRASE, e o valor não abre', async () => {
    globalThis.fetch = fetchQueRecusa(
      '.exe não é um tipo aceito aqui. Aceito: .csv, .doc, .pdf.')
    const tela = await abrirATela()
    const modal = await abrirOModalDoComprovante(tela)
    await escolherArquivo(modal, 'virus.exe')
    expect(modal.text()).toContain('não é um tipo aceito aqui')
    expect(modal.text()).not.toContain('Valor que está no documento')
  })

  it('anexo que já existe no quadro vira link de download', async () => {
    const tela = await abrirATela({
      comprovante_arquivo: 'anexo:91',
      comprovante_anexo: { id: 91, nome_original: 'recibo antigo.pdf',
                           bytes: 1024 * 1024 },
    })
    const modal = await abrirOModalDoComprovante(tela)
    expect(modal.text()).toContain('recibo antigo.pdf')
    expect(modal.text()).toContain('1.0 MB')
    expect(modal.text()).toContain('Trocar o arquivo')
    /* Já tem comprovante: o campo do valor já está aberto. */
    expect(modal.text()).toContain('Valor que está no documento')
  })
})
