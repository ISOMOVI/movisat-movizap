/*
 * @vitest-environment jsdom
 *
 * O CHECKLIST DA ETAPA no painel da Operação — áreas A e B (04/11).
 *
 * 🚨 SUÍTE VERDE NÃO PROVA TELA (`M9`) — em 29/10 ele achou 8 defeitos com o
 * placar verde. O que estes testes alcançam:
 *
 *   1. o **selo** "2 de 3" no card fechado, e a diferença entre *"a etapa tem
 *      lista e ninguém abriu"* e *"não tem lista"*;
 *   2. a **lista dentro do card**, marcar, e o item avulso com o ✕ — que o
 *      item de modelo **não** tem;
 *   3. a tela diz que o checklist **não vai para a OS**;
 *   4. o **aviso ao entrar** aparece, e depois do Ok **não aparece de novo**
 *      por 10 minutos (decisão dele);
 *   5. `localStorage` quebrado **não impede mover**.
 *
 * ⚠️ Arquivo próprio, com mock próprio: o `painel_2210.teste.js` tem 1152
 * linhas e guarda outras 60 regras — mexer no mock dele para caber isto seria
 * arriscar o que já está provado.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = {
  quadro: null, postado: [], apagado: [], resposta: null,
  checklist: [], empurrado: [],
  /* 🔵 11/11: o campo de texto da etapa. `campos` é o CATÁLOGO que o servidor
     manda (etapa -> campo), e `camposDaEtapa` são os valores já escritos. */
  campos: {}, camposDaEtapa: {},
}

/* O catálogo como o `movizap/campo_etapa.py` o devolve -- retrato, e não
   invenção: se o servidor mudar os rótulos, esta fixture fica irreal e é isso
   que se conserta, não o código. */
const CATALOGO = {
  rastreio: { situacao_id: 677, rotulo: 'Rastreamento',
              ajuda: 'O código que será enviado ao cliente junto com o item.',
              ao_cliente: true },
  devolucao: { situacao_id: 15696, rotulo: 'Devolução',
               ajuda: 'O código de devolução do item. Consulta interna da '
                      + 'operadora — não é enviado ao cliente.',
               ao_cliente: false },
}

vi.mock('../src/api/cliente.js', () => ({}))
vi.mock('./api/cliente.js', () => ({
  api: {
    get: async (caminho) => {
      const c = String(caminho)
      if (c.includes('/checklist')) return { itens: estado.checklist }
      if (c.includes('/passagens')) return { passagens: [] }
      if (c.includes('/ficha')) {
        return { observacoes: estado.observacoes || [], prioridades: {},
                 campos: estado.campos, campos_da_etapa: estado.camposDaEtapa }
      }
      return estado.quadro
    },
    post: async (caminho, corpo) => {
      estado.postado.push([caminho, corpo])
      if (String(caminho).includes('/checklist/item')) {
        estado.checklist = [...estado.checklist,
                            { id: 90, texto: corpo.texto, feito: false,
                              avulso: true }]
        return { itens: estado.checklist }
      }
      return estado.resposta ?? { ok: true }
    },
    put: async (caminho) => {
      estado.postado.push([caminho, null])
      estado.checklist = estado.checklist.map(
        (i) => (caminho.endsWith(`/${i.id}`) ? { ...i, feito: !i.feito } : i))
      return { itens: estado.checklist }
    },
    del: async (caminho) => {
      estado.apagado.push(caminho)
      estado.checklist = estado.checklist.filter(
        (i) => !caminho.endsWith(`/${i.id}`))
      return { itens: estado.checklist }
    },
  },
  /* 🚨 O QUE O `estado/sessao.js` IMPORTA. A tela passou a ler quem está
     logado (para o `souOwner` do apagar), e sem estes três o import do módulo
     estoura na COLETA -- a suíte inteira cai antes do primeiro teste.
     ⚠️ Molde do `abas_do_painel_0611.teste.js`, que já os declarava. */
  quandoPerderSessao: () => {},
  definirToken: () => {},
  temToken: () => false,
  relatarErroDeBotao: () => {},
  ErroDeApi: class extends Error {},
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: (d) => estado.empurrado.push(d) }),
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

function card(extra = {}) {
  return {
    id: null, origem: 'erp', numero_ordem: 17056, os_id: 870036,
    situacao_id: 251, cliente: 'Zz Cliente', criada_em: '2026-11-04T09:00:00-03:00',
    tipo_nome: 'Retirada', placas: [], tecnicos: [], observacoes: 0,
    anexos: 0, estado: null, formulario: null, prioridade: 382,
    prioridade_nome: 'Normal', status_str: 'Nova', finalizada: false,
    checklist: null, tem_checklist: false, ...extra,
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

async function montar() {
  const tela = mount(PainelOperacao, { global: { stubs: { AjudaDaTela: true } } })
  await flushPromises()
  return tela
}

beforeEach(() => {
  estado.quadro = quadro()
  estado.postado = []
  estado.apagado = []
  estado.resposta = null
  estado.checklist = []
  estado.empurrado = []
  estado.observacoes = []
  estado.campos = CATALOGO
  estado.camposDaEtapa = {}
  try { localStorage.clear() } catch { /* jsdom sempre tem, mas não custa */ }
})

describe('o selo no card fechado', () => {
  it('🔵 mostra "2 de 3" quando há checklist marcado', async () => {
    estado.quadro = quadro({ 251: [card({ checklist: { feitos: 2, total: 3 },
                                          tem_checklist: true })] })
    const tela = await montar()
    expect(tela.text()).toContain('2 de 3')
  })

  it('🚨 "tem lista e ninguém abriu" é DIFERENTE de "não tem lista"', async () => {
    estado.quadro = quadro({ 251: [card({ checklist: null,
                                          tem_checklist: true })] })
    let tela = await montar()
    expect(tela.text()).toContain('checklist')

    estado.quadro = quadro({ 38: [card({ situacao_id: 38, checklist: null,
                                         tem_checklist: false })] })
    tela = await montar()
    /* Etapa sem lista não desenha selo nenhum — nem a palavra. */
    const pilulas = tela.findAll('.pilula').map((p) => p.text())
    expect(pilulas).not.toContain('checklist')
  })
})

/* 🚨 A TRAVA *"diz que NAO vai para a OS"* SAIU EM 05/11: ele tirou a frase
   do pe do painel do checklist (*"nao precisam mante-los no card"*).
   ⚠️ A regra segue: mover o card grava o checklist como observacao, e nada
   chega ao Harmonit -- e a decisao O4 dele de 04/11. O que saiu foi o texto. */

describe('a lista dentro do card', () => {
  beforeEach(() => {
    estado.quadro = quadro({ 251: [card({ checklist: { feitos: 0, total: 2 },
                                          tem_checklist: true })] })
    estado.checklist = [
      { id: 1, texto: 'Informação do contrato sobre os equipamentos',
        feito: false, avulso: false, feito_por: null, feito_em: null },
      { id: 2, texto: 'Cadastrar cliente e veículos',
        feito: true, avulso: false, feito_por: 'Iago',
        feito_em: '2026-11-04T15:02:00-03:00' },
      { id: 3, texto: 'Conferir com o cliente', feito: false, avulso: true,
        feito_por: null, feito_em: null },
    ]
  })

  async function abrir() {
    const tela = await montar()
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    return tela
  }

  it('abre com os itens e o placar', async () => {
    const tela = await abrir()
    const texto = tela.text()
    expect(texto).toContain('Checklist desta etapa')
    expect(texto).toContain('Informação do contrato sobre os equipamentos')
    expect(texto).toContain('1 de 3')
  })


  it('marcar manda o PUT e relê do servidor', async () => {
    const tela = await abrir()
    const caixas = tela.findAll('.check__linha input')
    await caixas[0].trigger('change')
    await flushPromises()
    const put = estado.postado.find(([c]) => c.includes('/checklist/item/1'))
    expect(put).toBeTruthy()
  })

  it('🚨 só o item AVULSO tem o ✕', async () => {
    const tela = await abrir()
    const linhas = tela.findAll('.modal__passagens li')
    const comX = linhas.filter((l) => l.text().includes('✕'))
    expect(comX.length).toBe(1)
    expect(comX[0].text()).toContain('Conferir com o cliente')
  })

  it('acrescentar item manda o POST com a OS e a etapa', async () => {
    const tela = await abrir()
    const campo = tela.findAll('input').find(
      (i) => i.attributes('placeholder') === '+ Adicionar item')
    await campo.setValue('Zz item novo')
    await tela.findAll('button').find((b) => b.text() === 'Adicionar')
      .trigger('click')
    await flushPromises()
    const post = estado.postado.find(([c]) => c.endsWith('/checklist/item'))
    expect(post[1]).toMatchObject({ numero_os: 17056, situacao_id: 251,
                                    texto: 'Zz item novo' })
  })

  it('o item feito mostra quem e quando', async () => {
    const tela = await abrir()
    expect(tela.text()).toContain('Iago')
  })
})

describe('o aviso ao entrar na etapa (Área B)', () => {
  beforeEach(() => {
    estado.quadro = quadro({
      38: [card({ situacao_id: 38, tem_checklist: false })],
      251: [card({ numero_ordem: 17057, tem_checklist: true })],
    })
  })

  async function moverPeloModal(tela, destino) {
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    const select = tela.findAll('select').find(
      (s) => s.text().includes('Configurar equipamentos'))
    await select.setValue(String(destino))
    await flushPromises()
  }

  it('🔵 aparece ao mover para etapa COM checklist', async () => {
    const tela = await montar()
    await moverPeloModal(tela, 251)
    expect(tela.text()).toContain('Esta etapa tem')
    expect(tela.text()).toContain('dentro do card')
  })

  it('🚨 depois do Ok, NÃO avisa de novo', async () => {
    const tela = await montar()
    await moverPeloModal(tela, 251)
    await tela.findAll('button').find((b) => b.text() === 'Ok').trigger('click')
    await flushPromises()
    expect(tela.text()).not.toContain('Esta etapa tem')

    /* O segundo card, na mesma etapa, dentro dos 10 min: silêncio. */
    await moverPeloModal(tela, 251)
    expect(tela.text()).not.toContain('Esta etapa tem')
  })

  it('não aparece para etapa SEM checklist', async () => {
    const tela = await montar()
    await moverPeloModal(tela, 38)
    expect(tela.text()).not.toContain('Esta etapa tem')
  })

  it('⚠️ localStorage quebrado não impede mover', async () => {
    const guardar = Storage.prototype.setItem
    const ler = Storage.prototype.getItem
    Storage.prototype.setItem = () => { throw new Error('sem espaço') }
    Storage.prototype.getItem = () => { throw new Error('bloqueado') }
    try {
      const tela = await montar()
      await moverPeloModal(tela, 251)
      /* o mover aconteceu... */
      expect(estado.postado.some(([c]) => c.includes('/mover'))).toBe(true)
      /* ...e fechar o aviso não estoura */
      const ok = tela.findAll('button').find((b) => b.text() === 'Ok')
      if (ok) await ok.trigger('click')
    } finally {
      Storage.prototype.setItem = guardar
      Storage.prototype.getItem = ler
    }
  })
})

describe('os recados em modal (Área D)', () => {
  beforeEach(() => {
    estado.quadro = quadro({ 251: [card({ observacoes: 2 })] })
    /* ⚠️ NA ORDEM EM QUE O SERVIDOR DEVOLVE: mais NOVA primeiro
       (`passagem.observacoes` ordena `em DESC`). É por isso que o modal
       faz `.reverse()` — em conversa, a mais nova fica por último. Na
       primeira escrita este mock estava crescente, e o teste mediu com
       dado irreal. */
    estado.observacoes = [
      { id: 12, texto: 'Comprovante em anexo', em: '2026-11-04T17:00:00-03:00',
        quem: 'Karla',
        anexos: [{ id: 5, nome_original: 'nota.pdf', bytes: 2048, mime: 'application/pdf' }] },
      { id: 11, texto: '[checklist] Configurar equipamentos e Sistemas — 1 de 2\n✓ Um (Iago, 04/11 15:02)\n✗ Dois',
        em: '2026-11-04T16:00:00-03:00', quem: 'Iago', anexos: [] },
      { id: 10, texto: 'Cliente pediu para adiar', em: '2026-11-04T15:00:00-03:00',
        quem: 'Iago', anexos: [] },
    ]
  })

  async function abrirRecados(tela) {
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    await tela.findAll('button').find((b) => b.text() === 'Abrir observações')
      .trigger('click')
    await flushPromises()
  }

  it('🔵 o card aberto tem a PORTA, não a lista', async () => {
    const tela = await montar()
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    const secao = tela.find('.modal__recados').text()
    expect(secao).toContain('Abrir observações')
    /* O conteúdo do recado não aparece antes de abrir o modal. */
    expect(secao).not.toContain('Cliente pediu para adiar')
  })

  it('abre em bolhas, da mais antiga para a mais nova', async () => {
    const tela = await montar()
    await abrirRecados(tela)
    const baloes = tela.findAll('.recado')
    expect(baloes.length).toBe(3)
    expect(baloes[0].text()).toContain('Cliente pediu para adiar')
    expect(baloes[2].text()).toContain('Comprovante em anexo')
  })

  it('🚨 o recado do SISTEMA é desenhado diferente', async () => {
    const tela = await montar()
    await abrirRecados(tela)
    const sistema = tela.findAll('.recado').filter(
      (b) => b.text().includes('[checklist]'))
    expect(sistema.length).toBe(1)
    expect(sistema[0].classes()).toContain('recado--sistema')
    /* E diz por extenso que não foi pessoa que escreveu. */
    expect(sistema[0].text()).toContain('registrado pelo sistema')
  })

  it('o checklist vira várias linhas, não um parágrafo só', async () => {
    const tela = await montar()
    await abrirRecados(tela)
    const sistema = tela.findAll('.recado').find(
      (b) => b.text().includes('[checklist]'))
    expect(sistema.findAll('.recado__linha').length).toBe(3)
  })

  /* --------------------------------------------------------------------------
     A COR DO PLACAR — 11/11
     🔵 Ele: *"os marcados ficam com em verde e os não marcados ficam em
     vermelho"*.
     ⚠️ A classe é o que se pode medir: o jsdom não calcula cor computada, e
     afirmar sobre `color` aqui seria afirmar sobre nada.
     ------------------------------------------------------------------------ */
  it('🔵 o item feito fica verde e o que faltou fica vermelho', async () => {
    const tela = await montar()
    await abrirRecados(tela)
    const sistema = tela.findAll('.recado').find(
      (b) => b.text().includes('[checklist]'))
    const linhas = sistema.findAll('.recado__linha')
    /* A primeira linha é o cabeçalho com o placar — não é item, não tem cor. */
    expect(linhas[0].classes()).not.toContain('recado__linha--feito')
    expect(linhas[0].classes()).not.toContain('recado__linha--falta')
    expect(linhas[1].text()).toContain('Um')
    expect(linhas[1].classes()).toContain('recado__linha--feito')
    expect(linhas[2].text()).toContain('Dois')
    expect(linhas[2].classes()).toContain('recado__linha--falta')
  })

  it('🚨 o ✓ e o ✗ CONTINUAM no texto — cor não é portador sozinha', async () => {
    const tela = await montar()
    await abrirRecados(tela)
    const sistema = tela.findAll('.recado').find(
      (b) => b.text().includes('[checklist]'))
    /* Quem não distingue verde de vermelho tem de continuar lendo o placar.
       É a mesma régua da pílula do card (âmbar E luminosidade) e do item
       riscado E esmaecido. */
    expect(sistema.text()).toContain('✓ Um')
    expect(sistema.text()).toContain('✗ Dois')
  })

  it('⚠️ recado de PESSOA que começa com ✓ não é pintado', async () => {
    /* Pintar qualquer linha com ✓ inventaria significado: só o recado do
       checklist é placar de etapa. */
    estado.observacoes = [
      { id: 20, texto: '✓ falei com o cliente\n✗ não atendeu',
        em: '2026-11-04T15:00:00-03:00', quem: 'Karla', anexos: [] },
    ]
    const tela = await montar()
    await abrirRecados(tela)
    const linhas = tela.findAll('.recado__linha')
    expect(linhas.length).toBe(2)
    expect(linhas[0].classes()).not.toContain('recado__linha--feito')
    expect(linhas[1].classes()).not.toContain('recado__linha--falta')
  })

  it('🚨 o anexo é pedido pelo ID, nunca pelo caminho de disco', async () => {
    /* ⚠️ ESTA TRAVA MUDOU DE ALVO EM 05/11, e nao de regra. Ela exigia um
       `<a href>` -- e o `<a href>` era o DEFEITO: a rota do anexo e protegida
       por `Bearer` sem nenhum outro caminho, e navegacao de link **nao manda
       cabecalho `Authorization`**. Todo clique era **401**: o arquivo subia e
       nunca voltava. ⚠️ Ninguem notou porque `os_observacao_arquivo` tinha
       ZERO linhas -- o furo estava no caminho de volta, nunca percorrido.
       🚨 A REGRA QUE IMPORTA CONTINUA INTEIRA, e e esta: o que identifica o
       anexo e o ID, e o `caminho` de disco nao aparece em lugar nenhum. */
    const tela = await montar()
    await abrirRecados(tela)
    const botao = tela.find('.recado__anexos .recado__anexo')
    expect(botao.exists()).toBe(true)
    expect(botao.element.tagName).toBe('BUTTON')
    expect(botao.text()).toContain('nota.pdf')
    /* 🚨 e nada no DOM carrega o caminho de disco */
    expect(tela.html()).not.toContain('/home/claude')
    expect(tela.find('.recado__anexos a').exists()).toBe(false)
  })

  /* 🚨 A TRAVA *"diz que o anexo NAO tem backup"* SAIU EM 05/11: ele mandou
     apagar a frase (*"esses comentarios pode apagar, nao precisamos deles"*).
     ⚠️ O FATO CONTINUA VERDADE -- a pasta dos anexos vive fora do repositorio
     e o backup leva o banco, entao a linha sobrevive e o arquivo nao. O que
     deixou de existir foi a tela dizer isso. Esta escrito na migracao 091 e no
     `docs/06`, e a trava esta no git, no commit anterior. */

  it('o modal repete que não vai para a OS', async () => {
    const tela = await montar()
    await abrirRecados(tela)
    expect(tela.text()).toMatch(/Não (vai|vão) para a OS/)
  })

  it('salvar manda o texto e depois relê do servidor', async () => {
    const tela = await montar()
    await abrirRecados(tela)
    const caixa = tela.findAll('textarea').find(
      (t) => t.attributes('aria-label') === 'Escrever observação')
    await caixa.setValue('Zz recado novo')
    await tela.findAll('button').find((b) => b.text() === 'Salvar')
      .trigger('click')
    await flushPromises()
    const post = estado.postado.find(([c]) => c.endsWith('/observacao'))
    expect(post[1]).toMatchObject({ numero_os: 17056, texto: 'Zz recado novo' })
  })

  it('não salva com texto vazio e sem anexo', async () => {
    const tela = await montar()
    await abrirRecados(tela)
    const botao = tela.findAll('button').find((b) => b.text() === 'Salvar')
    expect(botao.attributes('disabled')).toBeDefined()
  })
})

/*
 * ÁREA E (05/11) — O TERMO NO CARD E A BUSCA POR TERMO
 *
 * 🔵 *"termo no card e busca"*.
 *
 * ⚠️ VIVE NESTE ARQUIVO, e não no `painel_2210.teste.js`: o mock daqui já é o
 * do card e do modal, e o de lá tem 1152 linhas guardando outras 60 regras.
 *
 * 🚨 O QUE A SUÍTE NÃO ALCANÇA (`M9`): se o termo está no cache. A extração é
 * medida no FPSL (`tests/teste_termo_da_os.py`) e o preenchimento das 603 OS
 * do cache é script à mão. O que se mede aqui é a TELA, dado o campo.
 */
describe('o termo no card (Área E)', () => {
  it('🔵 escreve TERMO ao lado da OS', async () => {
    estado.quadro = quadro({ 251: [card({ termo: '8937' })] })
    const tela = await montar()
    expect(tela.text()).toContain('OS 17056')
    expect(tela.text()).toContain('TERMO 8937')
  })

  it('🚨 card SEM termo não escreve "sem termo" nenhum', async () => {
    // ⚠️ É 1 de cada 7 cards (medido em 05/11: 27 de 200 OS). Uma linha
    // dizendo "sem termo" seria ruído repetido em 85 cards para dizer o que
    // não tem o que dizer.
    estado.quadro = quadro({ 251: [card({ termo: null })] })
    const tela = await montar()
    // ⚠️ A asserção é no CARD, não na tela: a caixa de busca diz "ou termo"
    // de propósito, e um `not.toMatch` na tela inteira reprovaria por causa
    // dela — era o teste errado, não a tela.
    const umCard = tela.find('.card')
    expect(umCard.text()).toContain('OS 17056')
    expect(umCard.text()).not.toMatch(/termo/i)
    expect(tela.find('.card__termo').exists()).toBe(false)
  })

  it('o termo aparece também no card ABERTO', async () => {
    estado.quadro = quadro({ 251: [card({ termo: '8937' })] })
    const tela = await montar()
    await tela.find('.card__os').trigger('click')
    await flushPromises()
    /* ⚠️ A CLASSE MUDOU EM 05/11 (`modal__sub` -> `modal__ident`), com a
       proposta A: o cliente subiu para titulo do modal e os identificadores
       (OS, TERMO, tipo, placa) passaram a ser uma linha propria, em vez de um
       subtitulo de apoio. A regra medida e a mesma: o termo aparece no card
       aberto. */
    expect(tela.find('.modal__ident').text()).toContain('TERMO 8937')
  })

  it('⚠️ o número da OS continua sendo o BOTÃO, não o termo', async () => {
    // 🚨 A OS é a identidade com que se AGE (abre o card); o termo é
    // referência de papel. Se o termo virasse alvo de clique, o card teria
    // dois jeitos de abrir e um deles não é o que a pessoa aprendeu.
    estado.quadro = quadro({ 251: [card({ termo: '8937' })] })
    const tela = await montar()
    expect(tela.find('.card__termo').element.tagName).not.toBe('BUTTON')
    expect(tela.find('.card__os').element.tagName).toBe('BUTTON')
  })

  it('🔵 a caixa de busca diz que procura por termo', async () => {
    const tela = await montar()
    const caixa = tela.find('.painel__busca input')
    expect(caixa.attributes('placeholder')).toContain('termo')
    expect(tela.find('.painel__busca').text()).toContain('termo')
  })

  it('🚨 a tela diz quando casou por TERMO', async () => {
    // Sem isto, quem procura 8937 não sabe se achou a OS 8937 ou as 6 OS do
    // termo 8937 — os dois são números de 4-5 dígitos no mesmo card.
    estado.quadro = quadro({ 251: [card({ termo: '8937' })] })
    estado.quadro.busca = '8937'
    estado.quadro.filtro_casou_por = ['termo']
    const tela = await montar()
    expect(tela.text()).toContain('casou por termo')
  })
})

/* ============================================================================
   O CAMPO DE TEXTO DA ETAPA — Rastreamento e Devolução (11/11)
   ----------------------------------------------------------------------------
   🔵 *"Abaixo de 'Observações', criar um campo de texto chamado
   'Rastreamento'"* (etapa 677) · *"um campo de texto chamado 'Devolução' (...)
   Apenas para consulta interna da operadora"* (etapa 15696).

   🚨 A TELA NÃO SABE QUAL ETAPA PEDE QUAL CAMPO -- quem diz é o servidor, no
   catálogo que a ficha devolve. Estas travas provam isso: trocar a situação do
   catálogo muda onde a caixa aparece, sem tocar na tela.
   ========================================================================== */
describe('o campo de texto da etapa', () => {
  async function abrirCardEm(situacao) {
    estado.quadro = quadro({ [situacao]: [card({ situacao_id: situacao })] })
    const tela = await montar()
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    await flushPromises()
    return tela
  }

  it('🔵 na etapa 677 a caixa Rastreamento aparece', async () => {
    const tela = await abrirCardEm(677)
    const texto = tela.find('.modal__caixa').text()
    expect(texto).toContain('Rastreamento')
    expect(texto).toContain('será enviado ao cliente')
    expect(tela.findAll('input[placeholder="Rastreamento"]').length).toBe(1)
  })

  it('🔵 na etapa 15696 a caixa Devolução aparece, e diz que é interna', async () => {
    const tela = await abrirCardEm(15696)
    const texto = tela.find('.modal__caixa').text()
    expect(texto).toContain('Devolução')
    /* 🚨 A diferença entre os dois campos é ESTA FRASE: o rastreio vai ao
       cliente, a devolução não. Sem ela, a operadora não tem como saber. */
    expect(texto).toContain('não é enviado ao cliente')
  })

  it('⚠️ etapa que não pede campo não desenha caixa nenhuma', async () => {
    const tela = await abrirCardEm(251)
    expect(tela.findAll('input[placeholder="Rastreamento"]').length).toBe(0)
    expect(tela.findAll('input[placeholder="Devolução"]').length).toBe(0)
  })

  it('🚨 a tela DIZ que o código não vai para o Harmonit', async () => {
    /* A mesma régua da observação: quem escreve precisa saber se chegou ao
       ERP, e não chega. */
    const tela = await abrirCardEm(677)
    expect(tela.find('.modal__caixa').text())
      .toContain('Não vai para a OS do Harmonit')
  })

  it('grava pela rota certa, com a chave da etapa', async () => {
    const tela = await abrirCardEm(677)
    const caixa = tela.find('input[placeholder="Rastreamento"]')
    await caixa.setValue('AA123456789BR')
    await tela.findAll('button').find((b) => b.text() === 'Gravar').trigger('click')
    await flushPromises()
    const pedido = estado.postado.find(
      ([c]) => String(c).includes('/campo-da-etapa'))
    expect(pedido).toBeTruthy()
    expect(pedido[1]).toEqual({ numero_os: 17056, chave: 'rastreio',
                                valor: 'AA123456789BR' })
  })

  it('⚠️ caixa vazia não grava, e espaço só também não', async () => {
    const tela = await abrirCardEm(677)
    const botao = tela.findAll('button').find((b) => b.text() === 'Gravar')
    expect(botao.attributes('disabled')).toBeDefined()
    await tela.find('input[placeholder="Rastreamento"]').setValue('   ')
    expect(botao.attributes('disabled')).toBeDefined()
    expect(estado.postado.filter(([c]) => String(c).includes('/campo-da-etapa')))
      .toEqual([])
  })

  it('🔵 o valor já escrito aparece com quem e quando', async () => {
    estado.camposDaEtapa = {
      rastreio: { valor: 'BB999999999BR', quem: 'Karla',
                  em: '2026-11-10T14:00:00-03:00' },
    }
    const tela = await abrirCardEm(677)
    const texto = tela.find('.modal__caixa').text()
    expect(texto).toContain('BB999999999BR')
    expect(texto).toContain('Karla')
  })

  it('🚨 o rastreio escrito na 677 CONTINUA visível em outra etapa', async () => {
    /* ⚠️ É o caso de uso real: na 15747 (Aguardando recebimento) o cliente
       pergunta onde está o item, e o código foi escrito na etapa anterior. */
    estado.camposDaEtapa = {
      rastreio: { valor: 'CC777777777BR', quem: 'Karla', em: null },
    }
    const tela = await abrirCardEm(15747)
    expect(tela.find('.modal__caixa').text()).toContain('CC777777777BR')
    /* E sem caixa para escrever: esta etapa não pede campo. */
    expect(tela.findAll('input[placeholder="Rastreamento"]').length).toBe(0)
  })
})

/* ============================================================================
   APAGAR OBSERVAÇÃO — 11/11
   ----------------------------------------------------------------------------
   🔵 Dele: *"Se excluírem, aparecerá como 'Observação excluida' e log's"* ·
   *"somente owner pode visualizar o exlcuido, com botão, como no chat
   interno"* · *"deve ter disponivel exibição da autoria sim, é um dos
   objetivos, rastreabilidade"*.

   🚨 O CONTEÚDO É ESCONDIDO PELO SERVIDOR, NÃO PELA TELA: para quem não é
   owner o `texto` chega **nulo**. Estas travas montam as duas respostas
   possíveis -- é o retrato do que a rota devolve, e não uma invenção da
   fixture.
   ========================================================================== */
describe('apagar observação', () => {
  /* ⚠️ HELPER PRÓPRIO: o `abrirRecados` do bloco dos recados vive dentro
     daquele `describe` e não se alcança daqui. Copiar o gesto é melhor que
     subir a função para o topo do arquivo e dar a dois blocos uma dependência
     comum que nenhum dos dois pediu. */
  async function abrirRecados(tela) {
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    await tela.findAll('button').find((b) => b.text() === 'Abrir observações')
      .trigger('click')
    await flushPromises()
  }

  /* ⚠️ O `beforeEach` de fora monta o quadro VAZIO -- sem card não há
     `.card__abrir` para clicar, e o modal dos recados vive dentro do card
     aberto. */
  beforeEach(() => { estado.quadro = quadro({ 251: [card()] }) })

  /* O que o servidor manda para quem NÃO é owner: sem texto, sem anexo, com a
     autoria dos dois lados. */
  const apagadaFechada = {
    id: 30, texto: null, em: '2026-11-11T09:00:00-03:00', quem: 'Karla',
    apagada_em: '2026-11-11T10:00:00-03:00', apagada_por_nome: 'Iago',
    anexos: [],
  }
  /* O que ele manda para o owner: o texto vem. */
  const apagadaAberta = { ...apagadaFechada, texto: 'o que dizia' }

  const normal = {
    id: 31, texto: 'recado de gente', em: '2026-11-11T11:00:00-03:00',
    quem: 'Karla', apagada_em: null, apagada_por_nome: null, anexos: [],
  }
  const doSistema = {
    id: 32, texto: '[sistema] prioridade: Normal → Alta',
    em: '2026-11-11T11:30:00-03:00', quem: null,
    apagada_em: null, apagada_por_nome: null, anexos: [],
  }

  it('🔵 o recado apagado diz "Observação excluída" e não mostra o texto', async () => {
    estado.observacoes = [apagadaFechada]
    const tela = await montar()
    await abrirRecados(tela)
    const texto = tela.find('.modal--recados').text()
    expect(texto).toContain('Observação excluída')
    expect(texto).not.toContain('o que dizia')
  })

  it('🔵 a AUTORIA fica visível para quem não é owner', async () => {
    /* É o objetivo que ele nomeou: some o QUE dizia, não QUEM escreveu nem
       QUEM apagou. */
    estado.observacoes = [apagadaFechada]
    const tela = await montar()
    await abrirRecados(tela)
    const texto = tela.find('.modal--recados').text()
    expect(texto).toContain('Karla')
    expect(texto).toContain('excluída por Iago')
  })

  it('🚨 quem não é owner NÃO tem o botão "ver o que dizia"', async () => {
    estado.observacoes = [apagadaFechada]
    const tela = await montar()
    await abrirRecados(tela)
    const botoes = tela.findAll('.recado__revelar')
      .filter((b) => b.text().includes('ver o que dizia'))
    expect(botoes.length).toBe(0)
  })

  it('⚠️ o anexo do recado apagado não aparece', async () => {
    /* Deixar `comprovante-pix.pdf` ao lado de "Observação excluída" devolveria
       pela legenda o que o apagar tirou do texto. */
    estado.observacoes = [{
      ...apagadaFechada,
      anexos: [{ id: 7, nome_original: 'comprovante-pix.pdf', bytes: 10,
                 mime: 'application/pdf' }],
    }]
    const tela = await montar()
    await abrirRecados(tela)
    expect(tela.find('.modal--recados').text())
      .not.toContain('comprovante-pix.pdf')
  })

  it('🔵 o botão "excluir" aparece no recado de gente', async () => {
    estado.observacoes = [normal]
    const tela = await montar()
    await abrirRecados(tela)
    const botao = tela.findAll('.recado__revelar')
      .find((b) => b.text() === 'excluir')
    expect(botao).toBeTruthy()
  })

  it('🚨 e NÃO aparece no recado do SISTEMA', async () => {
    /* Aquele texto é o log (checklist, prioridade, rastreio). Apagar log é
       apagar a prova. */
    estado.observacoes = [doSistema]
    const tela = await montar()
    await abrirRecados(tela)
    const botao = tela.findAll('.recado__revelar')
      .find((b) => b.text() === 'excluir')
    expect(botao).toBeUndefined()
  })

  it('⚠️ nem no recado JÁ apagado', async () => {
    estado.observacoes = [apagadaFechada]
    const tela = await montar()
    await abrirRecados(tela)
    const botao = tela.findAll('.recado__revelar')
      .find((b) => b.text() === 'excluir')
    expect(botao).toBeUndefined()
  })

  it('clicar em excluir chama a rota certa, com o id do recado', async () => {
    estado.observacoes = [normal]
    const tela = await montar()
    await abrirRecados(tela)
    await tela.findAll('.recado__revelar')
      .find((b) => b.text() === 'excluir').trigger('click')
    await flushPromises()
    const pedido = estado.postado.find(
      ([c]) => String(c).includes('/observacao/') && String(c).endsWith('/apagar'))
    expect(pedido).toBeTruthy()
    expect(String(pedido[0])).toBe('/api/paineis/operacao/observacao/31/apagar')
  })
})
