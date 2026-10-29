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

   🚨 O QUE NÃO MUDOU, e por isso continua testado aqui: **não há `draggable`**
   (mover de verdade escreve no Harmonit, e a rota não existe), coluna vazia
   nasce colapsada com o contador à vista, a cor nunca é o único portador, e o
   card leva para a ficha na `FRM_1.1`.

   🚨 E O QUE ENTROU NO LUGAR DOS TEXTOS: a linha de `fora_do_quadro`. Card sem
   OS, ou com situação fora das 17, não tem coluna -- e sumir da tela em
   silêncio é `M12`. A linha só aparece quando há o que dizer.
   ============================================================================ */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = { quadro: null, empurrado: [] }

vi.mock('../src/api/cliente.js', () => ({}))
vi.mock('./api/cliente.js', () => ({
  api: { get: async () => estado.quadro },
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
  ...extra,
})

async function abrir(dados) {
  estado.quadro = dados
  const tela = mount(PainelOperacao)
  await flushPromises()
  return tela
}

beforeEach(() => {
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

describe('mover o card', () => {
  it('🚨 não existe gesto de arrastar enquanto a escrita no Harmonit não existe', async () => {
    const tela = await abrir(quadro({ cards: { s38: [card()] } }))
    expect(tela.html()).not.toContain('draggable')
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
    const aviso = tela.find('.aviso--atencao')
    expect(aviso.text()).toContain('3 sem OS')
    expect(aviso.text()).not.toContain('Harmonit')
    expect(aviso.text()).toContain('Solicitações')
  })

  it('situação fora das 17 aparece com o NÚMERO CRU', async () => {
    const tela = await abrir(quadro({
      fora: { sem_os: 0, situacao_fora: 2, situacoes: [0, 99999] },
    }))
    const aviso = tela.find('.aviso--atencao')
    expect(aviso.text()).toContain('2 com situação fora das 17')
    // ⚠️ O número cru, nunca um rótulo inventado.
    expect(aviso.text()).toContain('0, 99999')
  })
})

describe('o card', () => {
  it('leva a solicitação e a OS lado a lado', async () => {
    const tela = await abrir(quadro({ cards: { s38: [card()] } }))
    const texto = tela.find('.card__abrir').text()
    expect(texto).toContain('Suporte')
    expect(texto).toContain('Cliente de exemplo')
    expect(texto).toContain('OS 17042')
    expect(texto).toContain('situação 38')
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

  it('clicar manda para a ficha na FRM_1.1', async () => {
    const tela = await abrir(quadro({ cards: { s38: [card({ id: 42 })] } }))
    await tela.find('.card__abrir').trigger('click')
    expect(estado.empurrado).toEqual([
      { path: '/solicitacoes', query: { solicitacao: 42 } },
    ])
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
    const aviso = tela.find('.aviso--atencao')
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
    const aviso = tela.find('.aviso--atencao')
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
    const texto = tela.find('.aviso--atencao').text()
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
    const texto = tela.find('.aviso--atencao').text()
    /* 5 sem OS - (2 nunca tentados + 1 com falha) = 2 sem explicação. */
    expect(texto).toContain('2 sem OS e sem motivo registrado')
    expect(texto).toContain('2 chamados sem OS, de antes')
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
    const aviso = tela.find('.aviso--atencao')
    /* 🚨 A frase do defeito NÃO pode voltar. */
    expect(aviso.text()).not.toContain('falhou')
    expect(aviso.text()).toContain('1 chamado sem OS')
    expect(aviso.text()).toContain('antes de a abertura ser automática')
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
    expect(texto).toContain('1 chamado sem OS')
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
