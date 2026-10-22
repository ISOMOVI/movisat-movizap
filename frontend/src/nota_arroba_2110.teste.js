/**
 * @vitest-environment jsdom
 *
 * O `@` da NOTA INTERNA na Caixa (21/10). Pedido dele: *"E o @ nas notas
 * internas tbm funcionaria, certo?"* -- e não funcionava: a lista não abria
 * fora de grupo e a tela apagava as menções da nota.
 *
 * 🚨 A MESMA TECLA, DOIS UNIVERSOS. Em grupo o `@` chama participante do
 * WhatsApp (JID); em conversa direta chama GENTE NOSSA (atendente), e o aviso
 * sai pelo chat interno. Estes testes guardam que um não vira o outro.
 *
 * ⚠️ Afirma o que a tela DESENHA e o que ela MANDA -- nunca o estado interno.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

let respostas
let posts
let gets
let respostaDoPost

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      gets.push(rota)
      const chave = Object.keys(respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? JSON.parse(JSON.stringify(respostas[chave])) : {})
    },
    post: (rota, corpo) => {
      posts.push({ rota, corpo })
      return Promise.resolve(respostaDoPost)
    },
    put: () => Promise.resolve({ ok: true }),
    del: () => Promise.resolve({ ok: true }),
  },
  pedirBlob: () => Promise.resolve(new Blob()),
  definirToken: () => {},
  temToken: () => true,
  quandoPerderSessao: () => {},
  relatarErroDeBotao: () => {},
  ErroDeApi: class ErroDeApi extends Error {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, params: {} }),
  useRouter: () => ({ replace: () => {}, push: () => {} }),
}))

vi.mock('./estado/sessao.js', async () => {
  const { computed, ref } = await import('vue')
  return {
    sessao: { usuario: { id: 1, nome: 'Teste' }, telas: [], iniciadaEm: 0 },
    codigosPermitidos: ref(new Set(['ATD_1.2', 'CAD_1.2', 'ATD_6.1'])),
    autenticado: computed(() => true),
  }
})

import CaixaDeEntrada from './telas/CaixaDeEntrada.vue'

const CONVERSA = {
  id: 7, tipo: 'direta', telefone_e164: '+5511932726146',
  nome_whatsapp: 'Murilo', contato_id: 9, contato_nome: 'Murilo Augusto | YUV',
  atendente_id: 1, atendente_nome: 'Teste', atendente_estado: 'disponivel',
  canal_nome: 'Atendimento', estado: 'humano', mensagens: [],
  tem_anteriores: false, janela: 40, empresa: null, bitrix: null,
  candidatos: [], bloqueio: null,
}

const INTERNOS = {
  pessoas: [
    { id: 2, nome: 'Thiago', dono: false },
    { id: 3, nome: 'Erika', dono: false },
  ],
}

function estadoPadrao() {
  return {
    '/api/conversas/resumo': { conversas: 1, sem_dono: 0, eventos_pendentes: 0, bloqueados: 0 },
    '/api/conversas/7/participantes': {
      participantes: [], sou_dono: true, sou_participante: true, eu: 1,
      convidaveis: [], transferiveis: [],
    },
    '/api/conversas/7/quem-chamar-interno': INTERNOS,
    '/api/conversas/7/quem-chamar': { participantes: [{ jid: 'x@s.whatsapp.net', nome: 'Cliente Zé' }] },
    '/api/conversas/7': { ...CONVERSA },
    '/api/conversas?': [{ ...CONVERSA }],
    '/api/conversas/buscar-empresa': { itens: [] },
    '/api/times': [],
    '/api/classificacoes': [],
  }
}

async function assentar(w, voltas = 6) {
  for (let i = 0; i < voltas; i++) {
    await new Promise((r) => setTimeout(r, 0))
    await w.vm.$nextTick()
  }
}

async function aberta(extra = {}) {
  respostas['/api/conversas/7'] = { ...CONVERSA, ...extra }
  respostas['/api/conversas?'] = [{ ...CONVERSA, ...extra }]
  const w = mount(CaixaDeEntrada)
  await assentar(w)
  await w.vm.abrir(7)
  await assentar(w)
  return w
}

const campo = (w) => w.find('textarea.campo__entrada')
const botao = (w, texto) => w.findAll('button').find((b) => b.text().trim() === texto)

/* Digita no compositor e dispara o `@` como o navegador faria. */
async function digitar(w, texto) {
  const c = campo(w)
  c.element.value = texto
  c.element.selectionStart = texto.length
  await c.trigger('input')
  await assentar(w, 3)
}

beforeEach(() => {
  respostas = estadoPadrao()
  posts = []
  gets = []
  respostaDoPost = { ok: true, chamados: [], avisos_falhos: [] }
})

describe('a lista do @ em conversa direta é de gente NOSSA', () => {
  it('🚨 pede a lista interna, e não a do grupo', async () => {
    const w = await aberta()
    gets = []
    await digitar(w, 'olha isso @')
    expect(gets.some((g) => g.includes('quem-chamar-interno'))).toBe(true)
    expect(gets.some((g) => g.endsWith('/quem-chamar'))).toBe(false)
  })

  it('mostra quem está na conversa', async () => {
    const w = await aberta()
    await digitar(w, 'olha isso @')
    const itens = w.findAll('.arroba__item').map((b) => b.text())
    expect(itens).toContain('Thiago')
    expect(itens).toContain('Erika')
  })

  it('a busca depois do @ filtra pelo nome', async () => {
    const w = await aberta()
    await digitar(w, 'olha isso @thi')
    expect(w.findAll('.arroba__item').map((b) => b.text())).toEqual(['Thiago'])
  })

  it('🚨 em GRUPO continua sendo a lista do WhatsApp', async () => {
    const w = await aberta({ tipo: 'grupo', grupo_nome: 'Tecnofrota',
                             grupo_jid: 'g@g.us' })
    gets = []
    await digitar(w, 'fala @')
    expect(gets.some((g) => g.endsWith('/quem-chamar'))).toBe(true)
    expect(gets.some((g) => g.includes('quem-chamar-interno'))).toBe(false)
  })
})

describe('escolher, e o que a tela promete', () => {
  it('insere o @Nome no texto', async () => {
    const w = await aberta()
    await digitar(w, 'olha isso @')
    await w.findAll('.arroba__item')[0].trigger('mousedown')
    await assentar(w, 3)
    expect(campo(w).element.value).toContain('@Thiago')
  })

  it('🚨 o chip diz que o aviso vai pelo CHAT, não pelo WhatsApp', async () => {
    const w = await aberta()
    await digitar(w, 'olha isso @')
    await w.findAll('.arroba__item')[0].trigger('mousedown')
    await assentar(w, 3)
    const linha = w.find('.chamados')
    expect(linha.text()).toContain('na nota interna, aviso pelo chat')
    expect(linha.text()).toContain('Thiago')
  })
})

describe('o que vai para a API', () => {
  async function comChamado(w) {
    await digitar(w, 'confere isso @')
    await w.findAll('.arroba__item')[0].trigger('mousedown')
    await assentar(w, 3)
  }

  it('a nota manda `chamar` com o id, e nenhum `mencionados`', async () => {
    const w = await aberta()
    await comChamado(w)
    await botao(w, 'Salvar nota').trigger('click')
    await assentar(w)
    const nota = posts.find((p) => p.rota.endsWith('/nota'))
    expect(nota.corpo.chamar).toEqual([2])
    expect(nota.corpo.mencionados).toBeUndefined()
  })

  it('⚠️ apagar o @Nome à mão desfaz o chamado', async () => {
    const w = await aberta()
    await comChamado(w)
    await digitar(w, 'confere isso sem chamar ninguem')
    await botao(w, 'Salvar nota').trigger('click')
    await assentar(w)
    expect(posts.find((p) => p.rota.endsWith('/nota')).corpo.chamar).toEqual([])
  })

  it('🚨 enviar AO CLIENTE com chamado escolhido pergunta antes', async () => {
    const w = await aberta()
    await comChamado(w)
    const perguntas = []
    vi.stubGlobal('confirm', (t) => { perguntas.push(t); return false })
    await botao(w, 'Enviar ao cliente').trigger('click')
    await assentar(w)
    expect(perguntas[0]).toContain('PARA O CLIENTE')
    expect(perguntas[0]).toContain('Thiago')
    expect(posts.filter((p) => p.rota.endsWith('/responder'))).toHaveLength(0)
    vi.unstubAllGlobals()
  })

  it('confirmando, vai ao cliente sem chamar ninguém', async () => {
    const w = await aberta()
    await comChamado(w)
    vi.stubGlobal('confirm', () => true)
    await botao(w, 'Enviar ao cliente').trigger('click')
    await assentar(w)
    const enviada = posts.find((p) => p.rota.endsWith('/responder'))
    expect(enviada).toBeTruthy()
    expect(enviada.corpo.chamar).toBeUndefined()
    vi.unstubAllGlobals()
  })
})

describe('🚨 o que a tela diz depois — o backend é que sabe', () => {
  async function salvarChamando(w) {
    await digitar(w, 'confere isso @')
    await w.findAll('.arroba__item')[0].trigger('mousedown')
    await assentar(w, 3)
    await botao(w, 'Salvar nota').trigger('click')
    await assentar(w)
  }

  it('aviso que saiu, diz quem foi avisado', async () => {
    respostaDoPost = { ok: true, chamados: [{ id: 2, nome: 'Thiago' }],
                       avisos_falhos: [] }
    const w = await aberta()
    await salvarChamando(w)
    expect(w.text()).toContain('Avisei Thiago pelo chat interno')
  })

  it('🚨 aviso que falhou NÃO é silêncio: a nota ficou, o aviso não saiu',
     async () => {
       respostaDoPost = { ok: true, chamados: [],
                          avisos_falhos: [{ id: 2, nome: 'Thiago',
                                            motivo: 'chat fora' }] }
       const w = await aberta()
       await salvarChamando(w)
       expect(w.text()).toContain('A nota ficou gravada, mas não consegui avisar Thiago')
     })
})
