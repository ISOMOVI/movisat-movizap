/**
 * @vitest-environment jsdom
 *
 * O modal Agendar e a tela Agendamentos — 21/10.
 *
 * 🚨 SUÍTE VERDE NÃO PROVA TELA (`M9`). O que estes testes provam é o que um
 * teste consegue provar: que as telas MONTAM, que a aba que abre depende do
 * tipo do contato, que a regra de agrupamento das mensagens é a que ele
 * declarou, e que ausência não é desenhada como vazio.
 *
 * O que se protege:
 *  · conversa de TÉCNICO vê Orçamento e Agendar; de CLIENTE vê Confirmar;
 *  · 🚨 conversa sem contato NÃO esconde o botão -- ela explica por quê;
 *  · mesma data e hora => UMA mensagem só, com placas e OS somadas;
 *  · OS sem oficina aparece como "sem placa registrada", nunca em branco;
 *  · OS já presa a outro compromisso vem marcada e não deixa escolher;
 *  · a tela de Agendamentos diz a COBERTURA dela.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const estado = vi.hoisted(() => ({ respostas: {}, posts: [] }))

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      const chave = Object.keys(estado.respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? estado.respostas[chave] : {})
    },
    post: (rota, corpo) => {
      estado.posts.push({ rota, corpo })
      return Promise.resolve(estado.respostas[rota] || { ok: true })
    },
    put: () => Promise.resolve({}),
    del: () => Promise.resolve({}),
  },
  definirToken: () => {},
  temToken: () => true,
  quandoPerderSessao: () => {},
  ErroDeApi: class ErroDeApi extends Error {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, params: {}, meta: {} }),
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
}))

import ModalAgendar from './componentes/ModalAgendar.vue'
import Agendamentos from './telas/Agendamentos.vue'

const CATALOGO = {
  catalogo: [
    { servico: 'KM DESLOCAMENTO', harmonit_id: 6971, unidade: 'km' },
    { servico: 'PAGAMENTO DE TECNICO', harmonit_id: 653939, unidade: 'un' },
  ],
  proximo_numero: 1668,
}

const CLIENTES = {
  clientes: [
    { harmonit_id: '998063', nome: 'VELASCO LEITE PASTELARIA ME',
      sem_cadastro: false, quantas_os: 17 },
    { harmonit_id: '50665', nome: 'OUTRA EMPRESA', sem_cadastro: false,
      quantas_os: 71 },
  ],
}

const OS_DO_CLIENTE = {
  os: [
    { numero_os: 16548, tipo: 2, status_str: 'Nova', sem_situacao: false,
      veiculos: [{ placa: 'FZU5D16', veiculo: 'FIORINO' }] },
    // ⚠️ Sem oficina: 336 das 572 OS da base estão assim.
    { numero_os: 16547, tipo: 2, status_str: null, sem_situacao: true, veiculos: [] },
    { numero_os: 16546, tipo: 2, status_str: 'Nova', sem_situacao: false, veiculos: [] },
  ],
  ja_agendadas: [16546],
}

function montarModal(props = {}) {
  return mount(ModalAgendar, {
    props: {
      conversaId: 1, relacao: 'tecnico', contatoNome: 'Franck Salustiano',
      clienteHarmonitId: '', clienteNome: '', ...props,
    },
  })
}

beforeEach(() => {
  estado.posts = []
  estado.respostas = {
    '/api/orcamento/catalogo': CATALOGO,
    '/api/agendamento/clientes/998063/os': OS_DO_CLIENTE,
    '/api/agendamento/clientes': CLIENTES,
    '/api/agendamento/endereco-sugerido': { endereco: 'Rua Antiga, 1' },
    '/api/agendamento/aguardando': { agendamentos: [] },
    '/api/agendamentos': { agendamentos: [] },
  }
})

describe('qual aba abre', () => {
  it('técnico vê Orçamento e Agendar', async () => {
    const tela = montarModal()
    await flushPromises()
    expect(tela.findAll('.agm__aba').map((n) => n.text()))
      .toEqual(['Orçamento', 'Agendar'])
  })

  it('cliente vê só Confirmar', async () => {
    const tela = montarModal({ relacao: 'cliente', clienteHarmonitId: '998063' })
    await flushPromises()
    expect(tela.findAll('.agm__aba').map((n) => n.text())).toEqual(['Confirmar'])
  })

  it('🚨 sem contato o modal EXPLICA, em vez de sumir', async () => {
    const tela = montarModal({ relacao: '' })
    await flushPromises()
    expect(tela.findAll('.agm__aba')).toHaveLength(0)
    expect(tela.text()).toContain('Marque o tipo do contato')
  })
})

describe('aba Orçamento', () => {
  it('traz o catálogo fechado e o próximo número', async () => {
    const tela = montarModal()
    await flushPromises()
    const opcoes = tela.findAll('option').map((n) => n.text())
    expect(opcoes).toEqual(['KM DESLOCAMENTO', 'PAGAMENTO DE TECNICO'])
    expect(tela.text()).toContain('1668')
  })

  it('a unidade acompanha o serviço escolhido (km no deslocamento)', async () => {
    const tela = montarModal()
    await flushPromises()
    expect(tela.find('tbody tr').text()).toContain('km')
  })

  it('não emite com linha incompleta', async () => {
    const tela = montarModal()
    await flushPromises()
    const botao = tela.findAll('button').find((b) => b.text().includes('Gerar e anexar'))
    expect(botao.attributes('disabled')).toBeDefined()
  })
})

describe('🚨 emitido e NÃO enviado é um terceiro caso', () => {
  async function emitir(resposta) {
    estado.respostas['/api/conversas/1/orcamento'] = resposta
    const tela = montarModal()
    await flushPromises()
    await tela.findAll('tbody input')[0].setValue('1,00')
    await tela.findAll('tbody input')[1].setValue('77,7')
    await tela.findAll('button').find((b) => b.text().includes('Gerar e anexar'))
      .trigger('click')
    await flushPromises()
    return tela
  }

  it('diz o nome do CADASTRO DO HARMONIT que saiu no documento', async () => {
    const tela = await emitir({
      id: 9, numero: 1668, total_centavos: 7770, enviado: { ok: true },
      tecnico_nome: 'Franck',
      tecnico_do_harmonit: { achado: true, nome: 'Franck' } })
    expect(tela.text()).toContain('Saiu em nome de')
    expect(tela.text()).toContain('cadastro do Harmonit')
  })

  it('avisa quando NÃO achou o técnico no cadastro e usou o nome daqui', async () => {
    const tela = await emitir({
      id: 9, numero: 1668, total_centavos: 7770, enviado: { ok: true },
      tecnico_nome: 'Franck | Campinas - SP',
      tecnico_do_harmonit: { achado: false, motivo: 'nenhum tecnico' } })
    expect(tela.text()).toContain('Não achei este técnico no cadastro')
    expect(tela.text()).toContain('Franck | Campinas - SP')
  })

  it('envio ok diz que o PDF foi para a conversa', async () => {
    const tela = await emitir({ id: 9, numero: 1668, total_centavos: 7770,
                                enviado: { ok: true } })
    expect(tela.text()).toContain('O PDF foi para')
    expect(tela.text()).not.toContain('Reenviar o PDF')
  })

  it('envio falho diz que o número JÁ FOI USADO e oferece reenviar', async () => {
    const tela = await emitir({
      id: 9, numero: 1668, total_centavos: 7770,
      enviado: { ok: false, motivo: 'o WhatsApp recusou' } })
    expect(tela.text()).toContain('o PDF não chegou à conversa')
    expect(tela.text()).toContain('o WhatsApp recusou')
    expect(tela.text()).toContain('reenvie este mesmo documento')
    expect(tela.findAll('button').some((b) => b.text().includes('Reenviar o PDF')))
      .toBe(true)
  })

  it('reenviar não emite outro: chama a rota do mesmo orçamento', async () => {
    const tela = await emitir({
      id: 9, numero: 1668, total_centavos: 7770,
      enviado: { ok: false, motivo: 'caiu' } })
    estado.respostas['/api/conversas/1/orcamento/9/reenviar'] = {
      numero: 1668, enviado: { ok: true } }
    await tela.findAll('button').find((b) => b.text().includes('Reenviar o PDF'))
      .trigger('click')
    await flushPromises()
    expect(estado.posts.map((p) => p.rota))
      .toContain('/api/conversas/1/orcamento/9/reenviar')
    expect(tela.text()).toContain('O PDF foi para')
  })
})

describe('aba Agendar', () => {
  it('não avança do passo 1 sem data e hora', async () => {
    const tela = montarModal()
    await flushPromises()
    await tela.findAll('.agm__aba')[1].trigger('click')
    const continuar = tela.findAll('button').find((b) => b.text() === 'Continuar')
    expect(continuar.attributes('disabled')).toBeDefined()
  })

  it('lista os clientes com OS em aberto', async () => {
    const tela = montarModal()
    await flushPromises()
    await tela.findAll('.agm__aba')[1].trigger('click')
    await tela.find('input[type="datetime-local"]').setValue('2026-10-23T09:00')
    await tela.findAll('button').find((b) => b.text() === 'Continuar').trigger('click')
    expect(tela.text()).toContain('VELASCO LEITE PASTELARIA ME')
    expect(tela.text()).toContain('OS em aberto nos últimos 6 meses')
  })

  it('OS sem oficina diz "sem placa registrada", e a já agendada não deixa escolher',
     async () => {
    const tela = montarModal()
    await flushPromises()
    await tela.findAll('.agm__aba')[1].trigger('click')
    await tela.find('input[type="datetime-local"]').setValue('2026-10-23T09:00')
    await tela.findAll('button').find((b) => b.text() === 'Continuar').trigger('click')
    await tela.findAll('.agm__item')[0].trigger('click') // escolhe a Velasco
    await flushPromises()
    expect(tela.text()).toContain('sem placa registrada')
    expect(tela.text()).toContain('sem situação')
    const presa = tela.findAll('.agm__item').find((b) => b.text().includes('16546'))
    expect(presa.attributes('disabled')).toBeDefined()
    expect(presa.text()).toContain('já agendada')
  })
})

describe('as duas confirmações', () => {
  const UM = {
    id: 1, cliente_nome: 'VELASCO', inicio: '2026-10-23T09:00:00-03:00',
    endereco: 'Rua Um, 100', tecnico_nome: 'Franck', orcamento_numero: 1668,
    responsavel_cliente: 'Dona Maria',
    ordens: [{ numero_os: 16548, placa: 'FZU5D16' }],
  }
  const OUTRO_MESMA_HORA = {
    ...UM, id: 2, ordens: [{ numero_os: 16547, placa: 'ABC1D23' }],
  }
  const OUTRA_HORA = {
    ...UM, id: 3, inicio: '2026-10-23T14:00:00-03:00',
    ordens: [{ numero_os: 16540, placa: 'XYZ9W87' }],
  }

  async function confirmar(lista) {
    estado.respostas['/api/agendamento/aguardando'] = { agendamentos: lista }
    for (const a of lista) estado.respostas[`/api/agendamentos/${a.id}/confirmar`] = a
    const tela = montarModal({ relacao: 'cliente', clienteHarmonitId: '998063' })
    await flushPromises()
    for (const item of tela.findAll('.agm__item')) await item.trigger('click')
    await tela.find('.agm__campo input').setValue('Dona Maria')
    await tela.findAll('button').find((b) => b.text().includes('Confirmar e escrever'))
      .trigger('click')
    await flushPromises()
    return tela
  }

  it('🚨 mesma data e hora => UMA mensagem só, com placas e OS somadas', async () => {
    const tela = await confirmar([UM, OUTRO_MESMA_HORA])
    expect(tela.findAll('.agm__mensagem')).toHaveLength(1)
    const texto = tela.find('.agm__mensagem').text()
    expect(texto).toContain('FZU5D16, ABC1D23')
    expect(texto).toContain('16548, 16547')
  })

  it('horas diferentes => mensagens separadas', async () => {
    const tela = await confirmar([UM, OUTRA_HORA])
    expect(tela.findAll('.agm__mensagem')).toHaveLength(2)
  })

  it('a do técnico leva OS e orçamento; a do cliente, não', async () => {
    const tela = await confirmar([UM])
    const blocos = tela.findAll('.agm__mensagem pre').map((n) => n.text())
    expect(blocos[0]).not.toContain('ORÇAMENTO')
    expect(blocos[1]).toContain('OS: 16548')
    expect(blocos[1]).toContain('ORÇAMENTO 1668')
    // O campo que ele exigiu nas duas.
    expect(blocos[0]).toContain('RESPONSÁVEL DO CLIENTE POR ACOMPANHAR O TÉCNICO: Dona Maria')
  })

  it('não confirma sem dizer quem acompanha o técnico', async () => {
    estado.respostas['/api/agendamento/aguardando'] = { agendamentos: [UM] }
    const tela = montarModal({ relacao: 'cliente', clienteHarmonitId: '998063' })
    await flushPromises()
    await tela.find('.agm__item').trigger('click')
    await tela.findAll('button').find((b) => b.text().includes('Confirmar e escrever'))
      .trigger('click')
    await flushPromises()
    expect(tela.text()).toContain('quem acompanha o técnico')
    expect(estado.posts.filter((p) => p.rota.includes('confirmar'))).toHaveLength(0)
  })

  it('o atendente é quem envia: o modal só escreve no compositor', async () => {
    const tela = await confirmar([UM])
    await tela.findAll('button').find((b) => b.text() === 'Escrever no compositor')
      .trigger('click')
    expect(tela.emitted('inserir')).toBeTruthy()
    expect(tela.emitted('inserir')[0][0]).toContain('DATA:')
    expect(tela.emitted('fechar')).toBeTruthy()
  })
})

describe('tela ATD_7.1 Agendamentos', () => {
  it('monta e diz a cobertura dela', async () => {
    const tela = mount(Agendamentos)
    await flushPromises()
    expect(tela.text()).toContain('agendado por este painel')
    expect(tela.text()).toContain('Nenhum serviço agendado por este painel neste dia')
  })

  it('o carrossel mostra ontem, hoje e os 5 próximos', async () => {
    const tela = mount(Agendamentos)
    await flushPromises()
    expect(tela.findAll('.agd__dia')).toHaveLength(7)
    expect(tela.findAll('.agd__dia--hoje')).toHaveLength(1)
  })

  it('a linha traz placa, OS e estado — e "sem placa registrada" quando não há',
     async () => {
    const hoje = new Date()
    const iso = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}-${String(hoje.getDate()).padStart(2, '0')}`
    estado.respostas['/api/agendamentos'] = {
      agendamentos: [
        { id: 1, inicio: `${iso}T09:00:00`, cliente_nome: 'VELASCO',
          tecnico_nome: 'Franck', endereco: 'Rua Um', responsavel_cliente: 'Maria',
          orcamento_numero: 1668, estado: 'confirmado',
          ordens: [{ numero_os: 16548, placa: null }] },
      ],
    }
    const tela = mount(Agendamentos)
    await flushPromises()
    const linha = tela.find('tbody tr').text()
    expect(linha).toContain('16548')
    expect(linha).toContain('sem placa registrada')
    expect(linha).toContain('Confirmado')
  })
})
