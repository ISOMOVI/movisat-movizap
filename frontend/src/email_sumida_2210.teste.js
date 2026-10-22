/**
 * @vitest-environment jsdom
 *
 * A mensagem que SUMIU do Gmail, na tela — 22/10.
 *
 * 🔵 Decisão dele: ela aparece na **Lixeira**, marcada como "só a nossa cópia".
 *
 * 🚨 O DEFEITO QUE ISTO DEFENDE, E EU É QUE O TORNEI ALCANÇÁVEL. Mover as
 * sumidas para a Lixeira (backend, mesmo dia) pôs o botão **"Restaurar"** na
 * frente delas — colado num aviso que diz *"Não dá para restaurar lá"*. E não
 * era só feio: para uma mensagem que não existe mais, TODA escrita no Gmail
 * devolve 404 (`modify` → `GmailIndisponivel` → 503 na tela). Vale para
 * "Restaurar", "Arquivar" e o envelope de "não lida".
 *
 * Antes de hoje isso era latente: a sumida ficava presa na aba Entrada, onde o
 * botão era "Excluir". Consertar faz parte da mudança, não é escopo novo.
 *
 * 🚨 ESTE ARQUIVO AFIRMA TEXTO VISÍVEL, nunca `title` nem `aria-label` — a
 * mesma regra do `ficha_e_rotulos.teste.js`, escrita lá porque foi a confusão
 * entre os dois que deixou um botão inachável por três semanas. Botão que
 * "existe" com a palavra fora da tela não existe para quem usa.
 *
 * ⚠️ Não substitui abrir a tela (`M9`): isto prova que a palavra está (ou não
 * está) no DOM. Que o chip CABE na linha, e onde, só o uso diz.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

let respostas
const pedidos = []

vi.mock('./api/cliente.js', () => ({
  api: {
    /* 🚨 A CHAVE MAIS LONGA VENCE — copiado do `ficha_e_rotulos.teste.js`, e
       aqui é indispensável: `/api/email/mensagens` engoliria
       `/api/email/mensagens/9` e abrir devolveria a LISTA no lugar da
       mensagem. Duplo que mente sobre a rota reprova código bom. */
    get: (rota) => {
      /* 🚨 GUARDA A ROTA PEDIDA. Metade do defeito de 22/10 não estava no que
         a tela desenhava, e sim no que ela MANDAVA: `caixa=lixeira` junto com
         `marcador=INBOX`. Sem registrar o pedido, nenhum teste de DOM veria
         isso -- a lista só vinha vazia, e vazio parece "não tem mensagem". */
      pedidos.push(rota)
      const chave = Object.keys(respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? respostas[chave] : {})
    },
    post: () => Promise.resolve({ ok: true }),
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
  const { computed, ref } = await import('vue')
  return {
    sessao: { usuario: { id: 1, nome: 'Teste' }, telas: [], iniciadaEm: 0 },
    codigosPermitidos: ref(new Set(['EML_1.1'])),
    autenticado: computed(() => true),
  }
})

import Email from './telas/Email.vue'

/** Uma mensagem como a API a devolve. Por padrão: viva, na lixeira. */
function msg(extra = {}) {
  return {
    id: 1,
    remetente: 'quem@fora.com',
    remetente_nome: 'Quem de Fora',
    assunto: 'um assunto',
    enviado_em: '2026-10-20T10:00:00-03:00',
    tem_anexo: false,
    lida: true,
    estrela: false,
    conta_id: 2,
    na_lixeira_desde: '2026-10-21T10:00:00-03:00',
    sumida_do_gmail_em: null,
    cliente_nome: null,
    ...extra,
  }
}

function estadoPadrao(mensagens) {
  return {
    '/api/email/caixas': { caixas: [{ id: 2, endereco: 'eu@movisat.com.br', nome_exibicao: 'Eu' }] },
    '/api/email/marcadores': { marcadores: [] },
    '/api/email/mensagens': { mensagens },
    '/api/email/mensagens/1': mensagens[0],
    '/api/email/fio': { fio: [] },
    '/api/eu/assinatura': { html: '' },
  }
}

async function assentar(w, voltas = 6) {
  for (let i = 0; i < voltas; i++) {
    await new Promise((r) => setTimeout(r, 0))
    await w.vm.$nextTick()
  }
}

/** Monta a tela e, se pedido, abre a primeira mensagem.

    🚨 A SUMIDA VAI COM `na_lixeira_desde` NULO, e isso importa. Das 266
    sumidas da caixa real, as **73** que estavam presas na aba Entrada eram
    exatamente estas: foram de ativa a inexistente ENTRE DUAS VARREDURAS e
    nunca passaram pela lixeira. Com a flag de lixeira preenchida, "Arquivar" e
    "Excluir" já estavam escondidos pela condição ANTIGA, e os testes passariam
    sem defender nada -- medido: era o que acontecia na primeira versão deste
    arquivo. */
async function montar({ sumida = false, abrir = false } = {}) {
  const m = msg(sumida
    ? { sumida_do_gmail_em: '2026-10-22T08:45:00-03:00', na_lixeira_desde: null }
    : {})
  respostas = estadoPadrao([m])
  const w = mount(Email)
  await assentar(w)
  if (abrir) {
    await w.find('.email__abrir').trigger('click')
    await assentar(w)
  }
  return w
}

beforeEach(() => { respostas = estadoPadrao([msg()]); pedidos.length = 0 })

describe('a marca na lista', () => {
  it('a sumida traz "só a nossa cópia"', async () => {
    const w = await montar({ sumida: true })
    expect(w.text()).toContain('só a nossa cópia')
  })

  it('🚨 a que só está na lixeira NÃO traz a marca', async () => {
    /* Na Lixeira convivem duas coisas diferentes, e a marca é o que as
       separa. Marca em tudo não separa nada. */
    const w = await montar({ sumida: false })
    expect(w.text()).not.toContain('só a nossa cópia')
  })
})

describe('as ações que o Gmail recusa somem', () => {
  it('a sumida não oferece "Restaurar"', async () => {
    /* 🚨 ERA O PIOR: ficava colado no aviso que diz que restaurar não dá, e
       clicar devolvia 404. */
    const w = await montar({ sumida: true, abrir: true })
    expect(w.text()).not.toContain('Restaurar')
  })

  it('a sumida não oferece "Arquivar"', async () => {
    const w = await montar({ sumida: true, abrir: true })
    expect(w.text()).not.toContain('Arquivar')
  })

  it('a sumida não oferece "Excluir" — o Gmail recusa esse também', async () => {
    /* ⚠️ Com `na_lixeira_desde` nulo (o caso das 73), a condição antiga
       (`v-if="!aberta.na_lixeira_desde"`) deixava "Excluir" à vista. */
    const w = await montar({ sumida: true, abrir: true })
    expect(w.text()).not.toContain('Excluir')
  })

  it('a sumida não oferece o botão de marcar como não lida', async () => {
    /* Este é só ícone (convenção de caixa de correio), então aqui o seletor
       é a afirmação possível -- e está marcado como exceção de propósito. */
    const w = await montar({ sumida: true, abrir: true })
    const envelopes = w.findAll('button').filter(
      (b) => (b.attributes('aria-label') || '') === 'Marcar como não lida')
    expect(envelopes).toHaveLength(0)
  })

  it('"Responder" FICA — é a única que ainda faz sentido', async () => {
    /* Responder compõe mensagem nova; não toca na original. Tirá-la junto
       transformaria "não dá para mexer no Gmail" em "não dá para nada". */
    const w = await montar({ sumida: true, abrir: true })
    expect(w.text()).toContain('Responder')
  })

  it('o aviso explica o que saiu e por quê', async () => {
    /* 🚨 Com os botões fora, o aviso é a ÚNICA explicação. Botão que
       desaparece sem palavra é o rótulo que mente, pelo avesso. */
    const w = await montar({ sumida: true, abrir: true })
    expect(w.text()).toContain('Removida do Gmail')
    expect(w.text()).toContain('única cópia que existe')
    expect(w.text()).toContain('só responder')
  })
})

describe('o contraste: a mensagem viva na lixeira não perdeu nada', () => {
  it('"Restaurar" continua lá para quem ainda dá', async () => {
    /* 🚨 O TESTE QUE IMPEDE O CONSERTO DE VIRAR REGRESSÃO. Guardar os quatro
       botões por `sumida_do_gmail_em` é fácil de errar para `na_lixeira_desde`
       e tirar o "Restaurar" de TODA a Lixeira -- que é a função da aba. */
    const w = await montar({ sumida: false, abrir: true })
    expect(w.text()).toContain('Restaurar')
  })

  it('e ela não oferece "Excluir", que é o par do Restaurar', async () => {
    const w = await montar({ sumida: false, abrir: true })
    expect(w.text()).not.toContain('Excluir')
  })
})

// ---- as quatro caixas (22/10) --------------------------------------------

describe('Enviados é lugar, não etiqueta', () => {
  it('a aba Enviados está na fileira de caixas', async () => {
    const w = await montar()
    const abas = w.findAll('.caixas--secundaria .caixas__aba').map((n) => n.text())
    expect(abas).toEqual(['Entrada', 'Enviados', 'Arquivadas', 'Lixeira'])
  })

  it('🚨 "Entrada" e "Enviados" NÃO aparecem mais na lista de etiquetas', async () => {
    /* A duplicação era o defeito: dois controles dizendo "onde estou", e a
       tela mandando os dois ao servidor de uma vez. */
    respostas = estadoPadrao([msg()])
    respostas['/api/email/marcadores'] = {
      marcadores: [
        { id: 1, id_externo: 'INBOX', nome: 'INBOX', natureza: 'sistema', quantidade: 9 },
        { id: 2, id_externo: 'SENT', nome: 'SENT', natureza: 'sistema', quantidade: 9 },
        { id: 3, id_externo: 'STARRED', nome: 'STARRED', natureza: 'sistema', quantidade: 2 },
        { id: 4, id_externo: 'Clientes', nome: 'Clientes', natureza: 'usuario', quantidade: 5 },
      ],
    }
    const w = mount(Email)
    await assentar(w)
    const etiquetas = w.findAll('.email__marcador').map((n) => n.text())
    expect(etiquetas.join(' ')).not.toContain('Caixa de entrada')
    expect(etiquetas.join(' ')).not.toContain('Enviados')
    // e as que SÃO etiqueta continuam lá
    expect(etiquetas.join(' ')).toContain('Com estrela')
    expect(etiquetas.join(' ')).toContain('Clientes')
  })

  it('clicar numa caixa manda `caixa=` e NÃO manda etiqueta', async () => {
    /* 🚨 ERA O BUG DAS 11: ir para a Lixeira mantinha `marcador=INBOX`, e a
       Lixeira mostrava só o que tinha o rótulo da Entrada. */
    const w = await montar()
    pedidos.length = 0
    const lixeira = w.findAll('.caixas--secundaria .caixas__aba')
      .find((n) => n.text() === 'Lixeira')
    await lixeira.trigger('click')
    await assentar(w)
    const lista = pedidos.filter((r) => r.startsWith('/api/email/mensagens?'))
    expect(lista.length).toBeGreaterThan(0)
    expect(lista[lista.length - 1]).toContain('caixa=lixeira')
    expect(lista[lista.length - 1]).toContain('marcador=&')
  })

  it('a barra diz o LUGAR, não a etiqueta', async () => {
    /* 🚨 Com o marcador começando em 'INBOX', esta linha escrevia "Caixa de
       entrada" mesmo com a Lixeira aberta -- `M12`, e passou despercebido
       porque os dois controles concordavam por acidente. */
    const w = await montar()
    const lixeira = w.findAll('.caixas--secundaria .caixas__aba')
      .find((n) => n.text() === 'Lixeira')
    await lixeira.trigger('click')
    await assentar(w)
    expect(w.find('.email__barra').text()).toContain('Lixeira')
    expect(w.find('.email__barra').text()).not.toContain('Caixa de entrada')
  })
})
