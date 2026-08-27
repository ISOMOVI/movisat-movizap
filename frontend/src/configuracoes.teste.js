/**
 * @vitest-environment jsdom
 *
 * A tela de Configurações e a escada da IA — 27/08.
 *
 * 🚨 POR QUE ISTO MONTA O COMPONENTE DE VERDADE. O MIOLO registra três placares
 * verdes que não viram a tela quebrada: 677 com o painel inteiro derrubado,
 * 1.322 com a trava só no comentário, 1.568 com o menu lateral morto. Um teste
 * que leia o `.vue` como texto entraria na mesma lista. Aqui o componente é
 * montado, a API é dublada e o que se afirma é o que ficou RENDERIZADO.
 *
 * 🚨 O DEFEITO QUE ISTO DEFENDE. Em 26/08 o usuário disse "não tem botão nenhum
 * ali, nem por canal, nem por prompt e nem por tipo" — e o journal mostrou que
 * ele estava com o bundle certo. Os botões existiam, espalhados em três telas,
 * e um deles SUMIA quando não podia ser usado. A regra nova é que nenhum degrau
 * some: travado fica cinza, com o motivo escrito.
 *
 * ⚠️ O ambiente jsdom é declarado NO ARQUIVO, não na configuração global: os
 * dois testes que já existem (avatar, destaque) são função pura e continuam
 * rodando em `node`, como sempre rodaram.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

import EscadaIa from './componentes/EscadaIa.vue'

/* O estado que a API devolveria. Cada teste mexe só no que lhe interessa. */
let respostas

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => Promise.resolve(respostas[rota]),
    put: () => Promise.resolve({ ok: true }),
    post: () => Promise.resolve({ ok: true }),
  },
  ErroDeApi: class ErroDeApi extends Error {},
}))

function estadoPadrao() {
  return {
    '/api/ia/prompt': {
      versao_ativa: null,
      total_versoes: 0,
      canais: [],
      motor_existe: false,
      motor: {
        disponivel: false,
        motivo: 'Nenhuma versão de prompt foi publicada ainda. Escreva '
          + 'e publique o prompt na CFG_2.1 antes de ligar a IA.',
      },
    },
    '/api/automacao': {
      tipos: [
        { relacao: 'cliente', ia_ligada: false, contatos: 1750 },
        { relacao: 'fornecedor', ia_ligada: false, contatos: 120 },
      ],
      ia_disponivel: false,
    },
    '/api/canais': [
      { id: 86, nome: 'Atendimento', tipo: 'atendimento', ativo: true, ia_ligada: false },
      { id: 478, nome: 'Informativos', tipo: 'informativo', ativo: true, ia_ligada: false },
    ],
  }
}

async function montar() {
  const w = mount(EscadaIa)
  await new Promise((r) => setTimeout(r, 0))
  await w.vm.$nextTick()
  return w
}

beforeEach(() => { respostas = estadoPadrao() })

describe('a escada da IA', () => {
  it('mostra os QUATRO degraus mesmo com tudo travado', async () => {
    // 🚨 É o coração da mudança. Antes, o degrau que não podia ser usado
    // sumia da tela -- inclusive o que levava ao prompt.
    const w = await montar()
    const degraus = w.findAll('.degrau')
    expect(degraus).toHaveLength(4)
  })

  it('nenhum degrau fica sem botão', async () => {
    const w = await montar()
    for (const degrau of w.findAll('.degrau')) {
      expect(degrau.find('button').exists()).toBe(true)
    }
  })

  it('o degrau travado diz POR QUE, e não só fica cinza', async () => {
    // Botão cinza sem explicação é o mesmo que botão ausente: ninguém
    // descobre o que fazer para destravá-lo.
    const w = await montar()
    const texto = w.text()
    expect(texto).toContain('Nenhuma versão de prompt foi publicada')
  })

  it('sem prompt, o passo 1 continua clicável — é ele que destrava o resto', async () => {
    const w = await montar()
    const passo1 = w.findAll('.degrau')[0]
    expect(passo1.find('button').attributes('disabled')).toBeUndefined()
    expect(passo1.text()).toContain('Escrever o prompt')
  })

  it('sem prompt, ensaiar e ligar ficam travados', async () => {
    const w = await montar()
    const [, passo2, passo3, passo4] = w.findAll('.degrau')
    expect(passo2.find('button').attributes('disabled')).toBeDefined()
    expect(passo3.find('button').attributes('disabled')).toBeDefined()
    expect(passo4.find('button').attributes('disabled')).toBeDefined()
  })

  it('com prompt publicado mas nenhum tipo ligado, o passo 4 explica o que falta', async () => {
    // 🚨 As duas travas são separadas de propósito: ligar o canal sem nenhum
    // tipo ligado não faria a IA responder ninguém.
    respostas['/api/ia/prompt'].versao_ativa = { id: 1, versao: 3, autor_nome: 'Iago' }
    respostas['/api/ia/prompt'].motor_existe = true
    respostas['/api/ia/prompt'].motor = { disponivel: true }
    respostas['/api/automacao'].ia_disponivel = true

    const w = await montar()
    const passo4 = w.findAll('.degrau')[3]
    expect(passo4.find('button').attributes('disabled')).toBeDefined()
    expect(passo4.text()).toContain('nenhum tipo de contato ligado')
  })

  it('com tudo pronto, o passo 4 destrava e oferece LIGAR', async () => {
    respostas['/api/ia/prompt'].versao_ativa = { id: 1, versao: 3, autor_nome: 'Iago' }
    respostas['/api/ia/prompt'].motor_existe = true
    respostas['/api/ia/prompt'].motor = { disponivel: true }
    respostas['/api/automacao'].tipos[0].ia_ligada = true

    const w = await montar()
    const passo4 = w.findAll('.degrau')[3]
    expect(passo4.find('button').attributes('disabled')).toBeUndefined()
    expect(passo4.text()).toContain('Ligar a IA')
  })

  it('com a IA no ar, DESLIGAR nunca fica travado', async () => {
    // ⚠️ É exatamente quando o motor está ruim que alguém quer desligar. A
    // regra vem do backend e a tela não pode contradizê-la.
    respostas['/api/canais'][0].ia_ligada = true
    const w = await montar()
    const passo4 = w.findAll('.degrau')[3]
    expect(passo4.find('button').attributes('disabled')).toBeUndefined()
    expect(passo4.text()).toContain('Desligar a IA')
  })

  it('o passo 3 mostra quantas pessoas os tipos ligados alcançam', async () => {
    // Sem o número, ligar "Cliente" parece inofensivo e atinge 1.750 pessoas.
    respostas['/api/automacao'].tipos[0].ia_ligada = true
    const w = await montar()
    expect(w.findAll('.degrau')[2].text()).toContain('1750')
  })

  it('não oferece IA no canal de informativo', async () => {
    // O informativo é disparo, não conversa, e a rota recusa. A tela não pode
    // oferecer o que o backend nega.
    const w = await montar()
    expect(w.text()).not.toContain('Informativos')
  })
})
