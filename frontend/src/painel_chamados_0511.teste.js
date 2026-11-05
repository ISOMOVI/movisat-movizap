/*
 * @vitest-environment jsdom
 *
 * A COLUNA `Chamados` E O CARD DE CHAMADO — 05/11.
 *
 * 🔵 Ele: *"vamos criar uma coluna nova antes de 'Nova solicitação', chamada
 * 'Chamados', aqui vão ser gerados os cards que virão do forms de suporte, não
 * mais em OS e nessa coluna não são OS ainda, somente o CARD mesmo, com OBS,
 * etc"* · *"ter o botão de 'Finalizar Chamado' e daí vai perguntar 'Resolvido'
 * ou 'Não resolvido'"* · *"no card do chamado, tbm tem um botão de 'abrir
 * conversa' que abrirá a conversa com aquele numero no movizap para chat"*.
 *
 * 🚨 A LINHA QUE ESTAS TRAVAS GUARDAM É UMA SÓ: um card de chamado NÃO É UMA
 * OS. Ele não tem número, não tem situação no Harmonit, e nada que se faça
 * nele escreve no ERP. Toda trava aqui prende um lugar onde a tela poderia
 * esquecer isso e tratar os dois mundos como um.
 *
 * ⚠️ Arquivo próprio pelo mesmo motivo do `painel_card_modal_0511`: o
 * `painel_2210.teste.js` tem 78 travas de outras regras.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = { quadro: null, ficha: null, chamado: null,
                 pedido: [], postado: [], empurrado: [] }

vi.mock('../src/api/cliente.js', () => ({}))
vi.mock('./api/cliente.js', () => ({
  api: {
    get: async (caminho) => {
      const c = String(caminho)
      estado.pedido.push(c)
      if (c.includes('/checklist')) return { itens: [] }
      if (c.includes('/passagens')) return { passagens: [] }
      if (c.includes('/chamado/')) return estado.chamado
      if (c.includes('/ficha')) return estado.ficha
      return estado.quadro
    },
    post: async (caminho, corpo) => {
      estado.postado.push([String(caminho), corpo])
      if (String(caminho).includes('/chamado/observacao')) {
        return { id: 9, observacoes: [{ id: 9, texto: corpo.texto, em: null,
                                        quem: 'Iago', anexos: [] }] }
      }
      return { ok: true }
    },
    put: async () => ({ itens: [] }),
    del: async () => ({ itens: [] }),
  },
  ErroDeApi: class extends Error {},
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: (p) => estado.empurrado.push(String(p)) }),
  useRoute: () => ({ query: {} }),
}))

import PainelOperacao from './telas/PainelOperacao.vue'

const AGORA = Date.now()
const ha = (horas) => new Date(AGORA - horas * 3600 * 1000).toISOString()

/* O card de chamado, no MESMO contrato de chaves do card de OS — com os nulos
   que fazem dele um chamado. É o retrato do que `paineis._card_do_chamado`
   devolve. */
function cardDeChamado(extra = {}) {
  return {
    id: 87, origem: 'chamado', solicitacao_id: 544,
    formulario: 'Suporte', slug: 'suporte',
    criada_em: ha(5), estado: null,
    cliente: 'Velasco Leite Pastelaria ME', cliente_id: null,
    resumo: 'rastreador parou de pegar', anexos: 0, observacoes: 0,
    os_id: null, numero_ordem: null, situacao_id: null, situacao_em: null,
    tipo_nome: null, status_str: null, finalizada: null,
    placas: [], tecnicos: [], visto_em: null, etapa_desde: null,
    prioridade: null, prioridade_nome: null, termo: null,
    desfecho: null, desfecho_em: null, desfecho_rotulo: null,
    desfecho_por: null, telefone: '+5518998116168',
    ...extra,
  }
}

function cardDeOs(extra = {}) {
  return {
    id: null, origem: 'erp', numero_ordem: 17081, os_id: 870036,
    situacao_id: 251, cliente: 'Pastelaria Velasco', criada_em: ha(26),
    tipo_nome: 'Retirada', placas: [], tecnicos: [], observacoes: 0,
    anexos: 0, estado: null, formulario: null, prioridade: 382,
    prioridade_nome: 'Normal', status_str: 'Nova', finalizada: false,
    termo: '8937', etapa_desde: ha(2), tem_checklist: false,
    visto_em: ha(0.1), ...extra,
  }
}

/* ⚠️ O quadro com a coluna `Chamados` NA FRENTE das situações, e com
   `situacao_id: null` — é o que `paineis.montar` passou a devolver. */
function quadro(chamados = [], osPorSituacao = {}) {
  const situacoes = [[38, 'Novo Solicitação 1ª'],
                     [251, 'Configurar equipamentos e Sistemas']]
  return {
    painel: 'operacao', titulo: 'Operação', total: 1, pode_mover: true,
    desde: '2026-10-24', so_abertas: true, busca: '', ordem: 'prazo',
    ordens: [], ponte_respondeu: true, ponte_motivo: null,
    fora_do_quadro: null, filtro_casou_por: null,
    colunas: [
      { chave: 'chamados', titulo: 'Chamados', situacao_id: null,
        etapa_id: 1, nota: null, total: chamados.length, cards: chamados },
      ...situacoes.map(([sid, titulo]) => ({
        chave: `s${sid}`, titulo, situacao_id: sid, nota: null,
        total: (osPorSituacao[sid] || []).length,
        cards: osPorSituacao[sid] || [],
      })),
    ],
  }
}

async function montar(chamados = [cardDeChamado()], os = {}) {
  estado.quadro = quadro(chamados, os)
  const tela = mount(PainelOperacao, {
    attachTo: document.body,
    global: { stubs: { AjudaDaTela: true } },
  })
  await flushPromises()
  return tela
}

function colunaDosChamados(tela) {
  return tela.findAll('.coluna').find((c) => c.text().includes('Chamados'))
}

async function abrirOChamado(tela) {
  await colunaDosChamados(tela).find('.card__os').trigger('click')
  await flushPromises()
  await flushPromises()
  return tela.find('.modal--chamado')
}

beforeEach(() => {
  estado.pedido = []
  estado.postado = []
  estado.empurrado = []
  estado.ficha = { observacoes: [], prioridades: {}, prioridade: null,
                   descricao: null, solucao_tecnica: null, chamado: null,
                   tem_agendamento: false, agendamentos: [] }
  estado.chamado = {
    card: { id: 87, aba_id: 1, etapa_id: 1, solicitacao_id: 544,
            cliente_id: null, criado_em: ha(5), desfecho: null,
            desfecho_em: null, desfecho_por_nome: null },
    chamado: {
      solicitacao_id: 544, formulario: 'Suporte',
      respostas: [
        { nome: 'COMPANY_TITLE', nosso_nome: 'empresa', rotulo: 'Empresa',
          tipo: 'string', valor: 'Velasco Leite Pastelaria ME' },
        { nome: 'CONTACT_PHONE', nosso_nome: 'telefone', rotulo: 'Telefone',
          tipo: 'string', valor: '+5518998116168' },
        { nome: 'COMPANY_UF_CRM_1646332310941', nosso_nome: 'problema',
          rotulo: 'Qual o problema?', tipo: 'list',
          valor: ['Rastreador sem comunicação'] },
      ],
      anexos: [],
    },
    etapas: [{ id: 1, titulo: 'Chamados', ordem: 1, final: false }],
    observacoes: [],
    historico: [{ id: 3, em: ha(5), de_etapa: null, para_etapa: 1,
                  de_titulo: null, para_titulo: 'Chamados', quem: 'Iago' }],
    desfechos: { resolvido: 'Resolvido', virou_os: 'Virou OS' },
  }
  document.body.innerHTML = ''
})

/* ==========================================================================
   A COLUNA
   ========================================================================== */
describe('a coluna Chamados', () => {
  it('🔵 aparece, e ANTES de "Novo Solicitação 1ª"', async () => {
    const tela = await montar()
    const titulos = tela.findAll('.coluna__titulo').map((t) => t.text())
    expect(titulos[0]).toContain('Chamados')
    expect(titulos.join(' | ')).toContain('Novo Solicitação 1ª')
  })

  it('🚨 NÃO diz "situação N no Harmonit" — a etapa é nossa', async () => {
    const tela = await montar()
    const col = colunaDosChamados(tela)
    expect(col.text()).not.toMatch(/situação\s+\d+\s+no Harmonit/i)
    /* ⚠️ E a coluna de OS continua dizendo: a informação não sumiu da tela. */
    expect(tela.text()).toMatch(/situação\s+\d+\s+no Harmonit/i)
  })
})

/* ==========================================================================
   O CARD FECHADO
   ========================================================================== */
describe('o card de chamado, fechado', () => {
  it('🚨 NÃO escreve "OS" nenhuma — ele não tem número', async () => {
    const tela = await montar()
    const card = colunaDosChamados(tela).find('.card__abrir')
    expect(card.text()).not.toContain('OS ')
    expect(card.text()).not.toContain('null')
    /* 🔵 O que identifica o chamado é o formulário de onde ele veio. */
    expect(card.find('.card__os').text()).toBe('Suporte')
  })

  it('🚨 é visivelmente outro: tem a classe própria', async () => {
    const tela = await montar()
    expect(colunaDosChamados(tela).find('.card__abrir').classes())
      .toContain('card__abrir--chamado')
  })

  it('🔵 arquivado esmaece E DIZ QUAL desfecho foi', async () => {
    const tela = await montar([cardDeChamado({
      desfecho: 'resolvido', desfecho_rotulo: 'Resolvido',
      desfecho_em: ha(1) })])
    const card = colunaDosChamados(tela).find('.card__abrir')
    expect(card.classes()).toContain('card__abrir--arquivado')
    /* 🚨 `opacity` NÃO É O PORTADOR: cor e opacidade não carregam
       informação, e esmaecer sozinho não distingue Resolvido de Virou OS. */
    expect(card.find('.card__arquivado').text()).toContain('Resolvido')
  })

  it('🚨 "Virou OS" aparece como tal, e não como "Resolvido"', async () => {
    const tela = await montar([cardDeChamado({
      desfecho: 'virou_os', desfecho_rotulo: 'Virou OS',
      desfecho_em: ha(1) })])
    expect(colunaDosChamados(tela).find('.card__arquivado').text())
      .toContain('Virou OS')
  })
})

/* ==========================================================================
   O CARD ABERTO
   ========================================================================== */
describe('o card de chamado, aberto', () => {
  it('🚨 abre o diálogo do CHAMADO, e não o da OS', async () => {
    const tela = await montar()
    const dlg = await abrirOChamado(tela)
    expect(dlg.exists()).toBe(true)
    expect(tela.find('.modal--card').exists()).toBe(false)
  })

  it('🚨 NÃO pede a /ficha — chamado não tem OS para ler no ERP', async () => {
    const tela = await montar()
    await abrirOChamado(tela)
    expect(estado.pedido.some((c) => c.includes('/ficha'))).toBe(false)
    expect(estado.pedido.some((c) => c.includes('/chamado/87'))).toBe(true)
  })

  it('🚨 mostra as respostas por RÓTULO, nunca a chave do Bitrix', async () => {
    const tela = await montar()
    const dlg = await abrirOChamado(tela)
    expect(dlg.text()).toContain('Qual o problema?')
    expect(dlg.text()).toContain('Rastreador sem comunicação')
    expect(dlg.text()).not.toContain('COMPANY_UF_CRM_1646332310941')
  })

  it('🔵 o histórico de etapas aparece', async () => {
    const tela = await montar()
    const dlg = await abrirOChamado(tela)
    expect(dlg.find('.modal__passagens').text()).toContain('Chamados')
  })

  it('🚨 o Escape fecha o diálogo do chamado', async () => {
    const tela = await montar()
    await abrirOChamado(tela)
    /* ⚠️ `window`, e não `document`: o `aoTeclar` está em `window`, e
       `document.dispatchEvent` não sobe para lá — foi o que esta trava achou
       na primeira rodada. */
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(tela.find('.modal--chamado').exists()).toBe(false)
  })
})

/* ==========================================================================
   FINALIZAR CHAMADO
   ========================================================================== */
describe('Finalizar Chamado', () => {
  const finalizar = (dlg) => dlg.findAll('button')
    .find((b) => b.text().includes('Finalizar Chamado'))

  it('🔵 PERGUNTA antes de gravar — não finaliza no primeiro clique', async () => {
    const tela = await montar()
    const dlg = await abrirOChamado(tela)
    await finalizar(dlg).trigger('click')
    expect(estado.postado).toEqual([])
    expect(dlg.find('.desfecho__pergunta').text()).toContain('Resolvido')
    expect(dlg.find('.desfecho__pergunta').text()).toContain('Não resolvido')
  })

  it('🔵 "Resolvido" grava o desfecho resolvido', async () => {
    const tela = await montar()
    const dlg = await abrirOChamado(tela)
    await finalizar(dlg).trigger('click')
    await dlg.findAll('.desfecho__pergunta button')
      .find((b) => b.text() === 'Resolvido').trigger('click')
    await flushPromises()
    const [caminho, corpo] = estado.postado[0]
    expect(caminho).toBe('/api/paineis/operacao/chamado/87/finalizar')
    expect(corpo).toEqual({ desfecho: 'resolvido' })
  })

  it('🔵 "Não resolvido" grava virou_os', async () => {
    const tela = await montar()
    const dlg = await abrirOChamado(tela)
    await finalizar(dlg).trigger('click')
    await dlg.findAll('.desfecho__pergunta button')
      .find((b) => b.text() === 'Não resolvido').trigger('click')
    await flushPromises()
    expect(estado.postado[0][1]).toEqual({ desfecho: 'virou_os' })
  })

  it('🚨 NADA escreve no ERP: nenhum POST vai para a rota de mover OS', async () => {
    const tela = await montar()
    const dlg = await abrirOChamado(tela)
    await finalizar(dlg).trigger('click')
    await dlg.findAll('.desfecho__pergunta button')
      .find((b) => b.text() === 'Resolvido').trigger('click')
    await flushPromises()
    /* 🚨 Decisão dele: *"só marca; a OS é pelo Operação"*. A rota `/mover` da
       OS grava `situacaoId` no Harmonit — e nenhuma delas pode ser chamada
       por este botão. */
    for (const [caminho] of estado.postado) {
      expect(caminho).not.toMatch(/\/operacao\/mover/)
      expect(caminho).not.toMatch(/\/prioridade/)
    }
  })

  it('🔵 card já arquivado oferece REABRIR, e não Finalizar', async () => {
    const tela = await montar([cardDeChamado({
      desfecho: 'resolvido', desfecho_rotulo: 'Resolvido',
      desfecho_em: ha(1) })])
    const dlg = await abrirOChamado(tela)
    expect(finalizar(dlg)).toBeUndefined()
    const reabrir = dlg.findAll('button')
      .find((b) => b.text().includes('Reabrir'))
    await reabrir.trigger('click')
    await flushPromises()
    expect(estado.postado[0][0])
      .toBe('/api/paineis/operacao/chamado/87/reabrir')
  })
})

/* ==========================================================================
   ABRIR CONVERSA
   ========================================================================== */
describe('Abrir conversa', () => {
  it('🔵 empurra /atendimento com o número do chamado', async () => {
    const tela = await montar()
    const dlg = await abrirOChamado(tela)
    await dlg.findAll('button').find((b) => b.text().includes('Abrir conversa'))
      .trigger('click')
    expect(estado.empurrado)
      .toEqual(['/atendimento?numero=%2B5518998116168'])
  })

  it('⚠️ SEM telefone o botão não aparece, em vez de falhar no clique', async () => {
    const tela = await montar([cardDeChamado({ telefone: null })])
    const dlg = await abrirOChamado(tela)
    expect(dlg.findAll('button').some((b) => b.text().includes('Abrir conversa')))
      .toBe(false)
  })
})

/* ==========================================================================
   AS OBSERVAÇÕES DO CHAMADO
   ========================================================================== */
describe('as observações do chamado', () => {
  it('🔵 grava por solicitacao_id, e não por número de OS', async () => {
    const tela = await montar()
    const dlg = await abrirOChamado(tela)
    await dlg.find('textarea').setValue('liguei, o cliente vai testar')
    await dlg.findAll('button').find((b) => b.text() === 'Salvar')
      .trigger('click')
    await flushPromises()
    const [caminho, corpo] = estado.postado[0]
    expect(caminho).toBe('/api/paineis/operacao/chamado/observacao')
    expect(corpo).toEqual({ solicitacao_id: 544,
                            texto: 'liguei, o cliente vai testar' })
  })

  it('🔵 a observação salva aparece sem recarregar a ficha', async () => {
    const tela = await montar()
    const dlg = await abrirOChamado(tela)
    await dlg.find('textarea').setValue('liguei')
    await dlg.findAll('button').find((b) => b.text() === 'Salvar')
      .trigger('click')
    await flushPromises()
    expect(tela.find('.modal--chamado').text()).toContain('liguei')
  })
})

/* ==========================================================================
   A GUARDA DOS DOIS MUNDOS
   ========================================================================== */
describe('a guarda do arrasto entre os dois mundos', () => {
  it('🚨 card de OS NÃO entra na coluna Chamados', async () => {
    const tela = await montar([], { 251: [cardDeOs()] })
    const col = colunaDosChamados(tela)
    await tela.findAll('.card')[0].trigger('dragstart')
    await col.trigger('drop')
    await flushPromises()
    /* 🚨 Recusado NA TELA, sem ir à rota: `mover(card, null)` seria 422 — falha
       no lado seguro, mas com erro feio e sem dizer por quê. */
    expect(estado.postado).toEqual([])
    expect(tela.text()).toContain('não entra em Chamados')
  })

  it('🚨 card de CHAMADO não entra numa coluna de situação do ERP', async () => {
    const tela = await montar([cardDeChamado()], {})
    const col = tela.findAll('.coluna')
      .find((c) => c.text().includes('Novo Solicitação 1ª'))
    await colunaDosChamados(tela).find('.card').trigger('dragstart')
    await col.trigger('drop')
    await flushPromises()
    expect(estado.postado).toEqual([])
    expect(tela.text()).toContain('ainda não é uma OS')
  })
})
