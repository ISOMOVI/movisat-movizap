/**
 * @vitest-environment jsdom
 *
 * A aba Ligações (LIG_1.1, 15/10) ABRE e diz a verdade?
 *
 * 🚨 SUITE VERDE NÃO PROVA QUE A TELA ABRE (`M9`). E aqui há uma segunda
 * coisa a provar, que é a que o usuário cobra: a aba mostra só as ligações de
 * quem tem agente instalado, e precisa DIZER isso -- senão quem não tem
 * agente parece não ter ligado, e tela que mente é defeito.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

let respostas
let gets

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      gets.push(rota)
      const chave = Object.keys(respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? respostas[chave] : {})
    },
    post: () => Promise.resolve({ ok: true }),
    put: () => Promise.resolve({ ok: true }),
    del: () => Promise.resolve({ ok: true }),
  },
  pedirBlob: () => Promise.resolve(new Blob(['x'])),
  definirToken: () => {},
  temToken: () => true,
  quandoPerderSessao: () => {},
  ErroDeApi: class ErroDeApi extends Error {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, params: {} }),
  useRouter: () => ({ replace: () => {}, push: () => {} }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('./estado/sessao.js', () => ({
  sessao: { nome: 'Fulano de Tal', telas: [], owner: true },
  sair: () => {},
}))

import Ligacoes from './telas/Ligacoes.vue'

const AGENTES = {
  agentes: [
    { atendente_id: 1, nome: 'Iago', ramal: '3404', agente_id: 17,
      ultimo_contato_em: '2026-10-15T09:33:04-03:00', ultima_versao: '0.4',
      ligacoes: 28, pendentes: 0, rec: 'ligado' },
    { atendente_id: 3, nome: 'Ludmila', ramal: '3348', agente_id: 18,
      ultimo_contato_em: '2026-10-19T08:47:58-03:00', ultima_versao: '0.4',
      ligacoes: 30, pendentes: 0, rec: 'desligado' },
    { atendente_id: 4, nome: 'Erika', ramal: '3401', agente_id: 19,
      ultimo_contato_em: null, ligacoes: 0, pendentes: 0, rec: 'desconhecido' },
    { atendente_id: 2, nome: 'Claudia', ramal: null, agente_id: null,
      ultimo_contato_em: null, ligacoes: 0, rec: null },
  ],
}

const UMA = {
  itens: [
    {
      id: 10, inicio: '2026-10-15T09:00:00-03:00', sentido: 'feita',
      situacao: 'Chamada encerrada', duracao_s: 95, ramal: '3404',
      numero_bruto: '5518998116168', telefone_e164: '+5518998116168',
      atendente_id: 1, atendente: 'Iago',
      gravacoes: [{ id: 99, bytes: 1048576, nome: 'a.mp3' }],
      clientes: [
        { id: 5, nome: 'Pastelaria Velasco', contato_nome: 'Seu Zé', ativo: true },
        { id: 6, nome: 'Velasco Transportes', contato_nome: 'Seu Zé', ativo: true },
      ],
    },
    {
      id: 11, inicio: '2026-10-14T18:00:00-03:00', sentido: 'perdida',
      situacao: 'Cancelada', duracao_s: 0, ramal: '3404',
      numero_bruto: '08000028000', telefone_e164: null,
      atendente_id: 1, atendente: 'Iago', gravacoes: [], clientes: [],
    },
  ],
  total: 2, pagina: 1, por_pagina: 50, paginas: 1,
  por_sentido: { feita: 1, recebida: 0, perdida: 1 },
}

async function montar() {
  const tela = mount(Ligacoes)
  await new Promise((r) => setTimeout(r, 0))
  await tela.vm.$nextTick()
  return tela
}

describe('A aba Ligações', () => {
  beforeEach(() => {
    gets = []
    respostas = { '/api/ligacoes/agentes': AGENTES, '/api/ligacoes': UMA }
  })

  it('abre e mostra as ligações', async () => {
    const tela = await montar()
    const texto = tela.text()
    expect(texto).toContain('Ligações')
    expect(texto).toContain('+5518998116168')
    expect(texto).toContain('Iago')
    expect(texto).toContain('2 ligações')
  })

  it('diz quem tem agente e NOMEIA quem está de fora', async () => {
    const tela = await montar()
    const texto = tela.text()
    expect(texto).toContain('3 de 4')
    expect(texto).toContain('Sem agente')
    expect(texto).toContain('Claudia')
  })

  /* 🔴 19/10, pedido dele: *"inserindo no fim de cada linha de o REC
     está ativado ou não"*. Medido no dia: 4 dos 5 PCs com agente estavam com a
     gravação desligada, e a aba dizia "30 ligações" sem dizer que nenhuma delas
     tinha áudio. 🚨 O terceiro estado é o que importa: PC que nunca falou não
     recebe "ligado" de graça. */
  it('diz o REC de cada PC, e não inventa o de quem nunca falou', async () => {
    const tela = await montar()
    const linhas = tela.findAll('.cobertura__lista li').map((l) => l.text())
    expect(linhas.find((t) => t.includes('Iago'))).toContain('REC ligado')
    expect(linhas.find((t) => t.includes('Ludmila'))).toContain('REC desligado')
    expect(linhas.find((t) => t.includes('Erika'))).toContain('REC não informado')
  })

  it('quem não tem agente não ganha linha de REC nenhuma', async () => {
    const tela = await montar()
    const linhas = tela.findAll('.cobertura__lista li').map((l) => l.text())
    expect(linhas.some((t) => t.includes('Claudia'))).toBe(false)
    expect(tela.text()).toContain('Sem agente')
  })

  it('número em duas empresas mostra a primeira e o +1, sem calar a outra', async () => {
    const tela = await montar()
    expect(tela.text()).toContain('Pastelaria Velasco')
    expect(tela.text()).toContain('+1')
  })

  it('número sem cadastro aparece como "sem cadastro", não em branco', async () => {
    const tela = await montar()
    expect(tela.text()).toContain('sem cadastro')
  })

  it('ligação sem gravação diz que não tem', async () => {
    const tela = await montar()
    expect(tela.text()).toContain('sem gravação')
  })

  it('o filtro vai para a API no corpo da URL', async () => {
    const tela = await montar()
    gets = []
    tela.vm.sentido = 'perdida'
    tela.vm.numero = '9811'
    await tela.vm.$nextTick()
    await tela.find('.botao--primario').trigger('click')
    await new Promise((r) => setTimeout(r, 0))
    const chamada = gets.find((g) => g.startsWith('/api/ligacoes?'))
    expect(chamada).toContain('sentido=perdida')
    expect(chamada).toContain('numero=9811')
    expect(chamada).toContain('pagina=1')
  })

  it('o estado vazio repete que só aparece quem tem agente', async () => {
    respostas['/api/ligacoes'] = {
      itens: [], total: 0, pagina: 1, paginas: 1,
      por_sentido: { feita: 0, recebida: 0, perdida: 0 },
    }
    const tela = await montar()
    expect(tela.text()).toContain('Nenhuma ligação neste filtro')
    expect(tela.text()).toContain('agente instalado')
  })
})
