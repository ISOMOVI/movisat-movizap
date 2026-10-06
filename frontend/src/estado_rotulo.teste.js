/**
 * @vitest-environment node
 *
 * 🔵 05/10: o rótulo do `offline` depende de contexto. Dentro do turno, o
 * offline automático (inatividade) é "Ausente"; fora do turno, ou escolhido à
 * mão, é "Fora do expediente". Os outros estados não mudam.
 */
import { describe, it, expect } from 'vitest'
import { rotuloDoEstado } from './util/estado.js'

describe('rotuloDoEstado — o offline tem dois significados', () => {
  it('offline automático DENTRO do turno = "Ausente"', () => {
    expect(rotuloDoEstado('offline', { automatico: true, emJornada: true })).toBe('Ausente')
  })

  it('offline automático FORA do turno = "fora do expediente"', () => {
    expect(rotuloDoEstado('offline', { automatico: true, emJornada: false })).toBe('fora do expediente')
  })

  it('offline ESCOLHIDO à mão (não automático) = "fora do expediente", mesmo no turno', () => {
    expect(rotuloDoEstado('offline', { automatico: false, emJornada: true })).toBe('fora do expediente')
  })

  it('sem flags, mantém o comportamento antigo', () => {
    expect(rotuloDoEstado('offline')).toBe('fora do expediente')
  })

  it('os outros estados não mudam', () => {
    expect(rotuloDoEstado('disponivel')).toBe('disponível')
    expect(rotuloDoEstado('ausente')).toBe('em pausa')
    expect(rotuloDoEstado('nao_perturbe')).toBe('não perturbe')
    expect(rotuloDoEstado('qualquer')).toBe('sem estado')
  })
})
