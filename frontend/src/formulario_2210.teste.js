/*
 * @vitest-environment jsdom
 *
 * ⚠️ O ambiente e declarado NO ARQUIVO, como nas outras suites de tela: o
 * `vite.config.js` deixa o global em `node`, que e mais rapido para os testes
 * que so leem codigo. Montar componente exige DOM.
 */

/* ============================================================================
   Formulários próprios — a regra condicional e o renderizador (22/10)
   ----------------------------------------------------------------------------
   🚨 OS CASOS DA REGRA SÃO OS MESMOS DO PYTHON: este arquivo lê
   `tests/casos_regras_formulario.json`, que `tests/teste_formularios.py`
   também lê. Servidor e navegador avaliam a MESMA estrutura, e duas
   implementações da mesma regra só convivem com um conjunto de casos em
   comum -- em 22/10 um `WHERE` copiado em dois lugares divergiu no mesmo dia.

   ⚠️ O que este arquivo NÃO cobre: a validação. Ela é do servidor, e está em
   `tests/teste_formularios.py`. Cobri-la aqui daria a impressão de que o
   navegador decide algo.
   ============================================================================ */
import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import { condicaoBate, visiveis } from './util/regras_formulario.js'
import CamposDoFormulario from './componentes/CamposDoFormulario.vue'

const CASOS = JSON.parse(readFileSync(
  '/home/claude/movizap_painel/tests/casos_regras_formulario.json', 'utf-8')).casos

describe('a regra condicional, pelos casos compartilhados com o Python', () => {
  for (const caso of CASOS) {
    it(caso.nome, () => {
      const vis = visiveis({ campos: caso.campos, regras: caso.regras }, caso.valores)
      expect([...vis].sort()).toEqual([...caso.visiveis].sort())
    })
  }

  it('operacao desconhecida nao bate (e nao explode)', () => {
    expect(condicaoBate({ target: 'A', operation: 'contem', value: 'x' }, { A: 'xis' }))
      .toBe(false)
  })
})

/* Um formulário de mentira com um campo de cada tipo que aparece nos 15. */
function campo(nome, tipo, extra = {}) {
  return {
    nome, tipo, rotulo: `Rotulo de ${nome}`, obrigatorio: false,
    multiplo: false, visivel: true, opcoes: [], ajuda: null, ...extra,
  }
}

describe('o renderizador desenha a definicao', () => {
  it('cada tipo ganha o controle certo', () => {
    const campos = [
      campo('texto', 'string'), campo('longo', 'text'),
      campo('numero', 'double'), campo('data', 'date'),
      campo('email', 'email'), campo('fone', 'phone'),
      campo('nome', 'name'), campo('sobrenome', 'last-name'),
      campo('meio', 'second-name'), campo('empresa', 'company-name'),
      campo('arquivo', 'file'), campo('produto', 'product'),
      campo('lista', 'list', { opcoes: [{ value: '1', label: 'Um' }] }),
    ]
    const tela = mount(CamposDoFormulario, {
      props: { campos, regras: [], valores: {} },
    })
    expect(tela.findAll('select')).toHaveLength(1)
    // `text` e `product` são os dois textos longos.
    expect(tela.findAll('textarea')).toHaveLength(2)
    expect(tela.find('input[type="file"]').exists()).toBe(true)
    expect(tela.find('input[type="email"]').exists()).toBe(true)
    expect(tela.find('input[type="tel"]').exists()).toBe(true)
    expect(tela.find('input[type="date"]').exists()).toBe(true)
    // 🚨 `double` é `text`, não `number`: o "CNPJ" do Bitrix é `double`, e
    // `number` no celular esconde o teclado com pontuação.
    expect(tela.find('input[type="number"]').exists()).toBe(false)
  })

  it('page e layout nao sao pergunta: viram separador', () => {
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [campo('pagina', 'page'), campo('traco', 'layout'),
                 campo('texto', 'string')],
        regras: [], valores: {},
      },
    })
    expect(tela.findAll('input')).toHaveLength(1)
    expect(tela.find('hr').exists()).toBe(true)
    expect(tela.findAll('label')).toHaveLength(1)
  })

  it('campo escondido por regra nao e desenhado, e aparece quando a regra bate', () => {
    const campos = [
      campo('gatilho', 'list', { opcoes: [{ value: '1704', label: 'Juridica' }] }),
      campo('cnpj', 'double', { visivel: false }),
    ]
    const regras = [{
      lista: [{
        condition: { target: 'gatilho', operation: '=', value: '1704' },
        action: { target: 'cnpj', type: 'show' },
      }],
    }]
    const valores = {}
    const tela = mount(CamposDoFormulario, { props: { campos, regras, valores } })
    expect(tela.findAll('input')).toHaveLength(0)

    const comValor = mount(CamposDoFormulario, {
      props: { campos, regras, valores: { gatilho: '1704' } },
    })
    expect(comValor.findAll('input')).toHaveLength(1)
  })

  it('campo travado fica desabilitado e DIZ por que', () => {
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [campo('empresa', 'company-name')],
        regras: [], valores: { empresa: 'Pastelaria Velasco' },
        travados: ['empresa'],
      },
    })
    expect(tela.find('input').attributes('disabled')).toBeDefined()
    // 🚨 Campo cinza SEM explicação parece defeito -- o precedente é o
    // ModalAgendar, que explica em vez de sumir.
    expect(tela.text()).toContain('Veio do cadastro desta conversa')
  })

  it('o obrigatorio aparece marcado, mas quem recusa e o servidor', () => {
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [campo('texto', 'string', { obrigatorio: true })],
        regras: [], valores: {},
      },
    })
    expect(tela.find('input').attributes('required')).toBeDefined()
  })
})
