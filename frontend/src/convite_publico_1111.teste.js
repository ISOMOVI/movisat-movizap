/**
 * @vitest-environment jsdom
 *
 * A PÁGINA PÚBLICA ABRE PRÉ-PREENCHIDA, QUANDO VEM DE UM CONVITE (11/11).
 *
 * 🔵 **Pedido dele:** formulários *"pré-preenchidos quando abertos pelo botão
 * dentro do chat"*.
 *
 * 🚨 **POR QUE ESTA TRAVA EXISTE.** O backend está provado por 34 travas em
 * Python e por chamada real de fora. O que **nenhuma** delas vê é a página
 * fazendo (ou não fazendo) o pedido e escrevendo nos campos — e "está no ar"
 * não é 200: o bundle pode estar publicado e o campo continuar vazio, que é
 * exatamente o defeito que ninguém percebe, porque campo vazio é o estado
 * normal.
 *
 * 🚨 **E a trava mais importante aqui é de NÃO-ACONTECIMENTO:** a página não
 * pode pedir nada quando não há bilhete, e não pode escrever nada quando o
 * convite é de outro formulário. Ambas passariam verdes num teste que só
 * olhasse o caso bom.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

import FormularioPublico from '../publico/FormularioPublico.vue'
import CamposDoFormulario from './componentes/CamposDoFormulario.vue'

/* A definição mínima que a página precisa, com os nomes do Suporte. */
const DEF = {
  slug: 'suporte',
  titulo: 'Suporte',
  formato: 'novo',
  campos: [
    { nome: 'COMPANY_TITLE', rotulo: 'Empresa', tipo: 'company-name',
      obrigatorio: true },
    { nome: 'CONTACT_PHONE', rotulo: 'Telefone', tipo: 'phone',
      obrigatorio: true },
    { nome: 'CONTACT_EMAIL', rotulo: 'E-mail', tipo: 'email',
      obrigatorio: true },
  ],
  regras: [],
  abertura: 'a123',
  desafio: null,
}

const VALORES = {
  COMPANY_TITLE: 'PASTELARIA VELASCO',
  CONTACT_PHONE: '+5518998116168',
  CONTACT_EMAIL: 'iago@movisat.com.br',
}

let pedidos = []

function responder(url) {
  pedidos.push(String(url))
  if (String(url).includes('/api/publico/convite/')) {
    const bilhete = String(url).split('/').pop()
    if (bilhete === 'vencido') {
      return Promise.resolve({ ok: false, status: 404,
                               json: () => Promise.resolve({}) })
    }
    if (bilhete === 'de-outro') {
      return Promise.resolve({ ok: true, status: 200,
                               json: () => Promise.resolve(
                                 { slug: 'rescisao', valores: VALORES }) })
    }
    if (bilhete === 'explode') {
      return Promise.reject(new Error('rede caiu'))
    }
    return Promise.resolve({ ok: true, status: 200,
                             json: () => Promise.resolve(
                               { slug: 'suporte', valores: VALORES }) })
  }
  if (String(url).includes('/api/publico/formulario/')) {
    return Promise.resolve({ ok: true, status: 200,
                             json: () => Promise.resolve(DEF) })
  }
  return Promise.resolve({ ok: true, status: 200,
                           json: () => Promise.resolve({}) })
}

function comUrl(busca) {
  /* ⚠️ A página lê o slug do CAMINHO e o bilhete da BUSCA, no momento em que o
     módulo monta. O jsdom não deixa trocar `location` direto, então o que se
     redefine é a propriedade. */
  delete window.location
  window.location = { pathname: '/f/suporte', search: busca, href: '' }
}

beforeEach(() => {
  pedidos = []
  vi.stubGlobal('fetch', vi.fn(responder))
  window.scrollTo = () => {}
})

afterEach(() => {
  vi.unstubAllGlobals()
})

async function montar(busca) {
  comUrl(busca)
  const tela = mount(FormularioPublico)
  await flushPromises()
  await flushPromises()
  return tela
}

/* 📏 MEDIDO, e e o motivo desta funcao existir: procurar o `<input>` nao
   serve aqui. Os campos nao tem atributo `name` (o `CamposDoFormulario`
   identifica cada entrada pelo `aria-label`), e com uma definicao mínima o
   componente nao desenha nenhuma entrada -- a primeira versao desta trava
   reprovou medindo "o campo nao existe", nao "o campo esta vazio".

   ⚠️ Entao o que se mede e o ESTADO DO FORMULARIO que a pagina entrega ao
   componente: e exatamente o que "pre-preenchido" quer dizer, e nao depende
   de como o campo e desenhado. Quem prova o DESENHO sao as travas do
   `CamposDoFormulario`, que ja existem. */
function estadoDoFormulario(tela) {
  const campos = tela.findComponent(CamposDoFormulario)
  expect(campos.exists()).toBe(true)
  return campos.props('valores')
}

function valorDe(tela, nome) {
  return estadoDoFormulario(tela)[nome]
}

describe('com bilhete, a pagina abre preenchida', () => {
  it('pede o convite e escreve nos campos', async () => {
    const tela = await montar('?c=umbilhete')
    expect(pedidos.some((u) => u.includes('/api/publico/convite/umbilhete')))
      .toBe(true)
    expect(valorDe(tela, 'COMPANY_TITLE')).toBe('PASTELARIA VELASCO')
    expect(valorDe(tela, 'CONTACT_PHONE')).toBe('+5518998116168')
    expect(valorDe(tela, 'CONTACT_EMAIL')).toBe('iago@movisat.com.br')
  })

  it('DIZ que preencheu', async () => {
    /* ⚠️ Campo preenchido sem explicação faz a pessoa achar que a Movisat já
       sabe mais do que sabe, ou que outra pessoa mexeu ali. */
    const tela = await montar('?c=umbilhete')
    expect(tela.text()).toContain('Já preenchemos o que sabemos')
  })
})

describe('sem bilhete, nada muda', () => {
  it('NAO pede convite nenhum', async () => {
    /* 🚨 Quem chega pelo site é o caso normal, e é a maioria. */
    await montar('')
    expect(pedidos.some((u) => u.includes('/convite/'))).toBe(false)
  })

  it('os campos ficam vazios e a pagina nao diz nada de convite', async () => {
    const tela = await montar('')
    expect(valorDe(tela, 'COMPANY_TITLE')).toBeUndefined()
    expect(tela.text()).not.toContain('Já preenchemos')
  })
})

describe('os tres jeitos de o convite nao servir', () => {
  it('vencido: abre VAZIA e em silencio', async () => {
    /* ⚠️ "Não deu para pré-preencher" assustaria quem só quer escrever um
       chamado. O silêncio é o desenho. */
    const tela = await montar('?c=vencido')
    expect(valorDe(tela, 'COMPANY_TITLE')).toBeUndefined()
    expect(tela.text()).not.toContain('Já preenchemos')
    expect(tela.text()).not.toContain('convite')
  })

  it('rede caiu: abre VAZIA e nao quebra a pagina', async () => {
    const tela = await montar('?c=explode')
    expect(valorDe(tela, 'COMPANY_TITLE')).toBeUndefined()
    /* E o formulário continua lá, utilizável. */
    expect(tela.findComponent(CamposDoFormulario).exists()).toBe(true)
  })

  it('convite de OUTRO formulario nao escreve NADA', async () => {
    /* 🚨 A trava que impede o pior caso: o link pode ter sido editado à mão, e
       sugerir o valor de um formulário no campo de outro escreveria dado no
       lugar errado. */
    const tela = await montar('?c=de-outro')
    expect(valorDe(tela, 'COMPANY_TITLE')).toBeUndefined()
    expect(valorDe(tela, 'CONTACT_PHONE')).toBeUndefined()
    expect(tela.text()).not.toContain('Já preenchemos')
  })
})
