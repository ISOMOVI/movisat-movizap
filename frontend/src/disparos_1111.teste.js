/*
 * @vitest-environment jsdom
 *
 * CFG_16.1 — DISPAROS OPERAÇÃO, a tela (11/11).
 *
 * 🔵 Dele: *"Deixar o campo de menagens que são enviadas em cada etapa do fluxo
 * com interruptor de 'ligado e desligado'"* · *"nasce em branco e com
 * interruptor desligado ainda"* · *"por enquanto somente cliente deixe no painel
 * de disparos uma nota que nenhuma vai ao tecnico"*.
 *
 * 🚨 ESTA TELA É A ÚLTIMA CONFERÊNCIA ANTES DE O CLIENTE RECEBER. Com o
 * interruptor ligado, mover um card envia sem mais nada. Toda trava aqui prende
 * um lugar onde a tela poderia deixar alguém ligar sem saber o que vai sair.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = { resposta: null, posto: [], erroDoGet: null, erroDoPut: null }

vi.mock('../src/api/cliente.js', () => ({}))
vi.mock('./api/cliente.js', () => ({
  api: {
    get: async () => {
      if (estado.erroDoGet) throw estado.erroDoGet
      return estado.resposta
    },
    put: async (caminho, corpo) => {
      estado.posto.push([String(caminho), corpo])
      if (estado.erroDoPut) throw estado.erroDoPut
      return {}
    },
    post: async () => ({}),
    del: async () => ({}),
  },
  ErroDeApi: class extends Error {},
}))

import DisparosOperacao from './telas/DisparosOperacao.vue'

/* O retrato do que a rota devolve. */
function resposta(extra = {}) {
  return {
    canal: 'whatsapp',
    vai_para: 'cliente',
    teto: 2000,
    variaveis: [
      { chave: '{{Contato: Primeiro nome}}', o_que_e: 'primeiro nome' },
      { chave: '{{Nome}}', o_que_e: 'o número da OS' },
      { chave: '{{Código de envio/acompanhamento transporte}}',
        o_que_e: 'o código de rastreio' },
    ],
    etapas: [
      { situacao_id: 677, nome: 'Enviar por correio/transportadora',
        canal: 'whatsapp', texto: null, ativo: false,
        atualizado_por_nome: null },
      { situacao_id: 15747, nome: 'Aguardando recebimento via correio',
        canal: 'whatsapp', texto: 'Oi {{Contato: Primeiro nome}}, a OS {{Nome}} '
          + 'seguiu. Código: {{Código de envio/acompanhamento transporte}}',
        ativo: true, atualizado_por_nome: 'Iago' },
    ],
    ...extra,
  }
}

async function montar() {
  const tela = mount(DisparosOperacao)
  await flushPromises()
  return tela
}

async function abrir(tela, nome) {
  await tela.findAll('.etapa__porta')
    .find((b) => b.text().includes(nome)).trigger('click')
  await flushPromises()
  return tela
}

beforeEach(() => {
  estado.resposta = resposta()
  estado.posto = []
  estado.erroDoGet = null
  estado.erroDoPut = null
})

describe('o estado da tela', () => {
  it('🔵 diz quantas estão ligadas, o canal e para quem vai', async () => {
    const tela = await montar()
    const topo = tela.find('.disparos__topo').text()
    expect(topo).toContain('1 de 2')
    expect(topo).toContain('whatsapp')
    expect(topo).toContain('cliente')
  })

  it('🔵 traz a NOTA que ele pediu: nenhuma vai ao técnico', async () => {
    const tela = await montar()
    expect(tela.text()).toContain('Nenhuma destas mensagens vai ao técnico')
  })

  it('🚨 o selo diz "Ligado"/"Desligado" por extenso, não só cor', async () => {
    /* A diferença aqui é "fala com o cliente" ou "não fala" -- cor sozinha não
       carrega isso. */
    const tela = await montar()
    const selos = tela.findAll('.etapa__porta .pilula').map((s) => s.text())
    expect(selos).toContain('Ligado')
    expect(selos).toContain('Desligado')
  })

  it('⚠️ e NÃO leva parágrafo explicativo', async () => {
    const tela = await montar()
    expect(tela.findAll('.disparos__topo .nota').length).toBe(1)
  })
})

describe('o texto e o exemplo', () => {
  it('🚨 mostra o que o CLIENTE vai ler, com as variáveis resolvidas', async () => {
    /* Ler `{{Nome}}` não diz nada sobre o que o cliente vê -- é isto que faz da
       tela uma conferência de verdade, e é a única que existe antes do envio. */
    const tela = await abrir(await montar(), 'Aguardando recebimento')
    const exemplo = tela.find('.etapa__exemplo').text()
    expect(exemplo).toContain('João')
    expect(exemplo).toContain('17105')
    expect(exemplo).toContain('AA123456789BR')
    expect(exemplo).not.toContain('{{')
  })

  it('a etapa sem texto não mostra exemplo', async () => {
    const tela = await abrir(await montar(), 'Enviar por correio')
    expect(tela.find('.etapa__exemplo').exists()).toBe(false)
  })

  it('os botões de variável usam a GRAFIA DELE', async () => {
    /* 🚨 Variável escrita diferente não resolve e sai crua ao cliente. */
    const tela = await abrir(await montar(), 'Enviar por correio')
    const rotulos = tela.findAll('.etapa__variaveis .botao').map((b) => b.text())
    expect(rotulos).toContain('{{Contato: Primeiro nome}}')
    expect(rotulos).toContain('{{Nome}}')
    expect(rotulos).toContain('{{Código de envio/acompanhamento transporte}}')
  })

  it('clicar na variável a insere no texto', async () => {
    const tela = await abrir(await montar(), 'Enviar por correio')
    await tela.findAll('.etapa__variaveis .botao')
      .find((b) => b.text() === '{{Nome}}').trigger('click')
    await flushPromises()
    expect(tela.find('textarea').element.value).toContain('{{Nome}}')
  })
})

describe('salvar e ligar', () => {
  it('⚠️ Salvar texto só habilita quando o texto MUDOU', async () => {
    /* Gravar aqui é mexer no que o cliente vai receber: um `v-model` direto
       gravaria a cada tecla. */
    const tela = await abrir(await montar(), 'Aguardando recebimento')
    const botao = tela.findAll('.etapa__acoes .botao')
      .find((b) => b.text() === 'Salvar texto')
    expect(botao.attributes('disabled')).toBeDefined()
    await tela.find('textarea').setValue('texto novo')
    expect(botao.attributes('disabled')).toBeUndefined()
  })

  it('🚨 NÃO dá para LIGAR uma etapa sem texto', async () => {
    const tela = await abrir(await montar(), 'Enviar por correio')
    const botao = tela.findAll('.etapa__acoes .botao')
      .find((b) => b.text() === 'Ligar')
    expect(botao.attributes('disabled')).toBeDefined()
    expect(estado.posto).toEqual([])
  })

  it('com texto escrito, o Ligar libera e manda ativo=true', async () => {
    const tela = await abrir(await montar(), 'Enviar por correio')
    await tela.find('textarea').setValue('Seu item foi enviado.')
    const botao = tela.findAll('.etapa__acoes .botao')
      .find((b) => b.text() === 'Ligar')
    expect(botao.attributes('disabled')).toBeUndefined()
    await botao.trigger('click')
    await flushPromises()
    const [caminho, corpo] = estado.posto[0]
    expect(caminho).toBe('/api/config/disparos-operacao/677')
    expect(corpo).toEqual({ texto: 'Seu item foi enviado.', ativo: true })
  })

  it('a etapa LIGADA oferece Desligar, e manda ativo=false', async () => {
    const tela = await abrir(await montar(), 'Aguardando recebimento')
    await tela.findAll('.etapa__acoes .botao')
      .find((b) => b.text() === 'Desligar').trigger('click')
    await flushPromises()
    expect(estado.posto[0][1].ativo).toBe(false)
  })

  it('a recusa do servidor aparece como alerta', async () => {
    estado.erroDoPut = new Error('Escreva a mensagem antes de ligar')
    const tela = await abrir(await montar(), 'Aguardando recebimento')
    await tela.find('textarea').setValue('outro')
    await tela.findAll('.etapa__acoes .botao')
      .find((b) => b.text() === 'Salvar texto').trigger('click')
    await flushPromises()
    expect(tela.find('[role="alert"]').exists()).toBe(true)
  })

  it('erro de leitura não vira lista vazia', async () => {
    estado.erroDoGet = new Error('caiu')
    const tela = await montar()
    expect(tela.find('[role="alert"]').exists()).toBe(true)
    expect(tela.findAll('.etapa__porta').length).toBe(0)
  })
})
