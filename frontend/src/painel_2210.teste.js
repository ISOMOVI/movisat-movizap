/*
 * @vitest-environment jsdom
 *
 * ⚠️ O ambiente e declarado NO ARQUIVO, como nas outras suites de tela.
 */

/* ============================================================================
   PNL_1.1 — o painel da Operação (22/10, redesenhado em 29/10)
   ----------------------------------------------------------------------------
   🚨 ESTE ARQUIVO MUDOU DE REGRA EM 29/10, e o que ele guardava antes não era
   defeito -- era o desenho de 22/10: **13 colunas** (as 11 situações de então
   mais "Sem OS" e "Sem situação"), as duas primeiras **fixas**, e a tela
   dizendo por que mover não existe.

   O que ele decidiu em 29/10:
     · *"eis as situações que precisamos manter"* -- **17**, e *"as situações já
       estão na Ordem"*;
     · *"qualquer aba fora dessas não deve estar no painel"* -- saem as duas que
       não eram situação;
     · *"os comentários tbm devem sumir dali"* -- sai o aviso de que mover não
       existe, a lista de formulários e o cartão de painel vazio.

   🚨 ATENÇÃO, ISTO MUDOU EM 29/10: até então este arquivo afirmava que **não
   há `draggable`** -- e era verdade, porque a rota que escreve a situação não
   existia. Ela existe (Bloco D), ele decidiu *"O card pode ser por arrastar"*,
   e agora o que se testa é o contrário: o card arrasta, o teclado também move
   pelo `select`, e `pode_mover` continua sendo a verdade do gesto. Coluna vazia
   nasce colapsada com o contador à vista, a cor nunca é o único portador, e o
   card leva para a ficha na `FRM_1.1`.

   🚨 E O QUE ENTROU NO LUGAR DOS TEXTOS: a linha de `fora_do_quadro`. Card sem
   OS, ou com situação fora das 17, não tem coluna -- e sumir da tela em
   silêncio é `M12`. A linha só aparece quando há o que dizer.
   ============================================================================ */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = { quadro: null, empurrado: [], postado: [],
                 resposta: null, passagens: [],
                 ficha: null, fichaFalha: false }

vi.mock('../src/api/cliente.js', () => ({}))
vi.mock('./api/cliente.js', () => ({
  api: {
    get: async (caminho) => {
      /* ⚠️ O modal le o log de passagens; sem isto o `get` devolveria o
         quadro e o teste passaria lendo a coisa errada. */
      if (String(caminho).includes('/passagens')) {
        return { passagens: estado.passagens || [] }
      }
      if (String(caminho).includes('/ficha')) {
        /* 🚨 A ficha pode FALHAR, e o teste precisa desse caminho: ficha vazia
           seria indistinguivel de OS sem dados. */
        if (estado.fichaFalha) {
          throw new Error('não deu para ler a OS 17099 no Harmonit agora')
        }
        return estado.ficha || {}
      }
      return estado.quadro
    },
    /* 🚨 O `post` registra o que foi enviado: o que importa no Bloco D é o
       CORPO do pedido (o `situacao_esperada` da trava de concorrência), não
       só que a chamada aconteceu. */
    post: async (caminho, corpo) => {
      estado.postado.push([caminho, corpo])
      return estado.resposta ?? { ok: true }
    },
  },
  ErroDeApi: class extends Error {},
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: (destino) => estado.empurrado.push(destino) }),
  useRoute: () => ({ query: {} }),
}))

import PainelOperacao from './telas/PainelOperacao.vue'

/* As 17 dele, na ORDEM dele — a mesma tupla de `movizap/paineis.py`. */
const AS_DEZESSETE = [
  [38, 'Novo Solicitação 1ª'],
  [16487, 'Pendente de ação da Movisat'],
  [251, 'Configurar equipamentos e Sistemas'],
  [16488, 'Entrega de materiais prontos'],
  [677, 'Enviar por correio/transportadora'],
  [15747, 'Aguardando recebimento via correio/transportadora'],
  [15797, 'Rescisão Aguardando Aviso Prévio'],
  [890, 'Agendar serviço'],
  [16489, 'Confirmação agendamento'],
  [1316, 'Serviço Agendado'],
  [15696, 'Aguardando devolução de equipamento'],
  [16490, 'Analise de Equipamentos Retornados'],
  [15694, 'Atendimento finalizado'],
  [16491, 'Não atendido'],
  [15746, 'Financeiro'],
  [15695, 'Pós venda'],
  [16492, 'Contratual'],
]

function quadro({ cards = {}, podeMover = false, fora = null } = {}) {
  const colunas = AS_DEZESSETE.map(([sid, titulo]) => ({
    chave: `s${sid}`, titulo, situacao_id: sid, nota: null,
    cards: cards[`s${sid}`] || [],
  }))
  for (const coluna of colunas) coluna.total = coluna.cards.length
  return {
    painel: 'operacao',
    titulo: 'Operação',
    colunas,
    total: colunas.reduce((soma, c) => soma + c.total, 0),
    pode_mover: podeMover,
    /* 🚨 A PONTE NASCE DE PE, e nao setar isto era um defeito da suite: com
       `undefined` (falso) TODOS os testes renderizavam o alarme "O FPSL nao
       respondeu", e a trava da ponte caida passava pelo motivo errado. */
    ponte_respondeu: true,
    /* O filtro e a ordem, como a resposta real os manda. */
    busca: null,
    ordem: 'prazo',
    filtro_casou_por: null,
    ordens: ['prazo', 'os_desc', 'os_asc', 'parado', 'cliente'],
    ponte_motivo: null,
    desde: '2026-10-24',
    so_abertas: true,
    fora_do_quadro: fora || {
      sem_os: 0, situacao_fora: 0, situacoes: [],
      /* 🚨 Os campos do Bloco A entram no dublê TAMBÉM no caso
         vazio: sem eles a tela leria `undefined`, a linha não
         apareceria e o teste passaria por acidente. */
      os_falhou: 0, os_falhou_chamados: 0, os_falhou_em: null,
    },
  }
}

const card = (extra = {}) => ({
  id: 7, formulario: 'Suporte', slug: 'suporte', criada_em: '2026-10-22T14:02:00-03:00',
  estado: 'nova', cliente: 'Cliente de exemplo', resumo: 'zz · prova',
  anexos: 0, os_id: 555, numero_ordem: '17042', situacao_id: 38, situacao_em: null,
  /* 🚨 Os campos de C e F entram no duble TAMBEM no caso vazio: sem
     eles a tela leria `undefined` e a trava passaria por acidente. */
  etapa_desde: null, observacoes: 0,
  prioridade: null, prioridade_nome: null,
  ...extra,
})


/* ⚠️ A faixa do card aberto tem dois selects (mover e prioridade). Procurar
   pelo ROTULO em vez do indice: indice quebra quando a ordem muda, e o rotulo
   e o que a pessoa le. */
function selectDaFaixa(tela, rotulo) {
  return tela.findAll('.faixa__campo')
    .find((l) => l.text().includes(rotulo))
    ?.find('select')
}

async function abrir(dados) {
  estado.quadro = dados
  const tela = mount(PainelOperacao)
  await flushPromises()
  return tela
}

beforeEach(() => {
  estado.postado = []
  estado.resposta = null
  estado.passagens = []
  estado.ficha = null
  estado.fichaFalha = false
  estado.empurrado = []
})

describe('as colunas', () => {
  it('🔵 são exatamente as 17 dele, e nenhuma a mais', async () => {
    const tela = await abrir(quadro())
    expect(tela.findAll('.coluna')).toHaveLength(17)
    const titulos = tela.findAll('.coluna__titulo').map((n) => n.text())
    expect(titulos[0]).toContain('Novo Solicitação 1ª')
    expect(titulos.some((t) => t.includes('Sem OS'))).toBe(false)
    expect(titulos.some((t) => t.includes('Sem situação'))).toBe(false)
  })

  it('🔵 na ORDEM dele — que é o fluxo, não alfabética', async () => {
    const tela = await abrir(quadro())
    const titulos = tela.findAll('.coluna__titulo').map((n) => n.text())
    expect(titulos[1]).toContain('Pendente de ação da Movisat')
    expect(titulos[9]).toContain('Serviço Agendado')
    expect(titulos[16]).toContain('Contratual')
  })

  it('coluna vazia nasce colapsada e a com card nasce aberta', async () => {
    const tela = await abrir(quadro({
      cards: { s15746: [card({ id: 9, situacao_id: 15746 })] },
    }))
    const colunas = tela.findAll('.coluna')
    const comCard = colunas.find((c) => c.text().includes('Financeiro'))
    const vazia = colunas.find((c) => c.text().includes('Não atendido'))
    expect(comCard.classes()).not.toContain('coluna--fechada')
    expect(vazia.classes()).toContain('coluna--fechada')
    // 🚨 Colapsada mostra o CONTADOR: ninguém precisa abrir para saber que é zero.
    expect(vazia.find('.coluna__conta').text()).toBe('0')
  })

  it('⚠️ TODA coluna colapsa — as duas fixas saíram com o redesenho', async () => {
    const tela = await abrir(quadro())
    expect(tela.findAll('.coluna__botao--fixo')).toHaveLength(0)
    expect(tela.findAll('.coluna__botao')).toHaveLength(17)
  })

  it('clicar no cabeçalho abre e fecha uma coluna vazia', async () => {
    const tela = await abrir(quadro())
    const vazia = tela.findAll('.coluna').find((c) => c.text().includes('Contratual'))
    await vazia.find('.coluna__botao').trigger('click')
    expect(vazia.classes()).not.toContain('coluna--fechada')
    expect(vazia.text()).toContain('situação 16492 no Harmonit')
  })
})

describe('🔵 os três textos que ele mandou sumir', () => {
  it('a tela não explica mais por que mover não existe', async () => {
    const tela = await abrir(quadro({ cards: { s38: [card()] } }))
    expect(tela.text()).not.toContain('escrever a situação na OS do Harmonit')
  })

  it('não lista mais os formulários com a contagem de campos', async () => {
    const tela = await abrir(quadro())
    expect(tela.text()).not.toContain('campos')
    expect(tela.find('.formularios').exists()).toBe(false)
  })

  it('e painel sem card nenhum fica CALADO, não diz que está vazio', async () => {
    const tela = await abrir(quadro())
    expect(tela.text()).not.toContain('Nenhuma solicitação')
    expect(tela.text()).not.toContain('forms.movisat.com.br')
    // ⚠️ E continua desenhando as 17 colunas: vazio não é tela quebrada.
    expect(tela.findAll('.coluna')).toHaveLength(17)
  })
})

describe('mover o card — Bloco D (29/10)', () => {
  /* 🚨 ESTA TRAVA ERA O CONTRÁRIO ATÉ 29/10: ela afirmava que **não** havia
     `draggable`, e era verdade -- a escrita de situação não existia e oferecer
     o gesto sem gravar seria pior. Ele decidiu: *"O card pode ser por
     arrastar"*. Trocar esta trava é parte de ligar o recurso, não um efeito
     colateral: a afirmação antiga deixou de ser verdadeira. */
  const comCard = () => quadro({
    cards: { s38: [card({ numero_ordem: 17099, situacao_id: 38 })] },
    podeMover: true,
  })

  it('o card arrasta quando pode mover', async () => {
    const tela = await abrir(comCard())
    expect(tela.find('.card').attributes('draggable')).toBe('true')
  })

  it('🚨 NAO arrasta quando pode_mover e falso', async () => {
    /* ⚠️ `pode_mover` continua sendo a verdade do gesto: quem não pode mover
       não recebe um card que parece arrastável. */
    const tela = await abrir(quadro({
      cards: { s38: [card({ numero_ordem: 17099 })] }, podeMover: false,
    }))
    expect(tela.find('.card').attributes('draggable')).toBe('false')
  })

  it('🚨 o CARD nao tem mais caixa de selecao', async () => {
    /* 🔵 Ele: *"pq ela foi substituida por uma caixa de selecao?"*. Ele decidiu
       arrastar, e enquanto o arrasto estava quebrado a caixa era o unico jeito
       de mover -- entao ela parecia a substituicao. Saiu do card. */
    const tela = await abrir(comCard())
    expect(tela.find('.card__mover').exists()).toBe(false)
  })

  it('🚨 o TECLADO move pelo card ABERTO, nao pelo card fechado', async () => {
    /* ⚠️ Arrastar nao e alcancavel por teclado. O caminho ficou: o numero da OS
       e um botao (abre o card com Enter) e o `select` das 17 vive DENTRO do
       card aberto. */
    const tela = await abrir(comCard())
    expect(tela.find('.card__os').element.tagName).toBe('BUTTON')
    await tela.find('.card__os').trigger('click')
    await flushPromises()
    const sel = selectDaFaixa(tela, 'Mover para')
    expect(sel.exists()).toBe(true)
    expect(sel.findAll('option')).toHaveLength(17)
    expect(sel.element.value).toBe('38')
  })

  it('🚨 manda a situacao ESPERADA no pedido — a trava de concorrencia',
     async () => {
    /* 🔵 Ele pediu a trava mesmo achando o risco pequeno: *"cada 1 atua em uma
       área especifica do fluxo"* · *"mas pode ter sim"*. Sem o
       `situacao_esperada`, mover escreveria por cima do que outra pessoa fez. */
    const tela = await abrir(comCard())
    await tela.find('.card__os').trigger('click')
    await flushPromises()
    await selectDaFaixa(tela, 'Mover para').setValue('1316')
    await flushPromises()
    expect(estado.postado).toHaveLength(1)
    expect(estado.postado[0]).toEqual([
      '/api/paineis/operacao/mover',
      { numero_os: 17099, para_situacao: 1316, situacao_esperada: 38 },
    ])
  })

  it('a recusa do servidor e DITA, com papel de alerta', async () => {
    /* 🚨 Falha silenciosa aqui faria a pessoa pensar que gravou. */
    estado.resposta = { ok: false, motivo: 'a OS esta na situacao 1316 no Harmonit' }
    const tela = await abrir(comCard())
    await tela.find('.card__os').trigger('click')
    await flushPromises()
    await selectDaFaixa(tela, 'Mover para').setValue('890')
    await flushPromises()
    const alerta = tela.findAll('[role="alert"]').map((p) => p.text()).join(' ')
    expect(alerta).toContain('no Harmonit')
  })
})

describe('🚨 o que não tem coluna é DITO, não escondido (M12)', () => {
  it('com zero, a linha não aparece — a tela fica limpa', async () => {
    const tela = await abrir(quadro())
    expect(tela.find('.aviso--atencao').exists()).toBe(false)
  })

  it('solicitação sem OS aparece como número, e sem acusar ninguém', async () => {
    /* 🚨 ESTE TESTE GUARDAVA O DEFEITO. Ele exigia a palavra "Harmonit" na
       frase -- isto é, exigia que a tela dissesse *"a escrita no Harmonit
       falhou"* para toda solicitação sem OS. Ele leu isso na tela em 29/10 e
       estava errado: a solicitação 544 nunca teve escrita tentada.
       ⚠️ O número continua sendo dito, que é o que este teste nasceu para
       guardar (`M12`). O que saiu é a CAUSA inventada. */
    const tela = await abrir(quadro({
      fora: { sem_os: 3, situacao_fora: 0, situacoes: [] },
    }))
    /* ⚠️ Sem `sem_tentativa` nem `os_falhou`, os 3 sem OS caem na SOBRA --
       "sem motivo registrado" -- que e a frase honesta para o caso em que nao
       se sabe por que o chamado nao tem OS. */
    const aviso = tela.find('.aviso--fora')
    expect(aviso.text()).toContain('3 sem OS e sem motivo registrado')
    expect(aviso.text()).not.toContain('Harmonit')
    expect(aviso.text()).toContain('Solicitações')
  })

  it('situação fora das 17 aparece com o NÚMERO CRU', async () => {
    const tela = await abrir(quadro({
      fora: {
        sem_os: 0, situacao_fora: 2, situacoes: [0, 99999],
        fora_quais: [{ numero_os: 17050, situacao_id: 0 },
                     { numero_os: 17051, situacao_id: 99999 }],
      },
    }))
    /* 🔵 Ele, 29/10: *"1 com situação fora das 17 (0)"* -> *"pq deu erro?"*.
       A contagem nao dizia QUAL OS nem DE QUEM era a situacao. Agora nomeia a
       OS e diz que o numero vem do Harmonit -- nao e defeito nosso. */
    const aviso = tela.find('.aviso--fora')
    expect(aviso.text()).toContain('a OS 17050 está em situação 0 no Harmonit')
    expect(aviso.text()).toContain('a OS 17051 está em situação 99999')
    // ⚠️ O número cru, nunca um rótulo inventado.
    expect(aviso.text()).toContain('99999')
  })
})

describe('o card', () => {
  it('leva a solicitação e a OS lado a lado', async () => {
    const tela = await abrir(quadro({ cards: { s38: [card()] } }))
    const texto = tela.find('.card__abrir').text()
    expect(texto).toContain('Suporte')
    expect(texto).toContain('Cliente de exemplo')
    expect(texto).toContain('OS 17042')
    /* 🔵 Ele: *"o card esta aparecendo como 'situacao n' - obviamente deve ser
       o texto da situacao real"*. 🚨 Eu havia invertido a regua da casa: o
       valor cru e a EXCECAO, para a situacao fora das 17. */
    expect(texto).toContain('Novo Solicitação 1ª')
    expect(texto).not.toContain('situação 38')
  })

  it('OS sem situação lida diz isso, e não finge um número', async () => {
    const tela = await abrir(quadro({
      cards: { s38: [card({ id: 13, situacao_id: null })] },
    }))
    expect(tela.find('.card__abrir').text()).toContain('situação nunca lida')
  })

  it('o estado vem escrito, não só na cor', async () => {
    const tela = await abrir(quadro({
      cards: { s38: [card({ estado: 'em_andamento' })] },
    }))
    expect(tela.find('.etiqueta').text()).toBe('Em andamento')
  })

  it('🚨 clicar ABRE O CARD, e NAO manda para outra aba', async () => {
    /* 🚨 ESTA TRAVA GUARDAVA O DEFEITO, e foi ele quem o achou no navegador:
       *"ao clicar no card nao esta abrindo o proposto no mockup, esta
       direcionando para outra aba"*. Ela exigia o `router.push` para
       `/solicitacoes` -- e desde a D8 a MAIORIA dos cards vem do ERP e nao tem
       solicitacao, entao o push levava para uma tela com consulta vazia.
       Agora o clique abre o card, que e o que o mockup propoe. */
    const tela = await abrir(quadro({
      cards: { s38: [card({ id: 42, numero_ordem: 17099 })] },
    }))
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    expect(estado.empurrado).toEqual([])
    expect(tela.find('.modal').exists()).toBe(true)
    expect(tela.find('.modal').text()).toContain('OS 17099')
  })

  it('o card do ERP abre sem botao de Solicitacoes', async () => {
    /* ⚠️ Sem solicitacao nao ha ficha para abrir -- e o botao nem aparece, em
       vez de levar para uma consulta vazia. */
    const tela = await abrir(quadro({
      cards: { s38: [card({ id: null, numero_ordem: 17098 })] },
    }))
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    expect(tela.find('.modal').exists()).toBe(true)
    expect(tela.find('.modal').text()).not.toContain('Ver o chamado')
  })

  it('o card de formulario tem o botao, e ele empurra para a FRM_1.1',
     async () => {
    const tela = await abrir(quadro({
      cards: { s38: [card({ id: 42, numero_ordem: 17099 })] },
    }))
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    const botoes = tela.findAll('.modal__acoes button')
    const ver = botoes.find((b) => b.text().includes('Ver o chamado'))
    expect(ver).toBeTruthy()
    await ver.trigger('click')
    expect(estado.empurrado).toEqual([
      { path: '/solicitacoes', query: { solicitacao: 42 } },
    ])
  })

  it('🚨 o conteudo do card NAO e um <button> — era o que impedia o arrasto',
     async () => {
    /* 🚨 A CAUSA DO ARRASTO NAO FUNCIONAR, achada no navegador por ele:
       navegador nao inicia o arrasto do pai a partir de um elemento
       interativo. O `<article draggable>` era preenchido inteiro por um
       `<button>`, o `mousedown` morria nele e o `dragstart` nunca disparava.

       ⚠️ A minha outra trava afirma `attributes('draggable') === 'true'`, que
       era VERDADE enquanto o gesto era impossivel. **Trava de atributo nao e
       trava de gesto** -- esta aqui olha o que de fato impedia. */
    const tela = await abrir(quadro({
      cards: { s38: [card({ numero_ordem: 17099 })] }, podeMover: true,
    }))
    expect(tela.find('.card__abrir').element.tagName).toBe('DIV')
    /* E o numero da OS continua focavel, para o teclado alcancar. */
    expect(tela.find('.card__os').element.tagName).toBe('BUTTON')
  })

  it('o dragstart dispara de verdade no card', async () => {
    const tela = await abrir(quadro({
      cards: { s38: [card({ numero_ordem: 17099 })] }, podeMover: true,
    }))
    const dados = { effectAllowed: '', setData: () => {} }
    await tela.find('.card').trigger('dragstart', { dataTransfer: dados })
    /* ⚠️ `move` e nao `copy`: o cursor tem de dizer que isto MOVE. */
    expect(dados.effectAllowed).toBe('move')
  })

  it('soltar na coluna move para a situacao dela', async () => {
    const tela = await abrir(quadro({
      cards: { s38: [card({ numero_ordem: 17099, situacao_id: 38 })] },
      podeMover: true,
    }))
    await tela.find('.card').trigger('dragstart',
                                     { dataTransfer: { setData: () => {} } })
    /* A terceira coluna das 17 é a 251 "Configurar equipamentos e Sistemas". */
    await tela.findAll('.coluna')[2].trigger('drop')
    await flushPromises()
    expect(estado.postado[0]).toEqual([
      '/api/paineis/operacao/mover',
      { numero_os: 17099, para_situacao: 251, situacao_esperada: 38 },
    ])
  })

  it('soltar na PROPRIA coluna nao escreve nada', async () => {
    /* ⚠️ Gravar a OS inteira por nada é risco sem ganho. */
    const tela = await abrir(quadro({
      cards: { s38: [card({ numero_ordem: 17099, situacao_id: 38 })] },
      podeMover: true,
    }))
    await tela.find('.card').trigger('dragstart',
                                     { dataTransfer: { setData: () => {} } })
    await tela.findAll('.coluna')[0].trigger('drop')
    await flushPromises()
    expect(estado.postado).toEqual([])
  })
})

/* ============================================================================
   A FALHA DE ABERTURA DE OS — Bloco A (29/10)
   ----------------------------------------------------------------------------
   🚨 "SEM OS" DEIXOU DE SER ESPERA E PASSOU A SER FALHA. Até 29/10 a OS nascia
   por botão, e não ter sido clicado explicava tudo. Com a D4 dele ("todo
   chamado de suporte abrirá uma OS", automático no envio) ficar sem OS é
   defeito -- e defeito que a tela não diz é `M12`.

   ⚠️ E a conta NÃO é a mesma que `sem_os`: um chamado de 4 placas pode ter 1 OS
   aberta e 3 falhas, e aí ele TEM coluna e TEM falha. São duas perguntas
   diferentes, e por isso duas frases.
   ============================================================================ */
describe('a falha de abertura de OS', () => {
  it('nao escreve nada quando nenhuma falhou', async () => {
    const tela = await abrir(quadro())
    expect(tela.text()).not.toContain('não abriu')
    expect(tela.text()).not.toContain('não abriram')
  })

  it('diz quantas OS nao abriram e em quantos chamados', async () => {
    const tela = await abrir(quadro({
      fora: {
        sem_os: 0, situacao_fora: 0, situacoes: [],
        os_falhou: 3, os_falhou_chamados: 2,
        os_falhou_em: '2026-10-29T15:40:00-03:00',
      },
    }))
    const aviso = tela.find('.aviso--fora')
    expect(aviso.text()).toContain('3 OS não abriram')
    expect(aviso.text()).toContain('2 chamados')
    expect(aviso.text()).toContain('última tentativa')
  })

  it('fala no singular quando e uma so', async () => {
    const tela = await abrir(quadro({
      fora: {
        sem_os: 0, situacao_fora: 0, situacoes: [],
        os_falhou: 1, os_falhou_chamados: 1, os_falhou_em: null,
      },
    }))
    const aviso = tela.find('.aviso--fora')
    expect(aviso.text()).toContain('1 OS não abriu')
    expect(aviso.text()).toContain('1 chamado')
    /* ⚠️ Sem hora, a tela não inventa uma. */
    expect(aviso.text()).not.toContain('última tentativa')
  })

  it('convive com as outras contas, sem engolir nenhuma', async () => {
    /* ⚠️ Aqui os 2 sem OS JÁ ESTÃO EXPLICADOS pelos 3 chamados com falha, e
       por isso não ganham frase própria -- repeti-los seria contar o mesmo
       chamado duas vezes na mesma linha. */
    const tela = await abrir(quadro({
      fora: {
        sem_os: 2, situacao_fora: 1, situacoes: [99999],
        os_falhou: 4, os_falhou_chamados: 3, os_falhou_em: null,
        sem_tentativa: 0,
      },
    }))
    const texto = tela.find('.aviso--fora').text()
    expect(texto).toContain('4 OS não abriram')
    expect(texto).toContain('1 com situação fora das 17')
    expect(texto).toContain('99999')
    expect(texto).not.toContain('sem motivo registrado')
  })

  it('a SOBRA ganha frase propria, em vez de desaparecer', async () => {
    /* 🚨 O BURACO QUE ESTA FRASE TAPA: uma linha de `solicitacao_os` preparada
       e nunca tentada (`os_id` nulo E `erro` nulo) não cai em "nunca se
       tentou" nem em "falhou". Sem esta sobra, aquele chamado desapareceria
       entre as duas frases -- o mesmo defeito que ele achou, mais fundo. */
    const tela = await abrir(quadro({
      fora: {
        sem_os: 5, situacao_fora: 0, situacoes: [],
        os_falhou: 1, os_falhou_chamados: 1, os_falhou_em: null,
        sem_tentativa: 2,
      },
    }))
    const texto = tela.find('.aviso--fora').text()
    /* 5 sem OS - (2 nunca tentados + 1 com falha) = 2 sem explicação. */
    expect(texto).toContain('2 sem OS e sem motivo registrado')
    expect(texto).toContain('2 chamados ainda sem OS')
    expect(texto).toContain('1 OS não abriu')
  })
})

/* ============================================================================
   "NUNCA SE TENTOU" NÃO É "FALHOU" — o defeito que ele achou na tela (29/10)
   ----------------------------------------------------------------------------
   🚨 Ele leu na tela, minutos depois de o painel subir: *"1 sem OS (a escrita
   no Harmonit falhou)"*. **Nada havia falhado** -- a solicitação era de antes
   de a abertura automática existir, e nunca teve escrita tentada.

   ⚠️ A frase era VERDADEIRA quando foi escrita, e isso é o `M12`: em 22/10 a
   OS nascia por botão e "sem OS" só podia ser espera; em 29/10 a abertura
   virou automática e a frase passou a acusar o Harmonit de um erro que não
   houve.
   ============================================================================ */
describe('sem OS: aguardando nao e falha', () => {
  const vazio = { sem_os: 0, situacao_fora: 0, situacoes: [], os_falhou: 0,
                  os_falhou_chamados: 0, os_falhou_em: null, sem_tentativa: 0 }

  it('nao acusa o Harmonit quando ninguem tentou escrever', async () => {
    const tela = await abrir(quadro({
      fora: { ...vazio, sem_os: 1, sem_tentativa: 1 },
    }))
    const aviso = tela.find('.aviso--fora')
    /* 🚨 A frase do defeito NÃO pode voltar. */
    expect(aviso.text()).not.toContain('falhou')
    expect(aviso.text()).toContain('1 chamado ainda sem OS')
    expect(aviso.text()).toContain('antes de a abertura automática entrar')
    /* 🚨 E NEM A CARA DE ATENCAO: nada falhou, entao a linha e NOTA. Foi o
       triangulo que fez ele perguntar *"pq deu erro?"*. */
    expect(aviso.classes()).toContain('aviso--nota')
    expect(aviso.classes()).not.toContain('aviso--atencao')
  })

  it('diz falha quando a escrita falhou de verdade', async () => {
    const tela = await abrir(quadro({
      fora: { ...vazio, os_falhou: 2, os_falhou_chamados: 1 },
    }))
    const aviso = tela.find('.aviso--atencao')
    expect(aviso.text()).toContain('2 OS não abriram')
    expect(aviso.text()).not.toContain('antes de a abertura')
  })

  it('separa os dois quando existem ao mesmo tempo', async () => {
    const tela = await abrir(quadro({
      fora: { ...vazio, sem_os: 1, sem_tentativa: 1,
              os_falhou: 3, os_falhou_chamados: 2 },
    }))
    const texto = tela.find('.aviso--atencao').text()
    expect(texto).toContain('1 chamado ainda sem OS')
    expect(texto).toContain('3 OS não abriram')
  })

  it('com zero nos dois, nao escreve nada', async () => {
    const tela = await abrir(quadro({ fora: { ...vazio } }))
    expect(tela.find('.aviso--atencao').exists()).toBe(false)
  })
})

/* ============================================================================
   BLOCO B — a ponte caída, a data matriz e o interruptor (29/10)
   ----------------------------------------------------------------------------
   🚨 QUADRO PEQUENO SEM EXPLICAÇÃO É O DEFEITO AQUI: sem o FPSL o painel mostra
   só os chamados que já têm OS registrada do nosso lado -- 2 cards em vez de
   10, medido em 29/10. Quem abrisse a tela concluiria que não há trabalho.
   ============================================================================ */
describe('a ponte do FPSL', () => {
  it('caida, a tela DIZ que esta vendo menos', async () => {
    const dados = quadro()
    dados.ponte_respondeu = false
    dados.ponte_motivo = 'o FPSL nao respondeu no tempo'
    const tela = await abrir(dados)
    const aviso = tela.find('.aviso--erro')
    expect(aviso.exists()).toBe(true)
    expect(aviso.text()).toContain('FPSL não respondeu')
    expect(aviso.text()).toContain('já têm OS registrada')
  })

  it('de pe, nao escreve nada sobre ela', async () => {
    const dados = quadro()
    dados.ponte_respondeu = true
    const tela = await abrir(dados)
    expect(tela.find('.aviso--erro').exists()).toBe(false)
  })
})

describe('a data matriz e o interruptor', () => {
  it('a tela diz desde quando monta', async () => {
    /* 🚨 "O painel está vazio" e "o painel começa em 24/10" são respostas
       diferentes para a mesma tela vazia. */
    const dados = quadro()
    dados.desde = '2026-10-24'
    const tela = await abrir(dados)
    expect(tela.text()).toContain('desde 24/10/2026')
  })

  it('o interruptor das finalizadas nasce LIGADO', async () => {
    const tela = await abrir(quadro())
    const caixa = tela.find('.painel__interruptor input')
    expect(caixa.exists()).toBe(true)
    expect(caixa.element.checked).toBe(true)
  })
})

/* ============================================================================
   OS EFEITOS DO MOCKUP (29/10) — e a regra que eles não podem romper
   ----------------------------------------------------------------------------
   🔵 Pedido dele: *"depois não esqueça de subir tbm com os efeitos, pois o
   mockup ficou muito bom"*.

   🚨 A TRAVA QUE IMPORTA É A PRIMEIRA: a cor do catavento é **código de
   etapa**, e cor nunca é o único portador nesta casa. O nome da etapa e o
   número da situação continuam escritos — quem não distingue as cores perde a
   decoração, nunca a informação.

   ⚠️ E a segunda: a OS vem na frente do card. Desde a D8 a maioria dos cards
   NÃO tem formulário (10 de 10 medidos em 29/10 vêm do ERP), e antes disso o
   card começava com um campo vazio.
   ============================================================================ */
describe('os efeitos do mockup', () => {
  const comCard = () => quadro({
    cards: {
      s38: [card({
        numero_ordem: 17099, origem: 'erp', formulario: null, slug: null,
        cliente: 'TRANSFORMADORES MINUZZI LTDA', cliente_id: 54406,
        tipo_nome: 'Upgrade', situacao_id: 38, estado: null,
        placas: [{ placa: 'ABC1D23' }], finalizada: false,
        visto_em: '2026-10-29T18:00:00Z',
      })],
    },
  })

  it('🚨 a cor NAO e o unico portador: o nome da etapa e a situacao vem escritos',
     async () => {
    const tela = await abrir(comCard())
    const texto = tela.text()
    /* O nome da etapa, na coluna. */
    expect(texto).toContain('Novo Solicitação 1ª')
    /* E o número da situação, no card. */
    expect(texto).toContain('situação 38')
  })

  it('a OS vem na frente do card, nao o formulario', async () => {
    const tela = await abrir(comCard())
    const card0 = tela.find('.card__os')
    expect(card0.exists()).toBe(true)
    expect(card0.text()).toBe('OS 17099')
  })

  it('cliente fora do nosso cadastro e DITO, nao deixado em branco', async () => {
    const dados = quadro({
      cards: { s38: [card({ numero_ordem: 17098, origem: 'erp',
                            cliente: null, cliente_id: 999999 })] },
    })
    const tela = await abrir(dados)
    expect(tela.text()).toContain('fora do nosso cadastro')
    expect(tela.text()).toContain('999999')
  })

  it('a OS finalizada ganha AVISO, nao so uma cor', async () => {
    /* 🚨 Ela só aparece com o interruptor desligado, e sem a marca ficaria
       indistinguível de uma OS viva na mesma coluna. */
    const dados = quadro({
      cards: { s38: [card({ numero_ordem: 17097, origem: 'erp',
                            finalizada: true })] },
    })
    const tela = await abrir(dados)
    expect(tela.find('.card__alerta').text()).toBe('finalizada')
  })

  it('diz quando leu o dado do Harmonit', async () => {
    /* ⚠️ A varredura roda a cada 5 min; a tela não pode deixar supor que o
       dado é de agora. */
    const tela = await abrir(comCard())
    expect(tela.find('.card__visto').exists()).toBe(true)
    expect(tela.find('.card__visto').text()).toContain('lido do Harmonit')
  })

  it('o contador fica CHEIO com card e vazado sem', async () => {
    const tela = await abrir(comCard())
    const contas = tela.findAll('.coluna__conta')
    /* A primeira coluna (38) tem 1 card; as outras 16 estão em zero. */
    expect(contas[0].classes()).not.toContain('coluna__conta--zero')
    expect(contas[1].classes()).toContain('coluna__conta--zero')
  })

  it('a placa da OS aparece quando existe', async () => {
    const tela = await abrir(comCard())
    expect(tela.text()).toContain('ABC1D23')
  })
})


/* ============================================================================
   OS QUATRO TEMAS DO CARD ABERTO — Bloco E (29/10)
   ----------------------------------------------------------------------------
   🔵 Ele: *"onde estão os temas do card, após clicar?"* — e eu os havia deixado
   para depois, com um texto no modal dizendo que faltavam. Dizer o que falta é
   melhor que caixa vazia, e **não substitui o recurso**.

   🚨 `descricao` e `solucaoTecnica` NÃO estão no cache: vêm ao vivo do ERP, uma
   chamada POR CARD ABERTO. Na montagem do quadro seriam 11.
   ============================================================================ */
describe('os quatro temas do card aberto', () => {
  const comFicha = (extra = {}) => {
    estado.ficha = {
      numero_os: 17099, descricao: 'MANUTENCAO COM TROCA: UQD 7I19',
      solucao_tecnica: null, tipo_nome: 'Solicitação de Cliente',
      prioridade: 382, situacao_id: 38, tem_agendamento: false,
      agendamentos: [], chamado: null, ...extra,
    }
    return quadro({ cards: { s38: [card({ numero_ordem: 17099 })] } })
  }

  it('os QUATRO temas aparecem', async () => {
    const tela = await abrir(comFicha())
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    const abas = tela.findAll('.temas__aba').map((a) => a.text())
    expect(abas).toHaveLength(4)
    expect(abas.join(' ')).toContain('Descrição da OS')
    expect(abas.join(' ')).toContain('Solução técnica')
    expect(abas.join(' ')).toContain('Dados do chamado')
    expect(abas.join(' ')).toContain('Agendamento')
  })

  it('a descricao vem da OS lida ao vivo', async () => {
    const tela = await abrir(comFicha())
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    expect(tela.find('.temas__texto').text()).toContain('MANUTENCAO COM TROCA')
  })

  it('🚨 VAZIO e DITO, nao deixado em branco', async () => {
    /* ⚠️ A solução técnica é nula na maioria das OS, e caixa branca parece
       defeito. */
    const tela = await abrir(comFicha())
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    const solucao = tela.findAll('.temas__aba')[1]
    expect(solucao.text()).toContain('sem solução técnica escrita')
  })

  it('🔵 o Agendamento nasce APAGADO e diz por que', async () => {
    /* 🔵 Desenho dele: *"nasce desabilitado e acende em Serviço Agendado"*. */
    const tela = await abrir(comFicha())
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    const ag = tela.findAll('.temas__aba')[3]
    expect(ag.classes()).toContain('temas__aba--apagada')
    expect(ag.attributes('disabled')).toBeDefined()
    expect(ag.text()).toContain('só a partir de "Serviço Agendado"')
  })

  it('o Agendamento ACENDE quando a OS tem compromisso', async () => {
    const tela = await abrir(comFicha({
      tem_agendamento: true,
      agendamentos: [{ usuario_id: 7493, nome: 'Franck', agendamento_id: 930447 }],
    }))
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    const ag = tela.findAll('.temas__aba')[3]
    expect(ag.classes()).not.toContain('temas__aba--apagada')
    expect(ag.text()).toContain('1 compromisso')
  })

  it('os dados do chamado saem com ROTULO, nunca a chave do Bitrix', async () => {
    /* 🚨 A tela do painel não pode mostrar `COMPANY_UF_CRM_1646332310941`. */
    const tela = await abrir(comFicha({
      chamado: {
        solicitacao_id: 544, formulario: 'Suporte', anexos: 0,
        respostas: [{ nome: 'COMPANY_UF_CRM_1646332310941',
                      rotulo: 'CNPJ', valor: 'WQ0P6GLD000108' }],
      },
    }))
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    await tela.findAll('.temas__aba')[2].trigger('click')
    const corpo = tela.find('.temas__respostas').text()
    expect(corpo).toContain('CNPJ')
    expect(corpo).not.toContain('COMPANY_UF_CRM')
  })

  it('🚨 falha ao ler a OS vira ERRO, nao ficha vazia', async () => {
    /* 🚨 Ficha vazia é indistinguível de OS sem dados, e o operador concluiria
       que não há o que ver. */
    estado.fichaFalha = true
    const tela = await abrir(quadro({
      cards: { s38: [card({ numero_ordem: 17099 })] },
    }))
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    const alerta = tela.findAll('[role="alert"]').map((p) => p.text()).join(' ')
    /* ⚠️ INSENSIVEL A CAIXA: a frase comeca com maiuscula na tela e
       minuscula na mensagem do servidor, e comparar com caixa fixa e o
       defeito que a memoria desta casa chama de
       varredura-de-rotulo-ignora-caixa. */
    expect(alerta.toLowerCase()).toContain('deu para ler a os')
  })
})


/* ============================================================================
   O CARD ABERTO: AS QUATRO FAIXAS DO MOCKUP — 🔵 *"está feio ainda tbm"*
   ----------------------------------------------------------------------------
   🚨 O QUE ESTAVA FEIO ERA ESTRUTURA, não cor: eu havia empilhado seis seções
   soltas com o mesmo peso visual, e sem hierarquia tudo grita junto. O mockup
   tem quatro faixas, e a hierarquia vem delas:
     1. o topo branco (quem é esta OS)
     2. UMA faixa com fundo: etapa, os dois tempos, e as duas ações de estado
     3. o corpo branco (os temas e o que se escreve)
     4. o pé com fundo (os botões)

   ⚠️ As travas olham a ESTRUTURA, não os pixels: quem redesenhar de novo pode
   mudar cor e espaço, mas não pode voltar a empilhar tudo com o mesmo peso.
   ============================================================================ */
describe('o card aberto tem as quatro faixas', () => {
  const abrirOCard = async () => {
    estado.ficha = {
      numero_os: 17099, descricao: 'x', solucao_tecnica: null,
      prioridade: 382, prioridades: { 381: 'Baixa', 382: 'Normal',
                                      383: 'Alta', 384: 'Urgente' },
      tem_agendamento: false, agendamentos: [], chamado: null,
      observacoes: [],
    }
    const tela = await abrir(quadro({
      cards: { s38: [card({ numero_ordem: 17099, situacao_id: 38 })] },
      podeMover: true,
    }))
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    return tela
  }

  it('as quatro faixas existem', async () => {
    const tela = await abrirOCard()
    for (const classe of ['.modal__topo', '.modal__faixa', '.modal__corpo',
                          '.modal__rodape']) {
      expect(tela.find(classe).exists(), classe).toBe(true)
    }
  })

  it('a faixa traz os DOIS TEMPOS e a etapa', async () => {
    const tela = await abrirOCard()
    const faixa = tela.find('.modal__faixa').text()
    expect(faixa).toContain('Etapa agora')
    expect(faixa).toContain('Novo Solicitação 1ª')
    expect(faixa).toContain('Nesta etapa')
    expect(faixa).toContain('Total da OS')
  })

  it('sem passagem, a faixa diz nao medido e nao um zero', async () => {
    /* 🚨 A `os_passagem` começou em 29/10, e a OS pode estar na etapa desde
       setembro. "0h" seria afirmar o que ninguém mediu. */
    const tela = await abrirOCard()
    expect(tela.find('.modal__faixa').text()).toContain('não medido')
  })

  it('as duas acoes de estado vivem na FAIXA, nao soltas', async () => {
    const tela = await abrirOCard()
    const campos = tela.findAll('.faixa__campo').map((c) => c.text())
    expect(campos.join(' ')).toContain('Mover para')
    expect(campos.join(' ')).toContain('Prioridade')
  })

  it('a observacao DIZ que nao vai para a OS', async () => {
    /* ⚠️ Sem essa frase, alguém escreve ali pensando que o técnico vai ler. */
    const tela = await abrirOCard()
    const recados = tela.find('.modal__recados').text()
    expect(recados).toContain('Não vai para a OS')
    expect(recados).toContain('não se apaga')
  })

  it('o pe diz que mover escreve no Harmonit', async () => {
    const tela = await abrirOCard()
    expect(tela.find('.modal__rodape').text())
      .toContain('escreve a situação na OS do Harmonit')
  })
})

/* ============================================================================
   O FILTRO E A ORDEM NA TELA — 🔵 *"filtros para os cards, por cliente, OS,
   placa // ordenadores tbm"*
   ============================================================================ */
describe('o filtro e a ordem', () => {
  it('a caixa de busca e o seletor de ordem existem', async () => {
    const tela = await abrir(quadro())
    expect(tela.find('.painel__busca input').exists()).toBe(true)
    expect(tela.findAll('.painel__ordem option')).toHaveLength(5)
  })

  it('a tela DIZ que esta filtrada, e por onde casou', async () => {
    /* 🚨 Quadro filtrado que não diz que está filtrado é `M12`: alguém abre o
       painel, vê 1 card e conclui que a operação está vazia. */
    const dados = quadro({ cards: { s38: [card()] } })
    dados.busca = 'MINUZZI'
    dados.filtro_casou_por = ['cliente']
    const tela = await abrir(dados)
    const texto = tela.text()
    expect(texto).toContain('MINUZZI')
    expect(texto).toContain('casou por cliente')
  })

  it('busca sem resultado DIZ que nenhum card casou', async () => {
    const dados = quadro()
    dados.busca = 'zzz'
    dados.filtro_casou_por = null
    const tela = await abrir(dados)
    expect(tela.text()).toContain('nenhum card casou')
  })

  it('tem como limpar o filtro', async () => {
    const dados = quadro()
    dados.busca = 'zzz'
    const tela = await abrir(dados)
    expect(tela.find('.painel__limpar').exists()).toBe(true)
  })
})

/* ============================================================================
   OS DOIS TEMPOS NO CARD FECHADO — Bloco C
   ============================================================================ */
describe('os dois tempos no card fechado', () => {
  it('diz nao medido quando nao houve passagem', async () => {
    const tela = await abrir(quadro({
      cards: { s38: [card({ numero_ordem: 17099, etapa_desde: null })] },
    }))
    expect(tela.find('.card__tempos').text()).toContain('não medido')
  })

  it('mostra o tempo da etapa quando houve passagem', async () => {
    const ontem = new Date(Date.now() - 36 * 3600 * 1000).toISOString()
    const tela = await abrir(quadro({
      cards: { s38: [card({ numero_ordem: 17099, etapa_desde: ontem })] },
    }))
    expect(tela.find('.card__tempos').text()).toContain('1d')
  })

  it('a prioridade diferente de Normal fica MARCADA', async () => {
    /* ⚠️ *"mudar é exceção, e exceção precisa estar visível sem abrir"*.
       🚨 E não só por cor -- o nome está escrito. */
    const tela = await abrir(quadro({
      cards: { s38: [card({ numero_ordem: 17099, prioridade: 383,
                            prioridade_nome: 'Alta' })] },
    }))
    const pil = tela.findAll('.pilula').find((p) => p.text() === 'Alta')
    expect(pil).toBeTruthy()
    expect(pil.classes()).toContain('pilula--forte')
  })

  it('prioridade NAO LIDA nao aparece, em vez de fingir Normal', async () => {
    const tela = await abrir(quadro({
      cards: { s38: [card({ numero_ordem: 17099, prioridade: null,
                            prioridade_nome: null })] },
    }))
    expect(tela.find('.card').text()).not.toContain('Normal')
  })
})


/* ============================================================================
   O ARRASTO, TERCEIRA VOLTA — 🔵 *"arrastar card ainda não funciona tbm -- ja
   esta cansativo tratar disso"*
   ----------------------------------------------------------------------------
   🚨 TRÊS CAUSAS DIFERENTES, e eu consertei uma por volta:
     1. o conteúdo era um `<button>` — elemento interativo engole o `mousedown`;
     2. faltava `user-select: none` — arrastar sobre texto selecionável inicia
        uma SELEÇÃO DE TEXTO, não o arrasto;
     3. **o `@click` competia com o arrasto** — todo arrasto começa curto, e o
        navegador entrega o início como clique: o card abria no meio do gesto,
        cobria a tela, e o arrasto morria.

   ⚠️ NENHUMA DAS TRÊS UM TESTE MEU PODIA PEGAR SOZINHO: `trigger('dragstart')`
   e `trigger('click')` são eventos separados e sintéticos, e a competição entre
   os dois só existe no navegador. O que estas travas guardam é o MECANISMO do
   conserto — a guarda de tempo e o alvo aceso —, e quem julga o gesto continua
   sendo o navegador dele.
   ============================================================================ */
describe('o arrasto nao compete mais com o clique', () => {
  const comCard = () => quadro({
    cards: { s38: [card({ numero_ordem: 17099, situacao_id: 38 })] },
    podeMover: true,
  })

  it('🚨 clique DEPOIS de arrastar NAO abre o card', async () => {
    /* 🚨 Era A causa da terceira volta: o card abria no meio do gesto. */
    const tela = await abrir(comCard())
    await tela.find('.card').trigger('dragstart',
                                     { dataTransfer: { setData: () => {} } })
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    expect(tela.find('.modal').exists()).toBe(false)
  })

  it('clique SEM arrasto continua abrindo o card', async () => {
    /* ⚠️ A guarda não pode engolir o clique de quem só quer abrir. */
    const tela = await abrir(comCard())
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    expect(tela.find('.modal').exists()).toBe(true)
  })

  it('🚨 a coluna ACENDE quando o card passa por cima', async () => {
    /* 🚨 Sem retorno visual não há como saber se o alvo aceita o solto -- e era
       justamente a informação que faltava para dizer ONDE o gesto quebrava. */
    const tela = await abrir(comCard())
    await tela.find('.card').trigger('dragstart',
                                     { dataTransfer: { setData: () => {} } })
    const terceira = tela.findAll('.coluna')[2]
    await terceira.trigger('dragenter')
    expect(terceira.classes()).toContain('coluna--alvo')
  })

  it('a coluna APAGA quando o card sai dela', async () => {
    const tela = await abrir(comCard())
    await tela.find('.card').trigger('dragstart',
                                     { dataTransfer: { setData: () => {} } })
    const terceira = tela.findAll('.coluna')[2]
    await terceira.trigger('dragenter')
    await terceira.trigger('dragleave')
    expect(terceira.classes()).not.toContain('coluna--alvo')
  })

  it('⚠️ sem arrasto em curso, passar por cima NAO acende nada', async () => {
    /* Senão a coluna acenderia com o mouse passeando. */
    const tela = await abrir(comCard())
    const terceira = tela.findAll('.coluna')[2]
    await terceira.trigger('dragenter')
    expect(terceira.classes()).not.toContain('coluna--alvo')
  })

  it('soltar ainda escreve, com a trava de concorrencia', async () => {
    const tela = await abrir(comCard())
    await tela.find('.card').trigger('dragstart',
                                     { dataTransfer: { setData: () => {} } })
    await tela.findAll('.coluna')[2].trigger('drop')
    await flushPromises()
    expect(estado.postado[0]).toEqual([
      '/api/paineis/operacao/mover',
      { numero_os: 17099, para_situacao: 251, situacao_esperada: 38 },
    ])
  })

  it('🔵 o ordenador nasce no PRAZO DE ENTREGA', async () => {
    /* 🔵 Decisão dele: *"o ordenador padrão deve ser por 'Prazo de entrega'"*. */
    const tela = await abrir(quadro())
    const sel = tela.find('.painel__ordem select')
    expect(sel.element.value).toBe('prazo')
    expect(sel.findAll('option')[0].text()).toContain('prazo de entrega')
  })
})
