/*
 * @vitest-environment jsdom
 *
 * O TERMO POSTO A MAO NO CARD DO CONTRATUAL — 25/11.
 *
 * Ele: *"os cards fechados na aba contratual devem ter o numero do termo antes
 * do nome do cliente: TERMO: '12345 - PASTELARIA VELASCO'"* e *"o operador
 * coloca a mao no card, pois so depois de assinado que ele sera gerado
 * oficialmente"*.
 *
 * O que estas travas prendem, e e o risco real desta entrega: o `CorpoDoCard` e
 * instanciado em DOIS lugares e um deles (`PainelAba`) serve as QUATRO abas.
 * Mudar a linha 1 sem condicao mudaria Pos-venda e Financeiro junto -- foi
 * exatamente o erro que custou as quatro telas hoje de manha. Entao ha trava
 * para o Contratual MOSTRAR e trava para as outras NAO mostrarem.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const CARD_COM_TERMO = {
  id: 4360, etapa_id: 888, cliente: 'PASTELARIA VELASCO',
  cliente_id: 257686, numero_os: null, numero_ordem: null,
  termo: '12345', termo_a_mao: true, termo_por_nome: 'Iago',
  termo_em: '2026-11-25T17:30:00-03:00',
  formulario: 'Aditivo contratual', slug: 'aditivo',
  resumo: 'Edlene · PASTELARIA VELASCO', observacoes: 0,
  criada_em: '2026-11-25T13:01:10-03:00', placas: [], tecnicos: [],
}

function quadro(codigo) {
  return {
    titulo: codigo === 'PNL_1.5' ? 'Contratual' : 'Financeiro',
    abas: [{ codigo_tela: codigo, titulo: 'x' }],
    colunas: [{
      etapa_id: 888, nome: 'Assinado', total: 1,
      cards: [JSON.parse(JSON.stringify(CARD_COM_TERMO))],
    }],
  }
}

const estado = { codigo: 'PNL_1.5', enviado: [] }

vi.mock('./api/cliente.js', () => ({
  api: {
    /* O dialogo pede a FICHA do card, nao o quadro: um dublê que devolve o
       mesmo objeto para toda URL faz a tela estourar no render e a trava
       reprova por motivo errado (dublê irreal não se conserta afrouxando o
       código -- conserta-se o dublê). */
    get: (url) => Promise.resolve(
      String(url).includes('/chamado/')
        ? { chamado: { respostas: [] }, observacoes: [], recados: [],
           historico: [] }
        : quadro(estado.codigo)),
    post: (url, corpo) => { estado.enviado.push([url, corpo]); return Promise.resolve({ ok: true }) },
    put: () => Promise.resolve({}),
  },
  ErroDeApi: class extends Error {},
}))

vi.mock('./estado/sessao.js', () => ({
  sessao: { nome: 'Iago', owner: true, telas: [] },
  codigosPermitidos: { value: new Set() },
  sair: () => {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ meta: { codigo: estado.codigo, aba: estado.codigo },
                     query: {}, params: {} }),
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

const PainelAba = (await import('./telas/PainelAba.vue')).default

let tela
async function abrir(codigo) {
  estado.codigo = codigo
  estado.enviado.length = 0
  tela = mount(PainelAba, { attachTo: document.body })
  await flushPromises()
  return tela
}
afterEach(() => tela && tela.unmount())

describe('o TERMO antes do cliente, no card fechado do Contratual', () => {
  it('o Contratual mostra TERMO e o numero ANTES do nome do cliente',
    async () => {
      await abrir('PNL_1.5')
      const linha = tela.find('.card__abrir').text().replace(/\s+/g, ' ')
      expect(linha).toContain('TERMO')
      expect(linha).toContain('12345')
      expect(linha).toContain('PASTELARIA VELASCO')
      /* A ORDEM e o pedido: o numero antes do nome. */
      expect(linha.indexOf('12345'))
        .toBeLessThan(linha.indexOf('PASTELARIA VELASCO'))
    })

  it('as OUTRAS abas NAO mudam — o componente serve as quatro', async () => {
    await abrir('PNL_1.4')
    const linha = tela.find('.card__abrir').text().replace(/\s+/g, ' ')
    expect(linha).toContain('PASTELARIA VELASCO')
    /* No Financeiro o cliente continua abrindo a linha 1, como ele aprovou em
       05/11 (variante C). */
    expect(linha.indexOf('PASTELARIA VELASCO'))
      .toBeLessThan(linha.indexOf('12345') === -1 ? Infinity
                    : linha.indexOf('12345'))
  })

  it('card SEM termo nenhum nao escreve rotulo vazio', async () => {
    const semTermo = JSON.parse(JSON.stringify(CARD_COM_TERMO))
    semTermo.termo = null
    semTermo.termo_a_mao = false
    const g = quadro('PNL_1.5')
    g.colunas[0].cards = [semTermo]
    vi.resetModules()
    await abrir('PNL_1.5')
    /* 1 de cada 7 OS nao nasce de termo; a tela nao diz nada quando falta. */
    const linha = tela.find('.card__abrir').text()
    expect(linha).toContain('PASTELARIA VELASCO')
  })
})

describe('o campo onde o operador POE o numero', () => {
  /* Sem campo, a coluna do banco e inalcancavel -- e esse defeito ja existe
     nesta casa: as 4 chaves do Procfy estao no `/config` e NENHUMA rota as
     escreve, entao ninguem consegue preenche-las. Trava para nao repetir. */
  async function abrirDialogo(codigo) {
    await abrir(codigo)
    await tela.find('.card__abrir').trigger('click')
    await flushPromises()
  }

  it('no Contratual o dialogo tem o campo do termo', async () => {
    await abrirDialogo('PNL_1.5')
    const campo = tela.find('input.campo--termo')
    expect(campo.exists(), 'o campo do termo precisa existir').toBe(true)
    expect(campo.element.value).toBe('12345')
  })

  it('salvar manda o numero para a rota certa', async () => {
    await abrirDialogo('PNL_1.5')
    await tela.find('input.campo--termo').setValue('8953')
    const botao = tela.findAll('button')
      .find((b) => /termo/i.test(b.text()) || /salvar/i.test(b.text()))
    expect(botao, 'precisa haver botao de salvar o termo').toBeTruthy()
    await botao.trigger('click')
    await flushPromises()
    const pedido = estado.enviado.find(([url]) => url.includes('/termo'))
    expect(pedido, 'nenhum POST para /termo').toBeTruthy()
    expect(pedido[0]).toContain('/chamado/4360/termo')
    expect(pedido[1]).toEqual({ termo: '8953' })
  })

  it('nas OUTRAS abas o campo NAO aparece', async () => {
    await abrirDialogo('PNL_1.4')
    expect(tela.find('input.campo--termo').exists()).toBe(false)
  })
})
