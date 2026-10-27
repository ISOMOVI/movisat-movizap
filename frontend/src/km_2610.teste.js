/**
 * @vitest-environment jsdom
 *
 * A calculadora de KM do técnico (`ModalKm.vue`, 26/10).
 *
 * 🚨 O QUE ESTE ARQUIVO PRENDE, E É O PONTO DA ENTREGA DE HOJE: a tela
 * funciona **sem o cálculo**. Enquanto não houver chave da API de rotas,
 * `disponivel` vem `false` e ela **diz por quê**, com o km manual — em vez de
 * oferecer um botão que falha. E a memória da origem funciona de qualquer
 * jeito, porque o backend grava o que foi digitado mesmo quando o cálculo não
 * acontece.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

let respostas
let posts

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      const chave = Object.keys(respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? respostas[chave] : {})
    },
    post: (rota, corpo) => {
      posts.push({ rota, corpo })
      const r = respostas[rota]
      if (r instanceof Error) return Promise.reject(r)
      return Promise.resolve(r || {})
    },
    put: () => Promise.resolve({}),
    del: () => Promise.resolve({}),
  },
  pedirBlob: () => Promise.resolve(new Blob([''])),
  definirToken: () => {},
  temToken: () => true,
  quandoPerderSessao: () => {},
  ErroDeApi: class ErroDeApi extends Error {},
}))

import ModalKm from './componentes/ModalKm.vue'

const MEMORIA = {
  origem: { cep: '19013180', logradouro: 'Rua Joaquim Nabuco', numero: '1234',
            bairro: 'Jardim Bongiovani', cidade: 'Presidente Prudente',
            uf: 'SP', complemento: '', atualizado_em: '2026-10-20T10:00:00-03:00' },
  disponivel: false,
}

const DESTINO = { cep: '19020000', logradouro: 'Avenida Brasil', numero: '500',
                  bairro: 'Centro', cidade: 'Presidente Prudente', uf: 'SP',
                  complemento: '' }

async function montar(props = {}) {
  const tela = mount(ModalKm, {
    props: { conversaId: 777, destinoInicial: DESTINO, ...props },
  })
  await new Promise((r) => setTimeout(r, 0))
  await tela.vm.$nextTick()
  return tela
}

function botao(tela, texto) {
  return tela.findAll('button').find((b) => b.text().includes(texto))
}

describe('a calculadora de KM', () => {
  beforeEach(() => {
    posts = []
    respostas = { '/api/rotas/origem': MEMORIA }
  })

  it('abre com a origem guardada já preenchida', async () => {
    const tela = await montar()
    const valores = tela.findAll('input').map((i) => i.element.value)
    expect(valores).toContain('Rua Joaquim Nabuco')
    expect(valores).toContain('1234')
    /* E diz DE QUANDO é a memória: endereço herdado em silêncio manda técnico
       para o lugar errado. */
    expect(tela.text()).toContain('guardado em')
  })

  it('o destino vem do passo do endereço, sem redigitar', async () => {
    const tela = await montar()
    const valores = tela.findAll('input').map((i) => i.element.value)
    expect(valores).toContain('Avenida Brasil')
    expect(valores).toContain('500')
  })

  /* 🚨 O coração da entrega: sem chave não há "Calcular aqui", e a tela
     APONTA O CAMINHO em vez de só avisar que não dá. */
  it('sem chave: não oferece o cálculo, e aponta a rota no Google', async () => {
    const tela = await montar()
    expect(botao(tela, 'Calcular aqui')).toBeUndefined()
    expect(tela.text()).toContain('Abra a rota no Google')
    expect(tela.text()).toContain('veja o km')
  })

  it('sem chave: diz que a origem fica guardada de qualquer forma', async () => {
    const tela = await montar()
    expect(tela.text()).toContain('fica guardado')
  })

  /* 🔵 O caminho SEM API — ideia dele, e o que funciona sempre. */
  describe('o link da rota (sem API, custo zero)', () => {
    it('existe mesmo SEM chave, e é âncora de aba nova', async () => {
      const tela = await montar()
      const a = tela.findAll('a').find((x) => x.text().includes('Ver a rota'))
      expect(a).toBeTruthy()
      /* Âncora e não `window.open`: bloqueador de pop-up come o segundo sem
         aviso, e o clique pareceria não fazer nada. */
      expect(a.attributes('target')).toBe('_blank')
      expect(a.attributes('rel')).toContain('noopener')
    })

    it('leva os DOIS endereços já preenchidos — é o trabalho que ele poupa',
       async () => {
      const tela = await montar()
      const href = tela.findAll('a')
        .find((x) => x.text().includes('Ver a rota')).attributes('href')
      expect(href).toContain('google.com/maps/dir/')
      expect(href).toContain('api=1')
      expect(href).toContain('travelmode=driving')
      const url = new URL(href)
      expect(url.searchParams.get('origin')).toContain('Rua Joaquim Nabuco')
      expect(url.searchParams.get('origin')).toContain('Presidente Prudente')
      expect(url.searchParams.get('destination')).toContain('Avenida Brasil')
    })

    it('sem endereço nenhum, não oferece link quebrado — diz o que falta',
       async () => {
      respostas['/api/rotas/origem'] = { origem: null, disponivel: false }
      const tela = await montar({ destinoInicial: {} })
      expect(tela.findAll('a').find((x) => x.text().includes('Ver a rota')))
        .toBeUndefined()
      expect(tela.text()).toContain('preencha os endereços')
    })

    it('avisa que o Google mostra a IDA, quando ida e volta está marcado',
       async () => {
      const tela = await montar()
      expect(tela.text()).toContain('mostra o km de ida')
    })
  })

  it('sem chave, o km digitado à mão vai embora no "Usar"', async () => {
    const tela = await montar()
    const manual = tela.findAll('input').at(-1)
    await manual.setValue('77')
    await botao(tela, 'Usar').trigger('click')
    const [[carga]] = tela.emitted('usar')
    expect(carga.km).toBe(77)
    /* E a origem vai junto: quem grava o compromisso precisa dos dois. */
    expect(carga.origem.logradouro).toBe('Rua Joaquim Nabuco')
  })

  it('"Usar" fica desabilitado enquanto não há km', async () => {
    const tela = await montar()
    expect(botao(tela, 'Usar').attributes('disabled')).toBeDefined()
  })

  describe('com a chave configurada', () => {
    beforeEach(() => {
      respostas = {
        '/api/rotas/origem': { ...MEMORIA, disponivel: true },
        '/api/rotas/km': { km_ida: 38.5, km: 77, ida_e_volta: true,
                           do_cache: false, consultado_em: null },
      }
    })

    it('oferece o botão e manda a conversa, não o id do contato', async () => {
      const tela = await montar()
      await botao(tela, 'Calcular aqui').trigger('click')
      await new Promise((r) => setTimeout(r, 0))
      expect(posts[0].rota).toBe('/api/rotas/km')
      expect(posts[0].corpo.conversa_id).toBe(777)
      expect(posts[0].corpo).not.toHaveProperty('tecnico_contato_id')
    })

    /* 🚨 AS DUAS CONTAS À VISTA: ninguém cobra errado por distração. */
    it('mostra a ida E o total, dizendo que é ida e volta', async () => {
      const tela = await montar()
      await botao(tela, 'Calcular aqui').trigger('click')
      await new Promise((r) => setTimeout(r, 0))
      await tela.vm.$nextTick()
      const texto = tela.text()
      expect(texto).toContain('38.5 km')
      expect(texto).toContain('77 km')
      expect(texto).toContain('ida e volta')
    })

    it('ida e volta nasce MARCADO (decisão dele de 26/10)', async () => {
      const tela = await montar()
      const caixa = tela.find('input[type="checkbox"]')
      expect(caixa.element.checked).toBe(true)
      await botao(tela, 'Calcular aqui').trigger('click')
      await new Promise((r) => setTimeout(r, 0))
      expect(posts[0].corpo.ida_e_volta).toBe(true)
    })

    it('o número calculado continua EDITÁVEL', async () => {
      const tela = await montar()
      await botao(tela, 'Calcular aqui').trigger('click')
      await new Promise((r) => setTimeout(r, 0))
      await tela.vm.$nextTick()
      expect(tela.text()).toContain('dá para corrigir')
      const manual = tela.findAll('input').at(-1)
      await manual.setValue('80')
      await botao(tela, 'Usar').trigger('click')
      expect(tela.emitted('usar')[0][0].km).toBe(80)
    })

    it('🚨 "não achei rota" NÃO é "não deu para perguntar"', async () => {
      respostas['/api/rotas/km'] = { km: null, motivo: 'não achei uma rota entre '
                                     + 'estes dois endereços' }
      const tela = await montar()
      await botao(tela, 'Calcular aqui').trigger('click')
      await new Promise((r) => setTimeout(r, 0))
      await tela.vm.$nextTick()
      expect(tela.text()).toContain('não achei uma rota')
      /* E oferece a saída: digitar. Beco sem saída é defeito. */
      expect(tela.text()).toContain('digite o km abaixo')
      /* ⚠️ E NUNCA preenche zero: zero é um número que vai para orçamento. */
      expect(tela.emitted('usar')).toBeFalsy()
    })

    it('o botão de calcular espera rua e cidade nos dois, e DIZ isso', async () => {
      respostas['/api/rotas/origem'] = { origem: null, disponivel: true }
      const tela = await montar()
      expect(botao(tela, 'Calcular aqui').attributes('disabled')).toBeDefined()
      expect(tela.text()).toContain('precisa de rua e cidade nos dois')
    })

    it('número já consultado antes diz DE QUANDO é', async () => {
      respostas['/api/rotas/km'] = { km_ida: 10, km: 20, ida_e_volta: true,
                                     do_cache: true,
                                     consultado_em: '2026-09-01T10:00:00-03:00' }
      const tela = await montar()
      await botao(tela, 'Calcular aqui').trigger('click')
      await new Promise((r) => setTimeout(r, 0))
      await tela.vm.$nextTick()
      /* Rota muda (obra, estrada nova): número sem data é afirmação sem
         prazo -- a régua da migração 076. */
      expect(tela.text()).toContain('já consultado em')
    })
  })
})
