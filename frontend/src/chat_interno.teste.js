/**
 * @vitest-environment jsdom
 *
 * ATD_6.1 — Chat interno: o que a pessoa ESTÁ ESCREVENDO, e quem o `@` oferece.
 *
 * 🚨 ESTES CINCO NASCERAM DE UM DEFEITO EM PRODUÇÃO (22/09). Ele relatou
 * *"alguns usuários não conseguem escrever, fica apagando sozinho a mensagem
 * antes de enviar"* -- e a suíte estava verde. O `ChatInterno.vue` tem 1.172
 * linhas e era montado por UM teste, que conferia o texto de um botão: nenhum
 * abria conversa, nenhum digitava, nenhum deixava o laço de 5 segundos rodar.
 * É o `M9` e o `M14` na mesma tela.
 *
 * ⚠️ A API DEVOLVE OBJETO NOVO A CADA CHAMADA, e o `JSON.parse(JSON.stringify(...))`
 * abaixo é DE PROPÓSITO. Era exatamente essa identidade nova que fazia o
 * `watch(sala, ...)` achar que a pessoa tinha trocado de conversa. Um dublê que
 * devolvesse sempre o mesmo objeto deixaria estes testes verdes com o defeito
 * de volta -- e foi por um dublê assim que ele passou.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

let respostas
let posts
let gets
let falharGet

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      gets.push(rota)
      if (falharGet) return Promise.reject(new Error('rede caiu'))
      const chave = Object.keys(respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? JSON.parse(JSON.stringify(respostas[chave])) : {})
    },
    post: (rota, corpo) => { posts.push({ rota, corpo }); return Promise.resolve({ ok: true }) },
    put: () => Promise.resolve({}),
    del: () => Promise.resolve({}),
  },
  pedirBlob: () => Promise.resolve(new Blob()),
  definirToken: () => {},
  temToken: () => true,
  quandoPerderSessao: () => {},
  ErroDeApi: class ErroDeApi extends Error {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, params: {} }),
  useRouter: () => ({ replace: () => {}, push: () => {} }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('./estado/sessao.js', () => ({
  sessao: { nome: 'Fulano de Tal', telas: [], owner: false },
  sair: () => {},
}))

import ChatInterno from './telas/ChatInterno.vue'

/* jsdom não implementa object URL, e o compositor e o balão dependem dele
   para mostrar imagem sem `<img src="/api/...">` — que não manda o cabeçalho
   de sessão. Stub simples: o que os testes conferem é o caminho, não o blob. */
if (!URL.createObjectURL) URL.createObjectURL = () => 'blob:falso'
if (!URL.revokeObjectURL) URL.revokeObjectURL = () => {}

function base({ enter = true, mensagens = [] } = {}) {
  return {
    '/api/eu/atalhos': { ligados: false, teclas: {}, catalogo: [], enviar_com_enter: enter },
    '/api/chat/salas/1': { mensagens },
    '/api/chat/salas/9/membros': {
      membros: [
        { atendente_id: 5, nome: 'Rodrigo', sou_eu: false },
        { atendente_id: 7, nome: 'Claudia', sou_eu: false },
      ],
    },
    '/api/chat/salas/9': { mensagens: [] },
    '/api/chat/salas': {
      salas: [
        { id: 1, tipo: 'direta', com: 'Erika', com_estado: 'disponivel', nao_lidas: 0 },
        { id: 9, tipo: 'grupo', nome: 'Financeiro', nao_lidas: 0 },
      ],
      contatos: [{ id: 5, nome: 'Rodrigo' }, { id: 7, nome: 'Claudia' }],
    },
  }
}

async function abrirSala(tela, rotulo) {
  const alvo = tela.findAll('.ci__sala').find((b) => b.text().includes(rotulo))
  await alvo.trigger('click')
  await flushPromises()
}

async function digitarArroba(tela, valor) {
  const campo = tela.get('textarea')
  campo.element.value = valor
  campo.element.selectionStart = valor.length
  await campo.trigger('input')
  await flushPromises()
  return campo
}

beforeEach(() => { respostas = base(); posts = []; gets = []; falharGet = false })

describe('Chat interno: o rascunho', () => {
  it('sobrevive ao ciclo de atualização de 5 s', async () => {
    vi.useFakeTimers()
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Erika')

    await t.get('textarea').setValue('Erika, o cliente da placa ABC1D23 ligou pedindo')
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()

    expect(t.get('textarea').element.value)
      .toBe('Erika, o cliente da placa ABC1D23 ligou pedindo')
    vi.useRealTimers()
  })

  it('sobrevive a TRÊS ciclos seguidos — quem escreve devagar também', async () => {
    vi.useFakeTimers()
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Erika')

    await t.get('textarea').setValue('mensagem comprida')
    await vi.advanceTimersByTimeAsync(15000)
    await flushPromises()

    expect(t.get('textarea').element.value).toBe('mensagem comprida')
    vi.useRealTimers()
  })

  /* 🚨 A INTENÇÃO ORIGINAL NÃO PODE SE PERDER. O `watch` existe para isto, e
     corrigir o critério não pode virar "nunca mais limpa": sem isto, você
     manda para a Erika o que escreveu para o grupo. */
  it('É apagado quando a conversa muda DE VERDADE', async () => {
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Erika')
    await t.get('textarea').setValue('isto era para a Erika')

    await abrirSala(t, 'Financeiro')

    expect(t.get('textarea').element.value).toBe('')
  })
})

describe('Chat interno: quem o `@` oferece', () => {
  it('não oferece os membros do GRUPO numa conversa de dois', async () => {
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Financeiro')
    await abrirSala(t, 'Erika')

    await digitarArroba(t, '@')

    expect(t.findAll('.arroba__item').map((b) => b.text())).toEqual([])
  })

  it('continua oferecendo os membros DENTRO do grupo', async () => {
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Financeiro')

    await digitarArroba(t, '@')

    expect(t.findAll('.arroba__item').map((b) => b.text()).join(' '))
      .toContain('Rodrigo')
  })
})

describe('Chat interno: o ciclo de fundo é mudo', () => {
  it('queda de rede no ciclo silencioso NÃO pinta faixa de erro', async () => {
    vi.useFakeTimers()
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Erika')

    falharGet = true
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    falharGet = false

    expect(t.find('.aviso--erro').exists()).toBe(false)
    vi.useRealTimers()
  })
})

describe('Chat interno: o anexo (22/09)', () => {
  /* 🚨 RÓTULO, NÃO SÓ ÍCONE. Esta tela já perdeu o "Criar grupo" assim em
     25/08: a função continuou inteira e ficou inachável. `title` não é
     rótulo — o balão demora cerca de um segundo e não existe em toque. */
  it('os botões de anexar e gravar dizem o que fazem, em texto', async () => {
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Erika')

    expect(t.text()).toContain('Anexar')
    expect(t.text()).toContain('Gravar')
  })

  it('colar um print põe o anexo à vista antes de enviar', async () => {
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Erika')

    const png = new File([new Uint8Array([1, 2, 3])], 'x.png', { type: 'image/png' })
    await t.get('textarea').trigger('paste', {
      clipboardData: { items: [{ type: 'image/png', getAsFile: () => png }] },
    })
    await flushPromises()

    // Sem esta linha na tela, quem cola não vê nada acontecer e cola de novo.
    expect(t.text()).toMatch(/print-/)
  })

  it('arquivo acima do teto é barrado ANTES de subir', async () => {
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Erika')

    const gordo = new File([new Uint8Array(10)], 'g.bin', { type: 'application/octet-stream' })
    Object.defineProperty(gordo, 'size', { value: 26 * 1024 * 1024 })
    const campo = t.get('input[type="file"]')
    Object.defineProperty(campo.element, 'files', { value: [gordo], configurable: true })
    await campo.trigger('change')
    await flushPromises()

    expect(t.find('.aviso--erro').text()).toContain('25 MB')
    expect(t.text()).not.toContain('g.bin')
  })

  it('o balão mostra a imagem, e o documento vira link de baixar', async () => {
    respostas = base({
      mensagens: [
        { id: 1, texto: '', autor: 'Erika', minha: false, criada_em: new Date().toISOString(),
          midia_id: 10, midia_mime: 'image/png', midia_nome: 'print.png', midia_tamanho: 2048 },
        { id: 2, texto: 'o contrato', autor: 'Erika', minha: false, criada_em: new Date().toISOString(),
          midia_id: 11, midia_mime: 'application/pdf', midia_nome: 'contrato.pdf', midia_tamanho: 90000 },
      ],
    })
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Erika')
    await flushPromises()

    expect(t.find('.balao__imagem').exists()).toBe(true)
    expect(t.find('.balao__arquivo').text()).toContain('contrato.pdf')
  })

  it('trocar de conversa larga o anexo escolhido', async () => {
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Erika')

    const png = new File([new Uint8Array([1])], 'y.png', { type: 'image/png' })
    await t.get('textarea').trigger('paste', {
      clipboardData: { items: [{ type: 'image/png', getAsFile: () => png }] },
    })
    await flushPromises()
    expect(t.text()).toMatch(/print-/)

    await abrirSala(t, 'Financeiro')
    // Era para AQUELA conversa — é rascunho como o texto.
    expect(t.text()).not.toMatch(/print-/)
  })
})

describe('Chat interno: o Enter obedece à preferência', () => {
  it('LIGADA, Enter envia', async () => {
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Erika')

    await t.get('textarea').setValue('vai por Enter')
    await t.get('textarea').trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(posts.some((p) => p.rota.includes('/escrever'))).toBe(true)
  })

  it('DESLIGADA, Enter não envia — e Ctrl+Enter envia', async () => {
    respostas = base({ enter: false })
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Erika')

    await t.get('textarea').setValue('não vai por Enter')
    await t.get('textarea').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(posts.some((p) => p.rota.includes('/escrever'))).toBe(false)

    await t.get('textarea').trigger('keydown', { key: 'Enter', ctrlKey: true })
    await flushPromises()
    expect(posts.some((p) => p.rota.includes('/escrever'))).toBe(true)
  })
})

/* ── 23/09 ──────────────────────────────────────────────────────────────── */

describe('Chat interno: o laço de 5 s busca a lista UMA vez', () => {
  /* 🚨 Medido em 22/09: a lista ia DUAS vezes por volta -- o ciclo buscava, e o
     `abrir()` buscava de novo no fim. Com 10 pessoas de tela aberta, o dobro
     do tráfego para nenhuma novidade. */
  it('com uma conversa aberta: 1 lista e 1 sala por ciclo', async () => {
    vi.useFakeTimers()
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Erika')
    gets = []
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(gets.filter((r) => r === '/api/chat/salas')).toHaveLength(1)
    expect(gets.filter((r) => r === '/api/chat/salas/1')).toHaveLength(1)
    vi.useRealTimers()
  })

  it('o clique numa sala continua atualizando a lista na hora', async () => {
    const t = mount(ChatInterno)
    await flushPromises()
    gets = []
    await abrirSala(t, 'Erika')
    expect(gets).toContain('/api/chat/salas')
  })
})

describe('Chat interno: o destaque da menção NA TELA', () => {
  /* 🚨 O `mencao.teste.js` testava uma cópia da função. Este monta a TELA:
     se o balão deixar de usar a regra, é aqui que reprova. */
  it('acende só quem está gravado como menção, e forte para mim', async () => {
    respostas = base({ mensagens: [{
      id: 1, texto: '@Erika manda para suporte@movisat.com.br',
      mencionados: [{ id: 2, nome: 'Erika' }], me_chamou: true,
      autor: 'Rodrigo', autor_id: 5, criada_em: '2026-09-23T10:00:00-03:00',
    }] })
    const t = mount(ChatInterno)
    await flushPromises()
    await abrirSala(t, 'Erika')
    const marcas = t.findAll('mark.mencao')
    expect(marcas.map((m) => m.text())).toEqual(['@Erika'])
    expect(marcas[0].classes()).toContain('mencao--eu')
  })
})
