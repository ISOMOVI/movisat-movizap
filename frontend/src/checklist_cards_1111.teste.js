/*
 * @vitest-environment jsdom
 *
 * CFG_17.1 — CHECKLIST DE CARDS, a tela (11/11).
 *
 * 🔵 Sugestão minha que ele aceitou: *"boa sugestão, pode fazer uma outra aba só
 * para isso de 'Checklist de Cards' vamos centralizar os fixos ali"*.
 *
 * 🚨 ESTA TELA NASCEU PARA ROTAS QUE JÁ ESTAVAM NO AR SEM PORTA. As de modelo do
 * checklist existem desde 04/11 e ninguém nunca pôde usá-las. Toda trava aqui
 * prende um lugar onde a tela poderia prometer mais do que a regra permite.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = { etapas: [], postado: [], posto: [], erroDoGet: null }

vi.mock('../src/api/cliente.js', () => ({}))
vi.mock('./api/cliente.js', () => ({
  api: {
    get: async () => {
      if (estado.erroDoGet) throw estado.erroDoGet
      return { etapas: estado.etapas }
    },
    post: async (caminho, corpo) => {
      estado.postado.push([String(caminho), corpo])
      return { id: 500 }
    },
    put: async (caminho, corpo) => {
      estado.posto.push([String(caminho), corpo])
      return { id: 1 }
    },
    del: async () => ({}),
  },
  ErroDeApi: class extends Error {},
}))

import ChecklistDeCards from './telas/ChecklistDeCards.vue'

/* O retrato do que a rota devolve: as 17, inclusive as VAZIAS. */
function etapas() {
  return [
    { situacao_id: 251, nome: 'Configurar equipamentos e Sistemas',
      itens: [
        { id: 1, situacao_id: 251, texto: 'Informação do contrato', ordem: 1,
          ativo: true },
        { id: 2, situacao_id: 251, texto: 'Item fora de uso', ordem: 2,
          ativo: false },
      ] },
    { situacao_id: 890, nome: 'Agendar serviço', itens: [] },
  ]
}

async function montar() {
  const tela = mount(ChecklistDeCards)
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
  estado.etapas = etapas()
  estado.postado = []
  estado.posto = []
  estado.erroDoGet = null
})

describe('a lista das etapas', () => {
  it('🔵 mostra TODAS as etapas, inclusive a vazia', async () => {
    /* 🚨 Sem a vazia na tela, não há onde acrescentar — e são as vazias que ele
       precisa preencher. */
    const tela = await montar()
    const portas = tela.findAll('.etapa__porta')
    expect(portas.length).toBe(2)
    expect(tela.text()).toContain('Agendar serviço')
  })

  it('conta só os itens ATIVOS no selo', async () => {
    const tela = await montar()
    const porta = tela.findAll('.etapa__porta')
      .find((b) => b.text().includes('Configurar'))
    /* 2 itens, 1 ativo. */
    expect(porta.text()).toContain('1 item')
  })

  it('⚠️ a etapa vazia DIZ o que a falta de lista causa', async () => {
    const tela = await abrir(await montar(), 'Agendar serviço')
    expect(tela.text()).toContain('não tem lista')
  })

  it('🚨 o item desativado APARECE, marcado', async () => {
    /* Ele continua no card de quem já o tinha, então esconder aqui faria a
       tela mentir sobre o que existe. */
    const tela = await abrir(await montar(), 'Configurar')
    /* ⚠️ O TEXTO DO ITEM MORA NO VALOR DO INPUT, não em nó de texto -- e minha
       primeira versão desta trava media `tela.text()` e reprovava sozinha.
       É o mesmo erro de ler a tela inteira procurando o que está num atributo. */
    const valores = tela.findAll('.item .campo__entrada')
      .map((c) => c.element.value)
    expect(valores).toContain('Item fora de uso')
    expect(tela.findAll('.item--inativo').length).toBe(1)
    expect(tela.text()).toContain('segue nos cards que já o tinham')
  })

  it('⚠️ a ação se chama "Desativar" por extenso, e nunca ✕', async () => {
    /* Um ✕ pareceria apagar, e apagar é o que esta tela não faz. */
    const tela = await abrir(await montar(), 'Configurar')
    const rotulos = tela.findAll('.item .botao').map((b) => b.text())
    expect(rotulos).toContain('Desativar')
    expect(rotulos).toContain('Reativar')
    expect(rotulos.join(' ')).not.toContain('✕')
  })
})

describe('acrescentar', () => {
  it('posta na rota certa, com a etapa e a ordem do FIM', async () => {
    const tela = await abrir(await montar(), 'Configurar')
    await tela.find('.etapa__novo .campo__entrada').setValue('Detalhes dos itens')
    await tela.findAll('.etapa__novo .botao')
      .find((b) => b.text() === 'Acrescentar').trigger('click')
    await flushPromises()
    expect(estado.postado.length).toBe(1)
    const [caminho, corpo] = estado.postado[0]
    expect(caminho).toBe('/api/paineis/operacao/checklist/modelo')
    expect(corpo.situacao_id).toBe(251)
    expect(corpo.texto).toBe('Detalhes dos itens')
    /* 1 ativo -> o novo é o 2º: quem acrescenta quer no fim, não no meio. */
    expect(corpo.ordem).toBe(2)
  })

  it('⚠️ campo vazio não posta, e espaço só também não', async () => {
    const tela = await abrir(await montar(), 'Agendar serviço')
    const botao = tela.findAll('.etapa__novo .botao')
      .find((b) => b.text() === 'Acrescentar')
    expect(botao.attributes('disabled')).toBeDefined()
    await tela.find('.etapa__novo .campo__entrada').setValue('   ')
    expect(botao.attributes('disabled')).toBeDefined()
    expect(estado.postado).toEqual([])
  })

  it('🚨 cada etapa tem o SEU campo — o texto não vaza para a outra', async () => {
    /* Com um campo compartilhado, escrever e trocar de etapa levaria o texto
       para a etapa errada. */
    const tela = await montar()
    await abrir(tela, 'Configurar')
    await tela.find('.etapa__novo .campo__entrada').setValue('da 251')
    await abrir(tela, 'Agendar serviço')
    expect(tela.find('.etapa__novo .campo__entrada').element.value).toBe('')
  })
})

describe('desativar e renomear', () => {
  it('desativar manda ativo=false, mantendo texto e ordem', async () => {
    const tela = await abrir(await montar(), 'Configurar')
    await tela.findAll('.item .botao')
      .find((b) => b.text() === 'Desativar').trigger('click')
    await flushPromises()
    const [caminho, corpo] = estado.posto[0]
    expect(caminho).toBe('/api/paineis/operacao/checklist/modelo/1')
    expect(corpo).toEqual({ situacao_id: 251,
                            texto: 'Informação do contrato',
                            ordem: 1, ativo: false })
  })

  it('reativar manda ativo=true', async () => {
    const tela = await abrir(await montar(), 'Configurar')
    await tela.findAll('.item .botao')
      .find((b) => b.text() === 'Reativar').trigger('click')
    await flushPromises()
    expect(estado.posto[0][1].ativo).toBe(true)
  })

  it('renomear manda o texto novo', async () => {
    const tela = await abrir(await montar(), 'Configurar')
    const campo = tela.findAll('.item .campo__entrada')[0]
    await campo.setValue('Informação do contrato sobre os equipamentos')
    await campo.trigger('change')
    await flushPromises()
    expect(estado.posto[0][1].texto)
      .toBe('Informação do contrato sobre os equipamentos')
  })

  it('⚠️ o campo do item DESATIVADO não aceita digitação', async () => {
    /* Reescrever item fora de uso mudaria o texto no card de quem o tem, sem
       que ele volte para a lista. */
    const tela = await abrir(await montar(), 'Configurar')
    const campos = tela.findAll('.item .campo__entrada')
    expect(campos[1].attributes('disabled')).toBeDefined()
  })

  it('renomear para o MESMO texto não posta nada', async () => {
    const tela = await abrir(await montar(), 'Configurar')
    const campo = tela.findAll('.item .campo__entrada')[0]
    await campo.trigger('change')
    await flushPromises()
    expect(estado.posto).toEqual([])
  })
})

describe('a tela não mente', () => {
  it('🚨 diz que a mudança vale para os PRÓXIMOS cards', async () => {
    /* É o que todo mundo supõe errado: o item do card é CÓPIA do modelo. */
    const tela = await montar()
    expect(tela.text()).toContain('vale para os próximos cards')
  })

  it('⚠️ e NÃO leva parágrafo explicativo', async () => {
    /* 🔵 Ele já tirou texto didático de tela três vezes -- *"atrapalha o
       profissionalismo"*. A régua é: a tela diz o ESTADO. */
    const tela = await montar()
    const notas = tela.findAll('.checklist__topo .nota')
    expect(notas.length).toBe(1)
    expect(notas[0].text().length).toBeLessThan(80)
  })

  it('erro de leitura aparece como alerta, não como lista vazia', async () => {
    estado.erroDoGet = new Error('caiu')
    const tela = await montar()
    expect(tela.find('[role="alert"]').exists()).toBe(true)
    expect(tela.findAll('.etapa__porta').length).toBe(0)
  })
})
