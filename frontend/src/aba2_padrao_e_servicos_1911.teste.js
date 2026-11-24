/**
 * @vitest-environment jsdom
 *
 * ===========================================================================
 * A ABA 2 DO FINANCEIRO NO PADRÃO DA ABA 1 — 19/11
 * ===========================================================================
 * 🔵 Dele: *"faltam várias coisas e melhorias de UX/UI principalmente em
 * relação a funcionalidade e estilos dos cards -- como a aba1 apresenta --
 * foque na aba 2 e finalize a entrega e serviços dela"* · *"regras de
 * ordenamento tbm da etapa de op faltam aqui"*.
 *
 * 🚨 ESTES TESTES OLHAM A TELA, não o JSON. Foi assim que o card cru de 18/11
 * passou despercebido por meses: o servidor mandava mais de 20 campos e a tela
 * desenhava 6, e nenhuma suíte reclamou porque o defeito era de OMISSÃO.
 *
 * As travas aqui guardam cinco coisas que a tela não tinha em 18/11:
 *   1. a TIRA DE ABAS (sem ela a PNL_1.6 é um beco: não está no menu);
 *   2. os DADOS DA OS no artefato (cliente, tipo, data do serviço);
 *   3. os ORDENADORES, que são os da Operação;
 *   4. o FILTRO e a MARCAÇÃO por CARD -- os dois vazavam entre técnicos;
 *   5. os TRÊS SERVIÇOS que o servidor tinha e ninguém alcançava
 *      (comprovante, DataScope e prévia).
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = vi.hoisted(() => ({
  quadro: null, os: null, posts: [], gets: [], previa: null,
}))

vi.mock('./api/cliente.js', () => {
  class ErroDeApi extends Error {}
  return {
    api: {
      get: (caminho) => {
        estado.gets.push(caminho)
        if (caminho.includes('/os/')) return Promise.resolve(estado.os)
        if (caminho.includes('/previa/')) return Promise.resolve(estado.previa)
        return Promise.resolve(estado.quadro)
      },
      post: (caminho, corpo) => {
        estado.posts.push({ caminho, corpo })
        return Promise.resolve({ ok: true, preparados: (corpo?.artefatos || []).length,
                                 semaforo: 'verde' })
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
  sessao: {
    nome: 'Iago', owner: true,
    telas: [
      { codigo: 'PNL_1.4', rota: '/paineis/financeiro' },
      { codigo: 'PNL_1.6', rota: '/paineis/servico-dos-tecnicos' },
    ],
  },
  codigosPermitidos: { value: new Set() },
  sair: () => {},
}))

vi.mock('./componentes/BarraDeRolagem.vue', () => ({
  default: { name: 'BarraDeRolagem', template: '<div />' },
}))
vi.mock('./componentes/RolagemDaBorda.vue', () => ({
  default: { name: 'RolagemDaBorda', template: '<div />' },
}))

import PainelServicoDosTecnicos from './telas/PainelServicoDosTecnicos.vue'

/* 📏 Dois técnicos e um card sem técnico, com os dados de OS que o servidor
   passou a mandar em 19/11. ⚠️ O artefato 3 NÃO tem nome de cliente: são os 14
   de 79 medidos, e a tela tem de DIZER isso. */
function quadro() {
  return {
    artefatos: 5,
    abas: [
      { codigo_tela: 'PNL_1.4', titulo: 'Financeiro' },
      { codigo_tela: 'PNL_1.6', titulo: 'Serviço dos técnicos' },
    ],
    colunas: [
      {
        chave: 'movimentacao', total: 3,
        cards: [
          {
            tecnico_id: 14262, tecnico_nome: 'Franck', pode_preparar: true,
            artefatos: [
              { id: 1, numero_os: 16689, termo: '8937', orcamento_numero: null,
                valor_pagamento: 80, valor_km: 12.5, data_os: '05/08/2026 08:00:00',
                cliente: 'SWM - COMERCIO E LOCACAO DE IMOVEIS LTDA',
                cliente_id: 249119, tipo_nome: 'Contrato', status_str: 'Iniciada' },
              { id: 2, numero_os: 17120, termo: null, orcamento_numero: 3,
                valor_pagamento: 175, valor_km: 0, data_os: '17/11/2026 09:00:00',
                cliente: 'ZIP FIRE SOLUCOES CONTRA INCENDIO LTDA',
                cliente_id: 262537, tipo_nome: 'Substituição/Instalação',
                status_str: 'Finalizado' },
            ],
          },
          {
            tecnico_id: 14999, tecnico_nome: 'Pedro Felipe', pode_preparar: true,
            artefatos: [
              { id: 3, numero_os: 16705, termo: null, orcamento_numero: null,
                valor_pagamento: 60, valor_km: 0, data_os: '10/09/2026 08:00:00',
                cliente: null, cliente_id: 1015624, tipo_nome: 'Contrato',
                status_str: 'Iniciada' },
            ],
          },
          {
            tecnico_id: null, tecnico_nome: 'sem técnico identificado',
            pode_preparar: false,
            artefatos: [
              { id: 4, numero_os: 16851, termo: null, orcamento_numero: null,
                valor_pagamento: 120, valor_km: 0, data_os: '11/10/2026 08:00:00',
                cliente: 'JG VIDROS E ESQUADRIAS LTDA', cliente_id: 30839,
                tipo_nome: 'Substituição/Instalação', status_str: 'Iniciada' },
            ],
          },
        ],
      },
      { chave: 'preparacao', total: 0, cards: [] },
      {
        chave: 'validacao', total: 1,
        cards: [
          {
            lote_id: 9, coluna: 'validacao', tecnico_id: 14262,
            tecnico_nome: 'Franck',
            artefatos: [
              { id: 5, numero_os: 16866, termo: null, orcamento_numero: 3,
                valor_pagamento: 90, valor_km: 10, data_os: '12/11/2026 08:00:00',
                cliente: 'REMOVERDE SERVICOS LTDA', cliente_id: 287121,
                tipo_nome: 'Instalação rastreador', status_str: 'Finalizado',
                semaforo: 'amarelo', comprovante_arquivo: null,
                comprovante_dispensa: null, valor_do_comprovante: null },
            ],
          },
        ],
      },
      { chave: 'procfy', total: 0, cards: [] },
      { chave: 'enviado', total: 0, cards: [] },
    ],
  }
}

async function montar() {
  const tela = mount(PainelServicoDosTecnicos, {
    attachTo: document.body,
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })
  await flushPromises()
  return tela
}

/* ===========================================================================
 * 🚨 O GESTO MUDOU EM 23/11 (tarefa 2.2), A REGRA NÃO
 * ===========================================================================
 * 🔵 Dele, 23/11: *"o card fechado só com resumo, dados e botões só no card
 * aberto"*. O filtro de data, a lista de artefatos, as caixas de marcação e os
 * botões de ação saíram do card fechado e foram para o diálogo do card aberto
 * — o padrão que a aba 1 e a Operação já seguiam desde 05/11.
 *
 * 🚨 **NENHUMA TRAVA DESTE ARQUIVO FOI AFROUXADA.** Cada uma cobra exatamente
 * o que cobrava em 19/11; o que ganharam foi UM clique antes, que é o gesto de
 * quem usa a tela. Afrouxar o que a trava mede para ela ficar verde seria o
 * contrário do que ela existe para fazer.
 *
 * ⚠️ **DUAS MUDARAM DE FORMA, não só de gesto**: as que provavam que o filtro
 * e a marcação são POR CARD olhando o card do Franck e o do Pedro LADO A LADO.
 * Com um diálogo por vez isso é impossível, e o isolamento agora se prova
 * abrindo um, medindo, fechando e abrindo o outro. O que elas guardam — que o
 * estado de um card não vaza para o outro — é o mesmo, e era o defeito de
 * 18/11.
 */
const DIALOGO = '.modal[aria-label^="Card de"]'

async function abrir(tela, nome) {
  const fechado = tela.findAll('article.card')
    .find((a) => a.text().includes(nome))
  expect(fechado, `o card de ${nome} tem de estar no quadro`).toBeTruthy()
  await fechado.find('button.card__abrir').trigger('click')
  await flushPromises()
  const d = tela.find(DIALOGO)
  expect(d.exists(), `o diálogo de ${nome} tem de abrir`).toBe(true)
  return d
}

async function fecharODialogo(tela) {
  await tela.find(DIALOGO).findAll('button')
    .find((b) => b.text().trim() === 'Fechar').trigger('click')
  await flushPromises()
  expect(tela.find(DIALOGO).exists(), 'o diálogo tem de fechar').toBe(false)
}

/* O card do Franck na MOVIMENTAÇÃO, e não o lote dele na Validação: os dois
   dizem "Franck", e o primeiro do quadro é o da coluna 1. */
async function abrirOFranck(tela) { return abrir(tela, 'Franck') }
async function abrirOLote(tela) { return abrir(tela, 'lote 9') }

beforeEach(() => {
  estado.quadro = quadro()
  estado.os = {
    numero_os: 16689,
    descricao: 'RESSARCIMENTO: placas: RVF 5G49 | 007933929 (Suntech ST310)',
    solucao_tecnica: null, chamado: null, tem_agendamento: false,
    agendamentos: [],
  }
  estado.previa = {
    ok: true, tecnico: 'Franck', artefatos: 1, total: 100,
    linhas: [{ 'Descrição': 'OS 16866 | Franck', 'Data de competência': '12/11/2026',
               Valor: '100,00', 'Observações': 'Orcamento 3' }],
    em_branco: ['procfy_categoria'],
    aviso: 'estas colunas saem em branco e precisam ser preenchidas na '
      + 'planilha antes de importar: Categoria',
  }
  estado.posts = []
  estado.gets = []
})

// ===========================================================================
// 1. A TIRA DE ABAS — sem ela a PNL_1.6 é um beco
// ===========================================================================
describe('a tira de abas', () => {
  it('desenha as duas abas do Financeiro e marca a atual', async () => {
    const tela = await montar()
    const abas = tela.findAll('.abas__item')
    expect(abas).toHaveLength(2)
    expect(abas.map((a) => a.text())).toEqual(['Financeiro', 'Serviço dos técnicos'])
    expect(abas[1].classes()).toContain('abas__item--atual')
  })

  it('o título é o do PAINEL, e não o da aba repetido', async () => {
    const tela = await montar()
    expect(tela.find('.painel__titulo').text()).toBe('Financeiro')
  })

  it('aba que a pessoa não alcança cai fora sem segunda régua', async () => {
    /* ⚠️ A permissão chega de graça pelo `sessao.telas`: a aba 1 sai da lista
       do servidor e não casa com nenhuma tela da sessão. */
    estado.quadro.abas = [{ codigo_tela: 'PNL_9.9', titulo: 'Inventada' },
                          { codigo_tela: 'PNL_1.6', titulo: 'Serviço dos técnicos' }]
    const tela = await montar()
    expect(tela.text()).not.toContain('Inventada')
  })
})

// ===========================================================================
// 2. OS DADOS DA OS NO ARTEFATO — *"como a aba1 apresenta"*
// ===========================================================================
describe('os dados da OS no artefato', () => {
  it('mostra cliente, tipo da OS e a data do serviço', async () => {
    const tela = await montar()
    await abrirOFranck(tela)
    const texto = tela.text()
    expect(texto).toContain('SWM - COMERCIO E LOCACAO DE IMOVEIS LTDA')
    expect(texto).toContain('Contrato')
    expect(texto).toContain('05/08/26')
    expect(texto).toContain('Iniciada')
  })

  it('cliente sem nome é DITO, não deixado em branco', async () => {
    /* ⚠️ O artefato sem nome de cliente é o do PEDRO, não o do Franck. */
    const tela = await montar()
    await abrir(tela, 'Pedro Felipe')
    expect(tela.text()).toContain('cliente 1015624, fora do nosso cadastro')
  })

  it('a ordem do artefato é Orçamento — OS — TERMO, a dele', async () => {
    const tela = await montar()
    await abrirOFranck(tela)
    const primeiro = tela.findAll('.artefato')[0].text().replace(/\s+/g, ' ')
    expect(primeiro).toMatch(/sem orçamento.*OS 16689.*TERMO 8937/)
  })
})

// ===========================================================================
// 3. OS ORDENADORES — *"regras de ordenamento tbm da etapa de op"*
// ===========================================================================
describe('a ordem', () => {
  it('nasce com o serviço mais antigo primeiro', async () => {
    const tela = await montar()
    await abrirOFranck(tela)
    const oss = tela.findAll('.artefato__os').map((b) => b.text())
    expect(oss.slice(0, 2)).toEqual(['OS 16689', 'OS 17120'])
  })

  it('trocar para "OS, da mais nova" muda o que está na tela', async () => {
    const tela = await montar()
    await abrirOFranck(tela)
    /* ⚠️ O seletor de ordem fica nos CONTROLES do painel, fora do diálogo —
       ele ordena os artefatos de todos os cards, e continua alcançável com o
       card aberto. */
    await tela.findAll('select')[0].setValue('os_desc')
    const oss = tela.findAll('.artefato__os').map((b) => b.text())
    expect(oss.slice(0, 2)).toEqual(['OS 17120', 'OS 16689'])
  })

  it('a busca diz ONDE casou, que é o que separa OS de termo', async () => {
    const tela = await montar()
    await abrirOFranck(tela)
    await tela.find('.controles__busca input').setValue('8937')
    const texto = tela.text()
    expect(texto).toContain('casou por termo')
    expect(texto).not.toContain('OS 17120')
  })

  it('card que ficou sem artefato some da busca, e a coluna diz por quê',
     async () => {
    const tela = await montar()
    await tela.find('.controles__busca input').setValue('zzzzz')
    expect(tela.text()).toContain('Nenhum card casa com a busca.')
  })
})

// ===========================================================================
// 4. O FILTRO E A MARCAÇÃO SÃO POR CARD — os dois vazavam em 18/11
// ===========================================================================
describe('o filtro e a marcação, por card', () => {
  it('filtrar o período do Franck não mexe no card do Pedro', async () => {
    /* 🚨 **MUDOU DE FORMA EM 23/11, e o que ela guarda é o mesmo.** Antes os
       dois cards estavam abertos lado a lado e bastava um `tela.text()`. Com
       um diálogo por vez, o isolamento se prova abrindo um, medindo, fechando
       e abrindo o outro — e é justamente essa ida e volta que pegaria o
       vazamento de 18/11, quando o filtro era um só para a tela inteira. */
    const tela = await montar()
    const franck = await abrirOFranck(tela)
    const datas = franck.findAll('input[type="date"]')
    /* ⚠️ `setValue` dispara `input`; o campo escuta `change` desde 19/11
       (ver o defeito do ano parcial abaixo), então o gesto precisa dos dois. */
    await datas[0].setValue('2026-11-01')
    await datas[0].trigger('change')
    /* A OS de agosto do Franck sai, a de 17/11 fica. */
    expect(franck.text()).not.toContain('OS 16689')
    expect(franck.text()).toContain('OS 17120')

    await fecharODialogo(tela)
    const pedro = await abrir(tela, 'Pedro Felipe')
    /* 🚨 A de setembro do PEDRO fica, porque o filtro não é dele -- e os
       campos de data DELE continuam vazios. */
    expect(pedro.text()).toContain('OS 16705')
    const dpedro = pedro.findAll('input[type="date"]')
    expect(dpedro[0].element.value, 'o filtro do Pedro não foi tocado').toBe('')
    expect(dpedro[1].element.value).toBe('')
  })

  it('marcar no card do Franck não conta no botão do Pedro', async () => {
    /* 🚨 **MUDOU DE FORMA EM 23/11**, pelo mesmo motivo da trava acima: antes
       os dois botões "Preparar os marcados" estavam na tela ao mesmo tempo e a
       trava comparava os dois contadores. Agora há um por diálogo, e a prova é
       a mesma ida e volta. */
    const tela = await montar()
    const franck = await abrirOFranck(tela)
    await franck.findAll('.artefato__marca input[type="checkbox"]')[0]
      .setValue(true)
    expect(franck.findAll('button').map((b) => b.text())
      .find((x) => x.startsWith('Preparar os marcados')))
      .toBe('Preparar os marcados (1)')

    await fecharODialogo(tela)
    const pedro = await abrir(tela, 'Pedro Felipe')
    expect(pedro.findAll('button').map((b) => b.text())
      .find((x) => x.startsWith('Preparar os marcados')))
      .toBe('Preparar os marcados (0)')

    /* ⚠️ E voltar ao Franck tem de ACHAR a marcação ainda lá: fechar o
       diálogo não é desmarcar. */
    await fecharODialogo(tela)
    const devolta = await abrirOFranck(tela)
    expect(devolta.findAll('button').map((b) => b.text())
      .find((x) => x.startsWith('Preparar os marcados')))
      .toBe('Preparar os marcados (1)')
  })

  it('prepara só os artefatos daquele card', async () => {
    const tela = await montar()
    const franck = await abrirOFranck(tela)
    await franck.findAll('.artefato__marca input[type="checkbox"]')[0]
      .setValue(true)
    const botao = franck.findAll('button')
      .find((b) => b.text().startsWith('Preparar os marcados'))
    await botao.trigger('click')
    await flushPromises()
    const pedido = estado.posts.find((p) => p.caminho.endsWith('/preparar'))
    expect(pedido.corpo.artefatos).toEqual([1])
  })

  it('o card sem técnico não prepara e DIZ por quê', async () => {
    const tela = await montar()
    /* 🚨 A VERSÃO CURTA FICA NO CARD FECHADO, de propósito: o dinheiro parado
       tem de ter explicação à vista, e esconder o motivo atrás de um clique
       deixaria o valor sem razão aparente na coluna. */
    const fechado = tela.findAll('article.card')
      .find((a) => a.text().includes('sem técnico identificado'))
    expect(fechado, 'o card dos sem técnico tem de estar no quadro').toBeTruthy()
    expect(fechado.text()).toContain('não há a quem pagar')

    /* E a frase INTEIRA, com o que fazer a respeito, fica no card aberto. */
    const aberto = await abrir(tela, 'sem técnico identificado')
    expect(aberto.text()).toContain('Não há a quem pagar até alguém')
    expect(aberto.text()).toContain('vincular o técnico na OS')
    /* 🚨 E não há botão de preparar: não há a quem pagar. */
    expect(aberto.text()).not.toContain('Preparar os marcados')
  })
})

// ===========================================================================
// 5. OS TRÊS SERVIÇOS QUE O SERVIDOR TINHA E NINGUÉM ALCANÇAVA
// ===========================================================================
describe('os serviços que a tela não chamava', () => {
  it('a OS abre pelo ARTEFATO, nunca pela rota da Operação', async () => {
    const tela = await montar()
    await abrirOFranck(tela)
    await tela.findAll('.artefato__os')[0].trigger('click')
    await flushPromises()
    expect(estado.gets).toContain('/api/paineis/servico-dos-tecnicos/os/1')
    expect(estado.gets.join(' ')).not.toContain('/api/paineis/operacao/ficha')
    const texto = tela.text()
    expect(texto).toContain('OS 16689 no Harmonit')
    expect(texto).toContain('Descrição da OS')
    expect(texto).toContain('Solução técnica')
    expect(texto).toContain('Dados do chamado')
    expect(texto).toContain('Agendamento')
    expect(texto).toContain('RESSARCIMENTO')
    /* ⚠️ VAZIO É DITO: a solução técnica é nula na maioria das OS. */
    expect(texto).toContain('sem solução técnica escrita')
  })

  it('o comprovante existe na Validação e manda arquivo e valor', async () => {
    const tela = await montar()
    /* ⚠️ O comprovante vive no card do LOTE, na Validação. */
    await abrirOLote(tela)
    const botao = tela.findAll('button').find((b) => b.text() === 'Comprovante')
    expect(botao).toBeTruthy()
    await botao.trigger('click')
    const campos = tela.findAll('.modal__caixa--curta input')
    await campos[0].setValue('recibo_franck_1811.pdf')
    /* 🔵 *"Após o envio do anexo, abre o campo que pede o valor"*: o campo do
       valor só aparece depois do arquivo. */
    const depois = tela.findAll('.modal__caixa--curta input')
    expect(depois.length).toBe(3)
    await depois[1].setValue('100')
    await tela.findAll('.modal__acoes button')
      .find((b) => b.text() === 'Salvar').trigger('click')
    await flushPromises()
    const pedido = estado.posts.find((p) => p.caminho.endsWith('/comprovante'))
    expect(pedido.corpo.artefato_id).toBe(5)
    expect(pedido.corpo.arquivo).toBe('recibo_franck_1811.pdf')
    expect(pedido.corpo.valor).toBe(100)
  })

  it('sem comprovante e sem justificativa, Salvar fica travado', async () => {
    const tela = await montar()
    await abrirOLote(tela)
    await tela.findAll('button').find((b) => b.text() === 'Comprovante')
      .trigger('click')
    const salvar = tela.findAll('.modal__acoes button')
      .find((b) => b.text() === 'Salvar')
    expect(salvar.attributes('disabled')).toBeDefined()
  })

  it('a prévia diz quais colunas do Procfy saem em branco', async () => {
    const tela = await montar()
    await abrirOLote(tela)
    await tela.findAll('button').find((b) => b.text() === 'Ver prévia')
      .trigger('click')
    await flushPromises()
    const texto = tela.text()
    expect(texto).toContain('O que vai para o Procfy')
    expect(texto).toContain('saem em branco')
    expect(texto).toContain('Categoria')
    expect(texto).toContain('OS 16866 | Franck')
    /* ⚠️ Ver a prévia NÃO move card. */
    expect(estado.posts.some((p) => p.caminho.includes('montar-arquivo')))
      .toBe(false)
  })

  it('o DataScope é lido por gesto, e só lido', async () => {
    const tela = await montar()
    await abrirOLote(tela)
    await tela.findAll('button').find((b) => b.text() === 'Ler DataScope')
      .trigger('click')
    await flushPromises()
    expect(estado.posts.some((p) => p.caminho.endsWith('/datascope/5')))
      .toBe(true)
    /* 🚨 Nada de `change_state`: a correção lá escreve em sistema de terceiro
       e é decisão dele. */
    expect(estado.posts.some((p) => p.caminho.includes('change'))).toBe(false)
  })
})

/* ===========================================================================
 * 🚨 O FILTRO DE DATA QUE FAZIA OS CARDS SUMIREM — achado por ELE usando a
 * tela, em 19/11, DEPOIS de eu publicar
 * ===========================================================================
 * 🔵 Dele: *"ao usa o filtro de data na aba2 os cards somem - precisa fazer um
 * audit decente dessa aba"*.
 *
 * 📏 A causa não era a comparação de datas, era o CAMPO: `<input type="date">`
 * dispara `input` a cada dígito do ano, então digitar 2026 produz
 * `0002-…`, `0020-…`, `0202-…` antes de `2026-…`. Com `até = 0002-11-19`
 * TODO artefato é maior que o limite e cai fora — o card esvazia enquanto a
 * pessoa digita, e ela vê os serviços desaparecerem.
 *
 * 🚨 ESTES TESTES EXERCITAM O GESTO, não a função: é a diferença entre o que
 * eu fiz antes de publicar (ler a fonte) e o que ele teve de fazer por mim
 * (usar a tela). As duas travas são independentes de propósito — se alguém
 * voltar o evento para `input`, a primeira pega; se um teclado comitar uma
 * data torta, a segunda pega.
 */
describe('o filtro de data não pode esvaziar o card', () => {
  it('o campo escuta `change`, não `input` — ano parcial não filtra nada',
     async () => {
    const tela = await montar()
    await abrirOFranck(tela)
    const datas = tela.findAll('.card__filtro input[type="date"]')
    const ate = datas[1]
    /* A sequência que o navegador produz enquanto se digita o ano 2026. */
    for (const parcial of ['0002-11-19', '0020-11-19', '0202-11-19']) {
      await ate.setValue(parcial)
      /* só `input`: é o que o navegador manda a cada dígito */
      await ate.trigger('input')
      expect(tela.text()).toContain('OS 16689')
      expect(tela.text()).toContain('OS 17120')
    }
  })

  it('ano implausível comitado ainda não esvazia o card', async () => {
    const tela = await montar()
    await abrirOFranck(tela)
    const ate = tela.findAll('.card__filtro input[type="date"]')[1]
    await ate.setValue('0002-11-19')
    await ate.trigger('change')
    /* 🚨 Limite com ano antes de 1900 é limite que NÃO EXISTE. */
    expect(tela.text()).toContain('OS 16689')
    expect(tela.text()).toContain('OS 17120')
  })

  it('a data completa e plausível filtra de verdade', async () => {
    const tela = await montar()
    await abrirOFranck(tela)
    const ate = tela.findAll('.card__filtro input[type="date"]')[1]
    await ate.setValue('2026-10-01')
    await ate.trigger('change')
    /* a de agosto fica, a de 17/11 sai */
    expect(tela.text()).toContain('OS 16689')
    expect(tela.text()).not.toContain('OS 17120')
  })

  it('o CARD continua na coluna mesmo sem nenhum artefato à vista, e DIZ',
     async () => {
    const tela = await montar()
    await abrirOFranck(tela)
    const datas = tela.findAll('.card__filtro input[type="date"]')
    await datas[0].setValue('2030-01-01')
    await datas[0].trigger('change')
    const texto = tela.text()
    /* 🚨 O card do Franck não pode desaparecer: card vazio é informação
       ("nada a pagar neste período"); card ausente é a tela mentindo.
       ⚠️ E agora são DUAS coisas a cobrar: o diálogo diz que está vazio, E o
       card fechado por trás continua na coluna. Sumir do quadro seria o mesmo
       defeito num lugar novo. */
    expect(texto).toContain('Franck')
    expect(texto).toContain('Nenhum artefato à vista com este filtro')
    expect(texto).not.toContain('OS 16689')
    expect(tela.findAll('article.card').some((a) => a.text().includes('Franck')),
           'o card fechado do Franck tem de continuar na coluna').toBe(true)
  })

  it('o contador do card acompanha o filtro', async () => {
    const tela = await montar()
    await abrirOFranck(tela)
    const ate = tela.findAll('.card__filtro input[type="date"]')[1]
    await ate.setValue('2026-10-01')
    await ate.trigger('change')
    /* 2 artefatos no card do Franck, 1 dentro do período */
    expect(tela.text()).toContain('1 de 2')
  })

  it('limpar devolve tudo', async () => {
    const tela = await montar()
    await abrirOFranck(tela)
    const ate = tela.findAll('.card__filtro input[type="date"]')[1]
    await ate.setValue('2026-10-01')
    await ate.trigger('change')
    expect(tela.text()).not.toContain('OS 17120')
    const limpar = tela.findAll('button').find((b) => b.text() === 'limpar')
    await limpar.trigger('click')
    expect(tela.text()).toContain('OS 17120')
  })
})
