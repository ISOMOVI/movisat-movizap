/**
 * @vitest-environment jsdom
 *
 * O BOTÃO "FINALIZAR" DA ETAPA 888 DO CONTRATUAL — 23/11.
 *
 * 🔵 Ele, 19/11: *"Daí o botão 'Finalizar' do card de 'Assinado' pergunta se há
 * termo para gerar OS e em caso de não, ele continua o fluxo local. Em caso de
 * 'Sim' abre o modal."* · 🔵 23/11, **D1**: *"o 'Finalizar' grava `resolvido`
 * para o 'Não' e `virou_os` para o 'Sim'"* · 🔵 23/11, **D8**: o caminho é o
 * **C** — aba nova no FPSL, não modal (o `X-Frame-Options DENY` do nginx mora
 * num snippet compartilhado com `prospeccao` e `prospeccaoia`) · 🔵 23/11,
 * **D9**: quem vê o botão é **quem tem a `PNL_1.5`**, e o MoviZap NÃO consulta
 * o FPSL para desenhá-lo.
 *
 * 🚨 **O QUE ESTE ARQUIVO GUARDA É UMA REGRESSÃO, não a função nova.** Medido
 * em 23/11: a `PainelAba.vue` serve **quatro** telas (`PNL_1.2`, `PNL_1.3`,
 * `PNL_1.4`, `PNL_1.5`) com **uma única** passagem de rótulo
 * (`PainelAba.vue:321`). E o "Finalizar" já está em uso **fora** da 888: os
 * cards 1500 e 2241 estão na etapa **885** (Elaborar contrato) com
 * `desfecho = virou_os`, e o 2588 na 885 com `resolvido`. Trocar o texto sem
 * condicionar à etapa E à aba mudaria o significado de três cards reais e de
 * quatro telas de uma vez.
 *
 * 🚨 **OS DOIS BOTÕES NÃO TROCAM DE PAYLOAD.** Hoje "Resolvido" chama
 * `finalizar('resolvido')` e "Não resolvido" chama `finalizar('virou_os')`. A
 * D1 pede "Não" → `resolvido` e "Sim" → `virou_os`: os MESMOS dois valores na
 * MESMA ordem. Só os textos mudam — e é por isso que não há migração, não há
 * rota nova e o `DESFECHOS` do `pipeline.py:42` não foi tocado.
 *
 * ⚠️ **MONTA-SE O `DialogoDeChamado` DIRETO**, que é o molde do
 * `os_no_card_da_aba_1911.teste.js`. A primeira versão deste arquivo montava a
 * `PainelAba` e os 13 testes reprovaram no MESMO ponto — o diálogo nem abria,
 * porque quem emite `abrir` é o `.card__abrir` dentro do `CorpoDoCard`, e não o
 * `<article>`. Teste que reprova pelo motivo errado não prova defeito nenhum.
 * A fiação da prop tem trava própria, no fim do arquivo, e essa monta a
 * `PainelAba` de verdade.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const estado = vi.hoisted(() => ({
  ficha: null, quadro: null, postado: [], empurrado: [],
}))

vi.mock('./api/cliente.js', () => {
  class ErroDeApi extends Error {}
  return {
    api: {
      get: (caminho) => {
        const c = String(caminho)
        if (c.includes('/checklist')) return Promise.resolve({ itens: [] })
        if (c.includes('/passagens')) return Promise.resolve({ passagens: [] })
        /* 🚨 Card do Contratual NÃO TEM OS: a rota responde 404 com a frase, e
           é isso que a fixture encena. Fixture que devolvesse uma OS aqui
           seria irreal. */
        if (c.endsWith('/os')) {
          return Promise.reject(new ErroDeApi('Este card não tem OS no Harmonit.'))
        }
        if (c.includes('/chamado/')) return Promise.resolve(estado.ficha)
        return Promise.resolve(estado.quadro)
      },
      post: (caminho, corpo) => {
        estado.postado.push([String(caminho), corpo])
        return Promise.resolve({ ok: true })
      },
      put: () => Promise.resolve({}),
      del: () => Promise.resolve({}),
    },
    definirToken: () => {},
    temToken: () => true,
    quandoPerderSessao: () => {},
    relatarErroDeBotao: () => {},
    ErroDeApi,
  }
})

vi.mock('./estado/sessao.js', () => ({
  sessao: { nome: 'Iago', owner: true, telas: [] },
  codigosPermitidos: { value: new Set() },
  sair: () => {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ meta: { codigo: 'PNL_1.5', aba: 'PNL_1.5' },
                     query: {}, params: {} }),
  useRouter: () => ({ push: (p) => estado.empurrado.push(String(p)),
                      replace: () => {} }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

import DialogoDeChamado from './componentes/DialogoDeChamado.vue'
import PainelAba from './telas/PainelAba.vue'

/* 🚨 O ENDEREÇO PÚBLICO DO FPSL, medido em 23/11 no nginx
   (`/etc/nginx/sites-available/fpsl.conf`, `server_name fpsl.movisat.com.br`).
   ⚠️ A trava o repete de propósito: trocar a constante da tela sem trocar aqui
   faz a suíte falar. O `FPSL_BASE_URL` do `.env` é `http://127.0.0.1:8004` e
   **não serve** — é o endereço servidor-a-servidor da ponte, que o navegador
   de quem usa a tela não alcança. */
const URL_ESPERADA = 'https://fpsl.movisat.com.br/painel/operacoes'

/* As etapas reais da aba 302 (Contratual), medidas em 23/11 no
   `pipeline_etapa`. 🚨 A 888 NÃO é a única `final = true`: a 889 (Não
   assinado) e a 890 (Desistiu de cancelar) também são, e por isso a condição
   da tela NÃO pode ser "etapa final". */
const ETAPAS_DO_CONTRATUAL = [
  { id: 885, titulo: 'Elaborar contrato' },
  { id: 886, titulo: 'Aguardando pendencias' },
  { id: 887, titulo: 'Aguardando assinatura' },
  { id: 888, titulo: 'Assinado' },
  { id: 889, titulo: 'Não assinado' },
  { id: 890, titulo: 'Desistiu de cancelar' },
]

/* O card 3493, que está de verdade na 888 sem desfecho (medido em 23/11). */
function card(etapa_id, extra = {}) {
  return { id: 3493, etapa_id, numero_os: null, numero_ordem: null,
           situacao_id: null, cliente: 'Zz Pastelaria Velasco',
           desfecho: null, desfecho_em: null, desfecho_rotulo: null,
           telefone: null, ...extra }
}

async function abrir(aba, etapa_id, etapas = ETAPAS_DO_CONTRATUAL) {
  estado.ficha = {
    card: { id: 3493, etapa_id, desfecho: null, desfecho_em: null },
    etapas, observacoes: [], historico: [], chamado: null,
  }
  const tela = mount(DialogoDeChamado, {
    props: { card: card(etapa_id), rotuloFinalizar: 'Finalizar', aba },
  })
  await flushPromises()
  await flushPromises()
  /* 🚨 O GESTO: clica-se em "Finalizar", que é o que faz a pergunta aparecer.
     A pergunta NÃO existe antes do clique — foi decisão dele em 05/11. */
  const botaoFinalizar = tela.findAll('button')
    .find((b) => b.text().trim() === 'Finalizar')
  expect(botaoFinalizar, 'o botão "Finalizar" tem de existir').toBeTruthy()
  await botaoFinalizar.trigger('click')
  await flushPromises()
  return tela
}

const pergunta = (tela) => tela.find('.desfecho__pergunta')
const botao = (tela, texto) =>
  tela.findAll('.desfecho__pergunta button, .desfecho__pergunta a')
    .find((b) => b.text().trim() === texto)

beforeEach(() => {
  estado.postado = []
  estado.empurrado = []
  estado.quadro = null
})

/* ==========================================================================
   A FUNÇÃO NOVA — só na 888 do Contratual
   ========================================================================== */
describe('a etapa 888 (Assinado) do Contratual', () => {
  const na888 = () => abrir('PNL_1.5', 888)

  it('🔵 pergunta "Há termo para gerar OS?", com "Sim" e "Não"', async () => {
    const tela = await na888()
    expect(pergunta(tela).text()).toContain('Há termo para gerar OS?')
    expect(botao(tela, 'Sim')).toBeTruthy()
    expect(botao(tela, 'Não')).toBeTruthy()
  })

  it('🚨 e NÃO diz mais "Resolvido?" nem "Não resolvido" (M12)', async () => {
    const tela = await na888()
    expect(pergunta(tela).text()).not.toContain('Resolvido?')
    expect(pergunta(tela).text()).not.toContain('Não resolvido')
  })

  it('🔵 D1: "Não" grava `resolvido` — o fluxo segue local', async () => {
    const tela = await na888()
    await botao(tela, 'Não').trigger('click')
    await flushPromises()
    const [caminho, corpo] = estado.postado[0]
    expect(caminho).toBe('/api/paineis/operacao/chamado/3493/finalizar')
    expect(corpo).toEqual({ desfecho: 'resolvido' })
  })

  it('🔵 D1: "Sim" grava `virou_os`', async () => {
    const tela = await na888()
    await botao(tela, 'Sim').trigger('click')
    await flushPromises()
    expect(estado.postado[0][1]).toEqual({ desfecho: 'virou_os' })
  })

  it('🔵 D8: "Sim" é uma ÂNCORA para o FPSL em aba nova, não um botão',
     async () => {
    const tela = await na888()
    const sim = botao(tela, 'Sim')
    /* ⚠️ `<a target="_blank">` e não `window.open`: a lição está escrita no
       `ModalKm.vue:160` — *"bloqueador de pop-up come `window.open` sem aviso,
       e aí o clique não faria nada e pareceria defeito"*. */
    expect(sim.element.tagName).toBe('A')
    expect(sim.attributes('href')).toBe(URL_ESPERADA)
    expect(sim.attributes('target')).toBe('_blank')
    /* 🚨 `rel="noopener"`: sem isto a aba do FPSL ganha `window.opener` e pode
       navegar a nossa. */
    expect(sim.attributes('rel')).toContain('noopener')
  })

  it('🚨 o "Não" NÃO leva a lugar nenhum — fluxo local é local', async () => {
    const tela = await na888()
    const nao = botao(tela, 'Não')
    expect(nao.element.tagName).toBe('BUTTON')
    expect(nao.attributes('href')).toBeUndefined()
    await nao.trigger('click')
    await flushPromises()
    expect(estado.empurrado).toEqual([])
  })

  it('🚨 NADA escreve no ERP, nos dois caminhos', async () => {
    for (const texto of ['Sim', 'Não']) {
      estado.postado = []
      const tela = await abrir('PNL_1.5', 888)
      await botao(tela, texto).trigger('click')
      await flushPromises()
      expect(estado.postado.length).toBeGreaterThan(0)
      for (const [caminho] of estado.postado) {
        expect(caminho).not.toMatch(/\/operacao\/mover/)
        expect(caminho).not.toMatch(/\/prioridade/)
        expect(caminho).not.toMatch(/\/situacao/)
      }
    }
  })
})

/* ==========================================================================
   A REGRESSÃO — as outras 5 etapas e as outras 3 telas não mudam
   🚨 ESTAS TRAVAS PASSAM ANTES DO CONSERTO. É isso que as torna travas de
   regressão e não de função: elas medem o que já estava certo.
   ========================================================================== */
describe('o que NÃO pode mudar', () => {
  /* 🚨 885 é onde estão os cards 1500, 2241 e 2588 DE VERDADE, com desfecho
     já gravado. É o caso que a mudança quebraria. */
  it('🚨 na 885 do Contratual continua "Resolvido?"', async () => {
    const tela = await abrir('PNL_1.5', 885)
    expect(pergunta(tela).text()).toContain('Resolvido?')
    expect(botao(tela, 'Resolvido')).toBeTruthy()
    expect(botao(tela, 'Não resolvido')).toBeTruthy()
    expect(pergunta(tela).text()).not.toContain('Há termo para gerar OS?')
  })

  it('🚨 e na 885 o "Resolvido" segue gravando `resolvido`', async () => {
    const tela = await abrir('PNL_1.5', 885)
    await botao(tela, 'Resolvido').trigger('click')
    await flushPromises()
    expect(estado.postado[0][1]).toEqual({ desfecho: 'resolvido' })
  })

  /* 🚨 889 e 890 também são `final = true`. Se a condição da tela virar
     "etapa final", estas duas quebram — e é só isto que elas medem. */
  it('🚨 na 889 (Não assinado), que também é final, continua "Resolvido?"',
     async () => {
    const tela = await abrir('PNL_1.5', 889)
    expect(pergunta(tela).text()).toContain('Resolvido?')
    expect(pergunta(tela).text()).not.toContain('Há termo para gerar OS?')
  })

  it('🚨 na 890 (Desistiu de cancelar), idem', async () => {
    const tela = await abrir('PNL_1.5', 890)
    expect(pergunta(tela).text()).toContain('Resolvido?')
    expect(pergunta(tela).text()).not.toContain('Há termo para gerar OS?')
  })

  /* 🚨 A `PainelAba` é A MESMA nas quatro telas. A trava prende a ABA, não só
     o número: se alguém criar uma etapa 888 em outra aba, isto diz. */
  it('🚨 no Financeiro (PNL_1.4) continua "Resolvido?", mesmo na etapa final',
     async () => {
    const etapas = [{ id: 875, titulo: 'Nova solicitação' },
                    { id: 883, titulo: 'Atendimento feito' }]
    const tela = await abrir('PNL_1.4', 883, etapas)
    expect(pergunta(tela).text()).toContain('Resolvido?')
    expect(pergunta(tela).text()).not.toContain('Há termo para gerar OS?')
  })

  it('🚨 no Pós-venda (PNL_1.2) continua "Resolvido?"', async () => {
    const etapas = [{ id: 465, titulo: 'Nova solicitação' },
                    { id: 468, titulo: 'Entregue' }]
    const tela = await abrir('PNL_1.2', 468, etapas)
    expect(pergunta(tela).text()).toContain('Resolvido?')
    expect(pergunta(tela).text()).not.toContain('Há termo para gerar OS?')
  })

  /* 🚨 A OPERAÇÃO não passa `aba` nenhuma — ela monta este diálogo direto.
     Mesmo que um card dela tivesse o id de etapa 888, a pergunta não é dela. */
  it('🚨 sem aba (a Operação) continua "Resolvido?", até na etapa 888',
     async () => {
    const tela = await abrir('', 888)
    expect(pergunta(tela).text()).toContain('Resolvido?')
    expect(pergunta(tela).text()).not.toContain('Há termo para gerar OS?')
  })
})

/* ==========================================================================
   A FIAÇÃO — a `PainelAba` passa mesmo o `:aba` ao diálogo
   🚨 Trava própria porque é o elo que nenhuma das de cima enxerga: as 13
   acima passariam com a `PainelAba.vue` intacta, e aí a função nova não
   apareceria na tela de verdade. É o *"campo novo não entra sozinho"*.
   ========================================================================== */
describe('a fiação da PainelAba', () => {
  it('🚨 a `PainelAba` do Contratual passa `aba = PNL_1.5` ao diálogo',
     async () => {
    estado.quadro = {
      painel: 'contratual', aba: 'PNL_1.5', titulo: 'Contratual',
      abas: [{ codigo_tela: 'PNL_1.5', titulo: 'Contratual' }],
      etapas: ETAPAS_DO_CONTRATUAL, desfechos: [], total: 1,
      pode_mover: true, fora_do_quadro: {},
      colunas: ETAPAS_DO_CONTRATUAL.map((e) => ({
        chave: `e${e.id}`, titulo: e.titulo, situacao_id: null,
        etapa_id: e.id, final: e.id >= 888, nota: null,
        cards: e.id === 888 ? [card(888)] : [],
        total: e.id === 888 ? 1 : 0,
      })),
    }
    estado.ficha = {
      card: { id: 3493, etapa_id: 888, desfecho: null, desfecho_em: null },
      etapas: ETAPAS_DO_CONTRATUAL, observacoes: [], historico: [],
      chamado: null,
    }
    const tela = mount(PainelAba, {
      global: { stubs: { RouterLink: { props: ['to'],
                                       template: '<a :href="to"><slot /></a>' } } },
    })
    await flushPromises()
    /* 🚨 O GESTO DE VERDADE: quem emite `abrir` é o `.card__abrir` do
       `CorpoDoCard`, não o `<article>`. Foi exatamente isto que derrubou os 13
       testes da primeira versão deste arquivo. */
    const alvo = tela.findAll('.card__abrir')
      .find((n) => n.text().includes('Pastelaria Velasco'))
    expect(alvo, 'o card 3493 tem de estar na coluna Assinado').toBeTruthy()
    await alvo.trigger('click')
    await flushPromises()
    await flushPromises()

    const dlg = tela.findComponent(DialogoDeChamado)
    expect(dlg.exists()).toBe(true)
    expect(dlg.props('aba')).toBe('PNL_1.5')
    /* E o efeito disso na tela, que é o que importa: a pergunta nova. */
    const btn = dlg.findAll('button')
      .find((b) => b.text().trim() === 'Finalizar')
    await btn.trigger('click')
    await flushPromises()
    expect(dlg.find('.desfecho__pergunta').text())
      .toContain('Há termo para gerar OS?')
  })
})
