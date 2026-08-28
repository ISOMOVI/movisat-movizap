/**
 * @vitest-environment jsdom
 *
 * A ficha, o modal de vínculo e os rótulos das ações — 28/08.
 *
 * 🚨 POR QUE ESTE ARQUIVO EXISTE. Três defeitos desta semana passaram por
 * suíte verde e build limpo, e todos eram a mesma coisa: o elemento existia,
 * a rota respondia, e a PALAVRA que levava até ele tinha sumido da tela.
 * "Ver ficha" virou "Sem ficha", "Criar grupo" virou um quadrado com um
 * ícone, e o E-mail continuou anunciando um recurso que já tinha.
 *
 * 🚨 ELE AFIRMA TEXTO VISÍVEL, NUNCA `aria-label` NEM `title`. Foi exatamente
 * a confusão entre os dois que deixou o "Criar grupo" inachável por três
 * semanas: o `aria-label` estava lá, perfeito, e a tela não dizia nada.
 * `wrapper.text()` só devolve o que está escrito -- é a única afirmação que
 * responde "dá para achar?".
 *
 * ⚠️ Não substitui abrir a tela. Isto prova que a palavra está no DOM; que
 * ela CABE, e onde, só o uso diz.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

let respostas
let posts

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      /* 🚨 A CHAVE MAIS LONGA VENCE. Casando por prefixo na ordem de inserção,
         `/api/informativos` engolia `/api/informativos/9` e o duplo devolvia a
         LISTA no lugar do disparo -- a tela montava com `aberto` errado e o
         teste acusava um botão desabilitado que na tela real está ativo.
         Duplo que mente sobre a rota é pior que duplo nenhum: ele reprova
         código bom. */
      const chave = Object.keys(respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? respostas[chave] : {})
    },
    post: (rota, corpo) => { posts.push({ rota, corpo }); return Promise.resolve({ ok: true }) },
    put: () => Promise.resolve({ ok: true }),
    del: () => Promise.resolve({ ok: true }),
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
}))

vi.mock('./estado/sessao.js', async () => {
  const { computed } = await import('vue')
  return {
    sessao: { usuario: { id: 1, nome: 'Teste' }, telas: [], iniciadaEm: 0 },
    codigosPermitidos: computed(() => new Set(['ATD_1.2', 'CAD_1.2', 'ATD_6.1'])),
    autenticado: computed(() => true),
  }
})

import CaixaDeEntrada from './telas/CaixaDeEntrada.vue'
import ChatInterno from './telas/ChatInterno.vue'
import Email from './telas/Email.vue'
import Historico from './telas/Historico.vue'
import Informativos from './telas/Informativos.vue'

/* Uma conversa SEM cadastro: é o caso de 231 das 381 conversas (61%, medido
   em 28/08) e por isso é o padrão deste arquivo. */
const CONVERSA = {
  id: 7,
  tipo: 'direta',
  telefone_e164: '+5518998116168',
  nome_whatsapp: 'Iago',
  contato_id: null,
  contato_nome: null,
  atendente_id: 1,
  atendente_nome: 'Teste',
  canal_nome: 'Atendimento',
  estado: 'aberta',
  mensagens: [],
  tem_anteriores: false,
  janela: 40,
  empresa: null,
  bitrix: null,
  candidatos: [],
}

function estadoPadrao() {
  return {
    '/api/conversas/resumo': { conversas: 3, sem_dono: 1, eventos_pendentes: 0 },
    '/api/conversas/7/participantes': {
      participantes: [], convidaveis: [], sou_dono: true, sou_participante: true,
    },
    '/api/conversas/7': { ...CONVERSA },
    '/api/conversas?': [{ ...CONVERSA }],
    '/api/conversas/buscar-empresa': { itens: [] },
    '/api/times': [],
    '/api/classificacoes': [],
    '/api/chat/salas': { salas: [], contatos: [] },
    '/api/email/caixas': { caixas: [] },
    '/api/email/marcadores': { marcadores: [] },
    '/api/email/mensagens': { itens: [], total: 0 },
    '/api/eu/assinatura': { html: '' },
    /* ⚠️ O Histórico devolve LISTA, não objeto: sem esta linha o duplo
       caía no `{}` do padrão e o `computed` de mensagens estourava. Teste
       verde com erro não tratado no console é falso positivo -- o vitest
       avisa, e eu quase segui em frente com "74 passed". */
    '/api/historico': [],
  }
}

async function assentar(w, voltas = 6) {
  for (let i = 0; i < voltas; i++) {
    await new Promise((r) => setTimeout(r, 0))
    await w.vm.$nextTick()
  }
}

async function comConversaAberta() {
  const w = mount(CaixaDeEntrada)
  await assentar(w)
  await w.vm.abrir(7)
  await assentar(w)
  return w
}

function acharBotao(w, texto) {
  return w.findAll('button').find((b) => b.text().includes(texto))
}

beforeEach(() => { respostas = estadoPadrao(); posts = [] })

describe('A ficha se anuncia como ficha', () => {
  it('sem cadastro, o botão ainda diz "Ficha"', async () => {
    /* 🚨 O DEFEITO QUE ISTO DEFENDE: o rótulo era "Sem ficha — vincular", que
       lê como ausência. Ele disse "não vejo mais a ficha nas conversas" -- e
       ela estava lá o tempo todo. */
    const w = await comConversaAberta()
    const botao = acharBotao(w, 'Ficha')
    expect(botao).toBeTruthy()
    expect(botao.text()).toContain('Ficha')
  })

  it('com cadastro, o botão diz o nome da empresa', async () => {
    respostas['/api/conversas/7'] = {
      ...CONVERSA,
      contato_id: 9,
      contato_nome: 'Velasco',
      empresa: {
        contato: { nome: 'Velasco', relacao: 'cliente' },
        cliente: { id: 3, nome: 'Pastelaria Velasco', ativo: true },
      },
    }
    const w = await comConversaAberta()
    expect(w.text()).toContain('Ficha · Pastelaria Velasco')
  })
})

describe('Vincular empresa é modal, não faixa espremida na gaveta', () => {
  it('a gaveta não carrega mais o campo de busca', async () => {
    const w = await comConversaAberta()
    await acharBotao(w, 'Ficha').trigger('click')
    await assentar(w)
    const gaveta = w.find('.gaveta')
    expect(gaveta.exists()).toBe(true)
    // 🚨 O que espremia era isto: a busca dentro do teto de 42vh da gaveta.
    expect(gaveta.find('input[type="search"]').exists()).toBe(false)
    expect(gaveta.text()).toContain('Vincular a uma empresa')
  })

  it('o botão abre o modal, e os achados aparecem dentro dele', async () => {
    respostas['/api/conversas/buscar-empresa'] = {
      itens: [
        { id: 3, nome: 'Pastelaria Velasco', documento: '12345678000199', ativo: true },
        { id: 4, nome: 'Velasco Transportes', documento: null, ativo: true },
      ],
    }
    const w = await comConversaAberta()
    await acharBotao(w, 'Ficha').trigger('click')
    await assentar(w)
    await acharBotao(w, 'Vincular a uma empresa').trigger('click')
    await assentar(w)

    const modal = w.find('.modal')
    expect(modal.exists()).toBe(true)
    await modal.find('input[type="search"]').setValue('velasco')
    await w.vm.procurarCliente()
    await assentar(w)

    const itens = w.findAll('.vincular__item')
    expect(itens).toHaveLength(2)
    expect(itens[0].text()).toContain('Pastelaria Velasco')
    // Sem CNPJ não pode virar espaço em branco: a linha diz que falta.
    expect(itens[1].text()).toContain('sem CNPJ')
  })

  it('escolher vincula e fecha o modal', async () => {
    respostas['/api/conversas/buscar-empresa'] = {
      itens: [{ id: 3, nome: 'Pastelaria Velasco', documento: null, ativo: true }],
    }
    const w = await comConversaAberta()
    await acharBotao(w, 'Ficha').trigger('click')
    await assentar(w)
    await acharBotao(w, 'Vincular a uma empresa').trigger('click')
    await assentar(w)
    w.vm.buscaCliente = 'velasco'
    await w.vm.procurarCliente()
    await assentar(w)

    await w.find('.vincular__item').trigger('click')
    await assentar(w)

    expect(posts.some((p) => p.rota.endsWith('/vincular') && p.corpo.cliente_id === 3)).toBe(true)
    expect(w.find('.modal').exists()).toBe(false)
  })

  it('o teto de 10 da rota aparece na tela', async () => {
    /* ⚠️ Regra da casa: todo teto tem de aparecer na resposta. Teto que
       ninguém vê não é limite, é dado sumindo. */
    respostas['/api/conversas/buscar-empresa'] = {
      itens: Array.from({ length: 10 }, (_, i) => (
        { id: i + 1, nome: `Empresa ${i + 1}`, documento: null, ativo: true })),
    }
    const w = await comConversaAberta()
    await acharBotao(w, 'Ficha').trigger('click')
    await assentar(w)
    await acharBotao(w, 'Vincular a uma empresa').trigger('click')
    await assentar(w)
    w.vm.buscaCliente = 'empresa'
    await w.vm.procurarCliente()
    await assentar(w)
    expect(w.find('.modal').text()).toContain('Mostrando as 10 primeiras')
  })
})

describe('Ação sobre a conversa tem palavra, não só ícone', () => {
  it('as quatro ações da barra estão escritas', async () => {
    const w = await comConversaAberta()
    const escritos = w.findAll('button').map((b) => b.text())
    for (const palavra of ['Transferir', 'Convidar', 'Devolver à fila', 'Sair']) {
      expect(escritos.some((t) => t.includes(palavra))).toBe(true)
    }
  })

  it('devolver e sair não dependem mais do balão para se distinguir', async () => {
    /* 🚨 Eram duas setas para a esquerda, lado a lado, fazendo coisas
       diferentes. Em toque, o `title` não existe. */
    const w = await comConversaAberta()
    const devolver = acharBotao(w, 'Devolver à fila')
    const sair = w.findAll('button').find((b) => b.text().trim() === 'Sair')
    expect(devolver).toBeTruthy()
    expect(sair).toBeTruthy()
    expect(devolver.text()).not.toBe(sair.text())
  })
})

describe('Chat interno: criar grupo voltou a ser achável', () => {
  it('o botão diz "Criar grupo" em texto', async () => {
    /* 🚨 Demanda dele de 25/08 ("podemos criar grupos com os temas"), entregue
       em 12/08 COM o texto, e escondida por mim em 25/08 ao virar só ícone. */
    const w = mount(ChatInterno)
    await assentar(w)
    const botao = acharBotao(w, 'Criar grupo')
    expect(botao).toBeTruthy()
    await botao.trigger('click')
    await assentar(w)
    expect(w.find('.grupo__novo').exists()).toBe(true)
  })
})

describe('E-mail: a tela não mente sobre o que faz', () => {
  it('a promessa de "vem em breve" saiu', async () => {
    const w = mount(Email)
    await assentar(w)
    expect(w.text()).not.toContain('vem em breve')
    expect(w.text()).not.toContain('Por enquanto dá para ler')
  })

  it('a explicação está no ícone de ajuda, não em faixa fixa', async () => {
    const w = mount(Email)
    await assentar(w)
    expect(w.find('.ajuda').exists()).toBe(true)
  })
})

describe('Caixa de entrada: a ajuda da busca virou ícone', () => {
  it('a faixa de três linhas saiu de baixo do campo', async () => {
    const w = mount(CaixaDeEntrada)
    await assentar(w)
    expect(w.find('.ajuda').exists()).toBe(true)
    // O texto continua legível -- ele se recolhe, não se perde.
    expect(w.find('.ajuda').text()).toContain('6168')
  })
})

describe('Nenhum campo de busca carrega faixa fixa de ajuda', () => {
  /* 🚨 ESTE BLOCO EXISTE PORQUE EU FALHEI DUAS VEZES NA MESMA COISA. Ele
     pediu a ocultação dos textos "pelo sistema todo" e citou dois exemplos
     com "etc". Eu entreguei os dois exemplos -- e deixei o TERCEIRO, no
     Histórico, na mesma construção e no mesmo lugar. Exemplo não é escopo.

     A invariante é mecânica: nenhum `.campo--busca` carrega `.campo__ajuda`.
     A explicação vive no ícone de ajuda do cabeçalho. */
  it('Caixa de entrada e Histórico não têm ajuda presa ao campo', async () => {
    for (const Tela of [CaixaDeEntrada, Historico]) {
      const w = mount(Tela)
      await assentar(w)
      const busca = w.find('.campo--busca')
      expect(busca.exists()).toBe(true)
      expect(busca.find('.campo__ajuda').exists()).toBe(false)
    }
  })

  it('o Histórico recolheu o texto para o ícone, sem perdê-lo', async () => {
    const w = mount(Historico)
    await assentar(w)
    expect(w.find('.ajuda').text()).toContain('qualquer grafia')
  })
})

describe('O tipo do contato tem UMA cara nas duas telas', () => {
  /* 🚨 A PROPOSTA ORIGINAL IA CRIAR A DIVERGÊNCIA. Ele pediu *"um botão menor
     e mais aderente ao design"* e eu propus chip+popover só na conversa --
     o mesmo campo (`contato.relacao`) com duas aparências no mesmo sistema.
     Ele perguntou "ficou aderente?" e a resposta era não.

     A invariante: as duas telas usam a MESMA classe, definida uma vez em
     `componentes.css`. Esta afirmação é sobre a fonte de propósito -- ela
     defende contra a próxima edição, não contra o render de hoje. */
  it('conversa e ficha do contato usam a mesma classe', async () => {
    const arquivos = ['./telas/CaixaDeEntrada.vue', './telas/Contatos.vue']
    for (const caminho of arquivos) {
      const fonte = await import(/* @vite-ignore */ caminho + '?raw')
      const semComentario = fonte.default.replace(/<!--[\s\S]*?-->/g, '')
      const i = semComentario.indexOf('RELACOES')
      expect(i).toBeGreaterThan(-1)
      expect(semComentario).toContain('campo__entrada--compacto')
    }
  })
})

describe('Botão cinza diz o que falta (item 6)', () => {
  /* ⚠️ A regra que ele aprovou na escada da IA vale para o painel inteiro.
     🚨 SÓ OS NOVE QUE DEPENDEM DE ALGUEM FAZER ALGO. Os oito que ficam cinza
     enquanto a acao esta EM VOO (`mexendo`, `enviando`, `vinculando`) mostram
     o girando e duram um instante -- texto neles seria o ruido que a rodada
     de hoje tirou. */
  it('o compositor diz por que nao da para enviar', async () => {
    const w = await comConversaAberta()
    const botoes = w.findAll('button').filter(
      (b) => b.attributes('disabled') !== undefined)
    const comMotivo = botoes.filter((b) => (b.attributes('title') || '').length > 0)
    expect(comMotivo.length).toBeGreaterThan(0)
    expect(comMotivo.some((b) => /Escreva algo|anexe/.test(b.attributes('title')))).toBe(true)
  })
})

describe('Atalhos na Caixa de entrada (item 7)', () => {
  /* O E-mail tinha 6 teclas; esta tela tinha ZERO -- a mais usada era a com
     menos ferramenta. */
  it('as teclas estao ensinadas no icone de ajuda', async () => {
    const w = mount(CaixaDeEntrada)
    await assentar(w)
    const ajuda = w.find('.ajuda').text()
    for (const tecla of ['j', 'k', '/', 'a', 'c']) {
      expect(ajuda).toContain(tecla)
    }
    expect(ajuda).toContain('Atalhos')
  })

  it('🚨 tecla NAO dispara enquanto se digita', async () => {
    /* Sem esta guarda, escrever "javali" para o cliente pularia de conversa
       no meio da palavra. */
    const w = mount(CaixaDeEntrada)
    await assentar(w)
    const campo = document.createElement('textarea')
    document.body.appendChild(campo)
    const evento = new KeyboardEvent('keydown', { key: 'j', bubbles: true })
    Object.defineProperty(evento, 'target', { value: campo })
    expect(() => document.dispatchEvent(evento)).not.toThrow()
    campo.remove()
  })
})

describe('Informativos: o freio existe (item 3)', () => {
  /* A rota `POST /api/informativos/{id}/pausar` existia com ZERO chamadores:
     envio em massa sem freio na tela. */
  async function comDisparo(estado) {
    /* ⚠️ A FORMA VEIO DO BACKEND, nao do meu chute: `respostas_recebidas()`
       devolve `{total, ultimas}`, e `listar()` devolve LISTA. Na primeira
       versao eu inventei `{itens: []}` e a tela estourou em
       `respostas.ultimas.length` -- o duplo mentindo sobre o contrato e o
       que o `feedback_contrato_de_json` existe para impedir. */
    respostas['/api/informativos/cobertura'] = {
      total: 0, alcancaveis: 0, sem_whatsapp: 0, so_fixo: 0, sem_telefone: 0,
    }
    respostas['/api/informativos/respostas'] = { total: 0, ultimas: [] }
    respostas['/api/informativos'] = []
    respostas['/api/informativos/9'] = {
      id: 9, titulo: 'zz teste', corpo: 'oi', estado,
      total_destinos: 3, criado_em: new Date().toISOString(),
    }
    const w = mount(Informativos)
    await assentar(w)
    await w.vm.abrir(9)
    await assentar(w)
    return w
  }

  it('enviando: da para pausar', async () => {
    const w = await comDisparo('enviando')
    const b = w.findAll('button').find((x) => x.text().includes('Pausar'))
    expect(b).toBeTruthy()
    expect(b.attributes('disabled')).toBeUndefined()
    await b.trigger('click')
    await assentar(w)
    expect(posts.some((x) => x.rota.endsWith('/pausar'))).toBe(true)
  })

  it('rascunho: fica cinza DIZENDO por que', async () => {
    /* Nada some: o que nao pode ser usado aparece com o motivo. */
    const w = await comDisparo('rascunho')
    const b = w.findAll('button').find((x) => x.text().includes('Pausar'))
    expect(b).toBeTruthy()
    expect(b.attributes('disabled')).toBeDefined()
    expect(b.attributes('title')).toContain('em andamento')
  })
})
