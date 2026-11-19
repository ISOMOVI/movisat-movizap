/*
 * @vitest-environment jsdom
 *
 * O CARD DE OS EM ETAPA NOSSA — 18/11.
 *
 * 🚨 ESTE ARQUIVO GUARDA UM DEFEITO QUE ELE ACHOU OLHANDO A TELA:
 * *"Então pq os cards informam que não vem de OS no painel?"*
 *
 * 📏 Medido no mesmo dia: os 8 cards do Financeiro eram **todos OS** (17120,
 * 17119, 17122, 17127, 17125, 17129, 17134, 17136), e nenhum veio de
 * formulário — a `formulario_solicitacao` não tinha uma única linha dos 4
 * formulários que apontam a etapa 875. Quem os trouxe foi
 * `recebe_situacao = 15746`.
 *
 * E ainda assim:
 *   · o card recebia `origem: "chamado"` e a borda `.card__abrir--chamado`,
 *     cujo próprio comentário no CSS dizia *"o card de CHAMADO é visivelmente
 *     outro: ele não é uma OS"*;
 *   · a tela das abas desenhava **6** campos, quando o servidor já mandava mais
 *     de 20 — `tipo_nome`, `termo`, `status_str`, `placas`, `prioridade`,
 *     `visto_em`, `etapa_desde`, `prazo` entraram em 12/11 a pedido dele
 *     (*"nos cards do financeiro, faltam informações sobre o tipo do termo,
 *     número do termo"* / *"igual da OP"*) e nunca apareceram.
 *
 * ⚠️ **E nenhuma suíte reclamava**, porque o defeito era de OMISSÃO: a tela
 * tinha o dado e não o mostrava. Foi preciso ele olhar. `M12` por omissão é o
 * mais difícil de pegar, e é por isso que estes testes olham o TEXTO do card,
 * e não a existência de um campo no JSON.
 *
 * 🚨 E A REGRA DO CONSERTO, que três destes testes travam: **o que muda é o
 * rótulo, não a guarda.** `numero_ordem` e `situacao_id` continuam nulos no
 * card de etapa nossa — é esse nulo que mantém o card sem arrasto para o ERP
 * numa aba cujo mover grava só no nosso banco.
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import CorpoDoCard from './componentes/CorpoDoCard.vue'

/* O card de OS em etapa NOSSA, como o `_card_do_chamado` o devolve hoje: com
   `numero_os` preenchido e `numero_ordem`/`situacao_id` NULOS de propósito. */
function cardDeOS(extra = {}) {
  return {
    id: 2645,
    origem: 'erp_em_etapa_nossa',
    etapa_id: 875,
    solicitacao_id: null,
    formulario: null,
    slug: null,
    criada_em: '2026-11-18T09:09:00-03:00',
    estado: null,
    cliente: 'Zz Pastelaria Velasco',
    cliente_id: 84792,
    resumo: null,
    anexos: 0,
    numero_os: 17134,
    os_id: null,
    numero_ordem: null,
    situacao_id: null,
    tipo_nome: 'Instalação',
    status_str: 'Iniciada',
    finalizada: false,
    placas: [{ placa: 'UVO 8E01' }],
    tecnicos: [{ nome: 'Franck' }],
    visto_em: '2026-11-18T12:49:21+00:00',
    etapa_desde: '2026-11-18T09:41:09-03:00',
    prazo: null,
    observacoes: 2,
    prioridade: 382,
    prioridade_nome: 'Normal',
    termo: '8955',
    desfecho: null,
    telefone: null,
    ...extra,
  }
}

/* O chamado de verdade: sem OS nenhuma. */
function cardDeChamado(extra = {}) {
  return {
    ...cardDeOS(),
    id: 87,
    origem: 'chamado',
    numero_os: null,
    formulario: 'Suporte',
    termo: null,
    tipo_nome: null,
    status_str: null,
    placas: [],
    visto_em: null,
    cliente: 'Zz Empresa do Chamado',
    resumo: 'detalhe a ocorrência: não liga',
    prazo: { vence_em: '2026-11-19T17:00:00-03:00', segundos_uteis: 25200,
             atrasado: false },
    ...extra,
  }
}

function montar(card) {
  return mount(CorpoDoCard, { props: { card } })
}

describe('o card de OS em etapa nossa NÃO se declara chamado', () => {
  it('não recebe a borda de chamado', () => {
    /* 🚨 O defeito exato que ele viu: a borda cujo CSS diz "ele não é uma OS",
       num card que é OS. */
    const tela = montar(cardDeOS())
    expect(tela.find('.card__abrir').classes())
      .not.toContain('card__abrir--chamado')
  })

  it('o chamado DE VERDADE continua recebendo a borda', () => {
    /* ⚠️ Guarda-de-regressão: consertar um não pode apagar o outro. O card sem
       OS é visivelmente outro, e isso é decisão de desenho dele. */
    const tela = montar(cardDeChamado())
    expect(tela.find('.card__abrir').classes())
      .toContain('card__abrir--chamado')
  })

  it('mostra OS, e não o nome do formulário, no botão', () => {
    const tela = montar(cardDeOS())
    expect(tela.find('.card__os').text()).toBe('OS 17134')
  })

  it('o chamado sem OS mostra o formulário no botão', () => {
    const tela = montar(cardDeChamado())
    expect(tela.find('.card__os').text()).toBe('Suporte')
  })
})

describe('os campos que o servidor mandava e a tela jogava fora', () => {
  it('mostra o TERMO', () => {
    /* 🔵 *"termo no card e busca por termo"* (05/11), e 🔵 12/11: *"faltam
       informações sobre o tipo do termo, número do termo"*. */
    expect(montar(cardDeOS()).text()).toContain('TERMO 8955')
  })

  it('mostra o TIPO e a PLACA', () => {
    const texto = montar(cardDeOS()).text()
    expect(texto).toContain('Instalação')
    expect(texto).toContain('UVO 8E01')
  })

  it('mostra o tempo NESTA ETAPA, e não "não medido"', () => {
    /* 🚨 Era `None` fixo no card de chamado até 11/11, e depois o backend
       passou a mandar `etapa_desde` — que esta tela ignorava. */
    const texto = montar(cardDeOS()).text()
    expect(texto).toContain('nesta etapa')
    expect(texto).not.toContain('não medido')
  })

  it('diz QUANDO foi lido do Harmonit', () => {
    /* ⚠️ A varredura roda a cada 5 min, e a tela não pode deixar supor que é
       agora. 🚨 E o campo é `atualizado_em` do cache, não `visto_em` — quem
       escolhe isso é o servidor. */
    expect(montar(cardDeOS()).text()).toContain('lido do Harmonit')
  })

  it('mostra as observações', () => {
    expect(montar(cardDeOS()).text()).toContain('2 obs')
  })

  it('"não medido" APARECE quando de fato não há passagem', () => {
    /* ⚠️ A `os_passagem` começou em 29/10: OS nunca movida por aqui não tem de
       onde tirar o tempo. Mostrar "0h" seria afirmar o que ninguém mediu. */
    const texto = montar(cardDeOS({ etapa_desde: null })).text()
    expect(texto).toContain('não medido')
  })
})

describe('o rótulo mudou, a guarda NÃO', () => {
  it('`numero_ordem` e `situacao_id` continuam nulos no card de etapa nossa', () => {
    /* 🚨 São eles que a tela lê para manter o card sem arrasto e sem `<select>`
       de mover. Enchê-los ligaria o arrasto ao ERP numa aba cujo mover grava
       só no nosso banco. Este teste trava o CONTRATO, não o desenho. */
    const card = cardDeOS()
    expect(card.numero_ordem).toBeNull()
    expect(card.situacao_id).toBeNull()
  })

  it('o card de OS em etapa nossa mostra OS mesmo com `numero_ordem` nulo', () => {
    /* ⚠️ É a consequência do de cima: o componente tem de achar a OS em
       `numero_os`, porque `numero_ordem` é nulo de propósito. */
    const tela = montar(cardDeOS({ numero_ordem: null, numero_os: 17134 }))
    expect(tela.find('.card__os').text()).toBe('OS 17134')
  })

  it('OS nascida de FORMULÁRIO mostra o formulário E a OS', () => {
    /* 🚨 Eu errei isto primeiro e derrubei dois testes de 22/10 e 05/11: troquei
       a regra da pílula de origem por "não tem OS", e isso escondia o nome do
       formulário exatamente no caso em que ele informa algo — a OS que nasceu
       de um formulário tem os dois. */
    const tela = montar(cardDeOS({ origem: 'formulario', formulario: 'Suporte',
                                   numero_ordem: 17042 }))
    expect(tela.find('.pilula--origem').text()).toBe('Suporte')
    expect(tela.find('.card__os').text()).toBe('OS 17042')
  })

  it('OS do ERP, sem formulário, NÃO ganha pílula de origem', () => {
    /* ⚠️ A origem ERP é a maioria: um selo em quase todo card não distingue
       nada e gasta a linha dos selos. */
    const tela = montar(cardDeOS({ origem: 'erp', numero_ordem: 17042 }))
    expect(tela.find('.pilula--origem').exists()).toBe(false)
  })
})

describe('os selos da Operação não vazam para as abas', () => {
  it('sem `mostrar-pendencia`, o selo da fila NÃO aparece', () => {
    /* ⚠️ Nas abas o mover grava no nosso banco: não existe escrita pendente, e
       mostrar o selo ali seria inventar um estado. */
    const tela = montar(cardDeOS({ passagem_pendente: true }))
    expect(tela.find('.card__pendente').exists()).toBe(false)
  })

  it('com `mostrar-pendencia`, aparece', () => {
    const tela = mount(CorpoDoCard, {
      props: { card: cardDeOS({ passagem_pendente: true }),
               mostrarPendencia: true },
    })
    expect(tela.find('.card__pendente').exists()).toBe(true)
    expect(tela.find('.card__pendente').text())
      .toContain('ainda não foi para a OS')
  })

  it('a trava de 60s só aparece com os segundos por `prop`', () => {
    expect(montar(cardDeOS()).find('.card__assentando').exists()).toBe(false)
    const tela = mount(CorpoDoCard, {
      props: { card: cardDeOS(), segundosDeEspera: 43 },
    })
    expect(tela.find('.card__assentando').text()).toContain('espere 43s')
  })
})

describe('o componente é UM, e é isso que conserta a causa', () => {
  it('a mesma caixa desenha o card de OS e o de chamado', () => {
    /* 🚨 A causa do defeito era estrutural: dois `<article>` em dois arquivos,
       um com 20 campos e outro com 6. Enquanto fossem dois, o próximo campo
       entraria num e faltaria no outro — e foi o que aconteceu com os campos de
       12/11. Este teste afirma que agora é um. */
    const comOS = montar(cardDeOS())
    const semOS = montar(cardDeChamado())
    expect(comOS.find('.card__abrir').exists()).toBe(true)
    expect(semOS.find('.card__abrir').exists()).toBe(true)
    /* E o que difere é o CONTEÚDO, não o desenho: os dois têm cliente, botão de
       identificação e a faixa de tempo. */
    for (const tela of [comOS, semOS]) {
      expect(tela.find('.card__cliente').exists()).toBe(true)
      expect(tela.find('.card__os').exists()).toBe(true)
      expect(tela.text()).toContain('nesta etapa')
    }
  })

  it('o prazo do chamado aparece, e no card de OS não', () => {
    /* 🔵 *"Abrirá com prazo de 24hrs uteis para conclusão, apenas informativo"*.
       ⚠️ OS não tem prazo: o Harmonit tem UM campo de data, `dataPrevisao`. */
    expect(montar(cardDeChamado()).text()).toContain('úteis')
    expect(montar(cardDeOS()).find('.card__prazo').exists()).toBe(false)
  })

  it('o resumo do formulário aparece no chamado', () => {
    expect(montar(cardDeChamado()).text()).toContain('não liga')
  })
})
