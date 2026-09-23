/**
 * @vitest-environment jsdom
 *
 * A Caixa de entrada de 23/09 -- o que a TELA desenha e o que ela MANDA.
 *
 * Os itens dele daquele dia que chegam a esta tela:
 *   21  o recado do convite vira nota; o resumo diz onde fica
 *   17  a bolinha do estado de quem responde (lista, cabeçalho, seletores)
 *   22  a aba "Time"
 *   11  bloquear e desbloquear, e o acesso a "Bloqueados"
 *   16  editar e apagar a MINHA mensagem, dentro da janela do WhatsApp
 *
 * ⚠️ Mesma disciplina do `ficha_e_rotulos.teste.js`: afirma TEXTO VISÍVEL e o
 * que vai para a API -- nunca `title` como prova de que dá para achar.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

let respostas
let posts
let gets

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      gets.push(rota)
      const chave = Object.keys(respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      // Rota marcada como NEGADA devolve erro, como o 403 real.
      if (chave && respostas[chave] === 'NEGADO') return Promise.reject(new Error('403'))
      return Promise.resolve(chave ? JSON.parse(JSON.stringify(respostas[chave])) : {})
    },
    post: (rota, corpo) => { posts.push({ rota, corpo }); return Promise.resolve({ ok: true }) },
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

const agoraMenos = (min) => new Date(Date.now() - min * 60000).toISOString()

function mensagem(id, { autor = 1, idade = 1, direcao = 'saida', tipo = 'texto' } = {}) {
  return {
    id, direcao, tipo, autor: direcao === 'entrada' ? 'cliente' : 'atendente',
    conteudo: `mensagem ${id}`, criada_em: agoraMenos(idade), entrega: 'enviada',
    atendente_id: autor, atendente_nome: autor === 1 ? 'Teste' : 'Outra', reacoes: [],
  }
}

const CONVERSA = {
  id: 7, tipo: 'direta', telefone_e164: '+5599900000007', nome_whatsapp: 'Cliente',
  contato_id: null, contato_nome: null, atendente_id: 1, atendente_nome: 'Teste',
  atendente_estado: 'ausente', canal_nome: 'Atendimento', estado: 'humano',
  mensagens: [], tem_anteriores: false, janela: 40, empresa: null, bitrix: null,
  candidatos: [], bloqueio: null,
}

function estadoPadrao() {
  return {
    '/api/conversas/resumo': { conversas: 3, sem_dono: 1, eventos_pendentes: 0, bloqueados: 0 },
    '/api/conversas/7/participantes': {
      participantes: [], sou_dono: true, sou_participante: true, eu: 1,
      convidaveis: [{ id: 5, nome: 'Rodrigo', estado: 'offline' }],
      transferiveis: [{ id: 5, nome: 'Rodrigo', estado: 'ausente' }],
    },
    '/api/conversas/7': { ...CONVERSA },
    '/api/conversas?': [{ ...CONVERSA, atendente_estado: 'offline' }],
    '/api/conversas/buscar-empresa': { itens: [] },
    '/api/times': [{ id: 3, nome: 'Financeiro', qtd_membros: 9 }],
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
  const w = mount(CaixaDeEntrada)
  await assentar(w)
  await w.vm.abrir(7)
  await assentar(w)
  return w
}

const botao = (w, texto) => w.findAll('button').find((b) => b.text().trim() === texto)
const postado = (fim) => posts.filter((p) => p.rota.endsWith(fim))

beforeEach(() => { respostas = estadoPadrao(); posts = []; gets = [] })

describe('22 — a aba Time', () => {
  it('existe, e pede as conversas dos MEUS times', async () => {
    const w = mount(CaixaDeEntrada)
    await assentar(w)
    const aba = w.findAll('.abas__aba').find((b) => b.text() === 'Time')
    expect(aba, 'a aba Time não está na tela').toBeTruthy()
    gets = []
    await aba.trigger('click')
    await assentar(w)
    expect(gets.some((g) => g.includes('meus_times=true'))).toBe(true)
  })

  it('vazia, diz o motivo dela', async () => {
    respostas['/api/conversas?'] = []
    const w = mount(CaixaDeEntrada)
    await assentar(w)
    await w.findAll('.abas__aba').find((b) => b.text() === 'Time').trigger('click')
    await assentar(w)
    expect(w.text()).toContain('Nenhuma conversa sem dono nos times de que você faz parte')
  })
})

describe('17 — o estado de quem responde', () => {
  it('a lista pinta a bolinha do dono', async () => {
    const w = mount(CaixaDeEntrada)
    await assentar(w)
    expect(w.find('.conversas__item .estado-bolinha').exists()).toBe(true)
  })

  it('o cabeçalho diz o estado em TEXTO', async () => {
    const w = await aberta()
    expect(w.text()).toContain('· em pausa')
  })

  it('convidar e transferir mostram o estado de cada um', async () => {
    const w = await aberta()
    await botao(w, 'Convidar').trigger('click')
    await assentar(w)
    expect(w.text()).toContain('fora do expediente')
    await botao(w, 'Cancelar').trigger('click')
    await botao(w, 'Transferir').trigger('click')
    await assentar(w)
    const opcao = w.findAll('option').find((o) => o.text().startsWith('Rodrigo'))
    expect(opcao.text()).toBe('Rodrigo — em pausa')
  })
})

describe('21 — o recado vira nota', () => {
  it('convidar com recado grava a nota interna', async () => {
    const w = await aberta()
    await botao(w, 'Convidar').trigger('click')
    await assentar(w)
    await w.find('.modal input[type="checkbox"]').setValue(true)
    const campo = w.findAll('.modal input.campo__entrada')[0]
    await campo.setValue('ver a placa ABC1D23')
    await w.findAll('.modal button').find((b) => b.text().startsWith('Convidar')).trigger('click')
    await assentar(w)
    expect(postado('/convidar')).toHaveLength(1)
    const nota = postado('/nota')
    expect(nota).toHaveLength(1)
    expect(nota[0].corpo.texto).toBe('Chamou Rodrigo para a conversa. Recado: ver a placa ABC1D23')
  })

  it('convidar SEM recado não cria nota', async () => {
    const w = await aberta()
    await botao(w, 'Convidar').trigger('click')
    await assentar(w)
    await w.find('.modal input[type="checkbox"]').setValue(true)
    await w.findAll('.modal button').find((b) => b.text().startsWith('Convidar')).trigger('click')
    await assentar(w)
    expect(postado('/nota')).toHaveLength(0)
  })

  it('o resumo da transferência diz onde fica', async () => {
    const w = await aberta()
    await botao(w, 'Transferir').trigger('click')
    await assentar(w)
    expect(w.text()).toContain('Fica na conversa como nota interna')
  })
})

describe('16 — editar e apagar a MINHA mensagem', () => {
  const balaoDe = (w, id) => w.findAll('.balao').find((b) => b.text().includes(`mensagem ${id}`))

  it('recente e minha: editar e apagar; de outra pessoa: nenhum', async () => {
    const w = await aberta({ mensagens: [mensagem(1), mensagem(2, { autor: 2 })] })
    expect(balaoDe(w, 1).find('[aria-label="Editar mensagem"]').exists()).toBe(true)
    expect(balaoDe(w, 1).find('[aria-label="Apagar para todos"]').exists()).toBe(true)
    expect(balaoDe(w, 2).find('[aria-label="Editar mensagem"]').exists()).toBe(false)
    expect(balaoDe(w, 2).find('[aria-label="Apagar para todos"]').exists()).toBe(false)
  })

  it('passados 15 minutos, só apagar', async () => {
    const w = await aberta({ mensagens: [mensagem(3, { idade: 20 })] })
    expect(balaoDe(w, 3).find('[aria-label="Editar mensagem"]').exists()).toBe(false)
    expect(balaoDe(w, 3).find('[aria-label="Apagar para todos"]').exists()).toBe(true)
  })

  it('mensagem do cliente não se edita', async () => {
    const w = await aberta({ mensagens: [mensagem(4, { direcao: 'entrada', autor: null })] })
    expect(balaoDe(w, 4).find('[aria-label="Editar mensagem"]').exists()).toBe(false)
  })

  it('editar manda o texto novo', async () => {
    const w = await aberta({ mensagens: [mensagem(1)] })
    await balaoDe(w, 1).find('[aria-label="Editar mensagem"]').trigger('click')
    await assentar(w)
    await w.find('.modal textarea').setValue('texto corrigido')
    await botao(w, 'Salvar').trigger('click')
    await assentar(w)
    expect(postado('/editar')[0].corpo).toEqual({ mensagem_id: 1, texto: 'texto corrigido' })
  })

  it('apagar pergunta antes, e só então manda', async () => {
    const w = await aberta({ mensagens: [mensagem(1)] })
    await balaoDe(w, 1).find('[aria-label="Apagar para todos"]').trigger('click')
    await assentar(w)
    expect(postado('/apagar')).toHaveLength(0)
    await w.vm.confirmar()
    await assentar(w)
    expect(postado('/apagar')[0].corpo).toEqual({ mensagem_id: 1 })
  })
})

describe('11 — bloquear pelo painel', () => {
  it('bloquear pergunta antes, e só então manda', async () => {
    const w = await aberta()
    await botao(w, 'Bloquear').trigger('click')
    await assentar(w)
    expect(postado('/bloquear')).toHaveLength(0)
    await w.vm.confirmar()
    await assentar(w)
    expect(postado('/bloquear')).toHaveLength(1)
  })

  it('bloqueada: a faixa diz, o Bloquear some, e Desbloquear manda', async () => {
    const w = await aberta({ bloqueio: { id: 1, bloqueado_por_nome: 'Teste' } })
    expect(w.text()).toContain('Número bloqueado pelo painel')
    expect(botao(w, 'Bloquear')).toBeFalsy()
    await botao(w, 'Desbloquear').trigger('click')
    await assentar(w)
    expect(postado('/desbloquear')).toHaveLength(1)
  })

  it('grupo não oferece bloquear', async () => {
    const w = await aberta({ tipo: 'grupo', grupo_jid: '1203@g.us', telefone_e164: null })
    expect(botao(w, 'Bloquear')).toBeFalsy()
  })

  it('com bloqueados, o placar dá acesso a eles', async () => {
    respostas['/api/conversas/resumo'].bloqueados = 2
    const w = mount(CaixaDeEntrada)
    await assentar(w)
    const acesso = botao(w, 'Bloqueados (2)')
    expect(acesso, 'o acesso a Bloqueados não está na tela').toBeTruthy()
    gets = []
    await acesso.trigger('click')
    await assentar(w)
    expect(gets.some((g) => g.includes('bloqueados=true'))).toBe(true)
  })

  it('sem bloqueados, o acesso não aparece', async () => {
    const w = mount(CaixaDeEntrada)
    await assentar(w)
    expect(w.text()).not.toContain('Bloqueados (')
  })
})

describe('o defeito de 07/08: classificação negada não apaga os times', () => {
  /* 🔴 A Caixa pedia times e classificações num Promise.all; o 403 da segunda
     derrubava a primeira, e o atendente via "Transferir" sem time nenhum. */
  it('com classificações negadas, o Transferir mostra os times', async () => {
    respostas['/api/classificacoes'] = 'NEGADO'
    const w = await aberta()
    await botao(w, 'Transferir').trigger('click')
    await assentar(w)
    const opcoes = w.findAll('option').map((o) => o.text())
    expect(opcoes.some((t) => t.startsWith('Financeiro')), opcoes.join(' | ')).toBe(true)
  })
})
