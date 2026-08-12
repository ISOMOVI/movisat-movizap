/* ============================================================================
   Testes de `partir` e `marcar` — o primeiro teste de JavaScript do projeto.
   ----------------------------------------------------------------------------
   O `05_Frontend` registrava "nenhum teste de frontend" como o maior buraco de
   cobertura do painel: o build pega import quebrado e erro de template, e não
   pega lógica. Estas duas funções são puras e sustentam o destaque da busca,
   inclusive a parte de segurança.
   ============================================================================ */
import { describe, expect, it } from 'vitest'

import { ANTES, DEPOIS, marcar, partir } from './destaque.js'

/** Junta os pedaços de volta, para conferir que nada se perdeu. */
const inteiro = (pedacos) => pedacos.map((p) => p.texto).join('')
/** Só o que foi marcado. */
const marcados = (pedacos) => pedacos.filter((p) => p.casa).map((p) => p.texto)

describe('marcar — dentro do balão', () => {
  it('marca a ocorrência e preserva o texto inteiro', () => {
    const r = marcar('o rastreador chegou', 'rastr')
    expect(inteiro(r)).toBe('o rastreador chegou')
    expect(marcados(r)).toEqual(['rastr'])
  })

  it('marca TODAS as ocorrências', () => {
    const r = marcar('rastreador e outro rastreador', 'rastreador')
    expect(marcados(r)).toHaveLength(2)
    expect(inteiro(r)).toBe('rastreador e outro rastreador')
  })

  it('ignora maiúscula e devolve o texto ORIGINAL no pedaço', () => {
    // 🚨 Devolver o termo digitado em vez do trecho original reescreveria a
    // mensagem do cliente na tela.
    const r = marcar('O RASTREADOR', 'rastreador')
    expect(marcados(r)).toEqual(['RASTREADOR'])
    expect(inteiro(r)).toBe('O RASTREADOR')
  })

  it('ocorrências coladas não se comem', () => {
    const r = marcar('aaaa', 'aa')
    expect(marcados(r)).toEqual(['aa', 'aa'])
    expect(inteiro(r)).toBe('aaaa')
  })

  it('termo no fim não deixa pedaço vazio sobrando', () => {
    const r = marcar('fim rastr', 'rastr')
    expect(inteiro(r)).toBe('fim rastr')
    expect(r.every((p) => p.texto.length > 0)).toBe(true)
  })

  it('termo que não existe devolve o texto inteiro, sem marca', () => {
    const r = marcar('bom dia', 'boleto')
    expect(inteiro(r)).toBe('bom dia')
    expect(marcados(r)).toEqual([])
  })

  it('texto vazio e termo vazio não quebram', () => {
    expect(inteiro(marcar('', 'x'))).toBe('')
    expect(inteiro(marcar('texto', ''))).toBe('texto')
    expect(inteiro(marcar(null, 'x'))).toBe('')
    expect(inteiro(marcar('texto', null))).toBe('texto')
  })

  it('termo só com espaço é tratado como vazio', () => {
    expect(marcados(marcar('texto qualquer', '   '))).toEqual([])
  })
})

describe('marcar — os caracteres que quebrariam uma regex', () => {
  // ⚠️ É por isto que a implementação usa indexOf e não RegExp: `(`, `+` e
  // `*` são metacaracteres, e um telefone digitado tem os três.
  it.each([
    ['ligar (18) 99811-6168 hoje', '(18)'],
    ['numero +5518998116168', '+55'],
    ['desconto de 10% * item', '* item'],
    ['array[0] deu erro', '[0]'],
    ['caminho c:\\temp\\x', '\\temp'],
    ['pergunta? sim.', '?'],
  ])('acha %j buscando %j', (texto, termo) => {
    const r = marcar(texto, termo)
    expect(marcados(r)).toEqual([termo])
    expect(inteiro(r)).toBe(texto)
  })
})

describe('marcar — segurança', () => {
  it('🚨 devolve HTML como TEXTO, em pedaços, nunca como marcação', () => {
    // O texto é o que o cliente escreveu. Se um dia alguém trocar isto por
    // `v-html`, este teste continua verde -- por isso ele afirma o CONTRATO:
    // o que sai são pedaços de string, e a soma é idêntica à entrada.
    const veneno = '<img src=x onerror="alert(1)"> rastreador'
    const r = marcar(veneno, 'rastreador')
    expect(inteiro(r)).toBe(veneno)
    expect(r.every((p) => typeof p.texto === 'string')).toBe(true)
    expect(marcados(r)).toEqual(['rastreador'])
  })

  it('termo com HTML também sai como texto', () => {
    const r = marcar('antes <script> depois', '<script>')
    expect(marcados(r)).toEqual(['<script>'])
    expect(inteiro(r)).toBe('antes <script> depois')
  })
})

describe('partir — prévia da lista', () => {
  it('recorta em volta do acerto, não do começo', () => {
    const enche = 'x'.repeat(200)
    const r = partir(`${enche} boleto ${enche}`, 'boleto')
    expect(marcados(r)).toEqual(['boleto'])
    // 🚨 O motivo de a conversa estar na lista tem de aparecer.
    expect(inteiro(r)).toContain('boleto')
    expect(inteiro(r).length).toBeLessThan(ANTES + DEPOIS + 20)
  })

  it('põe reticências dos dois lados quando corta', () => {
    const enche = 'x'.repeat(200)
    const r = partir(`${enche} boleto ${enche}`, 'boleto')
    expect(r[0].texto).toBe('…')
    expect(r[r.length - 1].texto).toBe('…')
  })

  it('não põe reticências quando não corta', () => {
    const r = partir('boleto vence hoje', 'boleto')
    expect(inteiro(r)).toBe('boleto vence hoje')
    expect(r.some((p) => p.texto === '…')).toBe(false)
  })

  it('acerto no começo não ganha reticência à esquerda', () => {
    const r = partir(`boleto ${'x'.repeat(200)}`, 'boleto')
    expect(r[0].texto).toBe('boleto')
    expect(r[0].casa).toBe(true)
  })

  it('marca só a PRIMEIRA ocorrência — é uma linha de prévia', () => {
    const r = partir('boleto e outro boleto', 'boleto')
    expect(marcados(r)).toHaveLength(1)
  })

  it('sem termo, devolve o começo cortado no tamanho da prévia', () => {
    const r = partir('y'.repeat(500), '')
    expect(inteiro(r)).toHaveLength(ANTES + DEPOIS)
    expect(marcados(r)).toEqual([])
  })

  it('termo que não existe não marca nada', () => {
    const r = partir('bom dia', 'boleto')
    expect(marcados(r)).toEqual([])
    expect(inteiro(r)).toBe('bom dia')
  })

  it('texto vazio ou nulo não quebra', () => {
    expect(inteiro(partir('', 'x'))).toBe('')
    expect(inteiro(partir(null, 'x'))).toBe('')
    expect(inteiro(partir(undefined, ''))).toBe('')
  })

  it('nenhum pedaço sai vazio', () => {
    // Pedaço vazio vira <span></span> à toa no DOM.
    for (const [t, q] of [
      ['boleto', 'boleto'],
      ['aboleto', 'boleto'],
      ['boletoz', 'boleto'],
      ['x'.repeat(300) + 'boleto', 'boleto'],
    ]) {
      expect(partir(t, q).every((p) => p.texto.length > 0)).toBe(true)
    }
  })

  it('respeita ANTES e DEPOIS', () => {
    const r = partir(`${'a'.repeat(100)}ALVO${'b'.repeat(100)}`, 'ALVO')
    const texto = inteiro(r).replaceAll('…', '')
    expect(texto).toBe(`${'a'.repeat(ANTES)}ALVO${'b'.repeat(DEPOIS)}`)
  })
})
