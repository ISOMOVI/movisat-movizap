/*
 * @vitest-environment jsdom
 *
 * OS DOIS SELOS DO CARD, no painel da Operação (18/11).
 *
 * 🔵 Duas decisões dele do mesmo dia:
 *   · o **mover otimista** — *"assim op não para de trabalhar e seguimos no
 *     background com a OS"*: o card anda na hora e a escrita vai para fila;
 *   · a **trava de 1 minuto** — *"travas de 1 minuto para poder mexer o card,
 *     com mensagem na tela, assim evitamos gravação e movimentação rápida"*.
 *
 * 🚨 OS DOIS SÓ PODEM EXISTIR COM SELO, e é isto que estes testes guardam.
 * Card que anda sem garantia e sem dizer é tela que mente (`M12`) -- pior que o
 * erro honesto de antes, porque ninguém desconfia. E card que para de arrastar
 * sem explicar faz o operador concluir que travou e clicar mais, que é
 * exatamente o laço de 7 cliques da OS 17133 em 18/11.
 *
 * 🚨 E HÁ UMA ARMADILHA PRÓPRIA DESTA TELA, que custou uma entrega em 05–11/11:
 * `.pilula` é `scoped` por componente e NÃO existe em `estilo/*.css`. Selo que
 * reusasse aquele nome nasceria sem estilo nenhum, e **nenhum teste pegaria**,
 * porque o jsdom não faz layout. Então aqui se prova o que o jsdom alcança: a
 * classe certa, o ícone, o texto e o `title` -- e o `conferir_css_publicado.mjs`
 * cuida do resto no build.
 *
 * ⚠️ Arquivo e mock próprios, como o `disparo_dialogo_1711`: esticar o mock de
 * outro arquivo arriscaria o que já está provado lá.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = { quadro: null, postado: [], respostaMover: null }

vi.mock('../src/api/cliente.js', () => ({}))
vi.mock('./api/cliente.js', () => ({
  api: {
    get: async (caminho) => {
      const c = String(caminho)
      if (c.includes('/checklist')) return { itens: [] }
      if (c.includes('/passagens')) return { passagens: [] }
      if (c.includes('/ficha')) {
        return { observacoes: [], prioridades: {}, campos: {},
                 campos_da_etapa: {} }
      }
      return estado.quadro
    },
    post: async (caminho, corpo) => {
      estado.postado.push([String(caminho), corpo])
      if (String(caminho).includes('/mover')) {
        return estado.respostaMover ?? { ok: true }
      }
      return { ok: true }
    },
    put: async () => ({}),
    del: async () => ({}),
  },
  quandoPerderSessao: () => {},
  definirToken: () => {},
  temToken: () => false,
  relatarErroDeBotao: () => {},
  ErroDeApi: class extends Error {},
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: () => {} }),
  useRoute: () => ({ query: {} }),
}))

import PainelOperacao from './telas/PainelOperacao.vue'

const AS_DEZESSETE = [
  [38, 'Novo Solicitação 1ª'], [16487, 'Pendente de ação da Movisat'],
  [251, 'Configurar equipamentos e Sistemas'],
  [16488, 'Entrega de materiais prontos'],
  [677, 'Enviar por correio/transportadora'],
  [15747, 'Aguardando recebimento via correio/transportadora'],
  [15797, 'Rescisão Aguardando Aviso Prévio'], [890, 'Agendar serviço'],
  [16489, 'Confirmação agendamento'], [1316, 'Serviço Agendado'],
  [15696, 'Aguardando devolução de equipamento'],
  [16490, 'Analise de Equipamentos Retornados'],
  [15694, 'Atendimento finalizado'], [16491, 'Não atendido'],
  [15746, 'Financeiro'], [15695, 'Pós venda'], [16492, 'Contratual'],
]

function card(extra = {}) {
  return {
    id: null, origem: 'erp', numero_ordem: 17133, os_id: 942484,
    situacao_id: 677, cliente: 'Zz Cliente',
    criada_em: '2026-11-18T09:09:00-03:00',
    tipo_nome: 'Instalação', placas: [], tecnicos: [], observacoes: 0,
    anexos: 0, estado: null, formulario: null, prioridade: 382,
    prioridade_nome: 'Normal', status_str: 'Iniciada', finalizada: false,
    checklist: null, tem_checklist: false,
    passagem_pendente: false, pendente_desde: null,
    pendente_tentativas: null, pendente_erro: null, situacao_do_erp: null,
    etapa_desde: null, ...extra,
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
  estado.postado = []
  estado.respostaMover = { ok: true }
  estado.quadro = quadro({ 677: [card()] })
})

describe('o selo da pendência — o card andou e a OS não confirmou', () => {
  it('NÃO aparece quando não há pendência', async () => {
    const tela = await montar()
    expect(tela.find('.card__pendente').exists()).toBe(false)
  })

  it('aparece com ÍCONE E TEXTO quando a passagem está na fila', async () => {
    estado.quadro = quadro({ 677: [card({ passagem_pendente: true })] })
    const tela = await montar()
    const selo = tela.find('.card__pendente')
    expect(selo.exists()).toBe(true)
    /* 🚨 Texto, não só cor: cor e opacidade não são portadoras de informação. */
    expect(selo.text()).toContain('ainda não foi para a OS')
    expect(selo.find('i.bi-hourglass-split').exists()).toBe(true)
  })

  it('NÃO usa a classe `.pilula`', async () => {
    /* 🚨 A armadilha de 05–11/11: `.pilula` é `scoped` por componente e não
       existe em `estilo/*.css`. O selo nasceria sem estilo e nenhum teste
       pegaria, porque o jsdom não faz layout. */
    estado.quadro = quadro({ 677: [card({ passagem_pendente: true })] })
    const tela = await montar()
    expect(tela.find('.card__pendente').classes()).not.toContain('pilula')
  })

  it('conta a tentativa quando há mais de uma', async () => {
    estado.quadro = quadro({
      677: [card({ passagem_pendente: true, pendente_tentativas: 3 })],
    })
    const tela = await montar()
    expect(tela.find('.card__pendente').text()).toContain('3ª tentativa')
  })

  it('o `title` diz O MOTIVO POR EXTENSO e onde o ERP está', async () => {
    /* 🔵 Pendência 4 dele: *"os motivos de recusa deve aparecer descritos ao
       inves de erro generico, para que me tragam o problema ja cientes"*. */
    estado.quadro = quadro({
      677: [card({
        passagem_pendente: true, situacao_do_erp: 16488,
        pendente_erro: 'O Harmonit está sobrecarregado e não respondeu.',
      })],
    })
    const tela = await montar()
    const titulo = tela.find('.card__pendente').attributes('title')
    expect(titulo).toContain('ainda não confirmou')
    expect(titulo).toContain('16488')
    expect(titulo).toContain('sobrecarregado')
  })
})

describe('a trava de 1 minuto', () => {
  it('NÃO trava um card movido há muito tempo', async () => {
    estado.quadro = quadro({
      677: [card({ etapa_desde: '2026-11-18T09:00:00-03:00' })],
    })
    const tela = await montar()
    expect(tela.find('.card__assentando').exists()).toBe(false)
    expect(tela.find('.card').attributes('draggable')).toBe('true')
  })

  it('card movido AGORA mostra a contagem e NÃO arrasta', async () => {
    estado.quadro = quadro({
      677: [card({ etapa_desde: new Date().toISOString() })],
    })
    const tela = await montar()
    const selo = tela.find('.card__assentando')
    expect(selo.exists()).toBe(true)
    /* 🚨 A razão fica ESCRITA, com a contagem: card que para de arrastar sem
       dizer nada faz o operador clicar mais. */
    expect(selo.text()).toContain('acabou de ser movido')
    expect(selo.text()).toMatch(/espere \d+s/)
    /* ⚠️ A guarda de verdade está no servidor; isto é a explicação. */
    expect(tela.find('.card').attributes('draggable')).toBe('false')
  })

  it('card SEM passagem nenhuma não trava', async () => {
    /* ⚠️ `etapa_desde` nulo quer dizer "nunca movida por aqui" — a
       `os_passagem` começou em 29/10, e OS antiga não tem de onde tirar isso. */
    const tela = await montar()
    expect(tela.find('.card__assentando').exists()).toBe(false)
  })
})

describe('mover que entra na fila', () => {
  it('mostra AVISO, não erro, e o card fica onde o operador pôs', async () => {
    /* 🚨 Não é erro: o operador fez a coisa certa e a fila insiste sozinha.
       Chamar de erro faria ele tentar de novo -- o *"só cansa a req"* dele. */
    estado.respostaMover = {
      ok: true, gravou: false, pendente: true, causa: 'leitura_atrasada',
      motivo: 'o Harmonit ainda está respondendo a situação anterior',
    }
    estado.quadro = quadro({ 38: [card({ situacao_id: 38 })] })
    const tela = await montar()
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    const select = tela.findAll('select').find(
      (s) => s.text().includes('Enviar por correio'))
    await select.setValue('677')
    await flushPromises()
    await flushPromises()
    expect(tela.find('.aviso--pendente').exists()).toBe(true)
    expect(tela.find('.aviso--pendente').text()).toContain('Harmonit')
    /* 🚨 E NÃO entra no aviso de erro. */
    expect(tela.find('.aviso--erro').exists()).toBe(false)
  })

  it('recusa de verdade continua sendo ERRO', async () => {
    /* ⚠️ Valor que nunca escrevemos = alguém mexeu na OS no Harmonit, e o ERP
       é quem está certo. Isso recusa, como sempre. */
    estado.respostaMover = {
      ok: false, conflito: true, causa: 'conflito_de_situacao',
      motivo: 'a OS esta em Analise de Equipamentos Retornados no Harmonit',
    }
    estado.quadro = quadro({ 38: [card({ situacao_id: 38 })] })
    const tela = await montar()
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
    const select = tela.findAll('select').find(
      (s) => s.text().includes('Enviar por correio'))
    await select.setValue('677')
    await flushPromises()
    await flushPromises()
    expect(tela.find('.aviso--erro').exists()).toBe(true)
    expect(tela.find('.aviso--pendente').exists()).toBe(false)
  })
})
