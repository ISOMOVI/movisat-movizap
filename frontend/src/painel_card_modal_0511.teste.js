/*
 * @vitest-environment jsdom
 *
 * O CARD (variante C) E O MODAL (proposta A) — 05/11.
 *
 * 🔵 Ele, olhando os mockups: *"vamos de C"* · *"vamos de A"* · *"aumentar em
 * +2 e realinhar"* · *"dar uma elaborada para evidenciar as limitações das
 * caixas, talvez espessura ou sombreamento"* · *"e dai siga ambos"*.
 *
 * 🚨 ESTES TESTES PRENDEM OS SEIS DEFEITOS MEDIDOS, não a estética. Cada um
 * nasceu de uma medição na própria tela em 05/11:
 *
 *   D1  três seções do modal eram filhas DIRETAS da `.modal__caixa`, que tem
 *       `padding: 0`, e nenhuma definia o seu — o miolo colava na borda;
 *   D2  o teto de rolagem estava na única seção de tamanho previsível;
 *   D3  duas rolagens empilhadas (o palco e o corpo);
 *   D4  o card escrevia *"prazo"* num campo que o comentário logo acima dele
 *       proibia chamar de prazo, e o modal já escrevia *"previsão"*;
 *   D5  `aria-modal="true"` sem `Escape`, sem foco entrando e sem foco voltando;
 *   D6  as frases de REGRA do modal em `.apagado` (#94A3B8 = 2,56:1).
 *
 * E as duas repetições que saíram do card: o NOME DA SITUAÇÃO (que é o título
 * da coluna em que o card já está) e *"Harmonit"* (que aparecia em quase todo
 * card, porque a origem ERP é a maioria).
 *
 * ⚠️ Arquivo próprio: o `painel_2210.teste.js` tem 78 travas de outras regras e
 * o `painel_checklist_0411.teste.js` tem 27 — enfiar isto neles seria arriscar
 * o que já está provado.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = { quadro: null, checklist: [], ficha: null, postado: [] }

vi.mock('../src/api/cliente.js', () => ({}))
vi.mock('./api/cliente.js', () => ({
  api: {
    get: async (caminho) => {
      const c = String(caminho)
      if (c.includes('/checklist')) return { itens: estado.checklist }
      if (c.includes('/passagens')) {
        return {
          passagens: [
            { id: 1, em: '2026-11-04T09:00:00-03:00', de_situacao: 38,
              para_situacao: 251, quem: 'Iago', ok: true },
          ],
        }
      }
      if (c.includes('/ficha')) return estado.ficha
      return estado.quadro
    },
    post: async (caminho, corpo) => {
      estado.postado.push([String(caminho), corpo])
      return { ok: true }
    },
    put: async () => ({ itens: estado.checklist }),
    del: async () => ({ itens: estado.checklist }),
  },
  ErroDeApi: class extends Error {},
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: () => {} }),
  useRoute: () => ({ query: {} }),
}))

import PainelOperacao from './telas/PainelOperacao.vue'

const AS_DEZESSETE = [
  [38, 'Novo Solicitação 1ª'], [16487, 'Pendente de ação da Movisat'],
  [251, 'Configurar equipamentos e Sistemas'], [16488, 'Entrega de materiais prontos'],
  [677, 'Enviar por correio/transportadora'],
  [15747, 'Aguardando recebimento via correio/transportadora'],
  [15797, 'Rescisão Aguardando Aviso Prévio'], [890, 'Agendar serviço'],
  [16489, 'Confirmação agendamento'], [1316, 'Serviço Agendado'],
  [15696, 'Aguardando devolução de equipamento'],
  [16490, 'Analise de Equipamentos Retornados'], [15694, 'Atendimento finalizado'],
  [16491, 'Não atendido'], [15746, 'Financeiro'], [15695, 'Pós venda'],
  [16492, 'Contratual'],
]

/* Agora, 2h e 9 dias atrás — para os tempos serem de verdade. */
const AGORA = Date.now()
const ha = (horas) => new Date(AGORA - horas * 3600 * 1000).toISOString()

function card(extra = {}) {
  return {
    id: null, origem: 'erp', numero_ordem: 17081, os_id: 870036,
    situacao_id: 251, cliente: 'Pastelaria Velasco',
    criada_em: ha(26), tipo_nome: 'Retirada',
    placas: [{ placa: 'BUS0168', veiculo: 'BENZ L 1516' }], tecnicos: [],
    observacoes: 1, anexos: 0, estado: null, formulario: null,
    prioridade: 382, prioridade_nome: 'Normal', status_str: 'Nova',
    finalizada: false, termo: '8937', etapa_desde: ha(2),
    checklist: null, tem_checklist: false, visto_em: ha(0.1),
    ...extra,
  }
}

function quadro(cards = {}) {
  return {
    painel: 'operacao', titulo: 'Operação', total: 1, pode_mover: true,
    desde: '2026-10-24', so_abertas: true, busca: '', ordem: 'prazo',
    ordens: [], ponte_respondeu: true, ponte_motivo: null,
    fora_do_quadro: null, filtro_casou_por: null,
    colunas: AS_DEZESSETE.map(([sid, titulo]) => ({
      chave: `s${sid}`, titulo, situacao_id: sid, nota: null,
      total: (cards[sid] || []).length, cards: cards[sid] || [],
    })),
  }
}

async function montar(cards = { 251: [card()] }) {
  estado.quadro = quadro(cards)
  const tela = mount(PainelOperacao, {
    attachTo: document.body,
    global: { stubs: { AjudaDaTela: true } },
  })
  await flushPromises()
  return tela
}

async function abrirOCard(tela) {
  await tela.find('.card__os').trigger('click')
  await flushPromises()
  await flushPromises()
  return tela
}

beforeEach(() => {
  estado.checklist = []
  estado.postado = []
  estado.ficha = {
    observacoes: [], prioridades: { 381: 'Baixa', 382: 'Normal', 383: 'Alta', 384: 'Urgente' },
    prioridade: 382,
    descricao: 'Retirada: BUS 0168 | TERMO 8937 | O.S: 17081',
    solucao_tecnica: null, chamado: null, tem_agendamento: false,
    agendamentos: [],
  }
  document.body.innerHTML = ''
})

/* ==========================================================================
   O CARD FECHADO — variante C
   ========================================================================== */
describe('o card, variante C', () => {
  it('🔵 o CLIENTE é a primeira linha, e a OS vem depois', async () => {
    const tela = await montar()
    const texto = tela.find('.card__abrir').text()
    expect(texto.indexOf('Pastelaria Velasco'))
      .toBeLessThan(texto.indexOf('OS 17081'))
  })

  it('🚨 não repete o nome da situação, que é o título da coluna', async () => {
    const tela = await montar()
    expect(tela.find('.card__abrir').text())
      .not.toContain('Configurar equipamentos e Sistemas')
    /* ⚠️ Mas a coluna continua dizendo — a informação não sumiu, saiu da
       repetição. */
    expect(tela.text()).toContain('Configurar equipamentos e Sistemas')
  })

  it('🚨 não mostra o SELO "Harmonit", que aparecia em quase todo card', async () => {
    const tela = await montar()
    const selos = tela.findAll('.pilula').map((p) => p.text())
    expect(selos).not.toContain('Harmonit')
    /* ⚠️ A PALAVRA continua na tela, e de proposito: a linha *"lido do
       Harmonit há 5 min"* diz QUANDO o dado foi lido do ERP, e isso e o que
       impede alguem de supor que o card e de agora. O que saiu foi o selo de
       ORIGEM, que nao distinguia nada. */
    expect(tela.find('.card__visto').text()).toContain('lido do Harmonit')
  })

  it('o card de FORMULÁRIO mostra o nome do formulário', async () => {
    /* ⚠️ É o que distingue de verdade: a origem ERP é a maioria. */
    const tela = await montar({
      251: [card({ origem: 'formulario', formulario: 'Suporte' })],
    })
    expect(tela.find('.pilula--origem').text()).toBe('Suporte')
  })

  it('🚨 D4: escreve "previsão", nunca "prazo"', async () => {
    /* O comentário do próprio código dizia, com a medição, que chamar de prazo
       seria a tela afirmando o que o ERP não diz — e a linha escrevia `prazo`.
       O modal já usava "Previsão de entrega". */
    const tela = await montar()
    const texto = tela.find('.card__abrir').text()
    expect(texto).toContain('previsão')
    expect(texto).not.toContain('prazo')
  })

  it('🔵 a prioridade NORMAL não aparece; a Alta aparece e marca o card', async () => {
    const normal = await montar()
    expect(normal.find('.card__abrir').text()).not.toContain('Normal')
    expect(normal.find('.card__abrir').classes()).not.toContain('card__abrir--excecao')

    const alta = await montar({
      251: [card({ prioridade: 383, prioridade_nome: 'Alta' })],
    })
    expect(alta.find('.pilula--alerta').text()).toBe('Alta')
    expect(alta.find('.card__abrir').classes()).toContain('card__abrir--excecao')
  })

  it('🚨 prioridade NULA não é exceção — nulo é "a varredura não releu"', async () => {
    const tela = await montar({
      251: [card({ prioridade: null, prioridade_nome: null })],
    })
    expect(tela.find('.card__abrir').classes()).not.toContain('card__abrir--excecao')
  })

  it('🔵 parado além do limite marca o card e o tempo da etapa', async () => {
    const tela = await montar({ 251: [card({ etapa_desde: ha(24 * 6) })] })
    expect(tela.find('.card__abrir').classes()).toContain('card__abrir--excecao')
    expect(tela.find('.card__etapa').classes()).toContain('card__etapa--parado')
  })

  it('🚨 "não medido" NUNCA acende alerta', async () => {
    /* ⚠️ `etapa_desde` nulo quer dizer que a `os_passagem` não viu esta OS
       passar — e afirmar atraso sobre o que ninguém mediu é pior que não
       dizer nada. */
    const tela = await montar({ 251: [card({ etapa_desde: null })] })
    expect(tela.find('.card__etapa').text()).toContain('não medido')
    expect(tela.find('.card__etapa').classes()).not.toContain('card__etapa--parado')
    expect(tela.find('.card__abrir').classes()).not.toContain('card__abrir--excecao')
  })

  it('o checklist completo fica verde; incompleto, âmbar', async () => {
    const cheio = await montar({
      251: [card({ checklist: { feitos: 4, total: 4 } })],
    })
    expect(cheio.find('.pilula--pronto').text()).toBe('4 de 4')

    const falta = await montar({
      251: [card({ checklist: { feitos: 1, total: 4 } })],
    })
    expect(falta.find('.pilula--alerta').text()).toBe('1 de 4')
  })

  it('🚨 o nome comprido do cliente vai INTEIRO no title', async () => {
    /* Medido em 05/11: 11 dos 15 nomes do quadro passam de 24 caracteres, o
       maior tem 56. O card corta em 2 linhas por CSS; o dado não se perde. */
    const nome = 'TGS RIO ALUGUEL DE CACAMBAS E RECICLAGEM DE ENTULHO LTDA'
    const tela = await montar({ 251: [card({ cliente: nome })] })
    expect(tela.find('.card__cliente').attributes('title')).toBe(nome)
  })

  it('⚠️ cliente fora do cadastro continua DITO, não em branco', async () => {
    const tela = await montar({
      251: [card({ cliente: null, cliente_id: 70412 })],
    })
    expect(tela.find('.card__cliente--sem').text())
      .toContain('cliente 70412, fora do nosso cadastro')
  })

  it('a OS continua sendo o BOTÃO, e o termo não é clicável', async () => {
    const tela = await montar()
    expect(tela.find('.card__os').element.tagName).toBe('BUTTON')
    expect(tela.find('.card__termo').element.tagName).not.toBe('BUTTON')
  })
})

/* ==========================================================================
   O MODAL — proposta A
   ========================================================================== */
describe('o modal, proposta A', () => {
  it('🚨 D1: as quatro seções estão DENTRO do corpo, não soltas na caixa', async () => {
    /* O defeito: checklist, observações e passagens eram filhas diretas da
       `.modal__caixa` (que tem `padding: 0`) e nenhuma definia o seu padding.
       Só os temas estavam no corpo. */
    const tela = await abrirOCard(await montar({
      251: [card({ tem_checklist: true })],
    }))
    estado.checklist = [{ id: 1, texto: 'zz', feito: false, avulso: false }]

    const caixa = tela.findAll('.modal__caixa').pop().element
    const filhos = [...caixa.children].map((f) => f.className)
    /* Exatamente quatro faixas: topo, faixa, corpo, pé. */
    expect(filhos).toHaveLength(4)
    expect(filhos[0]).toContain('modal__topo')
    expect(filhos[1]).toContain('modal__faixa')
    expect(filhos[2]).toContain('modal__corpo')
    expect(filhos[3]).toContain('modal__rodape')

    const corpo = caixa.querySelector('.modal__corpo')
    expect(corpo.querySelector('.modal__log')).toBeTruthy()
    expect(corpo.querySelector('.modal__temas')).toBeTruthy()
    /* 🚨 E nenhuma delas é filha direta da caixa. */
    expect([...caixa.children].some((f) => f.classList.contains('modal__log')))
      .toBe(false)
  })

  it('🔵 duas colunas: o que se FAZ à esquerda, o que se LÊ à direita', async () => {
    const tela = await abrirOCard(await montar())
    const caixa = tela.findAll('.modal__caixa').pop().element
    const fazer = caixa.querySelector('.modal__coluna--fazer')
    const ler = caixa.querySelector('.modal__coluna--ler')
    expect(fazer).toBeTruthy()
    expect(ler).toBeTruthy()
    expect(ler.querySelector('.modal__temas')).toBeTruthy()
    expect(ler.querySelector('.modal__log')).toBeTruthy()
  })

  it('🚨 R1: os dois controles que ESCREVEM no ERP estão no pé, não na faixa', async () => {
    const tela = await abrirOCard(await montar())
    const caixa = tela.findAll('.modal__caixa').pop().element
    expect(caixa.querySelector('.modal__faixa select')).toBeNull()
    expect(caixa.querySelectorAll('.modal__rodape select').length).toBe(2)
  })

  it('🚨 os dois controles de escrita ficam no MESMO bloco, no pé', async () => {
    /* ⚠️ ESTA TRAVA FOI REESCRITA EM 05/11, e nao removida. Ela prendia duas
       coisas: a POSICAO dos dois controles juntos no pe (a regra de separar ler
       de agir, que e o que a entrega de 05/11 fez) e a FRASE ao lado deles, que
       ele mandou tirar. A frase saiu; a posicao continua sendo o ponto.
       🚨 E o motivo da posicao sobrevive a frase: os dois controles que
       escrevem no ERP ficam fora da faixa de medidas, que e so leitura. */
    const tela = await abrirOCard(await montar())
    const caixa = tela.findAll('.painel__dialogo').pop().element
    const agir = caixa.querySelector('.modal__agir')
    expect(agir).toBeTruthy()
    expect(agir.querySelectorAll('select').length).toBe(2)
    /* e a faixa de medidas continua sem nenhum */
    expect(caixa.querySelector('.modal__faixa select')).toBeNull()
  })

  it('⚠️ a faixa troca "Previsão de entrega" por "Aberta"', async () => {
    /* Ela gastava um slot de medida para dizer, numa nota, que a medida não
       valia ("hoje igual à abertura"). */
    const tela = await abrirOCard(await montar())
    const faixa = tela.findAll('.modal__caixa').pop().element
      .querySelector('.modal__faixa').textContent
    expect(faixa).toContain('Aberta')
    expect(faixa).not.toContain('Previsão de entrega')
    expect(faixa).not.toContain('hoje igual à abertura')
  })

  it('🚨 D6: nenhuma frase do modal usa a classe que falha contraste', async () => {
    const tela = await abrirOCard(await montar({
      251: [card({ tem_checklist: true })],
    }))
    const caixa = tela.findAll('.modal__caixa').pop().element
    expect(caixa.querySelectorAll('.apagado').length).toBe(0)
    /* E a classe que entrou no lugar está lá. */
    expect(caixa.querySelectorAll('.nota').length).toBeGreaterThan(0)
  })

  it('o cliente é o título do modal, e vem INTEIRO', async () => {
    const nome = 'TGS RIO ALUGUEL DE CACAMBAS E RECICLAGEM DE ENTULHO LTDA'
    const tela = await abrirOCard(await montar({ 251: [card({ cliente: nome })] }))
    expect(tela.find('.modal__cliente').text()).toBe(nome)
  })

})

/* ==========================================================================
   D5 — O TECLADO, que o `aria-modal` já prometia
   ========================================================================== */
describe('o teclado no modal (D5)', () => {
  function teclar(key) {
    window.dispatchEvent(new KeyboardEvent('keydown', { key }))
  }

  it('🚨 Escape fecha o card aberto', async () => {
    const tela = await abrirOCard(await montar())
    expect(tela.findAll('.modal__caixa').length).toBeGreaterThan(0)
    teclar('Escape')
    await flushPromises()
    expect(tela.find('.modal__caixa').exists()).toBe(false)
  })

  it('⚠️ outra tecla não fecha nada', async () => {
    const tela = await abrirOCard(await montar())
    teclar('a')
    await flushPromises()
    expect(tela.find('.modal__caixa').exists()).toBe(true)
  })

  it('🚨 Escape fecha o modal DE CIMA primeiro, não o de baixo', async () => {
    /* Os recados abrem de dentro do card aberto. Fechar o card por baixo
       deixaria o de cima órfão. */
    const tela = await abrirOCard(await montar())
    await tela.findAll('button').find((b) => b.text().includes('Abrir'))
      .trigger('click')
    await flushPromises()
    expect(tela.findAll('.modal__caixa').length).toBe(2)

    teclar('Escape')
    await flushPromises()
    /* o card continua aberto; só os recados fecharam */
    expect(tela.findAll('.modal__caixa').length).toBe(1)

    teclar('Escape')
    await flushPromises()
    expect(tela.find('.modal__caixa').exists()).toBe(false)
  })

  it('o foco volta para o botão da OS ao fechar', async () => {
    const tela = await montar()
    const botao = tela.find('.card__os').element
    botao.focus()
    await tela.find('.card__os').trigger('click')
    await flushPromises()
    await flushPromises()
    teclar('Escape')
    await flushPromises()
    /* ⚠️ `requestAnimationFrame` no jsdom não roda sozinho dentro do
       `flushPromises`: o que se mede aqui é que o alvo guardado é o botão, e
       que ele continua no DOM para receber o foco. */
    expect(document.body.contains(botao)).toBe(true)
  })
})

/* ==========================================================================
   A SEGUNDA VOLTA DE 05/11 — a coluna larga e o card em três faixas
   --------------------------------------------------------------------------
   🔵 Ele: *"o layout dos cards com a fonte maior não ficou bom, pode deixar um
   pouco mais retangular horizontal do que vertical, vendo 3 colunas por scroll
   esta ok"* · *"em algumas abas, como operação, existe uma margem entre o grid
   dos cards e o menu, isso é perca de espaço"*.
   ========================================================================== */
describe('o card em três faixas (segunda volta)', () => {
  it('🔵 são QUATRO faixas, e eram cinco', async () => {
    /* ⚠️ PAREI EM QUATRO, E NAO EM TRES, e a conta e a razao: com 334px de
       largura util, *"nesta etapa 3h · total 3h"* ja ocupa ~170px e os selos
       mais a previsão pedem ~160px. Juntos transbordam, e card que transborda
       é pior que card com uma faixa a mais. O que encostou foi o tipo e a placa,
       que subiram para a linha da OS. */
    const tela = await montar()
    const faixas = tela.findAll('.card__linha')
    expect(faixas).toHaveLength(4)
    expect(faixas[0].text()).toContain('Pastelaria Velasco')
    expect(faixas[1].text()).toContain('OS 17081')
    expect(faixas[2].text()).toContain('nesta etapa')
    expect(faixas[3].text()).toContain('previsão')
  })

  it('o tipo e a placa vão para a borda direita, junto da OS', async () => {
    const tela = await montar()
    const faixa = tela.findAll('.card__linha')[1]
    expect(faixa.find('.card__os').exists()).toBe(true)
    expect(faixa.find('.card__direita--dado').text()).toContain('Retirada')
    expect(faixa.find('.card__direita--dado').text()).toContain('BUS0168')
  })

  it('os dois tempos ficam na MESMA faixa', async () => {
    const tela = await montar()
    const texto = tela.find('.card__etapa').text()
    expect(texto).toContain('nesta etapa')
    expect(texto).toContain('total')
  })

  it('⚠️ "não medido" continua sem acender alerta na faixa nova', async () => {
    const tela = await montar({ 251: [card({ etapa_desde: null })] })
    expect(tela.find('.card__etapa').text()).toContain('não medido')
    expect(tela.find('.card__etapa').classes()).not.toContain('card__etapa--parado')
  })

  it('o card sem tipo e sem placa não deixa a faixa vazia', async () => {
    /* ⚠️ A OS aberta à mão pode não ter nenhum dos dois: a borda direita
       simplesmente não existe, em vez de abrir um espaço em branco. */
    const tela = await montar({
      251: [card({ tipo_nome: null, placas: [] })],
    })
    const faixa = tela.findAll('.card__linha')[1]
    expect(faixa.find('.card__os').exists()).toBe(true)
    expect(faixa.find('.card__direita--dado').exists()).toBe(false)
  })

  it('🚨 a previsão continua escrita, e nunca como "prazo"', async () => {
    /* A terceira faixa mudou de conteúdo; a regra do D4 não mudou. */
    const tela = await montar()
    const texto = tela.find('.card__abrir').text()
    expect(texto).toContain('previsão')
    expect(texto).not.toContain('prazo')
  })
})

/* ==========================================================================
   O PAINEL DO MODAL — as três faixas, e a ORDEM da cascata
   --------------------------------------------------------------------------
   🔵 Ele, olhando a tela: *"o layout do card apos o clique esta errado"*.
   🚨 A CAUSA: eu escrevi as regras do `.modal__painel` ANTES das regras antigas
   de `.modal__recados`/`.modal__log`/`.modal__temas`. Mesma especificidade, e a
   que vem depois ganha — então o cabeçalho do painel caía para `--txt-sm` e o
   `gap` voltava a `--e-2`, e o painel ficava uma caixa de padding único em vez
   das três faixas do mockup.
   ⚠️ **jsdom não aplica `<style scoped>`**, então nenhum teste aqui mede cor ou
   tamanho computado — é o limite conhecido desta suíte. O que se mede é a
   ESTRUTURA que as faixas precisam para existir.
   ========================================================================== */
/* 🚨 TRES TRAVAS DESTE BLOCO SAIRAM EM 05/11, e nao por estarem erradas: ele
   tirou a faixa de baixo do painel (*"nao precisam mante-los no card"*), e elas
   prendiam a POSICAO e a classe daquela frase. Sem a faixa, nao tinham assunto.
   ⚠️ A regra que a frase dizia continua no codigo -- o checklist vira observacao
   ao mover, e nada chega ao Harmonit. O que se perdeu foi a prova de que a TELA
   dizia isso. Estao no git, no commit anterior. */
describe('as três faixas do painel do modal', () => {
  it('🔵 o checklist e as observações são painéis', async () => {
    estado.checklist = [{ id: 1, texto: 'zz', feito: false, avulso: false }]
    const tela = await abrirOCard(await montar({
      251: [card({ tem_checklist: true })],
    }))
    const paineis = tela.findAll('.modal__painel')
    /* checklist, observações, temas e passagens */
    expect(paineis.length).toBe(4)
  })

  it('🚨 o h3 é FILHO DIRETO do painel — é ele que vira a faixa de cima', async () => {
    /* O seletor é `.modal__painel > h3`. Se o markup envolver o título num
       `<div>`, a faixa deixa de pintar e ninguém percebe. */
    estado.checklist = [{ id: 1, texto: 'zz', feito: false, avulso: false }]
    const tela = await abrirOCard(await montar({
      251: [card({ tem_checklist: true })],
    }))
    const painel = tela.findAll('.modal__painel')[0].element
    const h3 = painel.querySelector('h3')
    expect(h3).toBeTruthy()
    expect(h3.parentElement).toBe(painel)
  })



})
