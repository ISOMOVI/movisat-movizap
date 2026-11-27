/**
 * @vitest-environment jsdom
 *
 * O foco de coluna que vem da URL — `PNL_1.1`, 26/11.
 *
 * 🔵 Pedido dele na `ATD_7.1`: *"o botão no card do agendamento leva para a
 * coluna do clicado em outra aba, só isso, bem simples mesmo, já atende"*. E,
 * para quando a OS não está lá: *"pode aparecer caixa de diálogo, 'O card do
 * agendamento não está na coluna correta' e depois do 'OK' abrir com a coluna
 * que ele estiver em foco - ou até já com o filtro da OS"*.
 *
 * 🚨 O QUE ESTE ARQUIVO GUARDA ACIMA DE TUDO: que **sem query nada muda**.
 * Dez arquivos de teste pisam nesta tela e o arrasto dela escreve no ERP —
 * então o acréscimo tinha de ser inerte para quem abre o quadro pelo menu.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const estado = vi.hoisted(() => ({ quadro: null, query: {}, pedidos: [] }))

vi.mock('./api/cliente.js', () => ({
  api: {
    get: async (caminho) => {
      estado.pedidos.push(caminho)
      if (String(caminho).includes('/passagens')) return { passagens: [] }
      if (String(caminho).includes('/ficha')) return {}
      if (String(caminho).includes('/checklist')) return { itens: [] }
      if (String(caminho).includes('/observacoes')) return { observacoes: [] }
      return estado.quadro
    },
    post: async () => ({ ok: true }),
    del: async () => ({}),
    put: async () => ({}),
  },
  quandoPerderSessao: () => {},
  definirToken: () => {},
  temToken: () => false,
  relatarErroDeBotao: () => {},
  pedirBlob: async () => new Blob(),
  ErroDeApi: class extends Error {},
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  useRoute: () => ({ query: estado.query }),
}))

import PainelOperacao from './telas/PainelOperacao.vue'

const AGENDADO = 1316
const EXECUTADO = 1320

function quadro() {
  return {
    total: 3,
    pode_mover: false,
    colunas: [
      { chave: 'nova', titulo: 'Novo Solicitação 1ª', situacao_id: 38,
        total: 1, cards: [{ numero_ordem: 17100, situacao_id: 38 }] },
      { chave: 'agendado', titulo: 'Serviço Agendado', situacao_id: AGENDADO,
        total: 1, cards: [{ numero_ordem: 17133, situacao_id: AGENDADO }] },
      { chave: 'executado', titulo: 'Serviço Executado', situacao_id: EXECUTADO,
        total: 1, cards: [{ numero_ordem: 17140, situacao_id: EXECUTADO }] },
    ],
  }
}

async function montar() {
  const tela = mount(PainelOperacao)
  await flushPromises()
  await flushPromises()
  return tela
}

beforeEach(() => {
  estado.quadro = quadro()
  estado.query = {}
  estado.pedidos = []
})

describe('sem query — o quadro de todo dia', () => {
  it('🚨 nenhuma coluna apontada e nenhum diálogo', async () => {
    const tela = await montar()
    expect(tela.find('.coluna--apontada').exists()).toBe(false)
    expect(tela.text()).not.toContain('não está na coluna correta')
  })

  it('as três colunas continuam desenhadas e abertas', async () => {
    const tela = await montar()
    expect(tela.findAll('.coluna')).toHaveLength(3)
    expect(tela.findAll('.coluna--fechada')).toHaveLength(0)
  })
})

describe('?situacao= — a coluna em foco', () => {
  it('aponta a coluna pedida, e só ela', async () => {
    estado.query = { situacao: String(AGENDADO) }
    const tela = await montar()
    const apontadas = tela.findAll('.coluna--apontada')
    expect(apontadas).toHaveLength(1)
    expect(apontadas[0].text()).toContain('Serviço Agendado')
  })

  it('⚠️ toda coluna leva `data-situacao`, que é por onde a rolagem a acha',
     async () => {
    /* 🚨 A ROLAGEM LÊ O DOM, e não um `ref` por coluna: 17 colunas com `ref`
       seriam 17 referências para um gesto que acontece uma vez. Se este
       atributo sair do template, o foco para de funcionar **em silêncio** --
       a coluna abre, a classe entra, e a tela simplesmente não rola. */
    const tela = await montar()
    const atributos = tela.findAll('.coluna')
      .map((n) => n.attributes('data-situacao'))
    expect(atributos).toEqual(['38', String(AGENDADO), String(EXECUTADO)])
  })

  it('situação que não é coluna deste quadro DIZ, em vez de rolar para o vazio',
     async () => {
    estado.query = { situacao: '99999' }
    const tela = await montar()
    expect(tela.find('.coluna--apontada').exists()).toBe(false)
    expect(tela.text()).toContain('Não achei a coluna da situação 99999')
  })

  it('a OS que ESTÁ na coluna pedida não abre diálogo nenhum', async () => {
    estado.query = { situacao: String(AGENDADO), os: '17133' }
    const tela = await montar()
    expect(tela.find('.coluna--apontada').exists()).toBe(true)
    expect(tela.text()).not.toContain('não está na coluna correta')
  })
})

describe('a OS fora da coluna — o diálogo dele', () => {
  it('🔵 diz que não está na coluna correta E diz onde está', async () => {
    estado.query = { situacao: String(AGENDADO), os: '17140' }
    const tela = await montar()
    const texto = tela.text()
    expect(texto).toContain('não está na coluna correta')
    expect(texto).toContain('17140')
    expect(texto).toContain('Serviço Executado')
  })

  it('⚠️ e a coluna PEDIDA continua em foco enquanto o diálogo está aberto',
     async () => {
    estado.query = { situacao: String(AGENDADO), os: '17140' }
    const tela = await montar()
    expect(tela.find('.coluna--apontada').text()).toContain('Serviço Agendado')
  })

  it('🔵 no OK, foca a coluna onde ela ESTÁ e põe a OS na busca', async () => {
    estado.query = { situacao: String(AGENDADO), os: '17140' }
    const tela = await montar()
    await tela.findAll('button').find((b) => b.text() === 'Ok').trigger('click')
    await flushPromises()
    expect(tela.find('.coluna--apontada').text()).toContain('Serviço Executado')
    // A busca filtra o quadro, e é isso que faz o card saltar à vista.
    expect(estado.pedidos.some((p) => p.includes('busca=17140'))).toBe(true)
  })

  it('OS que não está em coluna NENHUMA é outro caso, com outra saída',
     async () => {
    estado.query = { situacao: String(AGENDADO), os: '16000' }
    const tela = await montar()
    expect(tela.text()).toContain('16000')
    expect(tela.text()).toContain('não está neste quadro')
    expect(tela.text()).toContain('só abertas')
  })

  it('🚨 "Mostrar também as fechadas" desliga o filtro e recarrega', async () => {
    estado.query = { situacao: String(AGENDADO), os: '16000' }
    const tela = await montar()
    await tela.findAll('button')
      .find((b) => b.text().includes('Mostrar também as fechadas'))
      .trigger('click')
    await flushPromises()
    expect(estado.pedidos.some((p) => p.includes('so_abertas=0'))).toBe(true)
  })

  it('várias OS: a que está fora é nomeada, e a que está lá não vira ruído',
     async () => {
    estado.query = { situacao: String(AGENDADO), os: '17133,17140' }
    const tela = await montar()
    const corpo = tela.find('.modal__corpo').text()
    expect(corpo).toContain('17140')
    expect(corpo).not.toContain('17133')
  })
})

describe('o foco age UMA vez só', () => {
  it('🚨 recarregar o quadro não puxa a rolagem de volta', async () => {
    /* O `carregar()` roda a cada filtro; refocar em cada um tiraria a tela da
       mão de quem opera no meio do trabalho. Aqui: depois do OK (que recarrega
       com busca), a coluna apontada é a do OK, e não a da URL outra vez. */
    estado.query = { situacao: String(AGENDADO), os: '17140' }
    const tela = await montar()
    await tela.findAll('button').find((b) => b.text() === 'Ok').trigger('click')
    await flushPromises()
    await flushPromises()
    expect(tela.find('.coluna--apontada').text()).toContain('Serviço Executado')
    expect(tela.text()).not.toContain('não está na coluna correta')
  })
})
