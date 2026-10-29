/**
 * @vitest-environment jsdom
 *
 * Aviso de NOTA INTERNA (28/10): a régua de quando toca, e o balão próprio.
 *
 * 🔵 *"verifique se as notas internas tbm estao gerando notificacoes como
 * mensagens novas no movizap, se nao tiver - proponha para que sejam tbm"* e,
 * depois da proposta, *"somente daqui para frente, pode ajustar notific para
 * notas"*.
 *
 * 🚨 O QUE ESTE ARQUIVO PRENDE:
 *   · a nota NÃO gasta o teto de 4 do cliente, e o cliente não gasta o da nota
 *     -- são duas filas, e o teto existe para *"não sumir a atenção"*;
 *   · nota a mais numa conversa que JÁ tinha nota nova não toca de novo;
 *   · a conversa aberta e à vista não toca;
 *   · a primeira leitura (F5) nunca toca;
 *   · o balão da nota tem TÍTULO PRÓPRIO e `tag` própria -- "Nova mensagem"
 *     diria que o cliente falou, e foi um colega.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

import { decidirToque, decidirToqueNota, TETO } from './util/regraToque.js'

const nota = (id, quantas = 1) => ({
  conversa_id: id, quantas, nome: 'Zé', autor: 'Ana', trecho: 'x',
})

describe('decidirToqueNota — a régua do toque da nota', () => {
  it('primeira leitura nunca toca (senão todo F5 tocaria)', () => {
    const d = decidirToqueNota(null, { notas: [nota(1)] })
    expect(d.tocar).toBe(false)
    expect(d.motivo).toBe('primeira leitura')
  })

  it('nota nova em conversa que não tinha nota: toca, e diz qual', () => {
    const d = decidirToqueNota({ notas: [] }, { notas: [nota(7)] })
    expect(d.tocar).toBe(true)
    expect(d.motivo).toBe('nota nova')
    expect(d.notas.map((x) => x.conversa_id)).toEqual([7])
  })

  it('nota A MAIS na mesma conversa não toca de novo', () => {
    const d = decidirToqueNota({ notas: [nota(7, 1)] }, { notas: [nota(7, 4)] })
    expect(d.tocar).toBe(false)
    expect(d.motivo).toBe('nada novo')
  })

  it('a conversa aberta E à vista não toca', () => {
    expect(decidirToqueNota({ notas: [] }, { notas: [nota(7)] }, 7).tocar).toBe(false)
  })

  it('acima do teto de 4 conversas com nota, não toca', () => {
    const antes = { notas: [nota(1), nota(2), nota(3), nota(4)] }
    const depois = { notas: [nota(1), nota(2), nota(3), nota(4), nota(5)] }
    const d = decidirToqueNota(antes, depois)
    expect(d.tocar).toBe(false)
    expect(d.motivo).toBe('acima do teto')
  })

  it('no teto exato, ainda toca', () => {
    const antes = { notas: [nota(1), nota(2), nota(3)] }
    const depois = { notas: [nota(1), nota(2), nota(3), nota(4)] }
    expect(decidirToqueNota(antes, depois).tocar).toBe(true)
    expect(TETO).toBe(4)
  })

  it('sem notas na resposta, não estoura', () => {
    expect(decidirToqueNota({ notas: [] }, {}).tocar).toBe(false)
    expect(decidirToqueNota({}, { notas: [] }).tocar).toBe(false)
  })
})

describe('🚨 as duas filas são SEPARADAS', () => {
  it('nota não gasta o teto do cliente', () => {
    /* 4 conversas do cliente não lidas (no teto) + uma nota nova. A nota toca
       pela régua dela, e a do cliente não é afetada -- se fossem a mesma
       função, a nota teria estourado o teto e calado o cliente. */
    const assumidas = [1, 2, 3, 4].map((id) => ({ id, nao_lidas: 1 }))
    const antes = { donas: [1, 2, 3, 4], assumidas, notas: [] }
    const depois = { donas: [1, 2, 3, 4], assumidas, notas: [nota(99)] }
    expect(decidirToque(antes, depois).tocar).toBe(false)
    expect(decidirToqueNota(antes, depois).tocar).toBe(true)
  })

  it('e o contrário: mensagem do cliente não é lida como nota', () => {
    const antes = { donas: [5], assumidas: [{ id: 5, nao_lidas: 0 }], notas: [] }
    const depois = { donas: [5], assumidas: [{ id: 5, nao_lidas: 2 }], notas: [] }
    expect(decidirToque(antes, depois).tocar).toBe(true)
    expect(decidirToqueNota(antes, depois).tocar).toBe(false)
  })
})

describe('mostrarBalaoNota — o balão diz QUEM anotou', () => {
  let chamadas

  beforeEach(() => {
    chamadas = []
    class FalsaNotificacao {
      constructor(titulo, opcoes) {
        chamadas.push({ titulo, opcoes })
        this.onclick = null
      }
      close() {}
    }
    FalsaNotificacao.permission = 'granted'
    vi.stubGlobal('Notification', FalsaNotificacao)
    window.Notification = FalsaNotificacao
  })

  it('tem título próprio, e nunca "Nova mensagem"', async () => {
    const { mostrarBalaoNota } = await import('./util/balao.js')
    mostrarBalaoNota({
      conversa_id: 3, nome: 'Cliente X', autor: 'Ana', quantas: 1,
      trecho: 'confere o boleto',
    }, () => {})
    expect(chamadas).toHaveLength(1)
    expect(chamadas[0].titulo).not.toContain('Nova mensagem')
    expect(chamadas[0].titulo).toContain('Ana')
    expect(chamadas[0].titulo).toContain('Cliente X')
    expect(chamadas[0].opcoes.body).toBe('confere o boleto')
    // 🚨 `tag` própria: a nota NÃO substitui o balão da MENSAGEM da mesma conversa
    expect(chamadas[0].opcoes.tag).toBe('nota-3')
  })

  it('com mais de uma, diz quantas', async () => {
    const { mostrarBalaoNota } = await import('./util/balao.js')
    mostrarBalaoNota({
      conversa_id: 4, nome: 'Cliente Y', autor: 'Ana', quantas: 3,
      trecho: 'tres notas',
    }, () => {})
    expect(chamadas[0].titulo.startsWith('3 notas internas')).toBe(true)
  })
})
