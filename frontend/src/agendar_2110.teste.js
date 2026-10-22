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

const estado = vi.hoisted(() => ({ respostas: {}, posts: [], navegou: [],
                                   pedidos: [], erroNoPost: '' }))

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      // 🚨 Os GET ficam registrados: ha teste que prova que uma consulta NAO
      // sai (CEP curto nem deve chegar ao servidor).
      estado.pedidos.push(rota)
      const chave = Object.keys(estado.respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? estado.respostas[chave] : {})
    },
    post: (rota, corpo) => {
      estado.posts.push({ rota, corpo })
      // Para provar o caminho da recusa: sem isto, "envio falhou" nao tem como
      // ser exercitado, e e o estado que o atendente mais precisa entender.
      if (estado.erroNoPost && rota === estado.erroNoPost) {
        return Promise.reject(new Error('o WhatsApp recusou'))
      }
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
  // 🆕 21/10: a navegação é REGISTRADA. "Reenviar confirmação" oferece abrir a
  // conversa com o texto no compositor (ponta 2), e sem isto o teste não teria
  // como provar que ela foi aberta -- só que o clique não estourou.
  useRouter: () => ({
    push: (destino) => { estado.navegou.push(destino) },
    replace: (destino) => { estado.navegou.push(destino) },
  }),
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

/* 🚨 O TEXTO DAS MENSAGENS VIVE NO VALOR DO `textarea`, e nao no texto do
   DOM -- desde 21/10 elas sao editaveis no proprio modal (🔵 *"ao inves de
   editar na caixa de mensagem, pode editar ali no modal mesmo"*). `.text()`
   nao ve valor de campo, e por isso quatro testes passaram a ler daqui. */
function textoDaMensagem(tela, i = 0) {
  return tela.findAll('.agm__texto')[i].element.value
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
  estado.navegou = []
  estado.pedidos = []
  estado.erroNoPost = ''
  // O rascunho por conversa vive no `localStorage` (Bloco 7, 15/10), e a ponta
  // 2 escreve nele: teste que deixa lixo lá contamina o seguinte.
  try { localStorage.clear() } catch { /* sem storage */ }
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
    // O do cliente tem as placas; o do tecnico, as OS.
    expect(textoDaMensagem(tela, 0)).toContain('FZU5D16, ABC1D23')
    expect(textoDaMensagem(tela, 1)).toContain('16548, 16547')
  })

  it('horas diferentes => mensagens separadas', async () => {
    const tela = await confirmar([UM, OUTRA_HORA])
    expect(tela.findAll('.agm__mensagem')).toHaveLength(2)
  })

  it('a do técnico leva OS e orçamento; a do cliente, não', async () => {
    const tela = await confirmar([UM])
    const blocos = tela.findAll('.agm__texto').map((n) => n.element.value)
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

/* ==========================================================================
   AS TRÊS PONTAS DO PLANO QUE FALTAVAM — 21/10, tarde.
   --------------------------------------------------------------------------
   Ponta 1: o cabeçalho imprime o TIPO DA OS (era `(SERVIÇO)` literal), e
            OMITE o segmento quando o tipo não tem nome no Harmonit. 🚨 É a
            única das quatro que sai para o cliente.
   Ponta 2: "Reenviar confirmação", a quarta ação da linha da `ATD_7.1`.
            🚨 Não envia nada -- decisão 6 dele.
   Ponta 3: o mês navegável ao lado do carrossel.
   ========================================================================== */

describe('ponta 1 — o cabeçalho diz o TIPO DA OS', () => {
  const COM_TIPO = {
    id: 1, cliente_nome: 'VELASCO', inicio: '2026-10-23T09:00:00-03:00',
    endereco: 'Rua Um, 100', tecnico_nome: 'Franck', orcamento_numero: 1668,
    responsavel_cliente: 'Dona Maria',
    ordens: [{ numero_os: 16548, placa: 'FZU5D16', tipo_nome: 'Contrato' }],
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

  it('imprime o nome do tipo, e NÃO a palavra SERVIÇO', async () => {
    const tela = await confirmar([COM_TIPO])
    const texto = textoDaMensagem(tela)
    expect(texto).toContain('(CONTRATO) | FZU5D16 | VELASCO')
    expect(texto).not.toContain('SERVIÇO')
  })

  it('🚨 sem nome de tipo, o segmento SAI FORA — não vira número nem rótulo inventado',
     async () => {
    // 173 das 547 OS estão assim: `tipo` fora da lista do Harmonit.
    const tela = await confirmar([{
      ...COM_TIPO,
      ordens: [{ numero_os: 16548, placa: 'FZU5D16', tipo_nome: null }],
    }])
    const texto = textoDaMensagem(tela)
    expect(texto.split('\n')[0]).toBe('FZU5D16 | VELASCO')
    // ⚠️ O parêntese só pode faltar NO CABEÇALHO: o corpo tem sempre
    // `VEÍCULO(S) / PLACA(S)`, e medir o texto inteiro mediria a linha errada.
    expect(texto.split('\n')[0]).not.toContain('(')
    expect(texto).not.toContain('tipo 73')
  })

  it('grupo com tipos diferentes lista os dois, sem repetir', async () => {
    const tela = await confirmar([
      COM_TIPO,
      { ...COM_TIPO, id: 2,
        ordens: [{ numero_os: 16547, placa: 'ABC1D23', tipo_nome: 'Ordem de Serviço' },
                 { numero_os: 16545, placa: 'DEF2G34', tipo_nome: 'Contrato' }] },
    ])
    expect(tela.findAll('.agm__mensagem')).toHaveLength(1)
    expect(textoDaMensagem(tela)).toContain('(CONTRATO, ORDEM DE SERVIÇO)')
  })

  it('a OS escolhida leva o tipo GRAVADO para o compromisso (retrato)', async () => {
    estado.respostas['/api/agendamento/clientes/998063/os'] = {
      os: [{ numero_os: 16548, tipo: 2, tipo_nome: 'Contrato', status_str: 'Nova',
             sem_situacao: false, veiculos: [{ placa: 'FZU5D16' }] }],
      ja_agendadas: [],
    }
    const tela = montarModal()
    await flushPromises()
    await tela.findAll('.agm__aba')[1].trigger('click')
    await tela.find('input[type="datetime-local"]').setValue('2026-10-23T09:00')
    await tela.findAll('button').find((b) => b.text() === 'Continuar').trigger('click')
    await tela.findAll('.agm__item')[0].trigger('click')
    await flushPromises()
    // O tipo aparece na lista, para o operador ver antes de marcar o que o
    // cliente vai ler.
    expect(tela.text()).toContain('Contrato')
    // ⚠️ O PRIMEIRO clique escolheu o CLIENTE; a lista de OS substitui a de
    // clientes no mesmo `.agm__item`, então é o segundo que marca a OS.
    await tela.findAll('.agm__item')[0].trigger('click')
    await tela.findAll('button').find((b) => b.text() === 'Continuar').trigger('click')
    await flushPromises()
    // ⚠️ `Agendar` é também o rótulo da aba: a ação é a do passo 3, não a
    // primeira ocorrência no DOM.
    await tela.findAll('.botao--primario').find((b) => b.text() === 'Agendar')
      .trigger('click')
    await flushPromises()
    const post = estado.posts.find((p) => p.rota === '/api/agendamentos')
    expect(post.corpo.ordens[0]).toMatchObject({
      numero_os: 16548, placa: 'FZU5D16', tipo_nome: 'Contrato' })
  })

  it('OS sem nome de tipo diz isso na lista, em vez de calar', async () => {
    estado.respostas['/api/agendamento/clientes/998063/os'] = {
      os: [{ numero_os: 16451, tipo: 73, tipo_nome: null, status_str: 'Nova',
             sem_situacao: false, veiculos: [] }],
      ja_agendadas: [],
    }
    const tela = montarModal()
    await flushPromises()
    await tela.findAll('.agm__aba')[1].trigger('click')
    await tela.find('input[type="datetime-local"]').setValue('2026-10-23T09:00')
    await tela.findAll('button').find((b) => b.text() === 'Continuar').trigger('click')
    await tela.findAll('.agm__item')[0].trigger('click')
    await flushPromises()
    // 🔵 21/10: o tipo virou SELO (*"pode ter mais destaque"*), e o rotulo
    // do que nao tem nome acompanhou. Troca deliberada, nao regressao.
    expect(tela.text()).toContain('tipo sem nome no Harmonit')
  })
})

describe('ponta 2 — reenviar confirmação NÃO envia', () => {
  const hoje = new Date()
  const ISO_HOJE = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}-${String(hoje.getDate()).padStart(2, '0')}`

  function linha(extra = {}) {
    return {
      id: 1, inicio: `${ISO_HOJE}T09:00:00`, cliente_nome: 'VELASCO',
      cliente_harmonit_id: '998063', conversa_id: 77, tecnico_nome: 'Franck',
      endereco: 'Rua Um', responsavel_cliente: 'Dona Maria',
      orcamento_numero: 1668, estado: 'confirmado',
      ordens: [{ numero_os: 16548, placa: 'FZU5D16', tipo_nome: 'Contrato' }],
      ...extra,
    }
  }

  async function abrirReenvio(lista) {
    estado.respostas['/api/agendamentos'] = { agendamentos: lista }
    const tela = mount(Agendamentos)
    await flushPromises()
    await tela.findAll('button').find((b) => b.text() === 'Reenviar confirmação')
      .trigger('click')
    await flushPromises()
    return tela
  }

  it('mostra as duas mensagens e diz, por extenso, que não envia', async () => {
    const tela = await abrirReenvio([linha()])
    expect(tela.text()).toContain('não envia nada')
    const blocos = tela.findAll('.agd__reenvio-pre').map((n) => n.text())
    expect(blocos).toHaveLength(2)
    expect(blocos[0]).toContain('(CONTRATO) | FZU5D16 | VELASCO')
    expect(blocos[0]).not.toContain('ORÇAMENTO')
    expect(blocos[1]).toContain('OS: 16548')
    expect(blocos[1]).toContain('ORÇAMENTO 1668')
    // 🚨 Nenhum POST: a ação é de leitura.
    expect(estado.posts).toHaveLength(0)
  })

  it('🚨 junta os IRMÃOS da mesma hora — o cliente recebeu uma mensagem só',
     async () => {
    const tela = await abrirReenvio([
      linha(),
      linha({ id: 2, ordens: [{ numero_os: 16547, placa: 'ABC1D23', tipo_nome: 'Contrato' }] }),
      // Outra hora: fica de fora.
      linha({ id: 3, inicio: `${ISO_HOJE}T14:00:00`,
              ordens: [{ numero_os: 16540, placa: 'XYZ9W87', tipo_nome: 'Contrato' }] }),
      // Cancelado: fica de fora.
      linha({ id: 4, estado: 'cancelado',
              ordens: [{ numero_os: 16539, placa: 'QQQ1Q11', tipo_nome: 'Contrato' }] }),
    ])
    const doCliente = tela.findAll('.agd__reenvio-pre')[0].text()
    expect(doCliente).toContain('FZU5D16, ABC1D23')
    expect(doCliente).not.toContain('XYZ9W87')
    expect(doCliente).not.toContain('QQQ1Q11')
    expect(tela.text()).toContain('2 compromissos entraram numa mensagem só')
  })

  it('⚠️ compromisso aguardando sai com o campo vazio, e a tela diz por quê',
     async () => {
    const tela = await abrirReenvio([
      linha({ estado: 'aguardando', responsavel_cliente: null })])
    expect(tela.text()).toContain('ninguém disse quem acompanha o técnico')
    expect(tela.findAll('.agd__reenvio-pre')[0].text())
      .toContain('RESPONSÁVEL DO CLIENTE POR ACOMPANHAR O TÉCNICO:')
  })

  it('a ação não aparece em linha cancelada', async () => {
    estado.respostas['/api/agendamentos'] = {
      agendamentos: [linha({ estado: 'cancelado', motivo_cancelamento: 'cliente pediu' })] }
    const tela = mount(Agendamentos)
    await flushPromises()
    expect(tela.findAll('button').some((b) => b.text() === 'Reenviar confirmação'))
      .toBe(false)
  })

  it('abrir a conversa deixa o texto no rascunho DELA, e navega', async () => {
    const tela = await abrirReenvio([linha()])
    await tela.findAll('button')
      .find((b) => b.text() === 'Abrir conversa com este texto').trigger('click')
    await flushPromises()
    expect(localStorage.getItem('movizap.rascunho.77'))
      .toContain('(CONTRATO) | FZU5D16 | VELASCO')
    expect(estado.navegou).toContain('/atendimento/77')
  })

  it('⚠️ não sobrescreve rascunho do colega sem perguntar', async () => {
    localStorage.setItem('movizap.rascunho.77', 'meia frase do colega')
    const confirmou = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const tela = await abrirReenvio([linha()])
    await tela.findAll('button')
      .find((b) => b.text() === 'Abrir conversa com este texto').trigger('click')
    await flushPromises()
    expect(confirmou).toHaveBeenCalled()
    expect(localStorage.getItem('movizap.rascunho.77')).toBe('meia frase do colega')
    confirmou.mockRestore()
  })
})

describe('ponta 3 — o mês navegável ao lado', () => {
  it('nasce fechado e abre pelo botão Mês', async () => {
    const tela = mount(Agendamentos)
    await flushPromises()
    expect(tela.find('.agd__mes').exists()).toBe(false)
    await tela.findAll('button').find((b) => b.text().includes('Mês')).trigger('click')
    expect(tela.find('.agd__mes').exists()).toBe(true)
  })

  it('o mês tem os dias do mês e nenhum a mais', async () => {
    const tela = mount(Agendamentos)
    await flushPromises()
    await tela.findAll('button').find((b) => b.text().includes('Mês')).trigger('click')
    const agora = new Date()
    const quantos = new Date(agora.getFullYear(), agora.getMonth() + 1, 0).getDate()
    expect(tela.findAll('.agd__mes-dia')).toHaveLength(quantos)
  })

  it('🚨 o carrossel continua sendo o que manda: escolher um dia move a âncora',
     async () => {
    const tela = mount(Agendamentos)
    await flushPromises()
    await tela.findAll('button').find((b) => b.text().includes('Mês')).trigger('click')
    const dia = tela.findAll('.agd__mes-dia')[0]
    await dia.trigger('click')
    await flushPromises()
    // Fecha ao escolher, e o carrossel segue com os seus 7 dias.
    expect(tela.find('.agd__mes').exists()).toBe(false)
    expect(tela.findAll('.agd__dia')).toHaveLength(7)
    expect(tela.find('.agd__dia--ativo').exists()).toBe(true)
  })

  it('e diz onde estão as marcas de serviço, para o mês vazio não mentir',
     async () => {
    const tela = mount(Agendamentos)
    await flushPromises()
    await tela.findAll('button').find((b) => b.text().includes('Mês')).trigger('click')
    expect(tela.text()).toContain('As marcas de serviço ficam')
  })
})


/* ==========================================================================
   AS CINCO FRENTES DE 21/10, TARDE — depois do teste dele no navegador.
   --------------------------------------------------------------------------
   F1 (barreira do tecnico) vive na suite do FPSL: e regra de backend.
   Aqui ficam as quatro de tela.
   ========================================================================== */

describe('F3 — a trava do modal', () => {
  it('🚨 clicar fora NÃO fecha: pergunta primeiro', async () => {
    const perguntou = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const tela = montarModal()
    await flushPromises()
    await tela.find('.agm__fundo').trigger('click')
    expect(perguntou).toHaveBeenCalled()
    // Disse "não": o modal fica, e o trabalho não se perde.
    expect(tela.emitted('fechar')).toBeFalsy()
    perguntou.mockRestore()
  })

  it('confirmando, fecha', async () => {
    const perguntou = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const tela = montarModal()
    await flushPromises()
    await tela.find('.agm__fundo').trigger('click')
    expect(tela.emitted('fechar')).toBeTruthy()
    perguntou.mockRestore()
  })

  it('o X também pergunta — é o mesmo caminho de saída', async () => {
    const perguntou = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const tela = montarModal()
    await flushPromises()
    await tela.find('[aria-label="Fechar"]').trigger('click')
    expect(perguntou).toHaveBeenCalled()
    expect(tela.emitted('fechar')).toBeFalsy()
    perguntou.mockRestore()
  })
})

describe('F3 — o calendário sempre aberto', () => {
  async function naAbaAgendar() {
    const tela = montarModal()
    await flushPromises()
    await tela.findAll('.agm__aba')[1].trigger('click')
    return tela
  }

  it('🚨 nasce aberto, sem clique nenhum', async () => {
    const tela = await naAbaAgendar()
    expect(tela.find('.agm__cal').exists()).toBe(true)
    expect(tela.findAll('.agm__cal-dia').length).toBeGreaterThan(27)
    expect(tela.findAll('.agm__hora').length).toBeGreaterThan(10)
  })

  it('o passo é de 30 min, das 7h às 19h', async () => {
    const tela = await naAbaAgendar()
    const horas = tela.findAll('.agm__hora').map((n) => n.text())
    expect(horas[0]).toBe('07:00')
    expect(horas[1]).toBe('07:30')
    expect(horas[horas.length - 1]).toBe('19:00')
    expect(horas).toHaveLength(25)
  })

  it('escolher dia e hora monta o `quando`, e um não apaga o outro', async () => {
    const tela = await naAbaAgendar()
    await tela.findAll('.agm__cal-dia')[9].trigger('click')   // dia 10
    await tela.findAll('.agm__hora')[4].trigger('click')      // 09:00
    const campo = tela.find('input[type="datetime-local"]')
    expect(campo.element.value).toMatch(/-10T09:00$/)
    // Troca o dia: a hora tem de ficar.
    await tela.findAll('.agm__cal-dia')[14].trigger('click')  // dia 15
    expect(tela.find('input[type="datetime-local"]').element.value)
      .toMatch(/-15T09:00$/)
  })

  it('o campo digitado continua existindo, para fora do expediente', async () => {
    const tela = await naAbaAgendar()
    await tela.find('input[type="datetime-local"]').setValue('2026-10-23T05:15')
    const continuar = tela.findAll('button').find((b) => b.text() === 'Continuar')
    expect(continuar.attributes('disabled')).toBeUndefined()
  })
})

describe('F4 — o endereço em campos, e o CEP', () => {
  const OS_COM_ENDERECO = {
    numero_os: 16991,
    endereco: { cep: '19013180', endereco: 'Rua Domingos de Moraes',
                numero: 'S/N', bairro: 'Jardim Bela Daria',
                cidade: 'Presidente Prudente', uf: 'SP', complemento: null },
    tem_endereco: true,
  }

  async function noPasso3(resposta = OS_COM_ENDERECO) {
    estado.respostas['/api/agendamento/os/16548/endereco'] = resposta
    const tela = montarModal()
    await flushPromises()
    await tela.findAll('.agm__aba')[1].trigger('click')
    await tela.find('input[type="datetime-local"]').setValue('2026-10-23T09:00')
    await tela.findAll('button').find((b) => b.text() === 'Continuar').trigger('click')
    await tela.findAll('.agm__item')[0].trigger('click')   // cliente
    await flushPromises()
    await tela.findAll('.agm__item')[0].trigger('click')   // OS 16548
    await tela.findAll('button').find((b) => b.text() === 'Continuar').trigger('click')
    await flushPromises()
    return tela
  }

  it('são sete campos, com os nomes do Harmonit', async () => {
    const tela = await noPasso3()
    // O seletor precisa ser o PRIMEIRO span de cada label: o do CEP tem um
    // segundo span, que embrulha o campo e o botao Buscar.
    const rotulos = tela.findAll('.agm__endereco .agm__campo > span:first-child')
      .map((n) => n.text().split(' ')[0])
    expect(rotulos).toEqual(['CEP', 'Rua', 'Número', 'Bairro', 'Cidade', 'UF',
                             'Complemento'])
  })

  it('🚨 pré-preenche com o endereço da PRÓPRIA OS', async () => {
    const tela = await noPasso3()
    const valores = tela.findAll('.agm__endereco input').map((n) => n.element.value)
    expect(valores).toContain('19013180')
    expect(valores).toContain('Rua Domingos de Moraes')
    expect(valores).toContain('Presidente Prudente')
  })

  it('OS sem endereço avisa que o que for digitado vai gravado nela', async () => {
    const tela = await noPasso3({ numero_os: 16991, endereco: {}, tem_endereco: false })
    expect(tela.text()).toContain('não tem endereço')
  })

  it('o CEP preenche rua, bairro, cidade e UF — e nunca o número', async () => {
    estado.respostas['/api/cep/19013180'] = {
      achado: true, cep: '19013180', logradouro: 'Rua Domingos de Moraes',
      bairro: 'Jardim Bela Daria', cidade: 'Presidente Prudente', uf: 'SP' }
    const tela = await noPasso3({ numero_os: 1, endereco: {}, tem_endereco: false })
    const campos = tela.findAll('.agm__endereco input')
    await campos[0].setValue('19013180')
    await tela.findAll('button').find((b) => b.text() === 'Buscar').trigger('click')
    await flushPromises()
    const valores = tela.findAll('.agm__endereco input').map((n) => n.element.value)
    expect(valores[1]).toBe('Rua Domingos de Moraes')
    expect(valores[3]).toBe('Jardim Bela Daria')
    expect(valores[5]).toBe('SP')
    // 🚨 O número é do operador: o CEP não sabe.
    expect(valores[2]).toBe('')
  })

  it('🚨 CEP que não existe e CEP que não deu para consultar são DIFERENTES',
     async () => {
    estado.respostas['/api/cep/19013180'] = { achado: false, cep: '19013180' }
    const tela = await noPasso3({ numero_os: 1, endereco: {}, tem_endereco: false })
    await tela.findAll('.agm__endereco input')[0].setValue('19013180')
    await tela.findAll('button').find((b) => b.text() === 'Buscar').trigger('click')
    await flushPromises()
    expect(tela.text()).toContain('não existe na base dos Correios')
    expect(tela.text()).not.toContain('não quer dizer que')
  })

  it('CEP curto nem sai da tela', async () => {
    const tela = await noPasso3({ numero_os: 1, endereco: {}, tem_endereco: false })
    await tela.findAll('.agm__endereco input')[0].setValue('190')
    await tela.findAll('button').find((b) => b.text() === 'Buscar').trigger('click')
    await flushPromises()
    expect(tela.text()).toContain('8 dígitos')
    expect(estado.pedidos.filter((p) => p.includes('/api/cep/'))).toHaveLength(0)
  })

  it('sem rua, avisa que a OS do Harmonit não muda', async () => {
    const tela = await noPasso3({ numero_os: 1, endereco: {}, tem_endereco: false })
    expect(tela.text()).toContain('não vai para a OS do Harmonit')
  })

  it('manda os campos no POST, e a linha montada como endereço', async () => {
    const tela = await noPasso3()
    await tela.findAll('.agm__endereco input')[2].setValue('26')
    await tela.findAll('.botao--primario').find((b) => b.text() === 'Agendar')
      .trigger('click')
    await flushPromises()
    const post = estado.posts.find((p) => p.rota === '/api/agendamentos')
    expect(post.corpo.endereco_campos).toMatchObject({
      cep: '19013180', logradouro: 'Rua Domingos de Moraes', numero: '26',
      cidade: 'Presidente Prudente', uf: 'SP' })
    // A linha é o que o cliente lê, e sai montada dos campos.
    expect(post.corpo.endereco)
      .toBe('Rua Domingos de Moraes, 26 · Jardim Bela Daria · '
            + 'Presidente Prudente - SP · CEP 19013180')
  })
})

describe('F5 — enviar ao cliente, e abrir na conversa do técnico', () => {
  const UM = {
    id: 1, cliente_nome: 'VELASCO', inicio: '2026-10-23T09:00:00-03:00',
    endereco: 'Rua Um, 100', tecnico_nome: 'Franck', orcamento_numero: 1668,
    responsavel_cliente: 'Dona Maria', conversa_id: 777,
    ordens: [{ numero_os: 16548, placa: 'FZU5D16', tipo_nome: 'Contrato' }],
  }

  async function confirmar(lista = [UM]) {
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

  it('os dois botões são os que ele pediu', async () => {
    const tela = await confirmar()
    const textos = tela.findAll('button').map((b) => b.text())
    expect(textos).toContain('Enviar ao cliente')
    expect(textos).toContain('Abrir na conversa do técnico')
  })

  it('🚨 envia o do cliente e o MODAL PERSISTE', async () => {
    const tela = await confirmar()
    await tela.findAll('button').find((b) => b.text() === 'Enviar ao cliente')
      .trigger('click')
    await flushPromises()
    expect(estado.posts.map((p) => p.rota)).toContain('/api/conversas/1/responder')
    // Como o orçamento faz: não fecha, porque o segundo passo é opcional.
    expect(tela.emitted('fechar')).toBeFalsy()
    expect(tela.text()).toContain('Enviado')
    expect(tela.text()).toContain('O do técnico é opcional')
  })

  it('o texto editado no modal é o que vai enviado', async () => {
    const tela = await confirmar()
    await tela.findAll('.agm__texto')[0].setValue('texto que eu reescrevi')
    await tela.findAll('button').find((b) => b.text() === 'Enviar ao cliente')
      .trigger('click')
    await flushPromises()
    const post = estado.posts.find((p) => p.rota === '/api/conversas/1/responder')
    expect(post.corpo.texto).toBe('texto que eu reescrevi')
  })

  it('envio falho diz o motivo e deixa tentar de novo', async () => {
    const tela = await confirmar()
    estado.erroNoPost = '/api/conversas/1/responder'
    await tela.findAll('button').find((b) => b.text() === 'Enviar ao cliente')
      .trigger('click')
    await flushPromises()
    expect(tela.text()).toContain('o WhatsApp recusou')
    expect(tela.findAll('button').some((b) => b.text() === 'Enviar ao cliente'))
      .toBe(true)
    estado.erroNoPost = ''
  })

  it('🚨 o do técnico ABRE a conversa dele e semeia o compositor — não envia',
     async () => {
    const tela = await confirmar()
    await tela.findAll('button')
      .find((b) => b.text() === 'Abrir na conversa do técnico').trigger('click')
    await flushPromises()
    expect(localStorage.getItem('movizap.rascunho.777')).toContain('OS: 16548')
    expect(estado.navegou).toContain('/atendimento/777')
    // Nenhum envio na conversa do técnico: a rota exige estar nela.
    expect(estado.posts.map((p) => p.rota))
      .not.toContain('/api/conversas/777/responder')
  })

  it('compromisso sem conversa de origem não oferece o botão ativo', async () => {
    const tela = await confirmar([{ ...UM, conversa_id: null }])
    const botao = tela.findAll('button')
      .find((b) => b.text() === 'Abrir na conversa do técnico')
    expect(botao.attributes('disabled')).toBeDefined()
    expect(tela.text()).toContain('não guarda a conversa de origem')
  })
})
